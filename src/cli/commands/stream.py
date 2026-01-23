from __future__ import annotations

import argparse
import sys
from typing import Optional

from ...rpc import LiquidRpc
from ...service import LiquidService
from ...streaming.streamer_adapter import LiquidStreamerAdapter


def stream(args: argparse.Namespace) -> int:
    start_block = _resolve_start_block(args)
    if start_block is None:
        return 1

    rpc = LiquidRpc(args.provider_uri, datadir=args.datadir)
    service = LiquidService(rpc)
    adapter = LiquidStreamerAdapter(
        service=service,
        output=args.output,
        batch_size=args.batch_size,
        enrich=args.enrich,
    )
    adapter.stream(start_block=start_block, lag=args.lag, poll_interval=args.poll_interval)
    return 0


def _resolve_start_block(args: argparse.Namespace) -> Optional[int]:
    start_block = args.start_block
    if start_block is not None:
        return int(start_block)

    if args.output.startswith("postgres://") or args.output.startswith("postgresql://"):
        return _resume_start_from_postgres(args.output)

    print("Error: --start-block is required unless output is a Postgres DB", file=sys.stderr)
    return None


def _resume_start_from_postgres(dsn: str) -> Optional[int]:
    from ...utils.postgres_writer import PostgresWriter

    try:
        tmp_writer = PostgresWriter(dsn)
        max_height = tmp_writer.get_max_block_height()
        tmp_writer.close()
        if max_height is not None:
            start_block = max_height + 1
            print(f"Resuming from block {start_block} (DB max height: {max_height})", file=sys.stderr)
            return start_block
        print("Database empty, starting from block 0", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"Error checking DB state: {e}", file=sys.stderr)
        return None
