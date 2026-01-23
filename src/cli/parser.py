from __future__ import annotations

import argparse

from .commands.audit_rpc_schema import audit_rpc_schema
from .commands.enrich_transactions import enrich_transactions
from .commands.export_all import export_all
from .commands.export_blocks_and_transactions import export_blocks_and_transactions
from .commands.filter_items import filter_items
from .commands.get_block_range_for_date import get_block_range_for_date
from .commands.ingest_range_to_postgres import ingest_range_to_postgres
from .commands.load_ndjson_to_postgres import load_ndjson_to_postgres
from .commands.load_ndjson_to_sqlite import load_ndjson_to_sqlite
from .commands.repair_postgres import repair_postgres
from .commands.stream import stream
from .common_args import add_common_provider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="liquidetl", description="Liquid Network ETL and streaming toolkit"
    )
    parser.add_argument(
        "--config",
        help="Path to liquidetl.config.json (defaults: ./liquidetl.config.json or ~/.config/liquidetl/config.json)",
    )
    parser.add_argument("--profile", help="Optional config profile name (config.profiles.<name>)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_export = sub.add_parser(
        "export_blocks_and_transactions", help="Export blocks and transactions for a range"
    )
    add_common_provider(p_export)
    p_export.add_argument("-s", "-start", "--start-block", type=int, required=True)
    p_export.add_argument("-e", "-end", "--end-block", type=int, required=True)
    p_export.add_argument("--blocks-output", required=True)
    p_export.add_argument("--transactions-output", required=True)
    p_export.set_defaults(func=export_blocks_and_transactions)

    p_enrich = sub.add_parser(
        "enrich_transactions", help="Enrich transactions with input details (requires txindex=1)"
    )
    add_common_provider(p_enrich)
    p_enrich.add_argument("--transactions-input", required=True)
    p_enrich.add_argument("--transactions-output", required=True)
    p_enrich.set_defaults(func=enrich_transactions)

    p_range = sub.add_parser(
        "get_block_range_for_date", help="Return start and end block for a UTC date"
    )
    add_common_provider(p_range)
    p_range.add_argument("--date", required=True, help="YYYY-MM-DD")
    p_range.add_argument("--start-hour", type=int, default=0)
    p_range.add_argument("--end-hour", type=int, default=24)
    p_range.set_defaults(func=get_block_range_for_date)

    p_all = sub.add_parser(
        "export_all", help="Partition date or block ranges into batches and export"
    )
    add_common_provider(p_all)
    group = p_all.add_mutually_exclusive_group(required=True)
    group.add_argument("--date", help="YYYY-MM-DD for date partitioning")
    group.add_argument("--start-block", type=int)
    p_all.add_argument("--end-block", type=int)
    p_all.add_argument("--batch-size", type=int, default=1000)
    p_all.add_argument("--output", required=True)
    p_all.add_argument("--enrich", action="store_true")
    p_all.set_defaults(func=export_all)

    p_filter = sub.add_parser(
        "filter_items", help="Filter NDJSON or CSV outputs using a Python predicate"
    )
    p_filter.add_argument("--input", required=True)
    p_filter.add_argument("--output", required=True)
    p_filter.add_argument(
        "--predicate",
        required=True,
        help='Python expression like \'lambda x: x["block_timestamp"][:10]=="2019-03-01"\'',
    )
    p_filter.add_argument("--format", choices=("ndjson", "csv"), default="ndjson")
    p_filter.set_defaults(func=filter_items)

    p_stream = sub.add_parser("stream", help="Continuously stream blocks and transactions")
    add_common_provider(p_stream)
    p_stream.add_argument(
        "--start-block",
        type=int,
        required=False,
        help="Start block (optional for Postgres; resumes from DB max+1)",
    )
    p_stream.add_argument("--lag", type=int, default=0)
    p_stream.add_argument(
        "--output",
        default="console",
        help="'console', 'sqlite:///path/to.db', 'postgres://user:pass@host:5432/dbname' or projects/.../topics/crypto_liquid",
    )
    p_stream.add_argument("--batch-size", type=int, default=100)
    p_stream.add_argument("--rpc-batch-size", type=int, default=1, help="Number of blocks to fetch concurrently")
    p_stream.add_argument("--poll-interval", type=float, default=2.0)
    p_stream.add_argument("--enrich", action="store_true")
    p_stream.set_defaults(func=stream)

    p_load = sub.add_parser(
        "load_ndjson_to_sqlite", help="Load NDJSON exports into a local SQLite DB"
    )
    p_load.add_argument("--db", help="Path to .db file")
    p_load.add_argument("--blocks-input", help="Path to blocks NDJSON")
    p_load.add_argument("--transactions-input", help="Path to transactions NDJSON")
    p_load.set_defaults(func=load_ndjson_to_sqlite)

    p_load_pg = sub.add_parser("load_ndjson_to_postgres", help="Load NDJSON exports into Postgres")
    p_load_pg.add_argument(
        "--dsn",
        help="Postgres DSN, e.g. postgresql://user:pass@localhost:5432/liquidetl",
    )
    p_load_pg.add_argument("--blocks-input", help="Path to blocks NDJSON")
    p_load_pg.add_argument("--transactions-input", help="Path to transactions NDJSON")
    p_load_pg.set_defaults(func=load_ndjson_to_postgres)

    p_ingest_pg = sub.add_parser(
        "ingest_range_to_postgres", help="Directly ingest a block range into Postgres"
    )
    add_common_provider(p_ingest_pg)
    p_ingest_pg.add_argument(
        "-s",
        "-start",
        "--start-block",
        type=int,
        default=1,
        help="Start height (default: 1)",
    )
    p_ingest_pg.add_argument(
        "-e",
        "-end",
        "--end-block",
        type=int,
        default=None,
        help="End height (default: node tip)",
    )
    p_ingest_pg.add_argument(
        "--dsn",
        help="Postgres DSN, e.g. postgresql://user:pass@localhost:5432/liquidetl",
    )
    p_ingest_pg.add_argument("--enrich", action="store_true")
    p_ingest_pg.add_argument(
        "--rpc-batch-size",
        type=int,
        default=200,
        help="Batch size for RPC calls (reduces round trips)",
    )
    p_ingest_pg.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Number of blocks per DB transaction",
    )
    p_ingest_pg.add_argument(
        "--prefetch",
        type=int,
        default=8,
        help="Prefetch N chunks in a background thread (default: 0)",
    )
    p_ingest_pg.add_argument(
        "--conflict-strategy",
        choices=("update", "ignore"),
        default="update",
        help="How to handle existing rows (default: update)",
    )
    p_ingest_pg.add_argument(
        "--fast-local",
        action="store_true",
        help="Aggressive local-mode defaults (ignore conflicts, disable synchronous_commit, enable prefetch)",
    )
    p_ingest_pg.add_argument(
        "--fast-rpc-decode",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Decode RPC floats as float (faster, less precise than Decimal)",
    )
    pbar = p_ingest_pg.add_mutually_exclusive_group(required=False)
    pbar.add_argument("--progress", action="store_true", help="Force progress output")
    pbar.add_argument("--no-progress", action="store_true", help="Disable progress output")
    p_ingest_pg.set_defaults(func=ingest_range_to_postgres)

    p_repair_pg = sub.add_parser(
        "repair_postgres", help="Fix duplicates and fill missing block gaps in Postgres"
    )
    p_repair_pg.add_argument(
        "-p",
        "--provider-uri",
        required=False,
        help="JSON-RPC URI (required only when actually filling gaps), e.g. http://user:pass@localhost:7041",
    )
    p_repair_pg.add_argument(
        "--datadir",
        help="Elements/Liquid datadir (optional). Used to read .cookie or elements.conf when provider-uri has no creds.",
    )
    p_repair_pg.add_argument(
        "--dsn",
        help="Postgres DSN, e.g. postgresql://user:pass@localhost:5432/liquidetl",
    )
    p_repair_pg.add_argument(
        "--start-block", type=int, help="Only repair >= this height (default: DB min)"
    )
    p_repair_pg.add_argument(
        "--end-block", type=int, help="Only repair <= this height (default: DB max)"
    )
    p_repair_pg.add_argument(
        "--dry-run", action="store_true", help="Report gaps/dupes but do not change DB"
    )
    p_repair_pg.add_argument(
        "--no-dedupe", action="store_true", help="Skip duplicate-height cleanup"
    )
    p_repair_pg.add_argument(
        "--no-fill-gaps", action="store_true", help="Skip filling missing heights"
    )
    p_repair_pg.add_argument(
        "--backfill-present",
        action="store_true",
        help="Re-ingest all heights in the selected range (requires RPC)",
    )
    p_repair_pg.add_argument(
        "--rpc-batch-size",
        type=int,
        default=25,
        help="Batch size for RPC calls (reduces round trips)",
    )
    pbar2 = p_repair_pg.add_mutually_exclusive_group(required=False)
    pbar2.add_argument("--progress", action="store_true", help="Force progress output")
    pbar2.add_argument("--no-progress", action="store_true", help="Disable progress output")
    p_repair_pg.set_defaults(func=repair_postgres)

    p_audit_rpc = sub.add_parser(
        "audit_rpc_schema", help="Probe node RPC output and suggest schema cleanup"
    )
    add_common_provider(p_audit_rpc)
    p_audit_rpc.add_argument(
        "--sample-size", type=int, default=10, help="Number of blocks sampled from chain tip"
    )
    p_audit_rpc.set_defaults(func=audit_rpc_schema)

    return parser
