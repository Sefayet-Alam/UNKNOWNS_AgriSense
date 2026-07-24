"""LangChain tools available to the agent."""
from __future__ import annotations

import ast
import json
import operator
from datetime import datetime, timezone

from langchain_core.tools import tool

from ..adapters import weather as weather_mod
from ..config import settings
from ..database import AsyncSessionLocal
from . import memory as memory_mod


def _emit(stage: str, detail: str) -> None:
    """Emit a custom progress event if a stream writer is active (no-op else)."""
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
