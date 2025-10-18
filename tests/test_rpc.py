import json
from decimal import Decimal

import liquidetl.rpc as rpc_mod


class FakeResp:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self):
        self.auth = None

    def post(self, url, headers=None, data=None, timeout=None):
        payload = json.loads(data)
        # Single call
        if isinstance(payload, dict):
            return FakeResp(json.dumps({"jsonrpc": "2.0", "id": payload["id"], "result": {"amount": 1.23}}))
        # Batch call
        results = []
        for item in payload:
            results.append({"jsonrpc": "2.0", "id": item["id"], "result": f"ok-{item['id']}"})
        return FakeResp(json.dumps(results))


def test_call_parses_decimal(monkeypatch):
    # Patch requests.Session to our FakeSession
    monkeypatch.setattr(rpc_mod.requests, "Session", lambda: FakeSession())
    r = rpc_mod.LiquidRpc("http://user:pass@localhost:7041")
    res = r.call("getblockcount")
    # Ensure Decimal parsing occurred inside JSON loader by checking type
    assert isinstance(r._decode(json.dumps({"a": 1.23}))['a'], Decimal)
    assert res["amount"] == Decimal("1.23")


def test_batch_call_ordering(monkeypatch):
    monkeypatch.setattr(rpc_mod.requests, "Session", lambda: FakeSession())
    r = rpc_mod.LiquidRpc("http://user:pass@localhost:7041")
    out = r.batch_call([["x", []], ["y", [1]], ["z", [2]]])
    # Should return in the same order
    assert out == ["ok-1", "ok-2", "ok-3"]