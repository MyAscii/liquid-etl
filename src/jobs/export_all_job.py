from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple

from ..service import LiquidService
from .export_blocks_job import ExportBlocksJob
from .enrich_transactions_job import EnrichTransactionsJob


def _mkdir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def _batch_ranges(start: int, end: int, batch_size: int):
    cur = start
    while cur <= end:
        nxt = min(end, cur + batch_size - 1)
        yield cur, nxt
        cur = nxt + 1


def export_all(
    service: LiquidService,
    output_dir: str,
    date: Optional[str] = None,
    start_block: Optional[int] = None,
    end_block: Optional[int] = None,
    batch_size: int = 1000,
    enrich: bool = False,
) -> None:
    """Partition by date or block range and write Hive-style directories with NDJSON files."""

    chain_dir = Path(output_dir) / "chain=liquid"
    _mkdir(chain_dir)

    if date:
        s, e = service.get_block_range_for_date(date)
        base = chain_dir / f"date={date}"
        _mkdir(base)
        ranges = list(_batch_ranges(s, e, batch_size))
    else:
        if start_block is None or end_block is None:
            raise ValueError("When date is not provided, both start_block and end_block are required")
        base = chain_dir / f"blocks"
        _mkdir(base)
        ranges = list(_batch_ranges(start_block, end_block, batch_size))

    for i, (s, e) in enumerate(ranges):
        batch_dir = base / f"block_start={s}-block_end={e}"
        _mkdir(batch_dir)
        blocks_output = str(batch_dir / "blocks.json")
        tx_output = str(batch_dir / "transactions.json")

        ExportBlocksJob(service, s, e, blocks_output, tx_output).run()

        if enrich:
            enriched_output = str(batch_dir / "enriched_transactions.json")
            EnrichTransactionsJob(service, tx_output, enriched_output).run()