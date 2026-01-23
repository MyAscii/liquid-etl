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
        tx = {"hash": f"t{height}", "inputs": [], "outputs": []}
        return BlockWithTxs(block=block, transactions=[tx])


@pytest.fixture()
def stub_service() -> StubService:
    return StubService()
