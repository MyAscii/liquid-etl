# Liquid ETL

Liquid ETL is an Extract-Transform-Load and streaming toolkit for the Liquid Network (Elements), modeled after bitcoin-etl. It exports blocks and transactions, enriches transactions by resolving inputs, partitions outputs for analytics, and optionally streams data to console or Google Pub/Sub.

## Installation

- Stable: `pip install -e .`
- Latest dev with streaming extras: `pip install -e .[streaming]`
- Postgres ingestion extras: `pip install -e .[postgres]`

Requires a full Liquid/Elements node JSON-RPC endpoint (often `elementsd`), with `txindex=1` for input enrichment.

## Configuration

Most connection settings can be moved out of CLI flags into a JSON config file.

- Pass a config explicitly: `liquidetl --config configs/example.local.json <command> ...`
- Or drop a default config at `./liquidetl.config.json` or `~/.config/liquidetl/config.json`
- Optional profiles:
  - `liquidetl --config config.json --profile prod ...`
  - Or `LIQUID_ETL_CONFIG=config.json` and `LIQUID_ETL_PROFILE=prod`

CLI flags still work and override config values (for one-off changes).

## Key Commands

- `liquidetl export_blocks_and_transactions` — exports blocks and transactions for a block range to `blocks.json` and `transactions.json`.
- `liquidetl enrich_transactions` — fills transaction input details by looking up spent outputs; requires `txindex=1`.
- `liquidetl get_block_range_for_date` — returns the start and end block covering a specific UTC date.
- `liquidetl export_all` — partitions a date or block range into batches and writes Hive-style directories under `output/`, optionally enriching transactions.
- `liquidetl filter_items` — filters NDJSON or CSV outputs using a JSON predicate spec (e.g., by date or other fields).
- `liquidetl stream` — continuously streams blocks and transactions to console or Pub/Sub.

## Streaming

- Streams blocks and transactions:
  - To console by default.
  - To Google Pub/Sub when `--output projects/your-project/topics/crypto_liquid` is provided (publishes to `.blocks` and `.transactions` subtopics).
  - To Postgres when `--output postgresql://user:pass@host:5432/dbname` is provided.
- Supports lagging behind head (`--lag`), batch sizing, worker tuning, and optional enrichment.

## Local Postgres Ingestion

- Start a local Postgres (optional helper):
  ```sh
  docker compose up -d postgres
  ```
- Directly ingest a block range from RPC into Postgres:
  ```sh
  liquidetl --config configs/example.postgres.json ingest_range_to_postgres -s 0 -e 1000
  ```
- Load previously exported NDJSON into Postgres:
  ```sh
  liquidetl --config configs/example.postgres.json load_ndjson_to_postgres --blocks-input blocks.json --transactions-input transactions.json
  ```

## Full Stack (Docker)

A complete stack (elementsd node + parser + Postgres) is defined in `docker-compose.yml`. It backfills history, then streams the head into Postgres.

```sh
# Self-contained regtest (mines its own history):
docker compose --profile regtest up --build

# Liquid mainnet (real history, long initial sync):
CHAIN=liquidv1 LIQUID_WAIT_FOR_SYNC=1 docker compose up --build
```

See [docker/README.md](docker/README.md) for details and [.env.example](.env.example) for configuration. The parser runs `python -m liquidetl.pipeline`, an env-driven backfill-then-stream supervisor.

## Outputs and Schema

The ETL writes newline-delimited JSON (NDJSON). Below is the schema produced by the normalization layer.

### blocks.json

Field | Type
----- | ----
`hash` | hex_string
`size` | bigint
`stripped_size` | bigint
`weight` | bigint
`number` | bigint
`version` | bigint
`merkle_root` | hex_string
`timestamp` | bigint
`nonce` | bigint|null
`bits` | hex_string|null
`transaction_count` | bigint

### transactions.json

Field | Type
----- | ----
`hash` | hex_string
`size` | bigint
`virtual_size` | bigint
`version` | bigint
`lock_time` | bigint
`block_number` | bigint
`block_hash` | hex_string
`block_timestamp` | bigint
`is_coinbase` | boolean
`index` | bigint
`inputs` | []`transaction_input`
`outputs` | []`transaction_output`
`input_count` | bigint
`output_count` | bigint
`input_value` | decimal_string|null
`output_value` | decimal_string|null
`fee` | decimal_string|null

### transaction_input

Field | Type
----- | ----
`txid` | hex_string|null
`vout` | bigint|null
`sequence` | bigint
`type` | string|null  ("pegin", "issuance", or null)

### transaction_output

Field | Type
----- | ----
`n` | bigint  (output index)
`value` | decimal|null
`confidential_value` | string|null
`asset` | hex_string|null
`type` | string|null  ("confidential", "pegout", or null)
`addresses` | []string|null
`required_signatures` | bigint|null

Notes:
- Confidential outputs include `valuecommitment`/`assetcommitment` on-chain; when present, `value` is hidden and we mark `type="confidential"` and surface `confidential_value`.
- Peg-in and peg-out flags are normalized: inputs may have `type="pegin"` or `type="issuance"`; outputs may have `type="pegout"`.
- Fees and totals are only computed when all outputs are non-confidential.

## How It Works

- RPC client (`LiquidRpc`) batches JSON-RPC requests to the node and decodes with `parse_float=decimal.Decimal` to avoid precision loss.
- Core service (`LiquidService`) fetches block hashes and blocks, normalizes transactions (including confidential fields and asset IDs), and enriches inputs by resolving spent outputs.
- Jobs:
  - `ExportBlocksJob` iterates over block ranges and exports block and transaction items.
  - `EnrichTransactionsJob` resolves input details from previous outputs.
  - `export_all` orchestrates partitioning by date or block ranges and runs export jobs, writing Hive-style partitioned output.
- Streaming adapter (`LiquidStreamerAdapter`) collects blocks and transactions in batches, optionally enriches transactions, calculates `item_id`s, and exports to console or Pub/Sub.
- Utilities for filtering, iterating, batching, logging, and thread-local RPC proxies.

## Typical Examples

- Export a block range:
  ```sh
  liquidetl --config configs/example.local.json export_blocks_and_transactions -s 0 -e 500000 --blocks-output blocks.json --transactions-output transactions.json
  ```
- Enrich transactions:
  ```sh
  liquidetl --config configs/example.local.json enrich_transactions --transactions-input transactions.json --transactions-output enriched_transactions.json
  ```
- Get range for date:
  ```sh
  liquidetl --config configs/example.local.json get_block_range_for_date --date 2019-03-01
  ```
- Stream with lag and Pub/Sub:
  ```sh
  liquidetl --config configs/example.pubsub.json stream --start-block 500000
  ```

## Notes and Caveats

- Block times are not strictly monotonic; date-based ranges can include blocks slightly outside the date window; use `filter_items` to post-filter.
- Confidential amounts may hide values; the ETL records commitments and may not compute fees or totals for such transactions.
- For older RPCs or different Elements forks, some fields may be missing; the ETL attempts best-effort normalization.

## Testing

- Dev/test extras: `pip install -e .[dev]` then `pytest -vv`.
- Lint/format gate (also enforced in CI): `ruff check src tests tune_ingest.py`, `black --check src tests`, `isort --check-only src tests`.
- Install the pre-commit hook so the gate runs on every commit: `pre-commit install`.
- Optional env vars to point tests at nodes (integration/e2e are opt-in):
  - `LIQUID_RPC_URI`
  - `LIQUID_DSN`
  - `LIQUID_E2E=1`
