# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HermesHQ is a Docker-first multi-agent control plane. Backend: FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL 16. Frontend: React 19 + TypeScript + Vite + TailwindCSS v4. A WhatsApp bridge (Node.js/Baileys) is bundled into the backend Docker image.

### Architecture (v0.2.2)

**Three-product system:**
- **HermesHQ** (this repo): Cloud backend + web frontend for multi-tenant agent management
- **HeadmasterUI** (desktop): Electron app for local/cloud hybrid agent runtime
- **Headmaster iOS** (mobile): Swift/SwiftUI app for remote chat and agent control

**Key backend features:**
- Organization/school tenancy with role-based access (admin, school_admin, beta_user, user, student, staff)
- Desktop provision modes: `headmaster_local`, `headmaster_remote`, `headmaster_plus_thin`
- Cloud container supervisor for per-user Docker containers
- Cross-device session namespace for shared desktop + iOS experience
- Audit logging for all provision, container, and mode changes
- Server-controlled system prompt and capability gating

## Dev Workflow

Code is edited locally; the full stack runs on a separate always-on machine via Docker Compose. There is no local stack — don't assume `uvicorn` or `npm run dev` can be run locally.

To redeploy after changes, push to the remote or sync files manually, then `docker compose up --build -d` on the host machine.

Direct commits to `main` are fine — no PR workflow.

## Backend

### Setup

```bash
cd backend
uv venv && uv pip install -r requirements.txt
```

### Run locally (if available)

```bash
cd backend
uvicorn hermeshq.main:app --reload  # port 8000
```

### Tests

Some tests are always excluded — known failures or env-specific:

```bash
cd backend
python -m pytest tests/ -v --tb=short \
  --ignore=tests/test_gateway_supervisor_crash_loop.py \
  --ignore=tests/test_regressions.py \
  --ignore=tests/test_response_attachments.py
```

`asyncio_mode = auto` is set in `pytest.ini` — no `@pytest.mark.asyncio` needed.

### Linting & Formatting

Via pre-commit (runs on `git commit`):

```bash
ruff format backend/
ruff check backend/ --fix
mypy backend/hermeshq/ --config-file=backend/pyproject.toml
```

Ruff config: line-length 120 (not default 88), double quotes, Python 3.11 target. `alembic/versions/` is excluded from ruff.

### Database Migrations (Alembic)

1. Edit models in `backend/hermeshq/models/`
2. Autogenerate: `alembic -c backend/alembic.ini revision --autogenerate -m "short description"`
3. **Manually review** the generated file in `backend/hermeshq/alembic/versions/` — autogenerate misses some cases (constraints, index changes)
4. Apply: `alembic -c backend/alembic.ini upgrade head`

## Frontend

### Dev

```bash
cd frontend
npm install
npm run dev        # Vite dev server, port 5173
npm run build      # tsc --noEmit + vite build
```

### Linting

```bash
cd frontend
npx eslint "src/**/*.{ts,tsx}"
```

ESLint flat config (`eslint.config.js`), TypeScript strict mode, no Prettier.

## Full Stack (Docker)

```bash
docker compose up --build -d   # Build and start all services
docker compose logs -f backend # Stream backend logs
```

Backend port 8000 is not exposed to the host — it runs behind the nginx reverse-proxy on port 3420.

## Key Environment Variables

Required in `.env` (see `.env.example`):

| Variable | Default | Notes |
|---|---|---|
| `JWT_SECRET` | `change-me` | Must be changed in production |
| `DATABASE_URL` | set by Docker | Needs manual set for local dev |
| `VITE_API_BASE_URL` | *(empty)* | Empty = `/api` proxy via nginx. Setting `localhost` or `127.0.0.1` is blocked unless `ALLOW_LOCAL_API_BASE=true` |
| `CONCURRENCY_SEMAPHORE` | `8` | Max concurrent task runners; size as `available_RAM_MB / 60` |
| `AUTH_MODE` | `local` | `oidc` for enterprise SSO |

## Gotchas

- **Frontend API URL**: `VITE_API_BASE_URL` must be empty (uses nginx proxy) or a real hostname. `localhost`/`127.0.0.1` are blocked at build time unless `ALLOW_LOCAL_API_BASE=true` is set.
- **Backend not on host port**: Port 8000 uses `expose`, not `ports` — only reachable via nginx.
- **WhatsApp bridge**: Node.js 22 is installed inside the backend Docker image to run the Baileys bridge. Not a separate service.
- **Pytest exclusions**: The three ignored test files contain known failures or require special infra — always exclude them in CI and local runs.
- **Admin password**: Auto-generated and logged to console if `ADMIN_PASSWORD` is not set in `.env`.
- **Telegram conflicts**: Running two HermesHQ instances with the same bot token causes polling conflicts.
