---
name: ms365-teams
description: Leer y enviar mensajes en chats y equipos de Microsoft Teams del usuario.
---

# Microsoft 365 Teams Skill

Usa esta skill cuando el usuario necesite consultar o interactuar con sus chats y equipos de Microsoft Teams.

## Herramientas disponibles

- `teams_list_teams` — Lista los equipos de Teams a los que pertenece el usuario
- `teams_list_chats` — Lista los chats recientes del usuario
- `teams_get_chat_messages` — Obtiene mensajes de un chat específico
- `teams_send_chat_message` — Envía un mensaje a un chat

## Uso correcto

- Usa `teams_list_chats` para descubrir IDs de chats disponibles
- Usa `teams_get_chat_messages` con el `chat_id` para leer mensajes
- Para enviar, necesitas el `chat_id` y el `message`
- `teams_list_teams` muestra los equipos, no los chats individuales

## Notas

- Usa permisos delegados `Chat.Read` / `Chat.ReadWrite` del usuario autenticado
- El usuario debe tener su cuenta M365 conectada en Mi cuenta
