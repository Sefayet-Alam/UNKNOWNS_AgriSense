"""Unit tests for multi-node graph routing helpers."""
from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.graph import (
    AGENTS,
    _current_turn_tool_rounds,
    classify_heuristic,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "text,expected",
    [
        ("আবহাওয়া কেমন?", "weather"),
        ("Will it rain tomorrow?", "weather"),
        ("agami 3 dine bristi hobe?", "weather"),
        ("amar 3 bigha jomi ase", "intake"),
        ("budget 80k, sech ase", "intake"),
        ("আমার জমির মাটি বেলে", "intake"),
        ("How do I grow rice?", "advisor"),
        ("hello", "advisor"),
        ("dhonnobad", "advisor"),
    ],
)
def test_classify_heuristic(text, expected):
    assert classify_heuristic(text) == expected


def test_weather_beats_intake_when_both_present():
    # "brishti" (weather) + "jomi" (intake) -> weather grounding first.
    assert classify_heuristic("amar jomi te bristi hobe ki?") == "weather"


def test_agents_registry():
    assert set(AGENTS) == {"intake", "weather", "advisor"}


def test_tool_rounds_exclude_replayed_history():
    messages = [
        HumanMessage(content="hi"),
        # Replayed from history (synthetic hist_ ids) — must NOT count.
        AIMessage(
            content="",
            tool_calls=[
                {"name": "x", "args": {}, "id": "hist_5_0", "type": "tool_call"}
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {"name": "y", "args": {}, "id": "hist_6_0", "type": "tool_call"}
            ],
        ),
        # Live this turn — counts.
        AIMessage(
            content="",
            tool_calls=[
                {"name": "z", "args": {}, "id": "call_live_1", "type": "tool_call"}
            ],
        ),
    ]
    assert _current_turn_tool_rounds(messages) == 1


def test_tool_rounds_zero_for_plain_conversation():
    assert (
        _current_turn_tool_rounds(
            [HumanMessage(content="q"), AIMessage(content="a")]
        )
        == 0
    )
