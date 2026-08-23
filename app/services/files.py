"""CRUD for completion files (the files sent to users after the test).

Reads return plain dicts so the bot can use them without a live session.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from app.database import session_scope
from app.models import CompletionFile


def _to_dict(row: CompletionFile) -> dict[str, Any]:
    return {
        "id": row.id,
        "path": row.path,
        "original_name": row.original_name,
        "caption": row.caption,
        "source_message_id": row.source_message_id,
        "send_mode": row.send_mode or "copy",
        "is_channel": row.source_message_id is not None,
        "order": row.order,
        "is_active": row.is_active,
    }


def list_completion_files(active_only: bool = False) -> list[dict[str, Any]]:
    with session_scope() as session:
        stmt = select(CompletionFile).order_by(CompletionFile.order, CompletionFile.id)
        if active_only:
            stmt = stmt.where(CompletionFile.is_active.is_(True))
        return [_to_dict(r) for r in session.scalars(stmt).all()]


def add_completion_file(path: str, original_name: str = "", caption: str = "") -> None:
    with session_scope() as session:
        max_order = session.scalar(select(func.max(CompletionFile.order))) or 0
        session.add(
            CompletionFile(
                path=path,
                original_name=original_name,
                caption=caption.strip(),
                order=max_order + 1,
                is_active=True,
            )
        )


def add_channel_message(
    message_id: int, send_mode: str = "copy", caption: str = ""
) -> None:
    """Register a channel message (video/voice/…) to be sent on completion."""
    mode = "forward" if send_mode == "forward" else "copy"
    with session_scope() as session:
        max_order = session.scalar(select(func.max(CompletionFile.order))) or 0
        session.add(
            CompletionFile(
                path="",
                original_name=f"Channel message #{message_id}",
                caption=caption.strip(),
                source_message_id=message_id,
                send_mode=mode,
                order=max_order + 1,
                is_active=True,
            )
        )


def update_completion_file(file_id: int, *, caption: str, is_active: bool) -> None:
    with session_scope() as session:
        row = session.get(CompletionFile, file_id)
        if row is None:
            return
        row.caption = caption.strip()
        row.is_active = is_active


def delete_completion_file(file_id: int) -> None:
    with session_scope() as session:
        row = session.get(CompletionFile, file_id)
        if row is not None:
            session.delete(row)


def move_completion_file(file_id: int, direction: int) -> None:
    """Swap order with the adjacent file (direction: -1 up, +1 down)."""
    with session_scope() as session:
        rows = session.scalars(
            select(CompletionFile).order_by(CompletionFile.order, CompletionFile.id)
        ).all()
        ids = [r.id for r in rows]
        if file_id not in ids:
            return
        idx = ids.index(file_id)
        swap = idx + direction
        if 0 <= swap < len(rows):
            rows[idx].order, rows[swap].order = rows[swap].order, rows[idx].order
