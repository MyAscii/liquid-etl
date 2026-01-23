from __future__ import annotations

import argparse

from ...jobs.enrich_transactions_job import EnrichTransactionsJob
from ...rpc import LiquidRpc
from ...service import LiquidService


def enrich_transactions(args: argparse.Namespace) -> int:
    rpc = LiquidRpc(args.provider_uri, datadir=args.datadir)
    service = LiquidService(rpc)
    job = EnrichTransactionsJob(
        service=service,
        transactions_input=args.transactions_input,
        transactions_output=args.transactions_output,
    )
    job.run()
    return 0
