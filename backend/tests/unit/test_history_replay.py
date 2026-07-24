"""History replay must reconstruct NATIVE tool-call messages.

Regression guard for a live bug: tool traces flattened into assistant text as
"[tool X args=... -> result]" taught the model to IMITATE that format — it
pasted a fabricated tool block verbatim into the chat instead of calling the
tool. Replay must therefore produce AIMessage.tool_calls + ToolMessage pairs,
never imitable prose.
"""
from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.runner import _history_to_lc_messages
from app.models import ChatMessage

pytestmark = pytest.mark.unit


def _msg(id_, role, content="", trace=None):
    m = ChatMessage(session_id=1, role=role, content=content, tool_trace=trace or [])
    m.id = id_
    return m


def test_plain_messages_replay_as_human_and_ai():
    out = _history_to_lc_messages(
        [_msg(1, "user", "hello"), _msg(2, "assistant", "hi there")]
    )
    assert isinstance(out[0], HumanMessage) and out[0].content == "hello"
    assert isinstance(out[1], AIMessage) and out[1].content == "hi there"
    assert not out[1].tool_calls


def test_traced_assistant_replays_as_native_tool_call_plus_toolmessage():
    trace = [
        {
            "tool": "get_weather",
            "args": {"location": "", "days": 7},
            "result": '{"summary": {"total_rain_mm": 43.7}}',
        }
    ]
    out = _history_to_lc_messages([_msg(7, "assistant", "", trace)])

    ai, tm = out
    assert isinstance(ai, AIMessage)
    assert ai.tool_calls[0]["name"] == "get_weather"
    assert ai.tool_calls[0]["args"] == {"location": "", "days": 7}
    assert ai.tool_calls[0]["id"] == "hist_7_0"
    assert isinstance(tm, ToolMessage)
    assert tm.tool_call_id == "hist_7_0"
    assert "43.7" in tm.content
    # CRITICAL: no imitable "[tool ...]" text anywhere in replayed content.
    assert "[tool" not in (ai.content or "")


def test_multi_tool_trace_produces_one_toolmessage_each():
    trace = [
        {"tool": "get_farm_profile", "args": {}, "result": "{}"},
        {"tool": "update_farm_profile", "args": {"budget_bdt": 80000}, "result": "{}"},
    ]
    out = _history_to_lc_messages([_msg(9, "assistant", "", trace)])
    ai = out[0]
    assert len(ai.tool_calls) == 2
    tool_msgs = [m for m in out[1:] if isinstance(m, ToolMessage)]
    assert [t.tool_call_id for t in tool_msgs] == ["hist_9_0", "hist_9_1"]


def test_mixed_conversation_order_preserved():
    history = [
        _msg(1, "user", "আবহাওয়া?"),
        _msg(
            2,
            "assistant",
            "",
            [{"tool": "get_weather", "args": {}, "result": "rain"}],
        ),
        _msg(3, "assistant", "বৃষ্টি হবে।"),
        _msg(4, "user", "ধন্যবাদ"),
    ]
    out = _history_to_lc_messages(history)
    kinds = [type(m).__name__ for m in out]
    assert kinds == ["HumanMessage", "AIMessage", "ToolMessage", "AIMessage", "HumanMessage"]
