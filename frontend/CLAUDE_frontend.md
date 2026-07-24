# Frontend handoff — AgriSense

Last updated by: Codex (Jul 24, 2026).

## Current branch and rules

- Branch: `feat/agrisense-workspace`.
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
- Home motion uses GSAP/ScrollTrigger and a dynamically loaded React Three Fiber scene.
  `FieldAtlasScene` must retain its reduced-motion/no-WebGL `FieldAtlasFallback`; visual QA
  confirmed that headless Chrome cannot create a WebGL context.
- Bangladesh photographs are local under `public/images/`; licensing and source URLs are in
  `public/images/IMAGE_CREDITS.md`.
- Auth routes share `components/layout/AuthShell.tsx`. Keep each page's existing handlers intact.
- Profile tabs are controlled by `/profile?tab=info|history|billing`; never restore local-only tab
  state because refresh/direct-link persistence is required.
- History summaries use the existing `/api/chat/sessions` data only. The illustrative fallback is
  shown and labeled only when the endpoint errors or returns no saved sessions.
- Chat input focus uses river blue and jute; preserve that softer treatment. Interactive buttons,
  sidebar rows, suggestions, and key cards use restrained lift/floating hover feedback with the
  global reduced-motion guard.

## Verification

- `npm run typecheck` passes.
- `npm run build` passes.
- Full backend suite: 135 tests pass.
- Backend test command from inside Compose:
  `docker compose exec -T -e TEST_DATABASE_URL=postgresql+asyncpg://argi:argi_dev_password@db:5432/argi_test backend pytest -q`.
- Docker services are running on frontend `:3000`, backend `:8080`, Postgres `:5433`.

## Remaining BDApps work

Add provisioned `BDAPPS_APPLICATION_ID` and `BDAPPS_PASSWORD` to root `.env`, set
`BILLING_PROVIDER=bdapps`, ensure `BDAPPS_PLAN_ID` matches the portal tariff, rebuild
the backend, then test request/verify/status/cancel with a real eligible number.
