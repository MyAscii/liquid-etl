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


def test_migrate_renames_legacy_tables(monkeypatch):
    state = {"tables": {"blocks": {"number"}, "transactions": {"tx_index"}}, "renames": []}
    _install_fake_psycopg(monkeypatch, state)
    pg_mod.PostgresWriter("postgresql://x", network="liquidv1")
    assert ("blocks", "blocks_legacy") in state["renames"]
    assert ("transactions", "transactions_legacy") in state["renames"]


def test_migrate_renames_v2_tables(monkeypatch):
    state = {"tables": {"blocks_v2": {"height"}, "transactions_v2": {"txid"}, "txins_v2": {"txid"}, "txouts_v2": {"txid"}}, "renames": []}
    _install_fake_psycopg(monkeypatch, state)
    pg_mod.PostgresWriter("postgresql://x", network="liquidv1")
    assert ("blocks_v2", "blocks") in state["renames"]
    assert ("transactions_v2", "transactions") in state["renames"]
    assert ("txins_v2", "txins") in state["renames"]
    assert ("txouts_v2", "txouts") in state["renames"]


def test_migrate_does_not_rename_when_targets_exist(monkeypatch):
    state = {"tables": {"blocks": {"height"}, "blocks_v2": {"height"}}, "renames": []}
    _install_fake_psycopg(monkeypatch, state)
    pg_mod.PostgresWriter("postgresql://x", network="liquidv1")
    assert ("blocks_v2", "blocks") not in state["renames"]
