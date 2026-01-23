from __future__ import annotations

from typing import Any, Dict, Optional

from ..amounts import to_satoshi
from ..script_parsing import extract_op_return_data_hex
from .address import pick_address


def normalize_vout(vout: Dict[str, Any], *, network: str, txid: Optional[str]) -> Dict[str, Any]:
    spk = vout.get("scriptPubKey", {}) if isinstance(vout.get("scriptPubKey"), dict) else {}
    scriptpubkey_hex = spk.get("hex") if isinstance(spk, dict) else None
    op_return_data_hex = extract_op_return_data_hex(scriptpubkey_hex)
    is_fee = bool(vout.get("is_fee") or (isinstance(spk, dict) and spk.get("type") == "fee"))
    is_pegout = _is_pegout(vout)

    pegout = vout.get("pegout") if isinstance(vout.get("pegout"), dict) else None

    return {
        "network": network,
        "txid": txid,
        "vout": vout.get("n"),
        "asset_id": vout.get("asset"),
        "asset_commitment": vout.get("assetcommitment"),
        "value_sat": to_satoshi(vout.get("value")) if vout.get("value") is not None else None,
        "value_commitment": vout.get("valuecommitment"),
        "scriptpubkey_hex": scriptpubkey_hex,
        "scriptpubkey_asm": spk.get("asm") if isinstance(spk, dict) else None,
        "script_type": spk.get("type") if isinstance(spk, dict) else None,
        "address": pick_address(spk),
        "is_op_return": bool(op_return_data_hex),
        "op_return_data_hex": op_return_data_hex,
        "is_fee": is_fee,
        "is_pegout": is_pegout,
        "pegout_chain_genesis_hash": pegout.get("genesis_hash") if pegout else None,
        "pegout_btc_scriptpubkey_hex": pegout.get("scriptpubkey") if pegout else None,
        "pegout_value_sat": to_satoshi(pegout.get("value")) if pegout and pegout.get("value") is not None else None,
        "pegout_asset_id": pegout.get("asset") if pegout else None,
        "pegout_extra_data_hex": pegout.get("extra_data") if pegout else None,
        "nonce": vout.get("nonce"),
        "surjection_proof": vout.get("surjectionproof"),
        "rangeproof": vout.get("rangeproof"),
        "spent": vout.get("spent"),
        "spent_by_txid": vout.get("spentby"),
        "spent_by_vin": vout.get("spentbyvin"),
        "spent_at_height": vout.get("spentheight"),
    }


def _is_pegout(vout: Dict[str, Any]) -> bool:
    spk = vout.get("scriptPubKey", {})
    if vout.get("is_pegout") or vout.get("pegout"):
        return True
    if isinstance(spk, dict) and (spk.get("pegout") or spk.get("type") == "pegout"):
        return True
    return False

