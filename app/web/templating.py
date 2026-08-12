"""Shared Jinja2 templates instance and helpers.

Kept separate from ``main`` so routers can import it without a circular import.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.web.security import current_user

WEB_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))


def _datetime_format(value, fmt: str = "%Y-%m-%d %H:%M") -> str:
    if value is None:
        return ""
    try:
        return value.strftime(fmt)
    except AttributeError:
        return str(value)


templates.env.filters["dt"] = _datetime_format


def render(request: Request, name: str, context: dict | None = None):
    """Render a template with common context (request + current user)."""
    ctx = {"request": request, "user": current_user(request)}
    if context:
        ctx.update(context)
    return templates.TemplateResponse(name, ctx)
