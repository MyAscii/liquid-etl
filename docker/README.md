# Containerized stack: node + parser + Postgres

`docker compose` brings up three (or four) services wired together:

- **elements** — `elementsd` from the official Blockstream release, configured with
  `txindex=1` and `validatepegin=0`, on either the built-in regtest chain or Liquid
  mainnet (`liquidv1`).
- **postgres** — the target database (Postgres 16), reachable on host port `5433`.
- **etl** — the `liquid-etl` parser running `python -m liquidetl.pipeline`: it waits
  for the node, batch-backfills history up to the tip, then streams the head continuously.
- **miner** (regtest profile only) — pre-mines an initial history, then produces a block
  every few seconds so there is live data to ingest.

## Quick start (regtest, self-contained)

```sh
cp .env.example .env          # optional; defaults already target regtest
docker compose --profile regtest up --build
```

Within a minute the miner pre-mines 200 blocks, the ETL backfills them into Postgres,
and then both keep going. Inspect the data:

```sh
docker compose exec postgres psql -U liquidetl -d liquidetl -c "SELECT COUNT(*) FROM blocks;"
# or from the host, since Postgres is published on 5433:
psql postgresql://liquidetl:liquidetl@localhost:5433/liquidetl -c "SELECT MAX(height) FROM blocks;"
```

## Liquid mainnet (real history)

```sh
CHAIN=liquidv1 LIQUID_WAIT_FOR_SYNC=1 docker compose up --build
```

Do **not** use the `regtest` profile (no miner). The node performs a full initial
block download first (large, hours+); with `LIQUID_WAIT_FOR_SYNC=1` the ETL waits for
IBD to finish, then backfills the full chain and follows the head. `validatepegin=0`
means no Bitcoin node is required.

## How the parser runs

`python -m liquidetl.pipeline` is env-driven (`LIQUID_*`, see [.env.example](../.env.example)):

1. wait for the node RPC (`getblockcount`);
2. optionally wait for initial sync (`LIQUID_WAIT_FOR_SYNC=1`);
3. **backfill** `ingest_range_to_postgres` from `LIQUID_START_BLOCK` (or DB max height + 1
   on restart) to the current tip, tuned for speed (`--fast-local`, prefetch, conflict
   `ignore`);
4. **stream** to follow the head, resuming from the DB max height.

`LIQUID_PIPELINE_MODE` selects `backfill_then_stream` (default), `backfill`, or `stream`.
The pipeline is idempotent and crash-safe: on restart it resumes from the DB.

## Updating the node version

Set `ELEMENTS_VERSION` to a current release from
<https://github.com/ElementsProject/elements/releases>. The build verifies the download
against Blockstream's published `SHA256SUMS`; for a strong pin, also set `ELEMENTS_SHA256`
to the known-good hash of the tarball for your architecture.

## Notes

- `rpcallowip=0.0.0.0/0` is scoped to the compose network. Do not expose the node RPC
  port publicly; drop `ELEMENTS_HOST_PORT` to keep it internal.
- Data persists in the `liquidetl_pg` and `elements_data` named volumes. `docker compose
  down -v` wipes them.
