import sqlite3

from liquidetl.streaming.streamer_adapter import LiquidStreamerAdapter


def test_stream_writes_to_sqlite(monkeypatch, tmp_path, stub_service):
    db_path = tmp_path / "local.db"
    adapter = LiquidStreamerAdapter(
        service=stub_service, output=f"sqlite://{db_path.as_posix()}", batch_size=1
    )

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
