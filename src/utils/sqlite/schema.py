from __future__ import annotations

import sqlite3
from typing import Dict, Set

from .sql_files import sql_text


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(sql_text("schema.sql"))

    ensure_columns(
        conn,
        "blocks",
        {
            "median_time": "INTEGER",
            "confirmations": "INTEGER",
            "version_hex": "TEXT",
            "previous_block_hash": "TEXT",
            "next_block_hash": "TEXT",
            "signblock_challenge": "TEXT",
            "signblock_witness_asm": "TEXT",
            "signblock_witness_hex": "TEXT",
        },
    )
    ensure_columns(
        conn,
        "transactions",
        {
            "txid": "TEXT",
            "wtxid": "TEXT",
            "withash": "TEXT",
            "tx_hex": "TEXT",
            "discount_virtual_size": "REAL",
            "discount_weight": "INTEGER",
            "node_fee": "TEXT",
        },
    )


def table_columns(conn: sqlite3.Connection, table: str) -> Set[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = {row[1] for row in cur.fetchall()}
    cur.close()
    return cols


def ensure_columns(conn: sqlite3.Connection, table: str, columns: Dict[str, str]) -> None:
    existing = table_columns(conn, table)
    cur = conn.cursor()
    for name, ctype in columns.items():
        if name in existing:
            continue
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ctype}")
    cur.close()
