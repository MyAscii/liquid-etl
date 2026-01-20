from liquidetl.service import LiquidService, BlockWithTxs


class StubRpc:
    def getblockhash(self, height: int):
        return "h0"

    def getblock(self, h: str, verbosity: int = 2):
        return {
            "hash": h,
            "height": 0,
            "time": 123,
            "tx": [
                {
                    "txid": "tx0",
                    "vin": [
                        {"txid": "a", "vout": 0, "is_pegin": True, "sequence": 0},
                        {"txid": "b", "vout": 1, "issuance": {"asset": "asset"}, "sequence": 0},
                        {"txid": "c", "vout": 2, "is_pegin": True, "issuance": {"asset": "asset2"}, "sequence": 0},
                    ],
                    "vout": [
                        {
                            "n": 0,
                            "asset": "assetid",
                            "value": None,
                            "valuecommitment": "vc",
                            "assetcommitment": "ac",
                            "scriptPubKey": {"address": "el1abc"},
                        },
                        {
                            "n": 1,
                            "asset": "assetid",
                            "value": "0.0001",
                            "scriptPubKey": {"address": "el1def"},
                        },
                        {
                            "n": 2,
                            "asset": "assetid",
                            "value": "0.5",
                            "scriptPubKey": {"pegout": True, "address": "bc1qxyz"},
                        },
                    ],
                }
            ],
        }


def test_input_types_and_confidential_outputs():
    s = LiquidService(StubRpc())
    bundle = s.get_block_by_number(0)
    t = bundle.transactions[0]
    # Input types mapping
    assert t["inputs"][0]["input_type"] == "pegin"
    assert t["inputs"][1]["input_type"] == "issuance"
    # When both flags present, issuance takes precedence
    assert t["inputs"][2]["input_type"] == "issuance"
    # Confidential output and fee behavior
    assert t["outputs"][0]["type"] == "confidential"
    assert t["fee"] is None
    # Output totals include non-confidential outputs (sum)
    assert t["output_value"] == "0.5001"
    # Inputs not enriched yet
    assert t["input_value"] is None
    # Pegout output detection
    assert t["outputs"][2]["type"] == "pegout"
