# 🔍 Auditoría Completa de HermesHQ — Informe de Mejoras

> **Fecha**: 2026-05-25  
> **Alcance**: Backend (Python/FastAPI), Frontend (React 19/TypeScript), DevOps (Docker)  
> **Tamaño**: ~23,265 líneas en 148 archivos (backend) + 75 archivos (frontend)  
> **Estado**: Pendiente de implementación

---

## Resumen Ejecutivo

HermesHQ es una plataforma de control multi-agente con un **backend FastAPI (Python)**, un **frontend React 19 + TypeScript**, y despliegue vía **Docker Compose**. La app es funcional y tiene una arquitectura razonable, pero presenta problemas significativos en **seguridad, cobertura de tests, monitoreo y mantenibilidad** que deben abordarse antes de un uso serio en producción.

---

## 🚨 P0 — CRÍTICO (Corregir inmediatamente)

### 1. Seguridad — Credenciales por defecto inseguras

| Archivo | Problema |
|---------|----------|
| `backend/hermeshq/config.py:28` | JWT secret por defecto = `"change-me"` |
| `backend/hermeshq/config.py:44-45` | Admin por defecto = `admin` / `admin123` |
| `docker-compose.yml` | `JWT_SECRET: ${JWT_SECRET:-change-me}`, `ADMIN_PASSWORD: ${ADMIN_PASSWORD:-admin123}` |

**Impacto**: Cualquier despliegue sin `.env` correcto queda expuesto. Un atacante puede forjar tokens JWT arbitrarios.

**Recomendación**:
- El instalador ya genera secretos aleatorios ✅, pero la app debería **rechazar arrancar** si detecta los valores por defecto en producción.
- Forzar cambio de contraseña en el primer login.

**Estado**: 🔴 Pendiente

---

### 2. Seguridad — Token de agente determinístico

`backend/hermeshq/core/security.py:48-53`: El token de servicio del agente es un HMAC determinístico sin expiración ni rotación. Una vez conocido, es válido para siempre.

**Recomendación**: Añadir timestamp/salt al HMAC, implementar rotación periódica.

**Estado**: 🔴 Pendiente

---

### 3. Seguridad — Comparación de tokens vulnerable a timing attacks

`backend/hermeshq/routers/internal_control.py:62`:
```python
if service_agent_token != expected:  # ← vulnerable
```
**Recomendación**: Usar `hmac.compare_digest()`.

**Estado**: 🔴 Pendiente

---

### 4. Seguridad — Sin rate limiting en login

`frontend/nginx.conf`: Las directivas de rate limiting están **comentadas**. El endpoint de login no tiene protección contra fuerza bruta.

**Recomendación**: Habilitar `limit_req_zone` en nginx y añadir rate limiting a nivel de aplicación.

**Estado**: 🔴 Pendiente

---

### 5. Seguridad — Backups sin cifrar

`scripts/backup-instance.sh`: El archivo de backup contiene `.env` (con todos los secretos) y el dump de PostgreSQL **en texto plano**.

**Recomendación**: Cifrar el archivo tar.gz con una passphrase antes de escribirlo a disco.

**Estado**: 🔴 Pendiente

---

### 6. Sin HEALTHCHECK en Docker

Ni el `Dockerfile` del backend, ni el del frontend, ni `docker-compose.yml` definen health checks. Docker/orquestadores no pueden determinar si la app está viva.

**Recomendación**:
```dockerfile
# Backend Dockerfile
HEALTHCHECK --interval=30s CMD curl -f http://localhost:8000/health || exit 1
```

**Estado**: 🔴 Pendiente

---

### 7. Frontend — Sin Error Boundary

`src/main.tsx`: No hay `<ErrorBoundary>` en la raíz. Cualquier error no capturado produce una **pantalla blanca** sin feedback al usuario.

**Estado**: 🔴 Pendiente

---

### 8. Frontend — Decodificación JWT incorrecta

`src/stores/sessionStore.ts:27`:
```typescript
const payload = JSON.parse(atob(parts[1])); // ← falla con base64url
```
Los JWT usan base64url (`-` y `_` en vez de `+` y `/`). Esto fallará silenciosamente con muchos tokens.

**Recomendación**: `atob(parts[1].replace(/-/g, '+').replace(/_/g, '/'))`.

**Estado**: 🔴 Pendiente

---

### 9. Sin CI/CD

**No existe ninguna configuración de CI/CD** — no hay GitHub Actions, no hay linting automatizado, no hay tests automatizados, no hay publicación de imágenes Docker.

**Recomendación**: Crear `.github/workflows/ci.yml` con stages de lint → test → build → push.

**Estado**: 🔴 Pendiente

---

## ⚠️ P1 — ALTO (Corregir en el próximo sprint)

### 10. Backend — Archivos "Dios" (God Files)

| Archivo | Líneas | Funciones |
|---------|--------|-----------|
| `hermes_installation.py` | 1,159 | 53 |
| `gateway_supervisor.py` | 1,188 | 44 |
| `mcp_server.py` | 944 | 29 |
| `auth.py` | 913 | — |
| `internal_control.py` | 828 | 42 |

Estos archivos violan gravemente el Principio de Responsabilidad Única. `hermes_installation.py` maneja workspace, config YAML, soul.md, skills, plugins, skins, dotenv, system prompt, roster, WhatsApp bridge, y más.

**Recomendación**: Descomponer en módulos por dominio (p.ej. `installation/workspace.py`, `installation/config_builder.py`, `installation/skill_sync.py`).

**Estado**: 🔴 Pendiente

---

### 11. Frontend — Componente "Dios" de 1,587 líneas

`src/pages/AgentDetailPage.tsx` tiene **20+ `useState`**, sincronización manual de datos con `useEffect`, y 12 handlers async inline. Maneja: identidad, system prompt, runtime profile, versiones, approval mode, integraciones, skills, activity logs, workspace, terminal, y más.

**Recomendación**: Descomponer en 8-10 sub-componentes: `AgentIdentitySection`, `AgentRuntimeSection`, `AgentIntegrationsSection`, etc.

**Estado**: 🔴 Pendiente

---

### 12. Backend — Performance: cientos de queries DB por tarea

`agent_supervisor.py:249-276`: `stream_callback` abre una **nueva sesión DB por cada chunk** de streaming. Una tarea con 500 chunks = 500 round-trips a la base de datos.

**Recomendación**: Batch writes — acumular chunks y flush cada N segundos o N chunks.

**Estado**: 🔴 Pendiente

---

### 13. Backend — Memory leak en rate limiter

`mcp_rate_limiter.py`: El método `cleanup()` existe pero **nunca se llama**. `_windows` crece indefinidamente.

**Recomendación**: Programar cleanup periódico como tarea background.

**Estado**: 🔴 Pendiente

---

### 14. Frontend — 15 queries de polling simultáneas

`AgentMessagingPanel.tsx`: Consulta runtime + logs para las 5 plataformas (Telegram, WhatsApp, Teams, GChat, Kapso) **simultáneamente**, cada una con `refetchInterval: 5000`. Resultado: **~10 requests cada 5 segundos** por página de agente.

**Recomendación**: Solo consultar la plataforma activa (lazy loading por tab).

**Estado**: 🔴 Pendiente

---

### 15. Frontend — Código duplicado

| Qué | Dónde |
|-----|-------|
| `slugify()` | `AgentDetailPage.tsx` ↔ `AgentsPage.tsx` |
| `statusTone()` | `AgentDetailPage.tsx` ↔ `AgentsPage.tsx` |
| `safeReadLocalStorage()` | `sessionStore.ts` ↔ `uiStore.ts` |
| Opciones de configuración | `AgentDetailPage.tsx` ↔ `AgentsPage.tsx` |

**Recomendación**: Extraer a `src/lib/utils.ts` y `src/lib/agent-helpers.ts`.

**Estado**: 🔴 Pendiente

---

### 16. Tipado débil en la API

`src/api/agents.ts`: `Record<string, unknown>` para payloads de creación/edición de agentes. Esto elimina toda la seguridad de tipos.

`src/types/api.ts`: La interfaz `Agent` tiene 40+ campos y `RealtimeEvent` es genérico (`type: string` en vez de unión de tipos conocidos).

**Recomendación**: Crear DTOs tipados (`CreateAgentRequest`, `UpdateAgentRequest`) y usar uniones discriminadas.

**Estado**: 🔴 Pendiente

---

### 17. Sin infraestructura de tests

| Área | Tests |
|------|-------|
| Backend — 148 archivos | **9 tests** en 1 archivo |
| Frontend — 75 archivos | **0 tests** |

No hay `conftest.py`, no hay fixtures, no hay vitest, no hay testing-library.

**Recomendación**: Establecer infraestructura mínima con tests de integración para auth, agents, y MCP.

**Estado**: 🔴 Pendiente

---

### 18. Configuración global mutable sin validación

`config.py:96`: `update_runtime_setting(key, value)` usa `setattr()` sin validación, thread safety, ni audit logging.

**Estado**: 🔴 Pendiente

---

## 📋 P2 — MEDIO (Planificar a corto/medio plazo)

### 19. Anti-patrón Service Locator

Todo el backend accede a servicios vía `request.app.state.*`. Esto equivale a un Service Locator global — imposible entender dependencias sin leer cada call site.

**Recomendación**: Inyectar dependencias vía FastAPI `Depends()` o un contenedor DI.

**Estado**: 🔴 Pendiente

---

### 20. Patrones de código

| Problema | Ejemplo |
|----------|---------|
| `except Exception: pass` | `gateway_supervisor.py`, `hermes_installation.py:600`, `auth.py:632` |
| Magic strings para estados | `"running"`, `"stopped"`, `"queued"` aparecen en 10+ archivos |
| `datetime.utcnow()` deprecado | `gateway_supervisor.py:316` (Python 3.12+) |
| Import circular lazy | `agent_supervisor.py:703` → `from hermeshq.main import app` |

**Recomendación**: Usar Enums para estados/roles, usar `datetime.now(timezone.utc)`, eliminar el import circular con una interfaz.

**Estado**: 🔴 Pendiente

---

### 21. Frontend — UX/Accesibilidad

- `window.confirm()` / `window.alert()` bloquean el hilo UI y no son estilizables
- Sin ARIA labels en botones de solo icono
- Sin gestión de foco en cambios de ruta
- Sin skip-to-content link
- Org chart sin soporte de teclado

**Estado**: 🔴 Pendiente

---

### 22. Frontend — Configuración de TanStack Query

`src/main.tsx`: `new QueryClient()` sin defaults → `staleTime: 0` causa refetching agresivo. Además, mutaciones invalidan caches demasiado amplias (`["dashboard"]`, `["agents"]`, `["tasks"]`, `["logs"]` simultáneamente).

**Estado**: 🔴 Pendiente

---

### 23. DevOps — Documentación faltante

| Documento | Estado |
|-----------|--------|
| `SECURITY.md` | ❌ No existe |
| Guía de despliegue productivo | ❌ No existe |
| Referencia de variables de entorno | ❌ Incompleta |
| Guía de troubleshooting | ❌ No existe |
| `CONTRIBUTING.md` | ❌ No existe |
| Arquitectura ADRs | ❌ No existe |

**Estado**: 🔴 Pendiente

---

### 24. DevOps — Observabilidad

- Sin métricas Prometheus
- Sin logging estructurado (JSON)
- Sin tracing distribuido
- Sin alerting
- El endpoint `/health` solo devuelve la versión, no checkea DB ni dependencias

**Estado**: 🔴 Pendiente

---

### 25. Dependencias

| Problema | Detalle |
|----------|---------|
| `python-telegram-bot`, `faster-whisper` como obligatorios | Deberían ser extras opcionales (`pip install hermeshq[telegram]`) |
| `python-jose` abandonado | Migrar a `PyJWT` |
| Sin lockfile | `requirements.txt` con rangos, no hay `requirements.lock` |
| Imágenes Docker con tags flotantes | `python:3.11-slim` → debería usar digest |
| PyYAML no listado | Se importa pero no está en `requirements.txt` |

**Estado**: 🔴 Pendiente

---

## 📊 Resumen de Prioridades

| Prioridad | Cantidad | Esfuerzo estimado |
|-----------|----------|-------------------|
| **P0 — Crítico** | 9 items | ~2-3 semanas |
| **P1 — Alto** | 9 items | ~4-6 semanas |
| **P2 — Medio** | 7 items | ~6-8 semanas |

---

## 🏗️ Propuesta de Hoja de Ruta

```
Sprint 1-2 (P0): Seguridad crítica + Health checks + Error Boundary
├── Eliminar credenciales por defecto
├── hmac.compare_digest para tokens
├── Rate limiting en nginx
├── HEALTHCHECK en Dockerfiles
├── Error Boundary en frontend
├── Fix decodificación JWT base64url
└── CI/CD básico (lint + build)

Sprint 3-5 (P1): Arquitectura + Performance + Tests
├── Descomponer god files (backend + frontend)
├── Batch writes en stream_callback
├── Rate limiter cleanup periódico
├── Lazy loading de canales de mensajería
├── Extraer código duplicado
├── DTOs tipados en frontend
└── Tests de integración (auth, agents, MCP)

Sprint 6-8 (P2): Observabilidad + DX + Pulido
├── Métricas Prometheus + dashboard Grafana
├── Logging estructurado JSON
├── Enums para estados/roles
├── Accesibilidad (ARIA, foco, teclado)
├── Documentación (SECURITY.md, deployment guide)
├── Lockfiles + Docker image pinning
└── Dependency extras para pesos pesados
```

---

## 📝 Changelog

| Fecha | Cambio |
|-------|--------|
| 2026-05-25 | Creación del informe a partir de auditoría completa del codebase |
