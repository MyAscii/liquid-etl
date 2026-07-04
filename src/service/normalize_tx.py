from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from ..utils.script_parsing import disassemble_script, extract_op_return_data_hex


def normalize_tx(
    rpc: Any,
    t: Dict[str, Any],
    block_item: Dict[str, Any],
    tx_index: Optional[int] = None,
) -> Dict[str, Any]:
    is_coinbase = any(isinstance(vin, dict) and "coinbase" in vin for vin in t.get("vin", []))
    inputs: List[Dict[str, Any]] = []
    input_value_total: Decimal = Decimal(0)
    inputs_all_explicit = True
    outputs: List[Dict[str, Any]] = []
    output_value_total: Optional[Decimal] = Decimal(0)
    confidential_present = False

    for vin in t.get("vin", []):
        if not isinstance(vin, dict):
            # A malformed input we cannot value; do not crash and do not claim a fee.
            inputs_all_explicit = False
            continue
        itype = None
        if vin.get("is_pegin"):
            itype = "pegin"
        if "issuance" in vin or "assetissuance" in vin:
            itype = "issuance"
        scriptsig_hex, scriptsig_asm, coinbase_hex = _scriptsig_fields(rpc, vin)

        witness = vin.get("txinwitness")
        if witness is None:
            witness = vin.get("witness")

        issuance = vin.get("issuance") if isinstance(vin.get("issuance"), dict) else None
        if issuance is None and isinstance(vin.get("assetissuance"), dict):
            issuance = vin.get("assetissuance")

        item: Dict[str, Any] = {
            "txid": vin.get("txid"),
            "vout": vin.get("vout"),
            "sequence": vin.get("sequence"),
            "input_type": itype,
            "is_coinbase": bool("coinbase" in vin),
            "scriptsig_asm": scriptsig_asm,
            "scriptsig_hex": scriptsig_hex,
            "coinbase_hex": coinbase_hex,
            "witness": witness,
            "is_pegin": bool(vin.get("is_pegin")),
            "pegin_witness": vin.get("pegin_witness"),
            "pegin_value": vin.get("pegin_value"),
            "pegin_asset": vin.get("pegin_asset"),
            "pegin_genesis_hash": vin.get("pegin_genesis_hash"),
            "pegin_claim_script": vin.get("pegin_claim_script"),
            "pegin_tx": vin.get("pegin_tx"),
            "pegin_txout_proof": vin.get("pegin_txout_proof"),
            "pegin_blockhash": vin.get("pegin_blockhash"),
            "issuance": issuance,
        }

        prevout = vin.get("prevout") if isinstance(vin.get("prevout"), dict) else None
        prevout_value = None
        if prevout:
            spk = (
                prevout.get("scriptPubKey", {})
                if isinstance(prevout.get("scriptPubKey"), dict)
                else {}
            )
            addrs, req_sigs = normalize_address_info(spk)
            item["addresses"] = addrs
            item["required_signatures"] = req_sigs
            item["type"] = spk.get("type")
            prevout_value = prevout.get("value")
            item["value"] = prevout_value
            item["asset"] = prevout.get("asset")
            item["scriptpubkey_asm"] = spk.get("asm")
            item["scriptpubkey_hex"] = spk.get("hex")

        # Accumulate input value only when every non-coinbase input has an explicit
        # prevout value; otherwise the fee is not computable and stays null.
        if not item["is_coinbase"]:
            if prevout_value is not None:
                try:
                    input_value_total += Decimal(str(prevout_value))
                except (InvalidOperation, ValueError):
                    inputs_all_explicit = False
            else:
                inputs_all_explicit = False

        inputs.append(item)

    for vout in t.get("vout", []):
        spk = vout.get("scriptPubKey", {})
        addrs, req_sigs = normalize_address_info(spk)
        asset = vout.get("asset") or (spk.get("asset") if isinstance(spk, dict) else None)
        value = vout.get("value")
        vcommit = vout.get("valuecommitment")
        acommit = vout.get("assetcommitment")
        is_confidential = (vcommit or acommit) and value is None
        is_pegout = bool(
            vout.get("is_pegout")
            or vout.get("pegout")
            or vout.get("pegout_chain")
            or (isinstance(spk, dict) and (spk.get("pegout") or spk.get("type") == "pegout"))
        )
        is_fee = bool(vout.get("is_fee") or (isinstance(spk, dict) and spk.get("type") == "fee"))
        otype = (
            "pegout"
            if is_pegout
            else ("fee" if is_fee else ("confidential" if is_confidential else None))
        )

        if is_confidential:
            confidential_present = True
        else:
            try:
                output_value_total = (output_value_total or Decimal(0)) + (
                    Decimal(str(value)) if value is not None else Decimal(0)
                )
            except Exception:
                pass

        scriptpubkey_hex = spk.get("hex") if isinstance(spk, dict) else None
        scriptpubkey_asm = spk.get("asm") if isinstance(spk, dict) else None
        op_return_data_hex = extract_op_return_data_hex(scriptpubkey_hex)
        pegout = vout.get("pegout") if isinstance(vout.get("pegout"), dict) else None
        outputs.append(
            {
                "value": value,
                "confidential_value": vcommit,
                "asset_commitment": acommit,
                "asset": asset,
                "type": otype,
                "n": vout.get("n"),
                "addresses": addrs,
                "required_signatures": req_sigs,
                "scriptpubkey_asm": scriptpubkey_asm,
                "scriptpubkey_hex": scriptpubkey_hex,
                "script_type": spk.get("type") if isinstance(spk, dict) else None,
                "op_return_data_hex": op_return_data_hex,
                "nonce": vout.get("nonce"),
                "surjection_proof": vout.get("surjectionproof"),
                "rangeproof": vout.get("rangeproof"),
                "pegout_chain_genesis_hash": pegout.get("genesis_hash") if pegout else None,
                "pegout_btc_scriptpubkey_hex": pegout.get("scriptpubkey") if pegout else None,
                "pegout_value": pegout.get("value") if pegout else None,
                "pegout_asset": pegout.get("asset") if pegout else None,
                "pegout_extra_data_hex": pegout.get("extra_data") if pegout else None,
            }
        )

    input_value = (
        input_value_total if (inputs and not is_coinbase and inputs_all_explicit) else None
    )

    fee = None
    if not confidential_present and input_value is not None and output_value_total is not None:
        fee = str(input_value - output_value_total)

    return {
        "hash": t.get("txid") or t.get("hash"),
        "txid": t.get("txid"),
        "wtxid": t.get("wtxid"),
        "withash": t.get("withash"),
        "tx_hex": t.get("hex"),
        "size": t.get("size"),
        "virtual_size": t.get("vsize"),
        "discount_virtual_size": t.get("discountvsize"),
        "weight": t.get("weight"),
        "discount_weight": t.get("discountweight"),
        "sigops": t.get("sigops"),
        "version": t.get("version"),
        "lock_time": t.get("locktime"),
        "block_number": block_item.get("number"),
        "block_hash": block_item.get("hash"),
        "block_timestamp": block_item.get("timestamp"),
        "is_coinbase": is_coinbase,
        "index": tx_index,
        "inputs": inputs,
        "outputs": outputs,
        "input_count": len(inputs),
        "output_count": len(outputs),
        "input_value": str(input_value) if input_value is not None else None,
        "output_value": str(output_value_total) if output_value_total is not None else None,
        "fee": fee,
        "node_fee": t.get("fee"),
    }


def normalize_address_info(spk: Dict[str, Any]) -> Tuple[Optional[List[str]], Optional[int]]:
    addrs = spk.get("addresses") or (spk.get("address") and [spk.get("address")])
    req_sigs = spk.get("reqSigs")
    return addrs, req_sigs


def _scriptsig_fields(
    rpc: Any, vin: Dict[str, Any]
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    scriptsig = vin.get("scriptSig") if isinstance(vin.get("scriptSig"), dict) else {}
    is_coinbase_input = "coinbase" in vin
    scriptsig_hex = scriptsig.get("hex")
    scriptsig_asm = scriptsig.get("asm")
    coinbase_hex = vin.get("coinbase") if is_coinbase_input else None

    if is_coinbase_input and not scriptsig_hex:
        scriptsig_hex = coinbase_hex
    if is_coinbase_input and scriptsig_hex:
        scriptsig_asm = disassemble_script(scriptsig_hex) or scriptsig_asm
    elif scriptsig_hex and not scriptsig_asm:
        try:
            scriptsig_asm = rpc.decodescript(scriptsig_hex).get("asm")
        except Exception:
            scriptsig_asm = disassemble_script(scriptsig_hex)

    return scriptsig_hex, scriptsig_asm, coinbase_hex
