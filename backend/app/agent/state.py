"""Graph state definition."""
from __future__ import annotations

from langgraph.graph import MessagesState


class OrchestratorState(MessagesState):
    """Multi-node workflow state.

    ``messages`` (from MessagesState) is the shared conversation memory every
    node sees. The extra keys carry routing + farm context across nodes:

    - ``intent``       — set by the classify node; drives routing.
    - ``active_agent`` — which specialist node is currently driving; the
      shared tools node returns control to it after executing tool calls.
    - ``farm_context`` — snapshot of the active farm profile loaded at turn
      start (location, missing fields, phase) so routing/prompts can use it
      without an extra DB roundtrip.
    - ``reply_language`` — the conversation's reply language ("bengali" |
      "english"). Updated by the classify node on EVERY user message
      (deterministic detection: Bengali script / Banglish -> bengali, else
      english); every specialist injects a directive built from this state,
      so replies always follow the farmer's latest language.
    """

    intent: str
    active_agent: str
    farm_context: dict
    reply_language: str
