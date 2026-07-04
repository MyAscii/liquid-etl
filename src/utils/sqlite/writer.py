from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, Iterable, Iterator

from .schema import ensure_schema
from .sql_files import sql_text


def _block_params(block: Dict[str, Any]) -> Dict[str, Any]:
    number = block.get("number")
    if number is None:
        number = block.get("height")
    tx_count = block.get("transaction_count")
    if tx_count is None:
        tx_count = block.get("n_tx")
    return {
        "hash": block.get("hash") or block.get("item_id"),
        "number": number,
        "timestamp": block.get("timestamp"),
        "median_time": block.get("median_time"),
        "confirmations": block.get("confirmations"),
        "size": block.get("size"),
        "stripped_size": block.get("stripped_size"),
        "weight": block.get("weight"),
        "version": block.get("version"),
        "version_hex": block.get("version_hex"),
        "merkle_root": block.get("merkle_root"),
        "nonce": block.get("nonce"),
        "bits": block.get("bits"),
        "previous_block_hash": block.get("previous_block_hash"),
        "next_block_hash": block.get("next_block_hash"),
        "transaction_count": tx_count,
        "signblock_challenge": block.get("signblock_challenge"),
        "signblock_witness_asm": block.get("signblock_witness_asm"),
        "signblock_witness_hex": block.get("signblock_witness_hex"),
    }


def _tx_params(tx: Dict[str, Any]) -> Dict[str, Any]:
    idx = tx.get("index")
    if idx is None:
        raise ValueError(
            f"transaction {tx.get('hash') or tx.get('txid')} has no 'index'; "
            "cannot key the SQLite (hash, index) primary key"
        )
    return {
        "hash": tx.get("hash") or tx.get("item_id"),
        "txid": tx.get("txid"),
        "wtxid": tx.get("wtxid"),
        "withash": tx.get("withash"),
        "tx_hex": tx.get("tx_hex"),
        "index": idx,
        "block_hash": tx.get("block_hash"),
        "block_number": tx.get("block_number"),
        "block_timestamp": tx.get("block_timestamp"),
        "lock_time": tx.get("lock_time"),
        "size": tx.get("size"),
        "virtual_size": tx.get("virtual_size"),
        "discount_virtual_size": tx.get("discount_virtual_size"),
        "weight": tx.get("weight"),
        "discount_weight": tx.get("discount_weight"),
        "sigops": tx.get("sigops"),
        "version": tx.get("version"),
        "is_coinbase": 1 if tx.get("is_coinbase") else 0,
        "input_count": tx.get("input_count"),
        "output_count": tx.get("output_count"),
        "input_value": tx.get("input_value"),
        "output_value": tx.get("output_value"),
        "fee": tx.get("fee"),
        "node_fee": (
            json.dumps(tx.get("node_fee"), default=str) if tx.get("node_fee") is not None else None
        ),
        "inputs": json.dumps(tx.get("inputs", []), default=str),
        "outputs": json.dumps(tx.get("outputs", []), default=str),
    }


class SQLiteWriter:
    def __init__(self, db_path: str):
        self.db_path = db_path
        # Deferred isolation so we control transaction boundaries (see batch()).
        self.conn = sqlite3.connect(db_path)
        self._apply_pragmas()
        ensure_schema(self.conn)
        self._in_batch = False

    def _apply_pragmas(self) -> None:
        # WAL + NORMAL sync makes writes durable-on-crash without an fsync per row;
        # busy_timeout avoids spurious "database is locked" under a concurrent reader.
        for pragma in (
            "PRAGMA journal_mode=WAL",
            "PRAGMA synchronous=NORMAL",
            "PRAGMA busy_timeout=5000",
        ):
            self.conn.execute(pragma)

    @contextmanager
    def batch(self) -> Iterator["SQLiteWriter"]:
        """Group many writes into a single committed transaction (one fsync)."""
        self._in_batch = True
        try:
            yield self
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise
        finally:
            self._in_batch = False

    def _maybe_commit(self) -> None:
        if not self._in_batch:
            self.conn.commit()

    def write_block(self, block: Dict[str, Any]) -> None:
        self.conn.execute(sql_text("insert_blocks.sql"), _block_params(block))
        self._maybe_commit()

    def write_blocks(self, blocks: Iterable[Dict[str, Any]]) -> None:
        params = [_block_params(b) for b in blocks]
        if not params:
            return
        self.conn.executemany(sql_text("insert_blocks.sql"), params)
        self._maybe_commit()

    def write_transaction(self, tx: Dict[str, Any]) -> None:
        self.conn.execute(sql_text("insert_transactions.sql"), _tx_params(tx))
        self._maybe_commit()

    def write_transactions(self, txs: Iterable[Dict[str, Any]]) -> None:
        params = [_tx_params(t) for t in txs]
        if not params:
            return
        self.conn.executemany(sql_text("insert_transactions.sql"), params)
        self._maybe_commit()

    def close(self) -> None:
        try:
            self.conn.commit()
        except Exception:
            pass
        try:
            self.conn.close()
        except Exception:
            pass
