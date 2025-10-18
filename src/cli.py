import argparse
import sys


def _add_common_provider(parser: argparse.ArgumentParser):
    parser.add_argument(
        "-p", "--provider-uri", required=True,
        help="JSON-RPC URI, e.g. http://user:pass@localhost:7041"
    )


def _cmd_export_blocks_and_transactions(args: argparse.Namespace) -> int:
    from .jobs.export_blocks_job import ExportBlocksJob
    from .service import LiquidService
    from .rpc import LiquidRpc

    rpc = LiquidRpc(args.provider_uri)
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

    rpc = LiquidRpc(args.provider_uri)
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

    rpc = LiquidRpc(args.provider_uri)
    service = LiquidService(rpc)
    start, end = service.get_block_range_for_date(args.date, args.start_hour, args.end_hour)
    print(f"{start} {end}")
    return 0


def _cmd_export_all(args: argparse.Namespace) -> int:
    from .jobs.export_all_job import export_all
    from .rpc import LiquidRpc
    from .service import LiquidService

    rpc = LiquidRpc(args.provider_uri)
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

    rpc = LiquidRpc(args.provider_uri)
    service = LiquidService(rpc)
    adapter = LiquidStreamerAdapter(
        service=service,
        output=args.output,
        batch_size=args.batch_size,
        enrich=args.enrich,
    )
    adapter.stream(start_block=args.start_block, lag=args.lag, poll_interval=args.poll_interval)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="liquidetl", description="Liquid Network ETL and streaming toolkit")
    sub = parser.add_subparsers(dest="command", required=True)

    # export_blocks_and_transactions
    p_export = sub.add_parser("export_blocks_and_transactions", help="Export blocks and transactions for a range")
    _add_common_provider(p_export)
    p_export.add_argument("-s", "-start", "--start-block", type=int, required=True)
    p_export.add_argument("-e", "-end", "--end-block", type=int, required=True)
    p_export.add_argument("--blocks-output", required=True)
    p_export.add_argument("--transactions-output", required=True)
    p_export.set_defaults(func=_cmd_export_blocks_and_transactions)

    # enrich_transactions
    p_enrich = sub.add_parser("enrich_transactions", help="Enrich transactions with input details (requires txindex=1)")
    _add_common_provider(p_enrich)
    p_enrich.add_argument("--transactions-input", required=True)
    p_enrich.add_argument("--transactions-output", required=True)
    p_enrich.set_defaults(func=_cmd_enrich_transactions)

    # get_block_range_for_date
    p_range = sub.add_parser("get_block_range_for_date", help="Return start and end block for a UTC date")
    _add_common_provider(p_range)
    p_range.add_argument("--date", required=True, help="YYYY-MM-DD")
    p_range.add_argument("--start-hour", type=int, default=0)
    p_range.add_argument("--end-hour", type=int, default=24)
    p_range.set_defaults(func=_cmd_get_block_range_for_date)

    # export_all
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

    # filter_items
    p_filter = sub.add_parser("filter_items", help="Filter NDJSON or CSV outputs using a Python predicate")
    p_filter.add_argument("--input", required=True)
    p_filter.add_argument("--output", required=True)
    p_filter.add_argument("--predicate", required=True, help="Python expression like 'lambda x: x[\"block_timestamp\"][:10]==\"2019-03-01\"'")
    p_filter.add_argument("--format", choices=("ndjson", "csv"), default="ndjson")
    p_filter.set_defaults(func=_cmd_filter_items)

    # stream
    p_stream = sub.add_parser("stream", help="Continuously stream blocks and transactions")
    _add_common_provider(p_stream)
    p_stream.add_argument("--start-block", type=int, required=True)
    p_stream.add_argument("--lag", type=int, default=0)
    p_stream.add_argument("--output", default="console", help="'console' or projects/.../topics/crypto_liquid")
    p_stream.add_argument("--batch-size", type=int, default=100)
    p_stream.add_argument("--poll-interval", type=float, default=2.0)
    p_stream.add_argument("--enrich", action="store_true")
    p_stream.set_defaults(func=_cmd_stream)

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