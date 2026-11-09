"""Client POD links (story 77, spec assumption 14), through the HTTP API."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from sqlalchemy import select

from app.auth import SESSION_COOKIE, make_session_token
from app.client_links import AUDIENCE
from app.config import settings
from app.models import AuditEvent, Role
from tests.factories import make_attempt, make_trip, make_user

PASSWORD = "correct horse battery"


def days_ago(days: float) -> datetime:
    return datetime.now(UTC) - timedelta(days=days)


@pytest.fixture
def office_user(api_client, db):
    user = make_user(db, Role.OPERATIONS_HEAD, password=PASSWORD)
    api_client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    return user


def delivered(db, delivered_days_ago: float = 1, **trip_values):
    """A trip with its first photo taken some days ago, which sets its delivery time."""
    trip = make_trip(db, **({"pod_status": "verified"} | trip_values))
    when = days_ago(delivered_days_ago)
    make_attempt(db, trip, captured_at=when, received_at=when)
    return trip


def make_link(client, client_id) -> str:
    """Makes a link through the API, then signs out, so what follows is only the client."""
    response = client.post("/api/client-links", json={"client_id": str(client_id)})
    assert response.status_code == 201
    client.cookies.clear()
    return response.json()["url"].rsplit("/c/", 1)[1]


def as_client(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def signed(claims: dict, secret: str | None = None) -> str:
    return jwt.encode(claims, secret or settings.session_secret, algorithm="HS256")


@pytest.mark.usefixtures("office_user")
def test_a_link_lasts_7_days_and_points_at_the_client_page(api_client, db):
    trip = make_trip(db)

    response = api_client.post("/api/client-links", json={"client_id": str(trip.client_id)})

    assert response.status_code == 201
    body = response.json()
    assert body["url"].startswith(f"{settings.web_origin}/c/")
    expires_at = datetime.fromisoformat(body["expires_at"])
    assert abs(expires_at - (datetime.now(UTC) + timedelta(days=7))) < timedelta(minutes=1)


def test_each_link_made_is_logged_without_its_token(api_client, db, office_user):
    trip = make_trip(db)

    token = make_link(api_client, trip.client_id)

    events = db.scalars(
        select(AuditEvent).where(
            AuditEvent.action == "client_link_created", AuditEvent.actor_id == office_user.id
        )
    ).all()
    assert len(events) == 1
    assert events[0].trip_id is None
    assert events[0].detail["client_id"] == str(trip.client_id)
    assert token not in str(events[0].detail)


@pytest.mark.usefixtures("office_user")
def test_a_link_for_an_unknown_client_is_refused(api_client):
    response = api_client.post("/api/client-links", json={"client_id": str(uuid4())})

    assert response.status_code == 404


@pytest.mark.usefixtures("office_user")
def test_the_office_can_list_clients_to_make_a_link_for(api_client, db):
    trip = make_trip(db)

    response = api_client.get("/api/client-links/clients")

    assert response.status_code == 200
    assert str(trip.client_id) in {client["id"] for client in response.json()}


@pytest.mark.usefixtures("office_user")
def test_the_page_shows_only_that_clients_accepted_pods_newest_first(api_client, db):
    older = delivered(db, delivered_days_ago=3)
    client_id = older.client_id
    newer = delivered(db, delivered_days_ago=1, client_id=client_id, pod_status="invoiced")
    delivered(db, client_id=client_id, pod_status="needs_review")
    delivered(db, client_id=client_id, pod_status="disputed")
    make_trip(db, client_id=client_id)  # Still waiting for a photo.
    delivered(db)  # Another client's.
    token = make_link(api_client, client_id)

    response = api_client.get("/api/client-pods", headers=as_client(token))

    assert response.status_code == 200
    body = response.json()
    assert [pod["trip_code"] for pod in body["pods"]] == [newer.trip_code, older.trip_code]
    assert [pod["invoiced"] for pod in body["pods"]] == [True, False]


@pytest.mark.usefixtures("office_user")
def test_the_consignee_is_masked_and_no_phone_is_sent(api_client, db):
    trip = delivered(db, consignee_name="Sample Consignee Nagpur")
    token = make_link(api_client, trip.client_id)

    pod = api_client.get("/api/client-pods", headers=as_client(token)).json()["pods"][0]

    assert pod["consignee_name"] == "S. C. N."
    assert "Sample Consignee" not in str(pod)
    assert trip.consignee_phone not in str(pod)


@pytest.mark.usefixtures("office_user")
def test_a_client_with_no_accepted_pods_gets_an_empty_list(api_client, db):
    trip = make_trip(db)
    token = make_link(api_client, trip.client_id)

    response = api_client.get("/api/client-pods", headers=as_client(token))

    assert response.status_code == 200
    assert response.json()["pods"] == []


@pytest.mark.usefixtures("office_user")
def test_the_client_can_open_its_own_pod_photo(api_client, db):
    trip = delivered(db)
    token = make_link(api_client, trip.client_id)

    response = api_client.get(f"/api/client-pods/trips/{trip.id}/photo", headers=as_client(token))

    assert response.status_code == 200
    assert response.content.startswith(b"\xff\xd8\xff")
    assert "private" in response.headers["cache-control"]


@pytest.mark.usefixtures("office_user")
def test_another_clients_photo_or_one_not_yet_accepted_is_not_found(api_client, db):
    trip = delivered(db)
    in_review = delivered(db, client_id=trip.client_id, pod_status="needs_review")
    someone_else = delivered(db)
    token = make_link(api_client, trip.client_id)

    for other in (in_review, someone_else):
        url = f"/api/client-pods/trips/{other.id}/photo"
        assert api_client.get(url, headers=as_client(token)).status_code == 404


@pytest.mark.usefixtures("office_user")
def test_the_link_opens_nothing_that_writes(api_client, db):
    trip = delivered(db)
    token = make_link(api_client, trip.client_id)

    for method in ("POST", "PUT", "PATCH", "DELETE"):
        response = api_client.request(method, "/api/client-pods", headers=as_client(token))
        assert response.status_code == 405


def test_an_expired_link_is_refused(api_client, db):
    trip = make_trip(db)
    claims = {"sub": str(trip.client_id), "aud": AUDIENCE, "exp": days_ago(1)}

    response = api_client.get("/api/client-pods", headers=as_client(signed(claims)))

    assert response.status_code == 401


@pytest.mark.usefixtures("office_user")
def test_a_tampered_link_is_refused(api_client, db):
    trip = make_trip(db)
    token = make_link(api_client, trip.client_id)
    header, payload, signature = token.split(".")
    flipped = signature[:-2] + ("AA" if signature[-2:] != "AA" else "BB")

    response = api_client.get("/api/client-pods", headers=as_client(f"{header}.{payload}.{flipped}"))

    assert response.status_code == 401


def test_a_link_pointed_at_another_client_without_the_secret_is_refused(api_client, db):
    trip = make_trip(db)
    claims = {"sub": str(trip.client_id), "aud": AUDIENCE, "exp": days_ago(-1)}

    forged = signed(claims, secret="not the server's secret, but long enough to sign")
    response = api_client.get("/api/client-pods", headers=as_client(forged))

    assert response.status_code == 401


def test_an_unsigned_link_is_refused(api_client, db):
    trip = make_trip(db)
    claims = {"sub": str(trip.client_id), "aud": AUDIENCE, "exp": days_ago(-1)}
    unsigned = jwt.encode(claims, None, algorithm="none")

    assert api_client.get("/api/client-pods", headers=as_client(unsigned)).status_code == 401


def test_an_office_session_token_is_not_a_client_link(api_client, db):
    user = make_user(db, Role.OPERATIONS_HEAD)

    response = api_client.get("/api/client-pods", headers=as_client(make_session_token(user)))

    assert response.status_code == 401


@pytest.mark.usefixtures("office_user")
def test_a_client_link_is_not_an_office_session(api_client, db):
    trip = make_trip(db)
    token = make_link(api_client, trip.client_id)
    api_client.cookies.set(SESSION_COOKIE, token)

    assert api_client.get("/api/auth/me").status_code == 401
