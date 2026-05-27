"""Mobile app attachment endpoints – upload, download, delete media files."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from hermeshq.core.security import ensure_agent_access, get_current_user
from hermeshq.database import get_db_session
from hermeshq.models.user import User

router = APIRouter(prefix="/agents", tags=["attachments"])

ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg",
    ".mp3", ".aac", ".ogg", ".wav", ".m4a", ".flac",
    ".mp4", ".webm", ".mov", ".avi", ".mkv",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".csv", ".json", ".md", ".xml", ".html", ".zip",
}

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

MIME_MAP = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
    ".mp3": "audio/mpeg", ".aac": "audio/aac", ".ogg": "audio/ogg",
    ".wav": "audio/wav", ".m4a": "audio/mp4", ".flac": "audio/flac",
    ".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime",
    ".avi": "video/x-msvideo", ".mkv": "video/x-matroska",
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain", ".csv": "text/csv", ".json": "application/json",
    ".md": "text/markdown", ".xml": "application/xml", ".html": "text/html",
    ".zip": "application/zip",
}


def _resolve_media_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return MIME_MAP.get(ext, "application/octet-stream")


def _uploads_dir(workspace_manager, agent_id: str) -> Path:
    workspace = workspace_manager.build_workspace_path(agent_id)
    uploads = workspace / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    return uploads


@router.post("/{agent_id}/attachments")
async def upload_attachment(
    agent_id: str,
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Upload a media file for an agent. Returns file_id and metadata."""
    await ensure_agent_access(db, current_user, agent_id)

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed.",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large. Max {MAX_FILE_SIZE // (1024*1024)}MB")

    file_id = str(uuid.uuid4())
    safe_filename = f"{file_id}{ext}"
    uploads = _uploads_dir(request.app.state.workspace_manager, agent_id)
    file_path = uploads / safe_filename

    with open(file_path, "wb") as f:
        f.write(content)

    media_type = _resolve_media_type(file.filename)
    relative_path = f"uploads/{safe_filename}"

    return {
        "file_id": file_id,
        "filename": file.filename,
        "media_type": media_type,
        "size": len(content),
        "path": relative_path,
    }


@router.get("/{agent_id}/attachments/{file_id}")
async def download_attachment(
    agent_id: str,
    file_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> FileResponse:
    """Download an attachment by file_id."""
    await ensure_agent_access(db, current_user, agent_id)

    uploads = _uploads_dir(request.app.state.workspace_manager, agent_id)
    matches = list(uploads.glob(f"{file_id}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="Attachment not found")

    file_path = matches[0]
    media_type = _resolve_media_type(file_path.name)
    return FileResponse(file_path, media_type=media_type, filename=file_path.name)


@router.delete("/{agent_id}/attachments/{file_id}")
async def delete_attachment(
    agent_id: str,
    file_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Delete an attachment by file_id."""
    await ensure_agent_access(db, current_user, agent_id)

    uploads = _uploads_dir(request.app.state.workspace_manager, agent_id)
    matches = list(uploads.glob(f"{file_id}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="Attachment not found")

    for match in matches:
        match.unlink()

    return {"status": "deleted", "file_id": file_id}
