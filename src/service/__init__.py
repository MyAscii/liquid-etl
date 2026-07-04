from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..rpc import LiquidRpc
from .normalize_block import normalize_block
from .normalize_tx import normalize_address_info, normalize_tx
from .range import get_block_range_for_date as _get_block_range_for_date


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
        b = self.rpc.getblock(h, verbosity=3)
        block_item = self._normalize_block(b)
        tx_items = [
            self._normalize_tx(t, block_item, tx_index=i) for i, t in enumerate(b.get("tx", []))
        ]
        return BlockWithTxs(block=block_item, transactions=tx_items)

    def get_blocks_by_numbers(self, heights: List[int]) -> List[BlockWithTxs]:
        if not heights:
            return []
        hashes = self.rpc.batch_call([("getblockhash", [h]) for h in heights])
        blocks = self.rpc.batch_call([("getblock", [block_hash, 3]) for block_hash in hashes])
        bundles: List[BlockWithTxs] = []
        for b in blocks:
            block_item = self._normalize_block(b)
            tx_items = [
                self._normalize_tx(t, block_item, tx_index=i) for i, t in enumerate(b.get("tx", []))
            ]
            bundles.append(BlockWithTxs(block=block_item, transactions=tx_items))
        return bundles

    def get_head_height(self) -> int:
        return self.rpc.getblockcount()

    def get_block_range_for_date(
        self, date_str: str, start_hour: int = 0, end_hour: int = 24
    ) -> Tuple[int, int]:
        head = self.get_head_height()
        return _get_block_range_for_date(
            get_block_timestamp=lambda h: self.get_block_by_number(h).block["timestamp"],
            head_height=head,
            date_str=date_str,
            start_hour=start_hour,
            end_hour=end_hour,
        )

    # ---- Normalization helpers ----
    def _normalize_block(self, b: Dict[str, Any]) -> Dict[str, Any]:
        return normalize_block(b)

    def _normalize_address_info(
        self, spk: Dict[str, Any]
    ) -> Tuple[Optional[List[str]], Optional[int]]:
        return normalize_address_info(spk)

    def _normalize_tx(
        self, t: Dict[str, Any], block_item: Dict[str, Any], tx_index: Optional[int] = None
    ) -> Dict[str, Any]:
        return normalize_tx(self.rpc, t, block_item, tx_index)
