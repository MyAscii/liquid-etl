import pytest
from liquidetl.streaming.streamer_adapter import LiquidStreamerAdapter


def test_postgres_output_requires_optional_dependency(stub_service):
    try:
        __import__("psycopg")
    except Exception:
        with pytest.raises(RuntimeError) as e:
            LiquidStreamerAdapter(
                service=stub_service, output="postgresql://user:pass@localhost:5432/liquidetl"
            )
        assert "psycopg not installed" in str(e.value)
    else:
        pytest.skip("psycopg installed; skipping optional-dependency assertion")
