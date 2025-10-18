from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from ..service import LiquidService


class LiquidStreamerAdapter:
    def __init__(self, service: LiquidService, output: str = "console", batch_size: int = 100, enrich: bool = False):
        self.service = service
        self.output = output
        self.batch_size = batch_size
        self.enrich = enrich
        self._pubsub = None
        self._topics = None

        if output and output.startswith("projects/"):
            try:
                from google.cloud import pubsub_v1
                self._pubsub = pubsub_v1.PublisherClient()
                # Subtopics
                self._topics = {
                    "blocks": f"{output}.blocks",
                    "transactions": f"{output}.transactions",
                }
            except Exception:
                raise RuntimeError("google-cloud-pubsub not installed; install with pip install -e .[streaming]")

    def _emit(self, topic: str, item: Dict[str, Any]):
        line = json.dumps(item)
        if self._pubsub:
            self._pubsub.publish(self._topics[topic], line.encode("utf-8"))
        else:
            print(line)

    def _inline_enrich(self, tx: Dict[str, Any]) -> None:
        # Best-effort inline enrichment
        if not self.enrich:
            return
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
                    addrs = spk.get("addresses") or (spk.get("address") and [spk.get("address")])
                    vin["addresses"] = addrs
                    vin["required_signatures"] = spk.get("reqSigs")
                    vin["type"] = spk.get("type")
                    vin["value"] = pv.get("value")
                    vin["asset"] = pv.get("asset")
            except Exception:
                pass

    def stream(self, start_block: int, lag: int = 0, poll_interval: float = 2.0) -> None:
        current = start_block
        batch_count = 0
        while True:
            try:
                head = self.service.get_head_height() - max(0, lag)
                if current > head:
                    time.sleep(poll_interval)
                    continue
                # Emit up to batch_size
                emitted = 0
                while emitted < self.batch_size and current <= head:
                    bundle = self.service.get_block_by_number(current)
                    block_item = bundle.block
                    block_item["item_id"] = block_item.get("hash")
                    self._emit("blocks", block_item)
                    for tx in bundle.transactions:
                        tx["item_id"] = tx.get("hash")
                        self._inline_enrich(tx)
                        self._emit("transactions", tx)
                    emitted += 1
                    current += 1
                batch_count += 1
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"stream error: {e}")
                time.sleep(max(5.0, poll_interval))