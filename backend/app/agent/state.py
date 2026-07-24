"""Graph state definition."""
from __future__ import annotations

from langgraph.graph import MessagesState


class OrchestratorState(MessagesState):
    """Single-agent ReAct state: just the running message list."""
