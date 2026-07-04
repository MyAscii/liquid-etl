"""Tests for the production coercion functions used by PostgresWriter.

These target liquidetl.utils.postgres.coercion (what write_transaction/write_block
actually call), not the former dead in-class copies on PostgresWriter.
"""

from liquidetl.utils.postgres import writer as pg_writer
from liquidetl.utils.postgres.coercion import coerce_block_row, coerce_tx_rows


def test_coerce_tx_rows_populates_fee_maps_and_issuance():
    tx = {
        "txid": "t1",
        "hash": "t1",
        "withash": None,
        "wtxid": None,
        "block_hash": "b1",
        "block_number": 1,
        "block_timestamp": 10,
        "version": 2,
        "lock_time": 0,
        "size": 100,
        "virtual_size": 90,
        "weight": 360,
        "discount_virtual_size": 90,
        "discount_weight": 360,
        "node_fee": {"assetX": "0.00000100"},
        "inputs": [
            {
                "txid": "p0",
                "vout": 0,
                "sequence": 1,
                "input_type": "issuance",
                "is_coinbase": False,
                "scriptsig_hex": "00",
                "scriptsig_asm": "",
                "witness": [],
                "issuance": {"assetamount": "1.0", "tokenamount": "2.0"},
            }
        ],
        "outputs": [
            {
                "n": 0,
                "asset": "assetX",
                "value": "0.00000100",
                "type": "fee",
                "scriptpubkey_hex": "",
                "scriptpubkey_asm": "",
                "script_type": "fee",
                "op_return_data_hex": None,
                "nonce": "02",
                "surjection_proof": "sp",
                "rangeproof": "rp",
            }
        ],
    }

    tx_row, txins, txouts = coerce_tx_rows(tx)
    assert tx_row["fee_by_asset"] == {"assetX": 100}
    assert tx_row["explicit_out_by_asset"] == {"assetX": 100}
    assert tx_row["explicit_in_by_asset"] is None
    assert len(txins) == 1
    assert txins[0]["has_issuance"] is True
    assert txins[0]["issuance_amount"] == 100000000
    assert txins[0]["issuance_inflation_keys"] == 200000000
    assert len(txouts) == 1
    assert txouts[0]["is_fee"] is True
    assert txouts[0]["surjection_proof"] == "sp"


def test_pegin_and_issuance_input_keeps_pegin_flag():
    # M1 regression: an input that is both a peg-in and an issuance had input_type
    # clobbered to "issuance"; is_pegin/has_pegin must still be True.
    tx = {
        "txid": "t1",
        "hash": "t1",
        "inputs": [
            {
                "txid": "c",
                "vout": 2,
                "input_type": "issuance",
                "is_pegin": True,
                "issuance": {"assetamount": "1.0"},
            }
        ],
        "outputs": [],
    }
    tx_row, txins, _ = coerce_tx_rows(tx)
    assert txins[0]["is_pegin"] is True
    assert txins[0]["has_issuance"] is True
    assert tx_row["has_pegin"] is True
    assert tx_row["has_issuance"] is True


def test_empty_op_return_is_flagged():
    # L2 regression: a bare OP_RETURN (empty payload "") is still an OP_RETURN.
    tx = {
        "txid": "t1",
        "hash": "t1",
        "inputs": [],
        "outputs": [
            {"n": 0, "op_return_data_hex": ""},
            {"n": 1, "op_return_data_hex": None},
            {"n": 2, "op_return_data_hex": "abcd"},
        ],
    }
    _, _, txouts = coerce_tx_rows(tx)
    assert txouts[0]["is_op_return"] is True
    assert txouts[1]["is_op_return"] is False
    assert txouts[2]["is_op_return"] is True


def test_coerce_block_row_genesis_keeps_zero_height():
    # H3 regression: number==0 must not become NULL via `number or height`.
    row = coerce_block_row({"hash": "h0", "number": 0})
    assert row["height"] == 0
    # falls back to height when number absent
    assert coerce_block_row({"hash": "h5", "height": 5})["height"] == 5


def test_rewrite_upsert_to_do_nothing_keeps_conflict_target():
    sql = "INSERT INTO t(a) VALUES (1) ON CONFLICT (a) DO UPDATE SET a = EXCLUDED.a"
    out = pg_writer._rewrite_upsert_to_do_nothing(sql)
    assert "ON CONFLICT (a) DO NOTHING" in out
    assert "DO UPDATE SET" not in out


def test_coerce_block_row_includes_all_block_table_columns():
    block = {
        "hash": "b1",
        "number": 1,
        "version": 2,
        "previous_block_hash": "p",
        "next_block_hash": None,
        "merkle_root": "m",
        "timestamp": 10,
        "median_time": 11,
        "transaction_count": 1,
        "size": 100,
        "stripped_size": 90,
        "weight": 360,
        "signblock_witness_hex": None,
        "txids": ["t1"],
    }
    row = coerce_block_row(block)
    expected = {
        "hash",
        "height",
        "version",
        "prev_block_hash",
        "next_block_hash",
        "merkle_root",
        "time",
        "median_time",
        "tx_count",
        "size",
        "stripped_size",
        "weight",
        "signblock_solution_hex",
        "txids",
    }
    assert expected.issubset(set(row.keys()))
