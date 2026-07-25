# BDApps CaaS Sandbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a truthful BDApps-compatible sandbox checkout with balance deduction and a durable receipt, separate from subscription billing.

**Architecture:** A server-side simulator owns virtual balances and CaaS transaction persistence. Authenticated billing endpoints expose a quote and confirmed debit; the existing profile billing page renders the sandbox flow and redacted trace.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, PostgreSQL, Pydantic, Next.js, TypeScript, Tailwind.

## Global Constraints

- Never call a real CaaS debit endpoint in sandbox mode.
- Keep API keys server-only and redact `password` from every returned trace.
- CaaS checkout must not alter recurring subscription state.
- Server owns product and amount; client supplies only product id and confirmation.
- Use exact BDApps-compatible camelCase receipt/request fields at the provider boundary.

---

### Task 1: Persisted CaaS transaction ledger

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/migrations/versions/0011_caas_sandbox_transactions.py`
- Test: `backend/tests/integration/test_caas_sandbox.py`

**Interfaces:**
- Produces `CaasTransaction(user_id, product_id, external_trx_id, internal_trx_id, reference_id, amount_bdt, balance_before_bdt, balance_after_bdt, status_code, status_detail, created_at)`.

- [ ] Write a failing integration test that creates a user, posts a debit, and asserts one persisted receipt has BDT 500 before and BDT 450 after.
- [ ] Run `pytest -q tests/integration/test_caas_sandbox.py` and confirm the missing route/model failure.
- [ ] Add `CaasTransaction` with a unique `external_trx_id`, indexed `user_id`, integer monetary fields, and receipt IDs.
- [ ] Add migration `0011_caas_sandbox_transactions` from `0010_merge_market_research` to create `caas_transactions` and its indexes.
- [ ] Re-run the integration test and confirm the schema is available.

### Task 2: CaaS sandbox provider and API contract

**Files:**
- Create: `backend/app/adapters/caas_sandbox.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/routers/billing.py`
- Test: `backend/tests/unit/test_caas_sandbox.py`
- Test: `backend/tests/integration/test_caas_sandbox.py`

**Interfaces:**
- Produces `CaasQuoteOut` and `CaasDebitOut`.
- Exposes `GET /api/billing/caas/quote` and `POST /api/billing/caas/debit`.
- `POST` input is `CaasDebitRequest(product_id: Literal["fertilizer_bundle"], confirm: Literal[True])`.

- [ ] Write failing unit tests for `build_direct_debit_request`, `debit`, insufficient balance `E1326`, and password redaction.
- [ ] Implement `CaasSandboxProvider` with BDT 500 opening balance, fixed BDT 50 `fertilizer_bundle`, UUID-derived external/internal/reference IDs, exact CaaS request keys, and receipt response keys.
- [ ] Add Pydantic models for quote, debit input, request trace, receipt, and balance transition.
- [ ] Add authenticated quote and debit routes. Quote derives `tel:88{user.phone}` and debit ignores client-side amount/subscriber values.
- [ ] Make debit idempotent by returning the persisted receipt for a reused external transaction internally; browser route always creates one server transaction per confirmation.
- [ ] Run focused unit and integration tests.

### Task 3: Billing-tab sandbox checkout

**Files:**
- Create: `frontend/src/components/billing/CaasSandboxCheckout.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/app/profile/page.tsx`

**Interfaces:**
- Consumes `apiCaasQuote()` and `apiCaasDebit("fertilizer_bundle")`.
- Produces a receipt panel with status, IDs, balance transition, and redacted request trace.

- [ ] Add TypeScript types matching `CaasQuoteOut` and `CaasDebitOut` and API-client calls to `/api/billing/caas/quote` and `/api/billing/caas/debit`.
- [ ] Build a three-state modal: review BDT 50 bundle and BDT 500 balance, confirm sandbox debit, receipt with BDT 450 balance and trace.
- [ ] Add a compact `BDApps CaaS Sandbox` panel to Billing with an explicit “No real mobile balance is charged” label.
- [ ] Keep existing `BdAppsCheckout` untouched and do not change plan/subscription state.
- [ ] Run `npm run typecheck` and `npm run build`.

### Task 4: Demo verification and documentation

**Files:**
- Modify: `docs/API_CONTRACT.md`
- Modify: `docs/BDAPPS_SETUP.md`
- Modify: `README.md`
- Test: `backend/tests/integration/test_caas_sandbox.py`

- [ ] Document the two CaaS routes, request/response examples, fixed BDT 50 sandbox price, and the fact that it is BDApps-compatible local simulation.
- [ ] Document the real-gateway evidence: complete read-only balance requests returned HTTP 404 and are not represented as carrier validation.
- [ ] Start Compose, execute the authenticated sandbox checkout once, and verify receipt persistence plus unchanged subscription state.
- [ ] Run focused backend tests, frontend typecheck/build, and `git diff --check`.
