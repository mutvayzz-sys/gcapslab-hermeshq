# Changelog

All notable changes to HermesHQ will be documented in this file.

## v0.2.2 — 2026-06-25

### Added
- **Multi-tenant provision system** — `POST /api/desktop/provision` with mode resolution (`headmaster_local`, `headmaster_remote`, `headmaster_plus_thin`)
- **Organization model** — `Organization` table with `kind` (school/company/personal), `default_mode`, `default_capabilities`, `system_prompt_override`
- **User tenancy** — `organization_id` foreign key on `User` model, role-based access (`admin`, `beta_user`, `school_admin`, `staff`, `student`)
- **Container supervisor** — Docker-based container lifecycle (create/start/stop/destroy/health monitor) with subprocess fallback
- **Container model** — Lifecycle statuses (pending/creating/running/stopped/error/destroyed) per user
- **Remote runtime endpoints** — Cloud container config in provision snapshot, endpoint URL generation
- **Audit logging** — Provision events, container lifecycle, mode changes, security events
- **System prompt override** — Organization-level system prompt injection
- **GET /api/desktop/provision/current** — Returns resolved mode based on user role + org settings
- **Alembic migration** — Organizations table + user foreign key

### Fixed
- **AGENTS.md stale paths** — Removed deprecated `gcaplabs-headmaster/repo/` prefix
- **GitHub workflows** — Removed `aioncore` references, updated `iOfficeAI` → `GCAP-Labs`

### Changed
- **Version** — 0.2.1 → 0.2.2
- **User model** — Added `organization_id`, expanded role enum
- **Desktop provision schema** — Added `cloud_container_config`, `local_container_config`, `system_prompt_override`

### Security
- **Timing-safe token comparison** — `hmac.compare_digest()` for token validation
- **Runtime validation** — Privileged actions require active provision

---

## v2026.5.30.1 — 2026-05-30

### Added
- **Microsoft 365 Delegated Auth** — Device Code Flow for per-user M365 authentication with encrypted token storage
- **MS365 Mail Plugin** — list, get, send, and search emails via Microsoft Graph API using delegated permissions
- **MS365 Admin Settings** — M365 configuration tab in Settings (Azure AD app registration)
- **MS365 User Connect** — M365 connection panel in My Account for users to link their accounts
- **MS365 Agent Scopes** — Per-agent M365 scope permissions (AgentAssignment.m365_allowed_scopes)
- **User Isolation on Tasks** — Tasks are now filtered by `created_by_user_id` for non-admin users
- **Auxiliary Models** — Per-agent secondary model configuration (vision, compression, web_extract, approval) with JSON field
- **Available Models per Provider** — `available_models` list on providers with frontend dropdowns
- **Vision in Standard Profile** — `vision` toolset now enabled by default for all standard agents
- **Agent Model Override** — `use_provider_default` flag + per-agent model selection with provider dropdown
- **Mobile Attachments API** — Upload, download, and delete files per agent (PR #13)

### Fixed
- **Gateway Supervisor crash loop** — Transient error handling, configurable timeout/retries, filter stopped agents
- **Install.sh** — TTY stdin handling, URL-encoded DB passwords, URI-safe random passwords
- **Alembic migrations** — Idempotent column/table guards, proper migration chain
- **Backend port 8000** — Changed from `ports` to `expose` (only accessible via nginx)
- **Nginx** — `client_max_body_size 100m` for large attachment uploads
- **WebSocket stream** — Cleanup on unexpected errors via `finally` block
- **Timing-safe token comparison** — `hmac.compare_digest()` for agent M365 token validation
- **AuxiliaryModelEntry serialization** — Pydantic → dict conversion for JSONB storage
- **TaskRead schema** — Added missing `created_by_user_id` field

### Changed
- **Docker resources** — Backend increased to 2G RAM / 1.8 CPUs
- **Database pool** — Pre-ping enabled for connection health checks
- **Provider catalog** — 8 providers with `available_models` lists

### Dependencies
- `msal>=1.28,<2.0` (Microsoft Authentication Library)
