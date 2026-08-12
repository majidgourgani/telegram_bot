"""Bot settings, feature toggles and content texts."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import RedirectResponse

from app.config import BASE_DIR
from app.config import settings as app_settings
from app.services import content
from app.web.security import require_user
from app.web.templating import render

router = APIRouter(prefix="/settings")

_ALLOWED_IMAGE = {"image/jpeg", "image/png", "image/webp"}
_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


@router.get("")
def index(request: Request, user: str = Depends(require_user), saved: int = 0):
    groups = content.get_settings_grouped()
    return render(
        request,
        "settings.html",
        {"active": "settings", "groups": groups, "saved": bool(saved)},
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


@router.post("/upload-image")
async def upload_image(
    user: str = Depends(require_user),
    file: UploadFile = File(...),
):
    if file.content_type not in _ALLOWED_IMAGE:
        return RedirectResponse(url="/settings?saved=0", status_code=303)

    app_settings.upload_path.mkdir(parents=True, exist_ok=True)
    safe_stem = re.sub(r"[^a-zA-Z0-9_-]", "_", (file.filename or "completion").rsplit(".", 1)[0])
    filename = f"{safe_stem}{_EXT[file.content_type]}"
    dest = (app_settings.upload_path / filename).resolve()
    dest.write_bytes(await file.read())

    # Store a path relative to the project root so the bot (which joins paths to
    # BASE_DIR) can resolve it regardless of the working directory.
    try:
        stored = dest.relative_to(BASE_DIR.resolve())
    except ValueError:
        stored = dest
    content.set_setting("completion_image_path", str(stored))
    return RedirectResponse(url="/settings?saved=1", status_code=303)
