from __future__ import annotations

import argparse
import sys
import time
from typing import Any, Iterable, List, Optional, Sequence, Tuple

from ..progress import fmt_eta, render_bar


def repair_postgres(args: argparse.Namespace) -> int:
    from ...utils.normalizer import normalize_block, normalize_tx
    from ...utils.postgres_writer import PostgresWriter

    writer = PostgresWriter(args.dsn)
    show_progress = _should_show_progress(args)
    dedupe = not bool(getattr(args, "no_dedupe", False))
    fill_gaps = not bool(getattr(args, "no_fill_gaps", False))
    backfill_present = bool(getattr(args, "backfill_present", False))

    db_lo, db_hi = _db_height_bounds(writer)
    if db_lo is None or db_hi is None:
        print("No blocks in DB to repair", file=sys.stderr)
        writer.close()
        return 0

    start_h, end_h = _bounds(args, db_lo, db_hi)

    try:
        if dedupe:
            _dedupe_duplicate_heights(writer, start_h, end_h, dry_run=bool(args.dry_run))
        if fill_gaps:
            gaps = _compute_gaps(writer, start_h, end_h, backfill_present=backfill_present)
            if not gaps:
                print("No missing block gaps found", file=sys.stderr)
                return 0
            if bool(args.dry_run):
                _print_gaps(gaps)
                return 0
            try:
                rpc = _require_rpc(args)
            except RuntimeError as e:
                print(str(e), file=sys.stderr)
                print(
                    "Tip: start your node, or run with --dry-run / --no-fill-gaps", file=sys.stderr
                )
                return 1
            _ingest_gaps(
                writer=writer,
                rpc=rpc,
                gaps=gaps,
                rpc_batch_size=max(1, int(getattr(args, "rpc_batch_size", 25))),
                show_progress=show_progress,
                backfill_present=backfill_present,
                normalize_block=normalize_block,
                normalize_tx=normalize_tx,
            )
        return 0
    finally:
        writer.close()


def _should_show_progress(args: argparse.Namespace) -> bool:
    show_progress = bool(getattr(args, "progress", False))
    if getattr(args, "no_progress", False):
        show_progress = False
    if not show_progress:
        show_progress = bool(sys.stderr.isatty())
    return show_progress


def _db_height_bounds(writer: Any) -> Tuple[Optional[int], Optional[int]]:
    with writer.conn.cursor() as cur:
        cur.execute("SELECT MIN(height), MAX(height) FROM blocks WHERE height IS NOT NULL")
        row = cur.fetchone() or (None, None)
        lo, hi = row[0], row[1]
        return (int(lo) if lo is not None else None, int(hi) if hi is not None else None)


def _bounds(args: argparse.Namespace, db_lo: int, db_hi: int) -> Tuple[int, int]:
    start_h = int(args.start_block) if args.start_block is not None else db_lo
    end_h = int(args.end_block) if args.end_block is not None else db_hi
    if end_h < start_h:
        start_h, end_h = end_h, start_h
    return start_h, end_h


def _dedupe_duplicate_heights(writer: Any, start_h: int, end_h: int, dry_run: bool) -> None:
    dup_heights = _find_duplicate_heights(writer, start_h, end_h)
    if dup_heights:
        print(f"Found {len(dup_heights)} duplicate heights in blocks", file=sys.stderr)
    else:
        print("No duplicate heights found in blocks", file=sys.stderr)
    for h, _count in dup_heights:
        keep_hash, delete_hashes = _pick_keep_and_deletes(writer, h)
        if not delete_hashes:
            continue
        if dry_run:
            print(
                f"[dry-run] height={h} keep={keep_hash} delete={len(delete_hashes)} blocks",
                file=sys.stderr,
            )
            continue
        _delete_blocks(writer, h, keep_hash, delete_hashes)


def _find_duplicate_heights(writer: Any, start_h: int, end_h: int) -> List[Tuple[int, int]]:
    with writer.conn.cursor() as cur:
        cur.execute(
            """
            SELECT height, COUNT(*) AS c
            FROM blocks
            WHERE height IS NOT NULL AND height BETWEEN %s AND %s
            GROUP BY height
            HAVING COUNT(*) > 1
            ORDER BY height
            """,
            (start_h, end_h),
        )
        return [(int(r[0]), int(r[1])) for r in (cur.fetchall() or [])]


def _pick_keep_and_deletes(writer: Any, height: int) -> Tuple[str, List[str]]:
    with writer.conn.cursor() as cur:
        cur.execute(
            """
            SELECT b.hash
            FROM blocks b
            LEFT JOIN transactions t ON t.block_hash = b.hash
            WHERE b.height=%s
            GROUP BY b.hash
            ORDER BY COUNT(t.txid) DESC, MAX(b.time) DESC NULLS LAST, b.hash DESC
            LIMIT 1
            """,
            (height,),
        )
        keep_hash = cur.fetchone()[0]
        cur.execute("SELECT hash FROM blocks WHERE height=%s AND hash <> %s", (height, keep_hash))
        delete_hashes = [r[0] for r in (cur.fetchall() or [])]
        return keep_hash, delete_hashes


def _delete_blocks(writer: Any, height: int, keep_hash: str, delete_hashes: Sequence[str]) -> None:
    with writer.conn.transaction():
        with writer.conn.cursor() as cur:
            cur.execute(
                "SELECT txid FROM transactions WHERE block_hash = ANY(%s)", (list(delete_hashes),)
            )
            txids = [r[0] for r in (cur.fetchall() or [])]
            if txids:
                cur.execute("DELETE FROM txins WHERE txid = ANY(%s)", (txids,))
                cur.execute("DELETE FROM txouts WHERE txid = ANY(%s)", (txids,))
                cur.execute("DELETE FROM transactions WHERE txid = ANY(%s)", (txids,))
            cur.execute("DELETE FROM blocks WHERE hash = ANY(%s)", (list(delete_hashes),))
    print(
        f"Deduped height={height}: kept={keep_hash}, removed_blocks={len(delete_hashes)}",
        file=sys.stderr,
    )


def _compute_gaps(
    writer: Any, start_h: int, end_h: int, backfill_present: bool
) -> List[Tuple[int, int]]:
    if backfill_present:
        return [(start_h, end_h)]

    present_min, present_max, gaps = _query_gaps(writer, start_h, end_h)
    if present_min is not None and start_h < present_min:
        gaps = [(start_h, present_min - 1), *gaps]
    if present_max is not None and present_max < end_h:
        gaps = [*gaps, (present_max + 1, end_h)]
    return _merge_gaps(sorted(gaps, key=lambda x: x[0]))


def _query_gaps(
    writer: Any, start_h: int, end_h: int
) -> Tuple[Optional[int], Optional[int], List[Tuple[int, int]]]:
    with writer.conn.cursor() as cur:
        cur.execute(
            "SELECT MIN(height), MAX(height) FROM blocks WHERE height IS NOT NULL AND height BETWEEN %s AND %s",
            (start_h, end_h),
        )
        row = cur.fetchone() or (None, None)
        present_min = int(row[0]) if row[0] is not None else None
        present_max = int(row[1]) if row[1] is not None else None
        cur.execute(
            """
            WITH heights AS (
                SELECT DISTINCT height
                FROM blocks
                WHERE height IS NOT NULL AND height BETWEEN %s AND %s
            ),
            ordered AS (
                SELECT height, LEAD(height) OVER (ORDER BY height) AS next_height
                FROM heights
            )
            SELECT height + 1 AS start_missing, next_height - 1 AS end_missing
            FROM ordered
            WHERE next_height IS NOT NULL AND next_height > height + 1
            ORDER BY start_missing
            """,
            (start_h, end_h),
        )
        gaps = [(int(r[0]), int(r[1])) for r in (cur.fetchall() or [])]
    return present_min, present_max, gaps


def _merge_gaps(gaps: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    merged: List[List[int]] = []
    for a, b in gaps:
        if not merged:
            merged.append([a, b])
            continue
        prev = merged[-1]
        if a <= prev[1] + 1:
            prev[1] = max(prev[1], b)
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged]


def _print_gaps(gaps: Sequence[Tuple[int, int]]) -> None:
    for a, b in gaps[:50]:
        if a == b:
            print(f"[dry-run] missing height={a}", file=sys.stderr)
        else:
            print(f"[dry-run] missing heights {a}..{b}", file=sys.stderr)
    if len(gaps) > 50:
        print(f"[dry-run] ... {len(gaps) - 50} more gaps", file=sys.stderr)


def _require_rpc(args: argparse.Namespace):
    from ...rpc import LiquidRpc

    provider_uri = getattr(args, "provider_uri", None)
    if not provider_uri:
        raise RuntimeError(
            "Error: --provider-uri is required to fill gaps (or use --dry-run / --no-fill-gaps)"
        )
    try:
        return LiquidRpc(provider_uri, datadir=getattr(args, "datadir", None))
    except Exception as e:
        raise RuntimeError(f"Error: cannot connect to provider ({provider_uri}): {e}") from e


def _ingest_gaps(
    writer: Any,
    rpc: Any,
    gaps: Sequence[Tuple[int, int]],
    rpc_batch_size: int,
    show_progress: bool,
    backfill_present: bool,
    normalize_block: Any,
    normalize_tx: Any,
) -> None:
    missing_blocks = sum((b - a + 1) for a, b in gaps)
    label = "blocks to (re)ingest" if backfill_present else "missing blocks"
    print(f"Found {missing_blocks} {label} in {len(gaps)} gaps", file=sys.stderr)

    started = time.monotonic()
    last_render = started
    for a, b in gaps:
        heights = list(range(a, b + 1))
        total = len(heights)
        done = 0
        for chunk in _chunked(heights, rpc_batch_size):
            raw_blocks = _fetch_raw_blocks(rpc, chunk, show_progress)
            block_rows, tx_rows, txin_rows, txout_rows = _normalize_raw_blocks(
                raw_blocks, normalize_block=normalize_block, normalize_tx=normalize_tx
            )
            writer.write_chunk(block_rows, tx_rows, txin_rows, txout_rows)
            done += len(raw_blocks)
            last_render = _render_fill_progress(done, total, started, last_render, show_progress)
        if show_progress:
            sys.stderr.write("\n")


def _chunked(items: Sequence[int], size: int) -> Iterable[Sequence[int]]:
    for off in range(0, len(items), size):
        yield items[off : off + size]


def _fetch_raw_blocks(rpc: Any, heights: Sequence[int], show_progress: bool) -> List[dict]:
    if show_progress:
        sys.stderr.write(f"\rFetching batch of {len(heights)} blocks... ")
        sys.stderr.flush()
    hashes = rpc.batch_call([("getblockhash", [h]) for h in heights])
    return list(rpc.batch_call([("getblock", [bh, 3]) for bh in hashes]))


def _normalize_raw_blocks(
    raw_blocks: Sequence[dict], *, normalize_block: Any, normalize_tx: Any
) -> Tuple[List[dict], List[dict], List[dict], List[dict]]:
    block_rows: List[dict] = []
    tx_rows: List[dict] = []
    txin_rows: List[dict] = []
    txout_rows: List[dict] = []
    for raw_block in raw_blocks:
        block_row = normalize_block(raw_block, network="liquidv1")
        block_rows.append(block_row)
        for tx_index, raw_tx in enumerate(raw_block.get("tx", []) or []):
            if not isinstance(raw_tx, dict):
                continue
            tx_row, txins, txouts = normalize_tx(raw_tx, block_row, tx_index_in_block=tx_index)
            tx_rows.append(tx_row)
            txin_rows.extend(txins)
            txout_rows.extend(txouts)
    return block_rows, tx_rows, txin_rows, txout_rows


def _render_fill_progress(
    done: int, total: int, started: float, last_render: float, show_progress: bool
) -> float:
    if not show_progress:
        return last_render
    now = time.monotonic()
    if done != total and (now - last_render) < 0.25:
        return last_render
    elapsed = max(0.001, now - started)
    rate = done / elapsed
    eta = (total - done) / rate if rate > 0 else float("inf")
    bar = render_bar(done, total, width=30)
    sys.stderr.write(
        f"\r[{bar}] filled {done}/{total} ({(done / total) * 100:5.1f}%) {rate:6.1f} blk/s eta={fmt_eta(eta)}"
    )
    sys.stderr.flush()
    return now
