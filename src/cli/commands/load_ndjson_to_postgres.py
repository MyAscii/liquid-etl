from __future__ import annotations

import argparse
import json

from ...utils.postgres_writer import PostgresWriter


def load_ndjson_to_postgres(args: argparse.Namespace) -> int:
    writer = PostgresWriter(args.dsn)
    if args.blocks_input:
        for item in _iter_ndjson_items(args.blocks_input):
            writer.write_block(item)
    if args.transactions_input:
        for item in _iter_ndjson_items(args.transactions_input):
            writer.write_transaction(item)
    writer.close()
    return 0


def _iter_ndjson_items(path: str):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            yield json.loads(line)

