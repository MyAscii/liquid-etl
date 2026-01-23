import json
import sqlite3

from liquidetl.cli import main as cli_main


def test_cli_load_ndjson_into_sqlite(tmp_path):
    db_path = tmp_path / "loaded.db"
    blocks_path = tmp_path / "blocks.ndjson"
    tx_path = tmp_path / "tx.ndjson"

    with open(blocks_path, "w", encoding="utf-8") as bf:
        bf.write(json.dumps({"hash": "h1", "number": 1, "timestamp": 12345}) + "\n")
    with open(tx_path, "w", encoding="utf-8") as tf:
        tf.write(
            json.dumps(
                {
                    "hash": "t1",
                    "index": 0,
                    "block_hash": "h1",
                    "block_number": 1,
                    "block_timestamp": 12345,
                    "inputs": [],
                    "outputs": [],
                }
            )
            + "\n"
        )

    rc = cli_main(
        [
            "load_ndjson_to_sqlite",
            "--db",
            str(db_path),
            "--blocks-input",
            str(blocks_path),
            "--transactions-input",
            str(tx_path),
        ]
    )
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

