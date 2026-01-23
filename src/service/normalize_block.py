from __future__ import annotations

from typing import Any, Dict, List


def normalize_block(b: Dict[str, Any]) -> Dict[str, Any]:
    txids: List[str] = []
    for t in b.get("tx", []) or []:
        if isinstance(t, str):
            txids.append(t)
        elif isinstance(t, dict) and t.get("txid"):
            txids.append(t.get("txid"))
    return {
        "hash": b.get("hash"),
        "confirmations": b.get("confirmations"),
        "size": b.get("size"),
        "stripped_size": b.get("strippedsize"),
        "weight": b.get("weight"),
        "number": b.get("height"),
        "version": b.get("version"),
        "version_hex": b.get("versionHex"),
        "merkle_root": b.get("merkleroot"),
        "timestamp": b.get("time"),
        "median_time": b.get("mediantime"),
        "nonce": b.get("nonce"),
        "bits": b.get("bits"),
        "difficulty": b.get("difficulty"),
        "chainwork": b.get("chainwork"),
        "previous_block_hash": b.get("previousblockhash"),
        "next_block_hash": b.get("nextblockhash"),
        "transaction_count": b.get("nTx") if b.get("nTx") is not None else len(b.get("tx", [])),
        "signblock_challenge": b.get("signblock_challenge"),
        "signblock_witness_asm": b.get("signblock_witness_asm"),
        "signblock_witness_hex": b.get("signblock_witness_hex"),
        "dynafed_current_params": b.get("current_federation") or b.get("current_params"),
        "dynafed_proposed_params": b.get("proposed_federation") or b.get("proposed_params"),
        "signblock_witness": b.get("signblock_witness"),
        "txids": txids,
    }
