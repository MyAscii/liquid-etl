INSERT INTO transactions (
    txid, wtxid, hash, withash,
    block_hash, block_height, block_time, tx_index_in_block, confirmed,
    version, lock_time, size, vsize, weight, discount_vsize, discount_weight,
    vin_count, vout_count,
    fee_by_asset, explicit_in_by_asset, explicit_out_by_asset,
    has_any_confidential, has_pegin, has_issuance
) VALUES (
    %(txid)s, %(wtxid)s, %(hash)s, %(withash)s,
    %(block_hash)s, %(block_height)s, %(block_time)s, %(tx_index_in_block)s, %(confirmed)s,
    %(version)s, %(lock_time)s, %(size)s, %(vsize)s, %(weight)s, %(discount_vsize)s, %(discount_weight)s,
    %(vin_count)s, %(vout_count)s,
    %(fee_by_asset)s::jsonb, %(explicit_in_by_asset)s::jsonb, %(explicit_out_by_asset)s::jsonb,
    %(has_any_confidential)s, %(has_pegin)s, %(has_issuance)s
)
ON CONFLICT (txid) DO UPDATE SET
    wtxid = EXCLUDED.wtxid,
    hash = EXCLUDED.hash,
    withash = EXCLUDED.withash,
    block_hash = EXCLUDED.block_hash,
    block_height = EXCLUDED.block_height,
    block_time = EXCLUDED.block_time,
    tx_index_in_block = EXCLUDED.tx_index_in_block,
    confirmed = EXCLUDED.confirmed,
    version = EXCLUDED.version,
    lock_time = EXCLUDED.lock_time,
    size = EXCLUDED.size,
    vsize = EXCLUDED.vsize,
    weight = EXCLUDED.weight,
    discount_vsize = EXCLUDED.discount_vsize,
    discount_weight = EXCLUDED.discount_weight,
    vin_count = EXCLUDED.vin_count,
    vout_count = EXCLUDED.vout_count,
    fee_by_asset = EXCLUDED.fee_by_asset,
    explicit_in_by_asset = EXCLUDED.explicit_in_by_asset,
    explicit_out_by_asset = EXCLUDED.explicit_out_by_asset,
    has_any_confidential = EXCLUDED.has_any_confidential,
    has_pegin = EXCLUDED.has_pegin,
    has_issuance = EXCLUDED.has_issuance
