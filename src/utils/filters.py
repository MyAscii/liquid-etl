from __future__ import annotations

import csv
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Dict, List

# Structured, code-free predicate language.
#
# Predicates used to be arbitrary Python passed to eval(), which is remote code
# execution on --predicate (an empty __builtins__ is not a sandbox). They are now
# a JSON spec evaluated in pure Python. Grammar:
#
#   leaf:     {"field": "<dotted.path>", "op": "<op>", "value": <json>}
#   compound: {"and": [<node>, ...]} | {"or": [<node>, ...]} | {"not": <node>}
#
# Supported ops: eq ne lt le gt ge contains startswith endswith in regex exists.
# Field paths walk dicts by key and lists/tuples by integer index ("inputs.0.value").
#
# Examples:
#   {"field": "block_timestamp", "op": "startswith", "value": "2019-03-01"}
#   {"and": [{"field": "block_number", "op": "ge", "value": 100},
#            {"field": "block_number", "op": "lt", "value": 200}]}

_COMPARE_OPS = {"lt", "le", "gt", "ge"}
_LEAF_OPS = {
    "eq",
    "ne",
    "lt",
    "le",
    "gt",
    "ge",
    "contains",
    "startswith",
    "endswith",
    "in",
    "regex",
    "exists",
}

_MISSING = object()


class PredicateError(ValueError):
    """Raised when a predicate spec is malformed."""


def compile_predicate(spec: Any) -> Callable[[Dict[str, Any]], bool]:
    """Compile a predicate spec (JSON string or already-parsed object) to a callable."""
    if isinstance(spec, str):
        try:
            spec = json.loads(spec)
        except json.JSONDecodeError as e:
            raise PredicateError(
                "predicate must be a JSON object, e.g. "
                '{"field": "block_number", "op": "ge", "value": 100}'
            ) from e
    return _compile_node(spec)


# Back-compat internal name used by callers/tests.
_compile_predicate = compile_predicate


def _compile_node(node: Any) -> Callable[[Dict[str, Any]], bool]:
    if not isinstance(node, dict):
        raise PredicateError(f"predicate node must be an object, got {type(node).__name__}")

    if "and" in node:
        subs = _compile_seq(node["and"], "and")
        return lambda item: all(s(item) for s in subs)
    if "or" in node:
        subs = _compile_seq(node["or"], "or")
        return lambda item: any(s(item) for s in subs)
    if "not" in node:
        sub = _compile_node(node["not"])
        return lambda item: not sub(item)

    field = node.get("field")
    op = node.get("op")
    if not isinstance(field, str) or not field:
        raise PredicateError("leaf predicate requires a non-empty string 'field'")
    if op not in _LEAF_OPS:
        raise PredicateError(f"unsupported op '{op}'; expected one of {sorted(_LEAF_OPS)}")
    value = node.get("value")
    return _compile_leaf(field, op, value)


def _compile_seq(nodes: Any, name: str) -> List[Callable[[Dict[str, Any]], bool]]:
    if not isinstance(nodes, list) or not nodes:
        raise PredicateError(f"'{name}' requires a non-empty list of predicates")
    return [_compile_node(n) for n in nodes]


def _compile_leaf(field: str, op: str, value: Any) -> Callable[[Dict[str, Any]], bool]:
    parts = field.split(".")

    if op == "regex":
        try:
            pattern = re.compile(str(value))
        except re.error as e:
            raise PredicateError(f"invalid regex '{value}': {e}") from e

    def predicate(item: Dict[str, Any]) -> bool:
        actual = _get_path(item, parts)
        if op == "exists":
            present = actual is not _MISSING and actual is not None
            return present if _as_bool(value, default=True) else not present
        if actual is _MISSING or actual is None:
            return False
        if op == "eq":
            return _values_equal(actual, value)
        if op == "ne":
            return not _values_equal(actual, value)
        if op in _COMPARE_OPS:
            return _numeric_compare(actual, value, op)
        if op == "contains":
            if isinstance(actual, (list, tuple)):
                return value in actual
            return str(value) in str(actual)
        if op == "startswith":
            return str(actual).startswith(str(value))
        if op == "endswith":
            return str(actual).endswith(str(value))
        if op == "in":
            if not isinstance(value, (list, tuple)):
                return False
            return actual in value or any(_values_equal(actual, v) for v in value)
        if op == "regex":
            return pattern.search(str(actual)) is not None
        return False

    return predicate


def _get_path(item: Any, parts: List[str]) -> Any:
    cur: Any = item
    for part in parts:
        if isinstance(cur, dict):
            if part not in cur:
                return _MISSING
            cur = cur[part]
        elif isinstance(cur, (list, tuple)):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return _MISSING
        else:
            return _MISSING
    return cur


def _to_decimal(v: Any) -> Any:
    if isinstance(v, bool):
        return None
    if isinstance(v, Decimal):
        return v
    if isinstance(v, int):
        return Decimal(v)
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def _values_equal(a: Any, b: Any) -> bool:
    if a == b:
        return True
    da, db = _to_decimal(a), _to_decimal(b)
    if da is not None and db is not None:
        return da == db
    return str(a) == str(b)


def _numeric_compare(a: Any, b: Any, op: str) -> bool:
    da, db = _to_decimal(a), _to_decimal(b)
    if da is not None and db is not None:
        left, right = da, db
    else:
        left, right = str(a), str(b)
    if op == "lt":
        return left < right
    if op == "le":
        return left <= right
    if op == "gt":
        return left > right
    return left >= right


def _as_bool(v: Any, *, default: bool) -> bool:
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "t", "yes", "y"}
    return bool(v)


def filter_items(
    input_path: str, output_path: str, predicate: str, input_format: str = "ndjson"
) -> None:
    pred = compile_predicate(predicate)
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
