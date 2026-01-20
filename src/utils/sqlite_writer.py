import sqlite3
import json
from typing import Any, Dict, Optional, Set


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
                signblock_witness_hex TEXT,
                raw_block TEXT
            )
            """
        )
        cur.execute(
            """
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
                raw_tx TEXT,
                PRIMARY KEY (hash, "index")
            )
            """
        )
        cur.close()

        self._ensure_columns(
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
                "raw_block": "TEXT",
            },
        )
        self._ensure_columns(
            "transactions",
            {
                "txid": "TEXT",
                "wtxid": "TEXT",
                "withash": "TEXT",
                "tx_hex": "TEXT",
                "discount_virtual_size": "REAL",
                "discount_weight": "INTEGER",
                "node_fee": "TEXT",
                "raw_tx": "TEXT",
            },
        )
        return

    def _table_columns(self, table: str) -> Set[str]:
        cur = self.conn.cursor()
        cur.execute(f"PRAGMA table_info({table})")
        cols = {row[1] for row in cur.fetchall()}
        cur.close()
        return cols

    def _ensure_columns(self, table: str, columns: Dict[str, str]) -> None:
        existing = self._table_columns(table)
        cur = self.conn.cursor()
        for name, ctype in columns.items():
            if name in existing:
                continue
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ctype}")
        cur.close()

    def write_block(self, block: Dict[str, Any]) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO blocks (
                hash, number, timestamp, median_time, confirmations,
                size, stripped_size, weight,
                version, version_hex, merkle_root, nonce, bits,
                previous_block_hash, next_block_hash,
                transaction_count,
                signblock_challenge, signblock_witness_asm, signblock_witness_hex,
                raw_block
            ) VALUES (
                :hash, :number, :timestamp, :median_time, :confirmations,
                :size, :stripped_size, :weight,
                :version, :version_hex, :merkle_root, :nonce, :bits,
                :previous_block_hash, :next_block_hash,
                :transaction_count,
                :signblock_challenge, :signblock_witness_asm, :signblock_witness_hex,
                :raw_block
            )
            ON CONFLICT(hash) DO UPDATE SET
                number=excluded.number,
                timestamp=excluded.timestamp,
                median_time=excluded.median_time,
                confirmations=excluded.confirmations,
                size=excluded.size,
                stripped_size=excluded.stripped_size,
                weight=excluded.weight,
                version=excluded.version,
                version_hex=excluded.version_hex,
                merkle_root=excluded.merkle_root,
                nonce=excluded.nonce,
                bits=excluded.bits,
                previous_block_hash=excluded.previous_block_hash,
                next_block_hash=excluded.next_block_hash,
                transaction_count=excluded.transaction_count,
                signblock_challenge=excluded.signblock_challenge,
                signblock_witness_asm=excluded.signblock_witness_asm,
                signblock_witness_hex=excluded.signblock_witness_hex,
                raw_block=excluded.raw_block
            """,
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
                "transaction_count": block.get("transaction_count") or (block.get("n_tx") if block.get("n_tx") is not None else None),
                "signblock_challenge": block.get("signblock_challenge"),
                "signblock_witness_asm": block.get("signblock_witness_asm"),
                "signblock_witness_hex": block.get("signblock_witness_hex"),
                "raw_block": json.dumps(block.get("raw_block"), default=str) if block.get("raw_block") is not None else None,
            },
        )
        cur.close()

    def write_transaction(self, tx: Dict[str, Any]) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO transactions (
                hash, txid, wtxid, withash, tx_hex,
                "index", block_hash, block_number, block_timestamp,
                lock_time, size, virtual_size, discount_virtual_size,
                version, is_coinbase,
                input_count, output_count, input_value, output_value, fee,
                node_fee,
                inputs, outputs,
                weight, discount_weight, sigops,
                raw_tx
            ) VALUES (
                :hash, :txid, :wtxid, :withash, :tx_hex,
                :index, :block_hash, :block_number, :block_timestamp,
                :lock_time, :size, :virtual_size, :discount_virtual_size,
                :version, :is_coinbase,
                :input_count, :output_count, :input_value, :output_value, :fee,
                :node_fee,
                :inputs, :outputs,
                :weight, :discount_weight, :sigops,
                :raw_tx
            )
            ON CONFLICT(hash, "index") DO UPDATE SET
                txid=excluded.txid,
                wtxid=excluded.wtxid,
                withash=excluded.withash,
                tx_hex=excluded.tx_hex,
                block_hash=excluded.block_hash,
                block_number=excluded.block_number,
                block_timestamp=excluded.block_timestamp,
                lock_time=excluded.lock_time,
                size=excluded.size,
                virtual_size=excluded.virtual_size,
                discount_virtual_size=excluded.discount_virtual_size,
                version=excluded.version,
                is_coinbase=excluded.is_coinbase,
                input_count=excluded.input_count,
                output_count=excluded.output_count,
                input_value=excluded.input_value,
                output_value=excluded.output_value,
                fee=excluded.fee,
                node_fee=excluded.node_fee,
                inputs=excluded.inputs,
                outputs=excluded.outputs,
                weight=excluded.weight,
                discount_weight=excluded.discount_weight,
                sigops=excluded.sigops,
                raw_tx=excluded.raw_tx
            """,
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
                "node_fee": json.dumps(tx.get("node_fee"), default=str) if tx.get("node_fee") is not None else None,
                "inputs": json.dumps(tx.get("inputs", []), default=str),
                "outputs": json.dumps(tx.get("outputs", []), default=str),
                "raw_tx": json.dumps(tx.get("raw_tx"), default=str) if tx.get("raw_tx") is not None else None,
            },
        )
        cur.close()

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
