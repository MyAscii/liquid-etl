from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from .rpc_schema import RpcSchemaAudit


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


def _hit(counter: Dict[str, int], key: str, value: Any) -> None:
    if value is None:
        return
    counter[key] = counter.get(key, 0) + 1

