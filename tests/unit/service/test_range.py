from datetime import datetime, timezone

import pytest

from liquidetl.service import LiquidService
from liquidetl.service.range import get_block_range_for_date

DAY = "2020-01-02"
DAY_START = int(datetime(2020, 1, 2, tzinfo=timezone.utc).timestamp())
HOUR = 3600


def _chain(first_offset_hours: int, count: int):
    """A synthetic hourly chain; returns (get_ts, head_height)."""
    ts = [DAY_START + (first_offset_hours + i) * HOUR for i in range(count)]
    return (lambda h: ts[h]), len(ts) - 1


def test_default_end_hour_24_does_not_crash_and_covers_whole_day():
    # Regression for the end_hour=24 -> datetime.replace(hour=24) ValueError.
    get_ts, head = _chain(first_offset_hours=-5, count=48)  # heights 0..47
    first, last = get_block_range_for_date(get_ts, head, DAY)  # default start=0, end=24
    # Offsets in [0, 24) => heights i where (-5 + i) in [0, 24) => i in [5, 29)
    assert (first, last) == (5, 28)


def test_partial_day_hour_window():
    get_ts, head = _chain(first_offset_hours=-5, count=48)
    first, last = get_block_range_for_date(get_ts, head, DAY, start_hour=6, end_hour=12)
    # Offsets in [6, 12) => i in [11, 17)
    assert (first, last) == (11, 16)


def test_future_date_raises_instead_of_returning_whole_chain():
    # Every block predates the requested date's window.
    get_ts, head = _chain(first_offset_hours=-100, count=50)
    with pytest.raises(ValueError):
        get_block_range_for_date(get_ts, head, DAY)


def test_pre_genesis_date_raises():
    # Every block is after the requested date's window.
    get_ts, head = _chain(first_offset_hours=48, count=50)
    with pytest.raises(ValueError):
        get_block_range_for_date(get_ts, head, DAY)


def test_gap_between_blocks_raises():
    # One block just before the window, one just after: nothing inside.
    ts = [DAY_START - 10, DAY_START + 24 * HOUR + 10]
    with pytest.raises(ValueError):
        get_block_range_for_date((lambda h: ts[h]), len(ts) - 1, DAY)


class _StubRpc:
    """Node whose block ts increases by one hour per height, spanning DAY."""

    def getblockcount(self) -> int:
        return 47

    def getblockhash(self, height: int) -> str:
        return f"h{height}"

    def getblock(self, block_hash: str, verbosity: int = 3):
        h = int(block_hash[1:])
        return {"hash": block_hash, "height": h, "time": DAY_START + (-5 + h) * HOUR, "tx": []}


def test_service_default_hours_end_to_end():
    # T4: exercise LiquidService.get_block_range_for_date with the end_hour=24 default.
    svc = LiquidService(_StubRpc())
    first, last = svc.get_block_range_for_date(DAY)
    assert (first, last) == (5, 28)
