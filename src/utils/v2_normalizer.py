from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .amounts import amounts_map_to_satoshi_map, to_satoshi
from .script_parsing import disassemble_script, extract_op_return_data_hex


def normalize_block_v2(block: Dict[str, Any], network: str) -> Dict[str, Any]:
    txs = block.get("tx", []) or []
    txids = []
    for t in txs:
        if isinstance(t, dict) and t.get("txid"):
            txids.append(t.get("txid"))

    extdata_type = None
    if block.get("signblock_challenge") or block.get("signblock_witness_hex") or block.get("signblock_witness_asm"):
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
        "raw_block_hex": None,
        "raw_block_json": block,
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


def normalize_tx_v2(
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
        if vout.get("valuecommitment") or vout.get("assetcommitment") or vout.get("surjectionproof") or vout.get("rangeproof"):
            has_any_confidential = True
        if _is_pegout(vout):
            has_pegout = True

    fee_by_asset = amounts_map_to_satoshi_map(tx.get("fee"))

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
        "explicit_in_by_asset": {},
        "explicit_out_by_asset": explicit_out_by_asset,
        "has_any_confidential": has_any_confidential,
        "has_pegin": has_pegin,
        "has_pegout": has_pegout,
        "has_issuance": has_issuance,
        "raw_tx_hex": tx.get("hex"),
        "raw_tx_json": tx,
    }

    txins: List[Dict[str, Any]] = []
    for i, vin in enumerate(vins):
        if not isinstance(vin, dict):
            continue
        is_coinbase = "coinbase" in vin
        scriptsig = vin.get("scriptSig") if isinstance(vin.get("scriptSig"), dict) else {}
        scriptsig_hex = scriptsig.get("hex")
        scriptsig_asm = scriptsig.get("asm")
        coinbase_hex = vin.get("coinbase") if is_coinbase else None
        if is_coinbase and not scriptsig_hex:
            scriptsig_hex = coinbase_hex
        if is_coinbase and scriptsig_hex and not scriptsig_asm:
            scriptsig_asm = disassemble_script(scriptsig_hex)

        txinwitness = vin.get("txinwitness") or vin.get("witness")
        pegin_witness = vin.get("pegin_witness") or vin.get("pegin_witness_stack")

        issuance = vin.get("issuance") if isinstance(vin.get("issuance"), dict) else (vin.get("assetissuance") if isinstance(vin.get("assetissuance"), dict) else None)

        prevout = vin.get("prevout") if isinstance(vin.get("prevout"), dict) else None
        prevout_spk = prevout.get("scriptPubKey", {}) if isinstance(prevout, dict) and isinstance(prevout.get("scriptPubKey"), dict) else {}

        txins.append(
            {
                "network": network,
                "txid": tx.get("txid"),
                "vin": i,
                "prev_txid": vin.get("txid"),
                "prev_vout": vin.get("vout"),
                "sequence": vin.get("sequence"),
                "is_coinbase": is_coinbase,
                "scriptsig_hex": scriptsig_hex,
                "scriptsig_asm": scriptsig_asm,
                "txinwitness": txinwitness,
                "pegin_witness": pegin_witness,
                "is_pegin": bool(vin.get("is_pegin")),
                "pegin_value_sat": to_satoshi(vin.get("pegin_value")) if vin.get("pegin_value") is not None else None,
                "pegin_asset_id": vin.get("pegin_asset") or vin.get("pegin_asset_id"),
                "pegin_genesis_hash": vin.get("pegin_genesis_hash"),
                "pegin_claim_script_hex": vin.get("pegin_claim_script") or vin.get("pegin_claim_script_hex"),
                "pegin_mainchain_tx_hex": vin.get("pegin_tx") or vin.get("pegin_mainchain_tx_hex"),
                "pegin_merkle_proof_hex": vin.get("pegin_merkle_proof") or vin.get("pegin_merkle_proof_hex"),
                "pegin_referenced_block_hash": vin.get("pegin_reference_block") or vin.get("pegin_referenced_block_hash"),
                "has_issuance": issuance is not None,
                "issuance_asset_blinding_nonce": issuance.get("assetBlindingNonce") if issuance else None,
                "issuance_asset_entropy": issuance.get("assetEntropy") if issuance else None,
                "issuance_amount": to_satoshi(issuance.get("assetamount")) if issuance and issuance.get("assetamount") is not None else None,
                "issuance_amount_commitment": issuance.get("assetamountcommitment") if issuance else None,
                "issuance_inflation_keys": to_satoshi(issuance.get("tokenamount")) if issuance and issuance.get("tokenamount") is not None else None,
                "issuance_inflation_keys_commitment": issuance.get("tokenamountcommitment") if issuance else None,
                "prevout_asset_id": prevout.get("asset") if prevout else None,
                "prevout_value_sat": to_satoshi(prevout.get("value")) if prevout else None,
                "prevout_value_commitment": prevout.get("valuecommitment") if prevout else None,
                "prevout_asset_commitment": prevout.get("assetcommitment") if prevout else None,
                "prevout_scriptpubkey_hex": prevout_spk.get("hex") if isinstance(prevout_spk, dict) else None,
                "prevout_script_type": prevout_spk.get("type") if isinstance(prevout_spk, dict) else None,
                "prevout_address": _pick_address(prevout_spk),
            }
        )

    txouts: List[Dict[str, Any]] = []
    for vout in vouts:
        if not isinstance(vout, dict):
            continue
        spk = vout.get("scriptPubKey", {}) if isinstance(vout.get("scriptPubKey"), dict) else {}
        spk_hex = spk.get("hex") if isinstance(spk, dict) else None
        spk_asm = spk.get("asm") if isinstance(spk, dict) else None
        spk_type = spk.get("type") if isinstance(spk, dict) else None
        is_fee = spk_type == "fee"
        is_op_return = bool((spk_asm and str(spk_asm).startswith("OP_RETURN")) or (spk_hex and str(spk_hex).lower().startswith("6a")))

        pegout = vout.get("pegout") if isinstance(vout.get("pegout"), dict) else None

        txouts.append(
            {
                "network": network,
                "txid": tx.get("txid"),
                "vout": vout.get("n"),
                "asset_id": vout.get("asset"),
                "asset_commitment": vout.get("assetcommitment"),
                "value_sat": to_satoshi(vout.get("value")) if vout.get("value") is not None else None,
                "value_commitment": vout.get("valuecommitment"),
                "scriptpubkey_hex": spk_hex,
                "scriptpubkey_asm": spk_asm,
                "script_type": spk_type,
                "address": _pick_address(spk),
                "is_op_return": is_op_return,
                "op_return_data_hex": extract_op_return_data_hex(spk_hex) if spk_hex else None,
                "is_fee": is_fee,
                "is_pegout": _is_pegout(vout),
                "pegout_chain_genesis_hash": pegout.get("genesis_hash") if pegout else None,
                "pegout_btc_scriptpubkey_hex": pegout.get("scriptPubKey") if pegout else None,
                "pegout_value_sat": to_satoshi(pegout.get("value")) if pegout and pegout.get("value") is not None else None,
                "pegout_asset_id": pegout.get("asset") if pegout else None,
                "pegout_extra_data_hex": pegout.get("extra_data") if pegout else None,
                "nonce": vout.get("commitmentnonce"),
                "surjection_proof": vout.get("surjectionproof"),
                "rangeproof": vout.get("rangeproof"),
                "spent": None,
                "spent_by_txid": None,
                "spent_by_vin": None,
                "spent_at_height": None,
            }
        )

    return tx_row, txins, txouts

