import types

import liquidetl.utils.postgres_writer as pg_mod


class _FakeCursor:
    def __init__(self, state):
        self._state = state
        self._pending = None

    def execute(self, sql, params=None):
        if sql.strip().startswith("SELECT to_regclass"):
            name = (params[0] or "").split(".", 1)[-1]
            self._pending = ("to_regclass", name)
            return

        if "FROM information_schema.columns" in sql:
            table, column = params
            self._pending = ("has_column", table, column)
            return

        if sql.strip().startswith("ALTER TABLE") and " RENAME TO " in sql:
            parts = sql.strip().split()
            old = parts[2]
            new = parts[-1]
            self._state["renames"].append((old, new))
            if old in self._state["tables"]:
                self._state["tables"][new] = self._state["tables"].pop(old)
            self._pending = None
            return

        self._pending = None

    def fetchone(self):
        if not self._pending:
            return None
        kind = self._pending[0]
        if kind == "to_regclass":
            name = self._pending[1]
            return (name if name in self._state["tables"] else None,)
        if kind == "has_column":
            table, column = self._pending[1], self._pending[2]
            cols = self._state["tables"].get(table, set())
            return (1,) if column in cols else None
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def __init__(self, state):
        self._state = state

    def cursor(self):
        return _FakeCursor(self._state)

    def transaction(self):
        class _Tx:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, exc_type, exc, tb):
                return False

        return _Tx()

    def close(self):
        return None


def _install_fake_psycopg(monkeypatch, state):
    fake = types.SimpleNamespace(connect=lambda *_args, **_kwargs: _FakeConn(state))
    monkeypatch.setattr(pg_mod, "psycopg", fake, raising=False)
    monkeypatch.setitem(__import__("sys").modules, "psycopg", fake)


def test_coerce_tx_rows_populates_fee_maps_and_issuance(monkeypatch):
    state = {
        "tables": {
            "blocks": {"height"},
            "transactions": {"txid"},
            "txins": {"txid"},
            "txouts": {"txid"},
        },
        "renames": [],
    }
    _install_fake_psycopg(monkeypatch, state)
    w = pg_mod.PostgresWriter("postgresql://x")

    tx = {
        "txid": "t1",
        "hash": "t1",
        "withash": None,
        "wtxid": None,
        "block_hash": "b1",
        "block_number": 1,
        "block_timestamp": 10,
        "version": 2,
        "lock_time": 0,
        "size": 100,
        "virtual_size": 90,
        "weight": 360,
        "discount_virtual_size": 90,
        "discount_weight": 360,
        "node_fee": {"assetX": "0.00000100"},
        "inputs": [
            {
                "txid": "p0",
                "vout": 0,
                "sequence": 1,
                "input_type": "issuance",
                "is_coinbase": False,
                "scriptsig_hex": "00",
                "scriptsig_asm": "",
                "witness": [],
                "issuance": {"assetamount": "1.0", "tokenamount": "2.0"},
            }
        ],
        "outputs": [
            {
                "n": 0,
                "asset": "assetX",
                "value": "0.00000100",
                "type": "fee",
                "scriptpubkey_hex": "",
                "scriptpubkey_asm": "",
                "script_type": "fee",
                "op_return_data_hex": None,
                "nonce": "02",
                "surjection_proof": "sp",
                "rangeproof": "rp",
            }
        ],
    }

    tx_row, txins, txouts = w._coerce_tx_rows(tx)
    assert tx_row["fee_by_asset"] == {"assetX": 100}
    assert tx_row["explicit_out_by_asset"] == {"assetX": 100}
    assert tx_row["explicit_in_by_asset"] is None
    assert len(txins) == 1
    assert txins[0]["has_issuance"] is True
    assert txins[0]["issuance_amount"] == 100000000
    assert txins[0]["issuance_inflation_keys"] == 200000000
    assert len(txouts) == 1
    assert txouts[0]["is_fee"] is True
    assert txouts[0]["surjection_proof"] == "sp"


def test_coerce_block_row_includes_all_block_table_columns(monkeypatch):
    state = {
        "tables": {
            "blocks": {"height"},
            "transactions": {"txid"},
            "txins": {"txid"},
            "txouts": {"txid"},
        },
        "renames": [],
    }
    _install_fake_psycopg(monkeypatch, state)
    w = pg_mod.PostgresWriter("postgresql://x")

    block = {
        "hash": "b1",
        "number": 1,
        "version": 2,
        "previous_block_hash": "p",
        "next_block_hash": None,
        "merkle_root": "m",
        "timestamp": 10,
        "median_time": 11,
        "nonce": None,
        "bits": None,
        "difficulty": None,
        "chainwork": None,
        "transaction_count": 1,
        "size": 100,
        "stripped_size": 90,
        "weight": 360,
        "signblock_challenge": None,
        "signblock_witness_hex": None,
        "dynafed_current_params": None,
        "dynafed_proposed_params": None,
        "signblock_witness": None,
        "txids": ["t1"],
    }

    row = w._coerce_block_row(block)
    expected = {
        "hash",
        "height",
        "version",
        "prev_block_hash",
        "next_block_hash",
        "merkle_root",
        "time",
        "median_time",
        "tx_count",
        "size",
        "stripped_size",
        "weight",
        "signblock_solution_hex",
        "txids",
    }
    assert expected.issubset(set(row.keys()))

