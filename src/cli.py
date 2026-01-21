import argparse
import sys
import time


def _add_common_provider(parser: argparse.ArgumentParser):
    parser.add_argument(
        "-p", "--provider-uri", required=True,
        help="JSON-RPC URI, e.g. http://user:pass@localhost:7041"
    )
    parser.add_argument(
        "--datadir",
        help="Elements/Liquid datadir (optional). Used to read .cookie or elements.conf when provider-uri has no creds.",
    )


def _cmd_export_blocks_and_transactions(args: argparse.Namespace) -> int:
    from .jobs.export_blocks_job import ExportBlocksJob
    from .service import LiquidService
    from .rpc import LiquidRpc

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
    from .jobs.enrich_transactions_job import EnrichTransactionsJob
    from .rpc import LiquidRpc
    from .service import LiquidService

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
    from .service import LiquidService
    from .rpc import LiquidRpc

    rpc = LiquidRpc(args.provider_uri, datadir=args.datadir)
    service = LiquidService(rpc)
    start, end = service.get_block_range_for_date(args.date, args.start_hour, args.end_hour)
    print(f"{start} {end}")
    return 0


def _cmd_export_all(args: argparse.Namespace) -> int:
    from .jobs.export_all_job import export_all
    from .rpc import LiquidRpc
    from .service import LiquidService

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
    from .utils.filters import filter_items
    filter_items(
        input_path=args.input,
        output_path=args.output,
        predicate=args.predicate,
        input_format=args.format,
    )
    return 0


def _cmd_stream(args: argparse.Namespace) -> int:
    from .streaming.streamer_adapter import LiquidStreamerAdapter
    from .rpc import LiquidRpc
    from .service import LiquidService

    start_block = args.start_block
    if start_block is None:
        if args.output.startswith("postgres://") or args.output.startswith("postgresql://"):
            from .utils.postgres_writer import PostgresWriter
            try:
                tmp_writer = PostgresWriter(args.output)
                max_height = tmp_writer.get_max_block_height()
                tmp_writer.close()
                if max_height is not None:
                    start_block = max_height + 1
                    print(f"Resuming from block {start_block} (DB max height: {max_height})", file=sys.stderr)
                else:
                    start_block = 0
                    print("Database empty, starting from block 0", file=sys.stderr)
            except Exception as e:
                print(f"Error checking DB state: {e}", file=sys.stderr)
                return 1
        else:
            print("Error: --start-block is required unless output is a Postgres DB", file=sys.stderr)
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
    from .utils.sqlite_writer import SQLiteWriter
    import json

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
    from .utils.postgres_writer import PostgresWriter
    import json

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
    from .rpc import LiquidRpc
    from .utils.postgres_writer import PostgresWriter
    from .utils.normalizer import normalize_block, normalize_tx

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
    network = rpc.getblockchaininfo().get("chain") or "liquidv1"
    writer = PostgresWriter(args.dsn, network=network)
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
                    tx_row, txins, txouts = normalize_tx(raw_tx, block_row, tx_index_in_block=tx_index)
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="liquidetl", description="Liquid Network ETL and streaming toolkit")
    sub = parser.add_subparsers(dest="command", required=True)

    p_export = sub.add_parser("export_blocks_and_transactions", help="Export blocks and transactions for a range")
    _add_common_provider(p_export)
    p_export.add_argument("-s", "-start", "--start-block", type=int, required=True)
    p_export.add_argument("-e", "-end", "--end-block", type=int, required=True)
    p_export.add_argument("--blocks-output", required=True)
    p_export.add_argument("--transactions-output", required=True)
    p_export.set_defaults(func=_cmd_export_blocks_and_transactions)

    p_enrich = sub.add_parser("enrich_transactions", help="Enrich transactions with input details (requires txindex=1)")
    _add_common_provider(p_enrich)
    p_enrich.add_argument("--transactions-input", required=True)
    p_enrich.add_argument("--transactions-output", required=True)
    p_enrich.set_defaults(func=_cmd_enrich_transactions)

    p_range = sub.add_parser("get_block_range_for_date", help="Return start and end block for a UTC date")
    _add_common_provider(p_range)
    p_range.add_argument("--date", required=True, help="YYYY-MM-DD")
    p_range.add_argument("--start-hour", type=int, default=0)
    p_range.add_argument("--end-hour", type=int, default=24)
    p_range.set_defaults(func=_cmd_get_block_range_for_date)

    p_all = sub.add_parser("export_all", help="Partition date or block ranges into batches and export")
    _add_common_provider(p_all)
    group = p_all.add_mutually_exclusive_group(required=True)
    group.add_argument("--date", help="YYYY-MM-DD for date partitioning")
    group.add_argument("--start-block", type=int)
    p_all.add_argument("--end-block", type=int)
    p_all.add_argument("--batch-size", type=int, default=1000)
    p_all.add_argument("--output", required=True)
    p_all.add_argument("--enrich", action="store_true")
    p_all.set_defaults(func=_cmd_export_all)

    p_filter = sub.add_parser("filter_items", help="Filter NDJSON or CSV outputs using a Python predicate")
    p_filter.add_argument("--input", required=True)
    p_filter.add_argument("--output", required=True)
    p_filter.add_argument("--predicate", required=True, help="Python expression like 'lambda x: x[\"block_timestamp\"][:10]==\"2019-03-01\"'")
    p_filter.add_argument("--format", choices=("ndjson", "csv"), default="ndjson")
    p_filter.set_defaults(func=_cmd_filter_items)

    p_stream = sub.add_parser("stream", help="Continuously stream blocks and transactions")
    _add_common_provider(p_stream)
    p_stream.add_argument("--start-block", type=int, required=False, help="Start block (optional for Postgres; resumes from DB max+1)")
    p_stream.add_argument("--lag", type=int, default=0)
    p_stream.add_argument(
        "--output",
        default="console",
        help="'console', 'sqlite:///path/to.db', 'postgres://user:pass@host:5432/dbname' or projects/.../topics/crypto_liquid",
    )
    p_stream.add_argument("--batch-size", type=int, default=100)
    p_stream.add_argument("--poll-interval", type=float, default=2.0)
    p_stream.add_argument("--enrich", action="store_true")
    p_stream.set_defaults(func=_cmd_stream)

    p_load = sub.add_parser("load_ndjson_to_sqlite", help="Load NDJSON exports into a local SQLite DB")
    p_load.add_argument("--db", required=True, help="Path to .db file")
    p_load.add_argument("--blocks-input", help="Path to blocks NDJSON")
    p_load.add_argument("--transactions-input", help="Path to transactions NDJSON")
    p_load.set_defaults(func=_cmd_load_ndjson_to_sqlite)

    p_load_pg = sub.add_parser("load_ndjson_to_postgres", help="Load NDJSON exports into Postgres")
    p_load_pg.add_argument("--dsn", required=True, help="Postgres DSN, e.g. postgresql://user:pass@localhost:5432/liquidetl")
    p_load_pg.add_argument("--blocks-input", help="Path to blocks NDJSON")
    p_load_pg.add_argument("--transactions-input", help="Path to transactions NDJSON")
    p_load_pg.set_defaults(func=_cmd_load_ndjson_to_postgres)

    p_ingest_pg = sub.add_parser("ingest_range_to_postgres", help="Directly ingest a block range into Postgres")
    _add_common_provider(p_ingest_pg)
    p_ingest_pg.add_argument("-s", "-start", "--start-block", type=int, required=True)
    p_ingest_pg.add_argument("-e", "-end", "--end-block", type=int, required=True)
    p_ingest_pg.add_argument("--dsn", required=True, help="Postgres DSN, e.g. postgresql://user:pass@localhost:5432/liquidetl")
    p_ingest_pg.add_argument("--enrich", action="store_true")
    p_ingest_pg.add_argument("--rpc-batch-size", type=int, default=25, help="Batch size for RPC calls (reduces round trips)")
    pbar = p_ingest_pg.add_mutually_exclusive_group(required=False)
    pbar.add_argument("--progress", action="store_true", help="Force progress output")
    pbar.add_argument("--no-progress", action="store_true", help="Disable progress output")
    p_ingest_pg.set_defaults(func=_cmd_ingest_range_to_postgres)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
