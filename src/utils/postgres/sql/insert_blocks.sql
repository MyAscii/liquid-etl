INSERT INTO blocks (
    hash, height, version, prev_block_hash, next_block_hash,
    merkle_root, time, median_time,
    tx_count, size, stripped_size, weight,
    signblock_solution_hex,
    txids
) VALUES (
    %(hash)s, %(height)s, %(version)s, %(prev_block_hash)s, %(next_block_hash)s,
    %(merkle_root)s, %(time)s, %(median_time)s,
    %(tx_count)s, %(size)s, %(stripped_size)s, %(weight)s,
    %(signblock_solution_hex)s,
    %(txids)s::jsonb
)
ON CONFLICT (hash) DO UPDATE SET
    height = EXCLUDED.height,
    version = EXCLUDED.version,
    prev_block_hash = EXCLUDED.prev_block_hash,
    next_block_hash = EXCLUDED.next_block_hash,
    merkle_root = EXCLUDED.merkle_root,
    time = EXCLUDED.time,
    median_time = EXCLUDED.median_time,
    tx_count = EXCLUDED.tx_count,
    size = EXCLUDED.size,
    stripped_size = EXCLUDED.stripped_size,
    weight = EXCLUDED.weight,
    signblock_solution_hex = EXCLUDED.signblock_solution_hex,
    txids = EXCLUDED.txids
