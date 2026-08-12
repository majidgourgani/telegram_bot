"""Edit the quiz catalog: areas, questions and answer options."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app.services import catalog
from app.web.security import require_user
from app.web.templating import render

router = APIRouter(prefix="/questions")

_REDIRECT = RedirectResponse(url="/questions", status_code=303)


def _redirect() -> RedirectResponse:
    return RedirectResponse(url="/questions", status_code=303)


@router.get("")
def index(request: Request, user: str = Depends(require_user)):
    data = catalog.get_catalog()
    return render(
        request,
        "questions.html",
        {"active": "questions", **data},
    )


# --- Areas ------------------------------------------------------------------
@router.post("/areas/create")
def area_create(
    user: str = Depends(require_user),
    slug: str = Form(...),
    name: str = Form(...),
):
    if slug.strip() and name.strip():
        catalog.create_area(slug, name)
    return _redirect()


@router.post("/areas/{area_id}/delete")
def area_delete(area_id: int, user: str = Depends(require_user)):
    catalog.delete_area(area_id)
    return _redirect()


# --- Questions --------------------------------------------------------------
@router.post("/create")
def question_create(
    user: str = Depends(require_user),
    area_id: int = Form(...),
    text: str = Form(...),
):
    if text.strip():
        catalog.create_question(area_id, text)
    return _redirect()


@router.post("/{question_id}/update")
def question_update(
    question_id: int,
    user: str = Depends(require_user),
    area_id: int = Form(...),
    text: str = Form(...),
    is_active: Optional[str] = Form(None),
):
    catalog.update_question(
        question_id,
        text=text,
        area_id=area_id,
        is_active=is_active is not None,
    )
    return _redirect()


@router.post("/{question_id}/delete")
def question_delete(question_id: int, user: str = Depends(require_user)):
    catalog.delete_question(question_id)
    return _redirect()


@router.post("/{question_id}/move")
def question_move(
    question_id: int,
    user: str = Depends(require_user),
    direction: int = Form(...),
):
    catalog.move_question(question_id, 1 if direction > 0 else -1)
    return _redirect()


# --- Answer options ---------------------------------------------------------
@router.post("/options/create")
def option_create(
    user: str = Depends(require_user),
    label: str = Form(...),
    score: int = Form(...),
):
    if label.strip():
        catalog.create_option(label, score)
    return _redirect()


@router.post("/options/{option_id}/update")
def option_update(
    option_id: int,
    user: str = Depends(require_user),
    label: str = Form(...),
    score: int = Form(...),
    is_active: Optional[str] = Form(None),
):
    catalog.update_option(
        option_id, label=label, score=score, is_active=is_active is not None
    )
    return _redirect()


@router.post("/options/{option_id}/delete")
def option_delete(option_id: int, user: str = Depends(require_user)):
    catalog.delete_option(option_id)
    return _redirect()
