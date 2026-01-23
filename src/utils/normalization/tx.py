from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..amounts import amounts_map_to_satoshi_map, to_satoshi
from .vin import normalize_vin
from .vout import normalize_vout


def normalize_tx(
    tx: Dict[str, Any],
    block_row: Dict[str, Any],
    tx_index_in_block: int,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    network = block_row["network"]
    vins = tx.get("vin", []) or []
    vouts = tx.get("vout", []) or []

    has_any_confidential, has_pegin, has_issuance, has_pegout = _scan_tx_flags(vins, vouts)
    fee_by_asset = amounts_map_to_satoshi_map(tx.get("fee"))
    explicit_in_by_asset = _explicit_in_by_asset(vins)
    explicit_out_by_asset = _explicit_out_by_asset(vouts)

    tx_row = {
        "network": network,
        "txid": tx.get("txid"),
        "wtxid": tx.get("wtxid"),
        "hash": tx.get("hash"),
        "withash": tx.get("withash"),
        "block_hash": block_row.get("hash"),
        "block_height": block_row.get("height"),
        "block_time": block_row.get("time"),
        "tx_index_in_block": tx_index_in_block,
        "confirmed": True,
        "version": tx.get("version"),
        "lock_time": tx.get("locktime"),
        "size": tx.get("size"),
        "vsize": tx.get("vsize"),
        "weight": tx.get("weight"),
        "discount_vsize": tx.get("discountvsize"),
        "discount_weight": tx.get("discountweight"),
        "vin_count": len(vins),
        "vout_count": len(vouts),
        "fee_by_asset": fee_by_asset,
        "explicit_in_by_asset": explicit_in_by_asset,
        "explicit_out_by_asset": explicit_out_by_asset,
        "has_any_confidential": has_any_confidential,
        "has_pegin": has_pegin,
        "has_pegout": has_pegout,
        "has_issuance": has_issuance,
    }

    txins: List[Dict[str, Any]] = []
    for idx, vin in enumerate(vins):
        if not isinstance(vin, dict):
            continue
        txins.append(normalize_vin(vin, network=network, txid=tx.get("txid"), vin_index=idx))

    txouts: List[Dict[str, Any]] = []
    for vout in vouts:
        if not isinstance(vout, dict):
            continue
        txouts.append(normalize_vout(vout, network=network, txid=tx.get("txid")))

    return tx_row, txins, txouts


def _scan_tx_flags(vins: List[Any], vouts: List[Any]) -> Tuple[bool, bool, bool, bool]:
    has_any_confidential = False
    has_pegin = False
    has_issuance = False
    has_pegout = False

    for vin in vins:
        if isinstance(vin, dict) and vin.get("is_pegin"):
            has_pegin = True
        if isinstance(vin, dict) and ("issuance" in vin or "assetissuance" in vin):
            has_issuance = True

    for vout in vouts:
        if not isinstance(vout, dict):
            continue
        if (
            vout.get("valuecommitment")
            or vout.get("assetcommitment")
            or vout.get("surjectionproof")
            or vout.get("rangeproof")
        ):
            has_any_confidential = True
        if _is_pegout(vout):
            has_pegout = True

    return has_any_confidential, has_pegin, has_issuance, has_pegout


def _explicit_in_by_asset(vins: List[Any]) -> Optional[Dict[str, int]]:
    explicit_in_by_asset: Dict[str, int] = {}
    for vin in vins:
        if not isinstance(vin, dict):
            continue
        prevout = vin.get("prevout") if isinstance(vin.get("prevout"), dict) else None
        if not isinstance(prevout, dict):
            continue
        asset = prevout.get("asset")
        value = prevout.get("value")
        if asset is None or value is None:
            continue
        sat = to_satoshi(value)
        if sat is None:
            continue
        k = str(asset)
        explicit_in_by_asset[k] = explicit_in_by_asset.get(k, 0) + sat
    return explicit_in_by_asset or None


def _explicit_out_by_asset(vouts: List[Any]) -> Optional[Dict[str, int]]:
    explicit_out_by_asset: Dict[str, int] = {}
    for vout in vouts:
        if not isinstance(vout, dict):
            continue
        asset = vout.get("asset")
        value = vout.get("value")
        if asset is None or value is None:
            continue
        sat = to_satoshi(value)
        if sat is None:
            continue
        k = str(asset)
        explicit_out_by_asset[k] = explicit_out_by_asset.get(k, 0) + sat
    return explicit_out_by_asset or None


def _is_pegout(vout: Dict[str, Any]) -> bool:
    spk = vout.get("scriptPubKey", {})
    if vout.get("is_pegout") or vout.get("pegout"):
        return True
    if isinstance(spk, dict) and (spk.get("pegout") or spk.get("type") == "pegout"):
        return True
    return False
