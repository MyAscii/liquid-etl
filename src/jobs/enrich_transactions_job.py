from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from ..service import LiquidService
from ..utils.tx_enrichment import inline_enrich_inputs


class EnrichTransactionsJob:
    def __init__(self, service: LiquidService, transactions_input: str, transactions_output: str):
        self.service = service
        self.transactions_input = transactions_input
        self.transactions_output = transactions_output

    def _default(self, obj: Any):
        # Enriched prevout values decode as Decimal when use_decimal is on.
        if isinstance(obj, Decimal):
            return str(obj)
        raise TypeError(f"Type not serializable: {type(obj)}")

    def run(self) -> None:
        with (
            open(self.transactions_input, "r", encoding="utf-8") as fin,
            open(self.transactions_output, "w", encoding="utf-8") as fout,
        ):
            for line in fin:
                if not line.strip():
                    continue
                tx = json.loads(line)
                inline_enrich_inputs(self.service, tx)
                fout.write(json.dumps(tx, default=self._default))
                fout.write("\n")
