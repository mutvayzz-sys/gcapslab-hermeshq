---
name: ms365-mail
description: Leer, buscar y enviar correos electrónicos usando la cuenta Microsoft 365 del usuario.
---

# Microsoft 365 Mail Skill

Usa esta skill cuando el usuario necesite consultar, buscar o enviar correos de su cuenta Microsoft 365.

## Herramientas disponibles

- `ms365_mail_list` — Lista los correos de una carpeta (inbox, sentitems, drafts)
- `ms365_mail_get` — Obtiene el contenido completo de un correo por su ID
- `ms365_mail_send` — Envía un correo en nombre del usuario
- `ms365_mail_search` — Busca correos por palabras clave

## Uso correcto

- Usa `ms365_mail_list` primero para obtener IDs de correos
- Usa `ms365_mail_get` para leer el cuerpo completo de un correo específico
- Para enviar, asegúrate de tener `to`, `subject` y `body`
- Para buscar, usa `ms365_mail_search` con términos relevantes

## Notas

- Todos los accesos usan permisos delegados del usuario autenticado
- El usuario debe tener su cuenta M365 conectada en Mi cuenta
