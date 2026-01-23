from __future__ import annotations

from functools import lru_cache

from ..sql_resources import load_sql


@lru_cache(maxsize=None)
def sql_text(filename: str) -> str:
    return load_sql("liquidetl.utils.postgres", f"sql/{filename}")
