from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Tuple


def get_block_range_for_date(
    get_block_timestamp: Callable[[int], int],
    head_height: int,
    date_str: str,
    start_hour: int = 0,
    end_hour: int = 24,
) -> Tuple[int, int]:
    dt_start = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=start_hour, tzinfo=timezone.utc)
    dt_end = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=end_hour, tzinfo=timezone.utc)
    start_ts = int(dt_start.timestamp())
    end_ts = int(dt_end.timestamp())

    first = _binary_search_first_ge(get_block_timestamp, 0, head_height, start_ts)
    last = _binary_search_last_lt(get_block_timestamp, first, head_height, end_ts)
    return first, last


def _binary_search_first_ge(
    get_ts: Callable[[int], int], lo: int, hi: int, ts_threshold: int
) -> int:
    first = lo
    while lo <= hi:
        mid = (lo + hi) // 2
        ts = int(get_ts(mid))
        if ts < ts_threshold:
            lo = mid + 1
        else:
            first = mid
            hi = mid - 1
    return first


def _binary_search_last_lt(get_ts: Callable[[int], int], lo: int, hi: int, ts_threshold: int) -> int:
    last = hi
    while lo <= hi:
        mid = (lo + hi) // 2
        ts = int(get_ts(mid))
        if ts >= ts_threshold:
            hi = mid - 1
        else:
            last = mid
            lo = mid + 1
    return last

