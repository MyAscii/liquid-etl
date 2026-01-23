from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict

from .schema import ensure_schema
from .sql_files import sql_text


class SQLiteWriter:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, isolation_level=None)
        ensure_schema(self.conn)

    def write_block(self, block: Dict[str, Any]) -> None:
        cur = self.conn.cursor()
        cur.execute(
            sql_text("insert_blocks.sql"),
            {
                "hash": block.get("hash") or block.get("item_id"),
                "number": block.get("number") or block.get("height"),
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
                "transaction_count": block.get("transaction_count")
                or (block.get("n_tx") if block.get("n_tx") is not None else None),
                "signblock_challenge": block.get("signblock_challenge"),
                "signblock_witness_asm": block.get("signblock_witness_asm"),
                "signblock_witness_hex": block.get("signblock_witness_hex"),
            },
        )
        cur.close()

    def write_transaction(self, tx: Dict[str, Any]) -> None:
        cur = self.conn.cursor()
        cur.execute(
            sql_text("insert_transactions.sql"),
            {
                "hash": tx.get("hash") or tx.get("item_id"),
                "txid": tx.get("txid"),
                "wtxid": tx.get("wtxid"),
                "withash": tx.get("withash"),
                "tx_hex": tx.get("tx_hex"),
                "index": tx.get("index", 0),
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
                    json.dumps(tx.get("node_fee"), default=str)
                    if tx.get("node_fee") is not None
                    else None
                ),
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
