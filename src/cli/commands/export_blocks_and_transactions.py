from __future__ import annotations

import argparse

from ...jobs.export_blocks_job import ExportBlocksJob
from ...rpc import LiquidRpc
from ...service import LiquidService


def export_blocks_and_transactions(args: argparse.Namespace) -> int:
    rpc = LiquidRpc(args.provider_uri, datadir=args.datadir)
    service = LiquidService(rpc)
    job = ExportBlocksJob(
        service=service,
        start_block=args.start_block,
        end_block=args.end_block,
        blocks_output=args.blocks_output,
        transactions_output=args.transactions_output,
    )
    job.run()
    return 0
