from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from ..service import LiquidService
from ..utils.db_writer import DbWriter
from ..utils.postgres_writer import PostgresWriter
from ..utils.sqlite_writer import SQLiteWriter
from ..utils.tx_enrichment import inline_enrich_inputs


class LiquidStreamerAdapter:
    def __init__(self, service: LiquidService, output: str = "console", batch_size: int = 100, enrich: bool = False):
        self.service = service
        self.output = output
        self.batch_size = batch_size
        self.enrich = enrich
        self._pubsub = None
        self._topics = None
        self._db: Optional[DbWriter] = None

        if output and output.startswith("projects/"):
            try:
                from google.cloud import pubsub_v1
                self._pubsub = pubsub_v1.PublisherClient()
                self._topics = {
                    "blocks": f"{output}.blocks",
                    "transactions": f"{output}.transactions",
                }
            except Exception:
                raise RuntimeError("google-cloud-pubsub not installed; install with pip install -e .[streaming]")
        elif output and output.startswith("sqlite://"):
            path = output[len("sqlite://"):]
            self._db = SQLiteWriter(path)
        elif output and (output.startswith("postgres://") or output.startswith("postgresql://")):
            self._db = PostgresWriter(output)

    def _emit(self, topic: str, item: Dict[str, Any]):
        if self._db:
            if topic == "blocks":
                self._db.write_block(item)
            else:
                self._db.write_transaction(item)
            return

        def default(o):
            from decimal import Decimal
            if isinstance(o, Decimal):
                return str(o)
            raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")

        line = json.dumps(item, default=default)
        if self._pubsub:
            self._pubsub.publish(self._topics[topic], line.encode("utf-8"))
        else:
            print(line)

    def _inline_enrich(self, tx: Dict[str, Any]) -> None:
        if not self.enrich:
            return
        inline_enrich_inputs(self.service, tx)

    def stream(self, start_block: int, lag: int = 0, poll_interval: float = 2.0) -> None:
        import sys
        current = start_block
        batch_count = 0
        last_log_time = 0.0
        try:
            while True:
                try:
                    head = self.service.get_head_height() - max(0, lag)
                    if current > head:
                        # We are caught up
                        sys.stderr.write(f"\rWaiting for new blocks... (current: {current - 1}, head: {head})   ")
                        sys.stderr.flush()
                        time.sleep(poll_interval)
                        continue
                    
                    # We are catching up
                    emitted = 0
                    while emitted < self.batch_size and current <= head:
                        bundle = self.service.get_block_by_number(current)
                        block_item = bundle.block
                        block_item["item_id"] = block_item.get("hash")
                        self._emit("blocks", block_item)
                        for tx in bundle.transactions:
                            tx["item_id"] = tx.get("hash")
                            self._inline_enrich(tx)
                            self._emit("transactions", tx)
                        emitted += 1
                        current += 1

                        # Log progress every second or so
                        now = time.monotonic()
                        if now - last_log_time >= 1.0:
                            remaining = head - current + 1
                            sys.stderr.write(f"\rCatching up: processed block {current-1} (target: {head}, {remaining} left)   ")
                            sys.stderr.flush()
                            last_log_time = now

                    batch_count += 1
                except Exception as e:
                    sys.stderr.write(f"\nstream error: {e}\n")
                    time.sleep(max(5.0, poll_interval))
        except KeyboardInterrupt:
            sys.stderr.write("\nStream stopped by user\n")
            return
        finally:
            if self._db:
                self._db.close()
