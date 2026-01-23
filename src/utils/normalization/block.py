from __future__ import annotations

from typing import Any, Dict


def normalize_block(block: Dict[str, Any], network: str) -> Dict[str, Any]:
    txs = block.get("tx", []) or []
    txids = []
    for t in txs:
        if isinstance(t, dict) and t.get("txid"):
            txids.append(t.get("txid"))

    extdata_type = None
    if block.get("signblock_challenge") or block.get("signblock_witness_hex") or block.get(
        "signblock_witness_asm"
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

