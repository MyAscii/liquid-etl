import os
import sqlite3

import pytest
from liquidetl.rpc import LiquidRpc
from liquidetl.schema import BLOCK_SCHEMA_KEYS, TRANSACTION_SCHEMA_KEYS
from liquidetl.service import LiquidService
from liquidetl.utils.sqlite_writer import SQLiteWriter


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("LIQUID_RPC_URI"),
    reason="Set LIQUID_RPC_URI to run real RPC integration tests",
)
def test_real_rpc_normalization_and_sqlite_write(tmp_path):
    uri = os.environ["LIQUID_RPC_URI"]
    rpc = LiquidRpc(uri)
    service = LiquidService(rpc)

    head = service.get_head_height()
    assert head > 0

    # Use the latest block to ensure presence of transactions
    height = max(0, head)
    bundle = service.get_block_by_number(height)

    # Normalized block keys match expected schema keys
    block = bundle.block
    assert set(BLOCK_SCHEMA_KEYS).issubset(block.keys())

    # Normalized transaction keys present for at least one tx
    if bundle.transactions:
        tx = bundle.transactions[0]
        assert set(TRANSACTION_SCHEMA_KEYS).issubset(tx.keys())

    # Write to SQLite and verify counts
    db_path = tmp_path / "real.db"
    writer = SQLiteWriter(str(db_path))
    writer.write_block(block)
    for t in bundle.transactions:
        writer.write_transaction(t)
    writer.close()

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(1) FROM blocks")
    bcount = cur.fetchone()[0]
    cur.execute("SELECT COUNT(1) FROM transactions")
    tcount = cur.fetchone()[0]
    conn.close()

    assert bcount == 1
    assert tcount == len(bundle.transactions)
