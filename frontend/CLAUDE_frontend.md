# Frontend handoff — AgriSense

Last updated by: Codex (Jul 24, 2026).

## Current branch and rules

- Branch: `features/redesign` (created from `feat/agrisense-workspace` for the finalized redesign).
- Never commit or push without Sefayet's explicit approval.
- Browser API base is `NEXT_PUBLIC_API_URL` (`http://localhost:8080` under compose).
- `docker-compose.yml` and `docs/API_CONTRACT.md` are authoritative.

## Billing and passwords

- Billing state is server-owned; do not restore `localStorage["agri_tier"]`.
- Frontend client functions live in `src/lib/api.ts`; subscription UI is in
  `src/app/profile/page.tsx` and `src/components/billing/BdAppsCheckout.tsx`.
- Mock billing OTP is `1234`. Real BDApps mode never exposes the OTP.
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

## Verification

- `npm run typecheck` passes.
- `npm run build` passes.
- The production route manifest contains no `/demo`.
- Full backend suite: 135 tests pass.
- Backend test command from inside Compose:
  `docker compose exec -T -e TEST_DATABASE_URL=postgresql+asyncpg://argi:argi_dev_password@db:5432/argi_test backend pytest -q`.
- Docker services are running on frontend `:3000`, backend `:8080`, Postgres `:5433`.

## Remaining BDApps work

Add provisioned `BDAPPS_APPLICATION_ID` and `BDAPPS_PASSWORD` to root `.env`, set
`BILLING_PROVIDER=bdapps`, ensure `BDAPPS_PLAN_ID` matches the portal tariff, rebuild
the backend, then test request/verify/status/cancel with a real eligible number.
