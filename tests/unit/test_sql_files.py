from __future__ import annotations

from liquidetl.utils.postgres.sql_files import sql_text as pg_sql
from liquidetl.utils.sqlite.sql_files import sql_text as sqlite_sql


def test_postgres_sql_files_load():
    schema = pg_sql("schema.sql")
    assert "CREATE TABLE IF NOT EXISTS blocks" in schema
    insert_blocks = pg_sql("insert_blocks.sql")
    assert "INSERT INTO blocks" in insert_blocks


def test_sqlite_sql_files_load():
    schema = sqlite_sql("schema.sql")
    assert "CREATE TABLE IF NOT EXISTS blocks" in schema
    insert_tx = sqlite_sql("insert_transactions.sql")
    assert "INSERT INTO transactions" in insert_tx
