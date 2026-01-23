import json
import sqlite3

from liquidetl.streaming.streamer_adapter import LiquidStreamerAdapter
from liquidetl.service import LiquidService, BlockWithTxs
from liquidetl.cli import main as cli_main


class StubService(LiquidService):
    def __init__(self):
        class _R: pass
        super().__init__(_R())

    def get_head_height(self):
        return 0

    def get_block_by_number(self, height: int):
        block = {"hash": f"h{height}", "number": height, "timestamp": 1000 + height}
        tx = {"hash": f"t{height}", "inputs": [], "outputs": []}
        return BlockWithTxs(block=block, transactions=[tx])


def test_stream_writes_to_sqlite(monkeypatch, tmp_path):
    db_path = tmp_path / "local.db"
    s = StubService()
    adapter = LiquidStreamerAdapter(service=s, output=f"sqlite://{db_path.as_posix()}", batch_size=1)

    def raise_kbi(seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(__import__("time"), "sleep", raise_kbi)

    try:
        adapter.stream(start_block=0, lag=0, poll_interval=0.01)
    except KeyboardInterrupt:
        pass

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(1) FROM blocks")
    blocks_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(1) FROM transactions")
    tx_count = cur.fetchone()[0]
    conn.close()

    assert blocks_count >= 1
    assert tx_count >= 1


def test_cli_load_ndjson_into_sqlite(tmp_path):
    db_path = tmp_path / "loaded.db"
    blocks_path = tmp_path / "blocks.ndjson"
    tx_path = tmp_path / "tx.ndjson"

    with open(blocks_path, "w", encoding="utf-8") as bf:
        bf.write(json.dumps({"hash": "h1", "number": 1, "timestamp": 12345}) + "\n")
    with open(tx_path, "w", encoding="utf-8") as tf:
        tf.write(json.dumps({
            "hash": "t1", "index": 0, "block_hash": "h1", "block_number": 1, "block_timestamp": 12345,
            "inputs": [], "outputs": []
        }) + "\n")

    rc = cli_main([
        "load_ndjson_to_sqlite",
        "--db", str(db_path),
        "--blocks-input", str(blocks_path),
        "--transactions-input", str(tx_path),
    ])
    assert rc == 0

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(1) FROM blocks")
    blocks_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(1) FROM transactions")
    tx_count = cur.fetchone()[0]
    conn.close()

    assert blocks_count == 1
    assert tx_count == 1