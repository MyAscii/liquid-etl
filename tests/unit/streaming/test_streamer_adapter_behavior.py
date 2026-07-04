import builtins
from contextlib import contextmanager

import liquidetl.streaming.streamer_adapter as adapter_mod
import pytest
from liquidetl.service import BlockWithTxs
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

    adapter = LiquidStreamerAdapter(
        service=stub_service, output="console", batch_size=1, enrich=True
    )
    adapter.stream(start_block=0, lag=0, poll_interval=0.01)

    assert called["count"] >= 1


def test_db_writer_is_closed_on_shutdown(monkeypatch, stub_service, tmp_path):
    state = {"closed": False, "writes": 0}

    class FakeSQLiteWriter:
        def __init__(self, _path: str):
            return None

        @contextmanager
        def batch(self):
            state["batches"] = state.get("batches", 0) + 1
            yield self

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
    # M-stream: block + its txs are written inside a single batch() transaction.
    assert state.get("batches", 0) >= 1


class _FlakyService:
    """Head is fixed; get_block_by_number raises for one poisoned height."""

    def __init__(self, poison_height: int):
        self.poison_height = poison_height
        self.seen = []

    def get_head_height(self) -> int:
        return 3

    def get_block_by_number(self, height: int) -> BlockWithTxs:
        self.seen.append(height)
        if height == self.poison_height:
            raise RuntimeError(f"boom at {height}")
        return BlockWithTxs(
            block={"hash": f"h{height}", "number": height, "timestamp": height},
            transactions=[{"hash": f"t{height}", "index": 0}],
        )


def test_bad_block_is_dead_lettered_and_skipped(monkeypatch, tmp_path):
    svc = _FlakyService(poison_height=1)
    dl = tmp_path / "dead.ndjson"

    monkeypatch.setattr(__import__("time"), "sleep", lambda *_: None)

    adapter = LiquidStreamerAdapter(
        service=svc,
        output="console",
        batch_size=10,
        dead_letter=str(dl),
        max_block_failures=2,
    )

    # Stop the run once we have advanced past the poison block.
    real_process = adapter._process_block

    def process_and_maybe_stop(height):
        if height >= 3:
            raise KeyboardInterrupt
        return real_process(height)

    monkeypatch.setattr(adapter, "_process_block", process_and_maybe_stop)
    adapter.stream(start_block=0, lag=0, poll_interval=0.001)

    lines = [line for line in dl.read_text(encoding="utf-8").splitlines() if line]
    assert len(lines) == 1
    assert '"height": 1' in lines[0]
    # It retried height 1 max_block_failures times, then moved on to 2.
    assert svc.seen.count(1) == 2
    assert 2 in svc.seen


def test_bad_block_aborts_without_dead_letter(monkeypatch):
    svc = _FlakyService(poison_height=0)
    monkeypatch.setattr(__import__("time"), "sleep", lambda *_: None)

    adapter = LiquidStreamerAdapter(
        service=svc, output="console", batch_size=10, max_block_failures=3
    )
    with pytest.raises(RuntimeError, match="aborting stream"):
        adapter.stream(start_block=0, lag=0, poll_interval=0.001)
    assert svc.seen.count(0) == 3
