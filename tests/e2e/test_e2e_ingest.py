import os
import subprocess
import sys

import pytest


@pytest.mark.e2e
@pytest.mark.skipif(
    not (
        os.environ.get("LIQUID_E2E")
        and os.environ.get("LIQUID_RPC_URI")
        and os.environ.get("LIQUID_DSN")
    ),
    reason="Set LIQUID_E2E=1, LIQUID_RPC_URI, and LIQUID_DSN to run E2E tests",
)
def test_e2e_ingest_range_to_postgres_writes_block():
    try:
        import psycopg
    except Exception:
        pytest.skip("psycopg not installed")

    from liquidetl.rpc import LiquidRpc

    rpc = LiquidRpc(os.environ["LIQUID_RPC_URI"])
    head = int(rpc.getblockcount())
    start = max(0, head)
    end = start

    cmd = [
        sys.executable,
        "-m",
        "liquidetl.cli",
        "ingest_range_to_postgres",
        "-p",
        os.environ["LIQUID_RPC_URI"],
        "-s",
        str(start),
        "-e",
        str(end),
        "--dsn",
        os.environ["LIQUID_DSN"],
        "--rpc-batch-size",
        "1",
        "--no-progress",
    ]
    datadir = os.environ.get("ELEMENTS_DATADIR")
    if datadir:
        cmd.extend(["--datadir", datadir])

    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr

    with psycopg.connect(os.environ["LIQUID_DSN"]) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(1) FROM blocks WHERE height=%s", (start,))
            assert cur.fetchone()[0] >= 1
