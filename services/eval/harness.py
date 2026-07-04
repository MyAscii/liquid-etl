"""Deterministic normalizer eval for liquid-etl.

No LLM, no node: golden getblock(verbosity=3) fixtures are pushed through both
normalizer paths (the bulk `utils.normalization` path used by ingest, and the
`service` path used by streaming/export), and money-critical output fields are
scored field-by-field. The pass threshold is 100% on the critical fields, so a
regression on satoshi conversion, fee computation, genesis height, peg-in
classification, OP_RETURN detection, or confidential handling fails the eval.

Run:  python services/eval/run_eval.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Tuple

from liquidetl.service import LiquidService
from liquidetl.utils.normalization.block import normalize_block as bulk_normalize_block
from liquidetl.utils.normalization.tx import normalize_tx as bulk_normalize_tx
from liquidetl.utils.postgres.coercion import coerce_block_row, coerce_tx_rows

NETWORK = "liquidv1"


@dataclass
class Case:
    name: str
    block: Dict[str, Any]
    # Each check: (label, callable(ctx) -> actual, expected, is_critical)
    checks: List[Tuple[str, Callable[[Dict[str, Any]], Any], Any, bool]] = field(
        default_factory=list
    )


class _StubRpc:
    def __init__(self, block: Dict[str, Any]):
        self._block = block

    def getblockhash(self, height: int) -> str:
        return self._block["hash"]

    def getblock(self, block_hash: str, verbosity: int = 3) -> Dict[str, Any]:
        return self._block

    def getblockcount(self) -> int:
        return int(self._block.get("height", 0))

    def decodescript(self, script_hex: str) -> Dict[str, Any]:
        return {"asm": ""}


def _context(block: Dict[str, Any]) -> Dict[str, Any]:
    """Run both normalizer paths once and expose their outputs for checks."""
    # Bulk path (ingest_range_to_postgres).
    block_row = bulk_normalize_block(block, network=NETWORK)
    bulk_txs = []
    for idx, raw_tx in enumerate(block.get("tx", []) or []):
        tx_row, txins, txouts = bulk_normalize_tx(raw_tx, block_row, tx_index_in_block=idx)
        bulk_txs.append({"tx_row": tx_row, "txins": txins, "txouts": txouts})

    # Service/streaming path, then the Postgres coercion applied to its output.
    svc = LiquidService(_StubRpc(block))
    bundle = svc.get_block_by_number(int(block.get("height", 0)))
    coerced = [coerce_tx_rows(t) for t in bundle.transactions]

    return {
        "block": block,
        "bulk_block_row": block_row,
        "bulk": bulk_txs,
        "service_block": bundle.block,
        "service_txs": bundle.transactions,
        "coerced": coerced,  # list of (tx_row, txins, txouts)
        "coerced_block": coerce_block_row(bundle.block),
    }


@dataclass
class Result:
    case: str
    label: str
    expected: Any
    actual: Any
    ok: bool
    critical: bool


def run_case(case: Case) -> List[Result]:
    ctx = _context(case.block)
    out: List[Result] = []
    for label, getter, expected, critical in case.checks:
        try:
            actual = getter(ctx)
            ok = actual == expected
        except Exception as e:  # a crash is a failed check, never a crashed eval
            actual = f"EXC:{e!r}"
            ok = False
        out.append(Result(case.name, label, expected, actual, ok, critical))
    return out


def run_suite(cases: List[Case]) -> Tuple[List[Result], Dict[str, Any]]:
    results: List[Result] = []
    for c in cases:
        results.extend(run_case(c))
    total = len(results)
    passed = sum(1 for r in results if r.ok)
    crit = [r for r in results if r.critical]
    crit_passed = sum(1 for r in crit if r.ok)
    summary = {
        "total": total,
        "passed": passed,
        "score": (passed / total) if total else 1.0,
        "critical_total": len(crit),
        "critical_passed": crit_passed,
        "critical_score": (crit_passed / len(crit)) if crit else 1.0,
        "passed_gate": crit_passed == len(crit),
    }
    return results, summary


# ---------------------------------------------------------------------------
# Golden fixtures. Shapes mirror elementsd getblock(..., verbosity=3).
# ---------------------------------------------------------------------------


def _c(label, getter, expected, critical=True):
    return (label, getter, expected, critical)


GENESIS_COINBASE = Case(
    name="genesis_coinbase_op_return",
    block={
        "hash": "genesis",
        "height": 0,
        "time": 1_296_688_602,
        "version": 1,
        "tx": [
            {
                "txid": "cb0",
                "vin": [{"coinbase": "01710101", "sequence": 0xFFFFFFFF}],
                "vout": [
                    {"n": 0, "value": 0, "scriptPubKey": {"hex": "6a", "type": "nulldata"}},
                    {
                        "n": 1,
                        "value": "0.00000000",
                        "scriptPubKey": {
                            "hex": "6a04deadbeef",
                            "type": "nulldata",
                        },
                    },
                ],
            }
        ],
    },
    checks=[
        _c("bulk genesis height==0", lambda x: x["bulk_block_row"]["height"], 0),
        _c("coerced genesis height==0", lambda x: x["coerced_block"]["height"], 0),
        _c("service is_coinbase", lambda x: x["service_txs"][0]["is_coinbase"], True),
        _c(
            "bulk bare OP_RETURN flagged", lambda x: x["bulk"][0]["txouts"][0]["is_op_return"], True
        ),
        _c(
            "coerced bare OP_RETURN flagged",
            lambda x: x["coerced"][0][2][0]["is_op_return"],
            True,
        ),
        _c(
            "bulk data OP_RETURN payload",
            lambda x: x["bulk"][0]["txouts"][1]["op_return_data_hex"],
            "deadbeef",
        ),
    ],
)


CONFIDENTIAL_TX = Case(
    name="confidential_output",
    block={
        "hash": "b1",
        "height": 100,
        "time": 1_600_000_000,
        "tx": [
            {
                "txid": "t_conf",
                "vin": [{"txid": "p", "vout": 0, "sequence": 0}],
                "vout": [
                    {
                        "n": 0,
                        "value": None,
                        "valuecommitment": "0955aa",
                        "assetcommitment": "0acc",
                        "scriptPubKey": {"hex": "0014abcd", "address": "el1c"},
                    }
                ],
            }
        ],
    },
    checks=[
        _c(
            "bulk has_any_confidential",
            lambda x: x["bulk"][0]["tx_row"]["has_any_confidential"],
            True,
        ),
        _c(
            "bulk confidential value_sat is None",
            lambda x: x["bulk"][0]["txouts"][0]["value_sat"],
            None,
        ),
        _c(
            "service output type confidential",
            lambda x: x["service_txs"][0]["outputs"][0]["type"],
            "confidential",
        ),
        _c("service fee None on confidential", lambda x: x["service_txs"][0]["fee"], None),
    ],
)


PEGIN_ISSUANCE = Case(
    name="pegin_plus_issuance",
    block={
        "hash": "b2",
        "height": 200,
        "time": 1_600_100_000,
        "tx": [
            {
                "txid": "t_peg",
                "vin": [
                    {
                        "txid": "c",
                        "vout": 2,
                        "sequence": 0,
                        "is_pegin": True,
                        "issuance": {"assetamount": "1.0", "tokenamount": "2.0"},
                    }
                ],
                "vout": [
                    {"n": 0, "value": "0.5", "asset": "aid", "scriptPubKey": {"address": "el1p"}}
                ],
            }
        ],
    },
    checks=[
        _c("coerced txin is_pegin kept", lambda x: x["coerced"][0][1][0]["is_pegin"], True),
        _c("coerced tx has_pegin", lambda x: x["coerced"][0][0]["has_pegin"], True),
        _c("coerced tx has_issuance", lambda x: x["coerced"][0][0]["has_issuance"], True),
        _c(
            "issuance amount -> satoshi",
            lambda x: x["coerced"][0][1][0]["issuance_amount"],
            100_000_000,
        ),
    ],
)


EXPLICIT_FEE = Case(
    name="explicit_fee",
    block={
        "hash": "b3",
        "height": 300,
        "time": 1_600_200_000,
        "tx": [
            {
                "txid": "t_fee",
                "vin": [
                    {
                        "txid": "p",
                        "vout": 0,
                        "sequence": 0,
                        "prevout": {
                            "value": "1.0",
                            "asset": "aid",
                            "scriptPubKey": {"address": "el1in"},
                        },
                    }
                ],
                "vout": [
                    {
                        "n": 0,
                        "value": "0.99990000",
                        "asset": "aid",
                        "scriptPubKey": {"address": "el1out"},
                    }
                ],
            }
        ],
    },
    checks=[
        _c("service input_value", lambda x: x["service_txs"][0]["input_value"], "1.0"),
        _c("service output_value", lambda x: x["service_txs"][0]["output_value"], "0.99990000"),
        _c("service fee = in - out", lambda x: x["service_txs"][0]["fee"], "0.00010000"),
        _c("bulk out value_sat", lambda x: x["bulk"][0]["txouts"][0]["value_sat"], 99_990_000),
    ],
)


CASES: List[Case] = [GENESIS_COINBASE, CONFIDENTIAL_TX, PEGIN_ISSUANCE, EXPLICIT_FEE]
