from __future__ import annotations

from typing import Dict, List

from .rpc_schema import RpcSchemaAudit


def suggest_prunable_postgres_columns(audit: RpcSchemaAudit) -> Dict[str, List[str]]:
    candidates: Dict[str, List[str]] = {"blocks": [], "txins": [], "txouts": []}

    if audit.sampled_blocks > 0:
        for k in ("bits", "nonce", "difficulty", "chainwork"):
            if audit.block_key_hits.get(k, 0) == 0:
                candidates["blocks"].append(k)

    if audit.sampled_vouts > 0:
        for k in (
            "nonce",
            "rangeproof",
            "pegout",
            "is_pegout",
            "spent",
            "spentby",
            "spentbyvin",
            "spentheight",
        ):
            if audit.vout_key_hits.get(k, 0) == 0:
                candidates["txouts"].append(k)

    if audit.sampled_vins > 0:
        for k in (
            "pegin_value",
            "pegin_asset",
            "pegin_genesis_hash",
            "pegin_claim_script",
            "pegin_tx",
            "pegin_txout_proof",
            "pegin_blockhash",
        ):
            if audit.vin_key_hits.get(k, 0) == 0:
                candidates["txins"].append(k)

    return candidates


def to_postgres_drop_column_sql(prunable: Dict[str, List[str]]) -> List[str]:
    sql: List[str] = []

    blocks_map = {"bits": "bits", "nonce": "nonce", "difficulty": "difficulty", "chainwork": "chainwork"}
    txins_map = {
        "pegin_value": "pegin_value_sat",
        "pegin_asset": "pegin_asset_id",
        "pegin_genesis_hash": "pegin_genesis_hash",
        "pegin_claim_script": "pegin_claim_script_hex",
        "pegin_tx": "pegin_mainchain_tx_hex",
        "pegin_txout_proof": "pegin_merkle_proof_hex",
        "pegin_blockhash": "pegin_referenced_block_hash",
    }
    txouts_map = {
        "nonce": "nonce",
        "rangeproof": "rangeproof",
        "pegout": None,
        "is_pegout": "is_pegout",
        "spent": "spent",
        "spentby": "spent_by_txid",
        "spentbyvin": "spent_by_vin",
        "spentheight": "spent_at_height",
    }

    for k in prunable.get("blocks") or []:
        col = blocks_map.get(k)
        if col:
            sql.append(f"ALTER TABLE blocks DROP COLUMN IF EXISTS {col}")

    for k in prunable.get("txins") or []:
        col = txins_map.get(k)
        if col:
            sql.append(f"ALTER TABLE txins DROP COLUMN IF EXISTS {col}")

    for k in prunable.get("txouts") or []:
        if k == "pegout":
            for col in (
                "pegout_chain_genesis_hash",
                "pegout_btc_scriptpubkey_hex",
                "pegout_value_sat",
                "pegout_asset_id",
                "pegout_extra_data_hex",
            ):
                sql.append(f"ALTER TABLE txouts DROP COLUMN IF EXISTS {col}")
            continue
        col = txouts_map.get(k)
        if col:
            sql.append(f"ALTER TABLE txouts DROP COLUMN IF EXISTS {col}")

    return sql

