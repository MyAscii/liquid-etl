from __future__ import annotations

import argparse
import json

from ...rpc import LiquidRpc
from ...utils.rpc_schema_audit import (
    audit_rpc_blocks,
    suggest_prunable_postgres_columns,
    to_postgres_drop_column_sql,
)


def audit_rpc_schema(args: argparse.Namespace) -> int:
    rpc = LiquidRpc(args.provider_uri, datadir=args.datadir)
    head = rpc.getblockcount()
    sample_size = max(1, int(args.sample_size))
    heights = list(range(max(0, head - sample_size + 1), head + 1))

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

