# Deterministic Intake Research Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop incomplete-profile farm planning from consuming external research tools and remove stale five-crop routing assumptions.

**Architecture:** `graph.py` owns deterministic admission and conditional force policy; `tools.py` retains a fail-closed direct-call gate and exposes the widened catalog limit. Prompts describe sourced capability accurately rather than using the historic five-crop list. Tests cover the policy at helper, tool, and SSE boundaries.

**Tech Stack:** Python 3.12, FastAPI, LangGraph, LangChain tools, pytest, SQLAlchemy async.

## Global Constraints

- A request may execute at most six live tool rounds.
- No web/Wikipedia network call may occur before all six farm slots are complete.
- Do not alter the user’s existing `.env.example` change.
- Preserve five sourced Rabi dated calendars while allowing the 67-crop finance catalog and a maximum request limit of 50.

---

### Task 1: Deterministic graph admission and force policy

**Files:**
- Modify: `backend/app/agent/graph.py:42-75, 280-380, 440-525`
- Test: `backend/tests/unit/test_graph_routing.py`
- Test: `backend/tests/unit/test_tools.py`

**Interfaces:**
- Produces `enforce_intake_admission(intent: str, text: str, farm_context: dict) -> str`.
- Produces `research_is_eligible(messages: list) -> bool` for conditional force policy.

- [ ] **Step 1: Write failing routing and budget tests**

```python
def test_incomplete_personalised_planning_cannot_escape_intake():
    farm = {"missing_required_fields": ["farm_size", "budget"]}
    assert enforce_intake_admission("planner", "help plan my farm", farm) == "intake"
    assert enforce_intake_admission("recommender", "which crop", farm) == "intake"

def test_complete_profile_keeps_specialist_intent():
    assert enforce_intake_admission("recommender", "which crop", {}) == "recommender"

def test_tool_budget_is_six():
    assert MAX_TURNS == 6
```

- [ ] **Step 2: Run the unit tests and confirm they fail because the policy does not exist and the budget is 12**

Run: `pytest -q tests/unit/test_graph_routing.py tests/unit/test_tools.py`

- [ ] **Step 3: Implement the pure admission helper and use it in `classify_node`**

```python
def enforce_intake_admission(intent, text, farm_context):
    missing = (farm_context or {}).get("missing_required_fields") or []
    if not missing:
        return intent
    if intent in {"recommender", "planner", "finance"} or _PLANNING_OPENING_WORDS.search(text or ""):
        return "intake"
    return intent
```

Use it after `_classify`; do not rely on the LLM prompt for this boundary.

- [ ] **Step 4: Require research only after a successful actionable result**

Make the recommender research requirement conditional on a `rank_crop_candidates` tool result with `status="ok"`. Remove forced web/Wikipedia prefixes from planner and finance; their deterministic tools validate the crop/profile before optional research can be used.

- [ ] **Step 5: Run focused routing tests and commit Task 1**

Run: `pytest -q tests/unit/test_graph_routing.py tests/unit/test_tools.py`

### Task 2: Repair and strengthen the tool-level fallback

**Files:**
- Modify: `backend/app/agent/tools.py:530-570, 2910-3011`
- Modify: `backend/tests/integration/test_crop_recommendation.py:36-74`

**Interfaces:**
- `build_research_tools(user)` returns `web_search` and `search_wikipedia` which return `status=PROFILE_INCOMPLETE` without invoking adapters when profile slots are missing.

- [ ] **Step 1: Correct the failing hotfix test**

```python
async def test_research_tools_are_banned_until_profile_is_complete(
    auth_client, db_session, monkeypatch
):
    user, _farm = await _user_and_farm(db_session)
```

- [ ] **Step 2: Run the test and confirm it fails only if the tool gate leaks to a provider**

Run: `pytest -q tests/integration/test_crop_recommendation.py::test_research_tools_are_banned_until_profile_is_complete`

- [ ] **Step 3: Update stale profile/tool descriptions**

Ensure `get_farm_profile` lists `soil_type` among mandatory slots and research-tool documentation describes the active production gate, not dormant tools.

- [ ] **Step 4: Run the integration test and commit Task 2**

Run: `pytest -q tests/integration/test_crop_recommendation.py::test_research_tools_are_banned_until_profile_is_complete`

### Task 3: Replace legacy five-crop routing and recommendation cap

**Files:**
- Modify: `backend/app/agent/graph.py:285-322`
- Modify: `backend/app/agent/tools.py:1051-1071, 1330-1345, 1540-1545, 2141-2143, 2417-2418`
- Modify: `backend/app/engines/crop_ranker.py:470-482`
- Test: `backend/tests/unit/test_graph_routing.py`
- Test: `backend/tests/integration/test_crop_recommendation.py`

**Interfaces:**
- Bare exact names from `finance_mod.supported_finance_crops()` route to `planner` without a hand-maintained five-crop list.
- `rank_crop_candidates(limit)` accepts 3 through 50, returning only eligible candidates.

- [ ] **Step 1: Write failing catalog and limit tests**

```python
def test_bare_current_catalog_crop_routes_to_planner():
    assert classify_heuristic("lentil") == "planner"

async def test_rank_request_accepts_fifty(...):
    result = json.loads(await build_crop_recommendation_tool(user).ainvoke({"limit": 50}))
    assert len(result["candidates"]) <= 50
```

- [ ] **Step 2: Run tests to confirm the legacy behavior fails**

Run: `pytest -q tests/unit/test_graph_routing.py tests/integration/test_crop_recommendation.py`

- [ ] **Step 3: Implement catalog-derived bare-crop recognition and a 50 candidate cap**

Import the finance catalog into graph routing, replace hard-coded plan/finance crop clauses with generic intent phrases, and change both ranker caps from `5` to `50`. Keep default `limit=5` for concise normal responses.

- [ ] **Step 4: Correct prompts and docstrings precisely**

Describe five crops only as the sourced dated-calendar/schedule path. Describe finance coverage and candidate limits independently; never promise a dated plan for an unsupported crop.

- [ ] **Step 5: Run focused recommendation tests and commit Task 3**

Run: `pytest -q tests/unit/test_graph_routing.py tests/integration/test_crop_recommendation.py`

### Task 4: Prove the streaming boundary

**Files:**
- Modify: `backend/tests/e2e/test_pdf_tier0_journey.py`
- Modify: `backend/tests/fakes.py` only if a purpose-built forced-misroute fake is necessary.

**Interfaces:**
- The opening message `Can you help me plan my farm?` yields an intake question and has no `web_search` or `search_wikipedia` trace.

- [ ] **Step 1: Add an SSE assertion for the opening-turn tool trace**

```python
opening_tools = {trace["tool"] for trace in _completed_traces(all_events[0])}
assert opening_tools <= {"get_farm_profile", "update_farm_profile", "resolve_season"}
assert not opening_tools & {"web_search", "search_wikipedia"}
```

- [ ] **Step 2: Run the single end-to-end journey against a unique test database**

Run: `TEST_DATABASE_URL='postgresql+asyncpg://argi:argi_dev_password@localhost:5433/argi_intake_gate_20260725' pytest -q tests/e2e/test_pdf_tier0_journey.py::test_vague_opening_reaches_grounded_explained_costed_plan`

- [ ] **Step 3: Run all focused regression tests and commit Task 4**

Run: `pytest -q tests/unit/test_graph_routing.py tests/unit/test_tools.py tests/integration/test_crop_recommendation.py tests/e2e/test_pdf_tier0_journey.py tests/streaming/test_stream_agent.py`
