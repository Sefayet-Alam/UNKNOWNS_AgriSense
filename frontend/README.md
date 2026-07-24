# Argi — Frontend

Agentic agri-tech chat client. Next.js 14 (App Router) + TypeScript + Tailwind +
@tanstack/react-query + streaming SSE chat.

## Run

```bash
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev   # http://localhost:3000
```

`NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000` when unset.

## Scripts

- `npm run dev` — dev server
- `npm run build` — production build (standalone output)
- `npm run start` — serve the build on :3000
- `npm run typecheck` — `tsc --noEmit`

## Routes

- `/login`, `/register` — auth (centered card, leaf-mark logo).
- `/chat` — protected: session sidebar + streaming chat + composer.
- `/` — redirects to `/chat` if a token exists, else `/login`.

## Auth

Tokens live in `localStorage` (`argi_access` / `argi_refresh`). The API client
attaches `Authorization: Bearer <access>`; on `401` it refreshes once via
`POST /api/auth/refresh` (rotation: **both** tokens are replaced), then retries
the original request. A failed refresh clears tokens and redirects to `/login`.
Refreshes are single-flight so concurrent 401s share one round-trip.

## Chat streaming

`POST /api/chat/stream` is consumed with raw `fetch` + `ReadableStream` (so we
can send a Bearer header + POST body). Frames `data: {json}\n\n` are parsed and
dispatched by `type`: `session`, `message`, `message_update`, `progress`,
`done`, `error`. A `401` on the stream triggers one refresh + reconnect.

## Docker

```bash
docker build --build-arg NEXT_PUBLIC_API_URL=http://backend:8000 -t argi-frontend .
docker run -p 3000:3000 argi-frontend
```
