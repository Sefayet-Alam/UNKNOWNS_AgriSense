"""Seed the RAG vector store from the committed backup — no embedding calls.

Restores ``knowledge_chunks`` from the row-aligned pair written by
``scripts.backup_kb`` (``app/data/kb_seed/kb_chunks.jsonl`` +
``kb_embeddings.npy``). Idempotent per source: every source present in the
backup has its existing chunks replaced, other sources are untouched. Use
this instead of ``scripts.ingest_kb`` whenever the corpus itself hasn't
changed (fresh database, new machine, demo setup) — it needs no API key and
runs in seconds.

Usage (inside the backend container):

    docker compose exec backend python -m scripts.seed_rag_data
    docker compose exec backend python -m scripts.seed_rag_data --if-needed
"""
from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter

import numpy as np
from sqlalchemy import delete, select, text

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import KnowledgeChunk

from . import backup_kb

_INSERT_BATCH = 500
_SEED_LOCK_KEY = 0x4152474953454544  # stable PostgreSQL advisory-lock id: ARGISEED


async def _lock_seed_transaction(db) -> None:
    """Serialize startup seed checks/replacements across app replicas."""
    await db.execute(
        text("SELECT pg_advisory_xact_lock(:key)"), {"key": _SEED_LOCK_KEY}
    )


def load_seed() -> tuple[list[dict], np.ndarray]:
    """Load + validate the backup pair; raises SystemExit on mismatch."""
    chunks_path = backup_kb.CHUNKS_PATH
    embeddings_path = backup_kb.EMBEDDINGS_PATH
    if not chunks_path.is_file() or not embeddings_path.is_file():
        raise SystemExit(
            f"error: seed backup not found under {chunks_path.parent} — "
            "run scripts.ingest_kb then scripts.backup_kb first."
        )
    with open(chunks_path, encoding="utf-8") as f:
        chunks = [json.loads(line) for line in f if line.strip()]
    vectors = np.load(embeddings_path)
    if len(chunks) != vectors.shape[0]:
        raise SystemExit(
            f"error: {len(chunks)} chunk rows but {vectors.shape[0]} "
            "embedding rows — backup files are out of sync."
        )
    if vectors.shape[1] != settings.KB_EMBEDDING_DIM:
        raise SystemExit(
            f"error: backup dim {vectors.shape[1]} != configured "
            f"KB_EMBEDDING_DIM {settings.KB_EMBEDDING_DIM} — re-ingest with "
            "the current embedding model instead of seeding."
        )
    return chunks, vectors


async def seed(db, *, acquire_lock: bool = True) -> dict:
    """Replace every backed-up source's chunks in ``db`` from the seed files."""
    chunks, vectors = load_seed()
    sources = sorted({c["source"] for c in chunks})
    try:
        if acquire_lock:
            await _lock_seed_transaction(db)
        deleted = await db.execute(
            delete(KnowledgeChunk).where(KnowledgeChunk.source.in_(sources))
        )
        replaced = deleted.rowcount or 0
        for start in range(0, len(chunks), _INSERT_BATCH):
            for c, vec in zip(
                chunks[start : start + _INSERT_BATCH],
                vectors[start : start + _INSERT_BATCH],
            ):
                db.add(
                    KnowledgeChunk(
                        source=c["source"],
                        chunk_index=c["chunk_index"],
                        page_start=c.get("page_start"),
                        page_end=c.get("page_end"),
                        crop=c.get("crop", ""),
                        topic=c.get("topic", ""),
                        content=c["content"],
                        embedding=vec.tolist(),
                    )
                )
        # Delete + complete insert are one transaction: a failed restore can
        # never leave the managed knowledge corpus partially empty.
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {
        "chunks": len(chunks),
        "replaced": replaced,
        "sources": sources,
    }


async def ensure_seeded(db) -> dict:
    """Restore the backup only when one of its managed sources is incomplete.

    A mere non-empty table is not enough: an interrupted restore or an
    unrelated custom document must not prevent the committed FRG corpus from
    being present. Sources not represented in the backup remain untouched.
    """
    chunks, vectors = load_seed()
    await _lock_seed_transaction(db)
    expected = Counter(chunk["source"] for chunk in chunks)
    rows = (
        await db.execute(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.source.in_(list(expected)))
            .order_by(KnowledgeChunk.source, KnowledgeChunk.chunk_index)
        )
    ).scalars().all()
    actual_counts = Counter(row.source for row in rows)
    by_key = {(row.source, row.chunk_index): row for row in rows}
    complete = actual_counts == expected
    if complete:
        for chunk, vector in zip(chunks, vectors):
            row = by_key.get((chunk["source"], chunk["chunk_index"]))
            if row is None or any(
                (
                    row.page_start != chunk.get("page_start"),
                    row.page_end != chunk.get("page_end"),
                    row.crop != chunk.get("crop", ""),
                    row.topic != chunk.get("topic", ""),
                    row.content != chunk["content"],
                    not np.allclose(
                        np.asarray(row.embedding, dtype=np.float32),
                        np.asarray(vector, dtype=np.float32),
                        rtol=0,
                        atol=1e-6,
                    ),
                )
            ):
                complete = False
                break
    if complete:
        return {
            "action": "skipped",
            "chunks": len(chunks),
            "replaced": 0,
            "sources": sorted(expected),
        }
    return {"action": "seeded", **(await seed(db, acquire_lock=False))}


async def _run(*, if_needed: bool = False) -> None:
    async with AsyncSessionLocal() as db:
        stats = await (ensure_seeded(db) if if_needed else seed(db))
    action = stats.get("action", "seeded")
    if action == "skipped":
        print(
            f"RAG seed already complete ({stats['chunks']} chunks) — "
            f"sources: {stats['sources']}"
        )
    else:
        print(
            f"seeded {stats['chunks']} chunks from backup "
            f"({stats['replaced']} previous replaced) — sources: {stats['sources']}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--if-needed",
        action="store_true",
        help="skip when every source in the committed backup is already complete",
    )
    args = parser.parse_args()
    asyncio.run(_run(if_needed=args.if_needed))


if __name__ == "__main__":
    main()
