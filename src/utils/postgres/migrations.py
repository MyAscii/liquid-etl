from __future__ import annotations

from typing import Any


def migrate_tables(cur: Any) -> None:
    legacy_blocks = _table_exists(cur, "blocks") and _table_has_column(cur, "blocks", "number")
    legacy_transactions = _table_exists(cur, "transactions") and _table_has_column(
        cur, "transactions", "tx_index"
    )

    if legacy_blocks and not _table_exists(cur, "blocks_legacy"):
        _rename_table(cur, "blocks", "blocks_legacy")
    if legacy_transactions and not _table_exists(cur, "transactions_legacy"):
        _rename_table(cur, "transactions", "transactions_legacy")

    if _table_exists(cur, "blocks_v2") and not _table_exists(cur, "blocks"):
        _rename_table(cur, "blocks_v2", "blocks")
    if _table_exists(cur, "transactions_v2") and not _table_exists(cur, "transactions"):
        _rename_table(cur, "transactions_v2", "transactions")
    if _table_exists(cur, "txins_v2") and not _table_exists(cur, "txins"):
        _rename_table(cur, "txins_v2", "txins")
    if _table_exists(cur, "txouts_v2") and not _table_exists(cur, "txouts"):
        _rename_table(cur, "txouts_v2", "txouts")


def _table_exists(cur: Any, name: str) -> bool:
    cur.execute("SELECT to_regclass(%s)", (f"public.{name}",))
    return cur.fetchone()[0] is not None


def _table_has_column(cur: Any, table: str, column: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
        LIMIT 1
        """,
        (table, column),
    )
    return cur.fetchone() is not None


def _rename_table(cur: Any, old: str, new: str) -> None:
    cur.execute(f"ALTER TABLE {old} RENAME TO {new}")

