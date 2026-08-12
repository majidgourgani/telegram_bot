"""Persisting completed responses and reading them back for the dashboard."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select

from app.database import session_scope
from app.models import (
    Event,
    Response,
    ResponseAnswer,
    ResponseAreaScore,
)
from app.services.scoring import area_scores_from_answers


def log_event(event_type: str, telegram_user_id: int | None = None) -> None:
    with session_scope() as session:
        session.add(Event(type=event_type, telegram_user_id=telegram_user_id))


def save_response(
    *,
    first_name: str,
    last_name: str,
    phone_number: str,
    telegram_user_id: int | None,
    telegram_username: str | None,
    answers: dict[int, dict[str, Any]],
    snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    """Persist a completed response and return the computed area scores."""
    questions = snapshot["questions"]
    areas = snapshot["areas"]
    scores = area_scores_from_answers(answers, questions, areas)

    with session_scope() as session:
        response = Response(
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
        )
        session.add(response)
        session.flush()  # assign response.id

        for index, question in enumerate(questions):
            if index not in answers:
                continue
            answer = answers[index]
            session.add(
                ResponseAnswer(
                    response_id=response.id,
                    question_id=question.get("id"),
                    area_slug=question["area_slug"],
                    question_text=question["text"],
                    label=answer["label"],
                    score=answer["score"],
                )
            )

        for area_score in scores:
            session.add(
                ResponseAreaScore(
                    response_id=response.id,
                    area_slug=area_score["slug"],
                    area_name=area_score["name"],
                    score=area_score["score"],
                )
            )

    return scores


# --------------------------------------------------------------------------- #
# Dashboard read helpers
# --------------------------------------------------------------------------- #
def list_responses(
    *,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Response], int]:
    """Return (rows, total_count), newest first, optionally filtered."""
    with session_scope() as session:
        stmt = select(Response)
        count_stmt = select(func.count(Response.id))

        if search:
            like = f"%{search.strip()}%"
            condition = (
                Response.first_name.ilike(like)
                | Response.last_name.ilike(like)
                | Response.phone_number.ilike(like)
            )
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        total = session.scalar(count_stmt) or 0
        stmt = stmt.order_by(Response.created_at.desc()).limit(limit).offset(offset)
        rows = session.scalars(stmt).all()

        # Eager-load related collections before the session closes.
        for row in rows:
            _ = row.area_scores
        session.expunge_all()
        return rows, total


def get_response(response_id: int) -> Response | None:
    with session_scope() as session:
        response = session.get(Response, response_id)
        if response is None:
            return None
        _ = response.answers
        _ = response.area_scores
        session.expunge_all()
        return response


def delete_response(response_id: int) -> bool:
    with session_scope() as session:
        response = session.get(Response, response_id)
        if response is None:
            return False
        session.delete(response)
        return True


def all_responses_for_export() -> list[Response]:
    with session_scope() as session:
        stmt = select(Response).order_by(Response.created_at.desc())
        rows = session.scalars(stmt).all()
        for row in rows:
            _ = row.area_scores
        session.expunge_all()
        return rows


# --------------------------------------------------------------------------- #
# Analytics
# --------------------------------------------------------------------------- #
def analytics_summary(days: int = 30) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=days)

    with session_scope() as session:
        total = session.scalar(select(func.count(Response.id))) or 0
        recent = (
            session.scalar(
                select(func.count(Response.id)).where(Response.created_at >= since)
            )
            or 0
        )

        # Average score per area.
        area_rows = session.execute(
            select(
                ResponseAreaScore.area_slug,
                ResponseAreaScore.area_name,
                func.avg(ResponseAreaScore.score),
            ).group_by(ResponseAreaScore.area_slug, ResponseAreaScore.area_name)
        ).all()
        area_averages = [
            {"slug": slug, "name": name, "avg": round(float(avg), 2)}
            for slug, name, avg in area_rows
        ]

        # Responses per day within the window.
        day_rows = session.execute(
            select(
                func.date(Response.created_at).label("day"),
                func.count(Response.id),
            )
            .where(Response.created_at >= since)
            .group_by("day")
            .order_by("day")
        ).all()
        daily = [{"day": str(day), "count": int(count)} for day, count in day_rows]

        # Funnel from events.
        funnel_rows = session.execute(
            select(Event.type, func.count(Event.id)).group_by(Event.type)
        ).all()
        funnel = {etype: int(count) for etype, count in funnel_rows}

        starts = funnel.get("start_test", 0)
        completes = funnel.get("complete", 0)
        completion_rate = round(100 * completes / starts, 1) if starts else 0.0

        return {
            "total": total,
            "recent": recent,
            "days": days,
            "area_averages": area_averages,
            "daily": daily,
            "funnel": funnel,
            "completion_rate": completion_rate,
        }
