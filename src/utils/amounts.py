from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

SATOSHI_FACTOR = Decimal("100000000")


def to_satoshi(value: Any) -> Optional[int]:
    """Convert a BTC/L-BTC-denominated amount to integer satoshi.

    Contract:
    - ``None`` and booleans are not amounts -> ``None``.
    - ints, Decimals, strings and floats are interpreted as whole-coin amounts,
      so ``1`` and ``"1"`` both mean 1e8 satoshi.
    - A value with more precision than one satoshi (non-integral after scaling)
      returns ``None`` rather than silently truncating a money field.
    - Non-finite or unparseable values return ``None``.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, int):
        d = Decimal(value)
    else:
        try:
            d = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
    if not d.is_finite():
        return None
    q = d * SATOSHI_FACTOR
    if q != q.to_integral_value():
        return None
    return int(q)


def amounts_map_to_satoshi_map(m: Any) -> Dict[str, int]:
    if not isinstance(m, dict):
        return {}
    out: Dict[str, int] = {}
    for k, v in m.items():
        sat = to_satoshi(v)
        if sat is None:
            continue
        out[str(k)] = sat
    return out
