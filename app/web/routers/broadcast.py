"""Compose and queue broadcast messages to bot users."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app.services import broadcast
from app.web.security import require_user
from app.web.templating import render

router = APIRouter(prefix="/broadcast")


@router.get("")
def index(request: Request, user: str = Depends(require_user), sent: int = 0):
    return render(
        request,
        "broadcast.html",
        {
            "active": "broadcast",
            "counts": broadcast.audience_counts(),
            "broadcasts": broadcast.list_broadcasts(),
            "queued": bool(sent),
        },
    )


@router.post("")
def create(
    request: Request,
    user: str = Depends(require_user),
    message: str = Form(...),
    target: str = Form("all"),
    add_button: Optional[str] = Form(None),
    button_text: str = Form(""),
):
    text = message.strip()
    if not text:
        return RedirectResponse(url="/broadcast", status_code=303)

    broadcast.create_broadcast(
        message=text,
        target=target,
        add_button=add_button is not None,
        button_text=button_text,
        created_by=user,
    )
    return RedirectResponse(url="/broadcast?sent=1", status_code=303)
