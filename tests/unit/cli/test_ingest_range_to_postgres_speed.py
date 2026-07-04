import threading
import time

import liquidetl.cli.commands.ingest_range_to_postgres as mod
import pytest


def test_chunked_range_yields_expected_heights():
    chunks = list(mod._chunked_range(0, 5, 2))
    assert chunks == [[0, 1], [2, 3], [4, 5]]


def test_iter_raw_block_batches_prefetch_preserves_order(monkeypatch):
    def fake_fetch(_rpc, heights, *, rpc_batch_size, show_progress):
        return [{"height": h} for h in heights]

    monkeypatch.setattr(mod, "_fetch_raw_blocks_chunked", fake_fetch)
    chunks = [[0, 1], [2, 3], [4, 5]]

    out_no_prefetch = []
    for batch in mod._iter_raw_block_batches(
        None, chunks, rpc_batch_size=2, show_progress=False, prefetch=0
    ):
        out_no_prefetch.extend([b["height"] for b in batch])
    assert out_no_prefetch == [0, 1, 2, 3, 4, 5]

    out_prefetch = []
    for batch in mod._iter_raw_block_batches(
        None, chunks, rpc_batch_size=2, show_progress=False, prefetch=2
    ):
        out_prefetch.extend([b["height"] for b in batch])
    assert out_prefetch == [0, 1, 2, 3, 4, 5]


def test_prefetch_producer_stops_when_consumer_abandons_generator(monkeypatch):
    # M4 regression: if the consumer stops iterating (e.g. write raised), the
    # background producer must not leak, blocked forever on a full queue.
    def fake_fetch(_rpc, heights, *, rpc_batch_size, show_progress):
        return [{"height": h} for h in heights]

    monkeypatch.setattr(mod, "_fetch_raw_blocks_chunked", fake_fetch)
    chunks = [[h] for h in range(1000)]

    base = threading.active_count()
    gen = mod._iter_raw_block_batches(
        None, iter(chunks), rpc_batch_size=1, show_progress=False, prefetch=2
    )
    next(gen)  # start the producer and pull one batch
    gen.close()  # abandon: GeneratorExit runs the draining finally and joins the thread

    deadline = time.monotonic() + 2.0
    while threading.active_count() > base and time.monotonic() < deadline:
        time.sleep(0.01)
    assert threading.active_count() == base


def test_prefetch_producer_error_propagates_to_consumer(monkeypatch):
    def boom(_rpc, heights, *, rpc_batch_size, show_progress):
        raise RuntimeError("fetch failed")

    monkeypatch.setattr(mod, "_fetch_raw_blocks_chunked", boom)

    base = threading.active_count()
    with pytest.raises(RuntimeError, match="fetch failed"):
        for _ in mod._iter_raw_block_batches(
            None, iter([[0], [1]]), rpc_batch_size=1, show_progress=False, prefetch=2
        ):
            pass

    deadline = time.monotonic() + 2.0
    while threading.active_count() > base and time.monotonic() < deadline:
        time.sleep(0.01)
    assert threading.active_count() == base
