from __future__ import annotations

import json
from typing import Any

from ..service import LiquidService


class EnrichTransactionsJob:
    def __init__(self, service: LiquidService, transactions_input: str, transactions_output: str):
        self.service = service
        self.transactions_input = transactions_input
        self.transactions_output = transactions_output

    def _default(self, obj: Any):
        # No decimals expected in enrichment additions; keep simple
        raise TypeError(f"Type not serializable: {type(obj)}")

    def run(self) -> None:
        with (
            open(self.transactions_input, "r", encoding="utf-8") as fin,
            open(self.transactions_output, "w", encoding="utf-8") as fout,
        ):
            for line in fin:
                if not line.strip():
                    continue
                tx = json.loads(line)
                # For each input with txid/vout, resolve prevout
                for vin in tx.get("inputs", []):
                    txid = vin.get("txid")
                    vout_index = vin.get("vout")
                    if not txid or vout_index is None:
                        continue
                    try:
                        prev = self.service.rpc.getrawtransaction(txid, verbose=True)
                        vouts = prev.get("vout", [])
                        if vout_index < len(vouts):
                            pv = vouts[vout_index]
                            spk = pv.get("scriptPubKey", {})
                            addrs = spk.get("addresses") or (
                                spk.get("address") and [spk.get("address")]
                            )
                            vin["addresses"] = addrs
                            vin["required_signatures"] = spk.get("reqSigs")
                            vin["type"] = spk.get("type")
                            vin["value"] = pv.get("value")
                            vin["asset"] = pv.get("asset")
                    except Exception:
                        # Best-effort; leave vin as-is on failure
                        pass
                fout.write(json.dumps(tx))
                fout.write("\n")
