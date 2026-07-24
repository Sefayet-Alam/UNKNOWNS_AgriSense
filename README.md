# Argi — Agentic Chat (agri-tech)

Full-stack scaffold: **FastAPI** backend + **Next.js** frontend + **Postgres/pgvector**, wired together with Docker Compose. JWT auth (access/refresh with **rotation + blacklisting**), and an agentic chat interface built on **LangGraph + LangChain** (OpenRouter default, Ollama optional) with streaming, inline tool-call display, and long-term memory (pgvector semantic recall + rolling per-session summary).

## Layout
```
.
├── docker-compose.yml      # spins up db + backend + frontend
├── .env.example            # copy to .env (gitignored)
├── docs/API_CONTRACT.md    # frozen API + SSE contract
├── backend/                # FastAPI + LangGraph agent (own Dockerfile)
└── frontend/               # Next.js login/register/chat (own Dockerfile)
```

## Quick start
```bash
cp .env.example .env
# edit .env: set JWT_SECRET_KEY and OPENROUTER_API_KEY
docker compose up --build
```
- Frontend: http://localhost:3000
- Backend:  http://localhost:8080  (docs at /docs)
- Postgres: localhost:5433

> Host ports 8080/5433 are used (instead of 8000/5432) to avoid clashing with
> other local services. Change the mappings in `docker-compose.yml` and
> `NEXT_PUBLIC_API_URL` in `.env` together if you want different ports.

The database lives **only** in docker-compose (pgvector image). Backend and frontend each build from their own Dockerfile.

## Screens
1. **Login** — username + password.
2. **Register** — username, email, password1, password2.
3. **Chat** — session sidebar + streaming agentic chat with tool-call traces.

## LLM setup
- `OPENROUTER_API_KEY` + `OPENROUTER_MODEL` — the default chat provider.
- Ollama (`OLLAMA_BASE_URL`, `OLLAMA_MODEL`) is available as a secondary provider.
- Embeddings for long-term memory default to `EMBEDDINGS_PROVIDER=fake` (deterministic, offline). Switch to `ollama` + `nomic-embed-text` for real semantic recall.

See `docs/API_CONTRACT.md` for the full API + streaming event protocol.
