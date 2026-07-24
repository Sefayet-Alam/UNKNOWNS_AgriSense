"""Integration tests: KB backup -> seed_rag_data restore round-trip.

Uses fake embeddings (forced in conftest). The seed path must reproduce the
vector store byte-for-byte-equivalently WITHOUT any embedding calls.
"""
from __future__ import annotations

import asyncio

import numpy as np
import pytest
from sqlalchemy import delete, select

from app.models import KnowledgeChunk
from app.rag import ingest_document, search_kb
from scripts import backup_kb, seed_rag_data

DOC = (
    "<!-- Page 87 (embedded) -->\n\n"
    "Mustard fertilizer dose: urea applied in two equal splits at sowing "
    "and flowering stage."
)


def _point_at(tmp_path, monkeypatch):
    monkeypatch.setattr(backup_kb, "SEED_DIR", tmp_path)
    monkeypatch.setattr(backup_kb, "CHUNKS_PATH", tmp_path / "kb_chunks.jsonl")
    monkeypatch.setattr(
        backup_kb, "EMBEDDINGS_PATH", tmp_path / "kb_embeddings.npy"
    )


@pytest.mark.asyncio
async def test_backup_then_seed_restores_identical_store(
    db_session, tmp_path, monkeypatch
):
    _point_at(tmp_path, monkeypatch)
    await ingest_document(db_session, DOC, source="FRG 2024")
    original = (await db_session.execute(select(KnowledgeChunk))).scalar_one()
    original_vec = np.asarray(original.embedding, dtype=np.float32)

    stats = await backup_kb.backup(db_session)
    assert stats["chunks"] == 1 and stats["sources"] == ["FRG 2024"]

    # Wipe the table, restore purely from the backup files.
    await db_session.execute(delete(KnowledgeChunk))
    await db_session.commit()

    seeded = await seed_rag_data.seed(db_session)
    assert seeded["chunks"] == 1 and seeded["replaced"] == 0

    row = (await db_session.execute(select(KnowledgeChunk))).scalar_one()
    assert row.source == "FRG 2024"
    assert row.page_start == 87 and row.page_end == 87
    assert row.content == original.content
    np.testing.assert_allclose(
        np.asarray(row.embedding, dtype=np.float32), original_vec, atol=1e-6
    )

    # Retrieval works from the seeded store (no embedding of documents).
    hits = await search_kb(db_session, DOC.split("\n\n", 1)[1])
    assert hits and hits[0]["source"] == "FRG 2024"


@pytest.mark.asyncio
async def test_seed_is_idempotent_replaces_not_duplicates(
    db_session, tmp_path, monkeypatch
):
    _point_at(tmp_path, monkeypatch)
    await ingest_document(db_session, DOC, source="FRG 2024")
    await backup_kb.backup(db_session)

    first = await seed_rag_data.seed(db_session)
    second = await seed_rag_data.seed(db_session)
    assert first["replaced"] == 1  # replaced the ingested original
    assert second["replaced"] == 1  # replaced the first seed, no duplicates
    rows = (await db_session.execute(select(KnowledgeChunk))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_seed_rejects_dim_mismatch(db_session, tmp_path, monkeypatch):
    _point_at(tmp_path, monkeypatch)
    await ingest_document(db_session, DOC, source="FRG 2024")
    await backup_kb.backup(db_session)
    # Corrupt: wrong-dimension matrix.
    np.save(tmp_path / "kb_embeddings.npy", np.zeros((1, 8), dtype=np.float32))
    with pytest.raises(SystemExit, match="dim"):
        seed_rag_data.load_seed()


@pytest.mark.asyncio
async def test_ensure_seeded_restores_empty_store_then_skips_complete_store(
    db_session, tmp_path, monkeypatch
):
    _point_at(tmp_path, monkeypatch)
    await ingest_document(db_session, DOC, source="FRG 2024")
    await backup_kb.backup(db_session)
    await db_session.execute(delete(KnowledgeChunk))
    await db_session.commit()

    first = await seed_rag_data.ensure_seeded(db_session)
    assert first == {
        "action": "seeded",
        "chunks": 1,
        "replaced": 0,
        "sources": ["FRG 2024"],
    }
    row = (await db_session.execute(select(KnowledgeChunk))).scalar_one()
    row_id = row.id

    second = await seed_rag_data.ensure_seeded(db_session)
    assert second == {
        "action": "skipped",
        "chunks": 1,
        "replaced": 0,
        "sources": ["FRG 2024"],
    }
    assert (await db_session.execute(select(KnowledgeChunk))).scalar_one().id == row_id


@pytest.mark.asyncio
async def test_ensure_seeded_repairs_partial_seed_and_preserves_other_sources(
    db_session, tmp_path, monkeypatch
):
    _point_at(tmp_path, monkeypatch)
    await ingest_document(db_session, DOC, source="FRG 2024")
    await ingest_document(
        db_session,
        "<!-- Page 4 (embedded) -->\n\nWheat crop weather calendar.",
        source="BAMIS",
    )
    await backup_kb.backup(db_session)

    # Simulate an interrupted deployment plus a source that is not managed by
    # the committed seed. The missing seed source must be repaired without
    # deleting the unrelated row.
    await db_session.execute(
        delete(KnowledgeChunk).where(KnowledgeChunk.source == "BAMIS")
    )
    await ingest_document(db_session, "Local extension note.", source="Local note")

    result = await seed_rag_data.ensure_seeded(db_session)
    assert result["action"] == "seeded"
    assert result["replaced"] == 1
    sources = (
        await db_session.execute(select(KnowledgeChunk.source))
    ).scalars().all()
    assert sorted(sources) == ["BAMIS", "FRG 2024", "Local note"]


@pytest.mark.asyncio
async def test_ensure_seeded_repairs_same_count_content_corruption(
    db_session, tmp_path, monkeypatch
):
    _point_at(tmp_path, monkeypatch)
    await ingest_document(db_session, DOC, source="FRG 2024")
    await backup_kb.backup(db_session)
    row = (await db_session.execute(select(KnowledgeChunk))).scalar_one()
    row.content = "corrupted but row count unchanged"
    await db_session.commit()

    result = await seed_rag_data.ensure_seeded(db_session)
    assert result["action"] == "seeded"
    restored = (await db_session.execute(select(KnowledgeChunk))).scalar_one()
    assert restored.content != "corrupted but row count unchanged"
    assert "Mustard fertilizer dose" in restored.content


@pytest.mark.asyncio
async def test_concurrent_ensure_seeded_is_serial_and_never_duplicates(
    db_session, session_factory, tmp_path, monkeypatch
):
    _point_at(tmp_path, monkeypatch)
    await ingest_document(db_session, DOC, source="FRG 2024")
    await backup_kb.backup(db_session)
    await db_session.execute(delete(KnowledgeChunk))
    await db_session.commit()

    async def ensure_once():
        async with session_factory() as session:
            return await seed_rag_data.ensure_seeded(session)

    results = await asyncio.gather(ensure_once(), ensure_once())
    assert sorted(result["action"] for result in results) == ["seeded", "skipped"]
    rows = (await db_session.execute(select(KnowledgeChunk))).scalars().all()
    assert len(rows) == 1
    assert rows[0].content.endswith("flowering stage.")
