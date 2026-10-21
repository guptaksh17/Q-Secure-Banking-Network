"""Database engine/session management (SQLite by default; PostgreSQL via QSB_DATABASE_URL).

One ``Database`` per FastAPI app (stored on ``app.state.db``) so tests can point each
app at its own throwaway file. Tables are created with ``create_all`` at startup; a
migration tool (Alembic) would be the next step for a long-lived deployment.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


FICTIONAL_BANKS = [
    {"code": "bank_a", "name": "Qubit Savings Bank (fictional)", "account_prefix": "QSB-A-"},
    {"code": "bank_b", "name": "Photon Trust Bank (fictional)", "account_prefix": "QSB-B-"},
]


class Database:
    def __init__(self, url: str):
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, connect_args=connect_args)
        if url.startswith("sqlite"):
            @event.listens_for(self.engine, "connect")
            def _sqlite_pragmas(dbapi_conn, _record):
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.close()
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_all(self) -> None:
        from app.db import models  # noqa: F401  (register mappers)

        Base.metadata.create_all(self.engine)
        with self.session() as db:
            seed_banks(db)

    @contextmanager
    def session(self) -> Iterator[Session]:
        db = self.SessionLocal()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def dispose(self) -> None:
        self.engine.dispose()


def seed_banks(db: Session) -> None:
    from app.db.models import Bank

    existing = set(db.scalars(select(Bank.code)))
    for bank in FICTIONAL_BANKS:
        if bank["code"] not in existing:
            db.add(Bank(**bank))
    db.flush()
