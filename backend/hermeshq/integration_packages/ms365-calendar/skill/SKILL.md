---
name: ms365-calendar
description: Consultar, crear y gestionar eventos del calendario Microsoft 365 del usuario.
---

# Microsoft 365 Calendar Skill

Usa esta skill cuando el usuario necesite ver, crear, editar o eliminar eventos de su calendario Microsoft 365.

## Herramientas disponibles

- `ms365_calendar_list_events` — Lista eventos en un rango de fechas
- `ms365_calendar_get_event` — Obtiene detalle completo de un evento por ID
- `ms365_calendar_create_event` — Crea un nuevo evento en el calendario
- `ms365_calendar_update_event` — Modifica un evento existente
- `ms365_calendar_delete_event` — Elimina un evento del calendario

## Uso correcto

- Las fechas deben estar en formato ISO 8601 (ej: `2026-06-01T10:00:00`)
- Para crear reuniones, incluye `attendees` con lista de emails
- Usa `ms365_calendar_list_events` con rango de fechas para ver disponibilidad
- Siempre confirma antes de eliminar eventos

## Notas

- Todos los accesos usan permisos delegados del usuario autenticado
- El usuario debe tener su cuenta M365 conectada en Mi cuenta
