import csv
import json

import pytest
from liquidetl.utils.filters import PredicateError, compile_predicate, filter_items


def test_filter_ndjson_startswith(tmp_path):
    inp = tmp_path / "in.json"
    out = tmp_path / "out.json"
    items = [
        {"block_timestamp": "2019-03-01T00:00:00Z", "x": 1},
        {"block_timestamp": "2019-03-02T00:00:00Z", "x": 2},
    ]
    with open(inp, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it) + "\n")
    filter_items(
        input_path=str(inp),
        output_path=str(out),
        predicate=json.dumps(
            {"field": "block_timestamp", "op": "startswith", "value": "2019-03-01"}
        ),
    )
    with open(out, "r", encoding="utf-8") as f:
        lines = [line for line in f.read().splitlines() if line]
    assert len(lines) == 1
    assert json.loads(lines[0])["x"] == 1


def test_filter_csv_numeric_coercion(tmp_path):
    inp = tmp_path / "in.csv"
    out = tmp_path / "out.csv"
    with open(inp, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["a", "b"])
        writer.writeheader()
        writer.writerow({"a": "1", "b": "x"})
        writer.writerow({"a": "2", "b": "y"})
    # CSV values are strings; "gt 1" must still compare numerically.
    filter_items(
        input_path=str(inp),
        output_path=str(out),
        predicate=json.dumps({"field": "a", "op": "gt", "value": 1}),
        input_format="csv",
    )
    with open(out, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["a"] == "2"


def test_and_or_not_compound():
    pred = compile_predicate(
        {
            "and": [
                {"field": "n", "op": "ge", "value": 100},
                {"not": {"field": "n", "op": "ge", "value": 200}},
            ]
        }
    )
    assert pred({"n": 150}) is True
    assert pred({"n": 200}) is False
    assert pred({"n": 50}) is False


def test_dotted_path_into_list():
    pred = compile_predicate({"field": "inputs.0.value", "op": "eq", "value": "0.5"})
    assert pred({"inputs": [{"value": "0.5"}]}) is True
    assert pred({"inputs": [{"value": "0.6"}]}) is False
    # Missing path is False, never an error.
    assert pred({"inputs": []}) is False
    assert pred({}) is False


def test_exists_and_regex():
    assert compile_predicate({"field": "asset", "op": "exists"})({"asset": "abc"}) is True
    assert compile_predicate({"field": "asset", "op": "exists"})({"asset": None}) is False
    assert compile_predicate({"field": "asset", "op": "exists", "value": False})({}) is True
    assert compile_predicate({"field": "h", "op": "regex", "value": "^ab"})({"h": "abcd"}) is True


def test_malformed_predicate_raises():
    with pytest.raises(PredicateError):
        compile_predicate("not valid json {")
    with pytest.raises(PredicateError):
        compile_predicate({"field": "x", "op": "bogus", "value": 1})
    with pytest.raises(PredicateError):
        compile_predicate({"or": []})


def test_predicate_is_data_not_code(tmp_path):
    """Regression for the eval() RCE: a Python payload is treated as data, never executed."""
    marker = tmp_path / "pwned.txt"
    # The classic sandbox-escape string. Under the old eval() sink this could run code;
    # now it is just an invalid predicate spec and must raise, not execute.
    payload = (
        "[c for c in ().__class__.__base__.__subclasses__() "
        "if c.__name__=='catch_warnings'][0]()"
    )
    with pytest.raises(PredicateError):
        compile_predicate(payload)
    assert not marker.exists()
    # A lambda string (the old accepted form) is now rejected, not run.
    with pytest.raises(PredicateError):
        compile_predicate('lambda x: __import__("os").system("echo hi")')
