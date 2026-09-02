"""Compose and queue broadcast messages to bot users."""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app.services import broadcast
from app.web.security import require_user
from app.web.templating import render

router = APIRouter(prefix="/broadcast")


@router.get("")
def index(
    request: Request,
    user: str = Depends(require_user),
    sent: int = 0,
    missing: str = "",
    error: str = "",
):
    return render(
        request,
        "broadcast.html",
        {
            "active": "broadcast",
            "counts": broadcast.audience_counts(),
            "broadcasts": broadcast.list_broadcasts(),
            "queued": bool(sent),
            "missing": missing.replace("+", " ") if missing else "",
            "error": error.replace("+", " ") if error else "",
        },
    )


@router.post("")
def create(
    request: Request,
    user: str = Depends(require_user),
    message: str = Form(...),
    target: str = Form("all"),
    usernames: str = Form(""),
    add_button: Optional[str] = Form(None),
    button_text: str = Form(""),
):
    text = message.strip()
    if not text:
        return RedirectResponse(url="/broadcast?error=Message+is+empty", status_code=303)

    recipient_ids = None
    missing_note = ""

    if target == "custom":
        names = [n for n in re.split(r"[\s,]+", usernames or "") if n]
        if not names:
            return RedirectResponse(
                url="/broadcast?error=Enter+at+least+one+username", status_code=303
            )
        found, not_found = broadcast.resolve_usernames(names)
        if not found:
            joined = quote(", ".join("@" + n for n in not_found))
            return RedirectResponse(
                url=f"/broadcast?error=None+of+those+users+have+started+the+bot:+{joined}",
                status_code=303,
            )
        recipient_ids = [uid for uid, _ in found]
        if not_found:
            missing_note = "&missing=" + quote(", ".join("@" + n for n in not_found))

    broadcast.create_broadcast(
        message=text,
        target=target,
        add_button=add_button is not None,
        button_text=button_text,
        created_by=user,
        recipient_ids=recipient_ids,
    )
    return RedirectResponse(url=f"/broadcast?sent=1{missing_note}", status_code=303)
