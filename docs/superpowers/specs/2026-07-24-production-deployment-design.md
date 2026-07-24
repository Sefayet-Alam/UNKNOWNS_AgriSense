# Production Deployment Design

## Goal

Deploy AgriSense to the existing VPS on every push to `main` without
colliding with other applications, and serve it at
`agrisense.cortextech.dev` through the host's existing Nginx installation.

## Production Compose

Add `docker-compose.prod.yml` with three services: PostgreSQL, FastAPI, and
Next.js. The Compose project name is `agrisense-prod`; explicit container
names are omitted so Compose namespaces all resources safely.

- PostgreSQL has no published host port and stores data in the dedicated
  `agrisense_prod_pgdata` named volume.
- FastAPI publishes container port 8000 on `127.0.0.1:18743` only.
- Next.js publishes container port 3000 on `127.0.0.1:19327` only.
- The frontend build receives
  `NEXT_PUBLIC_API_URL=https://agrisense.cortextech.dev`.
- Existing `.env` production secrets remain on the VPS and are not committed.

## Nginx

Add `deploy/nginx/agrisense.conf` for `agrisense.cortextech.dev`.

- `/api/` proxies to `127.0.0.1:18743`.
- `/health` proxies to `127.0.0.1:18743`.
- All other paths proxy to `127.0.0.1:19327`.
- API proxying disables buffering and uses a long read timeout so SSE chat
  responses stream immediately.
- The repository config is plain HTTP; Certbot can add TLS and the redirect on
  the VPS.

## Continuous Deployment

Update `.github/workflows/cd.yml` to deploy with:

```bash
docker compose -p agrisense-prod -f docker-compose.prod.yml up -d --build --remove-orphans
```

The workflow checks that `.env` exists, fast-forwards the VPS checkout from
`origin/main`, rebuilds the production services, prints their state, and then
checks FastAPI on port 18743 and Next.js on port 19327. Any failed build,
Compose command, or health check fails the workflow.

## Verification

- Render the production Compose configuration with `docker compose config`.
- Parse and lint-check the workflow YAML where local tooling permits.
- Run `git diff --check`.
- Verify Nginx syntax in a disposable Nginx container when Docker is available.
- Confirm only the deployment spec and requested deployment files are staged
  and committed.
