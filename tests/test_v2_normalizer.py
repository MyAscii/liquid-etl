from liquidetl.utils.v2_normalizer import normalize_block_v2, normalize_tx_v2


def test_v2_normalizer_fee_output_and_confidential_detection():
    raw_block = {
        "hash": "bh",
        "height": 1,
        "version": 2,
        "previousblockhash": "p",
        "time": 10,
        "mediantime": 11,
        "nTx": 1,
        "tx": [
            {
                "txid": "t1",
                "wtxid": "w1",
                "hash": "h1",
                "withash": "wh1",
                "version": 2,
                "locktime": 0,
                "size": 100,
                "vsize": 90.5,
                "weight": 362,
                "discountvsize": 90.5,
                "discountweight": 362,
                "fee": {"assetX": "0.00000100"},
                "vin": [{"txid": "p0", "vout": 0, "sequence": 1, "scriptSig": {"hex": "00", "asm": ""}}],
                "vout": [
                    {"n": 0, "asset": "assetX", "value": "0.00000100", "scriptPubKey": {"type": "fee", "hex": "", "asm": ""}},
                    {"n": 1, "assetcommitment": "ac", "valuecommitment": "vc", "scriptPubKey": {"type": "nulldata", "hex": "6a", "asm": "OP_RETURN"}},
                ],
            }
        ],
    }
    block_row = normalize_block_v2(raw_block, network="liquidv1")
    assert block_row["network"] == "liquidv1"
    assert block_row["tx_count"] == 1
    tx_row, txins, txouts = normalize_tx_v2(raw_block["tx"][0], block_row, tx_index_in_block=0)
    assert tx_row["fee_by_asset"]["assetX"] == 100
    assert tx_row["has_any_confidential"] is True
    assert tx_row["explicit_out_by_asset"]["assetX"] == 100
    assert len(txins) == 1
    assert len(txouts) == 2
    assert txouts[0]["is_fee"] is True

