# API Contract — Argi (frozen)

Base URL: `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`). All JSON unless noted.
Auth = `Authorization: Bearer <access_token>` header on every non-auth-public route.

## Auth

> **Identity = mobile number.** Rural users have phones, not email. The mobile
> number is the unique key + login credential; `username` is a non-unique
> display name. Phone is normalized to canonical 11-digit `01XXXXXXXXX`
> (accepts `+880…`/`880…`/dropped-leading-zero on input). Address is captured
> at registration; each level carries BOTH a name and its CZIS/BBS geocode.

### POST /api/auth/register
Req:
```
{ "username": str,            // display name (not unique)
  "phone": str,               // BD mobile, e.g. "01712345678"
  "password1": str, "password2": str,
  "division_name": str, "division_code": str,     // e.g. "Rajshahi", "50"
  "district_name": str, "district_code": str,     // e.g. "Rajshahi", "5081"
  "upazila_name":  str, "upazila_code":  str,      // e.g. "Tanore", "508194"
  "union_name":    str, "union_code":    str }     // OPTIONAL, e.g. "Badhair", "50819427"
```
- 400 if `password1 != password2`, weak password, invalid phone, phone already
  registered, or a NON-EMPTY `union_code` is not a real union of `upazila_code`
  (validated against the bundled CZIS/BBS gazetteer). Union is optional (some
  upazilas list none); when given, its centroid pins the farm to exact lat/lon
  for weather grounding — otherwise the upazila centroid is used.
Res 201: `UserOut` (see Shapes).

### POST /api/auth/login
Req: `{ "phone": str, "password": str }`
Res 200: `{ "access_token": str, "refresh_token": str, "token_type": "bearer" }`
- 401 on bad creds.

### POST /api/auth/refresh
Req: `{ "refresh_token": str }`
Res 200: `{ "access_token": str, "refresh_token": str, "token_type": "bearer" }`
- **Rotation**: old refresh token's `jti` is blacklisted, a NEW refresh token is issued.
- 401 if the refresh token is expired, malformed, or its `jti` is already blacklisted (reuse detection).

### POST /api/auth/logout
Req: `{ "refresh_token": str }` (access token in header)
Res 204. Blacklists the refresh token `jti` (and the current access `jti`).

### GET /api/auth/me
Res 200: `UserOut` (see Shapes). 401 if unauthenticated.

### POST /api/auth/password/change
Bearer required.
Req: `{ "current_password": str, "new_password": str }`
Res 200: `{ "message": "Password updated successfully." }`
- 400 when the current password is wrong or the new password is unchanged.

### POST /api/auth/password/reset/request
Public. Req: `{ "phone": str }`
Res 200:
```
{ "challenge_id": str, "expires_in_seconds": int,
  "message": str, "demo_otp": "1234" | null }
```
The response never reveals whether the phone is registered. In the current
mock stage the OTP is `1234`; a real SMS provider must remove `demo_otp`.

### POST /api/auth/password/reset/confirm
Public.
Req: `{ "challenge_id": str, "otp": str, "new_password": str }`
Res 200: `{ "message": str }`. Challenges expire and have an attempt limit.

## Billing (all require Bearer)

The backend is authoritative for plans, prices, subscriber phone and status.
The browser must never send an amount or arbitrary phone number.

### GET /api/billing/plans
Res 200:
```
{ "results": [BillingPlan], "provider": "mock" | "bdapps",
  "subscribable_plan_ids": ["plus" | "pro"] }
```
With `BILLING_PROVIDER=bdapps` and zero complete application credential pairs,
the response reports effective provider `mock`, exposes both paid plans, and
uses development OTP `1234`. As soon as any Plus/Pro application ID/password
pair is complete, the response reports `bdapps`, mock activation is disabled
globally, and only tariffs with their own complete credentials are subscribable.
The frontend must not start checkout for an unconfigured live tariff.

The catalog is user-aware. For an active Plus subscription, its Pro entry has
`amount_bdt: 249`; development mode allows direct Plus → Pro OTP activation and
replaces the existing local record. The user does not manually cancel Plus.
In real BDApps mode the discounted Pro entry is unavailable until a dedicated
BDT 249 carrier application is supported; the regular BDT 499 Pro application
must never be used while displaying BDT 249.

### GET /api/billing/subscription
Res 200: `Subscription`. A user without a paid record receives the Free plan.

### POST /api/billing/otp/request
Req: `{ "plan_id": "plus" | "pro" }`
Res 201:
```
{ "challenge_id": str, "expires_in_seconds": int,
  "status_code": str, "status_detail": str, "demo_otp": "1234" | null }
```
Mock mode returns `1234`. BDApps mode calls `/otp/request` and does not expose
an OTP.

### POST /api/billing/otp/verify
Req: `{ "challenge_id": str, "otp": str }`
Res 200: `Subscription`. The server persists the activated subscription.
Successful verification is the terminal activation action; the browser must
update its plan immediately and must not require a second continuation button.

### POST /api/billing/subscription/cancel
Res 200: `{ "subscription": Subscription, "status_code": str, "status_detail": str }`
BDApps mode calls `/subscription/send` with action `"0"`.

### GET /api/billing/caas/quote
Authenticated Tier 2 CaaS sandbox quote. Returns the fixed AgriSense Plus checkout (BDT 199),
the authenticated subscriber ID, and the current virtual operator balance (BDT 500 on first use).
It is a local BDApps-compatible simulator and never calls a carrier endpoint.

### POST /api/billing/caas/debit
Body: `{ "product_id": "plus_subscription", "confirm": true }`.

The server owns the plan price and subscriber identity, persists the receipt, deducts virtual
operator balance, activates Plus, and returns `S1000`, external/internal/reference transaction IDs,
balance before/after, and a redacted BDApps Direct Debit request trace. The response never contains
an API key.

## BDApps callbacks (public; authenticated by provisioned application values)

### POST /api/bdapps/sms/receive
BDApps Message Receiving URL:
`https://agrisense.cortextech.dev/api/bdapps/sms/receive`.
Accepts the official SMS MO payload and returns
`{ "statusCode": "S1000", "statusDetail": "Request was successfully processed" }`.
Message content is intentionally not persisted.

### POST /api/bdapps/subscription/notify
BDApps Subscription Notification URL:
`https://agrisense.cortextech.dev/api/bdapps/subscription/notify`.
Matches `applicationId` and `password` to the provisioned Plus or Pro
application, then synchronizes REGISTERED / UNREGISTERED status using that
application's tariff. Opaque subscriber identities returned for BDApps Pro
applications are stored verbatim and reused for callback correlation, status
checks and cancellation. A delayed cancellation from the other application
cannot cancel the currently active plan.

## Gazetteer (public, no auth — used by the register form)

### GET /api/geo/unions/{upazila_code}
Res 200: `{ "upazila_code": str, "results": [ { "code": str, "name": str, "name_bn": str } ] }`
- 404 for an unknown upazila code. Paurashava wards are labelled
  `"<Paurashava> — Ward No-XX"`.

## Chat (all require Bearer)

### POST /api/chat/stream  → Server-Sent Events
Req: `{ "message": str, "session_id": int | null }`  (omit/null session_id => new session)
Response `Content-Type: text/event-stream`, frames formatted `data: {json}\n\n`.
Frame discriminated by `type`:
- `{ "type": "session", "session_id": int }` — first frame; confirms/creates session id.
- `{ "type": "message", "message": Message }` — a new persisted bubble (user echo, then assistant).
- `{ "type": "message_update", "message": Message }` — patches an existing bubble by id (tool results landing later).
- `{ "type": "progress", "stage": str, "detail": str }` — live status (e.g. tool running, recalling memory).
- `{ "type": "done" }` — turn finished.
- `{ "type": "error", "detail": str, "session_id": int }` — terminal failure.
Set headers `Cache-Control: no-cache`, `X-Accel-Buffering: no`.

### GET /api/chat/sessions
Res 200: `{ "results": [ Session ] }`  (current user only, newest first)

### GET /api/chat/sessions/{id}/messages
Res 200: `{ "session_id": int, "results": [ Message ] }`  (404 if not owned/not found)

### DELETE /api/chat/sessions/{id}
Res 204. (404 if not owned)

## Shapes

```
UserOut = {
  id: int, username: str, phone: str,   // phone canonical "01XXXXXXXXX"
  address: {
    division_name: str, division_code: str,
    district_name: str, district_code: str,
    upazila_name:  str, upazila_code:  str,
    union_name:    str, union_code:    str
  }
}
Session = {
  id: int, title: str, message_count: int,
  created_at: iso8601, updated_at: iso8601
}
Message = {
  id: int, role: "user" | "assistant", content: str,
  tool_trace: [ { tool: str, args: object, result: str } ],
  model: str, created_at: iso8601
}
BillingPlan = {
  id: "free" | "plus" | "pro", name: str, amount_bdt: int,
  billing_cycle: "none" | "monthly", features: [str]
}
Subscription = {
  plan_id: "free" | "plus" | "pro",
  status: "active" | "inactive" | "cancelled",
  provider: "internal" | "mock" | "bdapps", provider_status: str,
  subscriber_id: str, amount_bdt: int, billing_cycle: str,
  started_at: iso8601 | null, cancelled_at: iso8601 | null
}
```

## Agent (backend internals, must exist for the pipeline)
- LangGraph single-agent ReAct loop, OpenRouter default (`OPENROUTER_MODEL`).
- Tools registered: `get_current_time`, `calculator` (placeholder demo), `save_memory`, `recall_memory` (long-term).
- Long-term memory = pgvector semantic recall (user-scoped `LongTermMemory` rows w/ embedding) + per-session rolling `summary`.
- Streaming via `graph.stream(..., stream_mode=["updates","custom"])`; emit `message`/`message_update`/`progress` frames.
