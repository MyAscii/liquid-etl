"""Pytest wrapper so the normalizer eval runs in CI as a gate (it is deterministic)."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harness import CASES, run_suite  # noqa: E402


@pytest.mark.eval
def test_normalizer_eval_suite_passes():
    results, summary = run_suite(CASES)
    failures = [
        f"{r.case}:{r.label} expected={r.expected!r} actual={r.actual!r}"
        for r in results
        if not r.ok
    ]
    assert summary["passed_gate"], "critical eval checks failed:\n" + "\n".join(failures)
    assert summary["score"] == 1.0, "eval checks failed:\n" + "\n".join(failures)
