"""Long-term (pgvector) memory + rolling per-session summary."""
from __future__ import annotations

from typing import List

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ChatMessage, LongTermMemory
from .llm import build_embeddings

_embeddings = None


def _get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = build_embeddings()
    return _embeddings


async def save_memory(db: AsyncSession, user_id: int, content: str) -> None:
    """Embed ``content`` and persist it as a user-scoped memory row."""
    content = (content or "").strip()
    if not content:
        return
    vector = await _get_embeddings().aembed_query(content)
    row = LongTermMemory(user_id=user_id, content=content, embedding=vector)
    db.add(row)
    await db.commit()


async def recall_memory(
    db: AsyncSession, user_id: int, query: str, k: int
) -> List[str]:
    """Return up to ``k`` memories nearest to ``query`` by cosine distance."""
    query = (query or "").strip()
    if not query:
        return []
    vector = await _get_embeddings().aembed_query(query)
    stmt = (
        select(LongTermMemory.content)
        .where(LongTermMemory.user_id == user_id)
        .order_by(LongTermMemory.embedding.cosine_distance(vector))
        .limit(k)
    )
    result = await db.execute(stmt)
    return [row for row in result.scalars().all()]


async def refresh_summary(
    db: AsyncSession, session, cutoff_id: int, model
) -> None:
    """Roll older messages (id <= cutoff_id) into a dense <=200 word summary.

    Best-effort: prepends the previous summary and swallows any error.
    """
    try:
        if cutoff_id <= (session.summary_upto_id or 0):
            return
        stmt = (
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session.id,
                ChatMessage.id > (session.summary_upto_id or 0),
                ChatMessage.id <= cutoff_id,
            )
            .order_by(ChatMessage.id)
        )
        result = await db.execute(stmt)
        msgs = result.scalars().all()
        if not msgs:
            return

        convo = "\n".join(f"{m.role}: {m.content}" for m in msgs)
        prompt = [
            SystemMessage(
                content=(
                    "You maintain a running summary of an agriculture "
                    "assistant conversation. Produce a dense summary of at "
                    "most 200 words that preserves facts, user preferences, "
                    "crops, locations, and decisions. Merge the previous "
                    "summary with the new messages; do not lose earlier facts."
                )
            ),
            HumanMessage(
                content=(
                    f"Previous summary:\n{session.summary or '(none)'}\n\n"
                    f"New messages:\n{convo}"
                )
            ),
        ]
        resp = await model.ainvoke(prompt)
        text = resp.content if isinstance(resp.content, str) else str(resp.content)
        session.summary = text.strip()
        session.summary_upto_id = cutoff_id
        await db.commit()
    except Exception:
        try:
            await db.rollback()
        except Exception:
            pass
