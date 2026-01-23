from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..amounts import to_satoshi
from .coercion import coerce_block_row, coerce_tx_rows
from .migrations import migrate_tables
from .schema import ensure_schema
from .sql_files import sql_text


class PostgresWriter:
    def __init__(self, dsn: str):
        self.dsn = dsn
        try:
            import psycopg
        except Exception as e:
            raise RuntimeError(
                "psycopg not installed; install with pip install -e .[postgres]"
            ) from e
        self.conn = psycopg.connect(dsn, autocommit=True)
        self._ensure_schema()

    def close(self) -> None:
        self.conn.close()

    def _ensure_schema(self) -> None:
        with self.conn.cursor() as cur:
            migrate_tables(cur)
            ensure_schema(cur)

    def get_max_block_height(self) -> Optional[int]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT MAX(height) FROM blocks")
            row = cur.fetchone()
            if row and row[0] is not None:
                return int(row[0])
            return None

    def write_bundle(
        self,
        block_row: Dict[str, Any],
        tx_rows: List[Dict[str, Any]],
        txin_rows: List[Dict[str, Any]],
        txout_rows: List[Dict[str, Any]],
    ) -> None:
        with self.conn.transaction():
            self.write_blocks([block_row])
            self.write_transactions(tx_rows)
            self.write_txins(txin_rows)
            self.write_txouts(txout_rows)

    def write_chunk(
        self,
        block_rows: List[Dict[str, Any]],
        tx_rows: List[Dict[str, Any]],
        txin_rows: List[Dict[str, Any]],
        txout_rows: List[Dict[str, Any]],
    ) -> None:
        with self.conn.transaction():
            self.write_blocks(block_rows)
            self.write_transactions(tx_rows)
            self.write_txins(txin_rows)
            self.write_txouts(txout_rows)

    def write_block(self, block: Dict[str, Any]) -> None:
        row = coerce_block_row(block)
        with self.conn.transaction():
            self.write_blocks([row])

    def write_transaction(self, tx: Dict[str, Any]) -> None:
        tx_row, txins, txouts = coerce_tx_rows(tx)
        with self.conn.transaction():
            self.write_transactions([tx_row])
            if txins:
                self.write_txins(txins)
            if txouts:
                self.write_txouts(txouts)

    def _coerce_block_row(self, block: Dict[str, Any]) -> Dict[str, Any]:
        return coerce_block_row(block)

    def _coerce_tx_rows(
        self, tx: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
        if "vin" in tx and "vout" in tx:
            raise ValueError(
                "write_transaction expects normalized transaction items; use ingest_range_to_postgres for raw blocks"
            )

        inputs = tx.get("inputs", []) or []
        outputs = tx.get("outputs", []) or []

        has_any_confidential = any(
            isinstance(o, dict) and o.get("confidential_value") for o in outputs
        )
        has_pegin = any(isinstance(i, dict) and i.get("input_type") == "pegin" for i in inputs)
        has_issuance = any(
            isinstance(i, dict) and i.get("input_type") == "issuance" for i in inputs
        )

        fee_by_asset = None
        node_fee = tx.get("node_fee")
        if isinstance(node_fee, dict):
            fee_by_asset_map: Dict[str, int] = {}
            for asset, amount in node_fee.items():
                sat = to_satoshi(amount)
                if sat is None:
                    continue
                fee_by_asset_map[str(asset)] = fee_by_asset_map.get(str(asset), 0) + int(sat)
            fee_by_asset = fee_by_asset_map or None

        explicit_in_by_asset = None
        explicit_in_map: Dict[str, int] = {}
        for vin in inputs:
            if not isinstance(vin, dict):
                continue
            asset = vin.get("asset")
            value = vin.get("value")
            if asset is None or value is None:
                continue
            sat = to_satoshi(value)
            if sat is None:
                continue
            explicit_in_map[str(asset)] = explicit_in_map.get(str(asset), 0) + int(sat)
        explicit_in_by_asset = explicit_in_map or None

        explicit_out_by_asset = None
        explicit_out_map: Dict[str, int] = {}
        for vout in outputs:
            if not isinstance(vout, dict):
                continue
            asset = vout.get("asset")
            value = vout.get("value")
            if asset is None or value is None:
                continue
            sat = to_satoshi(value)
            if sat is None:
                continue
            explicit_out_map[str(asset)] = explicit_out_map.get(str(asset), 0) + int(sat)
        explicit_out_by_asset = explicit_out_map or None

        tx_row: Dict[str, Any] = {
            "txid": tx.get("txid"),
            "wtxid": tx.get("wtxid"),
            "hash": tx.get("hash"),
            "withash": tx.get("withash"),
            "block_hash": tx.get("block_hash"),
            "block_height": tx.get("block_number"),
            "block_time": tx.get("block_timestamp"),
            "tx_index_in_block": tx.get("index", 0),
            "confirmed": True,
            "version": tx.get("version"),
            "lock_time": tx.get("lock_time"),
            "size": tx.get("size"),
            "vsize": tx.get("virtual_size"),
            "weight": tx.get("weight"),
            "discount_vsize": tx.get("discount_virtual_size"),
            "discount_weight": tx.get("discount_weight"),
            "vin_count": (
                tx.get("input_count") if tx.get("input_count") is not None else len(inputs)
            ),
            "vout_count": (
                tx.get("output_count") if tx.get("output_count") is not None else len(outputs)
            ),
            "fee_by_asset": fee_by_asset,
            "explicit_in_by_asset": explicit_in_by_asset,
            "explicit_out_by_asset": explicit_out_by_asset,
            "has_any_confidential": bool(has_any_confidential),
            "has_pegin": bool(has_pegin),
            "has_issuance": bool(has_issuance),
        }

        txins: List[Dict[str, Any]] = []
        for vin_index, vin in enumerate(inputs):
            if not isinstance(vin, dict):
                continue
            addr = None
            addrs = vin.get("addresses")
            if isinstance(addrs, list) and addrs:
                addr = addrs[0]

            is_pegin = bool(vin.get("input_type") == "pegin" or vin.get("is_pegin"))
            issuance = vin.get("issuance") if isinstance(vin.get("issuance"), dict) else None

            issuance_asset_blinding_nonce = None
            issuance_asset_entropy = None
            issuance_amount_sat = None
            issuance_inflation_keys_sat = None
            if issuance:
                issuance_asset_blinding_nonce = issuance.get("assetBlindingNonce") or issuance.get(
                    "assetblindingnonce"
                )
                issuance_asset_entropy = issuance.get("assetEntropy") or issuance.get(
                    "assetentropy"
                )
                issuance_amount_sat = (
                    to_satoshi(issuance.get("assetamount"))
                    if issuance.get("assetamount") is not None
                    else None
                )
                issuance_inflation_keys_sat = (
                    to_satoshi(issuance.get("tokenamount"))
                    if issuance.get("tokenamount") is not None
                    else None
                )

            txins.append(
                {
                    "txid": tx.get("txid"),
                    "vin": vin_index,
                    "prev_txid": vin.get("txid"),
                    "prev_vout": vin.get("vout"),
                    "sequence": vin.get("sequence"),
                    "is_coinbase": bool(vin.get("is_coinbase")),
                    "scriptsig_hex": vin.get("scriptsig_hex") or vin.get("coinbase_hex"),
                    "scriptsig_asm": vin.get("scriptsig_asm"),
                    "txinwitness": vin.get("witness"),
                    "pegin_witness": vin.get("pegin_witness"),
                    "is_pegin": is_pegin,
                    "has_issuance": vin.get("input_type") == "issuance",
                    "issuance_asset_blinding_nonce": issuance_asset_blinding_nonce,
                    "issuance_asset_entropy": issuance_asset_entropy,
                    "issuance_amount": issuance_amount_sat,
                    "issuance_inflation_keys": issuance_inflation_keys_sat,
                    "prevout_scriptpubkey_hex": vin.get("scriptpubkey_hex"),
                    "prevout_script_type": vin.get("type"),
                    "prevout_address": addr,
                }
            )

        txouts: List[Dict[str, Any]] = []
        for vout in outputs:
            if not isinstance(vout, dict):
                continue
            addr = None
            addrs = vout.get("addresses")
            if isinstance(addrs, list) and addrs:
                addr = addrs[0]

            value_sat = to_satoshi(vout.get("value")) if vout.get("value") is not None else None

            txouts.append(
                {
                    "txid": tx.get("txid"),
                    "vout": vout.get("n"),
                    "asset_id": vout.get("asset"),
                    "asset_commitment": vout.get("asset_commitment"),
                    "value_sat": value_sat,
                    "value_commitment": vout.get("confidential_value"),
                    "scriptpubkey_hex": vout.get("scriptpubkey_hex"),
                    "scriptpubkey_asm": vout.get("scriptpubkey_asm"),
                    "script_type": vout.get("script_type"),
                    "address": addr,
                    "is_op_return": bool(vout.get("op_return_data_hex")),
                    "op_return_data_hex": vout.get("op_return_data_hex"),
                    "is_fee": vout.get("type") == "fee",
                    "surjection_proof": vout.get("surjection_proof"),
                }
            )

        return tx_row, txins, txouts

    def write_blocks(self, blocks: Iterable[Dict[str, Any]]) -> None:
        payloads = []
        for b in blocks:
            payloads.append(
                {
                    **b,
                    "txids": (
                        json.dumps(b.get("txids"), default=str)
                        if b.get("txids") is not None
                        else None
                    ),
                }
            )
        if not payloads:
            return
        with self.conn.cursor() as cur:
            cur.executemany(
                sql_text("insert_blocks.sql"),
                payloads,
            )

    def write_transactions(self, txs: Iterable[Dict[str, Any]]) -> None:
        payloads = []
        for t in txs:
            payloads.append(
                {
                    **t,
                    "fee_by_asset": (
                        json.dumps(t.get("fee_by_asset"), default=str)
                        if t.get("fee_by_asset") is not None
                        else None
                    ),
                    "explicit_in_by_asset": (
                        json.dumps(t.get("explicit_in_by_asset"), default=str)
                        if t.get("explicit_in_by_asset") is not None
                        else None
                    ),
                    "explicit_out_by_asset": (
                        json.dumps(t.get("explicit_out_by_asset"), default=str)
                        if t.get("explicit_out_by_asset") is not None
                        else None
                    ),
                }
            )
        if not payloads:
            return
        with self.conn.cursor() as cur:
            cur.executemany(
                sql_text("insert_transactions.sql"),
                payloads,
            )

    def write_txins(self, txins: Iterable[Dict[str, Any]]) -> None:
        payloads = []
        for i in txins:
            payloads.append(
                {
                    **i,
                    "txinwitness": (
                        json.dumps(i.get("txinwitness"), default=str)
                        if i.get("txinwitness") is not None
                        else None
                    ),
                    "pegin_witness": (
                        json.dumps(i.get("pegin_witness"), default=str)
                        if i.get("pegin_witness") is not None
                        else None
                    ),
                }
            )
        if not payloads:
            return
        with self.conn.cursor() as cur:
            cur.executemany(
                sql_text("insert_txins.sql"),
                payloads,
            )

    def write_txouts(self, txouts: Iterable[Dict[str, Any]]) -> None:
        payloads = [dict(o) for o in txouts]
        if not payloads:
            return
        with self.conn.cursor() as cur:
            cur.executemany(
                sql_text("insert_txouts.sql"),
                payloads,
            )
