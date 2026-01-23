import liquidetl.cli.commands.ingest_range_to_postgres as mod


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

