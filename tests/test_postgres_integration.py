import os

import pytest


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("LIQUID_DSN"), reason="Set LIQUID_DSN to run Postgres integration tests"
)
def test_postgres_writer_writes_rows():
    try:
        import psycopg
    except Exception:
        pytest.skip("psycopg not installed")

    from liquidetl.utils.normalizer import normalize_block, normalize_tx
    from liquidetl.utils.postgres_writer import PostgresWriter

    dsn = os.environ["LIQUID_DSN"]
    raw_block = {
        "hash": "it_block_hash",
        "height": 424242,
        "version": 2,
        "time": 123,
        "mediantime": 124,
        "tx": [
            {
                "txid": "it_txid",
                "wtxid": "it_wtxid",
                "hash": "it_hash",
                "withash": "it_withash",
                "version": 2,
                "locktime": 0,
                "size": 100,
                "vsize": 90.0,
                "weight": 360,
                "discountvsize": 90.0,
                "discountweight": 360,
                "fee": {"assetX": "0.00000100"},
                "vin": [
                    {
                        "txid": "p0",
                        "vout": 0,
                        "sequence": 1,
                        "scriptSig": {"hex": "00", "asm": ""},
                        "prevout": {"asset": "assetX", "value": "0.00000100"},
                        "issuance": {"assetamount": "1.0", "tokenamount": "2.0"},
                    }
                ],
                "vout": [
                    {
                        "n": 0,
                        "asset": "assetX",
                        "value": "0.00000100",
                        "nonce": "02",
                        "surjectionproof": "sp",
                        "rangeproof": "rp",
                        "scriptPubKey": {"type": "fee", "hex": "", "asm": ""},
                    }
                ],
            }
        ],
    }

    writer = PostgresWriter(dsn)
    try:
        block_row = normalize_block(raw_block, network="liquidv1")
        tx_row, txins, txouts = normalize_tx(raw_block["tx"][0], block_row, tx_index_in_block=0)
        writer.write_chunk([block_row], [tx_row], txins, txouts)
    finally:
        writer.close()

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(1) FROM blocks WHERE hash=%s", ("it_block_hash",))
            assert cur.fetchone()[0] == 1
            cur.execute("SELECT COUNT(1) FROM transactions WHERE txid=%s", ("it_txid",))
            assert cur.fetchone()[0] == 1
            cur.execute("SELECT COUNT(1) FROM txins WHERE txid=%s", ("it_txid",))
            assert cur.fetchone()[0] >= 1
            cur.execute("SELECT COUNT(1) FROM txouts WHERE txid=%s", ("it_txid",))
            assert cur.fetchone()[0] >= 1
            cur.execute(
                "SELECT COUNT(1) FROM txins WHERE txid=%s AND issuance_amount IS NOT NULL",
                ("it_txid",),
            )
            assert cur.fetchone()[0] >= 1
            cur.execute(
                "SELECT COUNT(1) FROM transactions WHERE txid=%s AND explicit_in_by_asset IS NOT NULL",
                ("it_txid",),
            )
            assert cur.fetchone()[0] == 1

        with conn.cursor() as cur:
            cur.execute("DELETE FROM txouts WHERE txid=%s", ("it_txid",))
            cur.execute("DELETE FROM txins WHERE txid=%s", ("it_txid",))
            cur.execute("DELETE FROM transactions WHERE txid=%s", ("it_txid",))
            cur.execute("DELETE FROM blocks WHERE hash=%s", ("it_block_hash",))


@pytest.mark.integration
@pytest.mark.skipif(
    not (os.environ.get("LIQUID_DSN") and os.environ.get("LIQUID_RPC_URI")),
    reason="Set LIQUID_DSN and LIQUID_RPC_URI to run RPC+Postgres integration tests",
)
def test_real_rpc_block_can_be_written_to_postgres():
    try:
        import psycopg
    except Exception:
        pytest.skip("psycopg not installed")

    from liquidetl.rpc import LiquidRpc
    from liquidetl.service import LiquidService
    from liquidetl.utils.normalizer import normalize_block, normalize_tx
    from liquidetl.utils.postgres_writer import PostgresWriter

    rpc = LiquidRpc(os.environ["LIQUID_RPC_URI"])
    service = LiquidService(rpc)
    head = service.get_head_height()
    height = max(0, head)
    block_hash = rpc.getblockhash(height)
    raw_block = rpc.getblock(block_hash, verbosity=3)

    dsn = os.environ["LIQUID_DSN"]
    network = rpc.getblockchaininfo().get("chain") or "liquidv1"

    writer = PostgresWriter(dsn)
    try:
        block_row = normalize_block(raw_block, network=network)
        tx_rows = []
        txins = []
        txouts = []
        for i, raw_tx in enumerate(raw_block.get("tx", []) or []):
            if not isinstance(raw_tx, dict):
                continue
            tx_row, ins, outs = normalize_tx(raw_tx, block_row, tx_index_in_block=i)
            tx_rows.append(tx_row)
            txins.extend(ins)
            txouts.extend(outs)
        writer.write_chunk([block_row], tx_rows, txins, txouts)
    finally:
        writer.close()

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(1) FROM blocks WHERE hash=%s", (raw_block.get("hash"),))
            assert cur.fetchone()[0] == 1
