from __future__ import annotations

import pytest
from liquidetl.service import BlockWithTxs, LiquidService


class StubService(LiquidService):
    def __init__(self) -> None:
        class _R:
            pass

        super().__init__(_R())

    def get_head_height(self) -> int:
        return 0

    def get_block_by_number(self, height: int) -> BlockWithTxs:
        block = {"hash": f"h{height}", "number": height, "timestamp": 1000 + height}
        # Real normalize_tx always sets 'index'; mirror that so writers can key rows.
        tx = {"hash": f"t{height}", "index": 0, "inputs": [], "outputs": []}
        return BlockWithTxs(block=block, transactions=[tx])


@pytest.fixture()
def stub_service() -> StubService:
    return StubService()
