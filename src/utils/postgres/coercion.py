from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..amounts import to_satoshi


def coerce_block_row(block: Dict[str, Any]) -> Dict[str, Any]:
    raw = block.get("raw_block") if isinstance(block.get("raw_block"), dict) else None

    txids = block.get("txids")
    if txids is None and isinstance(raw, dict) and isinstance(raw.get("tx"), list):
        txids = []
        for t in raw.get("tx") or []:
            if isinstance(t, str):
                txids.append(t)
            elif isinstance(t, dict) and t.get("txid"):
                txids.append(t.get("txid"))

    return {
        "hash": block.get("hash") or block.get("item_id"),
        "height": block.get("number") or block.get("height"),
        "version": block.get("version"),
        "prev_block_hash": block.get("previous_block_hash"),
        "next_block_hash": block.get("next_block_hash"),
        "merkle_root": block.get("merkle_root"),
        "time": block.get("timestamp"),
        "median_time": block.get("median_time"),
        "tx_count": block.get("transaction_count"),
        "size": block.get("size"),
        "stripped_size": block.get("stripped_size"),
        "weight": block.get("weight"),
        "signblock_solution_hex": block.get("signblock_witness_hex"),
        "txids": txids,
    }


def coerce_tx_rows(
    tx: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    if "vin" in tx and "vout" in tx:
        raise ValueError(
            "write_transaction expects normalized transaction items; use ingest_range_to_postgres for raw blocks"
        )

    inputs = tx.get("inputs", []) or []
    outputs = tx.get("outputs", []) or []

    has_any_confidential = any(isinstance(o, dict) and o.get("confidential_value") for o in outputs)
    has_pegin = any(isinstance(i, dict) and i.get("input_type") == "pegin" for i in inputs)
    has_issuance = any(isinstance(i, dict) and i.get("input_type") == "issuance" for i in inputs)

    fee_by_asset = _aggregate_fee_by_asset(tx.get("node_fee"))
    explicit_in_by_asset = _aggregate_explicit_by_asset(
        inputs, asset_key="asset", value_key="value"
    )
    explicit_out_by_asset = _aggregate_explicit_by_asset(
        outputs, asset_key="asset", value_key="value"
    )

    tx_row: Dict[str, Any] = {
        "txid": tx.get("txid"),
        "wtxid": tx.get("wtxid"),
        "hash": tx.get("hash"),
        "withash": tx.get("withash"),
        "block_hash": tx.get("block_hash"),
        "block_height": tx.get("block_number"),
        "block_time": tx.get("block_timestamp"),
        "tx_index_in_block": tx.get("index", 0),
        "confirmed": True,
        "version": tx.get("version"),
        "lock_time": tx.get("lock_time"),
        "size": tx.get("size"),
        "vsize": tx.get("virtual_size"),
        "weight": tx.get("weight"),
        "discount_vsize": tx.get("discount_virtual_size"),
        "discount_weight": tx.get("discount_weight"),
        "vin_count": len(inputs),
        "vout_count": len(outputs),
        "fee_by_asset": fee_by_asset,
        "explicit_in_by_asset": explicit_in_by_asset,
        "explicit_out_by_asset": explicit_out_by_asset,
        "has_any_confidential": has_any_confidential,
        "has_pegin": has_pegin,
        "has_issuance": has_issuance,
    }

    txins: List[Dict[str, Any]] = []
    for vin_index, vin in enumerate(inputs):
        if not isinstance(vin, dict):
            continue
        issuance = vin.get("issuance") if isinstance(vin.get("issuance"), dict) else {}
        issuance_amount_sat = (
            to_satoshi(issuance.get("assetamount"))
            if issuance.get("assetamount") is not None
            else None
        )
        issuance_inflation_keys_sat = (
            to_satoshi(issuance.get("tokenamount"))
            if issuance.get("tokenamount") is not None
            else None
        )
        addr = None
        addrs = vin.get("addresses")
        if isinstance(addrs, list) and addrs:
            addr = addrs[0]

        txins.append(
            {
                "txid": tx.get("txid"),
                "vin": vin.get("vin", vin_index),
                "prev_txid": vin.get("txid"),
                "prev_vout": vin.get("vout"),
                "sequence": vin.get("sequence"),
                "is_coinbase": bool(vin.get("is_coinbase")),
                "scriptsig_hex": vin.get("scriptsig_hex"),
                "scriptsig_asm": vin.get("scriptsig_asm"),
                "txinwitness": vin.get("witness"),
                "pegin_witness": vin.get("pegin_witness"),
                "is_pegin": vin.get("input_type") == "pegin",
                "has_issuance": vin.get("input_type") == "issuance",
                "issuance_asset_blinding_nonce": issuance.get("assetBlindingNonce"),
                "issuance_asset_entropy": issuance.get("assetEntropy"),
                "issuance_amount": issuance_amount_sat,
                "issuance_inflation_keys": issuance_inflation_keys_sat,
                "prevout_scriptpubkey_hex": vin.get("scriptpubkey_hex"),
                "prevout_script_type": vin.get("type"),
                "prevout_address": addr,
            }
        )

    txouts: List[Dict[str, Any]] = []
    for vout in outputs:
        if not isinstance(vout, dict):
            continue
        addr = None
        addrs = vout.get("addresses")
        if isinstance(addrs, list) and addrs:
            addr = addrs[0]

        value_sat = to_satoshi(vout.get("value")) if vout.get("value") is not None else None

        txouts.append(
            {
                "txid": tx.get("txid"),
                "vout": vout.get("n"),
                "asset_id": vout.get("asset"),
                "asset_commitment": vout.get("asset_commitment"),
                "value_sat": value_sat,
                "value_commitment": vout.get("confidential_value"),
                "scriptpubkey_hex": vout.get("scriptpubkey_hex"),
                "scriptpubkey_asm": vout.get("scriptpubkey_asm"),
                "script_type": vout.get("script_type"),
                "address": addr,
                "is_op_return": bool(vout.get("op_return_data_hex")),
                "op_return_data_hex": vout.get("op_return_data_hex"),
                "is_fee": vout.get("type") == "fee",
                "surjection_proof": vout.get("surjection_proof"),
            }
        )

    return tx_row, txins, txouts


def _aggregate_fee_by_asset(node_fee: Any) -> Optional[Dict[str, int]]:
    if not isinstance(node_fee, dict):
        return None
    fee_by_asset_map: Dict[str, int] = {}
    for asset, amount in node_fee.items():
        sat = to_satoshi(amount)
        if sat is None:
            continue
        k = str(asset)
        fee_by_asset_map[k] = fee_by_asset_map.get(k, 0) + int(sat)
    return fee_by_asset_map or None


def _aggregate_explicit_by_asset(
    items: List[Any], *, asset_key: str, value_key: str
) -> Optional[Dict[str, int]]:
    out: Dict[str, int] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        asset = it.get(asset_key)
        value = it.get(value_key)
        if asset is None or value is None:
            continue
        sat = to_satoshi(value)
        if sat is None:
            continue
        k = str(asset)
        out[k] = out.get(k, 0) + int(sat)
    return out or None
