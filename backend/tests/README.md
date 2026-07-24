# Argi backend test suite

Fast, isolated, deterministic regression tests. **No real LLM / network calls.**

## Layers

| dir | marker | what it covers |
|-----|--------|----------------|
| `tests/unit/` | `unit` | pure logic: password hashing + JWT (`test_security.py`), BD phone normalization (`test_phone.py`), agent static tools (`test_tools.py`). |
| `tests/integration/` | `integration` | app + test DB: auth contract (`test_auth.py`), chat session/message CRUD + ownership (`test_chat_api.py`), user-scoped pgvector memory (`test_memory.py`). |
| `tests/streaming/` | `streaming` | the SSE stream + agentic tool loop (`test_stream_agent.py`). |

## Running

Everything runs against a **separate** `argi_test` database on the SAME compose
Postgres (pgvector available). The app DB `argi` is never touched.

Inside the backend container (has the full dependency stack):

```bash
docker compose exec backend sh -c "
  pip install -r requirements-dev.txt &&
  TEST_DATABASE_URL=postgresql+asyncpg://argi:argi_dev_password@db:5432/argi_test \
  pytest -q
"
```

Locally (point `TEST_DATABASE_URL` at a reachable pgvector Postgres — the
compose one is exposed on `localhost:5433`):

```bash
pip install -r requirements-dev.txt
TEST_DATABASE_URL=postgresql+asyncpg://argi:argi_dev_password@localhost:5433/argi_test \
  pytest -q
```

Or via the Makefile: `make test`, `make test-unit`, `make test-integration`,
`make test-streaming`, `make cov`.

Select by marker: `pytest -m unit`, `pytest -m "integration or streaming"`.

## Isolation model (Django-`TestCase`-like rollback)

- A **session-scoped** fixture creates `argi_test`, the `vector` extension, and
  all tables via `Base.metadata.create_all` on a test engine (fast — no Alembic
  for the test schema), then drops them at session end.
- A **function-scoped** fixture opens ONE connection, begins an **outer
  transaction**, and hands the app a session factory bound to that connection
  with `join_transaction_mode="create_savepoint"`. Every `session.commit()` in
  application code becomes a SAVEPOINT release *inside* the outer transaction;
  at test end the outer transaction is rolled back, so **nothing ever really
  commits** and tests never leak state.
- The `get_db` dependency is overridden to use that factory, and the app's
  `AsyncSessionLocal` (used directly by the streaming router and the memory
  tools) is monkeypatched to the **same** connection-bound factory — so streamed
  writes are visible within the test and are rolled back with everything else.
- The app **lifespan is not run** (plain `ASGITransport`), so no
  `create_all` / Alembic DDL executes against the test DB during tests; schema
  is owned entirely by the fixtures.

## Fake LLM (deterministic agent tests)

Real chat calls go through `app.agent.llm.build_chat_model` (OpenRouter). Tests
monkeypatch it **everywhere it is imported/called** — in `app.agent.graph`,
`app.agent.runner`, and `app.agent.llm` — via the `fake_llm` fixture.

`FakeChatModel` (subclasses `langchain_core` `FakeMessagesListChatModel`)
returns **scripted** responses and implements `bind_tools` as a no-op. Two
scenarios (select via `@pytest.mark.parametrize("fake_llm", [...], indirect=True)`):

- `"plain"` — a single final `AIMessage`.
- `"tool"` — turn 1 returns an `AIMessage` with a `calculator` tool call
  (`{"expression": "2+2"}`); turn 2 returns the final answer. This exercises the
  tool loop, the `tool_trace` on the persisted message, and the
  `message_update` frame that fills the tool result.

Embeddings already default to the offline deterministic `fake` provider
(`EMBEDDINGS_PROVIDER=fake`), so memory tests need no network either.

## SSE, not WebSocket

The realtime transport is **Server-Sent Events** (`text/event-stream`), driven
with `client.stream("POST", "/api/chat/stream", ...)` and parsed by
`tests.fakes.read_sse_events` (accumulates `data:` lines, splits on blank
lines, `json.loads` each frame).

There is **no WebSocket** production code. If a WS endpoint is ever added, test
it with Starlette's `TestClient` websocket helper — a synchronous context
manager, since httpx's `AsyncClient` has no WS support:

```python
from starlette.testclient import TestClient

def test_ws_echo():
    with TestClient(app) as tc:
        with tc.websocket_connect("/ws") as ws:
            ws.send_json({"message": "hi"})
            assert ws.receive_json()["type"] == "session"
```

(Documented for the future only — do **not** add WS prod code for it.)
