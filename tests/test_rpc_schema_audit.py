from liquidetl.utils.rpc_schema_audit import audit_rpc_blocks, suggest_prunable_postgres_columns


def test_audit_rpc_blocks_counts_keys():
    blocks = [
        {
            "signblock_challenge": "aa",
            "signblock_witness_hex": "bb",
            "tx": [
                {
                    "vin": [{"is_pegin": True, "prevout": {"value": "<confidential>"}, "txinwitness": ["00"]}],
                    "vout": [{"value": "<confidential>", "asset": "asset", "valuecommitment": "vc", "surjectionproof": "sp"}],
                }
            ],
        }
    ]
    audit = audit_rpc_blocks(blocks)
    assert audit.sampled_blocks == 1
    assert audit.block_key_hits["signblock_challenge"] == 1
    assert audit.block_key_hits["signblock_witness_hex"] == 1
    assert audit.vin_key_hits["is_pegin"] == 1
    assert audit.vin_key_hits["prevout"] == 1
    assert audit.vout_key_hits["surjectionproof"] == 1
    assert audit.prevout_key_hits["value"] == 1


def test_suggest_prunable_columns_when_fields_never_seen():
    blocks = [
        {
            "tx": [
                {
                    "vin": [{"is_pegin": True}],
                    "vout": [{"value": 1, "asset": "a"}],
                }
            ]
        }
    ]
    audit = audit_rpc_blocks(blocks)
    prunable = suggest_prunable_postgres_columns(audit)
    assert "bits" in prunable["blocks"]
    assert "nonce" in prunable["blocks"]
    assert "difficulty" in prunable["blocks"]
    assert "chainwork" in prunable["blocks"]
    assert "pegin_value" in prunable["txins"]
    assert "pegin_asset" in prunable["txins"]
    assert "pegin_claim_script" in prunable["txins"]
    assert "rangeproof" in prunable["txouts"]
