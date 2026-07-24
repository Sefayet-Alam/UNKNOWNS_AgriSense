# Argi Backend

FastAPI + async SQLAlchemy + pgvector backend for the Argi agri-tech agentic
chat. Implements JWT auth (with refresh rotation + blacklist) and a LangGraph
single-agent ReAct pipeline that streams over SSE.

## Run

### Docker (recommended)
Built to run behind a Postgres service named `db` with the pgvector image
(e.g. `pgvector/pgvector:pg16`). From `docker-compose`:

```yaml
backend:
  build: ./backend
  env_file: .env
  ports: ["8000:8000"]
  depends_on: [db]
```

The app runs `CREATE EXTENSION IF NOT EXISTS vector;` and
`Base.metadata.create_all` on startup — no migrations needed for the scaffold.

### Local
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# point DATABASE_URL at a reachable pgvector Postgres, then:
uvicorn app.main:app --reload --port 8000
```

## Environment
See `../.env.example`. Key vars:

| var | default | purpose |
|-----|---------|---------|
| `DATABASE_URL` | `postgresql+asyncpg://argi:...@db:5432/argi` | async DSN (asyncpg) |
| `JWT_SECRET_KEY` / `JWT_ALGORITHM` | — / `HS256` | token signing |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | access lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | refresh lifetime |
| `OPENROUTER_API_KEY` | — | **required for chat**; agent raises without it |
| `OPENROUTER_MODEL` / `OPENROUTER_BASE_URL` | `deepseek/deepseek-chat` / openrouter | chat LLM |
| `EMBEDDINGS_PROVIDER` | `fake` | `fake` (offline, deterministic) or `ollama` |
| `EMBEDDING_DIM` | `768` | pgvector column width (must match provider) |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` / `OLLAMA_EMBED_MODEL` | — | Ollama config |
| `HISTORY_LIMIT` | `40` | message window before rolling summary |
| `MEMORY_TOP_K` | `5` | semantic recall depth |
| `CORS_ORIGINS` | `http://localhost:3000,...` | comma-separated allowed origins |

> Embeddings default to `fake` so long-term memory works fully offline.
> The **chat** model always needs a valid `OPENROUTER_API_KEY`.

## Endpoints
All under the base URL (default `http://localhost:8000`). See
`docs/API_CONTRACT.md` for exact shapes.

- `POST /api/auth/register` · `POST /api/auth/login`
- `POST /api/auth/refresh` (rotation) · `POST /api/auth/logout` · `GET /api/auth/me`
- `POST /api/chat/stream` (SSE) · `GET /api/chat/sessions`
- `GET /api/chat/sessions/{id}/messages` · `DELETE /api/chat/sessions/{id}`
- `GET /health`

## Agent
LangGraph ReAct loop (`app/agent/`): tools `get_current_time`, `calculator`,
`save_memory`, `recall_memory`. Long-term memory is user-scoped pgvector
semantic recall; each session also keeps a rolling `summary`. The stream
runner emits `session` / `message` / `message_update` / `progress` / `done` /
`error` frames per the contract.
