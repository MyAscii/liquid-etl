import os
import time

import liquidetl.cli as cli_mod
import pytest


@pytest.mark.integration
def test_ingest_benchmark_smoke():
    if os.getenv("LIQUID_INGEST_BENCH") != "1":
        pytest.skip("Set LIQUID_INGEST_BENCH=1 to run ingest benchmark")
    provider_uri = os.getenv("LIQUID_RPC_URI")
    dsn = os.getenv("LIQUID_DSN")
    if not provider_uri or not dsn:
        pytest.skip("Set LIQUID_RPC_URI and LIQUID_DSN to run ingest benchmark")

    start_block = int(os.getenv("LIQUID_INGEST_BENCH_START", "1"))
    end_block = int(os.getenv("LIQUID_INGEST_BENCH_END", "50"))

    t0 = time.monotonic()
    rc = cli_mod.main(
        [
            "ingest_range_to_postgres",
            "-p",
            provider_uri,
            "-s",
            str(start_block),
            "-e",
            str(end_block),
            "--dsn",
            dsn,
            "--fast-local",
            "--fast-rpc-decode",
            "--no-progress",
        ]
    )
    elapsed = max(0.001, time.monotonic() - t0)
    blocks = end_block - start_block + 1
    print(f"ingest benchmark: {blocks / elapsed:.2f} blk/s ({blocks} blocks in {elapsed:.2f}s)")
    assert rc == 0

