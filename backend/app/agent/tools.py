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

from .. import geo as geo_mod
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

    Coordinate resolution is OFFLINE-FIRST: the farmer's active farm (or
    registration address) already carries lat/lon from the bundled gazetteer
    (union centroid), and admin-unit names resolve through the same bundle —
    the flaky live geocoder is only the last resort for non-admin place names.
    The forecast itself calls the real Open-Meteo API (keyless). On failure a
    structured WEATHER_UNAVAILABLE message is returned — the agent must relay
    the outage honestly and never invent forecast values.
    """

    async def _default_location() -> Optional[dict]:
        """The farmer's own field: farm lat/lon, else gazetteer centroid."""
        async with AsyncSessionLocal() as session:
            farm = await _get_or_create_active_farm(session, user)
        label = farm.union_name or farm.upazila_name or farm.district_name
        if farm.latitude is not None and farm.longitude is not None:
            return {
                "name": label or "farm",
                "latitude": farm.latitude,
                "longitude": farm.longitude,
                "admin1": farm.division_name,
                "admin2": farm.district_name,
                "geocode_source": "farm_profile",
            }
        resolved = geo_mod.resolve_coords(
            union_code=farm.union_geocode or getattr(user, "union_code", ""),
            upazila_code=farm.upazila_code or getattr(user, "upazila_code", ""),
            district_code=farm.district_code or getattr(user, "district_code", ""),
        )
        if resolved:
            return {
                "name": label or resolved["name"],
                "latitude": resolved["lat"],
                "longitude": resolved["lon"],
                "admin1": farm.division_name,
                "admin2": farm.district_name,
                "geocode_source": f"gazetteer_{resolved['level']}_centroid",
            }
        return None

    @tool
    async def get_weather(
        location: str = "",
        days: int = 7,
        past_days: int = 0,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> str:
        """Fetch REAL weather (live Open-Meteo API) for a Bangladesh location —
        forecast AND recent past.

        Args:
            location: Place name (union/upazila/district/town), e.g. "Tanore".
                Leave empty to use the farmer's own farm location — preferred,
                it always resolves to exact coordinates.
            days: Forecast horizon in days, 0-16 (Open-Meteo maximum is 16;
                0 = no forecast, past only). A negative value is treated as
                past_days (e.g. -7 = last 7 days, no forecast).
            past_days: How many RECENT PAST days to include (0-92). Use for
                questions like "how much rain fell last week?" — past rows are
                recorded weather (kind=past) with their own past_summary;
                never guess historical weather.
            latitude: Optional explicit latitude — overrides location lookup.
            longitude: Optional explicit longitude — overrides location lookup.

        Returns daily min/max temperature (C), rainfall (mm), rain probability
        (%), FAO ET0 evapotranspiration (mm) and max wind (km/h), plus
        summaries (forecast summary + past_summary when past days requested).
        These are actual API values — cite them as retrieved data. If this
        tool reports WEATHER_UNAVAILABLE, tell the farmer live weather is
        currently unavailable; NEVER invent weather numbers, past or future.
        If a location name is not understood, retry once passing
        latitude/longitude explicitly.
        """
        # Tolerate the negative-days convention: -7 means "last 7 days".
        if days < 0:
            past_days = max(past_days, -days)
            days = 0
        place = (location or "").strip()
        loc: Optional[dict] = None
        try:
            if latitude is not None and longitude is not None:
                loc = {
                    "name": place or f"({latitude}, {longitude})",
                    "latitude": float(latitude),
                    "longitude": float(longitude),
                    "admin1": "",
                    "admin2": "",
                    "geocode_source": "explicit_coordinates",
                }
            elif not place:
                _emit("weather", "resolving farmer's farm coordinates")
                loc = await _default_location()
                if loc is None:
                    return (
                        "WEATHER_UNAVAILABLE: the farm has no saved location "
                        "yet. Ask the farmer for their upazila/union first "
                        "(or pass a location name)."
                    )
            else:
                # Named place: bundled gazetteer first (all unions/upazilas/
                # districts, offline + exact), live geocoder only after that.
                row = geo_mod.find_place(place)
                if row is not None:
                    loc = {
                        "name": row.get("name_en") or place,
                        "latitude": row["lat"],
                        "longitude": row["lon"],
                        "admin1": "",
                        "admin2": "",
                        "geocode_source": f"gazetteer_{row['level']}_centroid",
                    }
                else:
                    # Explicit place -> no registered-district bias (the whole
                    # point of naming a place is that it may be elsewhere).
                    _emit("weather", f"geocoding location: {place}")
                    loc = await weather_mod.geocode_place(place, district=None)
            span = f"{days}-day forecast" if days else ""
            if past_days:
                span = f"past {past_days} days" + (f" + {span}" if span else "")
            _emit(
                "weather",
                f"fetching {span or 'forecast'} for {loc['name']} "
                f"({loc['latitude']}, {loc['longitude']})",
            )
            forecast = await weather_mod.fetch_forecast(
                loc["latitude"], loc["longitude"], days, past_days=past_days
            )
        except weather_mod.WeatherError as exc:
            return (
                f"WEATHER_UNAVAILABLE: {exc}. Live weather could not be "
                "fetched. Tell the farmer honestly that live weather is "
                "unavailable right now and do NOT invent forecast values."
            )
        payload = {"location": loc, **forecast}
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
            "union_geocode": farm.union_geocode,
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


def _re_resolve_farm_geo(farm: Farm, warnings: list[str]) -> None:
    """Re-attach geocodes + centroid coordinates after a name-based location edit.

    Matches farmer-stated names against the bundled CZIS/BBS gazetteer:
    upazila name -> codes for upazila/district/division; union name (within
    the upazila) -> union geocode. Then pins lat/lon to the most specific
    centroid available. Unmatched names keep empty codes — get_weather then
    falls back to the live geocoder for that place name.
    """
    if not farm.upazila_code and farm.upazila_name:
        row = geo_mod.find_upazila_by_name(
            farm.upazila_name, farm.district_code or None
        )
        if row is None:
            row = geo_mod.find_upazila_by_name(farm.upazila_name)
        if row is not None:
            farm.upazila_code = row["code"]
            farm.upazila_name = row["name_en"]
            district = geo_mod.get("district", row["district_code"])
            if district is not None:
                farm.district_code = district["code"]
                farm.district_name = district["name_en"]
            division = geo_mod.get("division", row["division_code"])
            if division is not None:
                farm.division_code = division["code"]
                farm.division_name = division["name_en"]
    if not farm.union_geocode and farm.union_name and farm.upazila_code:
        row = geo_mod.find_union_by_name(farm.union_name, farm.upazila_code)
        if row is not None:
            farm.union_geocode = row["code"]
            farm.union_name = row["name_en"]
    resolved = geo_mod.resolve_coords(
        union_code=farm.union_geocode or "",
        upazila_code=farm.upazila_code or "",
        district_code=farm.district_code or "",
    )
    if resolved:
        farm.latitude = resolved["lat"]
        farm.longitude = resolved["lon"]
    elif farm.latitude is None:
        warnings.append(
            "location not found in the gazetteer — weather will fall back to "
            "live geocoding of the place name; double-check the spelling"
        )


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
    # agent must confirm — the actual field may be elsewhere). The union
    # centroid from the bundled gazetteer pins the farm to coordinates so
    # weather never depends on live geocoding.
    resolved = geo_mod.resolve_coords(
        union_code=getattr(user, "union_code", "") or "",
        upazila_code=user.upazila_code or "",
        district_code=user.district_code or "",
    )
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
        union_name=getattr(user, "union_name", "") or "",
        union_geocode=getattr(user, "union_code", "") or "",
        latitude=resolved["lat"] if resolved else None,
        longitude=resolved["lon"] if resolved else None,
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
            union_changed = False
            if union_name is not None and union_name.strip() != farm.union_name:
                farm.union_name = union_name.strip()
                farm.union_geocode = ""
                union_changed = True
            if location_changed:
                # Stale coordinates would silently ground weather/land advice
                # in the OLD place — clear, then re-resolve from the bundle.
                farm.latitude = None
                farm.longitude = None
                if not union_changed:
                    # The old union cannot belong to the new upazila.
                    farm.union_name = ""
                    farm.union_geocode = ""
                warnings.append(
                    "farm location changed — stale geocodes cleared; land "
                    "context must be re-fetched"
                )
            if location_changed or union_changed:
                _re_resolve_farm_geo(farm, warnings)
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
