from __future__ import annotations

import json
import re
from contextlib import contextmanager
from typing import Any, Dict, Iterable, Iterator, List, Optional

from .coercion import coerce_block_row, coerce_tx_rows
from .migrations import migrate_tables
from .schema import ensure_schema
from .sql_files import sql_text


class PostgresWriter:
    def __init__(self, dsn: str, *, conflict_strategy: str = "update", fast_local: bool = False):
        self.dsn = dsn
        try:
            import psycopg
        except Exception as e:
            raise RuntimeError(
                "psycopg not installed; install with pip install -e .[postgres]"
            ) from e
        self.conn = psycopg.connect(dsn, autocommit=True)
        if fast_local:
            with self.conn.cursor() as cur:
                cur.execute("SET synchronous_commit TO OFF")
        self._ensure_schema()
        self._insert_blocks_sql = _apply_conflict_strategy(
            sql_text("insert_blocks.sql"), conflict_strategy
        )
        self._insert_transactions_sql = _apply_conflict_strategy(
            sql_text("insert_transactions.sql"), conflict_strategy
        )
        self._insert_txins_sql = _apply_conflict_strategy(
            sql_text("insert_txins.sql"), conflict_strategy
        )
        self._insert_txouts_sql = _apply_conflict_strategy(
            sql_text("insert_txouts.sql"), conflict_strategy
        )

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def batch(self) -> Iterator["PostgresWriter"]:
        """Group a block and its transactions into a single committed transaction."""
        with self.conn.transaction():
            yield self

    def _ensure_schema(self) -> None:
        with self.conn.cursor() as cur:
            migrate_tables(cur)
            ensure_schema(cur)

    def get_max_block_height(self) -> Optional[int]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT MAX(height) FROM blocks")
            row = cur.fetchone()
            if row and row[0] is not None:
                return int(row[0])
            return None

    def write_bundle(
        self,
        block_row: Dict[str, Any],
        tx_rows: List[Dict[str, Any]],
        txin_rows: List[Dict[str, Any]],
        txout_rows: List[Dict[str, Any]],
    ) -> None:
        with self.conn.transaction():
            self.write_blocks([block_row])
            self.write_transactions(tx_rows)
            self.write_txins(txin_rows)
            self.write_txouts(txout_rows)

    def write_chunk(
        self,
        block_rows: List[Dict[str, Any]],
        tx_rows: List[Dict[str, Any]],
        txin_rows: List[Dict[str, Any]],
        txout_rows: List[Dict[str, Any]],
    ) -> None:
        with self.conn.transaction():
            self.write_blocks(block_rows)
            self.write_transactions(tx_rows)
            self.write_txins(txin_rows)
            self.write_txouts(txout_rows)

    def write_block(self, block: Dict[str, Any]) -> None:
        row = coerce_block_row(block)
        with self.conn.transaction():
            self.write_blocks([row])

    def write_transaction(self, tx: Dict[str, Any]) -> None:
        tx_row, txins, txouts = coerce_tx_rows(tx)
        with self.conn.transaction():
            self.write_transactions([tx_row])
            if txins:
                self.write_txins(txins)
            if txouts:
                self.write_txouts(txouts)

    def write_blocks(self, blocks: Iterable[Dict[str, Any]]) -> None:
        payloads = []
        for b in blocks:
            payloads.append(
                {
                    **b,
                    "txids": (
                        json.dumps(b.get("txids"), default=str)
                        if b.get("txids") is not None
                        else None
                    ),
                }
            )
        if not payloads:
            return
        with self.conn.cursor() as cur:
            cur.executemany(
                self._insert_blocks_sql,
                payloads,
            )

    def write_transactions(self, txs: Iterable[Dict[str, Any]]) -> None:
        payloads = []
        for t in txs:
            payloads.append(
                {
                    **t,
                    "fee_by_asset": (
                        json.dumps(t.get("fee_by_asset"), default=str)
                        if t.get("fee_by_asset") is not None
                        else None
                    ),
                    "explicit_in_by_asset": (
                        json.dumps(t.get("explicit_in_by_asset"), default=str)
                        if t.get("explicit_in_by_asset") is not None
                        else None
                    ),
                    "explicit_out_by_asset": (
                        json.dumps(t.get("explicit_out_by_asset"), default=str)
                        if t.get("explicit_out_by_asset") is not None
                        else None
                    ),
                }
            )
        if not payloads:
            return
        with self.conn.cursor() as cur:
            cur.executemany(
                self._insert_transactions_sql,
                payloads,
            )

    def write_txins(self, txins: Iterable[Dict[str, Any]]) -> None:
        payloads = []
        for i in txins:
            payloads.append(
                {
                    **i,
                    "txinwitness": (
                        json.dumps(i.get("txinwitness"), default=str)
                        if i.get("txinwitness") is not None
                        else None
                    ),
                    "pegin_witness": (
                        json.dumps(i.get("pegin_witness"), default=str)
                        if i.get("pegin_witness") is not None
                        else None
                    ),
                }
            )
        if not payloads:
            return
        with self.conn.cursor() as cur:
            cur.executemany(
                self._insert_txins_sql,
                payloads,
            )

    def write_txouts(self, txouts: Iterable[Dict[str, Any]]) -> None:
        payloads = [dict(o) for o in txouts]
        if not payloads:
            return
        with self.conn.cursor() as cur:
            cur.executemany(
                self._insert_txouts_sql,
                payloads,
            )


def _apply_conflict_strategy(sql: str, strategy: str) -> str:
    normalized = str(strategy).strip().lower()
    if normalized == "update":
        return sql
    if normalized == "ignore":
        return _rewrite_upsert_to_do_nothing(sql)
    raise ValueError(f"Unsupported conflict strategy: {strategy}")


def _rewrite_upsert_to_do_nothing(sql: str) -> str:
    m = re.search(r"ON\s+CONFLICT\s*\(([^)]+)\)\s*DO\s+UPDATE\s+SET", sql, flags=re.IGNORECASE)
    if not m:
        raise ValueError("SQL does not contain an ON CONFLICT DO UPDATE clause")
    target = m.group(1).strip()
    prefix = sql[: m.start()].rstrip()
    return f"{prefix}\nON CONFLICT ({target}) DO NOTHING"
