"""Analytics page + JSON feed for the charts."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.services.responses import analytics_summary
from app.web.security import require_user
from app.web.templating import render

router = APIRouter(prefix="/analytics")


@router.get("")
def index(request: Request, user: str = Depends(require_user), days: int = 30):
    days = days if days in (7, 30, 90, 365) else 30
    summary = analytics_summary(days=days)
    return render(
        request,
        "analytics.html",
        {"active": "analytics", "summary": summary, "days": days},
    )
