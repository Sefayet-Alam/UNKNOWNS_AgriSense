"""Unit tests for the agent's static tools."""
from __future__ import annotations

from datetime import datetime
import inspect

import pytest

from app.agent import tools as tools_mod
from app.agent import runner as runner_mod
from app.agent.tools import build_research_tools, calculator, get_current_time

pytestmark = pytest.mark.unit


def _call(tool, **kwargs):
    """Invoke a LangChain @tool with plain kwargs, returning the raw result."""
    return tool.invoke(kwargs)


def test_calculator_basic_arithmetic():
    assert _call(calculator, expression="2+2") == "4"
    assert _call(calculator, expression="10 / 4") == "2.5"
    assert _call(calculator, expression="2 ** 10") == "1024"
    assert _call(calculator, expression="(1 + 2) * 3 - 4") == "5"
    assert _call(calculator, expression="17 % 5") == "2"
    assert _call(calculator, expression="-7 + 2") == "-5"


@pytest.mark.parametrize(
    "expr",
    [
        "__import__('os').system('ls')",  # import / call
        "os.system('rm -rf /')",          # attribute/name access
        "open('/etc/passwd').read()",     # builtin call
        "abs(-1)",                         # any function call
        "x + 1",                           # bare name
        "[1,2,3]",                         # list literal (unsupported node)
        "lambda: 1",                       # lambda
    ],
)
def test_calculator_rejects_unsafe_expressions(expr):
    result = _call(calculator, expression=expr)
    # Rejected safely: returns an error string, never executes.
    assert result.startswith("Error:")


def test_get_current_time_returns_iso8601():
    result = _call(get_current_time)
    # Must be parseable as ISO 8601.
    parsed = datetime.fromisoformat(result)
    assert parsed.tzinfo is not None  # UTC-aware


@pytest.mark.asyncio
async def test_research_tool_factory_returns_untrusted_web_results(monkeypatch):
    async def fake_search_web(query, max_results):
        assert query == "mustard disease"
        assert max_results == 2
        return {
            "source": "DuckDuckGo search",
            "content_trust": "untrusted_external_reference",
            "results": [{"title": "Example", "url": "https://example.test", "snippet": "x"}],
        }

    monkeypatch.setattr(tools_mod.research_mod, "search_web", fake_search_web)
    web_search, _wikipedia = build_research_tools()

    result = await web_search.ainvoke({"query": "mustard disease", "max_results": 2})

    assert '"status": "ok"' in result
    assert '"content_trust": "untrusted_external_reference"' in result


@pytest.mark.asyncio
async def test_research_tool_returns_honest_unavailable_status(monkeypatch):
    async def unavailable(*_args, **_kwargs):
        raise tools_mod.research_mod.ResearchError("Wikipedia is unavailable")

    monkeypatch.setattr(tools_mod.research_mod, "search_wikipedia", unavailable)
    _web_search, wikipedia = build_research_tools()

    result = await wikipedia.ainvoke({"query": "mustard"})

    assert '"status": "RESEARCH_UNAVAILABLE"' in result
    assert "Wikipedia is unavailable" in result


def test_research_tools_are_enabled_for_the_season_planner():
    """The planner node exposes the web + Wikipedia research tools."""
    runner_source = inspect.getsource(runner_mod)

    assert "build_research_tools" in runner_source


def test_forced_tool_sequence_names_are_real_registered_tools():
    """Every forced tool_choice name must be an actual tool the node exposes.

    tool_choice forces the model to call a function by name; a typo or an
    unregistered tool would fail live (the model is compelled to call a tool
    that the shared ToolNode cannot execute). Guard the invariant offline.
    """
    from app.agent.graph import FORCED_TOOL_SEQUENCE, FORCED_UNORDERED_TOOLS

    research_names = {t.name for t in build_research_tools()}
    kb_names = {t.name for t in tools_mod.build_kb_tools()}

    static_names = {t.name for t in tools_mod.build_static_tools()}

    assert FORCED_TOOL_SEQUENCE["recommender"] == ["rank_crop_candidates"]
    # Recommender ALSO requires one web + one Wikipedia search, any order.
    assert set(FORCED_UNORDERED_TOOLS["recommender"]) == {
        "web_search",
        "search_wikipedia",
    }
    assert set(FORCED_UNORDERED_TOOLS["recommender"]) <= research_names
    # The planner's forced trio: KB retrieval then the two research tools.
    assert FORCED_TOOL_SEQUENCE["planner"] == [
        "search_knowledge_base",
        "web_search",
        "search_wikipedia",
    ]
    # Finance: price gathering -> deterministic projection -> calculator check.
    assert FORCED_TOOL_SEQUENCE["finance"] == [
        "web_search",
        "search_knowledge_base",
        "search_wikipedia",
        "calculate_crop_financials",
        "calculator",
    ]
    assert "search_knowledge_base" in kb_names
    assert {"web_search", "search_wikipedia"} <= research_names
    assert "calculator" in static_names
