from __future__ import annotations

import argparse

from ...jobs.export_all_job import export_all as _export_all
from ...rpc import LiquidRpc
from ...service import LiquidService


def export_all(args: argparse.Namespace) -> int:
    rpc = LiquidRpc(args.provider_uri, datadir=args.datadir)
    service = LiquidService(rpc)
    _export_all(
        service=service,
        output_dir=args.output,
        date=args.date,
        start_block=args.start_block,
        end_block=args.end_block,
        batch_size=args.batch_size,
        enrich=args.enrich,
    )
    return 0

