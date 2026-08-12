"""Browse, inspect, delete and export collected responses."""

from __future__ import annotations

from typing import Optional

import csv
import io

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, StreamingResponse

from app.services import content
from app.services.responses import (
    all_responses_for_export,
    delete_response,
    get_response,
    list_responses,
)
from app.web.security import require_user
from app.web.templating import render

router = APIRouter(prefix="/responses")

PAGE_SIZE = 25


def _area_columns() -> list[dict]:
    return content.get_areas()


@router.get("")
def index(
    request: Request,
    user: str = Depends(require_user),
    q: Optional[str] = None,
    page: int = 1,
):
    page = max(page, 1)
    offset = (page - 1) * PAGE_SIZE
    rows, total = list_responses(search=q, limit=PAGE_SIZE, offset=offset)

    areas = _area_columns()
    # Map each response's area scores by slug for table rendering.
    table = []
    for row in rows:
        scores = {s.area_slug: s.score for s in row.area_scores}
        table.append({"row": row, "scores": scores})

    total_pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    return render(
        request,
        "responses.html",
        {
            "active": "responses",
            "table": table,
            "areas": areas,
            "q": q or "",
            "page": page,
            "total": total,
            "total_pages": total_pages,
        },
    )


@router.get("/export.csv")
def export_csv(user: str = Depends(require_user)):
    areas = content.get_areas()
    rows = all_responses_for_export()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    header = ["id", "first_name", "last_name", "phone_number", "telegram_username"]
    header += [a["slug"] for a in areas]
    header += ["created_at_utc"]
    writer.writerow(header)

    for row in rows:
        scores = {s.area_slug: s.score for s in row.area_scores}
        line = [
            row.id,
            row.first_name,
            row.last_name,
            row.phone_number,
            row.telegram_username or "",
        ]
        line += [f"{scores.get(a['slug'], ''):.2f}" if a["slug"] in scores else "" for a in areas]
        line += [row.created_at.isoformat() if row.created_at else ""]
        writer.writerow(line)

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=responses.csv"},
    )


@router.get("/export.xlsx")
def export_xlsx(user: str = Depends(require_user)):
    from openpyxl import Workbook

    areas = content.get_areas()
    rows = all_responses_for_export()

    wb = Workbook()
    ws = wb.active
    ws.title = "Responses"
    header = ["id", "first_name", "last_name", "phone_number", "telegram_username"]
    header += [a["name"] for a in areas]
    header += ["created_at_utc"]
    ws.append(header)

    for row in rows:
        scores = {s.area_slug: s.score for s in row.area_scores}
        line = [
            row.id,
            row.first_name,
            row.last_name,
            row.phone_number,
            row.telegram_username or "",
        ]
        line += [round(scores[a["slug"]], 2) if a["slug"] in scores else None for a in areas]
        line += [row.created_at.replace(tzinfo=None) if row.created_at else None]
        ws.append(line)

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=responses.xlsx"},
    )


@router.get("/{response_id}")
def detail(request: Request, response_id: int, user: str = Depends(require_user)):
    response = get_response(response_id)
    if response is None:
        return RedirectResponse(url="/responses", status_code=303)
    return render(
        request,
        "response_detail.html",
        {"active": "responses", "r": response},
    )


@router.post("/{response_id}/delete")
def remove(response_id: int, user: str = Depends(require_user)):
    delete_response(response_id)
    return RedirectResponse(url="/responses", status_code=303)
