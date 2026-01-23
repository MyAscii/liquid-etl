from liquidetl.jobs.export_all_job import export_all
from liquidetl.service import BlockWithTxs


class StubService:
    def get_block_range_for_date(self, date_str: str, start_hour: int = 0, end_hour: int = 24):
        return 0, 2

    def get_block_by_number(self, height: int):
        block = {"hash": f"h{height}", "number": height, "timestamp": 1000 + height}
        tx = {"hash": f"t{height}", "inputs": [{"txid": "prev", "vout": 0}], "outputs": []}
        return BlockWithTxs(block=block, transactions=[tx])

    class rpc:
        @staticmethod
        def getrawtransaction(txid: str, verbose: bool = True):
            return {
                "vout": [{"value": 0.1, "asset": "assetid", "scriptPubKey": {"address": "el1z"}}]
            }


def test_export_all_creates_hive_dirs(tmp_path):
    service = StubService()
    out_dir = tmp_path / "output"
    export_all(
        service=service, output_dir=str(out_dir), date="2020-01-01", batch_size=2, enrich=True
    )
    # Check directories and files
    chain_dir = out_dir / "chain=liquid" / "date=2020-01-01"
    batches = list(chain_dir.glob("block_start=*"))
    assert len(batches) >= 1
    for b in batches:
        assert (b / "blocks.json").exists()
        assert (b / "transactions.json").exists()
        assert (b / "enriched_transactions.json").exists()
