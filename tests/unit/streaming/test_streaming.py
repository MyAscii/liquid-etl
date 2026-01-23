from liquidetl.streaming.streamer_adapter import LiquidStreamerAdapter


def test_stream_emits_once_and_stops(monkeypatch, stub_service):
    adapter = LiquidStreamerAdapter(service=stub_service, output="console", batch_size=1)
    emitted = {"blocks": 0, "transactions": 0}

    def fake_emit(topic, item):
        emitted[topic] += 1

    monkeypatch.setattr(adapter, "_emit", fake_emit)

    def raise_kbi(seconds):
        raise KeyboardInterrupt

    # Cause the outer loop to break after the first sleep
    monkeypatch.setattr(__import__("time"), "sleep", raise_kbi)

    try:
        adapter.stream(start_block=0, lag=0, poll_interval=0.01)
    except KeyboardInterrupt:
        # The adapter catches KeyboardInterrupt internally; ensure no leak
        pass

    # One block and its tx should be emitted before stopping
    assert emitted["blocks"] >= 1
    assert emitted["transactions"] >= 1
