# services/eval — normalizer eval

Deterministic golden-fixture eval for the two normalizer paths. No LLM, no node.

## What it checks

Golden `getblock(verbosity=3)` fixtures are pushed through:

- the **bulk** path (`utils.normalization.normalize_block` / `normalize_tx`) used by `ingest_range_to_postgres`, and
- the **service** path (`LiquidService.get_block_by_number`) used by streaming/export, plus the Postgres `coercion` applied to its output.

Money-critical output fields are scored field-by-field. Cases cover the regressions this suite exists to prevent:

- `to_satoshi` scaling (`value_sat`, `issuance_amount`)
- fee / `input_value` / `output_value` computation from prevouts
- genesis block height (`0`, not NULL)
- peg-in classification when an input is both peg-in and issuance
- bare and data-carrying OP_RETURN detection
- confidential-output handling (hidden value, `fee` null)

## Run

```sh
python services/eval/run_eval.py        # prints a per-check table, exits nonzero on failure
pytest -m eval                          # same suite, as a gate test
```

The pass threshold is **100% of critical checks**. Add a fixture here whenever a
normalization bug is fixed, so the fix is proven to generalize.
