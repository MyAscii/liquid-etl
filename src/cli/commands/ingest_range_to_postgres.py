from __future__ import annotations

import argparse
import sys
import time
import queue
import threading
from typing import Any, Iterable, List, Sequence, Tuple

from ..progress import fmt_eta, render_bar


def ingest_range_to_postgres(args: argparse.Namespace) -> int:
    from ...rpc import LiquidRpc
    from ...utils.normalizer import normalize_block, normalize_tx
    from ...utils.postgres_writer import PostgresWriter

    fast_rpc_decode = bool(getattr(args, "fast_rpc_decode", False))
    rpc = LiquidRpc(args.provider_uri, datadir=args.datadir, use_decimal=not fast_rpc_decode)
    conflict_strategy = str(getattr(args, "conflict_strategy", "update"))
    fast_local = bool(getattr(args, "fast_local", False))
    if fast_local and conflict_strategy == "update":
        conflict_strategy = "ignore"
    writer = PostgresWriter(args.dsn, conflict_strategy=conflict_strategy, fast_local=fast_local)
    show_progress = _should_show_progress(args)
    start_block = max(0, int(getattr(args, "start_block", 1)))
    end_block = getattr(args, "end_block", None)
    if end_block is None:
        end_block = int(rpc.getblockcount())
    end_block = max(start_block, int(end_block))

    total = end_block - start_block + 1
    rpc_batch_size = max(1, int(getattr(args, "rpc_batch_size", 200)))
    chunk_size = max(1, int(getattr(args, "chunk_size", 500)))
    prefetch = max(0, int(getattr(args, "prefetch", 0)))
    if fast_local and prefetch == 0:
        prefetch = 2

    try:
        started = time.monotonic()
        last_render = started
        done = 0
        chunks = _chunked_range(start_block, end_block, chunk_size)
        for raw_blocks in _iter_raw_block_batches(
            rpc,
            chunks,
            rpc_batch_size=rpc_batch_size,
            show_progress=show_progress,
            prefetch=prefetch,
        ):
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
    if size <= 0:
        raise ValueError("size must be positive")
    current = start
    while current <= end:
        chunk_end = min(end, current + size - 1)
        yield list(range(current, chunk_end + 1))
        current = chunk_end + 1


def _fetch_raw_blocks(rpc: Any, heights: Sequence[int], show_progress: bool) -> List[dict]:
    if show_progress:
        sys.stderr.write(f"\rFetching batch of {len(heights)} blocks... ")
        sys.stderr.flush()
    hashes = rpc.batch_call([("getblockhash", [h]) for h in heights])
    raw_blocks = rpc.batch_call([("getblock", [bh, 3]) for bh in hashes])
    return list(raw_blocks)


def _fetch_raw_blocks_chunked(
    rpc: Any, heights: Sequence[int], *, rpc_batch_size: int, show_progress: bool
) -> List[dict]:
    raw_blocks: List[dict] = []
    for sub in _chunked_seq(heights, rpc_batch_size):
        raw_blocks.extend(_fetch_raw_blocks(rpc, sub, show_progress=show_progress))
    return raw_blocks


def _chunked_seq(items: Sequence[int], size: int) -> Iterable[Sequence[int]]:
    if size <= 0:
        raise ValueError("size must be positive")
    for off in range(0, len(items), size):
        yield items[off : off + size]


def _iter_raw_block_batches(
    rpc: Any,
    chunks: Iterable[Sequence[int]],
    *,
    rpc_batch_size: int,
    show_progress: bool,
    prefetch: int,
) -> Iterable[List[dict]]:
    if prefetch <= 0:
        for chunk in chunks:
            yield _fetch_raw_blocks_chunked(
                rpc, chunk, rpc_batch_size=rpc_batch_size, show_progress=show_progress
            )
        return

    q: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=prefetch)
    stop = threading.Event()

    def producer() -> None:
        try:
            for chunk in chunks:
                if stop.is_set():
                    break
                raw_blocks = _fetch_raw_blocks_chunked(
                    rpc, chunk, rpc_batch_size=rpc_batch_size, show_progress=False
                )
                q.put(("ok", raw_blocks))
        except BaseException as e:
            q.put(("error", e))
        finally:
            q.put(("done", None))

    t = threading.Thread(target=producer, daemon=True)
    t.start()
    while True:
        kind, payload = q.get()
        if kind == "ok":
            yield payload
        elif kind == "error":
            stop.set()
            raise payload
        elif kind == "done":
            break


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
