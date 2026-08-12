"""Login / logout."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.web.security import (
    current_user,
    login_session,
    logout_session,
    verify_credentials,
)
from app.web.templating import render

router = APIRouter()


@router.get("/login")
def login_form(request: Request):
    if current_user(request):
        return RedirectResponse(url="/", status_code=303)
    return render(request, "login.html", {"error": None})


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    if not verify_credentials(username, password):
        return render(
            request,
            "login.html",
            {"error": "Invalid username or password."},
        )
    login_session(request, username)
    return RedirectResponse(url="/", status_code=303)


@router.get("/logout")
def logout(request: Request):
    logout_session(request)
    return RedirectResponse(url="/login", status_code=303)
