# AgriSense AI — Architecture Brief & Presentation Context

> **What:** an autonomous agricultural advisor that takes a Bangladeshi smallholder
> farmer from an empty field to a **costed, weather-aware, explained season plan**,
> and keeps advising through harvest.
> **Repo:** `UNKNOWNS_AgriSense` · **Brief:** [Agentic_AI_Hackathon_Final_Question.pdf](Agentic_AI_Hackathon_Final_Question.pdf)
> **This doc doubles as the architecture reference and the presentation script.**

---

## 1. The thesis in one sentence

The judged bar is **"an agent, not a chatbot."** AgriSense is built around a single
hard rule that makes that difference structural, not cosmetic:

> **The LLM gathers information and explains it. Deterministic Python engines compute
> every farmer-facing number. Every number is traceable to a real tool call or the
> knowledge base — never model imagination.**

A chatbot would let the model *say* "apply urea." AgriSense forces the model down a
tool pipeline: read the farm, call the official soil/suitability service, call the
real weather API, retrieve the fertilizer guide, run a `Decimal` finance engine — and
only then explain the result in the farmer's language, naming the inputs behind it.

---

## 2. System architecture (layers)

```
┌──────────────────────────────────────────────────────────────────────────┐
│  FRONTEND  Next.js chat UI (login/register, SSE stream, tool-trace chips)  │
│            visible agent trace = every tool call + params + raw result     │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │  SSE (text/event-stream), JWT (phone identity)
┌───────────────────────────────▼──────────────────────────────────────────┐
│  API  FastAPI (async)   routers: auth · chat · geo · uploads · alerts ·   │
│                                   bdapps · billing                         │
│       frozen SSE contract: session · message · progress · message_update · │
│                            done · error                                    │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────────────┐
│  AGENT  LangGraph multi-node supervisor                                    │
│                                                                            │
│   START → classify → { intake │ advisor │ recommender │ planner │ finance }│
│                          │        │          │           │         │       │
│                          └────────┴────┬─────┴───────────┴─────────┘       │
│                                        ▼                                    │
│                            ONE shared ToolNode ──→ returns to active_agent  │
│                                        │                                    │
│                                        └──→ END when no tool calls remain   │
│                                                                            │
│   FORCED_TOOL_SEQUENCE compels grounding per node (see §4)                  │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ tools are thin wrappers; they never do math
┌──────────────┬────────────────┼────────────────┬─────────────────────────┐
│ ENGINES      │ ADAPTERS        │ RAG             │ DATA STORES             │
│ (pure, no IO)│ (real HTTP)     │ (pgvector)      │                         │
│ crop_ranker  │ weather (Open-  │ chunker         │ Postgres + pgvector     │
│ season_      │  Meteo)         │ store (cosine   │  12 tables incl. farms, │
│  planner     │ czis / czis_    │  top-k, 1536-d) │  chat, knowledge_chunks,│
│ finance      │  suitability    │ FRG 2024 corpus │  long_term_memory,      │
│  (Decimal)   │  (BARC CZIS)    │  → 287 chunks   │  season_plans,          │
│ scheduler    │ research (DDG,  │ OpenRouter      │  weather_alerts,        │
│ leaf_disease │  Wikipedia)     │  embeddings     │  attachments            │
│ weather_     │ billing (BDApps)│                 │ Alembic-owned schema    │
│  alerts      │ sms · transcribe│                 │  (0001→0009)            │
│ units        │                 │                 │                         │
└──────────────┴─────────────────┴─────────────────┴─────────────────────────┘
```

**Why this shape wins points:** the four bottom columns are the "agent, not chatbot"
proof. Adapters make external calls *real*; engines make math *deterministic and
inspectable*; RAG makes advice *retrieved, not recalled*; the trace makes all of it
*visible to a judge*.

---

## 3. The agent graph in detail

Nodes (`backend/app/agent/graph.py`, `AGENTS = (intake, advisor, recommender, planner, finance)`):

| Node | Job | Key tools |
|------|-----|-----------|
| **classify** | Route each turn from the farmer's LAST message. Cheap `OPENROUTER_MODEL_LITE` LLM + deterministic keyword fallback (fallback is the only path under `TESTING`). Also refreshes `reply_language`. | — |
| **intake** | Slot-filling: collect + save the six mandatory farm fields. | `get_farm_profile`, `update_farm_profile`, `get_soil_context`, `resolve_season`, `list/select/create_farm` |
| **advisor** | General agronomy, weather, fertilizer, disease-photo, weather alerts. | `get_weather`, CZIS tools, `search_knowledge_base`, `classify_leaf_disease`, `get_weather_alerts`, memory |
| **recommender** | Dedicated crop-choice node. | `rank_crop_candidates`, `czis_crop_varieties`, KB |
| **planner** | Dated season calendar for a chosen crop. | `generate_season_plan`, `generate_input_schedule`, KB + research |
| **finance** | Cost/yield/profit + what-if scenarios. | `calculate_crop_financials`, `simulate_scenario`, KB + research + calculator |

- **One shared `ToolNode`** executes whatever tool the active node called, then returns
  control to `state.active_agent`. Per-node LLMs via `build_chat_model(model)`.
- **`MAX_TURNS = 12`** tool rounds per request (replayed history rounds excluded, so long
  sessions never lose tool access).
- **`reply_language`** lives in graph state, refreshed by `classify` from every user
  message (Bengali script / Banglish → Bengali; else English); each node appends the
  language directive LAST so recency keeps it authoritative.

---

## 4. Strict tool-calling: `FORCED_TOOL_SEQUENCE`

A lite specialist model sometimes answers from memory instead of calling tools. We make
grounding **structural, not hoped-for**: on a node's first tool rounds, the model is bound
with `tool_choice` forcing a specific tool. Round *N* forces `sequence[N]`; after the
sequence, the node binds normally (`backend/app/agent/graph.py: FORCED_TOOL_SEQUENCE` +
`make_agent_node`).

| Node | Forced sequence (in order) | Effect |
|------|----------------------------|--------|
| **recommender** | `rank_crop_candidates` (ordered) **+** one `web_search` **and** one `search_wikipedia` (any order) | Cannot recommend without running the deterministic ranking first, then gathering external reference context. The two searches are any-order mandatory (`FORCED_UNORDERED_TOOLS`); they are untrusted reference and never change the ranking. |
| **planner** | `search_knowledge_base` → `web_search` → `search_wikipedia` | Every season plan is preceded by strict KB → DuckDuckGo → Wikipedia research grounding. |
| **finance** | `web_search` → `search_knowledge_base` → `search_wikipedia` → `calculate_crop_financials` → `calculator` | Gathers current input-price context, runs the Decimal projection, then independently verifies a headline figure with the calculator. |

The model still authors each query/expression (`tool_choice` forces *which* function, not
its args). Individual tools that return an "unavailable" payload never block the following
rounds — the sequence continues and the outage is disclosed honestly.

---

## 5. The one rule that keeps numbers honest

`docs/INSIGHTS.md` steer, enforced everywhere:

- **Engines** (`backend/app/engines/`, pure functions, no IO): `crop_ranker`,
  `season_planner`, `finance` (all `Decimal`), `scheduler`, `leaf_disease`,
  `weather_alerts`, `units`. Gold-number unit tests guard them.
- **Tools** are thin wrappers that call engines/adapters and return JSON — they never do
  math themselves.
- **Sentinels forbid invention:** `WEATHER_UNAVAILABLE`, `CZIS_UNAVAILABLE`,
  `SOIL_UNKNOWN`, `PATTERNS_UNKNOWN`, `KB_EMPTY`, `RESEARCH_UNAVAILABLE`,
  `YIELD_UNAVAILABLE`. On any source outage the tool degrades **visibly** and never
  fills the gap with a made-up value.
- **Retrieved KB / web text is UNTRUSTED:** wrapped in `<retrieved_document>` blocks;
  the prompt forbids obeying instructions inside it or lifting farmer-facing quantities
  from prose.

---

## 6. End-to-end working procedure (the Tier-0 journey)

A single farmer conversation, turn by turn. Each row is a real SSE trace a judge can see.

| Turn | Farmer says | Route → node | Tools called (visible chips) | Grounded output |
|------|-------------|--------------|------------------------------|-----------------|
| 1 | "I have 3 bigha in Tanor, want to farm this season" | classify → **intake** | `get_farm_profile` → `update_farm_profile` (area, location) → `get_soil_context` (survey soil) → `resolve_season("this season")` | Saves facts; soil auto-fills from the CZIS edaphic survey; **season grounded in today's real date**, not assumed. Asks only for the still-missing fields (water, budget). |
| 2 | "shallow tubewell, budget 40000 taka" | classify → **intake** | `update_farm_profile` (water, budget) | Six fields complete → confirms the profile. |
| 3 | "which crop should I plant?" | classify → **recommender** | **forced** `rank_crop_candidates` → `czis_crop_varieties` (top 2–3) | Ranks 3–5 crops with suitability (live BARC CZIS point layer), water need, risk, rough profit — each score component inspectable. |
| 4 | "let's go with wheat" | classify → **planner** | **forced** `search_knowledge_base` → `web_search` → `search_wikipedia` → `generate_season_plan` | Dated calendar (land prep → sowing → fertilizer → irrigation → weed/pest → harvest), live-weather-adjusted, live CZIS fertilizer amounts, FRG-cited, with the finance projection embedded. |
| 5 | "what if my budget is cut 40%?" | classify → **finance** | **forced** web → KB → wiki → `calculate_crop_financials` / `simulate_scenario` → `calculator` | Baseline vs revised numbers with explicit deltas; budget-fit recomputed; math verified. |

Every reply names the specific farm inputs and retrieved values it rests on — the PDF's
"Apply 45 kg/acre urea in 3 days *because*…" standard.

---

## 7. How the architecture solves each required problem (with evidence)

### 7a. The five judged agentic behaviors (PDF p.1)

| Behavior | How AgriSense does it | Evidence |
|----------|------------------------|----------|
| **1. Tool use** (real external service, uses returned values) | `get_weather` → **Open-Meteo** live API; `rank_crop_candidates` → **BARC CZIS GeoServer** point suitability; CZIS fertilizer doses relayed verbatim. Values flow into outputs; outage → `WEATHER_UNAVAILABLE`, never invented. | `adapters/weather.py` (`api.open-meteo.com`), `adapters/czis_suitability.py` (`map2.cropzoning.gov.bd/geoserver`), `adapters/czis.py` (`czis.cropzoning.gov.bd`) |
| **2. Multi-step planning** (one request → dependent sequence) | A crop-choice request forces `rank_crop_candidates` → `czis_crop_varieties`; a plan request forces KB → web → wiki → `generate_season_plan` (which itself chains weather + CZIS + FRG). Dependent, not one lookup. | `graph.py: FORCED_TOOL_SEQUENCE`; `tools.py: generate_season_plan` chains weather→CZIS→calendar |
| **3. Handling missing information** (identify gaps, targeted follow-ups) | Six-field **hard gate** (`_missing_slots`); tools return `PROFILE_INCOMPLETE` with the exact `missing_required_fields`; the directive asks for at most TWO missing fields, never a 3+ list. Relative season → `resolve_season` grounds it instead of guessing. | `tools.py: _missing_slots`, `rank_crop_candidates` gate; `engines/season_planner.py: resolve_season` |
| **4. Memory** (across turns and sessions) | Rolling per-session summary + **pgvector long-term semantic recall** + post-turn automatic fact extraction (dedup by embedding distance). Farmer identity injected each session. Farm facts live in the farm profile. | `agent/memory.py`, `long_term_memory` table, `farms` table |
| **5. Explainability** (every recommendation names its inputs) | Deterministic tool outputs carry `farm_inputs`, `score_components`, source evidence, provenance labels and warnings; node directives require relaying them, naming soil/land/irrigation/budget/area/season + retrieved yields/BCR. | `engines/crop_ranker.py` (score_components, risk reasons), `engines/finance.py` (per-value `source_type`) |

### 7b. Tier 0 — the required core (PDF p.2), all 8 done end-to-end

| # | Capability | Solved by | Evidence |
|---|-----------|-----------|----------|
| 1 | Conversational intake | intake node; six-slot gate; soil auto-fill from survey; season date-grounded | `tools.py: build_farm_tools/build_soil_tool/resolve_season`, `data/bd_soil.json` |
| 2 | Live weather grounding | `get_weather` → Open-Meteo (keyless, 16-day, ET0); coordinates-first (farm centroid, offline gazetteer); `WEATHER_UNAVAILABLE` on outage | `adapters/weather.py` |
| 3 | Crop recommendation (≥3, suitability/water/risk/profit) | `rank_crop_candidates` → deterministic `crop_ranker` over live CZIS suitability + weather + budget + recorded rotation economics | `engines/crop_ranker.py`, `adapters/czis_suitability.py`, `data/bd_cropping_patterns.json` |
| 4 | Season plan (dated, land-prep→harvest) | `generate_season_plan` → `season_planner` (BAMIS stages + FRG split timing + live CZIS fertilizer amounts + live weather date shift + RAG) | `engines/season_planner.py: build_season_calendar` |
| 5 | Financial projection (itemized, consistent) | `calculate_crop_financials` → pure `Decimal` engine; low/base/high, ROI, two break-evens, `math_checks` self-verify; change input → outputs change | `engines/finance.py: build_financial_projection` |
| 6 | Explained reasoning | see §7a-5 | across all engine outputs |
| 7 | Knowledge base + RAG | FRG 2024 corpus (287 chunks) in `knowledge_chunks` (pgvector, 1536-d); OpenRouter `text-embedding-3-small`; `search_knowledge_base` on advisor/recommender/planner/finance; cross-lingual (English query) | `rag/chunker.py`, `rag/store.py`, `data/kb_corpus/frg2024.md`, committed seed `data/kb_seed/` |
| 8 | Visible agent trace | SSE `message_update` frames + tool-trace chips; every tool call, params, raw result surfaced; new tools auto-appear as chips | `routers/chat.py`, `agent/runner.py`, frontend `chatTurns.ts` |

### 7c. Judging criteria (PDF p.5, 100 pts) — where the architecture earns each

| Criterion | Pts | Architectural answer |
|-----------|-----|----------------------|
| Agentic behavior | 20 | 6-node graph + forced tool sequences + shared ToolNode + memory (§3, §4, §7a) |
| Scope & execution | 15 | Tier 0 complete end-to-end, single stable path; 428 automated tests; startup self-heals RAG seed |
| Accuracy & practicality | 20 | Deterministic engines, `math_checks`, real CZIS/weather/FRG grounding, outage sentinels |
| Knowledge base | 12 | Real FRG 2024 ingested → pgvector → RAG actually feeds recommender/planner/finance advice |
| **bdapps Payment** | 10 | Real BDApps CaaS sandbox: **Plus = live carrier plan**, Pro = clearly-labelled mock; OTP + subscription + callback flow | 
| Explainability | 10 | Provenance labels + score components + named inputs in every output |
| Technical implementation | 8 | Clean async FastAPI + LangGraph, injectable HTTP clients, Alembic-owned schema (0001→0009), tests where they matter |
| Innovation | 5 | Scenario simulation, proactive weather SMS, leaf-disease detection, voice, forced-research grounding — all on top of a working core |

---

## 8. Beyond core — Tier 1 & Tier 2

**Tier 1 (differentiators):**
- **Persistent memory** across sessions (pgvector + auto-extraction).
- **Proactive weather-triggered advice** — daily forecast scan → `weather_alerts` table → outbound SMS via `adapters/sms.py` (sms.net.bd); farmer can ask `get_weather_alerts`.
- **Fertilizer/irrigation scheduler** — `generate_input_schedule`: staged chemical quantities (live CZIS) with seeded cost, organic IPNS-equivalent alternatives, and an irrigation water balance (BAMIS requirement − effective rainfall).
- **Scenario simulation** — `simulate_scenario`: signed-percent levers (rainfall/budget/cost/price) → baseline-vs-revised deltas.

**Tier 2 (bonus):**
- **bdapps Payment Gateway** — real CaaS sandbox flow (Plus live, Pro labelled mock).
- **Leaf-disease detection** — bundled INT8 TFLite multi-head model (`engines/leaf_disease.py`), on-device, no LLM in the classification path; `classify_leaf_disease` tool.
- **Voice interaction** — `adapters/transcribe.py` (Gemini speech→text, Bengali-native) → normal agent pipeline.
- **Bengali / Banglish** throughout — language detected per message, replies match.

---

## 9. Real vs mock (required by the PDF submission rules)

| Data / service | Status |
|----------------|--------|
| Weather (Open-Meteo) | **REAL, live** |
| Crop suitability (BARC CZIS GeoServer) | **REAL, live** |
| Crop varieties / CZIS fertilizer doses | **REAL, live** |
| Cropping-pattern economics (CZIS snapshot) | **REAL** (bundled snapshot of a real source) |
| Soil survey (CZIS edaphic, 480 upazilas) | **REAL** (bundled) |
| Knowledge base (FRG 2024) | **REAL** ingested corpus |
| Admin gazetteer / centroids (CZIS + OCHA COD-AB) | **REAL** (bundled) |
| Web / Wikipedia research | **REAL, live** (DuckDuckGo, Wikipedia API) |
| Leaf-disease model | **REAL** on-device TFLite |
| Voice transcription (Gemini) | **REAL** |
| BDApps **Plus** plan | **REAL** carrier sandbox |
| BDApps **Pro** plan | **MOCK** (clearly labelled, OTP 1234) |
| Seed input costs / sale prices / retail fertilizer cost | **SEEDED demo** (explicitly labelled, farmer-overridable) |

Core rule: computed farmgate/cost numbers come from a real tool or the KB, or are
**labelled** seeded-demo values the farmer can override. Nothing is silently invented.

---

## 10. Tech stack & quality

- **Backend:** FastAPI (async), SQLAlchemy 2.0 async, Postgres + **pgvector**, Alembic
  migrations (schema-owned, `0001→0009`, single head).
- **Agent:** **LangGraph** 1.x multi-node graph, **LangChain** core, **OpenRouter** chat
  (Gemini) + embeddings (`text-embedding-3-small`), per-node model selection.
- **External:** Open-Meteo, BARC CZIS (GeoServer WMS + REST), DuckDuckGo (`ddgs`),
  Wikipedia Action API, BDApps CaaS, sms.net.bd, Gemini transcription.
- **Frontend:** Next.js, SSE streaming, tool-trace chips (low UI investment by design —
  points are in Tier-0 substance).
- **Auth:** phone number as identity; JWT register/login/refresh with rotation, jti
  blacklist, reuse detection.
- **Tests:** **428 collected** — unit (engines gold-numbers, security, adapters, gazetteer,
  season inference), integration (auth, farm isolation, recommendation, plan, finance,
  scheduler, scenario), streaming (SSE contract, multi-turn journeys), E2E (PDF path +
  per-crop matrices). LLM + HTTP faked → offline, deterministic.
- **Ops:** `docker compose up --build`; startup runs Alembic then `seed_rag_data
  --if-needed` (advisory-locked, restores the 287-chunk RAG seed with zero API calls).

---

## 11. Presentation cheat-sheet (4-minute demo)

**Opening line:** "AgriSense is an agent, not a chatbot — the model never invents a number;
deterministic engines compute, real APIs ground, and every step is visible in the trace."

**Demo path (mirror §6):**
1. Vague opener in Bengali → watch **intake** save facts, auto-fill soil, **ground the
   season in today's date** (`resolve_season` chip), ask only what's missing.
2. "which crop?" → **recommender** forced `rank_crop_candidates` chip → 3–5 ranked crops
   with live CZIS suitability + score components on screen.
3. Pick wheat → **planner** forced KB→web→wiki chips, then a dated calendar with
   FRG-cited fertilizer timing + embedded finance.
4. "what if budget −40%?" → **finance** chips → revised numbers with deltas, math verified.
5. Point at the **trace panel**: "every chip is a real call — params in, raw values out.
   A judge can confirm no number came from the model's imagination."

**If asked "what's real vs mock?"** → §9 table. **If asked about payment** → BDApps Plus is
a live carrier sandbox; Pro is a labelled mock.

**One-sentence close:** "Tier 0 runs end-to-end and stable; every judged agentic behavior
is structural — forced by the graph, not left to the model's goodwill."

---

## 12. Complete data-source register (every URL, every dataset)

This is the full accounting the PDF asks for: what we pulled, from where, what each
source gave us, and which parts went into RAG.

### 12a. Live external APIs — called at runtime

| # | Source | URL / endpoint | Auth | What we get | Used by |
|---|--------|----------------|------|-------------|---------|
| 1 | **Open-Meteo Forecast** | `https://api.open-meteo.com/v1/forecast` | keyless | Daily rainfall, min/max temp, **ET0** (reference evapotranspiration); up to **16 days** ahead + **92 days** past | `get_weather`; season-plan date shift; crop ranking weather risk; scheduler water balance |
| 2 | **Open-Meteo Geocoding** | `https://geocoding-api.open-meteo.com/v1/search` | keyless | lat/lon for a non-admin place name (last-resort only — admin names resolve offline) | `get_weather` fallback |
| 3 | **BARC CZIS REST** | `https://czis.cropzoning.gov.bd` — `/crop/{id}/lat/{}/lon/{}`, `/cropvarietylist/{}`, `/var/{}`, `/croppingpattern/{code}`, `/crops/list2` | keyless | Live crop varieties, **yield (t/ha)** & duration; **server-computed fertilizer doses** (Urea/TSP/DAP/MoP/Gypsum/Zinc, relayed verbatim); recorded rotation economics | `czis_crop_context/varieties/fertilizer_recommendation`, `generate_season_plan`, `calculate_crop_financials` |
| 4 | **BARC CZIS GeoServer (WMS)** | `https://map2.cropzoning.gov.bd/geoserver/wsBARC/wms` — layer `wsBARC:view_biophysics_suite_all` | keyless | **Point land-suitability class** (VS/S/MS/MNS/NS) at exact farm lat/lon, via WMS `GetFeatureInfo` | `rank_crop_candidates` (suitability = 50% of the score) |
| 5 | **DuckDuckGo** (via `ddgs`) | web search | keyless | Untrusted external reference links/snippets (latest prices, crop notes) | recommender, planner, finance (forced) |
| 6 | **Wikipedia Action API** | `https://{lang}.wikipedia.org/w/api.php` | keyless (needs descriptive User-Agent) | Untrusted crop-agronomy background summaries | recommender, planner, finance (forced) |
| 7 | **OpenRouter** | `https://openrouter.ai/api/v1` | key | Chat LLM (Gemini) per node **and** KB embeddings (`openai/text-embedding-3-small`, 1536-d) | whole agent + RAG ingestion |
| 8 | **BDApps CaaS** | `https://developer.bdapps.com` | app key | Payment: OTP + subscription + callback flow (**Plus = live sandbox**) | `routers/bdapps.py`, `adapters/billing.py` |
| 9 | **sms.net.bd** | `https://api.sms.net.bd/sendsms` | key | Outbound SMS delivery for proactive weather advisories | `adapters/sms.py`, `weather_alerts` |
| 10 | **Gemini** | Google Generative AI | key | Voice-note speech→text (Bengali-native), Tier-2 accessibility | `adapters/transcribe.py` |

### 12b. Bundled datasets — harvested from real sources, committed for offline reliability

Government `.gov.bd` endpoints are flaky and some now require login, so we harvested them
**during the hackathon window** (2026-07-24) and committed offline copies. Harvest scripts
live in `scripts/data_harvest/` (provenance in its `README.md`).

| Dataset (`backend/app/data/`) | Size | Real source | What it provides |
|-------------------------------|------|-------------|------------------|
| `bd_admin.json` | 1.7 MB | CZIS `getAdminByCode.php` (hierarchy: 8 div / 64 dist / 497 upazila / 7,761 union) **+** OCHA COD-AB gazetteer centroids (`data.humdata.org/dataset/cod-ab-bgd`, v03 2023, CC BY 3.0 IGO) | Division→district→upazila→union geocodes + lat/lon centroids → pins a farm to exact coordinates at registration |
| `bd_soil.json` | 508 KB | CZIS per-upazila **edaphic survey** (480 upazilas) | Soil texture, land type, drainage, pH → **auto-fills the mandatory soil field** as a survey default |
| `bd_cropping_patterns.json` | 1.3 MB | CZIS `/croppingpattern/{upazila_code}` | Per-upazila recorded rotations + **BCR** (over variable/total cost) + **gross margin Tk/decimal** → the only defensible "rough profit" grounding |
| `czis_crops.json` | 12 KB | CZIS `/crops/list2` | 129-crop catalog (crop ids, seasons, variety groups) → candidate universe for ranking |
| `finance_assumptions.json` | 40 KB | **SEEDED demo** (50 Rabi crops); 5 focused-path crops cite BARC FRG 2024 pages, the rest illustrative | Itemized cost rates + sale prices for the finance engine (labelled demo, farmer-overridable) |
| `crop_disease_int8.tflite` + `class_names.json` | 54 MB | Bundled INT8 TFLite multi-head model (potato/rice/tomato + per-crop disease heads) | On-device leaf-disease classification (no LLM in the path) |

### 12c. BAMIS crop calendars — embedded as sourced constants (not live)

10 **BAMIS Rajshahi crop-weather calendar** PDFs (`bamis.gov.bd`) were transcribed into the
`season_planner.CROP_PLANS` and `crop_ranker.CROP_TRAITS` constants — growth stages, sowing
windows, phase-wise water requirements, and weather-risk thresholds. Each crop carries its
source URL. Focused-path crops: Wheat (`.../5116.pdf`), Maize (`.../5125.pdf`), Boro
(`.../5105.pdf`), Potato (`.../8864.pdf`), Mustard (`.../10986.pdf`); plus lentil/tomato/
onion/garlic/brinjal calendars for trait metadata.

### 12d. What went into RAG (and what deliberately did NOT)

**In the knowledge base** (`knowledge_chunks`, pgvector 1536-d):
- **BARC Fertilizer Recommendation Guide (FRG) 2024** — the full corpus, `app/data/kb_corpus/frg2024.md`
  (400 KB, pages 10–239, embedded text + **tesseract OCR** for image-only AEZ tables, via
  `scripts/data_harvest/frg_ocr_pipeline.py`) → **287 chunks**, source label `"FRG 2024"`.
- Embedded with OpenRouter `text-embedding-3-small`; committed as a zero-API restore seed
  (`app/data/kb_seed/kb_chunks.jsonl` + row-aligned `kb_embeddings.npy`), restored on startup
  by `seed_rag_data --if-needed`.
- **Content:** agronomic *prose* — fertilizer timing/splits, crop practices, soil & nutrient
  management, AEZ fertility tables, pest basics. Retrieved with an **English** query
  (cross-lingual), cited by source + page (e.g. "FRG 2024, p. 87").

**Kept OUT of RAG on purpose** — structured numbers live in JSON and are *computed*, never
retrieved as prose: fertilizer doses (live CZIS), cropping-pattern economics
(`bd_cropping_patterns.json`), finance rates (`finance_assumptions.json`), soil survey
(`bd_soil.json`), yields (live CZIS). Retrieved text is **untrusted** — the prompt forbids
lifting any farmer-facing quantity from it. This is the line that keeps the math honest.

### 12e. Source → problem mapping (how each helped solve the challenge)

| PDF requirement | Sources behind it |
|-----------------|-------------------|
| Live weather grounding | Open-Meteo (1) |
| Crop recommendation (suitability/water/risk/profit) | CZIS GeoServer (4) + CZIS patterns/soil (12b) + Open-Meteo (1) |
| Season plan (dated calendar) | BAMIS calendars (12c) + FRG timing (RAG) + live CZIS fertilizer (3) + Open-Meteo (1) |
| Financial projection | `finance_assumptions.json` (12b) + live CZIS yields (3) |
| Knowledge base + RAG | FRG 2024 (12d) |
| Intake / farm location & soil | `bd_admin.json` + `bd_soil.json` (12b) |
| Explainability | every source above carries provenance labels into the tool output |
| Tier-2 disease / voice / payment | TFLite model (12b) · Gemini (10) · BDApps (8) · sms.net.bd (9) |

---

*Generated as an architecture reference for the AgriSense AI submission. Source of truth
for scope is [Agentic_AI_Hackathon_Final_Question.pdf](Agentic_AI_Hackathon_Final_Question.pdf);
implementation state reflects commit `84e22fa`.*
