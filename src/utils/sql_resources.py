from __future__ import annotations

from importlib import resources


def load_sql(package: str, relative_path: str) -> str:
    return resources.files(package).joinpath(relative_path).read_text(encoding="utf-8")
