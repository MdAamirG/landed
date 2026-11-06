"""Driver links, through the HTTP API. Each test makes its own trip and link."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.driver_links import create_link
from app.models import AuditEvent, Client, Driver, DriverLink, PodStatus, Vehicle
from tests.factories import make_trip


def linked_trip(db, **overrides):
    """A trip and the token for a new link to it."""
    trip = make_trip(db, **overrides)
    token = create_link(db, trip)
    db.commit()
    return trip, token


def open_link(client, token: str):
    return client.get("/api/driver/trip", headers={"Authorization": f"Bearer {token}"})


def link_row(db, trip) -> DriverLink:
    return db.scalar(select(DriverLink).where(DriverLink.trip_id == trip.id))


def test_a_link_opens_its_trip(api_client, db):
    trip, token = linked_trip(db, origin="Sambhajinagar", destination="Pune", lr_number="48207x")

    response = open_link(api_client, token)

    assert response.status_code == 200
    assert response.json() == {
        "trip_code": trip.trip_code,
        "registration_no": db.get(Vehicle, trip.vehicle_id).registration_no,
        "client_name": db.get(Client, trip.client_id).name,
        "origin": "Sambhajinagar",
        "destination": "Pune",
        "lr_number": "48207x",
        "eway_bill_no": trip.eway_bill_no,
        "pod_status": "awaiting_pod",
    }


def test_a_link_opens_only_its_own_trip(api_client, db):
    first_trip, first_token = linked_trip(db)
    second_trip, second_token = linked_trip(db)

    assert open_link(api_client, first_token).json()["trip_code"] == first_trip.trip_code
    assert open_link(api_client, second_token).json()["trip_code"] == second_trip.trip_code


@pytest.mark.parametrize("token", ["", "not-a-real-token", "a" * 43])
def test_a_bad_token_is_refused(api_client, token):
    assert open_link(api_client, token).status_code == 401


def test_the_hash_of_a_token_is_not_itself_a_token(api_client, db):
    # A database leak hands out hashes, and they must not open anything.
    trip, _token = linked_trip(db)

    assert open_link(api_client, link_row(db, trip).token_hash).status_code == 401


def test_an_expired_link_is_refused(api_client, db):
    trip, token = linked_trip(db)
    link_row(db, trip).expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    assert open_link(api_client, token).status_code == 401


def test_a_revoked_link_is_refused(api_client, db):
    trip, token = linked_trip(db)
    link_row(db, trip).revoked_at = datetime.now(UTC)
    db.commit()

    assert open_link(api_client, token).status_code == 401


def test_a_link_lasts_72_hours_past_expected_delivery(db):
    expected = datetime(2026, 11, 10, 6, 30, tzinfo=UTC)
    trip, _token = linked_trip(db, expected_delivery_at=expected)

    assert link_row(db, trip).expires_at == expected + timedelta(hours=72)


def test_only_a_hash_of_the_token_is_stored(db):
    trip, token = linked_trip(db)

    assert token not in link_row(db, trip).token_hash


def test_no_response_or_audit_event_carries_the_token(api_client, db):
    trip, token = linked_trip(db)

    response = open_link(api_client, token)
    events = db.scalars(select(AuditEvent).where(AuditEvent.trip_id == trip.id)).all()

    assert token not in response.text
    assert [event.action for event in events] == ["driver_link_created"]
    assert token not in str(events[0].detail)


def test_no_consignee_or_driver_contact_in_the_response(api_client, db):
    trip, token = linked_trip(
        db, consignee_name="Sample Consignee Gate", consignee_phone="9000000099"
    )

    response = open_link(api_client, token)

    assert "consignee" not in response.text.lower()
    assert "Sample Consignee Gate" not in response.text
    assert "9000000099" not in response.text
    assert db.get(Driver, trip.driver_id).phone not in response.text


@pytest.mark.parametrize("status", list(PodStatus))
def test_the_response_reports_the_trip_status(api_client, db, status):
    _trip, token = linked_trip(db, pod_status=status)

    assert open_link(api_client, token).json()["pod_status"] == status
