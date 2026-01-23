from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..rpc import LiquidRpc
from .normalize_block import normalize_block
from .normalize_tx import normalize_address_info, normalize_tx
from .range import get_block_range_for_date as _get_block_range_for_date


@dataclass
class BlockWithTxs:
    block: Dict[str, Any]
    transactions: List[Dict[str, Any]]


class LiquidService:
    """High-level service to fetch and normalize blocks and transactions."""

    def __init__(self, rpc: LiquidRpc):
        self.rpc = rpc

    # ---- Public API ----
    def get_block_by_number(self, height: int) -> BlockWithTxs:
        h = self.rpc.getblockhash(height)
        b = self.rpc.getblock(h, verbosity=3)
        block_item = self._normalize_block(b)
        tx_items = [
            self._normalize_tx(t, block_item, tx_index=i) for i, t in enumerate(b.get("tx", []))
        ]
        return BlockWithTxs(block=block_item, transactions=tx_items)

    def get_blocks_by_numbers(self, heights: List[int]) -> List[BlockWithTxs]:
        if not heights:
            return []
        hashes = self.rpc.batch_call([("getblockhash", [h]) for h in heights])
        blocks = self.rpc.batch_call([("getblock", [block_hash, 3]) for block_hash in hashes])
        bundles: List[BlockWithTxs] = []
        for b in blocks:
            block_item = self._normalize_block(b)
            tx_items = [
                self._normalize_tx(t, block_item, tx_index=i) for i, t in enumerate(b.get("tx", []))
            ]
            bundles.append(BlockWithTxs(block=block_item, transactions=tx_items))
        return bundles

    def get_head_height(self) -> int:
        return self.rpc.getblockcount()

    def get_block_range_for_date(
        self, date_str: str, start_hour: int = 0, end_hour: int = 24
    ) -> Tuple[int, int]:
        head = self.get_head_height()
        return _get_block_range_for_date(
            get_block_timestamp=lambda h: self.get_block_by_number(h).block["timestamp"],
            head_height=head,
            date_str=date_str,
            start_hour=start_hour,
            end_hour=end_hour,
        )

    # ---- Normalization helpers ----
    def _normalize_block(self, b: Dict[str, Any]) -> Dict[str, Any]:
        return normalize_block(b)

    def _normalize_address_info(
        self, spk: Dict[str, Any]
    ) -> Tuple[Optional[List[str]], Optional[int]]:
        return normalize_address_info(spk)

    def _normalize_tx(
        self, t: Dict[str, Any], block_item: Dict[str, Any], tx_index: Optional[int] = None
    ) -> Dict[str, Any]:
        return normalize_tx(self.rpc, t, block_item, tx_index)
        is_coinbase = any("coinbase" in vin for vin in t.get("vin", []))
        inputs = []
        input_value_total: Optional[Decimal] = None
        outputs = []
        output_value_total: Optional[Decimal] = Decimal(0)
        confidential_present = False

        # Normalize inputs
        for vin in t.get("vin", []):
            itype = None
            if vin.get("is_pegin"):
                itype = "pegin"
            if "issuance" in vin or "assetissuance" in vin:
                itype = "issuance"
            scriptsig = vin.get("scriptSig") if isinstance(vin.get("scriptSig"), dict) else {}
            is_coinbase_input = "coinbase" in vin
            scriptsig_hex = scriptsig.get("hex")
            scriptsig_asm = scriptsig.get("asm")
            coinbase_hex = vin.get("coinbase") if is_coinbase_input else None
            if is_coinbase_input and not scriptsig_hex:
                scriptsig_hex = coinbase_hex
            if is_coinbase_input and scriptsig_hex:
                scriptsig_asm = disassemble_script(scriptsig_hex) or scriptsig_asm
            elif scriptsig_hex and not scriptsig_asm:
                try:
                    scriptsig_asm = self.rpc.decodescript(scriptsig_hex).get("asm")
                except Exception:
                    scriptsig_asm = disassemble_script(scriptsig_hex)

            witness = vin.get("txinwitness")
            if witness is None:
                witness = vin.get("witness")

            issuance = vin.get("issuance") if isinstance(vin.get("issuance"), dict) else None
            if issuance is None and isinstance(vin.get("assetissuance"), dict):
                issuance = vin.get("assetissuance")

            # Basic fields
            item: Dict[str, Any] = {
                "txid": vin.get("txid"),
                "vout": vin.get("vout"),
                "sequence": vin.get("sequence"),
                "input_type": itype,
                "is_coinbase": is_coinbase_input,
                "scriptsig_asm": scriptsig_asm,
                "scriptsig_hex": scriptsig_hex,
                "coinbase_hex": coinbase_hex,
                "witness": witness,
                "is_pegin": bool(vin.get("is_pegin")),
                "pegin_witness": vin.get("pegin_witness"),
                "pegin_value": vin.get("pegin_value"),
                "pegin_asset": vin.get("pegin_asset"),
                "pegin_genesis_hash": vin.get("pegin_genesis_hash"),
                "pegin_claim_script": vin.get("pegin_claim_script"),
                "pegin_tx": vin.get("pegin_tx"),
                "pegin_txout_proof": vin.get("pegin_txout_proof"),
                "pegin_blockhash": vin.get("pegin_blockhash"),
                "issuance": issuance,
            }
            prevout = vin.get("prevout") if isinstance(vin.get("prevout"), dict) else None
            if prevout:
                spk = (
                    prevout.get("scriptPubKey", {})
                    if isinstance(prevout.get("scriptPubKey"), dict)
                    else {}
                )
                addrs, req_sigs = self._normalize_address_info(spk)
                item["addresses"] = addrs
                item["required_signatures"] = req_sigs
                item["type"] = spk.get("type")
                item["value"] = prevout.get("value")
                item["asset"] = prevout.get("asset")
                item["scriptpubkey_asm"] = spk.get("asm")
                item["scriptpubkey_hex"] = spk.get("hex")
            # Amounts are not present on inputs here unless enriched
            inputs.append(item)

        # Normalize outputs
        for vout in t.get("vout", []):
            spk = vout.get("scriptPubKey", {})
            addrs, req_sigs = self._normalize_address_info(spk)
            # Elements includes asset ids
            asset = vout.get("asset") or (spk.get("asset") if isinstance(spk, dict) else None)
            # Confidential values
            value = vout.get("value")
            vcommit = vout.get("valuecommitment")
            acommit = vout.get("assetcommitment")
            is_confidential = (vcommit or acommit) and value is None
            # Pegout detection: common flags across Elements variants
            is_pegout = bool(
                vout.get("is_pegout")
                or vout.get("pegout")
                or vout.get("pegout_chain")
                or (isinstance(spk, dict) and (spk.get("pegout") or spk.get("type") == "pegout"))
            )
            is_fee = bool(
                vout.get("is_fee") or (isinstance(spk, dict) and spk.get("type") == "fee")
            )
            # Assign type with pegout priority, then confidential
            otype = (
                "pegout"
                if is_pegout
                else ("fee" if is_fee else ("confidential" if is_confidential else None))
            )
            if is_confidential:
                confidential_present = True
            else:
                try:
                    output_value_total = (output_value_total or Decimal(0)) + (
                        Decimal(str(value)) if value is not None else Decimal(0)
                    )
                except Exception:
                    pass

            scriptpubkey_hex = spk.get("hex") if isinstance(spk, dict) else None
            scriptpubkey_asm = spk.get("asm") if isinstance(spk, dict) else None
            op_return_data_hex = extract_op_return_data_hex(scriptpubkey_hex)
            pegout = vout.get("pegout") if isinstance(vout.get("pegout"), dict) else None
            outputs.append(
                {
                    "value": value,
                    "confidential_value": vcommit,
                    "asset_commitment": acommit,
                    "asset": asset,
                    "type": otype,
                    "n": vout.get("n"),
                    "addresses": addrs,
                    "required_signatures": req_sigs,
                    "scriptpubkey_asm": scriptpubkey_asm,
                    "scriptpubkey_hex": scriptpubkey_hex,
                    "script_type": spk.get("type") if isinstance(spk, dict) else None,
                    "op_return_data_hex": op_return_data_hex,
                    "nonce": vout.get("nonce"),
                    "surjection_proof": vout.get("surjectionproof"),
                    "rangeproof": vout.get("rangeproof"),
                    "pegout_chain_genesis_hash": pegout.get("genesis_hash") if pegout else None,
                    "pegout_btc_scriptpubkey_hex": pegout.get("scriptpubkey") if pegout else None,
                    "pegout_value": pegout.get("value") if pegout else None,
                    "pegout_asset": pegout.get("asset") if pegout else None,
                    "pegout_extra_data_hex": pegout.get("extra_data") if pegout else None,
                }
            )

        # Totals and fee: only computable if non-confidential
        fee = None
        if not confidential_present:
            try:
                if input_value_total is not None and output_value_total is not None:
                    fee = str(
                        (input_value_total or Decimal(0)) - (output_value_total or Decimal(0))
                    )
            except Exception:
                fee = None

        return {
            "hash": t.get("txid") or t.get("hash"),
            "txid": t.get("txid"),
            "wtxid": t.get("wtxid"),
            "withash": t.get("withash"),
            "tx_hex": t.get("hex"),
            "size": t.get("size"),
            "virtual_size": t.get("vsize"),
            "discount_virtual_size": t.get("discountvsize"),
            "weight": t.get("weight"),
            "discount_weight": t.get("discountweight"),
            "sigops": t.get("sigops"),
            "version": t.get("version"),
            "lock_time": t.get("locktime"),
            "block_number": block_item.get("number"),
            "block_hash": block_item.get("hash"),
            "block_timestamp": block_item.get("timestamp"),
            "is_coinbase": is_coinbase,
            "index": tx_index,
            "inputs": inputs,
            "outputs": outputs,
            "input_count": len(inputs),
            "output_count": len(outputs),
            "input_value": str(input_value_total) if input_value_total is not None else None,
            "output_value": str(output_value_total) if output_value_total is not None else None,
            "fee": fee,
            "node_fee": t.get("fee"),
        }
