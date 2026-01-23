import liquidetl.cli as cli_mod
import liquidetl.rpc as rpc_mod
import liquidetl.utils.postgres_writer as pg_mod
import pytest


@pytest.mark.smoke
def test_smoke_cli_help_exits_cleanly(capsys):
    with pytest.raises(SystemExit) as e:
        cli_mod.main(["--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "Liquid Network ETL" in out or "liquidetl" in out


@pytest.mark.smoke
def test_smoke_ingest_range_executes_with_stubs(monkeypatch):
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
                    out.append({"hash": bh, "height": height, "time": 1, "tx": []})
                return out
            raise AssertionError(f"unexpected method {method}")

    captured = {"chunks": 0, "blocks": 0, "txs": 0, "ins": 0, "outs": 0}

    class StubWriter:
        def __init__(self, dsn: str, network: str = "liquidv1"):
            self.dsn = dsn
            self.network = network

        def write_chunk(self, block_rows, tx_rows, txin_rows, txout_rows):
            captured["chunks"] += 1
            captured["blocks"] += len(block_rows)
            captured["txs"] += len(tx_rows)
            captured["ins"] += len(txin_rows)
            captured["outs"] += len(txout_rows)

        def close(self):
            return None

    monkeypatch.setattr(rpc_mod, "LiquidRpc", StubRpc)
    monkeypatch.setattr(pg_mod, "PostgresWriter", StubWriter)

    rc = cli_mod.main(
        [
            "ingest_range_to_postgres",
            "-p",
            "http://127.0.0.1:7041",
            "--datadir",
            "E:\\Elements",
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
    assert captured["chunks"] == 1
    assert captured["blocks"] == 2
    assert captured["txs"] == 0
