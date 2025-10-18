from __future__ import annotations

from typing import Optional

from ..service import LiquidService
from ..utils.io import append_ndjson


class ExportBlocksJob:
    def __init__(
        self,
        service: LiquidService,
        start_block: int,
        end_block: int,
        blocks_output: str,
        transactions_output: str,
    ):
        self.service = service
        self.start_block = start_block
        self.end_block = end_block
        self.blocks_output = blocks_output
        self.transactions_output = transactions_output

    def run(self) -> None:
        if self.start_block > self.end_block:
            raise ValueError("start_block must be <= end_block")
        for height in range(self.start_block, self.end_block + 1):
            bundle = self.service.get_block_by_number(height)
            append_ndjson(bundle.block, self.blocks_output)
            for tx in bundle.transactions:
                append_ndjson(tx, self.transactions_output)