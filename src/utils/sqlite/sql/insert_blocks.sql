INSERT INTO blocks (
    hash, number, timestamp, median_time, confirmations,
    size, stripped_size, weight,
    version, version_hex, merkle_root, nonce, bits,
    previous_block_hash, next_block_hash,
    transaction_count,
    signblock_challenge, signblock_witness_asm, signblock_witness_hex
) VALUES (
    :hash, :number, :timestamp, :median_time, :confirmations,
    :size, :stripped_size, :weight,
    :version, :version_hex, :merkle_root, :nonce, :bits,
    :previous_block_hash, :next_block_hash,
    :transaction_count,
    :signblock_challenge, :signblock_witness_asm, :signblock_witness_hex
)
ON CONFLICT(hash) DO UPDATE SET
    number=excluded.number,
    timestamp=excluded.timestamp,
    median_time=excluded.median_time,
    confirmations=excluded.confirmations,
    size=excluded.size,
    stripped_size=excluded.stripped_size,
    weight=excluded.weight,
    version=excluded.version,
    version_hex=excluded.version_hex,
    merkle_root=excluded.merkle_root,
    nonce=excluded.nonce,
    bits=excluded.bits,
    previous_block_hash=excluded.previous_block_hash,
    next_block_hash=excluded.next_block_hash,
    transaction_count=excluded.transaction_count,
    signblock_challenge=excluded.signblock_challenge,
    signblock_witness_asm=excluded.signblock_witness_asm,
    signblock_witness_hex=excluded.signblock_witness_hex
