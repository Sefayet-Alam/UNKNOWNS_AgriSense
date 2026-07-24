# Frontend handoff — AgriSense

Last updated by: Codex (Jul 25, 2026).

## Current branch and rules

- Branch: `feat/bdapps-plus`, tracking `origin/feat/bdapps-plus` and currently ahead by 13 commits.
- Current worktree already contains uncommitted billing/profile changes; do not overwrite them.
- Latest `origin/main` was merged cleanly at `4c0ea17`, bringing in regenerated agent graph docs
  from `b64b6f5`.
- Never commit or push without Sefayet's explicit approval.
- Browser API base is `NEXT_PUBLIC_API_URL` (`http://localhost:8080` under compose).
- `docker-compose.yml` and `docs/API_CONTRACT.md` are authoritative.

## Billing and passwords

- Billing state is server-owned; do not restore `localStorage["agri_tier"]`.
- Frontend client functions live in `src/lib/api.ts`; subscription UI is in
  `src/app/profile/page.tsx` and `src/components/billing/BdAppsCheckout.tsx`.
- Mock billing OTP is `1234`. Real BDApps mode never exposes the OTP.
- `/api/billing/plans` returns `subscribable_plan_ids`; in real mode Plus and
  Pro become available independently when their own BDApps app credentials are
  configured.
- `/api/billing/otp/verify` is the terminal subscription action. On success,
  `BdAppsCheckout` immediately calls `onSuccess`, updates the active plan, and closes;
  do not restore a receipt-gated “Continue with subscription” button.
- Real checkout explicitly states the recurring monthly mobile charge before
  requesting/verifying OTP. Keep this consent copy and the immediate activation behavior.
- A user must cancel an active paid plan before switching to the other BDApps
  application; do not enable direct switching because it could leave both
  recurring carrier subscriptions active.
- Password recovery route: `/forgot-password`, linked from login and registration.
- Profile password change calls `/api/auth/password/change`.

## Delta Field Atlas redesign

- Light-only visual system: rice paper, paddy green, jute, clay, and river blue.
- The logo and `public/favicon.svg` share the delta-field/rice geometry.
- The home hero uses a licensed rural Bangladesh paddy photograph with an AgriSense field-brief
  overlay; the earlier abstract React Three Fiber scene is no longer rendered.
- The planning route has five steps. Its yellow SVG reveal uses `getTotalLength()` at runtime;
  do not restore a hard-coded dash length or it will stop before the fifth node.
- The unauthenticated `/demo` route, `WorkspaceShell`, `mockAgent`, and its local upload helper
  were removed. Do not restore a parallel mock workspace; the real authenticated chat is the only
  workspace. On the authenticated landing header, `Open workspace` stays left of `Log out`.
- Bangladesh photographs are local under `public/images/`; licensing and source URLs are in
  `public/images/IMAGE_CREDITS.md`.
- Auth routes share `components/layout/AuthShell.tsx`. Keep each page's existing handlers intact.
- Profile tabs are controlled by `/profile?tab=info|history|billing`; never restore local-only tab
  state because refresh/direct-link persistence is required.
- History summaries use the existing `/api/chat/sessions` data only. The illustrative fallback is
  shown and labeled only when the endpoint errors or returns no saved sessions.
- Form controls and chat composers intentionally avoid green/teal outer focus rectangles. Inputs
  use a subtle clay/neutral border and shadow; buttons/links keep a terracotta keyboard indicator.
  Interactive buttons, sidebar rows, suggestions, and key cards use restrained lift/floating hover
  feedback with the global reduced-motion guard.

## Chat tool traces

- Backend persistence deliberately stores native tool-call AI messages and final-answer AI messages
  separately so model history replay remains valid.
- `src/lib/chatTurns.ts` aggregates those adjacent rows onto the final answer for display and hides
  only superseded empty tool-step bubbles.
- `mergeById` must keep live SSE rows authoritative over stale persisted rows; otherwise a completed
  `message_update` result can disappear intermittently.
- `ChatProvider` writes `message` and `message_update` frames through to the React Query cache.
  Preserve this when changing stream/session behavior.
- Every completed final reply renders one trace pill, including no-tool turns. `turnDurationMs`
  derives the durable `Thought for …` value from the preceding persisted user timestamp and final
  assistant timestamp; do not replace it with refresh-unsafe component-only timing.

## Registration address hierarchy

- `docs/upazilas.csv` is the source of truth for division, district, and upazila options.
- `scripts/data_harvest/build_frontend_geocodes.py` regenerates
  `src/data/bd-geocodes.json`; rerun it whenever the CSV changes.
- The generated hierarchy currently contains 8 divisions, 64 districts, and 497 upazilas and is
  shared by registration and profile address editing. Do not restore the older CZIS snapshot,
  which mixed metropolitan/thana records into the upazila dropdown.

## Verification

- Jul 25 mobile viewport pass: landing/home typography, spacing, photo overlays, and stats were
  tightened for phones; chat now uses a mobile top bar + drawer session list, floating trace
  trigger, `100dvh`, and tighter composer; profile/billing rows wrap and scroll safely on narrow
  screens. Laptop view is preserved through existing `sm`/`lg` classes. Verification passed:
  `npm run typecheck`, `npm run build`, rebuilt Compose frontend, frontend/backend HTTP 200.
  Final phone screenshot: `/private/tmp/agrisense-mobile-final-3.png`; desktop reference:
  `/private/tmp/agrisense-desktop-after.png`.
- Jul 25 runtime/context pass: Docker Desktop was opened and the existing Compose stack is running.
  Frontend `http://localhost:3000`, backend docs `http://localhost:8080/docs`, and Postgres
  `localhost:5433` all responded/healthy. Frontend production logs still show Next standalone
  `sharp` image-optimization warnings, although the optimized hero image endpoint returned
  `200 image/jpeg`; revisit during demo hardening if it persists after a fresh rebuild.
- `npm run typecheck` passes.
- `npm run build` passes.
- The production route manifest contains no `/demo`.
- Full merged backend suite: 224 tests pass after adding persisted-provider cancellation,
  automatic development fallback, dev-no-cooldown, and direct Plus-upgrade regressions.
- Focused streaming/tool-trace suite: 6 tests pass.
- Direct frontend state assertions cover live-over-persisted precedence, final-turn aggregation,
  and persisted turn-duration formatting.
- Backend test command from inside Compose:
  `docker compose exec -T -e TEST_DATABASE_URL=postgresql+asyncpg://argi:argi_dev_password@db:5432/argi_test backend pytest -q`.
- Docker services are running on frontend `:3000`, backend `:8080`, Postgres `:5433`.

## Remaining BDApps work

Set the per-plan `BDAPPS_PLUS_*` and `BDAPPS_PRO_*` application credentials in root `.env`, set
`BILLING_PROVIDER=bdapps`, rebuild, then test request/verify/status/cancel with real eligible Robi
numbers. Plus ID is `APP_139278`; both API passwords and the Pro ID are still external prerequisites.
Both apps use `/api/bdapps/sms/receive` and `/api/bdapps/subscription/notify`.

`BILLING_PROVIDER=mock` is only AgriSense's deterministic local rehearsal; it is not the official
BDApps sandbox. The currently published Pro SDK Simulator guide documents SMS/USSD/CaaS endpoints,
but no OTP or Subscription endpoints, so it cannot validate this checkout. Request a
subscription-capable sandbox from BDApps support or wait for issued application API passwords.
Existing subscriptions must always resolve status/cancellation from their stored `provider`,
independent of the current runtime mode.

When configured mode is `bdapps` but zero complete app ID/password pairs exist, the plans API
reports effective provider `mock` and enables OTP `1234` for both paid plans. The first complete
BDApps credential pair disables mock activation globally; only fully credentialed tariffs remain.
Development OTP requests are intentionally repeatable; cooldown applies only to the carrier.

Plan prices are server-authoritative and personalized. Active Plus users receive a Pro
`amount_bdt` of 249 and upgrade directly in development mode; do not restore the old
cancel-before-switch UI. Real BDApps mode intentionally withholds that upgrade until a separate BDT
249 carrier application is provisioned—the regular BDT 499 Pro app cannot represent the discount.
