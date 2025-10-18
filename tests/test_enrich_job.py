import json

from liquidetl.jobs.enrich_transactions_job import EnrichTransactionsJob
from liquidetl.service import LiquidService


class StubRpc:
    def getrawtransaction(self, txid: str, verbose: bool = True):
        return {
            "vout": [
                {"value": 0.5, "asset": "assetid", "scriptPubKey": {"addresses": ["el1x"], "reqSigs": 1}},
                {"value": 1.0, "asset": "assetid2", "scriptPubKey": {"address": "el1y"}},
            ]
        }


def test_enrich_transactions_job(tmp_path):
    service = LiquidService(StubRpc())
    input_file = tmp_path / "tx.json"
    output_file = tmp_path / "out.json"
    # One tx with one input referencing vout 1
    tx = {"hash": "t1", "inputs": [{"txid": "prev", "vout": 1}], "outputs": []}
    with open(input_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(tx) + "\n")
    job = EnrichTransactionsJob(service, str(input_file), str(output_file))
    job.run()
    # Read and verify enrichment
    with open(output_file, "r", encoding="utf-8") as f:
        enriched = json.loads(f.read())
    vin = enriched["inputs"][0]
    assert vin["addresses"] in ([["el1x"], ["el1y"]])
    assert "required_signatures" in vin
    assert "value" in vin
    assert "asset" in vin