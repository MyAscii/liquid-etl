import pytest

from liquidetl.service import LiquidService, BlockWithTxs
from liquidetl.streaming.streamer_adapter import LiquidStreamerAdapter


class StubService(LiquidService):
    def __init__(self):
        class _R: pass
        super().__init__(_R())

    def get_head_height(self):
        return 0

    def get_block_by_number(self, height: int):
        block = {"hash": f"h{height}", "number": height, "timestamp": 1000 + height}
        tx = {"hash": f"t{height}", "inputs": [], "outputs": []}
        return BlockWithTxs(block=block, transactions=[tx])


def test_postgres_output_requires_optional_dependency():
    try:
        __import__("psycopg")
    except Exception:
        with pytest.raises(RuntimeError) as e:
            LiquidStreamerAdapter(service=StubService(), output="postgresql://user:pass@localhost:5432/liquidetl")
        assert "psycopg not installed" in str(e.value)
    else:
        pytest.skip("psycopg installed; skipping optional-dependency assertion")
