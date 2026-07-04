from decimal import Decimal

from liquidetl.utils.amounts import amounts_map_to_satoshi_map, to_satoshi


def test_none_and_bool_are_not_amounts():
    assert to_satoshi(None) is None
    assert to_satoshi(True) is None
    assert to_satoshi(False) is None


def test_exact_eight_decimal_strings():
    assert to_satoshi("0.00000001") == 1
    assert to_satoshi("1.00000000") == 100_000_000
    assert to_satoshi(Decimal("1.5")) == 150_000_000
    assert to_satoshi("0") == 0


def test_int_is_whole_coin_not_already_satoshi():
    # Regression for the old `isinstance(value, int): return value` short-circuit.
    assert to_satoshi(1) == 100_000_000
    assert to_satoshi(0) == 0


def test_float_path():
    assert to_satoshi(0.1) == 10_000_000
    assert to_satoshi(2.0) == 200_000_000


def test_sub_satoshi_is_rejected_not_truncated():
    # Old code truncated toward zero; a money field must not silently round.
    assert to_satoshi("0.000000005") is None
    assert to_satoshi("1.999999999") is None


def test_max_supply_magnitude():
    # 21,000,000 BTC in satoshi fits and stays exact.
    assert to_satoshi("21000000") == 2_100_000_000_000_000


def test_unparseable_and_non_finite():
    assert to_satoshi("not-a-number") is None
    assert to_satoshi("nan") is None
    assert to_satoshi("inf") is None


def test_amounts_map_skips_invalid_values():
    m = {"a": "0.00000001", "b": None, "c": "0.000000005", "d": 2}
    assert amounts_map_to_satoshi_map(m) == {"a": 1, "d": 200_000_000}
    assert amounts_map_to_satoshi_map("nope") == {}
