# Changelog

All notable changes to HermesHQ are documented in this file.

## [2026.5.25.3] — 2026-05-25

### Feature: Password Recovery via Email (Resend)

Full password reset flow using the Resend email API, configurable from the Settings UI.

#### Backend
- **`models/password_reset.py`** (NEW): `PasswordResetToken` model with hashed tokens, expiration, single-use, rate limiting (3/hour).
- **`services/email_service.py`** (NEW): `EmailService` class with Resend REST API integration, dark-themed HTML email template, async config reload from database.
- **`routers/auth.py`**: 3 new endpoints:
  - `POST /auth/forgot-password` — generates reset token, sends email (anti-enumeration: always returns 200)
  - `POST /auth/reset-password` — validates token, updates password, invalidates other tokens
  - `GET /auth/email-config` — returns email config status for Settings UI
- **`schemas/auth.py`**: `ForgotPasswordRequest`, `ResetPasswordRequest`, `PasswordResetResponse`, `EmailConfigStatus`
- **`config.py`**: `resend_api_key`, `from_email`, `from_name`, `public_base_url`, `password_reset_token_minutes`
- **`models/app_settings.py`**: 4 new DB-backed fields for email config (editable from Settings UI)
- **Alembic migration**: `9a4ccb262336_add_email_and_password_reset`

#### Frontend
- **`ForgotPasswordPage.tsx`** (NEW): Email input → confirmation message, branded dark layout matching LoginPage
- **`ResetPasswordPage.tsx`** (NEW): Token validation, password + confirm fields, success → redirect to login
- **`EmailTab.tsx`** (NEW): Settings tab for Resend API key, From email/name, Public base URL, test email button
- **`LoginPage.tsx`**: "Forgot password?" link
- **`App.tsx`**: Routes for `/forgot-password` and `/reset-password`
- **`SettingsPage.tsx`**: New "Email" tab
- **i18n (EN/ES)**: 45+ new translation keys for password recovery and email config

#### Security
- Tokens hashed (SHA-256) in database — plaintext never stored
- 15-minute expiration (configurable)
- Single-use tokens with immediate invalidation on password change
- Rate limited to 3 requests per email per hour
- Anti-enumeration: identical response regardless of email existence
- Only works for `auth_source == "local"` users (OIDC users excluded)
- `PublicSettingsRead` does NOT expose email config or API keys

#### Tested
- ✅ Forgot password flow (registered + unregistered emails)
- ✅ Password reset with valid token
- ✅ Re-use of token blocked
- ✅ Old password rejected after reset
- ✅ Rate limiting (3/hour)
- ✅ Email config reads from DB dynamically
- ✅ Frontend pages load correctly
- ✅ TypeScript compiles with zero errors


## [2026.5.26.1] — 2026-05-26

### Fix: install.sh crashes on `read` with `set -u` (strict mode)

#### Problem
The install script (`install.sh`) and resize script (`hermeshq-resize.sh`) both use
`set -Eeuo pipefail` (strict mode). When `read -r` is called inside a sub-shell
(e.g. `PLANNED_AGENTS="$(prompt_agent_count)"`), the variable starts as unset.
Under `set -u`, bash treats this as a fatal error and aborts before the user can type.

This caused the installer to crash immediately when asking "How many agents do you plan to deploy?"

#### Fix
- **`install.sh`**: Initialize all 3 `read` variables with empty string defaults:
  `local count=""`, `local choice=""` (x2)
- **`scripts/hermeshq-resize.sh`**: Same fix: `local answer=""`

### Feature: Password recovery via email (Resend)

New password reset flow for local-auth users via transactional email using the Resend API.

#### Backend
- **`models/password_reset.py`** (NEW): `PasswordResetToken` model with token_hash, expires_at, used_at, ip_address.
- **`services/email_service.py`** (NEW): Email service via Resend REST API with dark-themed HTML templates.
- **`routers/auth.py`**: 3 new endpoints:
  - `POST /forgot-password` — generates reset token, sends email (rate-limited 3/hr, anti-enumeration)
  - `POST /reset-password` — validates token, updates password, invalidates other tokens
  - `GET /email-config` — returns email config status (admin only)
- **`config.py`**: 5 new fields: `resend_api_key`, `from_email`, `from_name`, `public_base_url`, `password_reset_token_minutes`
- **`models/app_settings.py`**: 4 new DB-backed fields for email config (configurable from Settings UI)
- **`schemas/auth.py`**: `ForgotPasswordRequest`, `ResetPasswordRequest`, `PasswordResetResponse`, `EmailConfigStatus`
- **Alembic migration** `9a4ccb262336`: Creates `password_reset_tokens` table + email columns on `app_settings`

#### Frontend
- **`ForgotPasswordPage.tsx`** (NEW): Email input → success confirmation page
- **`ResetPasswordPage.tsx`** (NEW): Token validation, new password form, success redirect to login
- **`EmailTab.tsx`** (NEW): Settings tab for Resend API key, from email, public URL, test email button
- **`LoginPage.tsx`**: "Forgot password?" link
- **`App.tsx`**: Routes for `/forgot-password` and `/reset-password` (outside auth shell)
- **`SettingsPage.tsx`**: New "Email" tab
- **i18n (EN/ES)**: 40+ new translation keys

#### Security
- Token stored as SHA-256 hash in DB (never plaintext)
- 15-minute expiration (configurable)
- Single-use tokens (marked `used_at` on consume)
- Anti-enumeration: always returns 200 with identical message
- Rate limit: 3 requests per email per hour
- Only `auth_source=local` users can reset
- Email config fields excluded from `PublicSettingsRead`


## [2026.5.25.2] — 2026-05-25

### Fix: Kapso webhook batch payload support

#### Problem
Kapso dashboard can send webhook events as a JSON array (batch/buffering mode,
e.g. 5-second window or up to 50 messages per batch). The webhook handler assumed
`payload` was always a `dict` and called `.get()` on it, causing:

```
AttributeError: 'list' object has no attribute 'get'
```

This resulted in HTTP 500 responses and Kapso marking deliveries as "Fallido".

#### Fix
- **`routers/webhooks.py`**: The `kapso_whatsapp_webhook` endpoint now normalizes
  the parsed payload to a `list[dict]` regardless of whether Kapso sends a single
  event (`{...}`) or a batch (`[{...}, {...}]`). Each event is processed individually
  through `handle_kapso_webhook`.

#### Tested
- ✅ Single event (dict payload) → 200 OK
- ✅ Batch events (list of 2 dicts) → 200 OK
- ✅ Nested data with header event type → 200 OK
- ✅ Zero errors / zero tracebacks in backend logs


## [2026.5.25.1] — 2026-05-25

### Fix: Provider env var routing — OPENAI_BASE_URL leak to non-OpenAI providers

#### Problem
When an agent used a non-OpenAI provider (kimi-coding, zai, openrouter, anthropic, bedrock),
`OPENAI_BASE_URL` was always set alongside the provider's dedicated base URL env var.
This caused auxiliary clients in Hermes Agent to route API calls to the wrong endpoint
when fallback triggered (e.g. kimi-coding auxiliary client sending requests to z.ai endpoint).

Additionally, `_merge_env_file` had hardcoded `managed_keys` that only covered zai, openrouter,
anthropic and openai — missing kimi-coding, gemini, bedrock, and openai-codex. This caused
`.env` files to accumulate duplicate entries on every sync (e.g. 8x KIMI_API_KEY lines).

#### Fix
- **`hermes_installation.py`** — `build_process_env()` and `_build_managed_env_map()`:
  `OPENAI_BASE_URL` is now only set for providers that actually use it
  (`openai`, `openai-codex`, `gemini`). All other providers use their dedicated base URL env var.
- **`hermes_installation.py`** — `_merge_env_file()`: `managed_keys` is now built dynamically
  from all known providers (8 providers) instead of hardcoded 4. This prevents duplicate entries.
- All 58 agent `.env` files were resynced to remove duplicates and leaked `OPENAI_BASE_URL` entries.

#### Verified
- ✅ kimi-coding agent `.env`: only `KIMI_*` vars, no `OPENAI_BASE_URL`
- ✅ zai agent `.env`: only `GLM_*` vars, no `OPENAI_BASE_URL`
- ✅ All 58 `.env` files clean: zero duplicates, zero leaks
- ✅ User-custom entries (non-managed keys) preserved correctly


## [2026.5.22.3] — 2026-05-25

### Feature: Kapso WhatsApp Channel Integration

New WhatsApp channel powered by the official Meta Cloud API via Kapso platform.

#### Backend
- **`services/kapso_whatsapp_gateway.py`** (NEW — 574 lines): Full gateway adapter running as asyncio task (no subprocess). Handles incoming webhooks, creates Tasks for agents, sends replies via Kapso REST API. Includes HMAC-SHA256 webhook signature verification, allowed-user access control, and delivery status tracking.
- **`services/enterprise_gateway_manager.py`**: Added `kapso_gateways` registry alongside `google_chat_gateways`. Bootstrap, lifecycle, and status for `kapso_whatsapp` platform.
- **`services/gateway_supervisor.py`**: Delegates `kapso_whatsapp` to EnterpriseGatewayManager (same pattern as Google Chat — no subprocess).
- **`routers/webhooks.py`**: New `POST /webhooks/kapso-whatsapp` endpoint with signature verification and event routing.
- **`routers/messaging_channels.py`**: `kapso_whatsapp` added to supported platforms with validation (secret_ref required, kapso_phone_number_id required in metadata_json).
- **`main.py`**: Exposes `kapso_gateways` on `app.state` for webhook routing.

#### Frontend
- **`AgentMessagingPanel.tsx`**: New "Kapso WA" tab with full CRUD hooks and save logic.
- **`ChannelForm.tsx`**: New Kapso metadata fields (Phone Number ID, Webhook Secret) and platform-specific labels/placeholders.
- **i18n (EN/ES)**: 16 new translation keys for Kapso WhatsApp channel.

#### Manual
- **`ManualPage.tsx`**: New "Kapso WhatsApp" section in both EN and ES with step-by-step setup guide (6 steps), prerequisites, testing instructions, and migration notes.

#### Key Design Decisions
- Coexists with existing Baileys WhatsApp (`"whatsapp"` legacy channel). Agents can use either or both.
- No subprocess overhead — runs as lightweight asyncio coroutine within the backend process.
- Credentials stored encrypted via SecretVault (same pattern as Google Chat).
- `metadata_json` holds `kapso_phone_number_id` and `kapso_webhook_secret` per channel.

#### Tested
- 14/14 functional tests passed (CRUD, validation, webhook, API connectivity, lifecycle).
- TypeScript compiles with zero errors.
- Backend starts cleanly with zero errors in logs.


## [2026.5.22.2] — 2026-05-22

### Stability & Architecture (Priority 2)

#### P2.1 — Full migration to Alembic, removed legacy inline schema updates
- **`database.py`**: Reduced from 381 → 57 lines (−324). Removed the entire `_run_schema_updates()` function containing 300+ lines of hardcoded `ALTER TABLE` statements.
- **`alembic/versions/d39fa7cf25af_initial_schema_from_models.py`**: New initial migration (stamp) of the current schema. All future schema changes go through Alembic.
- **`backend/Dockerfile`**: Added `COPY backend/alembic.ini` so Alembic is available inside the container.
- `init_database()` now runs `alembic upgrade head` as a subprocess, avoiding async event-loop conflicts.

#### P2.2 — Fixed identical branches in `_restore_secrets`
- **`services/instance_backup.py`**: `merge` mode now only fills `None` fields (preserving existing values), while `replace` mode overwrites everything. Previously both branches did the same thing (unconditional setattr).

#### P2.3 — JWT expiration validation in frontend session store
- **`frontend/src/stores/sessionStore.ts`**: Added `decodeJwtPayload()` that decodes the JWT and checks the `exp` claim. On store initialization, expired tokens are automatically discarded and removed from localStorage.

#### P2.4 — `resolveWsRoot()` now respects `VITE_API_BASE_URL`
- **`frontend/src/lib/apiBase.ts`**: When `VITE_API_BASE_URL` is an absolute URL, the WebSocket root is derived from it (e.g. `https://api.example.com/api` → `wss://api.example.com`). Previously always used `window.location.origin`, ignoring the environment variable.

#### P2.5 — Dead code removal
- **`routers/mcp_server.py`**: Removed write-only `_log_levels` dict and unused `is_error` variable.
- **`services/gateway_supervisor.py`**: Removed unreachable `return []` in exception handler.
- **`services/agent_supervisor.py`**: Removed redundant local `import Task` inside `_recover_zombie_tasks`.


## [2026.5.22.1] — 2026-05-22

### Security

#### S1 — Cookie `secure` flag configurable via environment variable
- **`config.py`**: Added `cookie_secure: bool = False` to the `Settings` class. Set `COOKIE_SECURE=true` in production behind TLS to prevent session cookies from being sent over plain HTTP.
- **`routers/auth.py`**: `_set_auth_cookie()` and `_clear_auth_cookie()` now read `get_settings().cookie_secure` instead of hardcoded `False`.

#### S2 — Restrictive file permissions on files containing secrets
- **`services/hermes_installation.py`**: Added `_protect_file(path)` helper that sets `chmod 0o600` (owner read/write only) on sensitive files.
- Applied after every write of `.env` (1 location) and `auth.json` (2 locations) inside agent workspaces, preventing other OS users from reading credentials.

#### S3 — Public settings endpoint no longer exposes sensitive configuration
- **`schemas/settings.py`**: New `PublicSettingsRead` Pydantic model with only 8 safe fields: `app_name`, `app_short_name`, `theme_mode`, `default_locale`, `logo_url`, `favicon_url`, `has_logo`, `has_favicon`.
- **`routers/settings.py`**: Added `_settings_to_public_read()` helper. `GET /api/settings/public` now returns `PublicSettingsRead` instead of the full `AppSettingsRead` which previously exposed `default_api_key_ref`, `default_base_url`, `default_provider`, `default_model`, internal `id`, and `app_version`.
- Frontend is fully backward-compatible — the public response is a subset of the previous one.

#### S4 — Zip bomb protection in backup restore
- **`services/instance_backup.py`**: Added two constants:
  - `MAX_ARCHIVE_TOTAL_UNCOMPRESSED_SIZE = 2 GB` — maximum total uncompressed size of a backup archive.
  - `MAX_ARCHIVE_SINGLE_FILE_SIZE = 500 MB` — maximum size of any single file within an archive.
- `_load_restore_payload()` now validates per-entry and total sizes **before** calling `extractall()`. Invalid archives raise `InstanceBackupError` with a descriptive message.

#### S5 — Sanitized environment variables in agent subprocesses
- **`services/hermes_installation.py`**: Added `_build_safe_env()` helper that filters out ~20 sensitive environment variable prefixes (`AWS_`, `HERMESHQ_`, `DATABASE_URL`, `REDIS_URL`, `DOCKER_`, `GITHUB_TOKEN`, `GITLAB_TOKEN`, `KUBECONFIG`, `STRIPE_`, `TWILIO_`, `SENDGRID_`, `VAULT_TOKEN`, `VAULT_ADDR`, etc.) from `os.environ` before passing them to agent subprocesses.
- `build_process_env()` now uses `_build_safe_env()` instead of the raw `os.environ`, preventing host secrets from leaking into agent runtimes.

### Files Changed

| File | Action |
|------|--------|
| `VERSION` | Updated to 2026.5.22.1 |
| `backend/hermeshq/config.py` | Added `cookie_secure` setting |
| `backend/hermeshq/routers/auth.py` | Dynamic `secure` flag on cookies |
| `backend/hermeshq/routers/settings.py` | New public-only endpoint logic |
| `backend/hermeshq/schemas/settings.py` | New `PublicSettingsRead` schema |
| `backend/hermeshq/services/hermes_installation.py` | `_protect_file`, `_build_safe_env`, filtered env |
| `backend/hermeshq/services/instance_backup.py` | Zip bomb size validation |

---

## [2026.5.21.1] — 2026-05-21

### Added — Configurable Concurrency & Resource-Aware Sizing

#### Phase 1: Configurable Semaphore

- **`concurrency_semaphore` setting** — Replaced hardcoded `asyncio.Semaphore(8)` in `AgentSupervisor` with a configurable value from environment variable `CONCURRENCY_SEMAPHORE` (default: 8).
- **Runtime semaphore update** — `PUT /api/settings/resources/semaphore` now updates the semaphore value **in real-time without restart**. Changes are persisted to `.env` for next boot.
- **`.env.example`** — Updated with `CONCURRENCY_SEMAPHORE` and all other configurable environment variables.
- **`docker-compose.yml`** — Added `CONCURRENCY_SEMAPHORE` to backend service environment.

#### Phase 2: Resource Monitoring API & Settings UI

- **Resource Monitor service** (`backend/hermeshq/services/resource_monitor.py`) — New service that detects:
  - Container memory/CPU limits via cgroups v1 and v2 (`/sys/fs/cgroup/`)
  - Container memory usage, CPU %, threads, processes
  - System RAM, CPU cores, available disk via `psutil`
  - Semaphore configuration and utilization percentage
  - Resource sizing calculations (RAM/CPU/disk per agent)
- **Settings API endpoints**:
  - `GET /api/settings/resources` — Full resource status (container limits, usage, system resources, semaphore info)
  - `PUT /api/settings/resources/semaphore` — Update concurrency semaphore (1–200 range, immediate effect)
  - `POST /api/settings/resources/generate-override` — Generate `docker-compose.override.yml` with resource limits and PostgreSQL tuning
- **New Pydantic schemas**: `ResourceStatusResponse`, `SemaphoreUpdateRequest`, `SemaphoreUpdateResponse`, `GenerateOverrideRequest`, `GenerateOverrideResponse`
- **Resources Settings Tab** (`frontend/src/components/settings/ResourcesTab.tsx`) — New UI tab with:
  - **Concurrency Control** — Current semaphore display, input to update (1–200), apply button
  - **Resource Estimator** — Input planned agent count, shows calculated resources table
  - **Generate Override** — Preview and download `docker-compose.override.yml`
  - **Current Status** — 4-card dashboard showing container memory, CPU, system RAM, disk
  - 10-second polling for live resource updates
- **i18n** — 33 new translation keys in English and Spanish for the Resources tab

#### Phase 3: Installer & Resize Scripts

- **`install.sh`** — Enhanced with resource-aware sizing:
  - Fresh install: prompts for planned agent count, detects system resources (RAM/CPU/disk), calculates sizing, validates, shows comparison table (✅/❌), generates `docker-compose.override.yml` with PostgreSQL tuning
  - Update: detects existing config, offers resize to recommended, manual resize, or skip
  - `SKIP_SIZING=1` env var to bypass sizing entirely (uses default semaphore=8)
  - `PLANNED_AGENTS=N` env var for non-interactive installs
  - Cross-platform: Linux + macOS support for resource detection
  - Max agent calculation based on available RAM, CPU, and disk
  - PostgreSQL tuning: `shared_buffers`, `max_connections`, `work_mem`, `effective_cache_size`
- **`scripts/hermeshq-resize.sh`** — New standalone resize script:
  - `--agents N` mode: validates resources, shows comparison table, updates `.env` and `docker-compose.override.yml`, restarts containers
  - `--detect` mode: shows current deployment stats, detected system resources, recommended resize (capped at 200 agents)
  - Interactive confirmation with `--yes` flag for automation
  - Pure bash arithmetic (no `bc` dependency)

### Fixed

- **Config singleton** — Replaced `@lru_cache` with explicit singleton in `get_settings()` to support runtime configuration updates without module reload.
- **AgentSupervisor runtime update** — Added `update_semaphore()` method to recreate `asyncio.Semaphore` in-place, allowing live concurrency changes.
- **macOS disk detection** — `df -BG` unavailable on macOS; added `df -g` fallback for Darwin systems.
- **Resize script macOS RAM** — Replaced `vm_stat`-based calculation (incorrect page size on Apple Silicon) with percentage-of-total-RAM approach.

### Technical Details

- **Sizing formulas**:
  - Semaphore = `max(1, total_agents ÷ 2)`
  - Backend RAM = `max(512, semaphore × 50MB) + 256MB`
  - PostgreSQL RAM = `max(128, total_agents × 12.5MB)`
  - CPU = `max(1, ceil(semaphore × 0.17))` for backend
  - Disk = `max(10, total_agents × 1.5GB)`
- **Resource validation**: Compares calculated needs vs. detected system resources with clear ✅/❌ indicators
- **Override generation**: Creates `docker-compose.override.yml` with `deploy.resources.limits` for all services

### Files Changed

| File | Action |
|------|--------|
| `VERSION` | Updated to 2026.5.21.1 |
| `backend/hermeshq/config.py` | Singleton settings, runtime update |
| `backend/hermeshq/services/resource_monitor.py` | **New** — Resource detection & sizing |
| `backend/hermeshq/services/agent_supervisor.py` | Runtime semaphore update, supervisor accessor |
| `backend/hermeshq/routers/settings.py` | 3 new endpoints (resources, semaphore, override) |
| `backend/hermeshq/schemas/settings.py` | 5 new Pydantic schemas |
| `frontend/src/api/settings.ts` | 3 new React Query hooks |
| `frontend/src/components/settings/ResourcesTab.tsx` | **New** — Resources settings UI |
| `frontend/src/pages/SettingsPage.tsx` | Added Resources tab |
| `frontend/src/lib/i18n/locales/en/settings.ts` | 33 new English keys |
| `frontend/src/lib/i18n/locales/es/settings.ts` | 33 new Spanish keys |
| `install.sh` | +368 lines (resource detection, sizing, override) |
| `scripts/hermeshq-resize.sh` | **New** — Standalone resize script |
| `.env.example` | Updated with all env vars |
| `docker-compose.yml` | Added CONCURRENCY_SEMAPHORE env |

---

## [2026.5.19.2] — 2026-05-19

### Fixed
- Zombie task recovery on server restart — stale running/queued tasks marked as failed.
- Provider error detection for responses disguised as successful.
- Added missing logging import for zombie task recovery.

### Added
- Concurrency semaphore (max 8) to prevent OOM on mass task submission.
- Design document `DESIGN_CONCURRENCY_SIZING.md` for configurable concurrency and resource-aware sizing.

### Fixed (post-release)
- `max_connections` PostgreSQL now has a minimum of 50 to prevent "too many clients already" errors on small deployments where `semaphore * 2` would be insufficient (e.g., semaphore=5 → 10 connections, but 9+ are needed by backend pool alone).

## [2026.5.21.2] - 2025-05-21

### Added
- **Fleet Health Dashboard** (Issue #7): `GET /api/dashboard/health` — agent status breakdown, task outcome summary, recent errors (10s polling)
- **Task Analytics Dashboard** (Issue #8): `GET /api/dashboard/analytics` — 14-day time series, P50/P95 completion, top failing agents, success rate (30s polling)
- FleetHealthPanel component — inline status chips, task counts, error list
- TaskAnalyticsPanel component — CSS bar charts, completion metrics, failing agents table
- 33 new i18n keys (EN + ES) for dashboard health and analytics

### Fixed
- Runtime semaphore update without container restart (`update_runtime_setting()` + `supervisor.update_semaphore()`)
- `Task.created_at` → `Task.queued_at` (model has no `created_at` field)
- `max_connections` minimum enforced to 50 across all generators (API, install.sh, resize.sh)
- Removed `bc` dependency from `hermeshq-resize.sh` (pure bash arithmetic)
- macOS disk detection fix in `install.sh` (`df -g` fallback for Darwin)

### Specs
- `SPEC_ISSUE_7.md` — Fleet Health Observability Dashboard detailed spec
- `SPEC_ISSUE_8.md` — Task Analytics Dashboard detailed spec
