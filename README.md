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

Backend startup runs Alembic and then verifies/restores the committed 287-chunk
FRG 2024 vector seed before serving. The restore uses committed embeddings and
does not spend embedding API calls; complete databases are left untouched.

- Frontend: http://localhost:3000
- Backend:  http://localhost:8080  (docs at /docs)
- Postgres: localhost:5433

> Host ports 8080/5433 are used (instead of 8000/5432) to avoid clashing with
> other local services. Change the mappings in `docker-compose.yml` and
> `NEXT_PUBLIC_API_URL` in `.env` together if you want different ports.

The database lives **only** in docker-compose (pgvector image). Backend and frontend each build from their own Dockerfile.

## Screens
1. **Login / reset password** — mobile-number auth with mock OTP recovery.
2. **Register** — name, mobile, Bangladesh address and password.
3. **Chat** — session sidebar + streaming agentic chat with tool-call traces.
4. **Profile / billing** — persisted subscription, cancel, and password change.

## Hackathon Tier 0 path

The focused demo path is: targeted six-field farm intake → live weather and
official point-suitability crop ranking → selected-crop dated calendar → an
itemized financial projection. The planner combines BAMIS crop calendars, the
BARC Fertilizer Recommendation Guide 2024 knowledge base, live BARC CZIS crop,
variety and farm-scaled fertilizer results, and live Open-Meteo weather. Native
tool calls, arguments and raw results are visible in the chat trace.

Financial arithmetic is deterministic (`Decimal`) and exposes itemized cost,
expected yield, revenue, net profit, ROI, break-even yield and break-even price.
Changing area, yield, sale price, cost items or a cost percentage recomputes the
dependent values. The tool also returns internal math checks.

The backend suite includes whole-product SSE journeys, not only unit tests: a
five-turn vague-opening-to-costed-plan flow, complete plan and finance flows for
all five focused crops, missing-profile hard gates for every crop, live-source
failure drills, and persisted raw-trace checks.

## Agricultural data: real vs generated/demo

| Data or behavior | Classification | Notes |
|---|---|---|
| Weather | **Real/live** | Open-Meteo forecast at the active farm coordinates; outage is surfaced, never filled in. |
| Crop point suitability | **Real/live** | Official BARC CZIS GeoServer response. |
| Variety yield and farm-scaled fertilizer | **Real/live** | Official BARC CZIS endpoints; the raw yield range and fertilizer response remain in the trace. |
| Crop calendar and fertilizer guidance | **Real/public reference** | BAMIS Rajshahi crop-weather calendars and FRG 2024; FRG is retrieved through the pgvector RAG store. |
| Soil default | **Real/public reference, bundled snapshot** | Upazila survey default; labelled as an assumption that the farmer must confirm. |
| Financial sale price and cultivation cost defaults | **Generated/seeded demo assumptions** | Not a market board or supplier quote. Every such value is labelled `seeded_demo_value`; farmer estimates override it. |
| Financial formulas | **Real deterministic computation** | Server-side `Decimal` math with inspectable identities and break-even values. |
| Billing | See below | Mock by default; real BDApps is configurable. |

## Billing: real vs mock

- Default `BILLING_PROVIDER=mock`: OTP is `1234`; subscription state is real
  Postgres data, but no operator charge occurs.
- `BILLING_PROVIDER=bdapps`: the backend uses the real BDApps OTP and
  Subscription APIs with server-only credentials. Configure the variables in
  `.env.example`; never expose the password through a `NEXT_PUBLIC_*` variable.

## LLM setup
- `OPENROUTER_API_KEY` + `OPENROUTER_MODEL` — the default chat provider.
- Ollama (`OLLAMA_BASE_URL`, `OLLAMA_MODEL`) is available as a secondary provider.
- Embeddings for long-term memory default to `EMBEDDINGS_PROVIDER=fake` (deterministic, offline). Switch to `ollama` + `nomic-embed-text` for real semantic recall.

See `docs/API_CONTRACT.md` for the full API + streaming event protocol.
