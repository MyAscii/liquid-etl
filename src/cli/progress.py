from __future__ import annotations


def fmt_eta(seconds: float) -> str:
    if seconds != seconds or seconds == float("inf") or seconds < 0:
        return "?:??"
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:d}:{s:02d}"


def render_bar(done: int, total: int, width: int = 30) -> str:
    frac = done / total if total else 1.0
    filled = int(frac * width)
    if filled >= width:
        return "=" * width
    return ("=" * filled) + ">" + ("." * (width - filled - 1))
