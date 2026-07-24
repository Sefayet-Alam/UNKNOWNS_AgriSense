"""LangChain tools available to the agent."""
from __future__ import annotations

import ast
import json
import logging
import operator
from datetime import datetime, timezone

from typing import Optional

from langchain_core.tools import tool
from sqlalchemy import select

from ..adapters import weather as weather_mod
from ..config import settings
from ..database import AsyncSessionLocal
from ..engines import units as units_mod
from ..models import Farm
from . import memory as memory_mod


log = logging.getLogger("agrisense.tools")


def _emit(stage: str, detail: str) -> None:
    """Emit a custom progress event if a stream writer is active (no-op else).

    Every progress emission is mirrored to the log file so tool activity is
    fully traceable even when no client is streaming.
    """
    log.info("[%s] %s", stage, detail)
    try:
        from langgraph.config import get_stream_writer

        writer = get_stream_writer()
        if writer is not None:
            writer({"stage": stage, "detail": detail})
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Static tools
# --------------------------------------------------------------------------- #
@tool
def get_current_time() -> str:
    """Return the current UTC date and time in ISO 8601 format."""
    _emit("tool", "reading current time")
    return datetime.now(timezone.utc).isoformat()


# Safe arithmetic evaluator -------------------------------------------------- #
_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _safe_eval(node: ast.AST):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Only numeric constants are allowed.")
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        return _ALLOWED_BINOPS[type(node.op)](
            _safe_eval(node.left), _safe_eval(node.right)
        )
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
        return _ALLOWED_UNARYOPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("Unsupported expression.")


@tool
def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression (+, -, *, /, //, %, ** and parentheses)."""
    _emit("tool", f"calculating: {expression}")
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree)
        return str(result)
    except Exception as exc:
        return f"Error: could not evaluate expression ({exc})."


# --------------------------------------------------------------------------- #
# Weather tool (factory — defaults to the farmer's registered location)
# --------------------------------------------------------------------------- #
def build_weather_tool(user):
    """Return a ``get_weather`` tool bound to the user's registered address.

    The tool calls the real Open-Meteo API (keyless). On any failure it
    returns a structured WEATHER_UNAVAILABLE message — the agent must relay
    the outage honestly and never invent forecast values.
    """
    default_place = (
        getattr(user, "upazila_name", "") or getattr(user, "district_name", "") or ""
    )
    default_district = getattr(user, "district_name", "") or None

    @tool
    async def get_weather(location: str = "", days: int = 7) -> str:
        """Fetch the REAL weather forecast (live Open-Meteo API) for a Bangladesh location.

        Args:
            location: Place name (upazila/district/town), e.g. "Tanore". Leave
                empty to use the farmer's registered upazila.
            days: Forecast horizon in days, 1-16 (Open-Meteo maximum is 16).

        Returns daily min/max temperature (C), rainfall (mm), rain probability
        (%), FAO ET0 evapotranspiration (mm) and max wind (km/h), plus a
        summary. These are actual API values — cite them as retrieved data. If
        this tool reports WEATHER_UNAVAILABLE, tell the farmer live weather is
        currently unavailable; NEVER invent forecast numbers.
        """
        place = (location or "").strip() or default_place
        _emit("weather", f"geocoding location: {place}")
        try:
            geo = await weather_mod.geocode_place(
                place,
                district=None if (location or "").strip() else default_district,
            )
            _emit(
                "weather",
                f"fetching {days}-day forecast for {geo['name']} "
                f"({geo['latitude']}, {geo['longitude']})",
            )
            forecast = await weather_mod.fetch_forecast(
                geo["latitude"], geo["longitude"], days
            )
        except weather_mod.WeatherError as exc:
            return (
                f"WEATHER_UNAVAILABLE: {exc}. Live weather could not be "
                "fetched. Tell the farmer honestly that live weather is "
                "unavailable right now and do NOT invent forecast values."
            )
        payload = {"location": geo, **forecast}
        return json.dumps(payload, ensure_ascii=False)

    return get_weather


# --------------------------------------------------------------------------- #
# Farm profile tools (factory — all queries scoped to the authenticated user)
# --------------------------------------------------------------------------- #
REQUIRED_SLOTS = ("location", "farm_size", "water_availability", "budget", "season")

_SEASON_ALIASES = {
    "rabi": "rabi",
    "robi": "rabi",
    "রবি": "rabi",
    "winter": "rabi",
    "শীত": "rabi",
    "shit": "rabi",
    "sheet": "rabi",
    "kharif-1": "kharif-1",
    "kharif1": "kharif-1",
    "summer": "kharif-1",
    "kharif-2": "kharif-2",
    "kharif2": "kharif-2",
    "monsoon": "kharif-2",
    "বর্ষা": "kharif-2",
}


def _normalize_season(raw: str) -> str:
    key = (raw or "").strip().lower()
    return _SEASON_ALIASES.get(key, key)


def _missing_slots(farm: Farm) -> list[str]:
    missing = []
    if not farm.upazila_name and not (farm.latitude and farm.longitude):
        missing.append("location")
    if farm.area_decimal is None:
        missing.append("farm_size")
    if farm.irrigation_available is None:
        missing.append("water_availability")
    if farm.budget_bdt is None:
        missing.append("budget")
    if not farm.season:
        missing.append("season")
    return missing


def _farm_payload(farm: Farm, warnings: Optional[list[str]] = None) -> dict:
    missing = _missing_slots(farm)
    return {
        "farm_id": farm.id,
        "name": farm.name,
        "is_active": farm.is_active,
        "location": {
            "division": farm.division_name,
            "district": farm.district_name,
            "upazila": farm.upazila_name,
            "upazila_code": farm.upazila_code,
            "union": farm.union_name,
            "latitude": farm.latitude,
            "longitude": farm.longitude,
        },
        "area": {
            "area_decimal": farm.area_decimal,
            "original_value": farm.original_area_value,
            "original_unit": farm.original_area_unit,
            "conversion_note": farm.area_conversion_note,
        },
        "land_type": farm.land_type,
        "soil_texture": farm.soil_texture,
        "soil_test": farm.soil_test,
        "irrigation_available": farm.irrigation_available,
        "water_source": farm.water_source,
        "budget_bdt": farm.budget_bdt,
        "season": farm.season,
        "previous_crop": farm.previous_crop,
        "risk_tolerance": farm.risk_tolerance,
        "preferred_crops": farm.preferred_crops or [],
        "excluded_crops": farm.excluded_crops or [],
        "phase": farm.phase,
        "missing_required_fields": missing,
        "warnings": warnings or [],
    }


async def _get_or_create_active_farm(session, user) -> Farm:
    result = await session.execute(
        select(Farm)
        .where(Farm.user_id == user.id, Farm.is_active.is_(True))
        .order_by(Farm.id)
        .limit(1)
    )
    farm = result.scalar_one_or_none()
    if farm is not None:
        return farm
    # First contact: prefill from the registration address (a DEFAULT the
    # agent must confirm — the actual field may be elsewhere).
    farm = Farm(
        user_id=user.id,
        name=f"{user.upazila_name or 'My'} Farm".strip(),
        is_active=True,
        division_name=user.division_name or "",
        division_code=user.division_code or "",
        district_name=user.district_name or "",
        district_code=user.district_code or "",
        upazila_name=user.upazila_name or "",
        upazila_code=user.upazila_code or "",
        preferred_crops=[],
        excluded_crops=[],
    )
    session.add(farm)
    await session.commit()
    await session.refresh(farm)
    return farm


def build_farm_tools(user):
    """Farm profile tools bound to the authenticated user.

    SECURITY: every query filters by ``user_id == user.id`` taken from the
    authenticated request — never from model-supplied arguments. The LLM can
    only ever see/modify farms belonging to this user.
    """

    @tool
    async def get_farm_profile() -> str:
        """Get the active farm's saved profile.

        Returns the farm's location, area, soil, water, budget, season,
        preferences, and — critically — ``missing_required_fields``: the slots
        still needed before crop planning (location, farm_size,
        water_availability, budget, season). Call this FIRST in a conversation
        to see what is already known so you never re-ask the farmer.
        """
        _emit("farm", "loading farm profile")
        async with AsyncSessionLocal() as session:
            farm = await _get_or_create_active_farm(session, user)
            return json.dumps(_farm_payload(farm), ensure_ascii=False)

    @tool
    async def update_farm_profile(
        name: Optional[str] = None,
        area_value: Optional[float] = None,
        area_unit: Optional[str] = None,
        local_unit_factor_decimal: Optional[float] = None,
        land_type: Optional[str] = None,
        soil_texture: Optional[str] = None,
        irrigation_available: Optional[bool] = None,
        water_source: Optional[str] = None,
        budget_bdt: Optional[int] = None,
        season: Optional[str] = None,
        previous_crop: Optional[str] = None,
        risk_tolerance: Optional[str] = None,
        add_preferred_crops: Optional[list[str]] = None,
        add_excluded_crops: Optional[list[str]] = None,
        division_name: Optional[str] = None,
        district_name: Optional[str] = None,
        upazila_name: Optional[str] = None,
        union_name: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> str:
        """Save facts the farmer EXPLICITLY stated about the active farm.

        Pass only fields the farmer actually said — never guess or infer.
        Area: pass area_value + area_unit (decimal/shotok, katha, bigha, kani,
        acre, hectare). bigha/kani vary by region — if the farmer confirmed the
        local size (e.g. "1 kani = 40 shotok here"), pass it as
        local_unit_factor_decimal; otherwise a conventional default is used and
        the result is marked ASSUMED — confirm it with the farmer.
        budget_bdt must be full taka (e.g. "80k" -> 80000, "২ লাখ" -> 200000).
        season: rabi / kharif-1 / kharif-2 (winter -> rabi).
        If the farmer's field is in a different place than registered, pass the
        new upazila_name/district_name — codes are re-resolved automatically.
        Returns the updated profile with missing_required_fields and any
        plausibility warnings — relay warnings to the farmer and confirm
        before planning.
        """
        _emit("farm", "updating farm profile")
        warnings: list[str] = []
        async with AsyncSessionLocal() as session:
            farm = await _get_or_create_active_farm(session, user)

            if name is not None:
                farm.name = name.strip()[:120]

            # ---- location ------------------------------------------------ #
            location_changed = False
            if division_name is not None and division_name.strip() != farm.division_name:
                farm.division_name = division_name.strip()
                farm.division_code = ""
                location_changed = True
            if district_name is not None and district_name.strip() != farm.district_name:
                farm.district_name = district_name.strip()
                farm.district_code = ""
                location_changed = True
            if upazila_name is not None and upazila_name.strip() != farm.upazila_name:
                farm.upazila_name = upazila_name.strip()
                farm.upazila_code = ""
                location_changed = True
            if union_name is not None:
                farm.union_name = union_name.strip()
                farm.union_geocode = ""
            if location_changed:
                farm.union_name = farm.union_name  # unions stay if re-stated above
                warnings.append(
                    "farm location changed — stale geocodes cleared; land "
                    "context must be re-fetched"
                )
            if latitude is not None:
                farm.latitude = float(latitude)
            if longitude is not None:
                farm.longitude = float(longitude)

            # ---- area (deterministic conversion) ------------------------- #
            if (
                area_value is None
                and local_unit_factor_decimal is not None
                and farm.original_area_value is not None
                and farm.original_area_unit
            ):
                # Farmer confirmed the local factor for the ALREADY-stated
                # area (e.g. "৩৩ শতক ধরে নেন") — reconvert the stored value.
                area_value = farm.original_area_value
                area_unit = farm.original_area_unit
            if area_value is not None:
                if not area_unit:
                    return json.dumps(
                        {
                            "error": (
                                "area_unit is required with area_value — ask "
                                "the farmer: decimal/shotok, katha, bigha, "
                                "kani, acre or hectare?"
                            )
                        },
                        ensure_ascii=False,
                    )
                try:
                    conv = units_mod.convert_area_to_decimal(
                        area_value, area_unit, local_unit_factor_decimal
                    )
                except units_mod.UnitError as exc:
                    return json.dumps({"error": str(exc)}, ensure_ascii=False)
                farm.area_decimal = conv.decimal_value
                farm.original_area_value = float(area_value)
                farm.original_area_unit = conv.unit
                farm.area_conversion_note = conv.note
                if conv.assumed:
                    warnings.append(conv.note)

            # ---- simple fields ------------------------------------------- #
            if land_type is not None:
                farm.land_type = land_type.strip()[:40]
            if soil_texture is not None:
                farm.soil_texture = soil_texture.strip()[:40]
            if irrigation_available is not None:
                farm.irrigation_available = bool(irrigation_available)
            if water_source is not None:
                farm.water_source = water_source.strip()[:80]
            if budget_bdt is not None:
                if budget_bdt <= 0:
                    return json.dumps(
                        {"error": "budget must be greater than zero"},
                        ensure_ascii=False,
                    )
                farm.budget_bdt = int(budget_bdt)
            if season is not None:
                farm.season = _normalize_season(season)[:20]
            if previous_crop is not None:
                farm.previous_crop = previous_crop.strip()[:60]
            if risk_tolerance is not None:
                farm.risk_tolerance = risk_tolerance.strip().lower()[:12]
            if add_preferred_crops:
                current = list(farm.preferred_crops or [])
                for crop in add_preferred_crops:
                    c = crop.strip().lower()
                    if c and c not in current:
                        current.append(c)
                farm.preferred_crops = current
            if add_excluded_crops:
                current = list(farm.excluded_crops or [])
                for crop in add_excluded_crops:
                    c = crop.strip().lower()
                    if c and c not in current:
                        current.append(c)
                farm.excluded_crops = current

            # ---- plausibility + phase ------------------------------------ #
            warnings.extend(
                units_mod.area_budget_warnings(farm.area_decimal, farm.budget_bdt)
            )
            farm.phase = "ready_for_planning" if not _missing_slots(farm) else "intake"

            await session.commit()
            await session.refresh(farm)
            return json.dumps(_farm_payload(farm, warnings), ensure_ascii=False)

    @tool
    async def list_farms() -> str:
        """List all of the farmer's saved farms (id, name, location, area,
        active flag). Use when the farmer mentions another field or asks about
        a previous farm/plan."""
        _emit("farm", "listing farms")
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Farm).where(Farm.user_id == user.id).order_by(Farm.id)
            )
            farms = result.scalars().all()
            return json.dumps(
                [
                    {
                        "farm_id": f.id,
                        "name": f.name,
                        "upazila": f.upazila_name,
                        "district": f.district_name,
                        "area_decimal": f.area_decimal,
                        "is_active": f.is_active,
                        "phase": f.phase,
                    }
                    for f in farms
                ],
                ensure_ascii=False,
            )

    @tool
    async def select_farm(farm_id: int) -> str:
        """Switch the active farm to one of the farmer's own farms by id
        (see list_farms). All subsequent profile/planning work applies to it."""
        _emit("farm", f"selecting farm {farm_id}")
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Farm).where(Farm.user_id == user.id, Farm.id == farm_id)
            )
            farm = result.scalar_one_or_none()
            if farm is None:
                return json.dumps(
                    {"error": f"no farm with id {farm_id} belongs to this user"},
                    ensure_ascii=False,
                )
            all_farms = (
                await session.execute(select(Farm).where(Farm.user_id == user.id))
            ).scalars().all()
            for f in all_farms:
                f.is_active = f.id == farm.id
            await session.commit()
            await session.refresh(farm)
            return json.dumps(_farm_payload(farm), ensure_ascii=False)

    @tool
    async def create_farm(
        name: str,
        upazila_name: Optional[str] = None,
        district_name: Optional[str] = None,
        division_name: Optional[str] = None,
    ) -> str:
        """Create an additional farm for the farmer (e.g. a second field in a
        different place) and make it the active one."""
        _emit("farm", f"creating farm: {name}")
        async with AsyncSessionLocal() as session:
            all_farms = (
                await session.execute(select(Farm).where(Farm.user_id == user.id))
            ).scalars().all()
            for f in all_farms:
                f.is_active = False
            farm = Farm(
                user_id=user.id,
                name=name.strip()[:120] or "New Farm",
                is_active=True,
                division_name=(division_name or "").strip(),
                district_name=(district_name or "").strip(),
                upazila_name=(upazila_name or "").strip(),
                preferred_crops=[],
                excluded_crops=[],
            )
            session.add(farm)
            await session.commit()
            await session.refresh(farm)
            return json.dumps(_farm_payload(farm), ensure_ascii=False)

    return [get_farm_profile, update_farm_profile, list_farms, select_farm, create_farm]


# --------------------------------------------------------------------------- #
# User-scoped memory tools (factory)
# --------------------------------------------------------------------------- #
def build_memory_tools(user_id: int, db=None):
    """Return async ``save_memory`` / ``recall_memory`` tools bound to a user.

    Each tool opens a *fresh* AsyncSession per call so concurrent tool calls
    never share a session. The ``db`` argument is accepted for call-site
    symmetry but intentionally not reused for the DB write/read.
    """

    @tool
    async def save_memory(content: str) -> str:
        """Store a durable fact/preference about the user for future chats."""
        _emit("tool", "saving to long-term memory")
        async with AsyncSessionLocal() as session:
            await memory_mod.save_memory(session, user_id, content)
        return "Saved to long-term memory."

    @tool
    async def recall_memory(query: str) -> str:
        """Recall durable facts about the user relevant to a query."""
        _emit("tool", "recalling long-term memory")
        async with AsyncSessionLocal() as session:
            hits = await memory_mod.recall_memory(
                session, user_id, query, settings.MEMORY_TOP_K
            )
        if not hits:
            return "No relevant memories found."
        return "\n".join(f"- {h}" for h in hits)

    return [save_memory, recall_memory]


def build_static_tools():
    return [get_current_time, calculator]
