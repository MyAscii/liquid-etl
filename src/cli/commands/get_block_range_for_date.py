from __future__ import annotations

import argparse

from ...rpc import LiquidRpc
from ...service import LiquidService


def get_block_range_for_date(args: argparse.Namespace) -> int:
    rpc = LiquidRpc(args.provider_uri, datadir=args.datadir)
    service = LiquidService(rpc)
    start, end = service.get_block_range_for_date(args.date, args.start_hour, args.end_hour)
    print(f"{start} {end}")
    return 0

