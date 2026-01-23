from __future__ import annotations

import argparse
import sys
import time
from typing import Any, Iterable, List, Sequence, Tuple

from ..progress import fmt_eta, render_bar


def ingest_range_to_postgres(args: argparse.Namespace) -> int:
    from ...rpc import LiquidRpc
    from ...utils.normalizer import normalize_block, normalize_tx
    from ...utils.postgres_writer import PostgresWriter

    rpc = LiquidRpc(args.provider_uri, datadir=args.datadir)
    writer = PostgresWriter(args.dsn)
    show_progress = _should_show_progress(args)
    total = int(args.end_block) - int(args.start_block) + 1
    rpc_batch_size = max(1, int(getattr(args, "rpc_batch_size", 25)))

    try:
        started = time.monotonic()
        last_render = started
        done = 0
        for chunk in _chunked_range(int(args.start_block), int(args.end_block), rpc_batch_size):
            raw_blocks = _fetch_raw_blocks(rpc, chunk, show_progress)
            block_rows, tx_rows, txin_rows, txout_rows = _normalize_raw_blocks(
                raw_blocks, normalize_block=normalize_block, normalize_tx=normalize_tx
            )
            writer.write_chunk(block_rows, tx_rows, txin_rows, txout_rows)
            done, last_render = _render_progress(
                raw_blocks=raw_blocks,
                done=done,
                total=total,
                started=started,
                last_render=last_render,
                show_progress=show_progress,
            )
    finally:
        writer.close()
        if show_progress:
            sys.stderr.write("\n")
    return 0


def _should_show_progress(args: argparse.Namespace) -> bool:
    show_progress = bool(getattr(args, "progress", False))
    if getattr(args, "no_progress", False):
        show_progress = False
    if not show_progress:
        show_progress = bool(sys.stderr.isatty())
    return show_progress


def _chunked_range(start: int, end: int, size: int) -> Iterable[Sequence[int]]:
    heights = list(range(start, end + 1))
    for off in range(0, len(heights), size):
        yield heights[off : off + size]


def _fetch_raw_blocks(rpc: Any, heights: Sequence[int], show_progress: bool) -> List[dict]:
    if show_progress:
        sys.stderr.write(f"\rFetching batch of {len(heights)} blocks... ")
        sys.stderr.flush()
    hashes = rpc.batch_call([("getblockhash", [h]) for h in heights])
    raw_blocks = rpc.batch_call([("getblock", [bh, 3]) for bh in hashes])
    return list(raw_blocks)


def _normalize_raw_blocks(
    raw_blocks: Sequence[dict], *, normalize_block: Any, normalize_tx: Any
) -> Tuple[List[dict], List[dict], List[dict], List[dict]]:
    network = "liquidv1"
    block_rows: List[dict] = []
    tx_rows: List[dict] = []
    txin_rows: List[dict] = []
    txout_rows: List[dict] = []
    for raw_block in raw_blocks:
        block_row = normalize_block(raw_block, network=network)
        block_rows.append(block_row)
        for tx_index, raw_tx in enumerate(raw_block.get("tx", []) or []):
            if not isinstance(raw_tx, dict):
                continue
            tx_row, txins, txouts = normalize_tx(raw_tx, block_row, tx_index_in_block=tx_index)
            tx_rows.append(tx_row)
            txin_rows.extend(txins)
            txout_rows.extend(txouts)
    return block_rows, tx_rows, txin_rows, txout_rows


def _render_progress(
    raw_blocks: Sequence[dict],
    done: int,
    total: int,
    started: float,
    last_render: float,
    show_progress: bool,
) -> Tuple[int, float]:
    for raw_block in raw_blocks:
        done += 1
        if not show_progress:
            continue
        now = time.monotonic()
        if done != total and (now - last_render) < 0.25:
            continue
        elapsed = max(0.001, now - started)
        rate = done / elapsed
        eta = (total - done) / rate if rate > 0 else float("inf")
        height = raw_block.get("height")
        bar = render_bar(done, total, width=30)
        sys.stderr.write(
            f"\r[{bar}] {done}/{total} ({(done / total) * 100:5.1f}%) "
            f"height={height} {rate:6.1f} blk/s eta={fmt_eta(eta)}"
        )
        sys.stderr.flush()
        last_render = now
    return done, last_render
