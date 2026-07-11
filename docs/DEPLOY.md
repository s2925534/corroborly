# Deploying ResearchBoss to a NAS

This covers deploying the ResearchBoss local API (and, once Phase 10 exists, its web UI) to a Synology NAS as `research.veloso.dev`, using `../synology-site-deployer`'s existing `deploy` command. It does not modify that project — everything NAS-specific lives in this repo (`Dockerfile`, `docker-compose.yml`, `.env.example`), and the deployer is used exactly as it already works for any project with its own Compose file.

Deploy status: documentation only. No deployment has been run from this repo yet — this is what running one would look like, written so it can be done in a single pass rather than improvised at deploy time.

## Prerequisites

- `../synology-site-deployer` set up and configured against your NAS (its own `README.md` covers this: `NAS_HOST`, SSH access, Cloudflare credentials if you want automatic DNS/tunnel routing).
- `CF_ZONE_DOMAIN` in that project's `.env` covering `veloso.dev`, if you want `research.veloso.dev` wired up automatically rather than manually.
- Docker installed locally if you want to build and test the image before shipping it to the NAS (recommended — see below).

## Test Locally First

Build and run the image on your own machine before involving the NAS at all:

```bash
cp .env.example .env
# edit .env: set RESEARCHBOSS_API_PASSWORD to something real
docker compose up --build
```

Then, from another terminal:

```bash
curl http://localhost:8000/health
curl -c cookies.txt -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" -d '{"password": "<your password>"}'
curl -b cookies.txt "http://localhost:8000/api/v1/projects/status?workspace=/data/workspaces/test"
```

The last call will 404 (`workspace_not_found`) until a workspace actually exists under `./data/workspaces/` on your machine — that's expected; it confirms auth and the `RESEARCHBOSS_WORKSPACE_ROOT` containment are both working before you deploy anything.

## Deploy

From this repo, using the deployer's `deploy` command for an existing project with its own Compose file (not `create`, which scaffolds a new app from scratch — ResearchBoss already exists):

```bash
cd ../synology-site-deployer
synology-site deploy research.veloso.dev \
  --compose-file ../ResearchBoss/docker-compose.yml \
  --env-file ../ResearchBoss/.env \
  --source-dir ../ResearchBoss \
  --port 8000 \
  --health-path /health \
  --container-name researchboss-api
```

Notes on these flags, from the deployer's own documented behavior:

- `--source-dir` uploads the whole repo and builds the image on the NAS, rather than requiring a pre-published container registry image. Simplest path for a project that doesn't already publish images.
- `--port 8000` enables the deployer's port allocation, health check, and (if Cloudflare credentials are configured) automatic tunnel routing + DNS for `research.veloso.dev`. Omit this only if fronting the service with an existing reverse proxy already running on the NAS instead.
- `--health-path /health` matches the route in `researchboss/api/routers/health.py`, which deliberately has no workspace or auth dependency — the health check must keep working regardless of login state.
- Before running this for real, fill in `.env` (copied from `.env.example`) with the actual `RESEARCHBOSS_API_PASSWORD` you want — never commit that file.

## Set Up a Workspace Per Research Project

The mounted volume (`./data/workspaces` locally, `/data/workspaces` inside the container, matching `RESEARCHBOSS_WORKSPACE_ROOT`) is empty on first deploy. Each research project gets its own workspace folder underneath it, exactly like local CLI use — the NAS deployment doesn't change how workspaces work, only where they live.

Until Phase 9 gets a scriptable "init over the wire" route (`POST /api/v1/projects/init` already exists and takes the same fields as CLI `init`, so this can be done via `curl`/the API directly today rather than needing NAS shell access):

```bash
curl -b cookies.txt -X POST https://research.veloso.dev/api/v1/projects/init \
  -H "Content-Type: application/json" \
  -d '{
    "workspace": "/data/workspaces/my-thesis",
    "project_name": "My Thesis",
    "project_type": "PhD",
    "topic": "..."
  }'
```

Because `RESEARCHBOSS_WORKSPACE_ROOT=/data/workspaces` is set, subsequent calls can reference this workspace as `workspace=my-thesis` (relative to the root) instead of repeating the full absolute path.

## Update

```bash
cd ../synology-site-deployer
synology-site update research.veloso.dev --health-path /health --container-name researchboss-api
```

Pulls/rebuilds and restarts in place (not zero-downtime blue/green — see the deployer's own README). Session cookies issued before an update will be invalidated (the in-memory session store does not survive a restart, by design — see the Dockerfile's single-process note); anyone using the API will need to log in again after an update.

## Rollback

The deployer's `update` has no built-in rollback. If a deploy goes wrong: fix the issue in this repo, commit, and run `deploy`/`update` again pointed at the fixed code. The workspace data volume (`./data/workspaces` on the NAS) is untouched by any of this — a bad deploy cannot lose research data, only the running service.

## License and Developer Information Consistency

This repo's `README.md` and `LICENSE` state: MIT License, Copyright © 2026 Pedro Veloso, no warranty, contact `pedro@veloso.dev`. Once a web UI exists (Phase 10), it should surface the same notice (footer or About page — see the Phase 10 TODO item for this). Until then, there is nothing on the deployed API itself that states licensing terms to a visitor — `GET /health` and the JSON API responses are not a place to add a license notice; this only becomes a live consistency concern once there is an actual page for a human to load.
