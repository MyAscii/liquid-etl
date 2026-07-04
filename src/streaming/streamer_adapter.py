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
    def __init__(
        self,
        service: LiquidService,
        output: str = "console",
        batch_size: int = 100,
        enrich: bool = False,
        dead_letter: Optional[str] = None,
        max_block_failures: int = 5,
        max_backoff: float = 60.0,
    ):
        self.service = service
        self.output = output
        self.batch_size = batch_size
        self.enrich = enrich
        self.dead_letter = dead_letter
        self.max_block_failures = max(1, int(max_block_failures))
        self.max_backoff = float(max_backoff)
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
            except Exception as e:
                raise RuntimeError(
                    "google-cloud-pubsub not installed; install with pip install -e .[streaming]"
                ) from e
        elif output and output.startswith("sqlite://"):
            path = output[len("sqlite://") :]
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

    def _process_block(self, height: int) -> None:
        bundle = self.service.get_block_by_number(height)
        block_item = bundle.block
        block_item["item_id"] = block_item.get("hash")
        txs = bundle.transactions
        # Enrich (network I/O) before opening the write transaction, then commit the
        # whole block in one transaction instead of one round-trip per item.
        for tx in txs:
            tx["item_id"] = tx.get("hash")
            self._inline_enrich(tx)
        if self._db is not None:
            with self._db.batch():
                self._db.write_block(block_item)
                for tx in txs:
                    self._db.write_transaction(tx)
        else:
            self._emit("blocks", block_item)
            for tx in txs:
                self._emit("transactions", tx)

    def _record_dead_letter(self, height: int, error: BaseException) -> None:
        if not self.dead_letter:
            return
        record = json.dumps({"height": height, "error": str(error)})
        with open(self.dead_letter, "a", encoding="utf-8") as f:
            f.write(record + "\n")

    def stream(self, start_block: int, lag: int = 0, poll_interval: float = 2.0) -> None:
        import sys

        current = start_block
        last_log_time = 0.0
        consecutive_failures = 0
        try:
            while True:
                try:
                    head = self.service.get_head_height() - max(0, lag)
                    if current > head:
                        # We are caught up
                        sys.stderr.write(
                            f"\rWaiting for new blocks... (current: {current - 1}, head: {head})   "
                        )
                        sys.stderr.flush()
                        time.sleep(poll_interval)
                        continue

                    # We are catching up
                    emitted = 0
                    while emitted < self.batch_size and current <= head:
                        self._process_block(current)
                        consecutive_failures = 0
                        emitted += 1
                        current += 1

                        # Log progress every second or so
                        now = time.monotonic()
                        if now - last_log_time >= 1.0:
                            remaining = head - current + 1
                            sys.stderr.write(
                                f"\rCatching up: processed block {current-1} (target: {head}, {remaining} left)   "
                            )
                            sys.stderr.flush()
                            last_log_time = now
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    consecutive_failures += 1
                    sys.stderr.write(
                        f"\nstream error at height {current} "
                        f"(attempt {consecutive_failures}/{self.max_block_failures}): {e}\n"
                    )
                    if consecutive_failures >= self.max_block_failures:
                        if self.dead_letter:
                            self._record_dead_letter(current, e)
                            sys.stderr.write(
                                f"dead-lettered height {current} after "
                                f"{consecutive_failures} failures; skipping\n"
                            )
                            current += 1
                            consecutive_failures = 0
                            continue
                        raise RuntimeError(
                            f"aborting stream: height {current} failed "
                            f"{consecutive_failures} times: {e}"
                        ) from e
                    backoff = min(
                        self.max_backoff,
                        max(1.0, poll_interval) * (2 ** (consecutive_failures - 1)),
                    )
                    time.sleep(backoff)
        except KeyboardInterrupt:
            sys.stderr.write("\nStream stopped by user\n")
            return
        finally:
            if self._db:
                self._db.close()
