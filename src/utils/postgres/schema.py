from __future__ import annotations

from typing import Any


def ensure_schema(cur: Any) -> None:
    _create_tables(cur)
    _create_indexes(cur)
    drop_obsolete_columns(cur)


def _create_tables(cur: Any) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS blocks (
            hash TEXT PRIMARY KEY,
            height BIGINT,
            version BIGINT,
            prev_block_hash TEXT,
            next_block_hash TEXT,
            merkle_root TEXT,
            time BIGINT,
            median_time BIGINT,
            tx_count BIGINT,
            size BIGINT,
            stripped_size BIGINT,
            weight BIGINT,
            signblock_solution_hex TEXT,
            txids JSONB
        )
        """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
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
            has_issuance BOOLEAN
        )
        """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS txins (
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
            has_issuance BOOLEAN,
            issuance_asset_blinding_nonce TEXT,
            issuance_asset_entropy TEXT,
            issuance_amount BIGINT,
            issuance_inflation_keys BIGINT,
            prevout_scriptpubkey_hex TEXT,
            prevout_script_type TEXT,
            prevout_address TEXT,
            PRIMARY KEY (txid, vin)
        )
        """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS txouts (
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
            surjection_proof TEXT,
            PRIMARY KEY (txid, vout)
        )
        """)


def _create_indexes(cur: Any) -> None:
    cur.execute(
        "CREATE INDEX IF NOT EXISTS transactions_block_height_idx ON transactions (block_height)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS txins_prev_outpoint_idx ON txins (prev_txid, prev_vout)"
    )
    cur.execute("CREATE INDEX IF NOT EXISTS txouts_asset_id_idx ON txouts (asset_id)")


def drop_obsolete_columns(cur: Any) -> None:
    cur.execute("ALTER TABLE blocks DROP COLUMN IF EXISTS network")
    cur.execute("ALTER TABLE blocks DROP COLUMN IF EXISTS nonce")
    cur.execute("ALTER TABLE blocks DROP COLUMN IF EXISTS bits")
    cur.execute("ALTER TABLE blocks DROP COLUMN IF EXISTS difficulty")
    cur.execute("ALTER TABLE blocks DROP COLUMN IF EXISTS chainwork")
    cur.execute("ALTER TABLE blocks DROP COLUMN IF EXISTS extdata_type")
    cur.execute("ALTER TABLE blocks DROP COLUMN IF EXISTS signblock_challenge_hex")
    cur.execute("ALTER TABLE blocks DROP COLUMN IF EXISTS dynafed_current_params")
    cur.execute("ALTER TABLE blocks DROP COLUMN IF EXISTS dynafed_proposed_params")
    cur.execute("ALTER TABLE blocks DROP COLUMN IF EXISTS signblock_witness")
    cur.execute("ALTER TABLE transactions DROP COLUMN IF EXISTS network")
    cur.execute("ALTER TABLE transactions DROP COLUMN IF EXISTS has_pegout")
    cur.execute("ALTER TABLE txins DROP COLUMN IF EXISTS network")
    cur.execute("ALTER TABLE txins DROP COLUMN IF EXISTS pegin_value_sat")
    cur.execute("ALTER TABLE txins DROP COLUMN IF EXISTS pegin_asset_id")
    cur.execute("ALTER TABLE txins DROP COLUMN IF EXISTS pegin_genesis_hash")
    cur.execute("ALTER TABLE txins DROP COLUMN IF EXISTS pegin_claim_script_hex")
    cur.execute("ALTER TABLE txins DROP COLUMN IF EXISTS pegin_mainchain_tx_hex")
    cur.execute("ALTER TABLE txins DROP COLUMN IF EXISTS pegin_merkle_proof_hex")
    cur.execute("ALTER TABLE txins DROP COLUMN IF EXISTS pegin_referenced_block_hash")
    cur.execute("ALTER TABLE txins DROP COLUMN IF EXISTS issuance_amount_commitment")
    cur.execute("ALTER TABLE txins DROP COLUMN IF EXISTS issuance_inflation_keys_commitment")
    cur.execute("ALTER TABLE txins DROP COLUMN IF EXISTS prevout_asset_id")
    cur.execute("ALTER TABLE txins DROP COLUMN IF EXISTS prevout_value_sat")
    cur.execute("ALTER TABLE txins DROP COLUMN IF EXISTS prevout_value_commitment")
    cur.execute("ALTER TABLE txins DROP COLUMN IF EXISTS prevout_asset_commitment")
    cur.execute("ALTER TABLE txouts DROP COLUMN IF EXISTS network")
    cur.execute("ALTER TABLE txouts DROP COLUMN IF EXISTS is_pegout")
    cur.execute("ALTER TABLE txouts DROP COLUMN IF EXISTS pegout_chain_genesis_hash")
    cur.execute("ALTER TABLE txouts DROP COLUMN IF EXISTS pegout_btc_scriptpubkey_hex")
    cur.execute("ALTER TABLE txouts DROP COLUMN IF EXISTS pegout_value_sat")
    cur.execute("ALTER TABLE txouts DROP COLUMN IF EXISTS pegout_asset_id")
    cur.execute("ALTER TABLE txouts DROP COLUMN IF EXISTS pegout_extra_data_hex")
    cur.execute("ALTER TABLE txouts DROP COLUMN IF EXISTS nonce")
    cur.execute("ALTER TABLE txouts DROP COLUMN IF EXISTS rangeproof")
    cur.execute("ALTER TABLE txouts DROP COLUMN IF EXISTS spent")
    cur.execute("ALTER TABLE txouts DROP COLUMN IF EXISTS spent_by_txid")
    cur.execute("ALTER TABLE txouts DROP COLUMN IF EXISTS spent_by_vin")
    cur.execute("ALTER TABLE txouts DROP COLUMN IF EXISTS spent_at_height")
    cur.execute("ALTER TABLE blocks DROP COLUMN IF EXISTS raw_block_hex")
    cur.execute("ALTER TABLE blocks DROP COLUMN IF EXISTS raw_block_json")
    cur.execute("ALTER TABLE transactions DROP COLUMN IF EXISTS raw_tx_hex")
    cur.execute("ALTER TABLE transactions DROP COLUMN IF EXISTS raw_tx_json")
