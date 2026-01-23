INSERT INTO txins (
    txid, vin,
    prev_txid, prev_vout, sequence, is_coinbase,
    scriptsig_hex, scriptsig_asm,
    txinwitness, pegin_witness,
    is_pegin,
    has_issuance, issuance_asset_blinding_nonce, issuance_asset_entropy,
    issuance_amount, issuance_inflation_keys,
    prevout_scriptpubkey_hex, prevout_script_type, prevout_address
) VALUES (
    %(txid)s, %(vin)s,
    %(prev_txid)s, %(prev_vout)s, %(sequence)s, %(is_coinbase)s,
    %(scriptsig_hex)s, %(scriptsig_asm)s,
    %(txinwitness)s::jsonb, %(pegin_witness)s::jsonb,
    %(is_pegin)s,
    %(has_issuance)s, %(issuance_asset_blinding_nonce)s, %(issuance_asset_entropy)s,
    %(issuance_amount)s, %(issuance_inflation_keys)s,
    %(prevout_scriptpubkey_hex)s, %(prevout_script_type)s, %(prevout_address)s
)
ON CONFLICT (txid, vin) DO UPDATE SET
    prev_txid = EXCLUDED.prev_txid,
    prev_vout = EXCLUDED.prev_vout,
    sequence = EXCLUDED.sequence,
    is_coinbase = EXCLUDED.is_coinbase,
    scriptsig_hex = EXCLUDED.scriptsig_hex,
    scriptsig_asm = EXCLUDED.scriptsig_asm,
    txinwitness = EXCLUDED.txinwitness,
    pegin_witness = EXCLUDED.pegin_witness,
    is_pegin = EXCLUDED.is_pegin,
    has_issuance = EXCLUDED.has_issuance,
    issuance_asset_blinding_nonce = EXCLUDED.issuance_asset_blinding_nonce,
    issuance_asset_entropy = EXCLUDED.issuance_asset_entropy,
    issuance_amount = EXCLUDED.issuance_amount,
    issuance_inflation_keys = EXCLUDED.issuance_inflation_keys,
    prevout_scriptpubkey_hex = EXCLUDED.prevout_scriptpubkey_hex,
    prevout_script_type = EXCLUDED.prevout_script_type,
    prevout_address = EXCLUDED.prevout_address
