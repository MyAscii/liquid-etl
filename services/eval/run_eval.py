"""CLI runner for the normalizer eval. Exits nonzero if any critical check fails."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harness import CASES, run_suite  # noqa: E402


def main() -> int:
    results, summary = run_suite(CASES)
    current = None
    for r in results:
        if r.case != current:
            current = r.case
            print(f"\n== {r.case} ==")
        mark = "PASS" if r.ok else "FAIL"
        crit = "*" if r.critical else " "
        print(f"  [{mark}]{crit} {r.label}: expected={r.expected!r} actual={r.actual!r}")
    print(
        f"\nscore={summary['passed']}/{summary['total']}  "
        f"critical={summary['critical_passed']}/{summary['critical_total']}  "
        f"gate={'PASS' if summary['passed_gate'] else 'FAIL'}"
    )
    return 0 if summary["passed_gate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
