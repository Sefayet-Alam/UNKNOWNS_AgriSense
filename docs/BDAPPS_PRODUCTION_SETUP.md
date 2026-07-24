# BDApps production setup

AgriSense uses the BDApps OTP and Subscription APIs. OTP verification is the
terminal activation action; there is no second payment/continue step. Plus and
Pro require separate BDApps applications because each application has one
provisioned recurring tariff.

## BDApps portal values

| Portal field | Value |
|---|---|
| Enable Mobile Originated SMS | Yes |
| Message Receiving URL | `https://agrisense.cortextech.dev/api/bdapps/sms/receive` |
| Enable Mobile Terminated SMS | Yes |
| Default Sender Address | The sender/short code assigned by BDApps |
| SMS Keyword | Plus: `agrisense`; Pro: `agrisense_pro` |
| USSD | Disabled; AgriSense has no USSD listener |
| CaaS | Disabled; recurring charging is owned by Subscription |
| Subscription Required | Yes |
| Subscription Response Message | `AgriSense Subscription is activated!` |
| Un-subscription Response Message | `AgriSense Subscription deactivated!` |
| Subscriber Confirmation Required | Yes |
| Send Subscription Notification | Yes |
| Subscription Notification URL | `https://agrisense.cortextech.dev/api/bdapps/subscription/notify` |
| Robi charging frequency | Monthly for both applications |
| Robi charging amount | Plus: BDT 199; Pro: BDT 499 |

## Server-only environment values

Put these in the production `.env` on the host. Never put them in a
`NEXT_PUBLIC_*` variable, browser code, Git, screenshots, or chat.

```dotenv
BILLING_PROVIDER=bdapps
BDAPPS_BASE_URL=https://developer.bdapps.com
BDAPPS_PLUS_APPLICATION_ID=APP_139278
BDAPPS_PLUS_PASSWORD=REPLACE_WITH_PLUS_APPLICATION_API_PASSWORD
BDAPPS_PLUS_APPLICATION_HASH=
BDAPPS_PRO_APPLICATION_ID=APP_REPLACE_WITH_PRO_ID
BDAPPS_PRO_PASSWORD=REPLACE_WITH_PRO_APPLICATION_API_PASSWORD
BDAPPS_PRO_APPLICATION_HASH=
BDAPPS_TIMEOUT_SECONDS=15
NEXT_PUBLIC_API_URL=https://agrisense.cortextech.dev
```

- `BDAPPS_PLUS_APPLICATION_ID`: the BDT 199 application's provisioned ID
  (`APP_139278`).
- `BDAPPS_PRO_APPLICATION_ID`: the BDT 499 application's provisioned `APP_…`
  ID.
- `BDAPPS_*_PASSWORD`: application password/API key from each app's
  credentials view. These are not the BDApps account password.
- `BDAPPS_*_APPLICATION_HASH`: optional for the web flow. Leave empty unless
  BDApps explicitly provides a hash for that application.

The legacy `BDAPPS_APPLICATION_ID`, `BDAPPS_PASSWORD`,
`BDAPPS_APPLICATION_HASH`, and `BDAPPS_PLAN_ID` values are supported only as a
single-app migration fallback. New production configuration should use the
per-plan variables above.

### Automatic development fallback

When `BILLING_PROVIDER=bdapps` but **zero** complete application ID/password
pairs exist, AgriSense automatically enables development billing for both paid
plans with OTP `1234` and no mobile charge. The plans API reports provider
`mock`, so the frontend clearly labels the flow.

As soon as **any** complete BDApps credential pair exists, mock activation is
disabled globally. The plans API reports provider `bdapps`, and only tariffs
with their own complete credentials can be selected. This prevents a
partially provisioned production deployment from silently creating mock
subscriptions.

Development OTP `1234` can be requested repeatedly without a cooldown. The
configured `OTP_REQUEST_COOLDOWN_SECONDS` limit applies only to real BDApps
carrier OTP requests.

### Plus-to-Pro loyalty upgrade

During development, an active Plus user sees Pro at BDT 249/month and can
upgrade directly with OTP `1234`; the backend replaces Plus with Pro without a
manual cancellation step.

BDApps subscription tariffs are provisioned per application. The existing BDT
499 Pro application cannot truthfully process a checkout displayed as BDT 249.
Before enabling this upgrade on the carrier, provision a separate BDT 249 Pro
upgrade application and extend the server with its credentials/routing. Until
then, real BDApps mode keeps the discounted upgrade unavailable rather than
risking an incorrect or duplicate charge.

## Deploy

From the production checkout after the feature branch is merged:

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=100 backend
```

The backend entrypoint applies Alembic migrations automatically. Migration
`0005_bdapps_subscriber_identity` expands the provider identity column for
masked BDApps Pro subscriber tokens.

## End-to-end acceptance test

1. Confirm `https://agrisense.cortextech.dev/health` returns HTTP 200.
2. Register or sign in with an eligible Robi number.
3. Open **Profile → Plan & billing** and choose **Plus**.
4. Test Plus: request the OTP, enter the real code, and confirm immediate
   activation at BDT 199.
5. Cancel Plus and confirm both AgriSense and the Plus BDApps app show
   UNREGISTERED.
6. Test Pro the same way and confirm BDT 499 and the Pro application are used.
7. Cancel Pro and confirm both systems show UNREGISTERED.

Real BDApps subscriptions require cancellation before switching plans so a
subscriber cannot accidentally remain active—and charged—in both carrier
applications. The direct Plus-to-Pro replacement described above is limited
to the explicitly labelled local mock flow until a dedicated carrier upgrade
tariff is implemented.

Keep `BILLING_PROVIDER=mock` locally when a real Robi-number test is not being
performed; mock mode uses OTP `1234` and never charges a mobile account.

## Local mock rehearsal (not the BDApps sandbox)

Until BDApps approves the applications and exposes their API passwords, test the
complete AgriSense checkout locally with `BILLING_PROVIDER=mock`. Rebuild the
services, register or sign in with any valid local phone, select Plus or Pro,
request the OTP, enter `1234`, verify that the plan becomes active immediately,
refresh Profile → Billing, and then cancel it. This exercises AgriSense's real
frontend, API routes, database persistence, and cancellation state without
calling BDApps or charging a number.

This mock provider verifies AgriSense's own UI/API/database flow; it is not the
BDApps simulator and must not be presented as BDApps sandbox validation.

## Official BDApps local simulator

The currently published English BDApps Pro SDK Simulator Guide is version 1.1.1
(13 May 2015). It starts a local Java simulator UI at
`http://localhost:10001/mchoice-tap-sdk` and documents gateway endpoints on port
7000 for **SMS, USSD, and CaaS only**. It does not document `/otp/request`,
`/otp/verify`, or any `/subscription/*` endpoint.

Therefore, do not point this subscription adapter at `http://localhost:7000`;
the published simulator cannot validate AgriSense's OTP/subscription flow. Ask
`support@bdapps.com` for a current subscription-capable sandbox or test
credentials. Until they provide one—or approve the applications and issue API
passwords—use `mock` only as an explicitly labeled AgriSense-local rehearsal.

An application account password is not an application API password. Without
approved app credentials—or subscription-capable test credentials—the real
`https://developer.bdapps.com` OTP flow cannot be authenticated.
