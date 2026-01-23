from __future__ import annotations

from typing import Any

from .sql_files import sql_text


def ensure_schema(cur: Any) -> None:
    _execute_script(cur, sql_text("schema.sql"))
    _execute_script(cur, sql_text("indexes.sql"))
    drop_obsolete_columns(cur)


def drop_obsolete_columns(cur: Any) -> None:
    _execute_script(cur, sql_text("drop_obsolete.sql"))


def _execute_script(cur: Any, sql: str) -> None:
    for stmt in sql.split(";"):
        s = stmt.strip()
        if not s:
            continue
        cur.execute(s)
