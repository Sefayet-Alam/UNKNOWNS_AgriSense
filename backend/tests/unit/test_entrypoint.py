"""Production container must migrate and populate RAG before serving."""
from pathlib import Path


def test_entrypoint_seeds_committed_rag_backup_after_migrations_before_uvicorn():
    script = (Path(__file__).parents[2] / "entrypoint.sh").read_text(encoding="utf-8")
    migrate = script.index("alembic upgrade head")
    seed = script.index("python -m scripts.seed_rag_data --if-needed")
    serve = script.index("exec uvicorn")
    assert migrate < seed < serve
