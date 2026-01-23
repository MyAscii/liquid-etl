INSERT INTO txouts (
    txid, vout,
    asset_id, asset_commitment, value_sat, value_commitment,
    scriptpubkey_hex, scriptpubkey_asm, script_type, address,
    is_op_return, op_return_data_hex,
    is_fee, surjection_proof
) VALUES (
    %(txid)s, %(vout)s,
    %(asset_id)s, %(asset_commitment)s, %(value_sat)s, %(value_commitment)s,
    %(scriptpubkey_hex)s, %(scriptpubkey_asm)s, %(script_type)s, %(address)s,
    %(is_op_return)s, %(op_return_data_hex)s,
    %(is_fee)s, %(surjection_proof)s
)
ON CONFLICT (txid, vout) DO UPDATE SET
    asset_id = EXCLUDED.asset_id,
    asset_commitment = EXCLUDED.asset_commitment,
    value_sat = EXCLUDED.value_sat,
    value_commitment = EXCLUDED.value_commitment,
    scriptpubkey_hex = EXCLUDED.scriptpubkey_hex,
    scriptpubkey_asm = EXCLUDED.scriptpubkey_asm,
    script_type = EXCLUDED.script_type,
    address = EXCLUDED.address,
    is_op_return = EXCLUDED.is_op_return,
    op_return_data_hex = EXCLUDED.op_return_data_hex,
    is_fee = EXCLUDED.is_fee,
    surjection_proof = EXCLUDED.surjection_proof
