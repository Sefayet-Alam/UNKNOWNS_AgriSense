# Free Vercel Deployment

AgriSense deploys as two Vercel projects from this monorepo. Docker/local
behavior is unchanged: disk uploads, file logs, and the lifespan weather loop
remain active when the Vercel variables are absent.

## 1. Backend project

Import this GitHub repository into Vercel with:

- Project name: `agrisense-api` (or any available name)
- Root Directory: `backend`
- Framework: Vercel detects FastAPI from `app/main.py` and `pyproject.toml`

Connect a free Neon database to this project. Use its pooled `DATABASE_URL`;
the application normalizes Neon's standard PostgreSQL URL for asyncpg. Connect
a **private Vercel Blob** store as well.

Configure these server-side environment variables for Production, Preview,
and Development:

```dotenv
DATABASE_URL=<injected by Neon>
BLOB_READ_WRITE_TOKEN=<injected by Vercel Blob>
JWT_SECRET_KEY=<existing strong secret>
OPENROUTER_API_KEY=<existing key>
CRON_SECRET=<new random secret>
BILLING_PROVIDER=mock
SMS_DRY_RUN=true
EMBEDDINGS_PROVIDER=fake
KB_EMBEDDINGS_PROVIDER=openrouter
CORS_ORIGINS=https://<frontend-project>.vercel.app
```

Generate `CRON_SECRET` locally with:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

`GEMINI_API_KEY` is optional and only enables voice transcription. Never import
the repository's whole local `.env`: its Docker `DATABASE_URL` and localhost
frontend URL are intentionally local-only.

### Initialize Neon once

After linking the `backend` directory to the backend Vercel project:

```bash
cd backend
npx vercel env pull .env.vercel.local --environment=production
set -a
source .env.vercel.local
set +a
alembic upgrade head
python -m scripts.seed_rag_data --if-needed
```

The pulled file is covered by the repository's `.env.*` ignore rule. Migrations
are idempotent, and the seed command restores the committed RAG vectors without
embedding API calls.

Deploy and verify:

```bash
npx vercel --prod
curl https://<backend-project>.vercel.app/health
```

Expected response: `{"status":"ok"}`.

The daily cron in `backend/vercel.json` calls `/api/alerts/cron` with Vercel's
Bearer authorization. The continuous lifespan loop is skipped only on Vercel.

## 2. Frontend project

Import the same GitHub repository a second time with:

- Project name: `agrisense-web` (or any available name)
- Root Directory: `frontend`
- Framework: Next.js

Connect the **same private Blob store** to this project, then configure:

```dotenv
NEXT_PUBLIC_API_URL=https://<backend-project>.vercel.app
NEXT_PUBLIC_UPLOAD_STORAGE=vercel-blob
BLOB_READ_WRITE_TOKEN=<injected by the connected Blob store>
```

The browser uploads images/audio directly to Blob using a short-lived token
issued by the frontend route. That avoids Vercel Functions' request-body limit;
the backend authenticates the user, downloads the private object, transcribes
audio when configured, and persists the existing attachment record.

Deploy the frontend, copy its final `*.vercel.app` URL into the backend
`CORS_ORIGINS`, and redeploy the backend.

## 3. Acceptance checks

1. `GET https://<backend>/health` returns 200.
2. Register, sign in, refresh the page, and sign in again.
3. Start a chat and confirm SSE progress/tool trace frames appear.
4. Upload a leaf image and confirm it remains visible after refresh.
5. Record a voice note; without `GEMINI_API_KEY`, the existing honest
   transcription warning is expected.
6. Run Profile billing with mock OTP `1234`; no carrier is charged.
7. In Vercel Cron, confirm the daily `/api/alerts/cron` invocation returns 200.

The free Vercel/Neon/Blob quotas are suitable for a hackathon demo, not a
high-traffic production service. No application feature is intentionally
removed for Vercel; provider outages continue to use the existing explicit
degraded/unavailable responses.
