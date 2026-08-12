"""Home dashboard overview."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.services import content
from app.services.responses import analytics_summary
from app.web.security import require_user
from app.web.templating import render

router = APIRouter()


@router.get("/")
def home(request: Request, user: str = Depends(require_user)):
    summary = analytics_summary(days=30)
    cfg = content.get_settings_dict()
    questions = content.get_active_questions()

    token = str(cfg.get("bot_token", ""))
    token_ready = bool(token) and token != "PASTE_YOUR_BOT_TOKEN_HERE"

    cards = {
        "total": summary["total"],
        "recent": summary["recent"],
        "completion_rate": summary["completion_rate"],
        "questions": len(questions),
    }
    status = {
        "token_ready": token_ready,
        "channel_set": bool(cfg.get("channel_id")),
        "require_membership": cfg.get("require_membership", True),
        "send_start_image": cfg.get("send_start_image", True),
    }
    return render(
        request,
        "dashboard.html",
        {"cards": cards, "status": status, "summary": summary, "active": "dashboard"},
    )
