"""Bot settings, feature toggles, content texts and file uploads."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse

from app.config import BASE_DIR
from app.config import settings as app_settings
from app.services import content
from app.web.security import require_user
from app.web.templating import render

router = APIRouter(prefix="/settings")

_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_MAX_UPLOAD_BYTES = 45 * 1024 * 1024  # Telegram bot send limit is ~50 MB.

# Upload targets: form field "target" -> (setting key, images-only?)
_UPLOAD_TARGETS = {
    "completion_file": ("completion_file_path", False),
    "start_image": ("start_image_path", True),
}


@router.get("")
def index(request: Request, user: str = Depends(require_user), saved: int = 0, error: str = ""):
    groups = content.get_settings_grouped()
    return render(
        request,
        "settings.html",
        {"active": "settings", "groups": groups, "saved": bool(saved), "error": error},
    )


@router.post("")
async def save(request: Request, user: str = Depends(require_user)):
    form = await request.form()
    # Collect the set of boolean settings so unchecked boxes become "false".
    bool_keys = {
        item["key"]
        for group in content.get_settings_grouped().values()
        for item in group
        if item["value_type"] == "bool"
    }
    values = {k: v for k, v in form.items() if k != "csrf"}
    content.update_settings(values, bool_keys)
    return RedirectResponse(url="/settings?saved=1", status_code=303)


def _safe_filename(original: str, fallback: str) -> str:
    """Sanitise a filename, preserving a short alphanumeric extension."""
    stem, dot, ext = (original or "").rpartition(".")
    if not dot:
        stem, ext = original or fallback, ""
    stem = re.sub(r"[^A-Za-z0-9_-]", "_", stem)[:60] or fallback
    ext = re.sub(r"[^A-Za-z0-9]", "", ext)[:10].lower()
    return f"{stem}.{ext}" if ext else stem


@router.post("/upload")
async def upload(
    user: str = Depends(require_user),
    target: str = Form(...),
    file: UploadFile = File(...),
):
    if target not in _UPLOAD_TARGETS:
        return RedirectResponse(url="/settings?error=Unknown+upload+target", status_code=303)
    setting_key, images_only = _UPLOAD_TARGETS[target]

    if images_only and file.content_type not in _IMAGE_TYPES:
        return RedirectResponse(
            url="/settings?error=Please+upload+an+image+(JPEG/PNG/WebP/GIF)", status_code=303
        )

    data = await file.read()
    if not data:
        return RedirectResponse(url="/settings?error=Empty+file", status_code=303)
    if len(data) > _MAX_UPLOAD_BYTES:
        return RedirectResponse(url="/settings?error=File+too+large+(max+45MB)", status_code=303)

    app_settings.upload_path.mkdir(parents=True, exist_ok=True)
    filename = _safe_filename(file.filename or "", fallback=target)
    dest = (app_settings.upload_path / filename).resolve()
    dest.write_bytes(data)

    # Store a path relative to the project root when possible, so the bot (which
    # joins relative paths to BASE_DIR) resolves it regardless of working dir.
    try:
        stored: Path | str = dest.relative_to(BASE_DIR.resolve())
    except ValueError:
        stored = dest
    content.set_setting(setting_key, str(stored))
    return RedirectResponse(url="/settings?saved=1", status_code=303)


@router.post("/clear-file")
async def clear_file(
    user: str = Depends(require_user),
    target: str = Form(...),
):
    """Unset a file setting (does not delete the file on disk)."""
    if target in _UPLOAD_TARGETS:
        content.set_setting(_UPLOAD_TARGETS[target][0], "")
    return RedirectResponse(url="/settings?saved=1", status_code=303)
