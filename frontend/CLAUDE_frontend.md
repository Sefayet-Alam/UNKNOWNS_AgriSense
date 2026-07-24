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

## Verification

- `npm run typecheck` passes.
- `npm run build` passes.
- Full backend suite: 135 tests pass.
- Docker services are running on frontend `:3000`, backend `:8080`, Postgres `:5433`.

## Remaining BDApps work

Add provisioned `BDAPPS_APPLICATION_ID` and `BDAPPS_PASSWORD` to root `.env`, set
`BILLING_PROVIDER=bdapps`, ensure `BDAPPS_PLAN_ID` matches the portal tariff, rebuild
the backend, then test request/verify/status/cancel with a real eligible number.
