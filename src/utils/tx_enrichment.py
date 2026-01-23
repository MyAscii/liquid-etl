from __future__ import annotations

from typing import Any, Dict

from ..service import LiquidService


def inline_enrich_inputs(service: LiquidService, tx: Dict[str, Any]) -> None:
    for vin in tx.get("inputs", []):
        txid = vin.get("txid")
        vout_index = vin.get("vout")
        if not txid or vout_index is None:
            continue
        try:
            prev = service.rpc.getrawtransaction(txid, verbose=True)
            vouts = prev.get("vout", [])
            if vout_index < len(vouts):
                pv = vouts[vout_index]
                spk = pv.get("scriptPubKey", {})
                addrs = spk.get("addresses") or (spk.get("address") and [spk.get("address")])
                vin["addresses"] = addrs
                vin["required_signatures"] = spk.get("reqSigs")
                vin["type"] = spk.get("type")
                vin["value"] = pv.get("value")
                vin["asset"] = pv.get("asset")
        except Exception:
            pass

