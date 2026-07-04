#!/usr/bin/env bash
# Generate elements.conf from env, then run elementsd with the correct config for
# either the built-in regtest (elementsregtest) or Liquid mainnet (liquidv1).
set -euo pipefail

DATADIR="${ELEMENTS_DATADIR:-/data}"
CHAIN="${CHAIN:-elementsregtest}"
RPC_USER="${RPC_USER:-liquid}"
RPC_PASSWORD="${RPC_PASSWORD:-liquid}"
RPC_PORT="${RPC_PORT:-7041}"

mkdir -p "${DATADIR}"
CONF="${DATADIR}/elements.conf"

# Network-bound settings (rpcport/rpcbind/listen) must live under the [chain] section;
# txindex is required for input enrichment, validatepegin=0 avoids needing a Bitcoin node.
cat > "${CONF}" <<EOF
server=1
txindex=1
validatepegin=0
rpcuser=${RPC_USER}
rpcpassword=${RPC_PASSWORD}
fallbackfee=0.00000100

[${CHAIN}]
listen=1
rpcbind=0.0.0.0
rpcallowip=0.0.0.0/0
rpcport=${RPC_PORT}
EOF

echo "elements: chain=${CHAIN} datadir=${DATADIR} rpcport=${RPC_PORT}"
exec elementsd -chain="${CHAIN}" -datadir="${DATADIR}" -conf="${CONF}" "$@"
