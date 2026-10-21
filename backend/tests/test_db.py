from sqlalchemy import inspect, select

from app.db.database import Database, seed_banks
from app.db.models import Bank, ExperimentResult


def test_tables_created(database):
    assert set(inspect(database.engine).get_table_names()) == {
        "banks", "qkd_sessions", "transactions", "security_events", "experiment_results",
    }


def test_fictional_banks_seeded_idempotently(database, db):
    seed_banks(db)
    seed_banks(db)
    banks = db.scalars(select(Bank).order_by(Bank.code)).all()
    assert [b.code for b in banks] == ["bank_a", "bank_b"]
    assert all("(fictional)" in b.name for b in banks)


def test_create_all_twice_is_safe(tmp_path):
    d = Database(f"sqlite:///{tmp_path / 'x.db'}")
    d.create_all()
    d.create_all()
    with d.session() as db:
        assert len(db.scalars(select(Bank)).all()) == 2
    d.dispose()


def test_session_rolls_back_on_error(database):
    try:
        with database.session() as db:
            db.add(ExperimentResult(name="x", kind="channel_sweep", parameter="noise", config={}, points=[]))
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    with database.session() as db:
        assert db.scalars(select(ExperimentResult)).all() == []


def test_foreign_keys_enforced(database):
    import pytest
    from sqlalchemy.exc import IntegrityError

    from app.db.models import SecurityEvent
    with pytest.raises(IntegrityError):
        with database.session() as db:
            db.add(SecurityEvent(event_type="x", severity="info", message="m", transaction_id="missing"))
