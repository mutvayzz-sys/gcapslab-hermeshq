# Changelog

All notable changes to HermesHQ are documented in this file.

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
