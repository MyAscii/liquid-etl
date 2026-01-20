from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List


class PostgresWriterV2:
    def __init__(self, dsn: str):
        self.dsn = dsn
        try:
            import psycopg
        except Exception as e:
            raise RuntimeError("psycopg not installed; install with pip install -e .[postgres]") from e
        self.conn = psycopg.connect(dsn, autocommit=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS blocks_v2 (
                    network TEXT NOT NULL,
                    hash TEXT PRIMARY KEY,
                    height BIGINT,
                    version BIGINT,
                    prev_block_hash TEXT,
                    next_block_hash TEXT,
                    merkle_root TEXT,
                    time BIGINT,
                    median_time BIGINT,
                    nonce BIGINT,
                    bits TEXT,
                    difficulty DOUBLE PRECISION,
                    chainwork TEXT,
                    tx_count BIGINT,
                    size BIGINT,
                    stripped_size BIGINT,
                    weight BIGINT,
                    extdata_type TEXT,
                    signblock_challenge_hex TEXT,
                    signblock_solution_hex TEXT,
                    dynafed_current_params JSONB,
                    dynafed_proposed_params JSONB,
                    signblock_witness JSONB,
                    txids JSONB,
                    raw_block_hex TEXT,
                    raw_block_json JSONB
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS transactions_v2 (
                    network TEXT NOT NULL,
                    txid TEXT PRIMARY KEY,
                    wtxid TEXT,
                    hash TEXT,
                    withash TEXT,
                    block_hash TEXT,
                    block_height BIGINT,
                    block_time BIGINT,
                    tx_index_in_block INTEGER,
                    confirmed BOOLEAN,
                    version BIGINT,
                    lock_time BIGINT,
                    size BIGINT,
                    vsize DOUBLE PRECISION,
                    weight BIGINT,
                    discount_vsize DOUBLE PRECISION,
                    discount_weight BIGINT,
                    vin_count INTEGER,
                    vout_count INTEGER,
                    fee_by_asset JSONB,
                    explicit_in_by_asset JSONB,
                    explicit_out_by_asset JSONB,
                    has_any_confidential BOOLEAN,
                    has_pegin BOOLEAN,
                    has_pegout BOOLEAN,
                    has_issuance BOOLEAN,
                    raw_tx_hex TEXT,
                    raw_tx_json JSONB
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS txins_v2 (
                    network TEXT NOT NULL,
                    txid TEXT NOT NULL,
                    vin INTEGER NOT NULL,
                    prev_txid TEXT,
                    prev_vout INTEGER,
                    sequence BIGINT,
                    is_coinbase BOOLEAN,
                    scriptsig_hex TEXT,
                    scriptsig_asm TEXT,
                    txinwitness JSONB,
                    pegin_witness JSONB,
                    is_pegin BOOLEAN,
                    pegin_value_sat BIGINT,
                    pegin_asset_id TEXT,
                    pegin_genesis_hash TEXT,
                    pegin_claim_script_hex TEXT,
                    pegin_mainchain_tx_hex TEXT,
                    pegin_merkle_proof_hex TEXT,
                    pegin_referenced_block_hash TEXT,
                    has_issuance BOOLEAN,
                    issuance_asset_blinding_nonce TEXT,
                    issuance_asset_entropy TEXT,
                    issuance_amount BIGINT,
                    issuance_amount_commitment TEXT,
                    issuance_inflation_keys BIGINT,
                    issuance_inflation_keys_commitment TEXT,
                    prevout_asset_id TEXT,
                    prevout_value_sat BIGINT,
                    prevout_value_commitment TEXT,
                    prevout_asset_commitment TEXT,
                    prevout_scriptpubkey_hex TEXT,
                    prevout_script_type TEXT,
                    prevout_address TEXT,
                    PRIMARY KEY (txid, vin)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS txouts_v2 (
                    network TEXT NOT NULL,
                    txid TEXT NOT NULL,
                    vout INTEGER NOT NULL,
                    asset_id TEXT,
                    asset_commitment TEXT,
                    value_sat BIGINT,
                    value_commitment TEXT,
                    scriptpubkey_hex TEXT,
                    scriptpubkey_asm TEXT,
                    script_type TEXT,
                    address TEXT,
                    is_op_return BOOLEAN,
                    op_return_data_hex TEXT,
                    is_fee BOOLEAN,
                    is_pegout BOOLEAN,
                    pegout_chain_genesis_hash TEXT,
                    pegout_btc_scriptpubkey_hex TEXT,
                    pegout_value_sat BIGINT,
                    pegout_asset_id TEXT,
                    pegout_extra_data_hex TEXT,
                    nonce TEXT,
                    surjection_proof TEXT,
                    rangeproof TEXT,
                    spent BOOLEAN,
                    spent_by_txid TEXT,
                    spent_by_vin INTEGER,
                    spent_at_height BIGINT,
                    PRIMARY KEY (txid, vout)
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS transactions_v2_block_height_idx ON transactions_v2 (block_height)")
            cur.execute("CREATE INDEX IF NOT EXISTS txins_v2_prev_outpoint_idx ON txins_v2 (prev_txid, prev_vout)")
            cur.execute("CREATE INDEX IF NOT EXISTS txouts_v2_asset_id_idx ON txouts_v2 (asset_id)")

    def write_bundle(self, block_row: Dict[str, Any], tx_rows: List[Dict[str, Any]], txin_rows: List[Dict[str, Any]], txout_rows: List[Dict[str, Any]]) -> None:
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

    def write_blocks(self, blocks: Iterable[Dict[str, Any]]) -> None:
        payloads = []
        for b in blocks:
            payloads.append(
                {
                    **b,
                    "dynafed_current_params": json.dumps(b.get("dynafed_current_params"), default=str) if b.get("dynafed_current_params") is not None else None,
                    "dynafed_proposed_params": json.dumps(b.get("dynafed_proposed_params"), default=str) if b.get("dynafed_proposed_params") is not None else None,
                    "signblock_witness": json.dumps(b.get("signblock_witness"), default=str) if b.get("signblock_witness") is not None else None,
                    "txids": json.dumps(b.get("txids"), default=str) if b.get("txids") is not None else None,
                    "raw_block_json": json.dumps(b.get("raw_block_json"), default=str) if b.get("raw_block_json") is not None else None,
                }
            )
        if not payloads:
            return
        with self.conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO blocks_v2 (
                    network, hash, height, version, prev_block_hash, next_block_hash,
                    merkle_root, time, median_time, nonce, bits, difficulty, chainwork,
                    tx_count, size, stripped_size, weight,
                    extdata_type, signblock_challenge_hex, signblock_solution_hex,
                    dynafed_current_params, dynafed_proposed_params, signblock_witness,
                    txids, raw_block_hex, raw_block_json
                ) VALUES (
                    %(network)s, %(hash)s, %(height)s, %(version)s, %(prev_block_hash)s, %(next_block_hash)s,
                    %(merkle_root)s, %(time)s, %(median_time)s, %(nonce)s, %(bits)s, %(difficulty)s, %(chainwork)s,
                    %(tx_count)s, %(size)s, %(stripped_size)s, %(weight)s,
                    %(extdata_type)s, %(signblock_challenge_hex)s, %(signblock_solution_hex)s,
                    %(dynafed_current_params)s::jsonb, %(dynafed_proposed_params)s::jsonb, %(signblock_witness)s::jsonb,
                    %(txids)s::jsonb, %(raw_block_hex)s, %(raw_block_json)s::jsonb
                )
                ON CONFLICT (hash) DO UPDATE SET
                    network = EXCLUDED.network,
                    height = EXCLUDED.height,
                    version = EXCLUDED.version,
                    prev_block_hash = EXCLUDED.prev_block_hash,
                    next_block_hash = EXCLUDED.next_block_hash,
                    merkle_root = EXCLUDED.merkle_root,
                    time = EXCLUDED.time,
                    median_time = EXCLUDED.median_time,
                    nonce = EXCLUDED.nonce,
                    bits = EXCLUDED.bits,
                    difficulty = EXCLUDED.difficulty,
                    chainwork = EXCLUDED.chainwork,
                    tx_count = EXCLUDED.tx_count,
                    size = EXCLUDED.size,
                    stripped_size = EXCLUDED.stripped_size,
                    weight = EXCLUDED.weight,
                    extdata_type = EXCLUDED.extdata_type,
                    signblock_challenge_hex = EXCLUDED.signblock_challenge_hex,
                    signblock_solution_hex = EXCLUDED.signblock_solution_hex,
                    dynafed_current_params = EXCLUDED.dynafed_current_params,
                    dynafed_proposed_params = EXCLUDED.dynafed_proposed_params,
                    signblock_witness = EXCLUDED.signblock_witness,
                    txids = EXCLUDED.txids,
                    raw_block_hex = EXCLUDED.raw_block_hex,
                    raw_block_json = EXCLUDED.raw_block_json
                """,
                payloads,
            )

    def write_transactions(self, txs: Iterable[Dict[str, Any]]) -> None:
        payloads = []
        for t in txs:
            payloads.append(
                {
                    **t,
                    "fee_by_asset": json.dumps(t.get("fee_by_asset"), default=str) if t.get("fee_by_asset") is not None else None,
                    "explicit_in_by_asset": json.dumps(t.get("explicit_in_by_asset"), default=str) if t.get("explicit_in_by_asset") is not None else None,
                    "explicit_out_by_asset": json.dumps(t.get("explicit_out_by_asset"), default=str) if t.get("explicit_out_by_asset") is not None else None,
                    "raw_tx_json": json.dumps(t.get("raw_tx_json"), default=str) if t.get("raw_tx_json") is not None else None,
                }
            )
        if not payloads:
            return
        with self.conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO transactions_v2 (
                    network, txid, wtxid, hash, withash,
                    block_hash, block_height, block_time, tx_index_in_block, confirmed,
                    version, lock_time,
                    size, vsize, weight, discount_vsize, discount_weight,
                    vin_count, vout_count,
                    fee_by_asset, explicit_in_by_asset, explicit_out_by_asset,
                    has_any_confidential, has_pegin, has_pegout, has_issuance,
                    raw_tx_hex, raw_tx_json
                ) VALUES (
                    %(network)s, %(txid)s, %(wtxid)s, %(hash)s, %(withash)s,
                    %(block_hash)s, %(block_height)s, %(block_time)s, %(tx_index_in_block)s, %(confirmed)s,
                    %(version)s, %(lock_time)s,
                    %(size)s, %(vsize)s, %(weight)s, %(discount_vsize)s, %(discount_weight)s,
                    %(vin_count)s, %(vout_count)s,
                    %(fee_by_asset)s::jsonb, %(explicit_in_by_asset)s::jsonb, %(explicit_out_by_asset)s::jsonb,
                    %(has_any_confidential)s, %(has_pegin)s, %(has_pegout)s, %(has_issuance)s,
                    %(raw_tx_hex)s, %(raw_tx_json)s::jsonb
                )
                ON CONFLICT (txid) DO UPDATE SET
                    network = EXCLUDED.network,
                    wtxid = EXCLUDED.wtxid,
                    hash = EXCLUDED.hash,
                    withash = EXCLUDED.withash,
                    block_hash = EXCLUDED.block_hash,
                    block_height = EXCLUDED.block_height,
                    block_time = EXCLUDED.block_time,
                    tx_index_in_block = EXCLUDED.tx_index_in_block,
                    confirmed = EXCLUDED.confirmed,
                    version = EXCLUDED.version,
                    lock_time = EXCLUDED.lock_time,
                    size = EXCLUDED.size,
                    vsize = EXCLUDED.vsize,
                    weight = EXCLUDED.weight,
                    discount_vsize = EXCLUDED.discount_vsize,
                    discount_weight = EXCLUDED.discount_weight,
                    vin_count = EXCLUDED.vin_count,
                    vout_count = EXCLUDED.vout_count,
                    fee_by_asset = EXCLUDED.fee_by_asset,
                    explicit_in_by_asset = EXCLUDED.explicit_in_by_asset,
                    explicit_out_by_asset = EXCLUDED.explicit_out_by_asset,
                    has_any_confidential = EXCLUDED.has_any_confidential,
                    has_pegin = EXCLUDED.has_pegin,
                    has_pegout = EXCLUDED.has_pegout,
                    has_issuance = EXCLUDED.has_issuance,
                    raw_tx_hex = EXCLUDED.raw_tx_hex,
                    raw_tx_json = EXCLUDED.raw_tx_json
                """,
                payloads,
            )

    def write_txins(self, txins: Iterable[Dict[str, Any]]) -> None:
        payloads = []
        for i in txins:
            payloads.append(
                {
                    **i,
                    "txinwitness": json.dumps(i.get("txinwitness"), default=str) if i.get("txinwitness") is not None else None,
                    "pegin_witness": json.dumps(i.get("pegin_witness"), default=str) if i.get("pegin_witness") is not None else None,
                }
            )
        if not payloads:
            return
        with self.conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO txins_v2 (
                    network, txid, vin,
                    prev_txid, prev_vout,
                    sequence, is_coinbase,
                    scriptsig_hex, scriptsig_asm,
                    txinwitness, pegin_witness,
                    is_pegin,
                    pegin_value_sat, pegin_asset_id, pegin_genesis_hash, pegin_claim_script_hex,
                    pegin_mainchain_tx_hex, pegin_merkle_proof_hex, pegin_referenced_block_hash,
                    has_issuance,
                    issuance_asset_blinding_nonce, issuance_asset_entropy,
                    issuance_amount, issuance_amount_commitment,
                    issuance_inflation_keys, issuance_inflation_keys_commitment,
                    prevout_asset_id, prevout_value_sat,
                    prevout_value_commitment, prevout_asset_commitment,
                    prevout_scriptpubkey_hex, prevout_script_type, prevout_address
                ) VALUES (
                    %(network)s, %(txid)s, %(vin)s,
                    %(prev_txid)s, %(prev_vout)s,
                    %(sequence)s, %(is_coinbase)s,
                    %(scriptsig_hex)s, %(scriptsig_asm)s,
                    %(txinwitness)s::jsonb, %(pegin_witness)s::jsonb,
                    %(is_pegin)s,
                    %(pegin_value_sat)s, %(pegin_asset_id)s, %(pegin_genesis_hash)s, %(pegin_claim_script_hex)s,
                    %(pegin_mainchain_tx_hex)s, %(pegin_merkle_proof_hex)s, %(pegin_referenced_block_hash)s,
                    %(has_issuance)s,
                    %(issuance_asset_blinding_nonce)s, %(issuance_asset_entropy)s,
                    %(issuance_amount)s, %(issuance_amount_commitment)s,
                    %(issuance_inflation_keys)s, %(issuance_inflation_keys_commitment)s,
                    %(prevout_asset_id)s, %(prevout_value_sat)s,
                    %(prevout_value_commitment)s, %(prevout_asset_commitment)s,
                    %(prevout_scriptpubkey_hex)s, %(prevout_script_type)s, %(prevout_address)s
                )
                ON CONFLICT (txid, vin) DO UPDATE SET
                    network = EXCLUDED.network,
                    prev_txid = EXCLUDED.prev_txid,
                    prev_vout = EXCLUDED.prev_vout,
                    sequence = EXCLUDED.sequence,
                    is_coinbase = EXCLUDED.is_coinbase,
                    scriptsig_hex = EXCLUDED.scriptsig_hex,
                    scriptsig_asm = EXCLUDED.scriptsig_asm,
                    txinwitness = EXCLUDED.txinwitness,
                    pegin_witness = EXCLUDED.pegin_witness,
                    is_pegin = EXCLUDED.is_pegin,
                    pegin_value_sat = EXCLUDED.pegin_value_sat,
                    pegin_asset_id = EXCLUDED.pegin_asset_id,
                    pegin_genesis_hash = EXCLUDED.pegin_genesis_hash,
                    pegin_claim_script_hex = EXCLUDED.pegin_claim_script_hex,
                    pegin_mainchain_tx_hex = EXCLUDED.pegin_mainchain_tx_hex,
                    pegin_merkle_proof_hex = EXCLUDED.pegin_merkle_proof_hex,
                    pegin_referenced_block_hash = EXCLUDED.pegin_referenced_block_hash,
                    has_issuance = EXCLUDED.has_issuance,
                    issuance_asset_blinding_nonce = EXCLUDED.issuance_asset_blinding_nonce,
                    issuance_asset_entropy = EXCLUDED.issuance_asset_entropy,
                    issuance_amount = EXCLUDED.issuance_amount,
                    issuance_amount_commitment = EXCLUDED.issuance_amount_commitment,
                    issuance_inflation_keys = EXCLUDED.issuance_inflation_keys,
                    issuance_inflation_keys_commitment = EXCLUDED.issuance_inflation_keys_commitment,
                    prevout_asset_id = EXCLUDED.prevout_asset_id,
                    prevout_value_sat = EXCLUDED.prevout_value_sat,
                    prevout_value_commitment = EXCLUDED.prevout_value_commitment,
                    prevout_asset_commitment = EXCLUDED.prevout_asset_commitment,
                    prevout_scriptpubkey_hex = EXCLUDED.prevout_scriptpubkey_hex,
                    prevout_script_type = EXCLUDED.prevout_script_type,
                    prevout_address = EXCLUDED.prevout_address
                """,
                payloads,
            )

    def write_txouts(self, txouts: Iterable[Dict[str, Any]]) -> None:
        payloads = list(txouts)
        if not payloads:
            return
        with self.conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO txouts_v2 (
                    network, txid, vout,
                    asset_id, asset_commitment,
                    value_sat, value_commitment,
                    scriptpubkey_hex, scriptpubkey_asm, script_type, address,
                    is_op_return, op_return_data_hex,
                    is_fee, is_pegout,
                    pegout_chain_genesis_hash, pegout_btc_scriptpubkey_hex,
                    pegout_value_sat, pegout_asset_id, pegout_extra_data_hex,
                    nonce, surjection_proof, rangeproof,
                    spent, spent_by_txid, spent_by_vin, spent_at_height
                ) VALUES (
                    %(network)s, %(txid)s, %(vout)s,
                    %(asset_id)s, %(asset_commitment)s,
                    %(value_sat)s, %(value_commitment)s,
                    %(scriptpubkey_hex)s, %(scriptpubkey_asm)s, %(script_type)s, %(address)s,
                    %(is_op_return)s, %(op_return_data_hex)s,
                    %(is_fee)s, %(is_pegout)s,
                    %(pegout_chain_genesis_hash)s, %(pegout_btc_scriptpubkey_hex)s,
                    %(pegout_value_sat)s, %(pegout_asset_id)s, %(pegout_extra_data_hex)s,
                    %(nonce)s, %(surjection_proof)s, %(rangeproof)s,
                    %(spent)s, %(spent_by_txid)s, %(spent_by_vin)s, %(spent_at_height)s
                )
                ON CONFLICT (txid, vout) DO UPDATE SET
                    network = EXCLUDED.network,
                    asset_id = EXCLUDED.asset_id,
                    asset_commitment = EXCLUDED.asset_commitment,
                    value_sat = EXCLUDED.value_sat,
                    value_commitment = EXCLUDED.value_commitment,
                    scriptpubkey_hex = EXCLUDED.scriptpubkey_hex,
                    scriptpubkey_asm = EXCLUDED.scriptpubkey_asm,
                    script_type = EXCLUDED.script_type,
                    address = EXCLUDED.address,
                    is_op_return = EXCLUDED.is_op_return,
                    op_return_data_hex = EXCLUDED.op_return_data_hex,
                    is_fee = EXCLUDED.is_fee,
                    is_pegout = EXCLUDED.is_pegout,
                    pegout_chain_genesis_hash = EXCLUDED.pegout_chain_genesis_hash,
                    pegout_btc_scriptpubkey_hex = EXCLUDED.pegout_btc_scriptpubkey_hex,
                    pegout_value_sat = EXCLUDED.pegout_value_sat,
                    pegout_asset_id = EXCLUDED.pegout_asset_id,
                    pegout_extra_data_hex = EXCLUDED.pegout_extra_data_hex,
                    nonce = EXCLUDED.nonce,
                    surjection_proof = EXCLUDED.surjection_proof,
                    rangeproof = EXCLUDED.rangeproof,
                    spent = EXCLUDED.spent,
                    spent_by_txid = EXCLUDED.spent_by_txid,
                    spent_by_vin = EXCLUDED.spent_by_vin,
                    spent_at_height = EXCLUDED.spent_at_height
                """,
                payloads,
            )

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
