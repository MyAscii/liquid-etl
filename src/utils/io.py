from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Iterable


def _json_default(obj: Any):
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Type not serializable: {type(obj)}")


def write_ndjson(items: Iterable[dict], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, default=_json_default))
            f.write("\n")


def append_ndjson(item: dict, path: str) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(item, default=_json_default))
        f.write("\n")