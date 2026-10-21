from collections.abc import Iterator
from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy.orm import Session


def get_db(request: Request) -> Iterator[Session]:
    """One unit of work per request: commit on success, roll back on error."""
    with request.app.state.db.session() as db:
        yield db


def iso(dt: datetime | None) -> str | None:
    """SQLite drops tzinfo; every stored timestamp is UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")
