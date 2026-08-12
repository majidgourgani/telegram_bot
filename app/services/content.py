"""Read/write access to editable bot content and settings.

Everything the bot renders at runtime comes through here, so a change made in
the dashboard is reflected on the next interaction with no redeploy.

Functions return plain dicts (not ORM objects) so callers in async bot handlers
never touch a live session or hit lazy-loading / detachment issues.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.database import session_scope
from app.models import AnswerOption, Area, Question, Setting

_TRUE = {"1", "true", "yes", "on"}


def _coerce(value: str, value_type: str) -> Any:
    if value_type == "int":
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    if value_type == "bool":
        return str(value).strip().lower() in _TRUE
    return value


def get_settings_dict() -> dict[str, Any]:
    """All settings as a ``{key: coerced_value}`` mapping."""
    with session_scope() as session:
        rows = session.scalars(select(Setting)).all()
        return {row.key: _coerce(row.value, row.value_type) for row in rows}


def get_setting(key: str, default: Any = None) -> Any:
    with session_scope() as session:
        row = session.get(Setting, key)
        if row is None:
            return default
        return _coerce(row.value, row.value_type)


def set_setting(key: str, value: Any) -> None:
    with session_scope() as session:
        row = session.get(Setting, key)
        if row is None:
            row = Setting(key=key, value=str(value))
            session.add(row)
        else:
            row.value = "" if value is None else str(value)


def get_areas() -> list[dict[str, Any]]:
    with session_scope() as session:
        areas = session.scalars(select(Area).order_by(Area.order, Area.id)).all()
        return [{"id": a.id, "slug": a.slug, "name": a.name} for a in areas]


def get_active_questions() -> list[dict[str, Any]]:
    """Active questions in display order, each with its area slug/name."""
    with session_scope() as session:
        stmt = (
            select(Question)
            .join(Area)
            .where(Question.is_active.is_(True))
            .order_by(Question.order, Question.id)
        )
        questions = session.scalars(stmt).all()
        return [
            {
                "id": q.id,
                "text": q.text,
                "area_slug": q.area.slug,
                "area_name": q.area.name,
            }
            for q in questions
        ]


def get_answer_options() -> list[dict[str, Any]]:
    with session_scope() as session:
        stmt = (
            select(AnswerOption)
            .where(AnswerOption.is_active.is_(True))
            .order_by(AnswerOption.order, AnswerOption.id)
        )
        options = session.scalars(stmt).all()
        return [{"label": o.label, "score": o.score} for o in options]


def get_settings_grouped() -> dict[str, list[dict[str, Any]]]:
    """All settings with their metadata, grouped for the settings page."""
    with session_scope() as session:
        rows = session.scalars(
            select(Setting).order_by(Setting.group, Setting.label, Setting.key)
        ).all()
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            groups.setdefault(row.group, []).append(
                {
                    "key": row.key,
                    "value": row.value,
                    "value_type": row.value_type,
                    "label": row.label or row.key,
                    "description": row.description,
                }
            )
        return groups


def update_settings(values: dict[str, Any], bool_keys: set[str]) -> None:
    """Bulk-update settings from a submitted form.

    ``bool_keys`` lists every boolean setting rendered on the form, so unchecked
    checkboxes (absent from the payload) are correctly stored as ``false``.
    """
    with session_scope() as session:
        rows = {r.key: r for r in session.scalars(select(Setting)).all()}
        for key in bool_keys:
            row = rows.get(key)
            if row is not None:
                row.value = "true" if key in values else "false"
        for key, value in values.items():
            row = rows.get(key)
            if row is None or row.value_type == "bool":
                continue
            row.value = "" if value is None else str(value)


def build_quiz_snapshot() -> dict[str, Any]:
    """A self-contained snapshot of the quiz for one test run.

    Captured when a user starts the questions so that edits made mid-test do
    not corrupt an in-progress session.
    """
    return {
        "questions": get_active_questions(),
        "options": get_answer_options(),
        "areas": get_areas(),
    }
