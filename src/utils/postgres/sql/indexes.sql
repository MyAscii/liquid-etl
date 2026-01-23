CREATE INDEX IF NOT EXISTS transactions_block_height_idx ON transactions (block_height);
CREATE INDEX IF NOT EXISTS txins_prev_outpoint_idx ON txins (prev_txid, prev_vout);
CREATE INDEX IF NOT EXISTS txouts_asset_id_idx ON txouts (asset_id);
