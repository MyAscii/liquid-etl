"""Schema hints for NDJSON outputs.

These are best-effort keys populated by normalization.
"""

BLOCK_SCHEMA_KEYS = [
    "hash",
    "size",
    "stripped_size",
    "weight",
    "number",
    "version",
    "merkle_root",
    "timestamp",
    "nonce",
    "bits",
    "transaction_count",
]

TRANSACTION_SCHEMA_KEYS = [
    "hash",
    "size",
    "virtual_size",
    "version",
    "lock_time",
    "block_number",
    "block_hash",
    "block_timestamp",
    "is_coinbase",
    "index",
    "inputs",
    "outputs",
    "input_count",
    "output_count",
    "input_value",
    "output_value",
    "fee",
]