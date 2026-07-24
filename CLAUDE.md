# AgriSense AI — Project Guide

> Bdapps Agentic AI Hackathon (IUT 12th ICT Fest). Full brief:
> [docs/Agentic_AI_Hackathon_Final_Question.pdf](docs/Agentic_AI_Hackathon_Final_Question.pdf).
> **Hard deadline: hacking ends 25 July 2026, 09:00.** On-time = final commit
> pushed before the cutoff. Repo naming convention `TeamName_AgriSense` — ours is
> `UNKNOWNS_AgriSense`.

## The mission

Build an **agent, not a chatbot**: an autonomous agricultural advisor that takes a
smallholder farmer from an empty field to a **costed, weather-aware season plan**,
and keeps advising through harvest. It must hold a conversation to learn the farm,
pull real external data, chain multiple dependent steps toward a goal, remember
context across turns/sessions, and explain every recommendation in terms of the
inputs behind it ("apply 45 kg/acre urea in 3 days *because* soil is sandy, rice is
vegetative, and no rain is forecast" — not "apply urea").

Five judged agentic behaviors: **tool use, multi-step planning, handling missing
information, memory, explainability.**

## Scope discipline (read before building)

The single biggest way teams lose is half-building many features. **Ship Tier 0
end-to-end first; add a tier only when the layer beneath it works.** A payment demo
whose crop advice ignores the weather it just fetched will be noticed.

### Tier 0 — Core (REQUIRED). Single path: short conversation → grounded, explained, costed season plan for one farm.

| # | Capability | Done when | Status |
|---|---|---|---|
| 1 | Conversational intake | Collects ≥ location, farm size, soil type, water availability, budget, target season; asks targeted follow-ups only for missing fields | ❌ TODO (agent is generic; no slot-filling) |
| 2 | Live weather grounding | Calls a **real** weather API by location; uses actual rainfall/temp, no invented forecasts | ❌ TODO (no weather tool) |
| 3 | Crop recommendation | Ranks ≥3 candidate crops w/ suitability, water need, risk, rough profit | ❌ TODO |
| 4 | Season plan | Dated calendar: sowing window, fertilizer timing, irrigation, weed/pest checkpoints, harvest | ❌ TODO |
| 5 | Financial projection | Itemized cost + yield, revenue, net profit, ROI, break-even; internally consistent (change input → outputs change) | ❌ TODO |
| 6 | Explained reasoning | Every recommendation names the specific farm inputs + retrieved data it rests on | ⚠️ partial (LLM explains, not yet grounded) |
| 7 | Knowledge base + RAG | Agronomic data (extension manuals, fertilizer/crop/soil refs) ingested into a KB; agent retrieves; crop/fertilizer/plan advice grounded in retrieval, not model recall | ❌ TODO (pgvector exists for memory, no agronomic KB) |
| 8 | Visible agent trace | UI exposes every tool call, params sent, raw values returned | ✅ DONE (tool-trace chips + `message_update` frames) |

### Tier 1 — Advanced (differentiators)
Persistent memory across sessions (✅ infra done via pgvector), proactive
weather-triggered advice, fertilizer/irrigation scheduler, pest/disease risk,
scenario simulation ("what if rainfall drops 30%?" → revised numbers).

### Tier 2 — Bonus (only after Tier 0 solid)
Marketplace/supplier comparison (mock catalog OK), market price intelligence
(sell/store/wait), leaf-photo disease detection, **bdapps CaaS Payment Gateway**
(sandbox — docs: https://dev.bdapps.com/API_Documentation/bdapps_tap_api.html),
Bengali/voice interaction.

### Judging (100 pts)
Agentic behavior 20 · Scope & execution 15 · Accuracy & practicality 20 ·
Knowledge base 12 · bdapps Payment 10 · Explainability 10 · Tech implementation 8 ·
Innovation 5. **"Don't spend too much time on UI/UX."** Priority = a stable Tier 0
that runs end-to-end in a 4-minute demo.

## What is built now (infrastructure + agent shell)

Full-stack scaffold already runs end-to-end; the domain capabilities above are the
remaining work.

- **Auth**: JWT register/login/me + refresh with rotation, jti blacklisting, reuse
  detection, logout blacklist. ([backend/app/routers/auth.py](backend/app/routers/auth.py), [backend/app/security.py](backend/app/security.py))
- **Chat**: SSE streaming, user-scoped sessions/messages, tool-trace display.
  ([backend/app/routers/chat.py](backend/app/routers/chat.py), [backend/app/agent/runner.py](backend/app/agent/runner.py))
- **Agent**: single-agent LangGraph ReAct loop, OpenRouter default (Ollama optional).
  Current tools are placeholders (`get_current_time`, `calculator`) + `save_memory`/
  `recall_memory`. ([backend/app/agent/graph.py](backend/app/agent/graph.py), [backend/app/agent/tools.py](backend/app/agent/tools.py))
- **Memory**: long-term semantic recall via pgvector + rolling per-session summary.
  ([backend/app/agent/memory.py](backend/app/agent/memory.py))
- **Frontend**: Next.js login/register/chat, agri-green theme, streaming + tool
  chips. ([frontend/src/](frontend/src/))

## Where to build Tier 0 (extension points)

- **New agent tools** (weather API, crop DB, KB retrieval, financial calc) →
  add `@tool` functions in [backend/app/agent/tools.py](backend/app/agent/tools.py); register in the graph's tool
  list. Streaming + trace UI handle new tools automatically — **no frontend change
  needed** for a tool to appear as a chip.
- **Structured intake / planning** → the graph is a single ReAct node today; for
  slot-filling + multi-step planning, evolve [backend/app/agent/graph.py](backend/app/agent/graph.py) (state in
  [backend/app/agent/state.py](backend/app/agent/state.py)). Keep the runner's SSE event contract intact.
- **RAG knowledge base** → ingest agronomic docs into a new pgvector table
  (separate from `long_term_memory`), expose a `search_knowledge_base` tool.
- **Emit progress** from long tools via `get_stream_writer()` (see `_emit` in
  tools.py) → surfaces as `progress` SSE frames in the working indicator.
- The API + SSE contract is **frozen** in [docs/API_CONTRACT.md](docs/API_CONTRACT.md); honor it so the
  frontend keeps working.

## Dev commands

```bash
cp .env.example .env          # set JWT_SECRET_KEY + OPENROUTER_API_KEY
docker compose up --build     # db (pgvector) + backend + frontend
docker compose logs -f backend
docker compose down           # stop  (-v also wipes the db volume)
```

- Frontend http://localhost:3000 · Backend http://localhost:8080 (docs `/docs`) ·
  Postgres localhost:5433. (Host ports 8080/5433 avoid local clashes; container
  ports are 8000/5432. `NEXT_PUBLIC_API_URL` in `.env` is baked into the frontend at
  build time — rebuild the frontend after changing it.)
- Seeded test user during dev: `farmer1` / `greenpass1`.
- Quick backend smoke test: register → login → `POST /api/chat/stream` with
  `Accept: text/event-stream, */*` and a `Bearer` access token.

## Conventions & constraints

- **Real vs mock**: the submission README must clearly state which data is
  real/live and which is generated/mock. Weather + payment should be genuinely
  called (sandbox OK); a seeded supplier/price catalog is explicitly allowed.
- **Grounding over invention**: numbers in the plan must come from a real tool call
  or the KB, and be traceable in the visible trace — never model imagination.
- **Financial math must be internally consistent**: judges will change an input and
  check the outputs change correctly. Keep the calc deterministic (do it in a tool,
  not free-text from the LLM).
- **Secrets**: `.env` is gitignored (holds the real OpenRouter key); `.env.example`
  stays blank. Teams provide their own API keys.
- **GitHub auth is SSH** (`git@github.com:abrar-nazib/UNKNOWNS_AgriSense.git`); never
  switch origin to HTTPS on this machine.
- **All application code must be written during the 24h window** — scaffolding is
  fine, a pre-existing AgriSense codebase is not.
- Backend: async SQLAlchemy 2.0, match existing file layout. Frontend: don't
  over-invest in UI polish (low judged weight) — spend the time on Tier 0 substance.
