import sqlite3

import pytest

from liquidetl.utils.sqlite.writer import SQLiteWriter


def _tx(hash_: str, index: int) -> dict:
    return {"hash": hash_, "txid": hash_, "index": index, "is_coinbase": index == 0}


def test_wal_mode_enabled(tmp_path):
    w = SQLiteWriter(str(tmp_path / "a.db"))
    mode = w.conn.execute("PRAGMA journal_mode").fetchone()[0]
    w.close()
    assert mode.lower() == "wal"


def test_genesis_block_keeps_zero_number(tmp_path):
    db = tmp_path / "g.db"
    w = SQLiteWriter(str(db))
    w.write_block({"hash": "h0", "number": 0, "timestamp": 1000, "transaction_count": 1})
    w.close()
    conn = sqlite3.connect(str(db))
    assert conn.execute("SELECT number FROM blocks WHERE hash='h0'").fetchone()[0] == 0
    conn.close()


def test_none_index_is_rejected(tmp_path):
    w = SQLiteWriter(str(tmp_path / "n.db"))
    try:
        with pytest.raises(ValueError):
            w.write_transaction({"hash": "t1", "txid": "t1", "index": None})
    finally:
        w.close()


def test_batch_commits_once_and_writes_all(tmp_path):
    db = tmp_path / "b.db"
    w = SQLiteWriter(str(db))
    with w.batch():
        w.write_block({"hash": "b1", "number": 5, "timestamp": 1, "transaction_count": 3})
        w.write_transactions([_tx("t0", 0), _tx("t1", 1), _tx("t2", 2)])
    w.close()
    conn = sqlite3.connect(str(db))
    assert conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 3
    assert conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0] == 1
    conn.close()


def test_batch_rolls_back_on_error(tmp_path):
    db = tmp_path / "r.db"
    w = SQLiteWriter(str(db))
    with pytest.raises(ValueError):
        with w.batch():
            w.write_block({"hash": "b1", "number": 1, "timestamp": 1, "transaction_count": 1})
            w.write_transaction({"hash": "t1", "txid": "t1", "index": None})  # raises
    w.close()
    conn = sqlite3.connect(str(db))
    # The whole batch rolled back: the block written before the failure is gone.
    assert conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0] == 0
    conn.close()
