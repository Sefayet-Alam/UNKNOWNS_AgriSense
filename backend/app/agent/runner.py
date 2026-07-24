"""Agent turn runner: drives the graph and yields contract SSE event dicts."""
from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..logging_setup import trunc
from ..models import ChatMessage, ChatSession, User
from ..schemas import serialize_message
from . import memory as memory_mod
from .graph import build_graph
from .llm import build_chat_model

log = logging.getLogger("agrisense.agent")
from .tools import (
    build_farm_tools,
    build_memory_tools,
    build_static_tools,
    build_weather_tool,
)

SYSTEM_PROMPT = (
    "You are AgriSense, an expert agricultural advisor for Bangladeshi "
    "farmers. Reply in the language the farmer uses (Bengali, Banglish, or "
    "English); prefer natural Bengali when they write Bengali or Banglish. "
    "Give practical, accurate, concise advice on crops, soil, pests, "
    "weather, irrigation, and markets.\n"
    "\n"
    "FARM PROFILE & INTAKE (slot-filling):\n"
    "- At the start of a planning conversation call get_farm_profile to see "
    "what is already known. NEVER re-ask something already saved.\n"
    "- Whenever the farmer states a fact about their farm (place, size, "
    "soil, water, budget, season, previous crop, preferences), immediately "
    "save it with update_farm_profile. Save only what they explicitly said "
    "— never guess or infer values.\n"
    "- Before crop planning these are required: location, farm size, water "
    "availability, budget, season (see missing_required_fields). Ask for "
    "missing ones with ONE or at most two targeted questions per turn — do "
    "not interrogate with a long list.\n"
    "- Land units: bigha and kani vary by region. If the farmer gives such "
    "a unit, ask how many shotok it is locally when practical; if they "
    "confirm, pass local_unit_factor_decimal. If a conversion was ASSUMED "
    "(see warnings), tell the farmer which assumption was used.\n"
    "- Relay any warnings from update_farm_profile (e.g. implausible "
    "area/budget) and confirm with the farmer before planning.\n"
    "- Once all required fields are present, summarize the profile in the "
    "farmer's language and confirm it is correct before recommending.\n"
    "- The registered address only prefills the farm location — if the "
    "farmer says the land is elsewhere, update it (list_farms / create_farm "
    "/ select_farm handle multiple farms; ask which farm when ambiguous).\n"
    "\n"
    "DATE & TIME: the CURRENT Bangladesh date-time is injected into the "
    "system context every turn — that value is authoritative. Your training "
    "data is stale: NEVER state or assume a date/year from memory (e.g. "
    "2024). All season timing, sowing windows, forecast dates and \"today\" "
    "references MUST use the injected current date (or get_current_time for "
    "a precise timestamp).\n"
    "\n"
    "TOOL PROTOCOL: tools are invoked ONLY through native function calls. "
    "NEVER write text that looks like a tool call or trace (e.g. '[tool "
    "get_weather ... -> ...]') in a reply — such text is not executed and "
    "would be shown to the farmer verbatim. If you need data, actually call "
    "the tool and wait for its result.\n"
    "\n"
    "GROUNDING RULES:\n"
    "- Weather: ALWAYS call get_weather for anything weather-related. Only "
    "cite values the tool returned. If it reports WEATHER_UNAVAILABLE, say "
    "live weather is unavailable — never invent forecast numbers. Forecasts "
    "reach at most 16 days ahead; beyond that, do not state daily weather.\n"
    "- Explain recommendations by naming the specific inputs behind them "
    "(the farmer's stated facts and retrieved data).\n"
    "\n"
    "Other tools: get_current_time, calculator for arithmetic, save_memory/"
    "recall_memory for durable personal facts (preferences, experiences) — "
    "farm facts belong in the farm profile, not memory. Be clear and friendly."
)


def _text_of(content: Any) -> str:
    """Flatten LangChain message content (str or list-of-parts) to plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                if part.get("type") == "text" and "text" in part:
                    parts.append(part["text"])
        return "".join(parts)
    return str(content)


def _history_to_lc_messages(history: list[ChatMessage]) -> list:
    """Replay persisted history as NATIVE LangChain messages.

    Assistant rows carrying a ``tool_trace`` are reconstructed as an
    ``AIMessage`` with real ``tool_calls`` plus one ``ToolMessage`` per trace
    entry (synthetic ids). Never flatten tool traces into plain text: models
    imitate that text — observed live as a fabricated
    ``[tool get_weather ... -> {...}]`` block pasted verbatim into the chat
    instead of a real tool call.
    """
    lc: list = []
    for m in history:
        if m.role == "user":
            lc.append(HumanMessage(content=m.content))
            continue
        trace = m.tool_trace or []
        if not trace:
            lc.append(AIMessage(content=m.content or ""))
            continue
        tool_calls = []
        tool_msgs = []
        for idx, entry in enumerate(trace):
            call_id = f"hist_{m.id}_{idx}"
            tool_calls.append(
                {
                    "name": entry.get("tool", ""),
                    "args": entry.get("args", {}) or {},
                    "id": call_id,
                    "type": "tool_call",
                }
            )
            tool_msgs.append(
                ToolMessage(
                    content=entry.get("result", "") or "",
                    tool_call_id=call_id,
                )
            )
        lc.append(AIMessage(content=m.content or "", tool_calls=tool_calls))
        lc.extend(tool_msgs)
    return lc


async def _touch_session(db: AsyncSession, session: ChatSession) -> None:
    from datetime import datetime, timezone

    session.updated_at = datetime.now(timezone.utc)
    await db.commit()


async def _message_count(db: AsyncSession, session_id: int) -> int:
    result = await db.execute(
        select(func.count(ChatMessage.id)).where(
            ChatMessage.session_id == session_id
        )
    )
    return int(result.scalar_one())


async def stream_agent_turn(
    db: AsyncSession,
    user: User,
    session_or_none: Optional[ChatSession],
    message: str,
) -> AsyncGenerator[dict, None]:
    """Run one user turn; yield event dicts matching the frozen contract."""
    session = session_or_none
    log.info(
        "turn start: user=%s session=%s message=%s",
        user.id,
        session.id if session else "NEW",
        trunc(message, 200),
    )
    try:
        # ---- get-or-create session -------------------------------------- #
        if session is None:
            title = message.strip()[:60] or "New chat"
            session = ChatSession(user_id=user.id, title=title)
            db.add(session)
            await db.commit()
            await db.refresh(session)

        yield {"type": "session", "session_id": session.id}

        # ---- persist user message + echo bubble ------------------------- #
        user_msg = ChatMessage(
            session_id=session.id, role="user", content=message, tool_trace=[]
        )
        db.add(user_msg)
        await db.commit()
        await db.refresh(user_msg)
        yield {"type": "message", "message": serialize_message(user_msg)}

        # ---- build tools ------------------------------------------------ #
        memory_tools = build_memory_tools(user.id, db)
        tools = (
            build_static_tools()
            + [build_weather_tool(user)]
            + build_farm_tools(user)
            + memory_tools
        )

        # ---- auto-recall top-K memories --------------------------------- #
        yield {
            "type": "progress",
            "stage": "memory",
            "detail": "recalling relevant memories",
        }
        recalled = await memory_mod.recall_memory(
            db, user.id, message, settings.MEMORY_TOP_K
        )

        # ---- load windowed history + summary prefix --------------------- #
        hist_result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.id.desc())
            .limit(settings.HISTORY_LIMIT)
        )
        history = list(reversed(hist_result.scalars().all()))
        total_count = await _message_count(db, session.id)

        from datetime import datetime
        from zoneinfo import ZoneInfo

        now_dhaka = datetime.now(ZoneInfo("Asia/Dhaka"))
        lc_messages: list = [
            SystemMessage(content=SYSTEM_PROMPT),
            SystemMessage(
                content=(
                    "CURRENT DATE & TIME (Asia/Dhaka): "
                    f"{now_dhaka.strftime('%A, %d %B %Y, %H:%M')} "
                    f"({now_dhaka.date().isoformat()}). This is authoritative "
                    "— use it for every 'today'/season/date computation."
                )
            ),
        ]
        if session.summary:
            lc_messages.append(
                SystemMessage(
                    content=f"Conversation summary so far:\n{session.summary}"
                )
            )
        if recalled:
            joined = "\n".join(f"- {r}" for r in recalled)
            lc_messages.append(
                SystemMessage(
                    content=(
                        "Relevant long-term memories about this user:\n"
                        f"{joined}"
                    )
                )
            )
        lc_messages.extend(_history_to_lc_messages(history))

        # ---- run the graph ---------------------------------------------- #
        graph = build_graph(tools)
        inputs = {"messages": lc_messages}
        log.info(
            "graph invoke: session=%s model=%s history_msgs=%d lc_msgs=%d "
            "recalled_memories=%d tools=%s",
            session.id,
            settings.OPENROUTER_MODEL,
            len(history),
            len(lc_messages),
            len(recalled),
            [t.name for t in tools],
        )

        # tool_call_id -> (db ChatMessage, index in its tool_trace)
        tool_call_map: dict[str, tuple[ChatMessage, int]] = {}

        async for mode, chunk in graph.astream(
            inputs, stream_mode=["updates", "custom"]
        ):
            if mode == "custom":
                yield {
                    "type": "progress",
                    "stage": chunk.get("stage", "tool")
                    if isinstance(chunk, dict)
                    else "tool",
                    "detail": chunk.get("detail", "")
                    if isinstance(chunk, dict)
                    else str(chunk),
                }
                continue

            if mode != "updates" or not isinstance(chunk, dict):
                continue

            for _node, payload in chunk.items():
                if not isinstance(payload, dict):
                    continue
                for msg in payload.get("messages", []) or []:
                    if isinstance(msg, AIMessage):
                        text = _text_of(msg.content)
                        traces = []
                        for tc in msg.tool_calls or []:
                            log.info(
                                "model tool_call [%s]: %s args=%s",
                                _node,
                                tc.get("name", ""),
                                trunc(tc.get("args", {}), 300),
                            )
                            traces.append(
                                {
                                    "tool": tc.get("name", ""),
                                    "args": tc.get("args", {}) or {},
                                    "result": "",
                                }
                            )
                        if text:
                            log.info(
                                "model answer [%s]: %d chars: %s",
                                _node,
                                len(text),
                                trunc(text, 200),
                            )
                            if text.lstrip().startswith("[tool "):
                                # Guard: the model imitated the old text-trace
                                # format instead of calling a tool. Should be
                                # impossible with native replay — surface loud.
                                log.warning(
                                    "model IMITATED tool-trace text instead of "
                                    "calling a tool (session=%s): %s",
                                    session.id,
                                    trunc(text, 300),
                                )
                        # Persist a bubble (carries text and/or tool_trace).
                        db_msg = ChatMessage(
                            session_id=session.id,
                            role="assistant",
                            content=text,
                            tool_trace=traces,
                            model=settings.OPENROUTER_MODEL,
                        )
                        db.add(db_msg)
                        await db.commit()
                        await db.refresh(db_msg)
                        for idx, tc in enumerate(msg.tool_calls or []):
                            tc_id = tc.get("id")
                            if tc_id:
                                tool_call_map[tc_id] = (db_msg, idx)
                        yield {
                            "type": "message",
                            "message": serialize_message(db_msg),
                        }

                    elif isinstance(msg, ToolMessage):
                        owner = tool_call_map.get(msg.tool_call_id)
                        if owner is None:
                            continue
                        db_msg, idx = owner
                        trace = list(db_msg.tool_trace or [])
                        if 0 <= idx < len(trace):
                            updated = dict(trace[idx])
                            updated["result"] = _text_of(msg.content)
                            log.info(
                                "tool result: %s -> %s",
                                updated.get("tool", "?"),
                                trunc(updated["result"], 400),
                            )
                            trace[idx] = updated
                            db_msg.tool_trace = trace  # reassign -> tracked
                            await db.commit()
                            await db.refresh(db_msg)
                            yield {
                                "type": "message_update",
                                "message": serialize_message(db_msg),
                            }

        # ---- bump session, refresh rolling summary on overflow ---------- #
        await _touch_session(db, session)

        new_total = await _message_count(db, session.id)
        if new_total > settings.HISTORY_LIMIT:
            # Summarize everything that has now fallen outside the window.
            offset = new_total - settings.HISTORY_LIMIT
            cutoff_result = await db.execute(
                select(ChatMessage.id)
                .where(ChatMessage.session_id == session.id)
                .order_by(ChatMessage.id)
                .offset(offset - 1)
                .limit(1)
            )
            cutoff_id = cutoff_result.scalar_one_or_none()
            if cutoff_id and cutoff_id > (session.summary_upto_id or 0):
                yield {
                    "type": "progress",
                    "stage": "summary",
                    "detail": "updating conversation summary",
                }
                try:
                    summary_model = build_chat_model()
                    await memory_mod.refresh_summary(
                        db, session, cutoff_id, summary_model
                    )
                except Exception:
                    pass

        log.info("turn done: session=%s", session.id)
        yield {"type": "done"}

    except Exception as exc:  # surface as terminal error frame
        sid = session.id if session is not None else 0
        log.exception("turn FAILED: user=%s session=%s: %s", user.id, sid, exc)
        try:
            await db.rollback()
        except Exception:
            pass
        yield {"type": "error", "detail": str(exc), "session_id": sid}
