import json

from liquidetl.jobs.export_blocks_job import ExportBlocksJob
from liquidetl.service import BlockWithTxs


class StubService:
    def get_block_by_number(self, height: int):
        block = {"hash": f"h{height}", "number": height, "timestamp": 1000 + height}
        tx = {"hash": f"t{height}", "inputs": [], "outputs": []}
        return BlockWithTxs(block=block, transactions=[tx])


def test_export_blocks_job_writes_ndjson(tmp_path):
    blocks_out = tmp_path / "blocks.json"
    tx_out = tmp_path / "transactions.json"
    job = ExportBlocksJob(StubService(), 0, 1, str(blocks_out), str(tx_out))
    job.run()
    # Two blocks lines
    with open(blocks_out, "r", encoding="utf-8") as f:
        lines = [l for l in f.read().splitlines() if l]
        assert len(lines) == 2
    with open(tx_out, "r", encoding="utf-8") as f:
        lines = [l for l in f.read().splitlines() if l]
        assert len(lines) == 2