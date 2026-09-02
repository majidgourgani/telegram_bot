"""Broadcast audience tracking, queueing and progress.

The dashboard *creates* broadcasts (status ``pending``); the bot process
*sends* them and records progress. Both talk to the same tables through here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

from app.database import session_scope
from app.models import Broadcast, BotUser, Event, Response


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Audience tracking (called by the bot)
# --------------------------------------------------------------------------- #
def upsert_bot_user(user_id: int, username: str | None, first_name: str | None) -> None:
    """Record/refresh a user who interacted with the bot."""
    if not user_id:
        return
    with session_scope() as session:
        row = session.get(BotUser, user_id)
        if row is None:
            session.add(
                BotUser(
                    telegram_user_id=user_id,
                    username=username,
                    first_name=first_name,
                    is_blocked=False,
                )
            )
        else:
            row.username = username
            row.first_name = first_name
            row.last_seen = _utcnow()
            # A message from the user means they haven't blocked us.
            row.is_blocked = False


def backfill_bot_users() -> int:
    """Populate ``bot_users`` from historical responses/events (idempotent).

    Ensures users who interacted before this feature existed are still
    reachable. Returns the number of new rows inserted.
    """
    with session_scope() as session:
        existing = set(session.scalars(select(BotUser.telegram_user_id)).all())

        historical: set[int] = set()
        for source in (Response.telegram_user_id, Event.telegram_user_id):
            ids = session.scalars(select(source).where(source.is_not(None)).distinct()).all()
            historical.update(uid for uid in ids if uid)

        # Prefer username/first_name from the latest response if available.
        names: dict[int, tuple[str | None, str | None]] = {}
        rows = session.execute(
            select(
                Response.telegram_user_id,
                Response.telegram_username,
                Response.first_name,
            ).where(Response.telegram_user_id.is_not(None))
        ).all()
        for uid, uname, fname in rows:
            names.setdefault(uid, (uname, fname))

        inserted = 0
        for uid in historical - existing:
            uname, fname = names.get(uid, (None, None))
            session.add(
                BotUser(telegram_user_id=uid, username=uname, first_name=fname, is_blocked=False)
            )
            inserted += 1
        return inserted


def mark_blocked(user_id: int) -> None:
    with session_scope() as session:
        row = session.get(BotUser, user_id)
        if row is not None:
            row.is_blocked = True


# --------------------------------------------------------------------------- #
# Recipients
# --------------------------------------------------------------------------- #
def _blocked_ids(session) -> set[int]:
    rows = session.scalars(
        select(BotUser.telegram_user_id).where(BotUser.is_blocked.is_(True))
    ).all()
    return set(rows)


def resolve_recipient_ids(target: str) -> list[int]:
    """Distinct, reachable (non-blocked) user ids for the given audience."""
    with session_scope() as session:
        blocked = _blocked_ids(session)
        if target == "completed":
            rows = session.scalars(
                select(Response.telegram_user_id)
                .where(Response.telegram_user_id.is_not(None))
                .distinct()
            ).all()
        else:  # "all"
            rows = session.scalars(
                select(BotUser.telegram_user_id).where(BotUser.is_blocked.is_(False))
            ).all()
        return sorted({uid for uid in rows if uid and uid not in blocked})


def count_recipients(target: str) -> int:
    return len(resolve_recipient_ids(target))


def audience_counts() -> dict[str, int]:
    with session_scope() as session:
        total_users = session.scalar(select(func.count(BotUser.telegram_user_id))) or 0
        blocked = session.scalar(
            select(func.count(BotUser.telegram_user_id)).where(BotUser.is_blocked.is_(True))
        ) or 0
        completed = session.scalar(
            select(func.count(func.distinct(Response.telegram_user_id))).where(
                Response.telegram_user_id.is_not(None)
            )
        ) or 0
    return {
        "all": max(total_users - blocked, 0),
        "completed": completed,
        "blocked": blocked,
    }


# --------------------------------------------------------------------------- #
# Queue lifecycle
# --------------------------------------------------------------------------- #
def create_broadcast(
    *,
    message: str,
    target: str,
    add_button: bool,
    button_text: str,
    created_by: str,
) -> int:
    with session_scope() as session:
        row = Broadcast(
            message=message,
            target="completed" if target == "completed" else "all",
            add_button=add_button,
            button_text=button_text.strip(),
            status="pending",
            created_by=created_by,
        )
        session.add(row)
        session.flush()
        return row.id


def _to_dict(row: Broadcast) -> dict[str, Any]:
    return {
        "id": row.id,
        "message": row.message,
        "target": row.target,
        "add_button": row.add_button,
        "button_text": row.button_text,
        "status": row.status,
        "total": row.total,
        "sent": row.sent,
        "failed": row.failed,
        "created_by": row.created_by,
        "created_at": row.created_at,
        "started_at": row.started_at,
        "finished_at": row.finished_at,
    }


def fetch_next_pending() -> dict[str, Any] | None:
    """Claim the oldest pending broadcast, flipping it to ``sending``."""
    with session_scope() as session:
        row = session.scalars(
            select(Broadcast)
            .where(Broadcast.status == "pending")
            .order_by(Broadcast.created_at)
            .limit(1)
        ).first()
        if row is None:
            return None
        row.status = "sending"
        row.started_at = _utcnow()
        session.flush()
        return _to_dict(row)


def set_total(broadcast_id: int, total: int) -> None:
    with session_scope() as session:
        row = session.get(Broadcast, broadcast_id)
        if row is not None:
            row.total = total


def update_progress(broadcast_id: int, sent: int, failed: int) -> None:
    with session_scope() as session:
        row = session.get(Broadcast, broadcast_id)
        if row is not None:
            row.sent = sent
            row.failed = failed


def finish(broadcast_id: int, sent: int, failed: int) -> None:
    with session_scope() as session:
        row = session.get(Broadcast, broadcast_id)
        if row is not None:
            row.sent = sent
            row.failed = failed
            row.status = "done"
            row.finished_at = _utcnow()


def list_broadcasts(limit: int = 30) -> list[dict[str, Any]]:
    with session_scope() as session:
        rows = session.scalars(
            select(Broadcast).order_by(Broadcast.created_at.desc()).limit(limit)
        ).all()
        return [_to_dict(r) for r in rows]


def requeue_stuck_sending() -> None:
    """On bot startup, reset any broadcast left mid-send by a previous run."""
    with session_scope() as session:
        rows = session.scalars(
            select(Broadcast).where(Broadcast.status == "sending")
        ).all()
        for row in rows:
            row.status = "pending"
            row.started_at = None
