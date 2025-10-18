from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from .rpc import LiquidRpc


@dataclass
class BlockWithTxs:
    block: Dict[str, Any]
    transactions: List[Dict[str, Any]]


class LiquidService:
    """High-level service to fetch and normalize blocks and transactions."""

    def __init__(self, rpc: LiquidRpc):
        self.rpc = rpc

    # ---- Public API ----
    def get_block_by_number(self, height: int) -> BlockWithTxs:
        h = self.rpc.getblockhash(height)
        b = self.rpc.getblock(h, verbosity=2)
        block_item = self._normalize_block(b)
        tx_items = [self._normalize_tx(t, block_item, tx_index=i) for i, t in enumerate(b.get("tx", []))]
        return BlockWithTxs(block=block_item, transactions=tx_items)

    def get_head_height(self) -> int:
        return self.rpc.getblockcount()

    def get_block_range_for_date(self, date_str: str, start_hour: int = 0, end_hour: int = 24) -> Tuple[int, int]:
        """Approximate [start, end] height range that covers the UTC date window.

        Uses binary search over heights to find first block with time >= start,
        and last block with time < end. Block timestamps are not strictly
        monotonic, so slight drift outside the window can occur.
        """
        dt_start = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=start_hour, tzinfo=timezone.utc)
        dt_end = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=end_hour, tzinfo=timezone.utc)
        start_ts = int(dt_start.timestamp())
        end_ts = int(dt_end.timestamp())

        head = self.get_head_height()
        # Find first block with ts >= start_ts
        lo, hi = 0, head
        first = 0
        while lo <= hi:
            mid = (lo + hi) // 2
            bm = self.get_block_by_number(mid).block
            ts = bm["timestamp"]
            if ts < start_ts:
                lo = mid + 1
            else:
                first = mid
                hi = mid - 1
        # Find last block with ts < end_ts
        lo, hi = first, head
        last = head
        while lo <= hi:
            mid = (lo + hi) // 2
            bm = self.get_block_by_number(mid).block
            ts = bm["timestamp"]
            if ts >= end_ts:
                hi = mid - 1
            else:
                last = mid
                lo = mid + 1
        return first, last

    # ---- Normalization helpers ----
    def _normalize_block(self, b: Dict[str, Any]) -> Dict[str, Any]:
        # Elements block fields closely mirror Bitcoin
        return {
            "hash": b.get("hash"),
            "size": b.get("size"),
            "stripped_size": b.get("strippedsize"),
            "weight": b.get("weight"),
            "number": b.get("height"),
            "version": b.get("version"),
            "merkle_root": b.get("merkleroot"),
            "timestamp": b.get("time"),
            "nonce": b.get("nonce"),
            "bits": b.get("bits"),
            "transaction_count": len(b.get("tx", [])),
        }

    def _normalize_address_info(self, spk: Dict[str, Any]) -> Tuple[Optional[List[str]], Optional[int]]:
        addrs = spk.get("addresses") or (spk.get("address") and [spk.get("address")])
        req_sigs = spk.get("reqSigs")
        return addrs, req_sigs

    def _normalize_tx(self, t: Dict[str, Any], block_item: Dict[str, Any], tx_index: Optional[int] = None) -> Dict[str, Any]:
        is_coinbase = any("coinbase" in vin for vin in t.get("vin", []))
        inputs = []
        input_value_total: Optional[Decimal] = None
        outputs = []
        output_value_total: Optional[Decimal] = Decimal(0)
        confidential_present = False

        # Normalize inputs
        for vin in t.get("vin", []):
            itype = None
            if vin.get("is_pegin"):
                itype = "pegin"
            if "issuance" in vin:
                itype = "issuance"
            # Basic fields
            item: Dict[str, Any] = {
                "txid": vin.get("txid"),
                "vout": vin.get("vout"),
                "sequence": vin.get("sequence"),
                "type": itype,
            }
            # Amounts are not present on inputs here unless enriched
            inputs.append(item)

        # Normalize outputs
        for vout in t.get("vout", []):
            spk = vout.get("scriptPubKey", {})
            addrs, req_sigs = self._normalize_address_info(spk)
            # Elements includes asset ids
            asset = vout.get("asset") or (spk.get("asset") if isinstance(spk, dict) else None)
            # Confidential values
            value = vout.get("value")
            vcommit = vout.get("valuecommitment")
            acommit = vout.get("assetcommitment")
            is_confidential = (vcommit or acommit) and value is None
            # Pegout detection: common flags across Elements variants
            is_pegout = bool(
                vout.get("is_pegout")
                or vout.get("pegout")
                or (isinstance(spk, dict) and (spk.get("pegout") or spk.get("type") == "pegout"))
            )
            # Assign type with pegout priority, then confidential
            otype = "pegout" if is_pegout else ("confidential" if is_confidential else None)
            if is_confidential:
                confidential_present = True
            else:
                try:
                    output_value_total = (output_value_total or Decimal(0)) + (Decimal(str(value)) if value is not None else Decimal(0))
                except Exception:
                    pass
            outputs.append({
                "value": value,
                "confidential_value": vcommit,
                "asset": asset,
                "type": otype,
                "n": vout.get("n"),
                "addresses": addrs,
                "required_signatures": req_sigs,
            })

        # Totals and fee: only computable if non-confidential
        fee = None
        if not confidential_present:
            try:
                if input_value_total is not None and output_value_total is not None:
                    fee = str((input_value_total or Decimal(0)) - (output_value_total or Decimal(0)))
            except Exception:
                fee = None

        return {
            "hash": t.get("txid") or t.get("hash"),
            "size": t.get("size"),
            "virtual_size": t.get("vsize"),
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
            "input_value": str(input_value_total) if input_value_total is not None else None,
            "output_value": str(output_value_total) if output_value_total is not None else None,
            "fee": fee,
        }