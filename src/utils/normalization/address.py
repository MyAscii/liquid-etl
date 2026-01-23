from __future__ import annotations

from typing import Any, Optional


def pick_address(spk: Any) -> Optional[str]:
    if not isinstance(spk, dict):
        return None
    addrs = spk.get("addresses")
    if isinstance(addrs, list) and addrs:
        return addrs[0]
    addr = spk.get("address")
    if isinstance(addr, str) and addr:
        return addr
    return None
