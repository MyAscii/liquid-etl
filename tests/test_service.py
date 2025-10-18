from decimal import Decimal

from liquidetl.service import LiquidService, BlockWithTxs


class StubRpc:
    def getblockhash(self, height: int) -> str:
        return f"h{height}"

    def getblock(self, block_hash: str, verbosity: int = 2):
        # Construct a block with two txs, one confidential output
        return {
            "hash": block_hash,
            "size": 1,
            "strippedsize": 1,
            "weight": 4,
            "height": int(block_hash[1:]) if block_hash.startswith("h") else 0,
            "version": 2,
            "merkleroot": "m",
            "time": 1000 + int(block_hash[1:]) if block_hash.startswith("h") else 1000,
            "nonce": 0,
            "bits": "1d00ffff",
            "tx": [
                {
                    "txid": "t1",
                    "size": 100,
                    "vsize": 90,
                    "version": 2,
                    "locktime": 0,
                    "vin": [{"txid": "prev", "vout": 0, "sequence": 0}],
                    "vout": [
                        {
                            "n": 0,
                            "value": 0.1234,
                            "asset": "assetid",
                            "scriptPubKey": {"addresses": ["el1..."], "reqSigs": 1},
                        }
                    ],
                },
                {
                    "txid": "t2",
                    "size": 100,
                    "vsize": 90,
                    "version": 2,
                    "locktime": 0,
                    "vin": [{"txid": "prev2", "vout": 1, "sequence": 0}],
                    "vout": [
                        {
                            "n": 0,
                            "value": None,
                            "valuecommitment": "comm",
                            "assetcommitment": "acomm",
                            "scriptPubKey": {"address": "el1abc"},
                        }
                    ],
                },
            ],
        }

    def getblockcount(self) -> int:
        return 10


def test_get_block_by_number_normalizes():
    s = LiquidService(StubRpc())
    bundle = s.get_block_by_number(0)
    b = bundle.block
    assert set(["hash", "size", "stripped_size", "weight", "number", "version", "merkle_root", "timestamp", "nonce", "bits", "transaction_count"]).issubset(b.keys())
    # Transactions have outputs and fee None when inputs not enriched
    t1 = bundle.transactions[0]
    assert t1["outputs"][0]["value"] == 0.1234
    assert t1["fee"] is None
    # Confidential mapping
    t2 = bundle.transactions[1]
    assert t2["outputs"][0]["type"] == "confidential"


def test_get_block_range_for_date_binary_search(monkeypatch):
    s = LiquidService(StubRpc())
    # Patch methods to control timestamps
    def fake_get_block_by_number(height: int):
        # Every minute starting from start
        return BlockWithTxs(block={"timestamp": 1_600_000_000 + height * 60, "hash": f"h{height}", "number": height}, transactions=[])

    monkeypatch.setattr(s, "get_block_by_number", fake_get_block_by_number)
    monkeypatch.setattr(s, "get_head_height", lambda: 100)

    start, end = s.get_block_range_for_date("2020-09-13", start_hour=0, end_hour=1)
    assert start < end