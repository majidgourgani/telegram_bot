"""One-off importer for a legacy ``users.csv`` into the database.

Usage:
    python -m scripts.migrate_csv path/to/users.csv

The legacy schema was:
    first_name, last_name, phone_number,
    control_score, security_score, growth_score, collected_at_utc

Area scores are imported as ``ResponseAreaScore`` rows (individual answers are
not available in the old CSV, so those are left empty).
"""

from __future__ import annotations

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.database import init_db, session_scope
from app.models import Response, ResponseAreaScore

_AREA_MAP = [
    ("control", "کنترل مالی", "control_score"),
    ("security", "امنیت مالی", "security_score"),
    ("growth", "رشد مالی", "growth_score"),
]


def _parse_dt(raw: str) -> datetime:
    try:
        return datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


def migrate(csv_path: Path) -> int:
    init_db()
    imported = 0
    with csv_path.open(encoding="utf-8") as fh, session_scope() as session:
        for row in csv.DictReader(fh):
            response = Response(
                first_name=row.get("first_name", ""),
                last_name=row.get("last_name", ""),
                phone_number=row.get("phone_number", ""),
                created_at=_parse_dt(row.get("collected_at_utc", "")),
            )
            session.add(response)
            session.flush()
            for slug, name, column in _AREA_MAP:
                value = row.get(column)
                if value in (None, ""):
                    continue
                session.add(
                    ResponseAreaScore(
                        response_id=response.id,
                        area_slug=slug,
                        area_name=name,
                        score=float(value),
                    )
                )
            imported += 1
    return imported


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.migrate_csv path/to/users.csv")
        raise SystemExit(1)
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}")
        raise SystemExit(1)
    count = migrate(path)
    print(f"Imported {count} responses from {path}.")
