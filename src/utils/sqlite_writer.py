import sqlite3
import json
from typing import Any, Dict, Optional


class SQLiteWriter:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, isolation_level=None)
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS blocks (
                hash TEXT PRIMARY KEY,
                number INTEGER,
                timestamp INTEGER,
                size INTEGER,
                stripped_size INTEGER,
                weight INTEGER,
                version INTEGER,
                merkle_root TEXT,
                nonce INTEGER,
                bits TEXT,
                transaction_count INTEGER
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                hash TEXT,
                "index" INTEGER,
                block_hash TEXT,
                block_number INTEGER,
                block_timestamp INTEGER,
                lock_time INTEGER,
                size INTEGER,
                virtual_size INTEGER,
                version INTEGER,
                is_coinbase INTEGER,
                input_count INTEGER,
                output_count INTEGER,
                input_value TEXT,
                output_value TEXT,
                fee TEXT,
                inputs TEXT,
                outputs TEXT,
                PRIMARY KEY (hash, "index")
            )
            """
        )
        cur.close()

    def write_block(self, block: Dict[str, Any]) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT OR IGNORE INTO blocks (
                hash, number, timestamp, size, stripped_size, weight,
                version, merkle_root, nonce, bits, transaction_count
            ) VALUES (
                :hash, :number, :timestamp, :size, :stripped_size, :weight,
                :version, :merkle_root, :nonce, :bits, :transaction_count
            )
            """,
            {
                "hash": block.get("hash") or block.get("item_id"),
                "number": block.get("number") or block.get("height"),
                "timestamp": block.get("timestamp"),
                "size": block.get("size"),
                "stripped_size": block.get("stripped_size"),
                "weight": block.get("weight"),
                "version": block.get("version"),
                "merkle_root": block.get("merkle_root"),
                "nonce": block.get("nonce"),
                "bits": block.get("bits"),
                "transaction_count": block.get("transaction_count") or (block.get("n_tx") if block.get("n_tx") is not None else None),
            },
        )
        cur.close()

    def write_transaction(self, tx: Dict[str, Any]) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT OR IGNORE INTO transactions (
                hash, "index", block_hash, block_number, block_timestamp,
                lock_time, size, virtual_size, version, is_coinbase,
                input_count, output_count, input_value, output_value, fee,
                inputs, outputs
            ) VALUES (
                :hash, :index, :block_hash, :block_number, :block_timestamp,
                :lock_time, :size, :virtual_size, :version, :is_coinbase,
                :input_count, :output_count, :input_value, :output_value, :fee,
                :inputs, :outputs
            )
            """,
            {
                "hash": tx.get("hash") or tx.get("item_id"),
                "index": tx.get("index", 0),
                "block_hash": tx.get("block_hash"),
                "block_number": tx.get("block_number"),
                "block_timestamp": tx.get("block_timestamp"),
                "lock_time": tx.get("lock_time"),
                "size": tx.get("size"),
                "virtual_size": tx.get("virtual_size"),
                "version": tx.get("version"),
                "is_coinbase": 1 if tx.get("is_coinbase") else 0,
                "input_count": tx.get("input_count"),
                "output_count": tx.get("output_count"),
                "input_value": tx.get("input_value"),
                "output_value": tx.get("output_value"),
                "fee": tx.get("fee"),
                "inputs": json.dumps(tx.get("inputs", []), default=str),
                "outputs": json.dumps(tx.get("outputs", []), default=str),
            },
        )
        cur.close()

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass