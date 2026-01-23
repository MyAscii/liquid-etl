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
            "tx": [
                {
                    "txid": "t1",
                    "size": 100,
                    "vsize": 90,
                    "version": 2,
                    "locktime": 0,
                    "vin": [
                        {
                            "txid": "prev",
                            "vout": 0,
                            "sequence": 0,
                            "issuance": {
                                "assetBlindingNonce": "00",
                                "assetEntropy": "11",
                                "assetamount": "1.0",
                                "tokenamount": "2.0",
                                "assetamountcommitment": "aa",
                                "tokenamountcommitment": "bb",
                            },
                        }
                    ],
                    "vout": [
                        {
                            "n": 0,
                            "value": 0.1234,
                            "asset": "assetid",
                            "scriptPubKey": {"addresses": ["el1..."], "reqSigs": 1, "type": "fee"},
                        }
                    ],
                },
                {
                    "txid": "t2",
                    "size": 100,
                    "vsize": 90,
                    "version": 2,
                    "locktime": 0,
                    "vin": [
                        {
                            "txid": "prev2",
                            "vout": 1,
                            "sequence": 0,
                            "is_pegin": True,
                            "pegin_genesis_hash": "00",
                            "pegin_claim_script": "51",
                            "pegin_tx": "aa",
                            "pegin_txout_proof": "bb",
                            "pegin_blockhash": "cc",
                            "pegin_value": "0.5",
                            "pegin_asset": "assetid",
                        }
                    ],
                    "vout": [
                        {
                            "n": 0,
                            "value": None,
                            "valuecommitment": "comm",
                            "assetcommitment": "acomm",
                            "nonce": "02",
                            "surjectionproof": "sp",
                            "rangeproof": "rp",
                            "pegout": {"genesis_hash": "00", "scriptpubkey": "0014", "value": "0.0001", "asset": "assetid", "extra_data": "ee"},
                            "scriptPubKey": {"address": "el1abc", "type": "pegout", "hex": "0014"},
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
    assert t2["outputs"][0]["type"] == "pegout"
    assert t2["inputs"][0]["input_type"] == "pegin"
    assert t2["inputs"][0]["pegin_genesis_hash"] == "00"
    assert t1["inputs"][0]["input_type"] == "issuance"
    assert isinstance(t1["inputs"][0]["issuance"], dict)


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
