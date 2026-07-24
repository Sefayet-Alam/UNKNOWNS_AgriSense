"""Deterministic land-area normalization + plausibility checks.

Everything is normalized to **decimals** (= shotok/shatak, 1/100 acre), the
unit rural Bangladesh actually transacts in. Hectare conversion for agronomic
rates lives at the engine boundary (1 ha = 247.105 decimal).

Region-varying units (bigha, kani) are the classic data-corruption trap
(docs/EXAMPLE_FLOW.md #1, #4): a bigha is 33 shotok in most of Rajshahi but
differs elsewhere, and a kani ranges 20-120 shotok by district. Policy:
- Without a farmer-confirmed factor we convert with the conventional default
  but mark the conversion ``assumed`` — the agent must ask for confirmation.
- A confirmed ``local_factor_decimal`` overrides the default and is recorded.
"""
from __future__ import annotations

from dataclasses import dataclass

DECIMAL_PER_HECTARE = 247.105
DECIMAL_PER_ACRE = 100.0

# Fixed units -> decimals per 1 unit.
FIXED_UNITS: dict[str, float] = {
    "decimal": 1.0,
    "shotok": 1.0,
    "shatak": 1.0,
    "shatangsha": 1.0,
    "katha": 1.65,  # conventional 720 sq ft katha
    "acre": DECIMAL_PER_ACRE,
    "hectare": DECIMAL_PER_HECTARE,
    "ha": DECIMAL_PER_HECTARE,
}

# Region-varying units -> conventional default (decimals per 1 unit).
VARIABLE_UNITS: dict[str, float] = {
    "bigha": 33.0,
    "kani": 40.0,
}

# Bengali / Banglish aliases -> canonical unit name.
UNIT_ALIASES: dict[str, str] = {
    "শতক": "shotok",
    "শতাংশ": "shotok",
    "sotok": "shotok",
    "shotangsho": "shotok",
    "ডেসিমাল": "decimal",
    "বিঘা": "bigha",
    "biga": "bigha",
    "bigha": "bigha",
    "কাঠা": "katha",
    "kata": "katha",
    "কানি": "kani",
    "একর": "acre",
    "ekor": "acre",
    "হেক্টর": "hectare",
}


class UnitError(ValueError):
    """Raised for unusable area values/units."""


@dataclass
class AreaConversion:
    decimal_value: float
    unit: str  # canonical unit
    factor_decimal_per_unit: float
    assumed: bool  # True => default factor used for a region-varying unit
    note: str


def canonical_unit(unit: str) -> str:
    key = (unit or "").strip().lower()
    key = UNIT_ALIASES.get(key, key)
    if key in FIXED_UNITS or key in VARIABLE_UNITS:
        return key
    raise UnitError(f"unknown area unit: {unit!r}")


def convert_area_to_decimal(
    value: float,
    unit: str,
    local_factor_decimal: float | None = None,
) -> AreaConversion:
    """Convert an area to decimals.

    ``local_factor_decimal`` is the farmer-confirmed decimals-per-unit for
    region-varying units (e.g. "আমাদের এখানে ৪০ শতক এক কানি" -> 40).
    """
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise UnitError(f"area value is not a number: {value!r}") from exc
    if value <= 0:
        raise UnitError("area must be greater than zero")

    cu = canonical_unit(unit)

    if cu in FIXED_UNITS:
        factor = FIXED_UNITS[cu]
        return AreaConversion(
            decimal_value=round(value * factor, 2),
            unit=cu,
            factor_decimal_per_unit=factor,
            assumed=False,
            note=f"1 {cu} = {factor} decimal (fixed)",
        )

    # Region-varying unit.
    if local_factor_decimal is not None:
        factor = float(local_factor_decimal)
        if factor <= 0:
            raise UnitError("local conversion factor must be positive")
        return AreaConversion(
            decimal_value=round(value * factor, 2),
            unit=cu,
            factor_decimal_per_unit=factor,
            assumed=False,
            note=f"farmer-confirmed: 1 {cu} = {factor} decimal",
        )

    default = VARIABLE_UNITS[cu]
    return AreaConversion(
        decimal_value=round(value * default, 2),
        unit=cu,
        factor_decimal_per_unit=default,
        assumed=True,
        note=(
            f"ASSUMED conventional 1 {cu} = {default} decimal — {cu} varies "
            "by region; confirm the local conversion with the farmer"
        ),
    )


def decimal_to_hectare(area_decimal: float) -> float:
    return round(area_decimal / DECIMAL_PER_HECTARE, 4)


# --------------------------------------------------------------------------- #
# Plausibility checks (docs/EXAMPLE_FLOW.md #5)
# --------------------------------------------------------------------------- #
# Very rough rabi-season cultivation cost band per decimal (BDT). Derived from
# seeded cost catalog ranges (mustard low ~400/dec, potato high ~1500/dec).
_MIN_COST_PER_DECIMAL = 200.0
_LARGE_AREA_DECIMAL = 3000.0  # ~30 acres — unusually large for a smallholder


def area_budget_warnings(
    area_decimal: float | None, budget_bdt: float | None
) -> list[str]:
    """Deterministic red flags for probable input errors. Never blocks; the
    agent must relay these and ask before planning."""
    warnings: list[str] = []
    if area_decimal is not None and area_decimal > _LARGE_AREA_DECIMAL:
        warnings.append(
            f"area {area_decimal:.0f} decimal (~{area_decimal / 100:.0f} acre) "
            "is unusually large for a smallholder — confirm it is not a typo"
        )
    if budget_bdt is not None and 0 < budget_bdt < 1000:
        warnings.append(
            f"budget BDT {budget_bdt:.0f} is implausibly small — the farmer "
            "may have meant thousands (e.g. '80k' = 80,000)"
        )
    if (
        area_decimal is not None
        and budget_bdt is not None
        and area_decimal > 0
        and budget_bdt > 0
    ):
        per_decimal = budget_bdt / area_decimal
        if per_decimal < _MIN_COST_PER_DECIMAL:
            warnings.append(
                f"budget/area ratio BDT {per_decimal:.0f}/decimal is far below "
                f"typical cultivation cost (≥{_MIN_COST_PER_DECIMAL:.0f}/decimal) "
                "— area or budget may be mistyped; confirm before planning"
            )
    return warnings
