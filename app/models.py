"""ORM models.

Design goals:

* **Editable content** — questions, answer options, areas and all bot texts
  live in tables, so the dashboard can change them without touching code.
* **Rich responses** — every individual answer is stored (not just the area
  averages), which keeps analytics and re-scoring flexible.
* **Auditable funnel** — lightweight ``Event`` rows let the dashboard show a
  start → consent → complete funnel.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Setting(Base):
    """Key/value store for scalar bot configuration and all UI texts."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # "text" | "int" | "bool" | "secret" — drives rendering in the dashboard.
    value_type: Mapped[str] = mapped_column(String(16), default="text")
    label: Mapped[str] = mapped_column(String(200), default="")
    group: Mapped[str] = mapped_column(String(64), default="general")
    description: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class Area(Base):
    """A scoring dimension (e.g. financial control / security / growth)."""

    __tablename__ = "areas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    order: Mapped[int] = mapped_column(Integer, default=0)

    questions: Mapped[list["Question"]] = relationship(
        back_populates="area", cascade="all, delete-orphan"
    )


class Question(Base):
    """A single quiz statement belonging to an area."""

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    area_id: Mapped[int] = mapped_column(ForeignKey("areas.id"))
    text: Mapped[str] = mapped_column(Text)
    order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    area: Mapped[Area] = relationship(back_populates="questions")


class AnswerOption(Base):
    """A selectable answer with an associated score (shared by all questions)."""

    __tablename__ = "answer_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(120))
    score: Mapped[int] = mapped_column(Integer)
    order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Response(Base):
    """A completed test submission."""

    __tablename__ = "responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(120))
    first_name: Mapped[str] = mapped_column(String(120))
    last_name: Mapped[str] = mapped_column(String(120))
    phone_number: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )

    answers: Mapped[list["ResponseAnswer"]] = relationship(
        back_populates="response", cascade="all, delete-orphan"
    )
    area_scores: Mapped[list["ResponseAreaScore"]] = relationship(
        back_populates="response", cascade="all, delete-orphan"
    )


class ResponseAnswer(Base):
    """One answered question inside a response (kept for full analytics)."""

    __tablename__ = "response_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    response_id: Mapped[int] = mapped_column(
        ForeignKey("responses.id", ondelete="CASCADE")
    )
    question_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("questions.id", ondelete="SET NULL")
    )
    area_slug: Mapped[str] = mapped_column(String(64))
    question_text: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(String(120))
    score: Mapped[int] = mapped_column(Integer)

    response: Mapped[Response] = relationship(back_populates="answers")


class ResponseAreaScore(Base):
    """Denormalised per-area average for a response (fast dashboard reads)."""

    __tablename__ = "response_area_scores"
    __table_args__ = (
        UniqueConstraint("response_id", "area_slug", name="uq_response_area"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    response_id: Mapped[int] = mapped_column(
        ForeignKey("responses.id", ondelete="CASCADE")
    )
    area_slug: Mapped[str] = mapped_column(String(64))
    area_name: Mapped[str] = mapped_column(String(120))
    score: Mapped[float] = mapped_column(Float)

    response: Mapped[Response] = relationship(back_populates="area_scores")


class CompletionFile(Base):
    """Something sent to the user after finishing the test. Multiple allowed.

    Each item is one of two kinds:

    * an **uploaded file** — ``path`` points at a local file (≤50 MB Bot API cap);
    * a **channel message** — ``source_message_id`` references a message in the
      configured channel (video, voice, anything), which the bot copies or
      forwards. This bypasses the upload limit entirely, so large videos work.
    """

    __tablename__ = "completion_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    path: Mapped[str] = mapped_column(Text, default="")
    original_name: Mapped[str] = mapped_column(String(200), default="")
    caption: Mapped[str] = mapped_column(Text, default="")
    # Channel-message items: id of the source message + how to deliver it.
    source_message_id: Mapped[Optional[int]] = mapped_column(Integer)
    send_mode: Mapped[str] = mapped_column(String(16), default="copy")  # copy | forward
    order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Event(Base):
    """Lightweight funnel event: start_test / consent / complete."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    telegram_user_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
