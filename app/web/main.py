"""FastAPI application factory for the admin dashboard."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import init_db
from app.web.routers import (
    analytics,
    auth,
    broadcast,
    dashboard,
    questions,
    responses,
    settings_router,
)
from app.web.security import NotAuthenticated

WEB_DIR = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    app = FastAPI(title="Financial Scan — Admin", docs_url=None, redoc_url=None)

    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

    # Serve static assets and dashboard-uploaded images.
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(settings.upload_path)), name="uploads")

    @app.on_event("startup")
    def _startup() -> None:
        init_db()

    @app.exception_handler(NotAuthenticated)
    async def _redirect_to_login(request: Request, exc: NotAuthenticated):
        return RedirectResponse(url="/login", status_code=303)

    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(responses.router)
    app.include_router(questions.router)
    app.include_router(settings_router.router)
    app.include_router(analytics.router)
    app.include_router(broadcast.router)

    return app


app = create_app()
