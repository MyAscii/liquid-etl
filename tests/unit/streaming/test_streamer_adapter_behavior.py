import builtins

import pytest

import liquidetl.streaming.streamer_adapter as adapter_mod
from liquidetl.streaming.streamer_adapter import LiquidStreamerAdapter


def test_pubsub_output_requires_optional_dependency(monkeypatch, stub_service):
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("google"):
            raise ImportError("google-cloud-pubsub not installed")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError) as e:
        LiquidStreamerAdapter(service=stub_service, output="projects/x", batch_size=1)
    assert "google-cloud-pubsub not installed" in str(e.value)


def test_enrich_calls_inline_enrichment(monkeypatch, stub_service):
    called = {"count": 0}

    def fake_inline_enrich_inputs(service, tx):
        called["count"] += 1

    monkeypatch.setattr(adapter_mod, "inline_enrich_inputs", fake_inline_enrich_inputs)

    def raise_kbi(_seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(__import__("time"), "sleep", raise_kbi)

    adapter = LiquidStreamerAdapter(service=stub_service, output="console", batch_size=1, enrich=True)
    adapter.stream(start_block=0, lag=0, poll_interval=0.01)

    assert called["count"] >= 1


def test_db_writer_is_closed_on_shutdown(monkeypatch, stub_service, tmp_path):
    state = {"closed": False, "writes": 0}

    class FakeSQLiteWriter:
        def __init__(self, _path: str):
            return None

        def write_block(self, _block):
            state["writes"] += 1

        def write_transaction(self, _tx):
            state["writes"] += 1

        def close(self):
            state["closed"] = True

    monkeypatch.setattr(adapter_mod, "SQLiteWriter", FakeSQLiteWriter)

    def raise_kbi(_seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(__import__("time"), "sleep", raise_kbi)

    db_path = tmp_path / "local.db"
    adapter = LiquidStreamerAdapter(
        service=stub_service, output=f"sqlite://{db_path.as_posix()}", batch_size=1
    )
    adapter.stream(start_block=0, lag=0, poll_interval=0.01)

    assert state["writes"] >= 2
    assert state["closed"] is True

