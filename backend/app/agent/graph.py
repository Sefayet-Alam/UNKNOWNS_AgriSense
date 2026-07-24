"""Single-agent ReAct graph."""
from __future__ import annotations

import logging

from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from .llm import build_chat_model
from .state import OrchestratorState

MAX_TURNS = 8

log = logging.getLogger("agrisense.agent.graph")


def build_graph(tools):
    """Compile a ReAct loop: agent -> (tools -> agent)* -> END.

    Caps tool loops at ``MAX_TURNS``; once exhausted the model is invoked
    WITHOUT tools so it is forced to produce a final answer.
    """
    model = build_chat_model()
    model_with_tools = model.bind_tools(tools)

    async def agent_node(state: OrchestratorState):
        messages = state["messages"]
        used_turns = sum(
            1
            for m in messages
            if isinstance(m, AIMessage) and getattr(m, "tool_calls", None)
        )
        if used_turns >= MAX_TURNS:
            log.warning(
                "MAX_TURNS (%d) reached — invoking model WITHOUT tools to "
                "force a final answer",
                MAX_TURNS,
            )
            active = model
        else:
            active = model_with_tools
        log.info(
            "agent node: llm call (tool_rounds_used=%d, messages=%d)",
            used_turns,
            len(messages),
        )
        response = await active.ainvoke(messages)
        return {"messages": [response]}

    def should_continue(state: OrchestratorState):
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return END

    builder = StateGraph(OrchestratorState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges(
        "agent", should_continue, {"tools": "tools", END: END}
    )
    builder.add_edge("tools", "agent")
    return builder.compile()
