"""Test harness: real Postgres on the Neon test branch, with safety checks first."""

import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]


def normalised_host(url: str) -> str | None:
    """Lower-case host, with Neon's -pooler suffix removed so both URLs of a branch compare equal."""
    host = urlsplit(url).hostname
    return host.lower().replace("-pooler.", ".") if host else None


def refusal_reason(test_url: str | None, app_urls: list[str | None]) -> str | None:
    """Why the suite must not run against test_url, or None if it's safe."""
    if not test_url:
        return "DATABASE_URL_TEST is not set. The tests empty tables, so they need the test branch."

    test_host = normalised_host(test_url)
    if test_host is None:
        return "DATABASE_URL_TEST has no host."

    if test_host in {normalised_host(url) for url in app_urls if url}:
        return "DATABASE_URL_TEST has the same host as the app's database. The tests empty tables."

    return None


def pytest_configure(config):
    load_dotenv(REPO_ROOT / ".env")  # Real environment variables win over .env.
    test_url = os.environ.get("DATABASE_URL_TEST")
    app_urls = [os.environ.get("DATABASE_URL"), os.environ.get("DATABASE_URL_POOLED")]

    reason = refusal_reason(test_url, app_urls)
    if reason:
        pytest.exit(reason, returncode=2)

    # From here on the app and Alembic can only see the test branch. App code is imported
    # after this point, because app.config reads these once at import.
    os.environ["DATABASE_URL"] = test_url
    os.environ["DATABASE_URL_POOLED"] = test_url


def empty_tables() -> None:
    """Remove every row. TRUNCATE ... CASCADE saves ordering the tables by foreign key."""
    from sqlalchemy import text

    from app.db import engine
    from app.models import Base

    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture(scope="session", autouse=True)
def test_database():
    """Each run brings the test branch up to the latest migration, then starts it empty."""
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(REPO_ROOT / "api" / "alembic.ini"), "head")
    empty_tables()


@pytest.fixture
def empty_db():
    """For tests that need exact row counts. Other tests' rows stay until the next run."""
    empty_tables()


@pytest.fixture
def db():
    """A session for tests. Factories commit; anything else is undone by the rollback."""
    from app.db import SessionLocal

    with SessionLocal() as session:
        yield session
        session.rollback()


@pytest.fixture
def api_client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
