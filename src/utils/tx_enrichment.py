from __future__ import annotations

import logging
from typing import Any, Dict

import requests

from ..rpc import RpcError
from ..service import LiquidService

logger = logging.getLogger("liquidetl.enrichment")


def inline_enrich_inputs(service: LiquidService, tx: Dict[str, Any]) -> Dict[str, int]:
    """Resolve each input's prevout (address/value/asset) via getrawtransaction.

    Failures are counted, logged, and marked on the input (``enrichment_error``)
    rather than silently swallowed, so a pruned/no-txindex node does not produce
    data that merely looks complete. Only transport/RPC errors are caught; bugs
    (KeyError/AttributeError) still propagate.
    """
    stats = {"attempted": 0, "enriched": 0, "failed": 0}
    for vin in tx.get("inputs", []):
        if not isinstance(vin, dict):
            continue
        txid = vin.get("txid")
        vout_index = vin.get("vout")
        if not txid or vout_index is None:
            continue
        stats["attempted"] += 1
        try:
            prev = service.rpc.getrawtransaction(txid, verbose=True)
        except (RpcError, requests.RequestException) as e:
            stats["failed"] += 1
            vin["enrichment_error"] = str(e)
            logger.warning("enrichment failed for %s:%s: %s", txid, vout_index, e)
            continue

        vouts = prev.get("vout", []) if isinstance(prev, dict) else []
        if not isinstance(vout_index, int) or vout_index < 0 or vout_index >= len(vouts):
            stats["failed"] += 1
            vin["enrichment_error"] = (
                f"prevout index {vout_index} out of range ({len(vouts)} vouts)"
            )
            logger.warning("enrichment prevout %s:%s out of range", txid, vout_index)
            continue

        pv = vouts[vout_index]
        spk = pv.get("scriptPubKey", {}) if isinstance(pv, dict) else {}
        addrs = spk.get("addresses") or (spk.get("address") and [spk.get("address")])
        vin["addresses"] = addrs
        vin["required_signatures"] = spk.get("reqSigs")
        vin["type"] = spk.get("type")
        vin["value"] = pv.get("value")
        vin["asset"] = pv.get("asset")
        stats["enriched"] += 1
    return stats
