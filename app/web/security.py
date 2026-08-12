"""Session-based authentication for the dashboard.

A single admin account (from ``.env``) is supported — enough for one operator.
Login state is stored in a signed session cookie via Starlette's
``SessionMiddleware``.
"""

from __future__ import annotations

import hmac

from fastapi import Request

from app.config import settings

SESSION_USER_KEY = "user"


class NotAuthenticated(Exception):
    """Raised by the ``require_user`` dependency when no valid session exists."""


def verify_credentials(username: str, password: str) -> bool:
    """Constant-time check against the configured admin credentials."""
    user_ok = hmac.compare_digest(username or "", settings.admin_username)
    pass_ok = hmac.compare_digest(password or "", settings.admin_password)
    return user_ok and pass_ok


def login_session(request: Request, username: str) -> None:
    request.session[SESSION_USER_KEY] = username


def logout_session(request: Request) -> None:
    request.session.pop(SESSION_USER_KEY, None)


def current_user(request: Request) -> str | None:
    return request.session.get(SESSION_USER_KEY)


def require_user(request: Request) -> str:
    """FastAPI dependency: return the logged-in user or raise NotAuthenticated."""
    user = current_user(request)
    if not user:
        raise NotAuthenticated()
    return user
