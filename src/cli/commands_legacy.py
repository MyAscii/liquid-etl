from __future__ import annotations

import argparse
import sys
import time


def _cmd_export_blocks_and_transactions(args: argparse.Namespace) -> int:
    from ..jobs.export_blocks_job import ExportBlocksJob
    from ..rpc import LiquidRpc
    from ..service import LiquidService

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


def _cmd_enrich_transactions(args: argparse.Namespace) -> int:
    from ..jobs.enrich_transactions_job import EnrichTransactionsJob
    from ..rpc import LiquidRpc
    from ..service import LiquidService

    rpc = LiquidRpc(args.provider_uri, datadir=args.datadir)
    service = LiquidService(rpc)
    job = EnrichTransactionsJob(
        service=service,
        transactions_input=args.transactions_input,
        transactions_output=args.transactions_output,
    )
    job.run()
    return 0


def _cmd_get_block_range_for_date(args: argparse.Namespace) -> int:
    from ..rpc import LiquidRpc
    from ..service import LiquidService

    rpc = LiquidRpc(args.provider_uri, datadir=args.datadir)
    service = LiquidService(rpc)
    start, end = service.get_block_range_for_date(args.date, args.start_hour, args.end_hour)
    print(f"{start} {end}")
    return 0


def _cmd_export_all(args: argparse.Namespace) -> int:
    from ..jobs.export_all_job import export_all
    from ..rpc import LiquidRpc
    from ..service import LiquidService

    rpc = LiquidRpc(args.provider_uri, datadir=args.datadir)
    service = LiquidService(rpc)
    export_all(
        service=service,
        output_dir=args.output,
        date=args.date,
        start_block=args.start_block,
        end_block=args.end_block,
        batch_size=args.batch_size,
        enrich=args.enrich,
    )
    return 0


def _cmd_filter_items(args: argparse.Namespace) -> int:
    from ..utils.filters import filter_items

    filter_items(
        input_path=args.input,
        output_path=args.output,
        predicate=args.predicate,
        input_format=args.format,
    )
    return 0


def _cmd_stream(args: argparse.Namespace) -> int:
    from ..rpc import LiquidRpc
    from ..service import LiquidService
    from ..streaming.streamer_adapter import LiquidStreamerAdapter

    start_block = args.start_block
    if start_block is None:
        if args.output.startswith("postgres://") or args.output.startswith("postgresql://"):
            from ..utils.postgres_writer import PostgresWriter

            try:
                tmp_writer = PostgresWriter(args.output)
                max_height = tmp_writer.get_max_block_height()
                tmp_writer.close()
                if max_height is not None:
                    start_block = max_height + 1
                    print(
                        f"Resuming from block {start_block} (DB max height: {max_height})",
                        file=sys.stderr,
                    )
                else:
                    start_block = 0
                    print("Database empty, starting from block 0", file=sys.stderr)
            except Exception as e:
                print(f"Error checking DB state: {e}", file=sys.stderr)
                return 1
        else:
            print(
                "Error: --start-block is required unless output is a Postgres DB", file=sys.stderr
            )
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


def _cmd_load_ndjson_to_sqlite(args: argparse.Namespace) -> int:
    import json

    from ..utils.sqlite_writer import SQLiteWriter

    writer = SQLiteWriter(args.db)
    if args.blocks_input:
        with open(args.blocks_input, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                writer.write_block(item)
    if args.transactions_input:
        with open(args.transactions_input, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                writer.write_transaction(item)
    writer.close()
    return 0


def _cmd_load_ndjson_to_postgres(args: argparse.Namespace) -> int:
    import json

    from ..utils.postgres_writer import PostgresWriter

    writer = PostgresWriter(args.dsn)
    if args.blocks_input:
        with open(args.blocks_input, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                writer.write_block(item)
    if args.transactions_input:
        with open(args.transactions_input, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                writer.write_transaction(item)
    writer.close()
    return 0


def _cmd_ingest_range_to_postgres(args: argparse.Namespace) -> int:
    from ..rpc import LiquidRpc
    from ..utils.normalizer import normalize_block, normalize_tx
    from ..utils.postgres_writer import PostgresWriter

    def _fmt_eta(seconds: float) -> str:
        if seconds != seconds or seconds == float("inf") or seconds < 0:
            return "?:??"
        s = int(seconds)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h:d}:{m:02d}:{s:02d}"
        return f"{m:d}:{s:02d}"

    rpc = LiquidRpc(args.provider_uri, datadir=args.datadir)
    network = "liquidv1"
    writer = PostgresWriter(args.dsn)
    total = args.end_block - args.start_block + 1
    show_progress = bool(getattr(args, "progress", False))
    if getattr(args, "no_progress", False):
        show_progress = False
    if not show_progress:
        show_progress = bool(sys.stderr.isatty())

    try:
        started = time.monotonic()
        last_render = started
        rpc_batch_size = max(1, int(getattr(args, "rpc_batch_size", 25)))

        heights = list(range(args.start_block, args.end_block + 1))
        done = 0
        for off in range(0, len(heights), rpc_batch_size):
            chunk = heights[off : off + rpc_batch_size]
            if show_progress:
                sys.stderr.write(f"\rFetching batch of {len(chunk)} blocks... ")
                sys.stderr.flush()
            hashes = rpc.batch_call([("getblockhash", [h]) for h in chunk])
            raw_blocks = rpc.batch_call([("getblock", [bh, 3]) for bh in hashes])

            block_rows = []
            all_tx_rows = []
            all_txin_rows = []
            all_txout_rows = []

            for raw_block in raw_blocks:
                block_row = normalize_block(raw_block, network=network)
                block_rows.append(block_row)
                for tx_index, raw_tx in enumerate(raw_block.get("tx", []) or []):
                    if not isinstance(raw_tx, dict):
                        continue
                    tx_row, txins, txouts = normalize_tx(
                        raw_tx, block_row, tx_index_in_block=tx_index
                    )
                    all_tx_rows.append(tx_row)
                    all_txin_rows.extend(txins)
                    all_txout_rows.extend(txouts)

            writer.write_chunk(block_rows, all_tx_rows, all_txin_rows, all_txout_rows)

            for raw_block in raw_blocks:
                done += 1
                if show_progress:
                    now = time.monotonic()
                    if done == total or (now - last_render) >= 0.25:
                        frac = done / total if total else 1.0
                        width = 30
                        filled = int(frac * width)
                        if filled >= width:
                            bar = "=" * width
                        else:
                            bar = ("=" * filled) + ">" + ("." * (width - filled - 1))
                        elapsed = max(0.001, now - started)
                        rate = done / elapsed
                        eta = (total - done) / rate if rate > 0 else float("inf")
                        height = raw_block.get("height")
                        msg = (
                            f"\r[{bar}] {done}/{total} ({frac * 100:5.1f}%) "
                            f"height={height} {rate:6.1f} blk/s eta={_fmt_eta(eta)}"
                        )
                        sys.stderr.write(msg)
                        sys.stderr.flush()
                        last_render = now
    finally:
        writer.close()
        if show_progress:
            sys.stderr.write("\n")
    return 0


def _cmd_repair_postgres(args: argparse.Namespace) -> int:
    from ..utils.normalizer import normalize_block, normalize_tx
    from ..utils.postgres_writer import PostgresWriter

    def _fmt_eta(seconds: float) -> str:
        if seconds != seconds or seconds == float("inf") or seconds < 0:
            return "?:??"
        s = int(seconds)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h:d}:{m:02d}:{s:02d}"
        return f"{m:d}:{s:02d}"

    dedupe = not bool(getattr(args, "no_dedupe", False))
    fill_gaps = not bool(getattr(args, "no_fill_gaps", False))
    backfill_present = bool(getattr(args, "backfill_present", False))

    rpc = None

    writer = PostgresWriter(args.dsn)
    show_progress = bool(getattr(args, "progress", False))
    if getattr(args, "no_progress", False):
        show_progress = False
    if not show_progress:
        show_progress = bool(sys.stderr.isatty())

    def _db_height_bounds():
        with writer.conn.cursor() as cur:
            cur.execute(
                "SELECT MIN(height), MAX(height) FROM blocks WHERE height IS NOT NULL",
            )
            row = cur.fetchone()
            if not row:
                return None, None
            lo, hi = row[0], row[1]
            return (int(lo) if lo is not None else None, int(hi) if hi is not None else None)

    db_lo, db_hi = _db_height_bounds()
    if db_lo is None or db_hi is None:
        print("No blocks in DB to repair", file=sys.stderr)
        writer.close()
        return 0

    start_h = int(args.start_block) if args.start_block is not None else db_lo
    end_h = int(args.end_block) if args.end_block is not None else db_hi
    if end_h < start_h:
        start_h, end_h = end_h, start_h

    try:
        if dedupe:
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
                dup_heights = [(int(r[0]), int(r[1])) for r in (cur.fetchall() or [])]

            if dup_heights:
                print(f"Found {len(dup_heights)} duplicate heights in blocks", file=sys.stderr)
            else:
                print("No duplicate heights found in blocks", file=sys.stderr)

            for h, _ in dup_heights:
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
                        (h,),
                    )
                    keep_hash = cur.fetchone()[0]
                    cur.execute(
                        "SELECT hash FROM blocks WHERE height=%s AND hash <> %s",
                        (h, keep_hash),
                    )
                    delete_hashes = [r[0] for r in (cur.fetchall() or [])]

                if not delete_hashes:
                    continue

                if args.dry_run:
                    print(
                        f"[dry-run] height={h} keep={keep_hash} delete={len(delete_hashes)} blocks",
                        file=sys.stderr,
                    )
                    continue

                with writer.conn.transaction():
                    with writer.conn.cursor() as cur:
                        cur.execute(
                            "SELECT txid FROM transactions WHERE block_hash = ANY(%s)",
                            (delete_hashes,),
                        )
                        txids = [r[0] for r in (cur.fetchall() or [])]
                        if txids:
                            cur.execute("DELETE FROM txins WHERE txid = ANY(%s)", (txids,))
                            cur.execute("DELETE FROM txouts WHERE txid = ANY(%s)", (txids,))
                            cur.execute("DELETE FROM transactions WHERE txid = ANY(%s)", (txids,))
                        cur.execute(
                            "DELETE FROM blocks WHERE hash = ANY(%s)",
                            (delete_hashes,),
                        )
                print(
                    f"Deduped height={h}: kept={keep_hash}, removed_blocks={len(delete_hashes)}",
                    file=sys.stderr,
                )

        if fill_gaps:
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

            if present_min is not None and start_h < present_min:
                gaps = [(start_h, present_min - 1), *gaps]
            if present_max is not None and present_max < end_h:
                gaps = [*gaps, (present_max + 1, end_h)]

            gaps.sort(key=lambda x: x[0])
            merged = []
            for a, b in gaps:
                if not merged:
                    merged.append([a, b])
                    continue
                prev = merged[-1]
                if a <= prev[1] + 1:
                    prev[1] = max(prev[1], b)
                else:
                    merged.append([a, b])
            gaps = [(a, b) for a, b in merged]

            if backfill_present:
                gaps = [(start_h, end_h)]

            if gaps:
                missing_blocks = sum((b - a + 1) for a, b in gaps)
                label = "blocks to (re)ingest" if backfill_present else "missing blocks"
                print(f"Found {missing_blocks} {label} in {len(gaps)} gaps", file=sys.stderr)
            else:
                print("No missing block gaps found", file=sys.stderr)

            if args.dry_run:
                for a, b in gaps[:50]:
                    if a == b:
                        print(f"[dry-run] missing height={a}", file=sys.stderr)
                    else:
                        print(f"[dry-run] missing heights {a}..{b}", file=sys.stderr)
                if len(gaps) > 50:
                    print(f"[dry-run] ... {len(gaps) - 50} more gaps", file=sys.stderr)
                return 0

            if rpc is None:
                from ..rpc import LiquidRpc

                provider_uri = getattr(args, "provider_uri", None)
                if not provider_uri:
                    print(
                        "Error: --provider-uri is required to fill gaps (or use --dry-run / --no-fill-gaps)",
                        file=sys.stderr,
                    )
                    return 1
                try:
                    rpc = LiquidRpc(provider_uri, datadir=getattr(args, "datadir", None))
                except Exception as e:
                    print(
                        f"Error: cannot connect to provider ({provider_uri}): {e}", file=sys.stderr
                    )
                    print(
                        "Tip: start your node, or run with --dry-run / --no-fill-gaps",
                        file=sys.stderr,
                    )
                    return 1

            started = time.monotonic()
            last_render = started
            rpc_batch_size = max(1, int(getattr(args, "rpc_batch_size", 25)))

            for a, b in gaps:
                heights = list(range(a, b + 1))
                total = len(heights)
                done = 0
                for off in range(0, len(heights), rpc_batch_size):
                    chunk = heights[off : off + rpc_batch_size]
                    if show_progress:
                        sys.stderr.write(f"\rFetching batch of {len(chunk)} blocks... ")
                        sys.stderr.flush()
                    hashes = rpc.batch_call([("getblockhash", [h]) for h in chunk])
                    raw_blocks = rpc.batch_call([("getblock", [bh, 3]) for bh in hashes])

                    block_rows = []
                    all_tx_rows = []
                    all_txin_rows = []
                    all_txout_rows = []

                    for raw_block in raw_blocks:
                        block_row = normalize_block(raw_block, network="liquidv1")
                        block_rows.append(block_row)
                        for tx_index, raw_tx in enumerate(raw_block.get("tx", []) or []):
                            if not isinstance(raw_tx, dict):
                                continue
                            tx_row, txins, txouts = normalize_tx(
                                raw_tx, block_row, tx_index_in_block=tx_index
                            )
                            all_tx_rows.append(tx_row)
                            all_txin_rows.extend(txins)
                            all_txout_rows.extend(txouts)

                    writer.write_chunk(block_rows, all_tx_rows, all_txin_rows, all_txout_rows)

                    done += len(raw_blocks)
                    if show_progress:
                        now = time.monotonic()
                        if done == total or (now - last_render) >= 0.25:
                            frac = done / total if total else 1.0
                            width = 30
                            filled = int(frac * width)
                            if filled >= width:
                                bar = "=" * width
                            else:
                                bar = ("=" * filled) + ">" + ("." * (width - filled - 1))
                            elapsed = max(0.001, now - started)
                            rate = done / elapsed
                            eta = (total - done) / rate if rate > 0 else float("inf")
                            msg = f"\r[{bar}] filled {done}/{total} ({frac * 100:5.1f}%) {rate:6.1f} blk/s eta={_fmt_eta(eta)}"
                            sys.stderr.write(msg)
                            sys.stderr.flush()
                            last_render = now
                if show_progress:
                    sys.stderr.write("\n")
            return 0
        return 0
    finally:
        writer.close()


def _cmd_audit_rpc_schema(args: argparse.Namespace) -> int:
    import json

    from ..rpc import LiquidRpc
    from ..utils.rpc_schema_audit import (
        audit_rpc_blocks,
        suggest_prunable_postgres_columns,
        to_postgres_drop_column_sql,
    )

    rpc = LiquidRpc(args.provider_uri, datadir=args.datadir)
    head = rpc.getblockcount()
    sample_size = max(1, int(args.sample_size))
    heights = []
    start = max(0, head - sample_size + 1)
    for h in range(start, head + 1):
        heights.append(h)

    hashes = rpc.batch_call([("getblockhash", [h]) for h in heights])
    blocks = rpc.batch_call([("getblock", [bh, 3]) for bh in hashes])
    audit = audit_rpc_blocks(blocks)
    prunable = suggest_prunable_postgres_columns(audit)

    out = audit.as_dict()
    out["head"] = head
    out["sampled_heights"] = heights
    out["prunable_postgres_columns_suggestion"] = prunable
    out["prunable_postgres_drop_sql"] = to_postgres_drop_column_sql(prunable)
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0
