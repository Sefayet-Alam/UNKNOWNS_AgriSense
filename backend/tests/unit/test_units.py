"""Gold-number tests for the deterministic area/unit engine."""
from __future__ import annotations

import pytest

from app.engines import units

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------- #
# Fixed conversions
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "value,unit,expected",
    [
        (70, "shotok", 70.0),
        (70, "decimal", 70.0),
        (1, "acre", 100.0),
        (1, "hectare", 247.1),  # engine rounds to 2 dp
        (2, "katha", 3.3),
        (50, "শতক", 50.0),
        (1, "একর", 100.0),
    ],
)
def test_fixed_unit_conversions(value, unit, expected):
    conv = units.convert_area_to_decimal(value, unit)
    assert conv.decimal_value == pytest.approx(expected)
    assert conv.assumed is False


# --------------------------------------------------------------------------- #
# Region-varying units
# --------------------------------------------------------------------------- #
def test_bigha_default_is_assumed_and_flagged():
    conv = units.convert_area_to_decimal(3, "bigha")
    assert conv.decimal_value == pytest.approx(99.0)  # 3 x 33
    assert conv.assumed is True
    assert "ASSUMED" in conv.note


def test_bigha_confirmed_local_factor_overrides_default():
    conv = units.convert_area_to_decimal(3, "বিঘা", local_factor_decimal=33)
    assert conv.decimal_value == pytest.approx(99.0)
    assert conv.assumed is False
    assert "farmer-confirmed" in conv.note


def test_kani_confirmed_factor_scenario_4():
    # EXAMPLE_FLOW #4: farmer confirms 1 kani = 40 shotok in Raozan.
    conv = units.convert_area_to_decimal(2, "kani", local_factor_decimal=40)
    assert conv.decimal_value == pytest.approx(80.0)
    assert conv.assumed is False


def test_kani_without_factor_uses_default_but_assumed():
    conv = units.convert_area_to_decimal(2, "কানি")
    assert conv.decimal_value == pytest.approx(80.0)  # conventional 40
    assert conv.assumed is True


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad", [0, -3, "abc", None])
def test_invalid_values_raise(bad):
    with pytest.raises(units.UnitError):
        units.convert_area_to_decimal(bad, "shotok")


def test_unknown_unit_raises():
    with pytest.raises(units.UnitError):
        units.convert_area_to_decimal(5, "furlong")


def test_negative_local_factor_raises():
    with pytest.raises(units.UnitError):
        units.convert_area_to_decimal(2, "bigha", local_factor_decimal=-1)


def test_decimal_to_hectare_roundtrip():
    assert units.decimal_to_hectare(247.105) == pytest.approx(1.0)
    assert units.decimal_to_hectare(99) == pytest.approx(0.4006, abs=1e-3)


# --------------------------------------------------------------------------- #
# Plausibility (EXAMPLE_FLOW #5)
# --------------------------------------------------------------------------- #
def test_implausible_area_budget_combo_flagged():
    # 300 bigha (9900 decimal) with BDT 60,000 budget.
    warnings = units.area_budget_warnings(9900.0, 60000)
    assert any("unusually large" in w for w in warnings)
    assert any("mistyped" in w or "ratio" in w for w in warnings)


def test_tiny_budget_flagged_as_possible_thousands():
    warnings = units.area_budget_warnings(99.0, 80)
    assert any("80" in w and "thousand" in w.lower() for w in warnings)


def test_reasonable_combo_produces_no_warnings():
    # 99 decimal + BDT 80,000 => ~808 BDT/decimal: plausible.
    assert units.area_budget_warnings(99.0, 80000) == []


def test_none_values_are_silent():
    assert units.area_budget_warnings(None, None) == []
    assert units.area_budget_warnings(99.0, None) == []
