import logging

import pytest
from liquidetl.rpc import RpcError
from liquidetl.service import LiquidService
from liquidetl.utils.tx_enrichment import inline_enrich_inputs


class OkRpc:
    def getrawtransaction(self, txid, verbose=True):
        return {
            "vout": [
                {"value": "0.5", "asset": "a", "scriptPubKey": {"address": "el1x", "reqSigs": 1}}
            ]
        }


class FailRpc:
    def getrawtransaction(self, txid, verbose=True):
        raise RpcError("no txindex on this node")


class BugRpc:
    def getrawtransaction(self, txid, verbose=True):
        raise TypeError("a real programming bug")


def _svc(rpc):
    return LiquidService(rpc)


def test_enrich_success_populates_and_counts():
    tx = {"inputs": [{"txid": "p", "vout": 0}]}
    stats = inline_enrich_inputs(_svc(OkRpc()), tx)
    assert stats == {"attempted": 1, "enriched": 1, "failed": 0}
    assert tx["inputs"][0]["value"] == "0.5"
    assert tx["inputs"][0]["addresses"] == ["el1x"]


def test_rpc_failure_is_marked_and_logged_not_swallowed(caplog):
    tx = {"inputs": [{"txid": "p", "vout": 0}]}
    with caplog.at_level(logging.WARNING):
        stats = inline_enrich_inputs(_svc(FailRpc()), tx)
    assert stats["failed"] == 1
    assert "enrichment_error" in tx["inputs"][0]
    assert "enrichment failed" in caplog.text


def test_prevout_index_out_of_range_is_marked():
    tx = {"inputs": [{"txid": "p", "vout": 9}]}
    stats = inline_enrich_inputs(_svc(OkRpc()), tx)
    assert stats["failed"] == 1
    assert "out of range" in tx["inputs"][0]["enrichment_error"]


def test_programming_errors_propagate():
    tx = {"inputs": [{"txid": "p", "vout": 0}]}
    with pytest.raises(TypeError):
        inline_enrich_inputs(_svc(BugRpc()), tx)
