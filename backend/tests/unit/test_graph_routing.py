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
        # Weather is a TOOL on the advisor, not a node — weather questions
        # route to the advisor for grounded get_weather answers.
        ("আবহাওয়া কেমন?", "advisor"),
        ("Will it rain tomorrow?", "advisor"),
        ("agami 3 dine bristi hobe?", "advisor"),
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
    # "brishti" (weather) + "jomi" (intake) -> the advisor grounds the
    # weather answer instead of slot-filling.
    assert classify_heuristic("amar jomi te bristi hobe ki?") == "advisor"


def test_agents_registry():
    assert set(AGENTS) == {"intake", "advisor"}


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


# --------------------------------------------------------------------------- #
# Reply-language STATE (state.reply_language -> per-node directive)
# --------------------------------------------------------------------------- #
def test_language_directive_from_state_value():
    from app.agent.messages import language_directive

    bn = language_directive("bengali")
    en = language_directive("english")
    assert "BENGALI" in bn.content and "বাংলা" in bn.content
    assert "ENGLISH" in en.content
    # Unknown/empty state falls back to english, never crashes.
    assert "ENGLISH" in language_directive("").content
    assert "ENGLISH" in language_directive("klingon").content


@pytest.mark.parametrize(
    "text,lang",
    [
        ("আবহাওয়া কেমন?", "bengali"),
        ("bhai amar jomi ase", "bengali"),
        ("What should I plant?", "english"),
    ],
)
def test_state_language_detection_matches_last_message(text, lang):
    # classify_node stores detect_reply_language(last message) into
    # state.reply_language — this pins the detector the state relies on.
    from app.agent.messages import detect_reply_language

    assert detect_reply_language(text) == lang
