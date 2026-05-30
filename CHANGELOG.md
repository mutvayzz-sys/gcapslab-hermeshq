# Changelog

All notable changes to HermesHQ will be documented in this file.

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
