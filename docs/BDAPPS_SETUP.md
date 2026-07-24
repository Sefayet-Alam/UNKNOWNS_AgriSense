# BDApps CaaS Integration — Go-Live (Plus real, Pro dummy)

The backend implementation is **complete** (`adapters/billing.py`, `routers/billing.py`,
`routers/bdapps.py`, `Subscription` model). Going live is a **configuration** step:
supply the approved application's credentials so the provider stops falling back to mock.

## 1. The only file to change: root `.env`

`docker compose` reads the repo-root `.env` (NOT `backend/.env`). Set:

```dotenv
BILLING_PROVIDER=bdapps

# Approved Plus application (APP_139278) — the API password is the app's
# server key from the BDApps dashboard, NOT your BDApps account password.
BDAPPS_PLUS_APPLICATION_ID=APP_139278
BDAPPS_PLUS_PASSWORD=<paste the Plus app password/API key>
BDAPPS_PLUS_APPLICATION_HASH=<paste the Plus app hash>   # optional; sent on OTP request if set

# Pro stays a DUMMY plan — leave all three empty so it is shown but not subscribable.
BDAPPS_PRO_APPLICATION_ID=
BDAPPS_PRO_PASSWORD=
BDAPPS_PRO_APPLICATION_HASH=

BDAPPS_BASE_URL=https://developer.bdapps.com
```

> Legacy single-app keys (`BDAPPS_APPLICATION_ID/PASSWORD/APPLICATION_HASH` +
> `BDAPPS_PLAN_ID=plus`) still work as a fallback, but the per-plan `BDAPPS_PLUS_*`
> keys above are the clean, self-documenting form. Use one or the other, not both.

### Why it currently behaves like mock
`BdAppsCredentials.is_complete = bool(application_id and password)`. Today
`BILLING_PROVIDER=bdapps` but the Plus **password is blank**, so zero apps are
"complete" and `effective_billing_provider_name()` silently uses the dev/mock
provider (OTP `1234`). **Filling the Plus password is what flips Plus to real.**
As soon as one complete app exists, mock activation is disabled globally.

## 2. Plus real vs Pro dummy — how the gating works (no code change)
- `configured_bdapps_plan_ids()` returns only plans whose credentials are complete →
  with just Plus filled, **only Plus** is in `subscribable_plan_ids`.
- `GET /api/billing/plans` still lists Pro (৳499) for display, but it is **not**
  in `subscribable_plan_ids`, so the UI shows it disabled → the "dummy" behavior.

## 3. BDApps dashboard config for APP_139278 (needs a public URL)
Server→BDApps OTP calls are outbound and need no hosting. The async callbacks do —
set these in the app's dashboard once you have a public tunnel/host:

| Dashboard field | URL |
|---|---|
| Subscription Notification URL | `https://<public-host>/api/bdapps/subscription/notify` |
| SMS Message Receiving URL | `https://<public-host>/api/bdapps/sms/receive` |

Both are HMAC/credential-verified against the configured app. For a local demo the
outbound OTP subscribe/verify flow works without these; the notify callback only
reconciles async status.

## 4. Demo flow (real BDApps sandbox, Plus)
1. `GET /api/billing/plans` → Plus subscribable, Pro shown-but-disabled.
2. `POST /api/billing/otp/request {plan_id:"plus"}` → server calls BDApps `/otp/request` → real OTP SMS.
3. `POST /api/billing/otp/verify {otp}` → BDApps `/otp/verify` → subscription `REGISTERED` → `Subscription` row `active`, provider `bdapps`.
4. `GET /api/billing/subscription` → live status (re-polls BDApps `/subscription/getStatus`).
5. `POST /api/billing/subscription/cancel` → BDApps `/subscription/send {action:"0"}` → `cancelled`.

## 5. Real vs mock (for the submission README)
- **Real/live:** Plus plan — genuine BDApps OTP + Subscription API calls (sandbox).
- **Dummy:** Pro plan — displayed, not subscribable (no approved application).
- **Dev default:** with no credentials, `mock` provider uses OTP `1234` (offline, deterministic).

## 6. After editing `.env`
```bash
docker compose up -d backend      # picks up new env (no rebuild needed for env-only change)
docker compose logs -f backend
```
No migration needed — the `subscriptions` table already exists.
