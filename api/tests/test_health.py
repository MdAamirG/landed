from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.db import engine, get_db
from app.main import app


def test_health_reports_api_and_database_up(api_client):
    response = api_client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "reachable"}


def test_health_reports_503_when_the_database_cannot_be_reached(api_client):
    # Nothing listens on port 1, so this is a real refused connection, not a fake error.
    dead_engine = create_engine("postgresql+psycopg://user:pass@127.0.0.1:1/nothing")

    def unreachable_db():
        with Session(dead_engine) as session:
            yield session

    app.dependency_overrides[get_db] = unreachable_db

    response = api_client.get("/api/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unreachable"}


def test_ping_answers_without_opening_a_database_connection(api_client):
    # An uptime monitor calls this, and any query would stop Neon suspending when idle.
    checkouts = []

    def record_checkout(*_):
        checkouts.append(1)

    event.listen(engine, "checkout", record_checkout)
    try:
        response = api_client.get("/api/ping")
        checkouts_during_ping = len(checkouts)
        api_client.get("/api/health")  # The control: proves this counter sees a real connection.
    finally:
        event.remove(engine, "checkout", record_checkout)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert checkouts_during_ping == 0
    assert len(checkouts) > 0
