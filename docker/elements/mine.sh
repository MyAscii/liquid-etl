#!/usr/bin/env bash
# Regtest block generator: creates a wallet, pre-mines an initial history so the ETL
# has a range to backfill, then mines one block every MINE_INTERVAL seconds.
# Only meaningful for CHAIN=elementsregtest (enabled via the compose "regtest" profile).
set -euo pipefail

CHAIN="${CHAIN:-elementsregtest}"
RPC_CONNECT="${RPC_CONNECT:-elements}"
RPC_PORT="${RPC_PORT:-7041}"
RPC_USER="${RPC_USER:-liquid}"
RPC_PASSWORD="${RPC_PASSWORD:-liquid}"
INITIAL_BLOCKS="${INITIAL_BLOCKS:-200}"
INTERVAL="${MINE_INTERVAL:-5}"
WALLET="${MINE_WALLET:-miner}"

cli() {
    elements-cli -chain="${CHAIN}" \
        -rpcconnect="${RPC_CONNECT}" -rpcport="${RPC_PORT}" \
        -rpcuser="${RPC_USER}" -rpcpassword="${RPC_PASSWORD}" "$@"
}

echo "miner: waiting for node ${RPC_CONNECT}:${RPC_PORT}..."
until cli getblockchaininfo >/dev/null 2>&1; do
    sleep 2
done

# Create or load the mining wallet (idempotent across restarts).
cli createwallet "${WALLET}" >/dev/null 2>&1 \
    || cli loadwallet "${WALLET}" >/dev/null 2>&1 \
    || true
ADDR="$(cli -rpcwallet="${WALLET}" getnewaddress)"

CUR="$(cli getblockcount)"
if [ "${CUR}" -lt "${INITIAL_BLOCKS}" ]; then
    NEED=$((INITIAL_BLOCKS - CUR))
    echo "miner: pre-mining ${NEED} blocks to reach ${INITIAL_BLOCKS}"
    cli -rpcwallet="${WALLET}" generatetoaddress "${NEED}" "${ADDR}" >/dev/null
fi

echo "miner: steady state, one block every ${INTERVAL}s"
while true; do
    cli -rpcwallet="${WALLET}" generatetoaddress 1 "${ADDR}" >/dev/null 2>&1 \
        || echo "miner: generate failed, retrying"
    sleep "${INTERVAL}"
done
