from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
TOOLSET = "hermeshq_ms365_mail"


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
        url,
        method="GET",
        headers={
            "X-HermesHQ-Agent-ID": agent_id,
            "X-HermesHQ-Agent-Token": agent_token,
        },
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
    # Ensure no raw spaces or control chars in URL (encode spaces as %20)
    url = f"{GRAPH_BASE}{path}".replace(" ", "%20")
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method.upper(),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
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

def _list_emails_tool(args: dict, **_kwargs) -> str:
    user_id = _task_user_id()
    if not user_id:
        return json.dumps({"success": False, "error": "No se pudo determinar el usuario de esta tarea."})
    token, err = _get_m365_token(user_id)
    if not token:
        return _auth_error(err)
    count = min(int(args.get("count") or 10), 50)
    folder = str(args.get("folder") or "inbox")
    fields = "id,subject,from,receivedDateTime,isRead,hasAttachments,bodyPreview"
    path = f"/me/mailFolders/{folder}/messages?$top={count}&$select={fields}&$orderby=receivedDateTime%20desc"
    result = _graph("GET", path, token)
    if "error" in result:
        return json.dumps({"success": False, "error": result["error"]})
    messages = result.get("value", [])
    return json.dumps({"success": True, "count": len(messages), "messages": messages}, ensure_ascii=False)


def _get_email_tool(args: dict, **_kwargs) -> str:
    user_id = _task_user_id()
    if not user_id:
        return json.dumps({"success": False, "error": "No se pudo determinar el usuario de esta tarea."})
    token, err = _get_m365_token(user_id)
    if not token:
        return _auth_error(err)
    message_id = str(args.get("message_id") or "").strip()
    if not message_id:
        return json.dumps({"success": False, "error": "Se requiere message_id."})
    result = _graph("GET", f"/me/messages/{message_id}", token)
    if "error" in result:
        return json.dumps({"success": False, "error": result["error"]})
    return json.dumps({"success": True, "message": result}, ensure_ascii=False)


def _send_email_tool(args: dict, **_kwargs) -> str:
    user_id = _task_user_id()
    if not user_id:
        return json.dumps({"success": False, "error": "No se pudo determinar el usuario de esta tarea."})
    token, err = _get_m365_token(user_id)
    if not token:
        return _auth_error(err)
    to = args.get("to")
    subject = str(args.get("subject") or "").strip()
    body = str(args.get("body") or "").strip()
    if not to or not subject or not body:
        return json.dumps({"success": False, "error": "Se requieren: to, subject, body."})
    recipients = [{"emailAddress": {"address": a.strip()}} for a in (to if isinstance(to, list) else [to])]
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "HTML", "content": body},
            "toRecipients": recipients,
        }
    }
    result = _graph("POST", "/me/sendMail", token, payload)
    if "error" in result:
        return json.dumps({"success": False, "error": result["error"]})
    return json.dumps({"success": True, "message": "Correo enviado correctamente."})


def _search_emails_tool(args: dict, **_kwargs) -> str:
    user_id = _task_user_id()
    if not user_id:
        return json.dumps({"success": False, "error": "No se pudo determinar el usuario de esta tarea."})
    token, err = _get_m365_token(user_id)
    if not token:
        return _auth_error(err)
    query = str(args.get("query") or "").strip()
    count = min(int(args.get("count") or 10), 50)
    if not query:
        return json.dumps({"success": False, "error": "Se requiere query."})
    fields = "id,subject,from,receivedDateTime,isRead,bodyPreview"
    path = f'/me/messages?$search=%22{query}%22&$top={count}&$select={fields}'
    result = _graph("GET", path, token)
    if "error" in result:
        return json.dumps({"success": False, "error": result["error"]})
    messages = result.get("value", [])
    return json.dumps({"success": True, "count": len(messages), "messages": messages}, ensure_ascii=False)


# ── Plugin registration ───────────────────────────────────────────────────────

def register(ctx):
    ctx.register_tool(
        name="ms365_mail_list",
        toolset=TOOLSET,
        schema={
            "name": "ms365_mail_list",
            "description": "Lista los correos del usuario desde Microsoft 365. Devuelve asunto, remitente, fecha y preview del cuerpo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "Número de correos a obtener (máx 50, default 10)"},
                    "folder": {"type": "string", "description": "Carpeta: inbox (default), sentitems, drafts, deleteditems"},
                },
            },
        },
        handler=_list_emails_tool,
        description="Listar correos M365 del usuario",
        emoji="📬",
    )
    ctx.register_tool(
        name="ms365_mail_get",
        toolset=TOOLSET,
        schema={
            "name": "ms365_mail_get",
            "description": "Obtiene el contenido completo de un correo de Microsoft 365 por su ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string", "description": "ID del mensaje a obtener"},
                },
                "required": ["message_id"],
            },
        },
        handler=_get_email_tool,
        description="Obtener correo M365 por ID",
        emoji="📧",
    )
    ctx.register_tool(
        name="ms365_mail_send",
        toolset=TOOLSET,
        schema={
            "name": "ms365_mail_send",
            "description": "Envía un correo en nombre del usuario a través de Microsoft 365.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"description": "Dirección o lista de direcciones destinatarias"},
                    "subject": {"type": "string", "description": "Asunto del correo"},
                    "body": {"type": "string", "description": "Cuerpo del correo (HTML o texto plano)"},
                },
                "required": ["to", "subject", "body"],
            },
        },
        handler=_send_email_tool,
        description="Enviar correo M365 en nombre del usuario",
        emoji="📤",
    )
    ctx.register_tool(
        name="ms365_mail_search",
        toolset=TOOLSET,
        schema={
            "name": "ms365_mail_search",
            "description": "Busca correos en el buzón Microsoft 365 del usuario.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Texto a buscar en asunto, remitente o cuerpo"},
                    "count": {"type": "integer", "description": "Número máximo de resultados (default 10)"},
                },
                "required": ["query"],
            },
        },
        handler=_search_emails_tool,
        description="Buscar correos en M365",
        emoji="🔍",
    )
