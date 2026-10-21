import pytest
from fastapi.testclient import TestClient

from app.config import get_settings


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch, tmp_path):
    """Give every test a clean settings cache and a throwaway database file.

    Prevents a developer's local backend/.env or qsb.db from leaking into tests.
    """
    monkeypatch.chdir(tmp_path)  # .env lookup is relative to CWD, so none is found
    monkeypatch.setenv("QSB_ENVIRONMENT", "test")
    monkeypatch.setenv("QSB_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client():
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def database(tmp_path):
    from app.db.database import Database

    db = Database(f"sqlite:///{tmp_path / 'service.db'}")
    db.create_all()
    yield db
    db.dispose()


@pytest.fixture
def db(database):
    with database.session() as session:
        yield session
