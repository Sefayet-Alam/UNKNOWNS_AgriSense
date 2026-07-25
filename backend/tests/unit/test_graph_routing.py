"""Unit tests for multi-node graph routing helpers."""
from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.graph import (
    AGENTS,
    MAX_TURNS,
    _current_turn_tool_rounds,
    classify_heuristic,
    enforce_intake_admission,
    research_is_eligible,
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
        # Crop-choice questions route to the dedicated recommender node.
        ("Which crop should I plant this rabi season?", "recommender"),
        ("What should I grow to make profit?", "recommender"),
        ("Recommend a crop for my farm", "recommender"),
        ("kon fosol lagabo ebar?", "recommender"),
        ("ki chash korle labjonok hobe?", "recommender"),
        ("এই মৌসুমে কোন ফসল চাষ করব?", "recommender"),
        ("কোন ফসল লাভজনক হবে?", "recommender"),
        ("I chose wheat. Make a season plan", "planner"),
        ("Create a calendar for potato", "planner"),
        ("সরিষার প্ল্যান বানাও", "planner"),
        ("Wheat", "planner"),
        ("গম", "planner"),
        ("সরিষা", "planner"),
        # Finance coverage is no longer limited to the original five Rabi
        # calendar crops; a bare catalog crop can be the farmer's selection.
        ("lentil", "planner"),
        ("Calculate ROI and break-even for wheat", "finance"),
        ("Show me a cost breakdown for mustard", "finance"),
        ("If wheat sells at 42 taka, recalculate the profit", "finance"),
    ],
)
def test_classify_heuristic(text, expected):
    assert classify_heuristic(text) == expected


def test_weather_beats_intake_when_both_present():
    # "brishti" (weather) + "jomi" (intake) -> the advisor grounds the
    # weather answer instead of slot-filling.
    assert classify_heuristic("amar jomi te bristi hobe ki?") == "advisor"


def test_incomplete_personalised_planning_cannot_escape_intake():
    incomplete = {"missing_required_fields": ["farm_size", "budget"]}

    assert (
        enforce_intake_admission("planner", "help me plan my farm", incomplete)
        == "intake"
    )
    assert (
        enforce_intake_admission("recommender", "which crop should I grow?", incomplete)
        == "intake"
    )
    # A model calling the opening an "advisor" request cannot bypass intake.
    assert (
        enforce_intake_admission("advisor", "Can you help me plan my farm?", incomplete)
        == "intake"
    )


def test_complete_profile_keeps_specialist_intent():
    assert enforce_intake_admission("recommender", "which crop?", {}) == "recommender"


def test_tool_round_budget_is_six():
    assert MAX_TURNS == 6


def test_research_requires_a_successful_current_turn_domain_result():
    assert not research_is_eligible([], "planner")
    assert not research_is_eligible(
        [
            ToolMessage(
                content='{"status":"PROFILE_INCOMPLETE"}',
                name="generate_season_plan",
                tool_call_id="call_plan",
            )
        ],
        "planner",
    )
    assert research_is_eligible(
        [
            ToolMessage(
                content='{"status":"ok"}',
                name="generate_season_plan",
                tool_call_id="call_plan",
            )
        ],
        "planner",
    )
    # Replayed history may inform the reply but cannot unlock tools this turn.
    assert not research_is_eligible(
        [
            ToolMessage(
                content='{"status":"ok"}',
                name="generate_season_plan",
                tool_call_id="hist_42_0",
            )
        ],
        "planner",
    )


def test_recommend_beats_intake_and_weather():
    # A crop-choice ask wins even when farm facts / weather words appear.
    assert (
        classify_heuristic("amar 3 bigha jomi te kon fosol lagabo?")
        == "recommender"
    )
    assert (
        classify_heuristic("bristi hobe naki? ki chash korbo ebar?")
        == "recommender"
    )


def test_agents_registry():
    assert set(AGENTS) == {"intake", "advisor", "recommender", "planner", "finance"}


def test_crop_choice_beats_plan_when_crop_is_not_selected_yet():
    assert (
        classify_heuristic("Recommend a crop and then make a season plan")
        == "recommender"
    )


def test_crop_choice_beats_finance_when_farmer_has_not_selected_a_crop():
    assert classify_heuristic("What should I grow to make profit?") == "recommender"


def test_hypothetical_crop_choice_is_not_misrouted_as_finance_scenario():
    assert classify_heuristic("What if I plant wheat this rabi season?") == "recommender"


def test_full_plan_beats_finance_for_a_selected_crop():
    assert classify_heuristic("Make a costed season plan for wheat") == "planner"


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
