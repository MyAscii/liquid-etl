from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple


def _parse_conf(conf_path: Path) -> Dict[str, str]:
    items: Dict[str, str] = {}
    if not conf_path.exists():
        return items
    for raw in conf_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        items[k.strip()] = v.strip()
    return items


def _read_cookie(cookie_path: Path) -> Optional[Tuple[str, str]]:
    if not cookie_path.exists():
        return None
    try:
        raw = cookie_path.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception:
        return None
    if ":" not in raw:
        return None
    user, pwd = raw.split(":", 1)
    user = user.strip()
    pwd = pwd.strip()
    if not user or not pwd:
        return None
    return user, pwd


def resolve_rpc_auth(datadir: str) -> Optional[Tuple[str, str]]:
    dd = Path(datadir)
    conf = _parse_conf(dd / "elements.conf")
    chain = conf.get("chain")

    if chain:
        cookie = _read_cookie(dd / chain / ".cookie")
        if cookie:
            return cookie

    cookie = _read_cookie(dd / ".cookie")
    if cookie:
        return cookie

    user = conf.get("rpcuser")
    pwd = conf.get("rpcpassword")
    if user and pwd:
        return user, pwd

    return None

