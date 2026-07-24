"""SSE streaming + agentic tool-loop tests (no real LLM).

The realtime transport is **SSE** (``text/event-stream``), not WebSocket. We
drive it with ``client.stream("POST", ...)`` and a tiny SSE parser
(``tests.fakes.read_sse_events``).
"""
from __future__ import annotations

import pytest

from tests.fakes import stream_turn

pytestmark = pytest.mark.streaming


def _types(events):
    return [e["type"] for e in events]


@pytest.mark.parametrize("fake_llm", ["plain"], indirect=True)
async def test_plain_turn_frame_order_and_persistence(auth_client, fake_llm):
    events = await stream_turn(auth_client, "How do I grow rice?")
    types = _types(events)

    # First frame is the session frame.
    assert types[0] == "session"
    session_id = events[0]["session_id"]

    # Terminal frame is done.
    assert types[-1] == "done"
    assert "error" not in types

    # The user echo comes before the assistant message.
    message_events = [e for e in events if e["type"] == "message"]
    user_msg = next(e["message"] for e in message_events if e["message"]["role"] == "user")
    assistant_msg = next(
        e["message"] for e in message_events if e["message"]["role"] == "assistant"
    )
    assert user_msg["content"] == "How do I grow rice?"
    assert assistant_msg["content"].strip() != ""

    # Ordering: session -> user message -> assistant message -> done.
    idx_session = types.index("session")
    idx_user = next(
        i for i, e in enumerate(events)
        if e["type"] == "message" and e["message"]["role"] == "user"
    )
    idx_assistant = next(
        i for i, e in enumerate(events)
        if e["type"] == "message" and e["message"]["role"] == "assistant"
    )
    idx_done = types.index("done")
    assert idx_session < idx_user < idx_assistant < idx_done

    # The assistant message was persisted.
    msgs = (
        await auth_client.get(f"/api/chat/sessions/{session_id}/messages")
    ).json()["results"]
    persisted_assistant = [m for m in msgs if m["role"] == "assistant"]
    assert persisted_assistant
    assert persisted_assistant[-1]["content"].strip() != ""


@pytest.mark.parametrize("fake_llm", ["tool"], indirect=True)
async def test_tool_turn_emits_trace_and_update_and_persists_result(
    auth_client, fake_llm
):
    events = await stream_turn(auth_client, "What is 2+2?")
    types = _types(events)

    assert types[0] == "session"
    assert types[-1] == "done"
    assert "error" not in types
    session_id = events[0]["session_id"]

    # A `message` frame carries a calculator tool_trace entry, result initially
    # empty.
    tool_message_idx = None
    for i, e in enumerate(events):
        if e["type"] == "message":
            trace = e["message"].get("tool_trace") or []
            calc = [t for t in trace if t.get("tool") == "calculator"]
            if calc:
                tool_message_idx = i
                assert calc[0]["result"] == ""  # not filled yet
                assert calc[0]["args"] == {"expression": "2+2"}
                break
    assert tool_message_idx is not None, f"no calculator tool_trace frame in {types}"

    # Followed by a `message_update` frame where the result is filled in.
    update_idx = None
    for i in range(tool_message_idx + 1, len(events)):
        e = events[i]
        if e["type"] == "message_update":
            trace = e["message"].get("tool_trace") or []
            calc = [t for t in trace if t.get("tool") == "calculator"]
            if calc and calc[0]["result"] != "":
                update_idx = i
                assert calc[0]["result"] == "4"
                break
    assert update_idx is not None, f"no message_update with filled result in {types}"

    # Then a final assistant message with content, then done.
    final_assistant_idx = None
    for i in range(update_idx + 1, len(events)):
        e = events[i]
        if e["type"] == "message" and e["message"]["role"] == "assistant":
            if e["message"]["content"].strip():
                final_assistant_idx = i
                break
    assert final_assistant_idx is not None
    assert types.index("done") > final_assistant_idx

    # Persisted: the assistant bubble's calculator tool_trace result is filled.
    msgs = (
        await auth_client.get(f"/api/chat/sessions/{session_id}/messages")
    ).json()["results"]
    filled = []
    for m in msgs:
        for t in m.get("tool_trace") or []:
            if t.get("tool") == "calculator":
                filled.append(t.get("result"))
    assert filled, "no persisted calculator trace"
    assert any(r for r in filled), "persisted calculator result is empty"
    assert "4" in filled


@pytest.mark.parametrize("fake_llm", ["weather"], indirect=True)
async def test_weather_tool_turn_traces_real_adapter_values(
    auth_client, fake_llm, monkeypatch
):
    """get_weather surfaces as a trace chip whose result carries adapter values.

    The adapter is monkeypatched (offline), but the values flow through the
    same tool -> ToolMessage -> message_update path as production.
    """
    from app.adapters import weather as weather_mod

    async def fake_geocode(name, district=None, client=None):
        return {
            "name": "Tanore",
            "latitude": 24.588,
            "longitude": 88.581,
            "admin1": "Rajshahi Division",
            "admin2": "Rajshahi",
            "geocode_source": "open-meteo-geocoding",
        }

    async def fake_forecast(lat, lon, days, client=None):
        return {
            "source": "Open-Meteo forecast API",
            "fetched_at": "2026-07-24T06:00:00+00:00",
            "request_params": {"latitude": lat, "longitude": lon},
            "timezone": "Asia/Dhaka",
            "days": [
                {
                    "date": "2026-07-24",
                    "t_min_c": 26.4,
                    "t_max_c": 33.1,
                    "rain_mm": 0.0,
                    "rain_prob_pct": 10,
                    "et0_mm": 4.2,
                    "wind_max_kmh": 12.0,
                }
            ],
            "summary": {"forecast_days": 1, "total_rain_mm": 0.0},
            "note": "",
        }

    monkeypatch.setattr(weather_mod, "geocode_place", fake_geocode)
    monkeypatch.setattr(weather_mod, "fetch_forecast", fake_forecast)

    events = await stream_turn(auth_client, "আবহাওয়া কেমন?")
    types = _types(events)
    assert types[-1] == "done"
    assert "error" not in types

    # Chip appears with the scripted args.
    chip = None
    for e in events:
        if e["type"] == "message":
            for t in e["message"].get("tool_trace") or []:
                if t.get("tool") == "get_weather":
                    chip = t
                    break
    assert chip is not None, f"no get_weather chip in {types}"
    assert chip["args"] == {"location": "", "days": 3}

    # A message_update fills the result with adapter values (evidence).
    filled = None
    for e in events:
        if e["type"] == "message_update":
            for t in e["message"].get("tool_trace") or []:
                if t.get("tool") == "get_weather" and t.get("result"):
                    filled = t["result"]
    assert filled, "get_weather result never filled"
    assert "total_rain_mm" in filled
    assert "Open-Meteo" in filled
    assert "Tanore" in filled

    # Final Bengali assistant answer survives SSE intact.
    finals = [
        e["message"]["content"]
        for e in events
        if e["type"] == "message" and e["message"]["role"] == "assistant"
    ]
    assert any("তানোরে" in c for c in finals)


@pytest.mark.parametrize("fake_llm", ["intake"], indirect=True)
async def test_multi_turn_intake_fills_profile_across_turns(
    auth_client, fake_llm, db_session
):
    """Two-turn slot-fill: profile check + saves happen as visible tool chips
    and the farm row ends complete (EXAMPLE_FLOW #1/#2 shape)."""
    from sqlalchemy import select

    from app.models import Farm

    # Turn 1: farmer gives place/area/water; agent reads profile, saves, asks.
    events1 = await stream_turn(
        auth_client, "vai amar jomi Tanore te. 3 bigha. shallow pump ase."
    )
    types1 = _types(events1)
    assert types1[-1] == "done"
    assert "error" not in types1
    session_id = events1[0]["session_id"]

    chips1 = [
        t["tool"]
        for e in events1
        if e["type"] == "message"
        for t in e["message"].get("tool_trace") or []
    ]
    assert "get_farm_profile" in chips1
    assert "update_farm_profile" in chips1

    # The update result relayed the ASSUMED bigha conversion.
    updates1 = [
        t["result"]
        for e in events1
        if e["type"] == "message_update"
        for t in e["message"].get("tool_trace") or []
        if t.get("tool") == "update_farm_profile" and t.get("result")
    ]
    assert any("ASSUMED" in r for r in updates1)

    # Turn 2 (same session): budget + season.
    events2 = await stream_turn(
        auth_client, "budget 80k. robi te korbo.", session_id=session_id
    )
    assert _types(events2)[-1] == "done"
    assert "error" not in _types(events2)

    # Farm row is complete: converted area, budget, season, phase advanced.
    farm = (
        await db_session.execute(select(Farm).order_by(Farm.id.desc()))
    ).scalars().first()
    assert farm is not None
    assert farm.area_decimal == pytest.approx(99.0)
    assert farm.irrigation_available is True
    assert farm.budget_bdt == 80000
    assert farm.season == "rabi"
    assert farm.phase == "ready_for_planning"

    # Final assistant summary (Bengali) reached the client intact.
    finals = [
        e["message"]["content"]
        for e in events2
        if e["type"] == "message" and e["message"]["role"] == "assistant"
    ]
    assert any("৮০,০০০" in c for c in finals)


@pytest.mark.parametrize("fake_llm", ["plain"], indirect=True)
async def test_continue_existing_session(auth_client, fake_llm):
    first = await stream_turn(auth_client, "first message")
    session_id = first[0]["session_id"]

    second = await stream_turn(auth_client, "second message", session_id=session_id)
    # Same session id echoed back (no new session created).
    assert second[0]["type"] == "session"
    assert second[0]["session_id"] == session_id

    msgs = (
        await auth_client.get(f"/api/chat/sessions/{session_id}/messages")
    ).json()["results"]
    user_contents = [m["content"] for m in msgs if m["role"] == "user"]
    assert "first message" in user_contents
    assert "second message" in user_contents


async def test_stream_requires_auth(client):
    # No Bearer token -> 401 (streaming endpoint is protected).
    resp = await client.post(
        "/api/chat/stream", json={"message": "hi", "session_id": None}
    )
    assert resp.status_code == 401
