from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


@dataclass(frozen=True)
class RpcSchemaAudit:
    sampled_blocks: int
    sampled_transactions: int
    sampled_vins: int
    sampled_vouts: int
    block_key_hits: Dict[str, int]
    vin_key_hits: Dict[str, int]
    vout_key_hits: Dict[str, int]
    issuance_key_hits: Dict[str, int]
    prevout_key_hits: Dict[str, int]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "sampled_blocks": self.sampled_blocks,
            "sampled_transactions": self.sampled_transactions,
            "sampled_vins": self.sampled_vins,
            "sampled_vouts": self.sampled_vouts,
            "block_key_hits": dict(self.block_key_hits),
            "vin_key_hits": dict(self.vin_key_hits),
            "vout_key_hits": dict(self.vout_key_hits),
            "issuance_key_hits": dict(self.issuance_key_hits),
            "prevout_key_hits": dict(self.prevout_key_hits),
        }


def _hit(counter: Dict[str, int], key: str, value: Any) -> None:
    if value is None:
        return
    counter[key] = counter.get(key, 0) + 1


def audit_rpc_blocks(
    blocks: Iterable[Dict[str, Any]],
    *,
    block_keys: Optional[List[str]] = None,
    vin_keys: Optional[List[str]] = None,
    vout_keys: Optional[List[str]] = None,
) -> RpcSchemaAudit:
    if block_keys is None:
        block_keys = [
            "bits",
            "nonce",
            "difficulty",
            "chainwork",
            "current_federation",
            "current_params",
            "proposed_federation",
            "proposed_params",
            "signblock_challenge",
            "signblock_witness_hex",
            "signblock_witness",
        ]
    if vin_keys is None:
        vin_keys = [
            "prevout",
            "is_pegin",
            "pegin_witness",
            "pegin_value",
            "pegin_asset",
            "pegin_genesis_hash",
            "pegin_claim_script",
            "pegin_tx",
            "pegin_txout_proof",
            "pegin_blockhash",
            "issuance",
            "assetissuance",
            "txinwitness",
            "witness",
        ]
    if vout_keys is None:
        vout_keys = [
            "asset",
            "assetcommitment",
            "value",
            "valuecommitment",
            "nonce",
            "surjectionproof",
            "rangeproof",
            "pegout",
            "is_pegout",
            "spent",
            "spentby",
            "spentbyvin",
            "spentheight",
        ]

    block_key_hits: Dict[str, int] = {}
    vin_key_hits: Dict[str, int] = {}
    vout_key_hits: Dict[str, int] = {}
    issuance_key_hits: Dict[str, int] = {}
    prevout_key_hits: Dict[str, int] = {}

    sampled_blocks = 0
    sampled_transactions = 0
    sampled_vins = 0
    sampled_vouts = 0

    for b in blocks:
        if not isinstance(b, dict):
            continue
        sampled_blocks += 1
        for k in block_keys:
            if k in b:
                _hit(block_key_hits, k, b.get(k))

        txs = b.get("tx") or []
        for t in txs:
            if not isinstance(t, dict):
                continue
            sampled_transactions += 1

            vins = t.get("vin") or []
            for vin in vins:
                if not isinstance(vin, dict):
                    continue
                sampled_vins += 1
                for k in vin_keys:
                    if k in vin:
                        _hit(vin_key_hits, k, vin.get(k))

                prevout = vin.get("prevout") if isinstance(vin.get("prevout"), dict) else None
                if isinstance(prevout, dict):
                    for k in ("asset", "value", "valuecommitment", "assetcommitment"):
                        if k in prevout:
                            _hit(prevout_key_hits, k, prevout.get(k))

                issuance = vin.get("issuance") if isinstance(vin.get("issuance"), dict) else None
                if issuance is None and isinstance(vin.get("assetissuance"), dict):
                    issuance = vin.get("assetissuance")
                if isinstance(issuance, dict):
                    for k in (
                        "assetBlindingNonce",
                        "assetEntropy",
                        "assetamount",
                        "assetamountcommitment",
                        "tokenamount",
                        "tokenamountcommitment",
                    ):
                        if k in issuance:
                            _hit(issuance_key_hits, k, issuance.get(k))

            vouts = t.get("vout") or []
            for vout in vouts:
                if not isinstance(vout, dict):
                    continue
                sampled_vouts += 1
                for k in vout_keys:
                    if k in vout:
                        _hit(vout_key_hits, k, vout.get(k))

    return RpcSchemaAudit(
        sampled_blocks=sampled_blocks,
        sampled_transactions=sampled_transactions,
        sampled_vins=sampled_vins,
        sampled_vouts=sampled_vouts,
        block_key_hits=block_key_hits,
        vin_key_hits=vin_key_hits,
        vout_key_hits=vout_key_hits,
        issuance_key_hits=issuance_key_hits,
        prevout_key_hits=prevout_key_hits,
    )


def suggest_prunable_postgres_columns(audit: RpcSchemaAudit) -> Dict[str, List[str]]:
    candidates: Dict[str, List[str]] = {"blocks": [], "txins": [], "txouts": []}

    if audit.sampled_blocks > 0:
        for k in ("bits", "nonce", "difficulty", "chainwork"):
            if audit.block_key_hits.get(k, 0) == 0:
                candidates["blocks"].append(k)

    if audit.sampled_vouts > 0:
        for k in ("nonce", "rangeproof", "pegout", "is_pegout", "spent", "spentby", "spentbyvin", "spentheight"):
            if audit.vout_key_hits.get(k, 0) == 0:
                candidates["txouts"].append(k)

    if audit.sampled_vins > 0:
        for k in ("pegin_value", "pegin_asset", "pegin_genesis_hash", "pegin_claim_script", "pegin_tx", "pegin_txout_proof", "pegin_blockhash"):
            if audit.vin_key_hits.get(k, 0) == 0:
                candidates["txins"].append(k)

    return candidates


def to_postgres_drop_column_sql(prunable: Dict[str, List[str]]) -> List[str]:
    sql: List[str] = []

    blocks_map = {
        "bits": "bits",
        "nonce": "nonce",
        "difficulty": "difficulty",
        "chainwork": "chainwork",
    }
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
