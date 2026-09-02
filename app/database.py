"""SQLAlchemy engine, session factory and declarative base.

A single SQLite file is shared by the bot process and the web process (each
opens its own engine). SQLite is fine for this workload; switching to Postgres
later is just a ``DATABASE_URL`` change.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import BASE_DIR, settings


def _make_engine():
    url = settings.database_url
    connect_args = {}

    if url.startswith("sqlite"):
        # Ensure the parent directory for the sqlite file exists.
        # URL form: sqlite:///./data/app.db  ->  path after the last '///'
        raw_path = url.split("///", 1)[-1]
        db_path = Path(raw_path)
        if not db_path.is_absolute():
            db_path = BASE_DIR / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # Allow the connection to be shared across threads (uvicorn workers,
        # ptb's executor). We serialise writes at the app level.
        connect_args = {"check_same_thread": False}

    return create_engine(
        url,
        connect_args=connect_args,
        future=True,
    )


engine = _make_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
    future=True,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional session scope.

    Commits on success, rolls back on error, always closes.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _run_lightweight_migrations() -> None:
    """Add columns introduced after a table was first created.

    ``create_all`` only creates missing *tables*, never missing *columns*, so
    for SQLite we add them by hand. Idempotent.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    per_table = {
        "completion_files": {
            "source_message_id": "INTEGER",
            "send_mode": "VARCHAR(16) DEFAULT 'copy'",
        },
        "broadcasts": {
            "recipient_ids": "TEXT DEFAULT ''",
        },
    }

    with engine.begin() as conn:
        for table, additions in per_table.items():
            if table not in tables:
                continue
            existing = {col["name"] for col in inspector.get_columns(table)}
            for name, ddl in additions.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def init_db() -> None:
    """Create tables (idempotent), run migrations, and seed defaults."""
    # Import models so they are registered on ``Base.metadata``.
    from app import models  # noqa: F401
    from app.seed import seed_defaults

    Base.metadata.create_all(bind=engine)
    _run_lightweight_migrations()
    seed_defaults()
