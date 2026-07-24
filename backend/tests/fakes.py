"""Test doubles + small helpers shared across the suite.

- ``FakeChatModel`` — a scripted, offline stand-in for the OpenRouter chat
  model. It never touches the network. It supports ``.bind_tools(...)`` (a
  no-op, since we script tool calls directly into the returned ``AIMessage``s)
  and returns pre-baked responses in order.
- ``make_fake_llm(scenario)`` — returns a *factory* suitable for monkeypatching
  ``build_chat_model``: each call yields a fresh ``FakeChatModel`` so the
  internal response index resets per graph build (i.e. per agent turn).
- SSE helpers to parse ``text/event-stream`` frames from an httpx response.
- Auth helpers to register/login users via the phone-auth contract.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List

from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel,
)
from langchain_core.messages import AIMessage, BaseMessage


class FakeChatModel(FakeMessagesListChatModel):
    """Deterministic offline chat model returning scripted messages in order.

    ``bind_tools`` is a no-op that returns ``self`` — the graph binds tools to
    the model, but because we script ``tool_calls`` straight into the AIMessage
    responses there is nothing to actually bind. Sharing the same instance
    keeps the response cursor (``i``) consistent across the bound/unbound
    references the graph holds.
    """

    def bind_tools(self, tools: Any, **kwargs: Any) -> "FakeChatModel":  # noqa: D401
        return self


# --------------------------------------------------------------------------- #
# Scenario scripts
# --------------------------------------------------------------------------- #
def _plain_script() -> List[BaseMessage]:
    return [
        AIMessage(
            content=(
                "Rice grows best in flooded paddies; keep 2-3 cm of standing "
                "water during the vegetative stage."
            )
        )
    ]


def _tool_script() -> List[BaseMessage]:
    return [
        # Turn 1: ask to run the calculator tool.
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "calculator",
                    "args": {"expression": "2+2"},
                    "id": "call_calc_1",
                    "type": "tool_call",
                }
            ],
        ),
        # Turn 2 (after the tool result comes back): the final answer.
        AIMessage(content="2 + 2 = 4."),
    ]


def _weather_script() -> List[BaseMessage]:
    return [
        # Turn 1: call the weather tool for the registered location.
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_weather",
                    "args": {"location": "", "days": 3},
                    "id": "call_weather_1",
                    "type": "tool_call",
                }
            ],
        ),
        # Turn 2: explain using the returned values.
        AIMessage(
            content=(
                "আগামী ৩ দিনে তানোরে বৃষ্টির সম্ভাবনা কম — মোট ০.০ মিমি "
                "পূর্বাভাস। সেচের পরিকল্পনা সেভাবে করুন।"
            )
        ),
    ]


def _intake_turn1() -> List[BaseMessage]:
    """Farmer gave place+area+water; agent checks profile, saves, asks budget."""
    return [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_farm_profile",
                    "args": {},
                    "id": "call_profile_1",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "update_farm_profile",
                    "args": {
                        "area_value": 3,
                        "area_unit": "bigha",
                        "irrigation_available": True,
                        "water_source": "shallow tubewell",
                    },
                    "id": "call_update_1",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(content="এই মৌসুমে আপনার আনুমানিক বাজেট কত?"),
    ]


def _intake_turn2() -> List[BaseMessage]:
    """Farmer gave budget+season; agent saves, fills soil from the survey
    (mandatory slot — get_soil_context first, ask only on SOIL_UNKNOWN),
    then confirms the summary."""
    return [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "update_farm_profile",
                    "args": {"budget_bdt": 80000, "season": "rabi"},
                    "id": "call_update_2",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_soil_context",
                    "args": {},
                    "id": "call_soil_1",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(
            content=(
                "আমি যা বুঝেছি: তানোরে ৩ বিঘা (৯৯ শতক), সেচ আছে, বাজেট "
                "৮০,০০০ টাকা, রবি মৌসুম; জরিপ অনুযায়ী মাটি এঁটেল দোআঁশ "
                "(Clay Loam) — ঠিক আছে?"
            )
        ),
    ]


def _recommendation_script() -> List[BaseMessage]:
    return [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "rank_crop_candidates",
                    "args": {"limit": 5},
                    "id": "call_rank_1",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(
            content=(
                "আপনার ৯৯ শতক তানোরের জমির জন্য রবি ফসলের ক্রম হলো: "
                "১) আলু, ২) গম, ৩) সরিষা। এই ক্রমে CZIS জমির উপযোগিতা, "
                "Open-Meteo পূর্বাভাস, সেচ, বাজেট এবং স্থানীয় রেকর্ডকৃত "
                "ফসল-চক্রের অর্থনীতি ব্যবহার করা হয়েছে।"
            )
        ),
    ]


def _recommendation_degraded_script() -> List[BaseMessage]:
    return [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "rank_crop_candidates",
                    "args": {"limit": 3},
                    "id": "call_rank_degraded",
                    "type": "tool_call",
                }
            ],
        ),
        AIMessage(
            content=(
                "একটি লাইভ উৎস এখন অনুপলব্ধ, তাই ফলাফলটি degraded হিসেবে "
                "দেখানো হলো। কোনো অনুপস্থিত আবহাওয়া বা উপযোগিতা মান আমি "
                "অনুমান করিনি; প্রদর্শিত Unknown মান যাচাই করে নিন।"
            )
        ),
    ]


_SCENARIOS: Dict[str, Callable[[], List[BaseMessage]]] = {
    "plain": _plain_script,
    "tool": _tool_script,
    "weather": _weather_script,
    "recommendation": _recommendation_script,
    "recommendation_degraded": _recommendation_degraded_script,
}

# Multi-turn scenarios: one script per agent TURN (per graph build). The
# factory returned by make_fake_llm hands out script N on its N-th call and
# repeats the last script if called more often.
_SEQUENCE_SCENARIOS: Dict[str, List[Callable[[], List[BaseMessage]]]] = {
    "intake": [_intake_turn1, _intake_turn2],
}


def make_fake_llm(scenario: str) -> Callable[..., FakeChatModel]:
    """Return a factory yielding ONE shared scripted ``FakeChatModel``.

    Monkeypatch this over ``build_chat_model`` everywhere. The multi-node
    graph builds several per-node models per turn, so the factory must
    return the SAME instance regardless of call count or the ``model``
    argument — only the active specialist actually consumes responses, so a
    single global cursor walks the script in conversation order.

    Single-turn scenarios (``_SCENARIOS``) provide one script; the fake
    sticks on its last response for any later turns. Multi-turn scenarios
    (``_SEQUENCE_SCENARIOS``) are concatenated in turn order — each turn
    consumes exactly its own script's responses.

    The classify node never consumes responses: under TESTING it uses the
    deterministic keyword heuristic.
    """
    if scenario in _SCENARIOS:
        responses = _SCENARIOS[scenario]()
    elif scenario in _SEQUENCE_SCENARIOS:
        responses = [
            msg
            for script in _SEQUENCE_SCENARIOS[scenario]
            for msg in script()
        ]
    else:
        raise ValueError(f"unknown fake-llm scenario: {scenario!r}")

    shared = FakeChatModel(responses=responses)

    def factory(*args, **kwargs) -> FakeChatModel:
        return shared

    return factory


# --------------------------------------------------------------------------- #
# SSE parsing
# --------------------------------------------------------------------------- #
async def read_sse_events(response) -> List[dict]:
    """Consume an httpx streaming response and return the list of SSE payloads.

    Each frame is ``data: {json}\\n\\n``; we collect ``data:`` lines until a
    blank line, then json-decode the joined payload.
    """
    events: List[dict] = []
    data_lines: List[str] = []
    async for line in response.aiter_lines():
        if line == "":
            if data_lines:
                payload = "\n".join(data_lines)
                events.append(json.loads(payload))
                data_lines = []
            continue
        if line.startswith("data:"):
            data_lines.append(line[len("data:") :].lstrip())
    # Flush a trailing frame not followed by a blank line.
    if data_lines:
        events.append(json.loads("\n".join(data_lines)))
    return events


async def stream_turn(client, message: str, session_id=None, headers=None) -> List[dict]:
    """Run one /api/chat/stream turn and return the parsed SSE events."""
    body: Dict[str, Any] = {"message": message, "session_id": session_id}
    async with client.stream(
        "POST", "/api/chat/stream", json=body, headers=headers
    ) as response:
        assert response.status_code == 200, await response.aread()
        return await read_sse_events(response)


# --------------------------------------------------------------------------- #
# Auth helpers (phone-auth contract)
# --------------------------------------------------------------------------- #
DEFAULT_PASSWORD = "farm-pass-123"


def register_payload(phone: str, password: str = DEFAULT_PASSWORD, **overrides) -> dict:
    body = {
        "username": "Test Farmer",
        "phone": phone,
        "password1": password,
        "password2": password,
        "division_name": "Rajshahi",
        "division_code": "50",
        "district_name": "Rajshahi",
        "district_code": "5081",
        "upazila_name": "Tanore",
        "upazila_code": "508194",
        "union_name": "Badhair",
        "union_code": "50819427",
    }
    body.update(overrides)
    return body


async def register_user(client, phone: str, password: str = DEFAULT_PASSWORD, **overrides):
    """Register a user; returns the httpx response."""
    return await client.post(
        "/api/auth/register", json=register_payload(phone, password, **overrides)
    )


async def login_user(client, phone: str, password: str = DEFAULT_PASSWORD):
    return await client.post(
        "/api/auth/login", json={"phone": phone, "password": password}
    )


async def auth_headers_for(
    client, phone: str = "01712345678", password: str = DEFAULT_PASSWORD, **overrides
) -> dict:
    """Register + log in a user, returning a Bearer auth header dict."""
    reg = await register_user(client, phone, password, **overrides)
    assert reg.status_code == 201, reg.text
    login = await login_user(client, phone, password)
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
