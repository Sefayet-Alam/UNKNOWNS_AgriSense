# API Contract — Argi (frozen)

Base URL: `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`). All JSON unless noted.
Auth = `Authorization: Bearer <access_token>` header on every non-auth-public route.

## Auth

### POST /api/auth/register
Req: `{ "username": str, "email": str, "password1": str, "password2": str }`
- 400 if `password1 != password2`, weak password, or username/email taken.
Res 201: `{ "id": int, "username": str, "email": str }`

### POST /api/auth/login
Req: `{ "username": str, "password": str }`
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
Res 200: `{ "id": int, "username": str, "email": str }` (401 if unauthenticated).

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
Session = {
  id: int, title: str, message_count: int,
  created_at: iso8601, updated_at: iso8601
}
Message = {
  id: int, role: "user" | "assistant", content: str,
  tool_trace: [ { tool: str, args: object, result: str } ],
  model: str, created_at: iso8601
}
```

## Agent (backend internals, must exist for the pipeline)
- LangGraph single-agent ReAct loop, OpenRouter default (`OPENROUTER_MODEL`).
- Tools registered: `get_current_time`, `calculator` (placeholder demo), `save_memory`, `recall_memory` (long-term).
- Long-term memory = pgvector semantic recall (user-scoped `LongTermMemory` rows w/ embedding) + per-session rolling `summary`.
- Streaming via `graph.stream(..., stream_mode=["updates","custom"])`; emit `message`/`message_update`/`progress` frames.
