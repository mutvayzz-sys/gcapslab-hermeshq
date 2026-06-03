from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
TOOLSET = "hermeshq_ms365_teams"


def _task_user_id() -> str | None:
    raw = os.environ.get("HERMESHQ_TASK_PAYLOAD", "")
    if not raw:
        return None
    try:
        payload = json.loads(raw)
        meta = payload.get("metadata") or {}
        return str(meta.get("thread_user_id") or meta.get("created_by_user_id") or "").strip() or None
    except Exception:
        return None


def _get_m365_token(user_id: str) -> tuple[str | None, str]:
    base_url = os.environ.get("HERMESHQ_INTERNAL_API_URL", "").rstrip("/")
    agent_id = os.environ.get("HERMESHQ_AGENT_ID", "")
    agent_token = os.environ.get("HERMESHQ_AGENT_TOKEN", "")
    if not base_url or not agent_id or not agent_token:
        return None, "HermesHQ internal control no configurado"
    url = f"{base_url}/control/m365/agent-token?user_id={user_id}"
    req = urllib.request.Request(
        url, method="GET",
        headers={"X-HermesHQ-Agent-ID": agent_id, "X-HermesHQ-Agent-Token": agent_token},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("access_token"), ""
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body).get("detail", body)
        except Exception:
            detail = body
        return None, str(detail)
    except Exception as exc:
        return None, str(exc)


def _graph(method: str, path: str, access_token: str, payload: dict | None = None) -> dict:
    url = f"{GRAPH_BASE}{path}".replace(" ", "%20")
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(
        url, data=data, method=method.upper(),
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return {"error": json.loads(body)}
        except Exception:
            return {"error": body, "status": exc.code}


def _auth_error(detail: str) -> str:
    return json.dumps({
        "success": False,
        "error": f"No se pudo obtener token M365: {detail}. Verifica que el usuario haya conectado su cuenta Microsoft 365 en Mi cuenta.",
    })


# ── Tool handlers ─────────────────────────────────────────────────────────────

def _list_teams_tool(args: dict, **_kwargs) -> str:
    user_id = _task_user_id()
    if not user_id:
        return json.dumps({"success": False, "error": "No se pudo determinar el usuario de esta tarea."})
    token, err = _get_m365_token(user_id)
    if not token:
        return _auth_error(err)
    result = _graph("GET", "/me/joinedTeams", token)
    if "error" in result:
        return json.dumps({"success": False, "error": result["error"]})
    teams = result.get("value", [])
    simplified = [{"id": t.get("id"), "name": t.get("displayName"), "description": t.get("description")} for t in teams]
    return json.dumps({"success": True, "count": len(simplified), "teams": simplified}, ensure_ascii=False)


def _list_chats_tool(args: dict, **_kwargs) -> str:
    user_id = _task_user_id()
    if not user_id:
        return json.dumps({"success": False, "error": "No se pudo determinar el usuario de esta tarea."})
    token, err = _get_m365_token(user_id)
    if not token:
        return _auth_error(err)
    count = min(int(args.get("count") or 20), 50)
    result = _graph("GET", f"/me/chats?$top={count}&$expand=members", token)
    if "error" in result:
        return json.dumps({"success": False, "error": result["error"]})
    chats = result.get("value", [])
    simplified = []
    for c in chats:
        members = [m.get("displayName") for m in (c.get("members") or []) if m.get("displayName")]
        simplified.append({
            "id": c.get("id"),
            "topic": c.get("topic") or ", ".join(members[:3]),
            "type": c.get("chatType"),
            "members": members,
        })
    return json.dumps({"success": True, "count": len(simplified), "chats": simplified}, ensure_ascii=False)


def _get_chat_messages_tool(args: dict, **_kwargs) -> str:
    user_id = _task_user_id()
    if not user_id:
        return json.dumps({"success": False, "error": "No se pudo determinar el usuario de esta tarea."})
    token, err = _get_m365_token(user_id)
    if not token:
        return _auth_error(err)
    chat_id = str(args.get("chat_id") or "").strip()
    if not chat_id:
        return json.dumps({"success": False, "error": "Se requiere chat_id."})
    count = min(int(args.get("count") or 20), 50)
    result = _graph("GET", f"/me/chats/{chat_id}/messages?$top={count}", token)
    if "error" in result:
        return json.dumps({"success": False, "error": result["error"]})
    messages = result.get("value", [])
    simplified = [
        {"id": m.get("id"), "from": (m.get("from") or {}).get("user", {}).get("displayName"),
         "body": (m.get("body") or {}).get("content", ""), "created": m.get("createdDateTime")}
        for m in messages
    ]
    return json.dumps({"success": True, "count": len(simplified), "messages": simplified}, ensure_ascii=False)


def _send_chat_message_tool(args: dict, **_kwargs) -> str:
    user_id = _task_user_id()
    if not user_id:
        return json.dumps({"success": False, "error": "No se pudo determinar el usuario de esta tarea."})
    token, err = _get_m365_token(user_id)
    if not token:
        return _auth_error(err)
    chat_id = str(args.get("chat_id") or "").strip()
    message = str(args.get("message") or "").strip()
    if not chat_id or not message:
        return json.dumps({"success": False, "error": "Se requieren chat_id y message."})
    payload = {"body": {"contentType": "text", "content": message}}
    result = _graph("POST", f"/me/chats/{chat_id}/messages", token, payload)
    if "error" in result:
        return json.dumps({"success": False, "error": result["error"]})
    return json.dumps({"success": True, "message": "Mensaje enviado correctamente.", "id": result.get("id")})


# ── Plugin registration ───────────────────────────────────────────────────────

def register(ctx):
    ctx.register_tool(
        name="teams_list_teams",
        toolset=TOOLSET,
        schema={
            "name": "teams_list_teams",
            "description": "Lista los equipos de Microsoft Teams a los que pertenece el usuario.",
            "parameters": {"type": "object", "properties": {}},
        },
        handler=_list_teams_tool,
        description="Listar equipos de Teams",
        emoji="👥",
    )
    ctx.register_tool(
        name="teams_list_chats",
        toolset=TOOLSET,
        schema={
            "name": "teams_list_chats",
            "description": "Lista los chats recientes del usuario en Microsoft Teams.",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "Número de chats (máx 50, default 20)"},
                },
            },
        },
        handler=_list_chats_tool,
        description="Listar chats de Teams",
        emoji="💬",
    )
    ctx.register_tool(
        name="teams_get_chat_messages",
        toolset=TOOLSET,
        schema={
            "name": "teams_get_chat_messages",
            "description": "Obtiene los mensajes de un chat de Teams por su ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string", "description": "ID del chat"},
                    "count": {"type": "integer", "description": "Número de mensajes (máx 50, default 20)"},
                },
                "required": ["chat_id"],
            },
        },
        handler=_get_chat_messages_tool,
        description="Obtener mensajes de un chat Teams",
        emoji="📨",
    )
    ctx.register_tool(
        name="teams_send_chat_message",
        toolset=TOOLSET,
        schema={
            "name": "teams_send_chat_message",
            "description": "Envía un mensaje de texto a un chat de Microsoft Teams.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chat_id": {"type": "string", "description": "ID del chat de Teams"},
                    "message": {"type": "string", "description": "Texto del mensaje a enviar"},
                },
                "required": ["chat_id", "message"],
            },
        },
        handler=_send_chat_message_tool,
        description="Enviar mensaje en chat Teams",
        emoji="📤",
    )
