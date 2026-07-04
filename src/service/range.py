from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable, Optional, Tuple


def get_block_range_for_date(
    get_block_timestamp: Callable[[int], int],
    head_height: int,
    date_str: str,
    start_hour: int = 0,
    end_hour: int = 24,
) -> Tuple[int, int]:
    """Return the inclusive [first, last] block heights whose timestamps fall in the
    half-open window [start, end) of the given UTC date.

    ``end_hour`` may be 24 to mean midnight of the next day (the common whole-day case).
    Raises ValueError if no block falls in the window, instead of returning the whole chain.
    """
    day = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    dt_start = day + timedelta(hours=start_hour)
    dt_end = day + timedelta(hours=end_hour)
    start_ts = int(dt_start.timestamp())
    end_ts = int(dt_end.timestamp())

    if head_height < 0:
        raise ValueError(f"no blocks found for {date_str}: empty chain")

    first = _binary_search_first_ge(get_block_timestamp, 0, head_height, start_ts)
    last = _binary_search_last_lt(get_block_timestamp, 0, head_height, end_ts)

    if first is None or last is None or first > last:
        raise ValueError(
            f"no blocks found for {date_str} in window "
            f"[{start_ts}, {end_ts}) (head height {head_height})"
        )
    return first, last


def _binary_search_first_ge(
    get_ts: Callable[[int], int], lo: int, hi: int, ts_threshold: int
) -> Optional[int]:
    """Smallest height in [lo, hi] with ts >= threshold, or None if no such height."""
    first: Optional[int] = None
    while lo <= hi:
        mid = (lo + hi) // 2
        ts = int(get_ts(mid))
        if ts < ts_threshold:
            lo = mid + 1
        else:
            first = mid
            hi = mid - 1
    return first


def _binary_search_last_lt(
    get_ts: Callable[[int], int], lo: int, hi: int, ts_threshold: int
) -> Optional[int]:
    """Largest height in [lo, hi] with ts < threshold, or None if no such height."""
    last: Optional[int] = None
    while lo <= hi:
        mid = (lo + hi) // 2
        ts = int(get_ts(mid))
        if ts >= ts_threshold:
            hi = mid - 1
        else:
            last = mid
            lo = mid + 1
    return last
