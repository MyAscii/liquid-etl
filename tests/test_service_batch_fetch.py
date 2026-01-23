from liquidetl.service import LiquidService


class StubRpc:
    def __init__(self):
        self.calls = []

    def batch_call(self, calls):
        self.calls.append(list(calls))
        method = calls[0][0] if calls else None
        if method == "getblockhash":
            return [f"h{params[0]}" for _, params in calls]
        if method == "getblock":
            out = []
            for _, params in calls:
                h = params[0]
                out.append({"hash": h, "height": int(h[1:]), "time": 1, "tx": []})
            return out
        raise AssertionError(f"unexpected method {method}")

    def getblockcount(self):
        return 0


def test_get_blocks_by_numbers_batches_calls():
    rpc = StubRpc()
    s = LiquidService(rpc)
    bundles = s.get_blocks_by_numbers([5, 6, 7])
    assert [b.block["number"] for b in bundles] == [5, 6, 7]
    assert len(rpc.calls) == 2
    assert [m for (m, _) in rpc.calls[0]] == ["getblockhash", "getblockhash", "getblockhash"]
    assert [m for (m, _) in rpc.calls[1]] == ["getblock", "getblock", "getblock"]

