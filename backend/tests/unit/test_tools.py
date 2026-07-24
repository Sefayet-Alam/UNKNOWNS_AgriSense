"""Unit tests for the agent's static tools."""
from __future__ import annotations

from datetime import datetime

import pytest

from app.agent.tools import calculator, get_current_time

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
