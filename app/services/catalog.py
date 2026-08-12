"""CRUD for the editable quiz catalog: areas, questions, answer options.

Used by the dashboard. Reads return detached ORM objects (session expunged) so
templates can access attributes safely after the session closes.
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.database import session_scope
from app.models import AnswerOption, Area, Question


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
def get_catalog() -> dict:
    """Everything the questions page needs, detached from the session."""
    with session_scope() as session:
        areas = session.scalars(select(Area).order_by(Area.order, Area.id)).all()
        questions = session.scalars(
            select(Question).order_by(Question.order, Question.id)
        ).all()
        options = session.scalars(
            select(AnswerOption).order_by(AnswerOption.order, AnswerOption.id)
        ).all()
        # Touch relationships / expunge before the session closes.
        area_by_id = {a.id: a for a in areas}
        grouped = {a.id: [] for a in areas}
        for q in questions:
            grouped.setdefault(q.area_id, []).append(q)
        session.expunge_all()
        return {
            "areas": areas,
            "questions": questions,
            "options": options,
            "grouped": grouped,
            "area_by_id": area_by_id,
        }


# --------------------------------------------------------------------------- #
# Areas
# --------------------------------------------------------------------------- #
def create_area(slug: str, name: str) -> None:
    with session_scope() as session:
        max_order = session.scalar(select(func.max(Area.order))) or 0
        session.add(Area(slug=slug.strip(), name=name.strip(), order=max_order + 1))


def delete_area(area_id: int) -> None:
    with session_scope() as session:
        area = session.get(Area, area_id)
        if area is not None:
            session.delete(area)  # cascades to its questions


# --------------------------------------------------------------------------- #
# Questions
# --------------------------------------------------------------------------- #
def create_question(area_id: int, text: str) -> None:
    with session_scope() as session:
        max_order = session.scalar(select(func.max(Question.order))) or 0
        session.add(
            Question(
                area_id=area_id,
                text=text.strip(),
                order=max_order + 1,
                is_active=True,
            )
        )


def update_question(
    question_id: int,
    *,
    text: str,
    area_id: int,
    is_active: bool,
) -> None:
    with session_scope() as session:
        q = session.get(Question, question_id)
        if q is None:
            return
        q.text = text.strip()
        q.area_id = area_id
        q.is_active = is_active


def delete_question(question_id: int) -> None:
    with session_scope() as session:
        q = session.get(Question, question_id)
        if q is not None:
            session.delete(q)


def move_question(question_id: int, direction: int) -> None:
    """Swap order with the adjacent question (direction: -1 up, +1 down)."""
    with session_scope() as session:
        current = session.get(Question, question_id)
        if current is None:
            return
        ordered = session.scalars(
            select(Question).order_by(Question.order, Question.id)
        ).all()
        ids = [q.id for q in ordered]
        idx = ids.index(question_id)
        swap = idx + direction
        if 0 <= swap < len(ordered):
            other = ordered[swap]
            current.order, other.order = other.order, current.order


# --------------------------------------------------------------------------- #
# Answer options
# --------------------------------------------------------------------------- #
def create_option(label: str, score: int) -> None:
    with session_scope() as session:
        max_order = session.scalar(select(func.max(AnswerOption.order))) or 0
        session.add(
            AnswerOption(
                label=label.strip(),
                score=score,
                order=max_order + 1,
                is_active=True,
            )
        )


def update_option(option_id: int, *, label: str, score: int, is_active: bool) -> None:
    with session_scope() as session:
        opt = session.get(AnswerOption, option_id)
        if opt is None:
            return
        opt.label = label.strip()
        opt.score = score
        opt.is_active = is_active


def delete_option(option_id: int) -> None:
    with session_scope() as session:
        opt = session.get(AnswerOption, option_id)
        if opt is not None:
            session.delete(opt)
