from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional


SATOSHI_FACTOR = Decimal("100000000")


def to_satoshi(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal):
        d = value
    else:
        try:
            d = Decimal(str(value))
        except Exception:
            return None
    q = d * SATOSHI_FACTOR
    try:
        if q == q.to_integral_value():
            return int(q)
    except Exception:
        pass
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

