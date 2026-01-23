from __future__ import annotations

import csv
import json
from decimal import Decimal
from typing import Callable, Dict


def _compile_predicate(expr: str) -> Callable[[Dict], bool]:
    # Limited eval environment with safe helpers
    env = {
        "Decimal": Decimal,
        "int": int,
        "float": float,
        "str": str,
        "len": len,
    }
    globals_env = {"__builtins__": {}, **env}
    func = eval(expr, globals_env, {})
    if not callable(func):
        raise ValueError("predicate must evaluate to a callable, e.g., lambda x: ...")
    return func


def filter_items(
    input_path: str, output_path: str, predicate: str, input_format: str = "ndjson"
) -> None:
    pred = _compile_predicate(predicate)
    if input_format == "ndjson":
        with (
            open(input_path, "r", encoding="utf-8") as fin,
            open(output_path, "w", encoding="utf-8") as fout,
        ):
            for line in fin:
                if not line.strip():
                    continue
                item = json.loads(line)
                if pred(item):
                    fout.write(json.dumps(item))
                    fout.write("\n")
    else:
        with open(input_path, "r", encoding="utf-8") as fin:
            reader = csv.DictReader(fin)
            rows = list(reader)
        # Write keeping same headers
        if rows:
            with open(output_path, "w", encoding="utf-8", newline="") as fout:
                writer = csv.DictWriter(fout, fieldnames=rows[0].keys())
                writer.writeheader()
                for row in rows:
                    if pred(row):
                        writer.writerow(row)
