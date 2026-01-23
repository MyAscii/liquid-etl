from __future__ import annotations

import sqlite3
from typing import Dict, Set


def ensure_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS blocks (
            hash TEXT PRIMARY KEY,
            number INTEGER,
            timestamp INTEGER,
            median_time INTEGER,
            confirmations INTEGER,
            size INTEGER,
            stripped_size INTEGER,
            weight INTEGER,
            version INTEGER,
            version_hex TEXT,
            merkle_root TEXT,
            nonce INTEGER,
            bits TEXT,
            previous_block_hash TEXT,
            next_block_hash TEXT,
            transaction_count INTEGER,
            signblock_challenge TEXT,
            signblock_witness_asm TEXT,
            signblock_witness_hex TEXT
        )
        """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            hash TEXT,
            txid TEXT,
            wtxid TEXT,
            withash TEXT,
            tx_hex TEXT,
            "index" INTEGER,
            block_hash TEXT,
            block_number INTEGER,
            block_timestamp INTEGER,
            lock_time INTEGER,
            size INTEGER,
            virtual_size INTEGER,
            discount_virtual_size REAL,
            weight INTEGER,
            discount_weight INTEGER,
            sigops INTEGER,
            version INTEGER,
            is_coinbase INTEGER,
            input_count INTEGER,
            output_count INTEGER,
            input_value TEXT,
            output_value TEXT,
            fee TEXT,
            node_fee TEXT,
            inputs TEXT,
            outputs TEXT,
            PRIMARY KEY (hash, "index")
        )
        """)
    cur.close()

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
