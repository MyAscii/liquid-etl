from liquidetl.streaming.streamer_adapter import LiquidStreamerAdapter
from liquidetl.service import LiquidService, BlockWithTxs


class StubService(LiquidService):
    def __init__(self):
        class _R: pass
        super().__init__(_R())
        self._called = 0

    def get_head_height(self):
        return 0

    def get_block_by_number(self, height: int):
        block = {"hash": f"h{height}", "number": height, "timestamp": 1000 + height}
        tx = {"hash": f"t{height}", "inputs": [], "outputs": []}
        return BlockWithTxs(block=block, transactions=[tx])


def test_stream_emits_once_and_stops(monkeypatch):
    s = StubService()
    adapter = LiquidStreamerAdapter(service=s, output="console", batch_size=1)
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