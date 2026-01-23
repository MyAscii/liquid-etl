from liquidetl.utils.normalizer import normalize_block, normalize_tx


def test_normalizer_fee_output_and_confidential_detection():
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
                "vin": [
                    {
                        "txid": "p0",
                        "vout": 0,
                        "sequence": 1,
                        "scriptSig": {"hex": "00", "asm": ""},
                        "prevout": {"asset": "assetX", "value": "0.00000100"},
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
                        "asset": "assetX",
                        "value": "0.00000100",
                        "scriptPubKey": {"type": "fee", "hex": "", "asm": ""},
                    },
                    {
                        "n": 1,
                        "assetcommitment": "ac",
                        "valuecommitment": "vc",
                        "scriptPubKey": {"type": "nulldata", "hex": "6a", "asm": "OP_RETURN"},
                    },
                ],
            }
        ],
    }
    block_row = normalize_block(raw_block, network="liquidv1")
    assert block_row["network"] == "liquidv1"
    assert block_row["tx_count"] == 1
    tx_row, txins, txouts = normalize_tx(raw_block["tx"][0], block_row, tx_index_in_block=0)
    assert tx_row["fee_by_asset"]["assetX"] == 100
    assert tx_row["has_any_confidential"] is True
    assert tx_row["explicit_in_by_asset"]["assetX"] == 100
    assert tx_row["explicit_out_by_asset"]["assetX"] == 100
    assert len(txins) == 1
    assert txins[0]["has_issuance"] is True
    assert txins[0]["issuance_amount"] == 100000000
    assert txins[0]["issuance_inflation_keys"] == 200000000
    assert len(txouts) == 2
    assert txouts[0]["is_fee"] is True


def test_normalize_block_txids_and_extdata_type():
    raw_block = {
        "hash": "bh",
        "height": 1,
        "version": 2,
        "time": 10,
        "mediantime": 11,
        "signblock_challenge": "aa",
        "signblock_witness_hex": "bb",
        "tx": [{"txid": "t1"}, {"txid": "t2"}, "not-a-dict", {"no_txid": True}],
    }
    block_row = normalize_block(raw_block, network="liquidv1")
    assert block_row["txids"] == ["t1", "t2"]
    assert block_row["extdata_type"] == "proof"


def test_normalize_tx_pegout_and_op_return_detection():
    raw_block = {"hash": "bh", "height": 1, "time": 10}
    block_row = normalize_block(raw_block, network="liquidv1")
    tx = {
        "txid": "t1",
        "vin": [{"txid": "p0", "vout": 0, "sequence": 1, "scriptSig": {"hex": "00", "asm": ""}}],
        "vout": [
            {
                "n": 0,
                "asset": "assetX",
                "value": "1.0",
                "scriptPubKey": {"type": "pegout", "hex": "", "asm": "", "address": "bc1qxyz"},
            },
            {
                "n": 1,
                "asset": "assetX",
                "value": "0.1",
                "scriptPubKey": {
                    "type": "nulldata",
                    "hex": "6a04deadbeef",
                    "asm": "OP_RETURN deadbeef",
                },
            },
        ],
    }
    tx_row, _, txouts = normalize_tx(tx, block_row, tx_index_in_block=0)
    assert tx_row["has_pegout"] is True
    assert txouts[0]["is_pegout"] is True
    assert txouts[1]["is_op_return"] is True
    assert txouts[1]["op_return_data_hex"] == "deadbeef"


def test_normalize_tx_pegin_value_and_asset():
    raw_block = {"hash": "bh", "height": 1, "time": 10}
    block_row = normalize_block(raw_block, network="liquidv1")
    tx = {
        "txid": "t1",
        "vin": [
            {
                "txid": "p0",
                "vout": 0,
                "sequence": 1,
                "is_pegin": True,
                "pegin_value": "0.5",
                "pegin_asset": "assetX",
            }
        ],
        "vout": [
            {
                "n": 0,
                "asset": "assetX",
                "value": "0.1",
                "scriptPubKey": {"type": "fee", "hex": "", "asm": ""},
            }
        ],
    }
    _, txins, _ = normalize_tx(tx, block_row, tx_index_in_block=0)
    assert txins[0]["is_pegin"] is True
    assert txins[0]["pegin_asset_id"] == "assetX"
    assert txins[0]["pegin_value_sat"] == 50000000


def test_monkey_normalizer_random_inputs_do_not_crash():
    import random

    rnd = random.Random(0)
    raw_block = {"hash": "bh", "height": 1, "time": 10}
    block_row = normalize_block(raw_block, network="liquidv1")

    for _ in range(250):
        vin_count = rnd.randint(0, 5)
        vout_count = rnd.randint(0, 6)

        vins = []
        for i in range(vin_count):
            scriptsig_hex = rnd.choice([None, "00", "51"])
            scriptsig = {}
            if scriptsig_hex is not None:
                scriptsig["hex"] = scriptsig_hex
            if rnd.random() < 0.3:
                scriptsig["asm"] = ""
            vin = {
                "txid": f"ptx{rnd.randint(0, 50)}",
                "vout": rnd.randint(0, 10),
                "sequence": rnd.randint(0, 10),
                "scriptSig": scriptsig,
            }
            if rnd.random() < 0.1:
                vin["is_pegin"] = True
            if rnd.random() < 0.1:
                vin["issuance"] = {"asset": "asset"}
            if rnd.random() < 0.2:
                vin["prevout"] = {
                    "asset": "assetX",
                    "value": f"0.{rnd.randint(0, 99999999):08d}",
                    "scriptPubKey": {
                        "type": "witness_v0_keyhash",
                        "hex": "0014",
                        "address": "el1qq",
                    },
                }
            vins.append(vin)

        vouts = []
        for n in range(vout_count):
            is_conf = rnd.random() < 0.2
            hex_script = rnd.choice(["", "0014", "6a02abcd", "76a914"])
            vout = {
                "n": n,
                "asset": "assetX",
                "scriptPubKey": {
                    "type": rnd.choice(["fee", "nulldata", "witness_v0_keyhash", "pegout"]),
                    "hex": hex_script,
                    "asm": "",
                },
            }
            if is_conf:
                vout["value"] = None
                vout["valuecommitment"] = "vc"
                vout["assetcommitment"] = "ac"
            else:
                vout["value"] = f"0.{rnd.randint(0, 99999999):08d}"
            if rnd.random() < 0.1:
                vout["pegout"] = {
                    "genesis_hash": "00",
                    "scriptpubkey": "51",
                    "value": "0.0001",
                    "asset": "assetX",
                }
            vouts.append(vout)

        tx = {
            "txid": f"t{rnd.randint(0, 100000)}",
            "hash": f"h{rnd.randint(0, 100000)}",
            "withash": f"wh{rnd.randint(0, 100000)}",
            "wtxid": f"w{rnd.randint(0, 100000)}",
            "locktime": rnd.randint(0, 500),
            "version": 2,
            "size": rnd.randint(0, 5000),
            "vsize": float(rnd.randint(0, 5000)),
            "weight": rnd.randint(0, 20000),
            "discountvsize": float(rnd.randint(0, 5000)),
            "discountweight": rnd.randint(0, 20000),
            "fee": {"assetX": f"0.{rnd.randint(0, 99999999):08d}"} if rnd.random() < 0.5 else None,
            "vin": vins,
            "vout": vouts,
        }

        tx_row, txins, txouts = normalize_tx(tx, block_row, tx_index_in_block=0)
        assert isinstance(tx_row, dict)
        assert isinstance(txins, list)
        assert isinstance(txouts, list)
        assert tx_row["network"] == "liquidv1"
