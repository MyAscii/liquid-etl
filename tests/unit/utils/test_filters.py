import csv
import json

from liquidetl.utils.filters import filter_items


def test_filter_ndjson(tmp_path):
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
        predicate='lambda x: x["block_timestamp"].startswith("2019-03-01")',
    )
    with open(out, "r", encoding="utf-8") as f:
        lines = [l for l in f.read().splitlines() if l]
    assert len(lines) == 1


def test_filter_csv(tmp_path):
    inp = tmp_path / "in.csv"
    out = tmp_path / "out.csv"
    with open(inp, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["a", "b"])
        writer.writeheader()
        writer.writerow({"a": "1", "b": "x"})
        writer.writerow({"a": "2", "b": "y"})
    filter_items(
        input_path=str(inp),
        output_path=str(out),
        predicate='lambda x: int(x["a"])>1',
        input_format="csv",
    )
    with open(out, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
