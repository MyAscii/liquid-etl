from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .amounts import amounts_map_to_satoshi_map, to_satoshi
from .script_parsing import disassemble_script, extract_op_return_data_hex


def normalize_block(block: Dict[str, Any], network: str) -> Dict[str, Any]:
    txs = block.get("tx", []) or []
    txids = []
    for t in txs:
        if isinstance(t, dict) and t.get("txid"):
            txids.append(t.get("txid"))

    extdata_type = None
    if (
        block.get("signblock_challenge")
        or block.get("signblock_witness_hex")
        or block.get("signblock_witness_asm")
    ):
        extdata_type = "proof"

    return {
        "network": network,
        "hash": block.get("hash"),
        "height": block.get("height"),
        "version": block.get("version"),
        "prev_block_hash": block.get("previousblockhash"),
        "next_block_hash": block.get("nextblockhash"),
        "merkle_root": block.get("merkleroot"),
        "time": block.get("time"),
        "median_time": block.get("mediantime"),
        "nonce": block.get("nonce"),
        "bits": block.get("bits"),
        "difficulty": block.get("difficulty"),
        "chainwork": block.get("chainwork"),
        "tx_count": block.get("nTx") if block.get("nTx") is not None else len(txs),
        "size": block.get("size"),
        "stripped_size": block.get("strippedsize"),
        "weight": block.get("weight"),
        "extdata_type": extdata_type,
        "signblock_challenge_hex": block.get("signblock_challenge"),
        "signblock_solution_hex": block.get("signblock_witness_hex"),
        "dynafed_current_params": block.get("current_federation") or block.get("current_params"),
        "dynafed_proposed_params": block.get("proposed_federation") or block.get("proposed_params"),
        "signblock_witness": block.get("signblock_witness"),
        "txids": txids,
    }


def _pick_address(spk: Any) -> Optional[str]:
    if not isinstance(spk, dict):
        return None
    addrs = spk.get("addresses")
    if isinstance(addrs, list) and addrs:
        return addrs[0]
    addr = spk.get("address")
    if isinstance(addr, str) and addr:
        return addr
    return None


def _is_pegout(vout: Dict[str, Any]) -> bool:
    spk = vout.get("scriptPubKey", {})
    if vout.get("is_pegout") or vout.get("pegout"):
        return True
    if isinstance(spk, dict) and (spk.get("pegout") or spk.get("type") == "pegout"):
        return True
    return False


def normalize_tx(
    tx: Dict[str, Any],
    block_row: Dict[str, Any],
    tx_index_in_block: int,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    network = block_row["network"]
    vins = tx.get("vin", []) or []
    vouts = tx.get("vout", []) or []

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

    fee_by_asset = amounts_map_to_satoshi_map(tx.get("fee"))

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
        explicit_in_by_asset[str(asset)] = explicit_in_by_asset.get(str(asset), 0) + sat

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
        explicit_out_by_asset[str(asset)] = explicit_out_by_asset.get(str(asset), 0) + sat

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
        "explicit_in_by_asset": explicit_in_by_asset or None,
        "explicit_out_by_asset": explicit_out_by_asset or None,
        "has_any_confidential": has_any_confidential,
        "has_pegin": has_pegin,
        "has_pegout": has_pegout,
        "has_issuance": has_issuance,
    }

    txins: List[Dict[str, Any]] = []
    for idx, vin in enumerate(vins):
        if not isinstance(vin, dict):
            continue
        scriptsig = vin.get("scriptSig") if isinstance(vin.get("scriptSig"), dict) else {}
        scriptsig_hex = scriptsig.get("hex") or (
            vin.get("coinbase") if vin.get("coinbase") else None
        )
        scriptsig_asm = scriptsig.get("asm")
        if scriptsig_hex and not scriptsig_asm:
            try:
                scriptsig_asm = disassemble_script(scriptsig_hex)
            except Exception:
                scriptsig_asm = None

        witness = vin.get("txinwitness")
        if witness is None:
            witness = vin.get("witness")

        prevout = vin.get("prevout") if isinstance(vin.get("prevout"), dict) else None
        spk = (
            prevout.get("scriptPubKey", {})
            if isinstance(prevout, dict) and isinstance(prevout.get("scriptPubKey"), dict)
            else {}
        )

        txins.append(
            {
                "network": network,
                "txid": tx.get("txid"),
                "vin": idx,
                "prev_txid": vin.get("txid"),
                "prev_vout": vin.get("vout"),
                "sequence": vin.get("sequence"),
                "is_coinbase": bool(vin.get("coinbase")),
                "scriptsig_hex": scriptsig_hex,
                "scriptsig_asm": scriptsig_asm,
                "txinwitness": witness,
                "pegin_witness": vin.get("pegin_witness"),
                "is_pegin": bool(vin.get("is_pegin")),
                "pegin_value_sat": (
                    to_satoshi(vin.get("pegin_value"))
                    if vin.get("pegin_value") is not None
                    else None
                ),
                "pegin_asset_id": vin.get("pegin_asset"),
                "pegin_genesis_hash": vin.get("pegin_genesis_hash"),
                "pegin_claim_script_hex": vin.get("pegin_claim_script"),
                "pegin_mainchain_tx_hex": vin.get("pegin_tx"),
                "pegin_merkle_proof_hex": vin.get("pegin_txout_proof"),
                "pegin_referenced_block_hash": vin.get("pegin_blockhash"),
                "has_issuance": bool("issuance" in vin or "assetissuance" in vin),
                "issuance_asset_blinding_nonce": (
                    (vin.get("issuance") or vin.get("assetissuance") or {}).get(
                        "assetBlindingNonce"
                    )
                    if isinstance(vin.get("issuance") or vin.get("assetissuance"), dict)
                    else None
                ),
                "issuance_asset_entropy": (
                    (vin.get("issuance") or vin.get("assetissuance") or {}).get("assetEntropy")
                    if isinstance(vin.get("issuance") or vin.get("assetissuance"), dict)
                    else None
                ),
                "issuance_amount": (
                    to_satoshi(
                        (vin.get("issuance") or vin.get("assetissuance") or {}).get("assetamount")
                    )
                    if isinstance(vin.get("issuance") or vin.get("assetissuance"), dict)
                    and (vin.get("issuance") or vin.get("assetissuance") or {}).get("assetamount")
                    is not None
                    else None
                ),
                "issuance_amount_commitment": (
                    (vin.get("issuance") or vin.get("assetissuance") or {}).get(
                        "assetamountcommitment"
                    )
                    if isinstance(vin.get("issuance") or vin.get("assetissuance"), dict)
                    else None
                ),
                "issuance_inflation_keys": (
                    to_satoshi(
                        (vin.get("issuance") or vin.get("assetissuance") or {}).get("tokenamount")
                    )
                    if isinstance(vin.get("issuance") or vin.get("assetissuance"), dict)
                    and (vin.get("issuance") or vin.get("assetissuance") or {}).get("tokenamount")
                    is not None
                    else None
                ),
                "issuance_inflation_keys_commitment": (
                    (vin.get("issuance") or vin.get("assetissuance") or {}).get(
                        "tokenamountcommitment"
                    )
                    if isinstance(vin.get("issuance") or vin.get("assetissuance"), dict)
                    else None
                ),
                "prevout_asset_id": prevout.get("asset") if isinstance(prevout, dict) else None,
                "prevout_value_sat": (
                    to_satoshi(prevout.get("value"))
                    if isinstance(prevout, dict) and prevout.get("value") is not None
                    else None
                ),
                "prevout_value_commitment": (
                    prevout.get("valuecommitment") if isinstance(prevout, dict) else None
                ),
                "prevout_asset_commitment": (
                    prevout.get("assetcommitment") if isinstance(prevout, dict) else None
                ),
                "prevout_scriptpubkey_hex": spk.get("hex") if isinstance(spk, dict) else None,
                "prevout_script_type": spk.get("type") if isinstance(spk, dict) else None,
                "prevout_address": _pick_address(spk),
            }
        )

    txouts: List[Dict[str, Any]] = []
    for vout in vouts:
        if not isinstance(vout, dict):
            continue
        spk = vout.get("scriptPubKey", {}) if isinstance(vout.get("scriptPubKey"), dict) else {}
        scriptpubkey_hex = spk.get("hex") if isinstance(spk, dict) else None
        op_return_data_hex = extract_op_return_data_hex(scriptpubkey_hex)
        is_fee = bool(vout.get("is_fee") or (isinstance(spk, dict) and spk.get("type") == "fee"))
        is_pegout = _is_pegout(vout)

        txouts.append(
            {
                "network": network,
                "txid": tx.get("txid"),
                "vout": vout.get("n"),
                "asset_id": vout.get("asset"),
                "asset_commitment": vout.get("assetcommitment"),
                "value_sat": (
                    to_satoshi(vout.get("value")) if vout.get("value") is not None else None
                ),
                "value_commitment": vout.get("valuecommitment"),
                "scriptpubkey_hex": scriptpubkey_hex,
                "scriptpubkey_asm": spk.get("asm") if isinstance(spk, dict) else None,
                "script_type": spk.get("type") if isinstance(spk, dict) else None,
                "address": _pick_address(spk),
                "is_op_return": bool(op_return_data_hex),
                "op_return_data_hex": op_return_data_hex,
                "is_fee": is_fee,
                "is_pegout": is_pegout,
                "pegout_chain_genesis_hash": (
                    (vout.get("pegout") or {}).get("genesis_hash")
                    if isinstance(vout.get("pegout"), dict)
                    else None
                ),
                "pegout_btc_scriptpubkey_hex": (
                    (vout.get("pegout") or {}).get("scriptpubkey")
                    if isinstance(vout.get("pegout"), dict)
                    else None
                ),
                "pegout_value_sat": (
                    to_satoshi((vout.get("pegout") or {}).get("value"))
                    if isinstance(vout.get("pegout"), dict)
                    and (vout.get("pegout") or {}).get("value") is not None
                    else None
                ),
                "pegout_asset_id": (
                    (vout.get("pegout") or {}).get("asset")
                    if isinstance(vout.get("pegout"), dict)
                    else None
                ),
                "pegout_extra_data_hex": (
                    (vout.get("pegout") or {}).get("extra_data")
                    if isinstance(vout.get("pegout"), dict)
                    else None
                ),
                "nonce": vout.get("nonce"),
                "surjection_proof": vout.get("surjectionproof"),
                "rangeproof": vout.get("rangeproof"),
                "spent": vout.get("spent"),
                "spent_by_txid": vout.get("spentby"),
                "spent_by_vin": vout.get("spentbyvin"),
                "spent_at_height": vout.get("spentheight"),
            }
        )

    return tx_row, txins, txouts
