from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
TOOLSET = "hermeshq_sharepoint"


def _task_user_id() -> str | None:
    raw = os.environ.get("HERMESHQ_TASK_PAYLOAD", "")
    if raw:
        try:
            payload = json.loads(raw)
            meta = payload.get("metadata") or {}
            uid = str(meta.get("thread_user_id") or meta.get("created_by_user_id") or "").strip()
            if uid:
                return uid
        except Exception:
            pass
    return os.environ.get("HERMESHQ_RESOLVED_USER_ID") or None


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

def _default_site_url() -> str:
    """Get the SharePoint site URL configured for this agent (may be empty)."""
    return os.environ.get("HERMESHQ_SHAREPOINT_SITE_URL", "").strip().rstrip("/")


def _list_files_tool(args: dict, **_kwargs) -> str:
    """List files using Files.Read.All - works with OneDrive and SharePoint."""
    user_id = _task_user_id()
    if not user_id:
        return json.dumps({"success": False, "error": "No se pudo determinar el usuario de esta tarea."})
    token, err = _get_m365_token(user_id)
    if not token:
        return _auth_error(err)

    # Use arg site_url, fallback to agent-configured site, fallback to OneDrive
    site_url = str(args.get("site_url") or _default_site_url()).strip().rstrip("/")
    folder_path = str(args.get("folder_path") or "").strip().strip("/")

    if site_url:
        # Access a specific SharePoint site by URL
        # GET /sites/{hostname}:/{site-path}
        parsed = urllib.parse.urlparse(site_url)
        hostname = parsed.netloc
        site_path = parsed.path.rstrip("/") or "/"
        base_path = f"/sites/{hostname}:{site_path}:/drive/root"
    else:
        # Default: user's OneDrive root
        base_path = "/me/drive/root"

    if folder_path:
        path = f"{base_path}:/{folder_path}:/children"
    else:
        path = f"{base_path}/children"

    result = _graph("GET", path, token)
    if "error" in result:
        return json.dumps({"success": False, "error": result["error"]})
    items = result.get("value", [])
    simplified = [
        {"id": i.get("id"), "name": i.get("name"),
         "type": "folder" if "folder" in i else "file",
         "size": i.get("size"), "url": i.get("webUrl"),
         "modified": i.get("lastModifiedDateTime")}
        for i in items
    ]
    return json.dumps({"success": True, "count": len(simplified), "items": simplified}, ensure_ascii=False)


def _get_file_tool(args: dict, **_kwargs) -> str:
    user_id = _task_user_id()
    if not user_id:
        return json.dumps({"success": False, "error": "No se pudo determinar el usuario de esta tarea."})
    token, err = _get_m365_token(user_id)
    if not token:
        return _auth_error(err)

    file_path = str(args.get("file_path") or "").strip().strip("/")
    site_url = str(args.get("site_url") or _default_site_url()).strip().rstrip("/")

    if not file_path:
        return json.dumps({"success": False, "error": "Se requiere file_path."})

    if site_url:
        parsed = urllib.parse.urlparse(site_url)
        hostname = parsed.netloc
        site_path = parsed.path.rstrip("/") or "/"
        path = f"/sites/{hostname}:{site_path}:/drive/root:/{file_path}"
    else:
        path = f"/me/drive/root:/{file_path}"

    result = _graph("GET", path, token)
    if "error" in result:
        return json.dumps({"success": False, "error": result["error"]})
    return json.dumps({"success": True, "item": result}, ensure_ascii=False)


def _list_drives_tool(args: dict, **_kwargs) -> str:
    """List accessible drives (OneDrive + SharePoint document libraries)."""
    user_id = _task_user_id()
    if not user_id:
        return json.dumps({"success": False, "error": "No se pudo determinar el usuario de esta tarea."})
    token, err = _get_m365_token(user_id)
    if not token:
        return _auth_error(err)

    result = _graph("GET", "/me/drives", token)
    if "error" in result:
        return json.dumps({"success": False, "error": result["error"]})
    drives = result.get("value", [])
    simplified = [
        {"id": d.get("id"), "name": d.get("name"),
         "type": d.get("driveType"), "url": d.get("webUrl")}
        for d in drives
    ]
    return json.dumps({"success": True, "count": len(simplified), "drives": simplified}, ensure_ascii=False)


def _search_tool(args: dict, **_kwargs) -> str:
    user_id = _task_user_id()
    if not user_id:
        return json.dumps({"success": False, "error": "No se pudo determinar el usuario de esta tarea."})
    token, err = _get_m365_token(user_id)
    if not token:
        return _auth_error(err)

    query = str(args.get("query") or "").strip()
    if not query:
        return json.dumps({"success": False, "error": "Se requiere query."})
    count = min(int(args.get("count") or 10), 25)

    payload = {
        "requests": [{
            "entityTypes": ["driveItem"],
            "query": {"queryString": query},
            "from": 0,
            "size": count,
            "fields": ["id", "name", "webUrl", "lastModifiedDateTime", "size", "parentReference"],
        }]
    }
    result = _graph("POST", "/search/query", token, payload)
    if "error" in result:
        return json.dumps({"success": False, "error": result["error"]})
    hits = []
    for resp in result.get("value", []):
        for hc in resp.get("hitsContainers", []):
            for hit in hc.get("hits", []):
                resource = hit.get("resource", {})
                hits.append({
                    "name": resource.get("name"),
                    "url": resource.get("webUrl"),
                    "modified": resource.get("lastModifiedDateTime"),
                    "size": resource.get("size"),
                })
    return json.dumps({"success": True, "count": len(hits), "hits": hits}, ensure_ascii=False)


# ── Plugin registration ───────────────────────────────────────────────────────

def register(ctx):
    ctx.register_tool(
        name="sharepoint_list_drives",
        toolset=TOOLSET,
        schema={
            "name": "sharepoint_list_drives",
            "description": "Lista las unidades de almacenamiento accesibles: OneDrive personal y bibliotecas de documentos de SharePoint.",
            "parameters": {"type": "object", "properties": {}},
        },
        handler=_list_drives_tool,
        description="Listar drives disponibles (OneDrive + SharePoint)",
        emoji="🗄️",
    )
    ctx.register_tool(
        name="sharepoint_list_files",
        toolset=TOOLSET,
        schema={
            "name": "sharepoint_list_files",
            "description": "Lista archivos y carpetas en OneDrive o en un sitio SharePoint específico.",
            "parameters": {
                "type": "object",
                "properties": {
                    "site_url": {"type": "string", "description": "URL del sitio SharePoint (opcional, ej: https://empresa.sharepoint.com/sites/Marketing). Si no se indica, usa el OneDrive del usuario."},
                    "folder_path": {"type": "string", "description": "Ruta de carpeta (opcional, ej: 'Documents/Projects')"},
                },
            },
        },
        handler=_list_files_tool,
        description="Listar archivos en SharePoint/OneDrive",
        emoji="📁",
    )
    ctx.register_tool(
        name="sharepoint_get_file",
        toolset=TOOLSET,
        schema={
            "name": "sharepoint_get_file",
            "description": "Obtiene información de un archivo por su ruta en OneDrive o SharePoint.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Ruta del archivo (ej: 'Documents/informe.pdf')"},
                    "site_url": {"type": "string", "description": "URL del sitio SharePoint (opcional)"},
                },
                "required": ["file_path"],
            },
        },
        handler=_get_file_tool,
        description="Obtener archivo de SharePoint/OneDrive",
        emoji="📄",
    )
    ctx.register_tool(
        name="sharepoint_search",
        toolset=TOOLSET,
        schema={
            "name": "sharepoint_search",
            "description": "Busca archivos y documentos en SharePoint y OneDrive usando Microsoft Search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Término de búsqueda"},
                    "count": {"type": "integer", "description": "Número de resultados (máx 25, default 10)"},
                },
                "required": ["query"],
            },
        },
        handler=_search_tool,
        description="Buscar archivos en SharePoint/OneDrive",
        emoji="🔍",
    )
