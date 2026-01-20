from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Dict, Iterable, Optional


class PostgresWriter:
    def __init__(self, dsn: str):
        self.dsn = dsn
        try:
            import psycopg
        except Exception as e:
            raise RuntimeError("psycopg not installed; install with pip install -e .[postgres]") from e

        self._psycopg = psycopg
        self.conn = psycopg.connect(dsn, autocommit=True)
        self._init_schema()

    def _block_payload(self, block: Dict[str, Any]) -> Dict[str, Any]:
        return {
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
            "raw_block": json.dumps(block.get("raw_block"), default=str) if block.get("raw_block") is not None else None,
        }

    def _tx_payload(self, tx: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "hash": tx.get("hash") or tx.get("item_id"),
            "tx_index": tx.get("index", 0),
            "txid": tx.get("txid"),
            "wtxid": tx.get("wtxid"),
            "withash": tx.get("withash"),
            "tx_hex": tx.get("tx_hex"),
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
            "is_coinbase": bool(tx.get("is_coinbase")),
            "input_count": tx.get("input_count"),
            "output_count": tx.get("output_count"),
            "input_value": self._to_decimal(tx.get("input_value")),
            "output_value": self._to_decimal(tx.get("output_value")),
            "fee": self._to_decimal(tx.get("fee")),
            "node_fee_json": json.dumps(tx.get("node_fee"), default=str) if tx.get("node_fee") is not None else None,
            "inputs": json.dumps(tx.get("inputs", []), default=str),
            "outputs": json.dumps(tx.get("outputs", []), default=str),
            "raw_tx": json.dumps(tx.get("raw_tx"), default=str) if tx.get("raw_tx") is not None else None,
        }

    def _init_schema(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS blocks (
                    hash TEXT PRIMARY KEY,
                    number BIGINT,
                    timestamp BIGINT,
                    median_time BIGINT,
                    confirmations BIGINT,
                    size BIGINT,
                    stripped_size BIGINT,
                    weight BIGINT,
                    version BIGINT,
                    version_hex TEXT,
                    merkle_root TEXT,
                    nonce BIGINT,
                    bits TEXT,
                    previous_block_hash TEXT,
                    next_block_hash TEXT,
                    transaction_count BIGINT,
                    signblock_challenge TEXT,
                    signblock_witness_asm TEXT,
                    signblock_witness_hex TEXT,
                    raw_block JSONB
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    hash TEXT NOT NULL,
                    tx_index INTEGER NOT NULL,
                    txid TEXT,
                    wtxid TEXT,
                    withash TEXT,
                    tx_hex TEXT,
                    block_hash TEXT,
                    block_number BIGINT,
                    block_timestamp BIGINT,
                    lock_time BIGINT,
                    size BIGINT,
                    virtual_size BIGINT,
                    discount_virtual_size DOUBLE PRECISION,
                    weight BIGINT,
                    discount_weight BIGINT,
                    sigops BIGINT,
                    version BIGINT,
                    is_coinbase BOOLEAN,
                    input_count INTEGER,
                    output_count INTEGER,
                    input_value NUMERIC,
                    output_value NUMERIC,
                    fee NUMERIC,
                    node_fee_json JSONB,
                    inputs JSONB,
                    outputs JSONB,
                    raw_tx JSONB,
                    PRIMARY KEY (hash, tx_index)
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS transactions_block_number_idx ON transactions (block_number)")
            cur.execute("CREATE INDEX IF NOT EXISTS transactions_block_hash_idx ON transactions (block_hash)")
            cur.execute("ALTER TABLE blocks ADD COLUMN IF NOT EXISTS median_time BIGINT")
            cur.execute("ALTER TABLE blocks ADD COLUMN IF NOT EXISTS confirmations BIGINT")
            cur.execute("ALTER TABLE blocks ADD COLUMN IF NOT EXISTS version_hex TEXT")
            cur.execute("ALTER TABLE blocks ADD COLUMN IF NOT EXISTS previous_block_hash TEXT")
            cur.execute("ALTER TABLE blocks ADD COLUMN IF NOT EXISTS next_block_hash TEXT")
            cur.execute("ALTER TABLE blocks ADD COLUMN IF NOT EXISTS signblock_challenge TEXT")
            cur.execute("ALTER TABLE blocks ADD COLUMN IF NOT EXISTS signblock_witness_asm TEXT")
            cur.execute("ALTER TABLE blocks ADD COLUMN IF NOT EXISTS signblock_witness_hex TEXT")
            cur.execute("ALTER TABLE blocks ADD COLUMN IF NOT EXISTS raw_block JSONB")
            cur.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS txid TEXT")
            cur.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS wtxid TEXT")
            cur.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS withash TEXT")
            cur.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS tx_hex TEXT")
            cur.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS discount_virtual_size DOUBLE PRECISION")
            cur.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS discount_weight BIGINT")
            cur.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS node_fee_json JSONB")
            cur.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS raw_tx JSONB")

    def _to_decimal(self, v: Optional[Any]) -> Optional[Decimal]:
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        if isinstance(v, str):
            return Decimal(v) if v else None
        return Decimal(str(v))

    def write_block(self, block: Dict[str, Any]) -> None:
        payload = self._block_payload(block)
        with self.conn.cursor() as cur:
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
                    %(hash)s, %(number)s, %(timestamp)s, %(median_time)s, %(confirmations)s,
                    %(size)s, %(stripped_size)s, %(weight)s,
                    %(version)s, %(version_hex)s, %(merkle_root)s, %(nonce)s, %(bits)s,
                    %(previous_block_hash)s, %(next_block_hash)s,
                    %(transaction_count)s,
                    %(signblock_challenge)s, %(signblock_witness_asm)s, %(signblock_witness_hex)s,
                    %(raw_block)s::jsonb
                )
                ON CONFLICT (hash) DO UPDATE SET
                    number = EXCLUDED.number,
                    timestamp = EXCLUDED.timestamp,
                    median_time = EXCLUDED.median_time,
                    confirmations = EXCLUDED.confirmations,
                    size = EXCLUDED.size,
                    stripped_size = EXCLUDED.stripped_size,
                    weight = EXCLUDED.weight,
                    version = EXCLUDED.version,
                    version_hex = EXCLUDED.version_hex,
                    merkle_root = EXCLUDED.merkle_root,
                    nonce = EXCLUDED.nonce,
                    bits = EXCLUDED.bits,
                    previous_block_hash = EXCLUDED.previous_block_hash,
                    next_block_hash = EXCLUDED.next_block_hash,
                    transaction_count = EXCLUDED.transaction_count,
                    signblock_challenge = EXCLUDED.signblock_challenge,
                    signblock_witness_asm = EXCLUDED.signblock_witness_asm,
                    signblock_witness_hex = EXCLUDED.signblock_witness_hex,
                    raw_block = EXCLUDED.raw_block
                """,
                payload,
            )

    def write_blocks(self, blocks: Iterable[Dict[str, Any]]) -> None:
        payloads = [self._block_payload(b) for b in blocks]
        if not payloads:
            return
        with self.conn.transaction():
            with self.conn.cursor() as cur:
                cur.executemany(
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
                        %(hash)s, %(number)s, %(timestamp)s, %(median_time)s, %(confirmations)s,
                        %(size)s, %(stripped_size)s, %(weight)s,
                        %(version)s, %(version_hex)s, %(merkle_root)s, %(nonce)s, %(bits)s,
                        %(previous_block_hash)s, %(next_block_hash)s,
                        %(transaction_count)s,
                        %(signblock_challenge)s, %(signblock_witness_asm)s, %(signblock_witness_hex)s,
                        %(raw_block)s::jsonb
                    )
                    ON CONFLICT (hash) DO UPDATE SET
                        number = EXCLUDED.number,
                        timestamp = EXCLUDED.timestamp,
                        median_time = EXCLUDED.median_time,
                        confirmations = EXCLUDED.confirmations,
                        size = EXCLUDED.size,
                        stripped_size = EXCLUDED.stripped_size,
                        weight = EXCLUDED.weight,
                        version = EXCLUDED.version,
                        version_hex = EXCLUDED.version_hex,
                        merkle_root = EXCLUDED.merkle_root,
                        nonce = EXCLUDED.nonce,
                        bits = EXCLUDED.bits,
                        previous_block_hash = EXCLUDED.previous_block_hash,
                        next_block_hash = EXCLUDED.next_block_hash,
                        transaction_count = EXCLUDED.transaction_count,
                        signblock_challenge = EXCLUDED.signblock_challenge,
                        signblock_witness_asm = EXCLUDED.signblock_witness_asm,
                        signblock_witness_hex = EXCLUDED.signblock_witness_hex,
                        raw_block = EXCLUDED.raw_block
                    """,
                    payloads,
                )

    def write_transaction(self, tx: Dict[str, Any]) -> None:
        payload = self._tx_payload(tx)
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO transactions (
                    hash, tx_index, txid, wtxid, withash, tx_hex,
                    block_hash, block_number, block_timestamp,
                    lock_time, size, virtual_size, discount_virtual_size,
                    version, is_coinbase,
                    input_count, output_count, input_value, output_value, fee,
                    node_fee_json,
                    inputs, outputs,
                    weight, discount_weight, sigops,
                    raw_tx
                ) VALUES (
                    %(hash)s, %(tx_index)s, %(txid)s, %(wtxid)s, %(withash)s, %(tx_hex)s,
                    %(block_hash)s, %(block_number)s, %(block_timestamp)s,
                    %(lock_time)s, %(size)s, %(virtual_size)s, %(discount_virtual_size)s,
                    %(version)s, %(is_coinbase)s,
                    %(input_count)s, %(output_count)s, %(input_value)s, %(output_value)s, %(fee)s,
                    %(node_fee_json)s::jsonb,
                    %(inputs)s::jsonb, %(outputs)s::jsonb,
                    %(weight)s, %(discount_weight)s, %(sigops)s,
                    %(raw_tx)s::jsonb
                )
                ON CONFLICT (hash, tx_index) DO UPDATE SET
                    txid = EXCLUDED.txid,
                    wtxid = EXCLUDED.wtxid,
                    withash = EXCLUDED.withash,
                    tx_hex = EXCLUDED.tx_hex,
                    block_hash = EXCLUDED.block_hash,
                    block_number = EXCLUDED.block_number,
                    block_timestamp = EXCLUDED.block_timestamp,
                    lock_time = EXCLUDED.lock_time,
                    size = EXCLUDED.size,
                    virtual_size = EXCLUDED.virtual_size,
                    discount_virtual_size = EXCLUDED.discount_virtual_size,
                    weight = EXCLUDED.weight,
                    discount_weight = EXCLUDED.discount_weight,
                    sigops = EXCLUDED.sigops,
                    version = EXCLUDED.version,
                    is_coinbase = EXCLUDED.is_coinbase,
                    input_count = EXCLUDED.input_count,
                    output_count = EXCLUDED.output_count,
                    input_value = EXCLUDED.input_value,
                    output_value = EXCLUDED.output_value,
                    fee = EXCLUDED.fee,
                    node_fee_json = EXCLUDED.node_fee_json,
                    inputs = EXCLUDED.inputs,
                    outputs = EXCLUDED.outputs,
                    raw_tx = EXCLUDED.raw_tx
                """,
                payload,
            )

    def write_transactions(self, txs: Iterable[Dict[str, Any]]) -> None:
        payloads = [self._tx_payload(t) for t in txs]
        if not payloads:
            return
        with self.conn.transaction():
            with self.conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO transactions (
                        hash, tx_index, txid, wtxid, withash, tx_hex,
                        block_hash, block_number, block_timestamp,
                        lock_time, size, virtual_size, discount_virtual_size,
                        version, is_coinbase,
                        input_count, output_count, input_value, output_value, fee,
                        node_fee_json,
                        inputs, outputs,
                        weight, discount_weight, sigops,
                        raw_tx
                    ) VALUES (
                        %(hash)s, %(tx_index)s, %(txid)s, %(wtxid)s, %(withash)s, %(tx_hex)s,
                        %(block_hash)s, %(block_number)s, %(block_timestamp)s,
                        %(lock_time)s, %(size)s, %(virtual_size)s, %(discount_virtual_size)s,
                        %(version)s, %(is_coinbase)s,
                        %(input_count)s, %(output_count)s, %(input_value)s, %(output_value)s, %(fee)s,
                        %(node_fee_json)s::jsonb,
                        %(inputs)s::jsonb, %(outputs)s::jsonb,
                        %(weight)s, %(discount_weight)s, %(sigops)s,
                        %(raw_tx)s::jsonb
                    )
                    ON CONFLICT (hash, tx_index) DO UPDATE SET
                        txid = EXCLUDED.txid,
                        wtxid = EXCLUDED.wtxid,
                        withash = EXCLUDED.withash,
                        tx_hex = EXCLUDED.tx_hex,
                        block_hash = EXCLUDED.block_hash,
                        block_number = EXCLUDED.block_number,
                        block_timestamp = EXCLUDED.block_timestamp,
                        lock_time = EXCLUDED.lock_time,
                        size = EXCLUDED.size,
                        virtual_size = EXCLUDED.virtual_size,
                        discount_virtual_size = EXCLUDED.discount_virtual_size,
                        weight = EXCLUDED.weight,
                        discount_weight = EXCLUDED.discount_weight,
                        sigops = EXCLUDED.sigops,
                        version = EXCLUDED.version,
                        is_coinbase = EXCLUDED.is_coinbase,
                        input_count = EXCLUDED.input_count,
                        output_count = EXCLUDED.output_count,
                        input_value = EXCLUDED.input_value,
                        output_value = EXCLUDED.output_value,
                        fee = EXCLUDED.fee,
                        node_fee_json = EXCLUDED.node_fee_json,
                        inputs = EXCLUDED.inputs,
                        outputs = EXCLUDED.outputs,
                        raw_tx = EXCLUDED.raw_tx
                    """,
                    payloads,
                )

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
