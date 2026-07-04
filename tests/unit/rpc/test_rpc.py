import json
from decimal import Decimal

import liquidetl.rpc as rpc_mod
import pytest
from liquidetl.rpc import RpcError


class FakeResp:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise rpc_mod.requests.HTTPError(f"HTTP {self.status_code}")
        return None


def _mk(monkeypatch, session):
    monkeypatch.setattr(rpc_mod.requests, "Session", lambda: session)
    return rpc_mod.LiquidRpc("http://user:pass@localhost:7041")


class OkSession:
    def __init__(self):
        self.auth = None

    def post(self, url, headers=None, data=None, timeout=None):
        payload = json.loads(data)
        if isinstance(payload, dict):
            return FakeResp(
                json.dumps({"jsonrpc": "2.0", "id": payload["id"], "result": {"amount": 1.23}})
            )
        # Batch: echo results but REVERSED, so a positional (non-reordering) impl fails.
        results = [
            {"jsonrpc": "2.0", "id": item["id"], "result": f"ok-{item['id']}"} for item in payload
        ]
        return FakeResp(json.dumps(list(reversed(results))))


def test_call_parses_decimal(monkeypatch):
    r = _mk(monkeypatch, OkSession())
    res = r.call("getblockcount")
    assert isinstance(r._decode(json.dumps({"a": 1.23}))["a"], Decimal)
    assert res["amount"] == Decimal("1.23")


def test_batch_call_reorders_by_id(monkeypatch):
    r = _mk(monkeypatch, OkSession())
    out = r.batch_call([["x", []], ["y", [1]], ["z", [2]]])
    # Node returned reversed; client must reorder back to request order.
    assert out == ["ok-1", "ok-2", "ok-3"]


class ErrorFieldSession:
    auth = None

    def post(self, url, headers=None, data=None, timeout=None):
        payload = json.loads(data)
        return FakeResp(
            json.dumps({"id": payload["id"], "error": {"code": -8, "message": "bad block"}})
        )


def test_call_raises_rpc_error_on_error_field(monkeypatch):
    r = _mk(monkeypatch, ErrorFieldSession())
    with pytest.raises(RpcError, match="bad block"):
        r.call("getblock", ["deadbeef"])


class Http500JsonSession:
    auth = None

    def post(self, url, headers=None, data=None, timeout=None):
        payload = json.loads(data)
        # elementsd returns HTTP 500 with a JSON-RPC error body for bad requests.
        return FakeResp(
            json.dumps({"id": payload["id"], "error": {"code": -32601, "message": "no method"}}),
            status_code=500,
        )


def test_http_500_with_jsonrpc_body_surfaces_as_rpc_error(monkeypatch):
    r = _mk(monkeypatch, Http500JsonSession())
    with pytest.raises(RpcError, match="no method"):
        r.call("bogus")


class ShortBatchSession:
    auth = None

    def post(self, url, headers=None, data=None, timeout=None):
        payload = json.loads(data)
        # Drop the last id from the response (partial/short batch).
        results = [
            {"jsonrpc": "2.0", "id": item["id"], "result": f"ok-{item['id']}"}
            for item in payload[:-1]
        ]
        return FakeResp(json.dumps(results))


def test_short_batch_raises_rpc_error_not_keyerror(monkeypatch):
    r = _mk(monkeypatch, ShortBatchSession())
    with pytest.raises(RpcError, match="missing ids"):
        r.batch_call([["a", []], ["b", []], ["c", []]])


class FlakySession:
    """Raises ConnectionError a set number of times, then succeeds."""

    auth = None

    def __init__(self, fail_times: int):
        self.fail_times = fail_times
        self.calls = 0

    def post(self, url, headers=None, data=None, timeout=None):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise rpc_mod.requests.ConnectionError("connection reset")
        payload = json.loads(data)
        return FakeResp(json.dumps({"id": payload["id"], "result": 42}))


def test_retries_transient_connection_errors(monkeypatch):
    monkeypatch.setattr(rpc_mod.time, "sleep", lambda *_: None)
    session = FlakySession(fail_times=2)
    r = _mk(monkeypatch, session)
    assert r.call("getblockcount") == 42
    assert session.calls == 3


def test_gives_up_after_max_retries(monkeypatch):
    monkeypatch.setattr(rpc_mod.time, "sleep", lambda *_: None)
    session = FlakySession(fail_times=99)
    r = _mk(monkeypatch, session)
    r._max_retries = 2
    with pytest.raises(RpcError, match="failed after 3 attempt"):
        r.call("getblockcount")
    assert session.calls == 3
