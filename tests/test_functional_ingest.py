import pytest

import liquidetl.cli as cli_mod
import liquidetl.rpc as rpc_mod
import liquidetl.utils.postgres_writer as pg_mod


@pytest.mark.functional
def test_ingest_range_builds_expected_rows(monkeypatch):
    class StubRpc:
        def __init__(self, provider_uri: str, timeout: float = 30.0, datadir=None):
            self.provider_uri = provider_uri
            self.datadir = datadir

        def getblockchaininfo(self):
            return {"chain": "liquidv1"}

        def batch_call(self, calls):
            if not calls:
                return []
            method = calls[0][0]
            if method == "getblockhash":
                return [f"h{params[0]}" for _, params in calls]
            if method == "getblock":
                out = []
                for _, params in calls:
                    bh = params[0]
                    height = int(bh[1:])
                    out.append(
                        {
                            "hash": bh,
                            "height": height,
                            "time": 1000 + height,
                            "mediantime": 900 + height,
                            "nTx": 1,
                            "tx": [
                                {
                                    "txid": f"tx{height}",
                                    "wtxid": f"wtx{height}",
                                    "hash": f"hash{height}",
                                    "withash": f"withash{height}",
                                    "version": 2,
                                    "locktime": 0,
                                    "size": 100,
                                    "vsize": 90.0,
                                    "weight": 360,
                                    "discountvsize": 90.0,
                                    "discountweight": 360,
                                    "fee": {"assetX": "0.00000100"},
                                    "vin": [{"txid": "p0", "vout": 0, "sequence": 1, "scriptSig": {"hex": "00", "asm": ""}}],
                                    "vout": [
                                        {
                                            "n": 0,
                                            "asset": "assetX",
                                            "value": "0.00000100",
                                            "scriptPubKey": {"type": "fee", "hex": "", "asm": ""},
                                        }
                                    ],
                                }
                            ],
                        }
                    )
                return out
            raise AssertionError(f"unexpected method {method}")

    captured = {"network": None, "blocks": None, "txs": None, "ins": None, "outs": None}

    class StubWriter:
        def __init__(self, dsn: str, network: str = "liquidv1"):
            captured["network"] = network

        def write_chunk(self, block_rows, tx_rows, txin_rows, txout_rows):
            captured["blocks"] = list(block_rows)
            captured["txs"] = list(tx_rows)
            captured["ins"] = list(txin_rows)
            captured["outs"] = list(txout_rows)

        def close(self):
            return None

    monkeypatch.setattr(rpc_mod, "LiquidRpc", StubRpc)
    monkeypatch.setattr(pg_mod, "PostgresWriter", StubWriter)

    rc = cli_mod.main(
        [
            "ingest_range_to_postgres",
            "-p",
            "http://127.0.0.1:7041",
            "-s",
            "10",
            "-e",
            "11",
            "--dsn",
            "postgresql://u:p@localhost:5433/db",
            "--rpc-batch-size",
            "2",
            "--no-progress",
        ]
    )
    assert rc == 0
    assert captured["network"] == "liquidv1"
    assert len(captured["blocks"]) == 2
    assert {b["height"] for b in captured["blocks"]} == {10, 11}
    assert len(captured["txs"]) == 2
    assert len(captured["ins"]) == 2
    assert len(captured["outs"]) == 2

