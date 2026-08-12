"""Bot settings, feature toggles, content texts and file management."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse

from app.config import BASE_DIR
from app.config import settings as app_settings
from app.services import content, files
from app.web.security import require_user
from app.web.templating import render

router = APIRouter(prefix="/settings")

_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_MAX_UPLOAD_BYTES = 45 * 1024 * 1024  # Telegram bot send limit is ~50 MB.


def _redirect(saved: bool = True, error: str = "") -> RedirectResponse:
    if error:
        return RedirectResponse(url=f"/settings?error={error}", status_code=303)
    return RedirectResponse(url=f"/settings?saved={int(saved)}", status_code=303)


def _safe_filename(original: str, fallback: str) -> str:
    """Sanitise a filename, preserving a short alphanumeric extension."""
    stem, dot, ext = (original or "").rpartition(".")
    if not dot:
        stem, ext = original or fallback, ""
    stem = re.sub(r"[^A-Za-z0-9_-]", "_", stem)[:60] or fallback
    ext = re.sub(r"[^A-Za-z0-9]", "", ext)[:10].lower()
    return f"{stem}.{ext}" if ext else stem


async def _save_upload(file: UploadFile, fallback: str) -> tuple[str, str]:
    """Persist an upload and return (stored_path, original_name).

    Raises ValueError with a user-facing message on validation failure.
    """
    data = await file.read()
    if not data:
        raise ValueError("Empty+file")
    if len(data) > _MAX_UPLOAD_BYTES:
        raise ValueError("File+too+large+(max+45MB)")

    app_settings.upload_path.mkdir(parents=True, exist_ok=True)
    filename = _safe_filename(file.filename or "", fallback=fallback)
    dest = (app_settings.upload_path / filename).resolve()
    dest.write_bytes(data)

    # Store a path relative to the project root when possible, so the bot (which
    # joins relative paths to BASE_DIR) resolves it regardless of working dir.
    try:
        stored: Path | str = dest.relative_to(BASE_DIR.resolve())
    except ValueError:
        stored = dest
    return str(stored), (file.filename or filename)


# --------------------------------------------------------------------------- #
# Page + settings form
# --------------------------------------------------------------------------- #
@router.get("")
def index(request: Request, user: str = Depends(require_user), saved: int = 0, error: str = ""):
    return render(
        request,
        "settings.html",
        {
            "active": "settings",
            "groups": content.get_settings_grouped(),
            "completion_files": files.list_completion_files(),
            "saved": bool(saved),
            "error": error.replace("+", " ") if error else "",
        },
    )


@router.post("")
async def save(request: Request, user: str = Depends(require_user)):
    form = await request.form()
    bool_keys = {
        item["key"]
        for group in content.get_settings_grouped().values()
        for item in group
        if item["value_type"] == "bool"
    }
    values = {k: v for k, v in form.items() if k != "csrf"}
    content.update_settings(values, bool_keys)
    return _redirect()


# --------------------------------------------------------------------------- #
# Start image (single)
# --------------------------------------------------------------------------- #
@router.post("/start-image/upload")
async def upload_start_image(
    user: str = Depends(require_user),
    file: UploadFile = File(...),
):
    if file.content_type not in _IMAGE_TYPES:
        return _redirect(error="Please+upload+an+image+(JPEG/PNG/WebP/GIF)")
    try:
        stored, _ = await _save_upload(file, fallback="start")
    except ValueError as exc:
        return _redirect(error=str(exc))
    content.set_setting("start_image_path", stored)
    return _redirect()


@router.post("/start-image/clear")
async def clear_start_image(user: str = Depends(require_user)):
    content.set_setting("start_image_path", "")
    return _redirect()


# --------------------------------------------------------------------------- #
# Completion files (multiple)
# --------------------------------------------------------------------------- #
@router.post("/completion-files/upload")
async def upload_completion_file(
    user: str = Depends(require_user),
    file: UploadFile = File(...),
    caption: str = Form(""),
):
    try:
        stored, original = await _save_upload(file, fallback="completion")
    except ValueError as exc:
        return _redirect(error=str(exc))
    files.add_completion_file(path=stored, original_name=original, caption=caption)
    return _redirect()


@router.post("/completion-files/{file_id}/update")
async def update_completion_file(
    file_id: int,
    user: str = Depends(require_user),
    caption: str = Form(""),
    is_active: Optional[str] = Form(None),
):
    files.update_completion_file(file_id, caption=caption, is_active=is_active is not None)
    return _redirect()


@router.post("/completion-files/{file_id}/move")
async def move_completion_file(
    file_id: int,
    user: str = Depends(require_user),
    direction: int = Form(...),
):
    files.move_completion_file(file_id, 1 if direction > 0 else -1)
    return _redirect()


@router.post("/completion-files/{file_id}/delete")
async def delete_completion_file(file_id: int, user: str = Depends(require_user)):
    files.delete_completion_file(file_id)
    return _redirect()
