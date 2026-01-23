from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from ..amounts import to_satoshi
from ..script_parsing import disassemble_script
from .address import pick_address


def normalize_vin(
    vin: Dict[str, Any], *, network: str, txid: Optional[str], vin_index: int
) -> Dict[str, Any]:
    scriptsig_hex, scriptsig_asm = _scriptsig_fields(vin)
    witness = vin.get("txinwitness")
    if witness is None:
        witness = vin.get("witness")

    prevout = vin.get("prevout") if isinstance(vin.get("prevout"), dict) else None
    spk = _prevout_spk(prevout)
    issuance = _issuance_dict(vin)

    return {
        "network": network,
        "txid": txid,
        "vin": vin_index,
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
            to_satoshi(vin.get("pegin_value")) if vin.get("pegin_value") is not None else None
        ),
        "pegin_asset_id": vin.get("pegin_asset"),
        "pegin_genesis_hash": vin.get("pegin_genesis_hash"),
        "pegin_claim_script_hex": vin.get("pegin_claim_script"),
        "pegin_mainchain_tx_hex": vin.get("pegin_tx"),
        "pegin_merkle_proof_hex": vin.get("pegin_txout_proof"),
        "pegin_referenced_block_hash": vin.get("pegin_blockhash"),
        "has_issuance": bool("issuance" in vin or "assetissuance" in vin),
        "issuance_asset_blinding_nonce": issuance.get("assetBlindingNonce") if issuance else None,
        "issuance_asset_entropy": issuance.get("assetEntropy") if issuance else None,
        "issuance_amount": (
            to_satoshi(issuance.get("assetamount"))
            if issuance and issuance.get("assetamount") is not None
            else None
        ),
        "issuance_amount_commitment": issuance.get("assetamountcommitment") if issuance else None,
        "issuance_inflation_keys": (
            to_satoshi(issuance.get("tokenamount"))
            if issuance and issuance.get("tokenamount") is not None
            else None
        ),
        "issuance_inflation_keys_commitment": (
            issuance.get("tokenamountcommitment") if issuance else None
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
        "prevout_address": pick_address(spk),
    }


def _scriptsig_fields(vin: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    scriptsig = vin.get("scriptSig") if isinstance(vin.get("scriptSig"), dict) else {}
    scriptsig_hex = scriptsig.get("hex") or (vin.get("coinbase") if vin.get("coinbase") else None)
    scriptsig_asm = scriptsig.get("asm")
    if scriptsig_hex and not scriptsig_asm:
        try:
            scriptsig_asm = disassemble_script(scriptsig_hex)
        except Exception:
            scriptsig_asm = None
    return scriptsig_hex, scriptsig_asm


def _prevout_spk(prevout: Any) -> Dict[str, Any]:
    if not isinstance(prevout, dict):
        return {}
    spk = prevout.get("scriptPubKey")
    return spk if isinstance(spk, dict) else {}


def _issuance_dict(vin: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    issuance = vin.get("issuance") or vin.get("assetissuance")
    return issuance if isinstance(issuance, dict) else None
