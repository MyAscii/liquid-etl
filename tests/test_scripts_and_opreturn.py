from liquidetl.service import LiquidService
from liquidetl.utils.script_parsing import extract_op_return_data_hex


def test_extract_op_return_data_hex():
    assert extract_op_return_data_hex("6a") == ""
    assert extract_op_return_data_hex("6a24aa21a9ed94f15ed3a62165e4a0b99699cc28b48e19cb5bc1b1f47155db62d63f1e047d45") == (
        "aa21a9ed94f15ed3a62165e4a0b99699cc28b48e19cb5bc1b1f47155db62d63f1e047d45"
    )


def test_normalize_coinbase_scriptsig_and_witness():
    class StubRpc:
        def decodescript(self, script_hex: str):
            return {"asm": ""}

    s = LiquidService(StubRpc())
    block_item = {"number": 1, "hash": "bh", "timestamp": 123}
    tx = {
        "txid": "05ae26b7249f9de347fd3370e482a960473325df9b6caf7468ceda55c8907116",
        "size": 224,
        "vsize": 193.25,
        "weight": 773,
        "version": 2,
        "locktime": 0,
        "vin": [
            {
                "coinbase": "01710101",
                "sequence": 0xFFFFFFFF,
                "txinwitness": [
                    "0000000000000000000000000000000000000000000000000000000000000000",
                ],
            }
        ],
        "vout": [
            {
                "n": 0,
                "value": 0,
                "scriptPubKey": {"asm": "OP_RETURN", "hex": "6a", "type": "nulldata"},
            },
            {
                "n": 1,
                "value": 0,
                "scriptPubKey": {
                    "asm": "OP_RETURN OP_PUSHBYTES_36 aa21a9ed94f15ed3a62165e4a0b99699cc28b48e19cb5bc1b1f47155db62d63f1e047d45",
                    "hex": "6a24aa21a9ed94f15ed3a62165e4a0b99699cc28b48e19cb5bc1b1f47155db62d63f1e047d45",
                    "type": "nulldata",
                },
            },
        ],
    }
    norm = s._normalize_tx(tx, block_item, tx_index=0)
    assert norm["hash"] == tx["txid"]
    assert norm["txid"] == tx["txid"]
    assert norm["weight"] == 773
    assert norm["inputs"][0]["is_coinbase"] is True
    assert norm["inputs"][0]["scriptsig_hex"] == "01710101"
    assert norm["inputs"][0]["scriptsig_asm"] == "OP_PUSHBYTES_1 71 OP_PUSHBYTES_1 01"
    assert norm["inputs"][0]["witness"][0].startswith("000000")
    assert norm["outputs"][0]["op_return_data_hex"] == ""
    assert norm["outputs"][1]["op_return_data_hex"].startswith("aa21a9ed")
