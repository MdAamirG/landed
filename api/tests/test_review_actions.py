"""The executive's other decisions: retake, dispute, resolve and pull back."""

import pytest
from sqlalchemy import select

from app.driver_links import create_link
from app.models import AuditEvent, DriverLink, Role, Trip
from tests.factories import clean_reading, make_trip, make_user
from tests.test_attempts import upload
from tests.test_review import PASSWORD, approve, audit, detail, trip_in_review


@pytest.fixture
def executive(api_client, db):
    user = make_user(db, Role.BILLING_EXECUTIVE, password=PASSWORD)
    api_client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    return user


def act(client, trip, action, version=None):
    version = detail(client, trip)["version"] if version is None else version
    return client.post(f"/api/review/trips/{trip.id}/{action}", json={"version": version})


def status_of(db, trip) -> str:
    db.expire_all()
    return db.get(Trip, trip.id).pod_status


def listed(client, trip, filter):
    codes = [item["trip_code"] for item in client.get(f"/api/review/queue?filter={filter}").json()]
    return trip.trip_code in codes


def test_asking_for_a_retake_texts_the_driver_and_counts(api_client, db, fake_ai, executive):
    trip = trip_in_review(api_client, db, fake_ai)

    response = act(api_client, trip, "retake")

    assert response.status_code == 200
    assert response.json()["pod_status"] == "retake_requested"
    assert response.json()["retakes_used"] == 1
    sent = audit(db, trip, "sms_sent")
    assert len(sent) == 1
    assert sent[0].actor_id == executive.id


def test_an_office_retake_renews_the_link(api_client, db, fake_ai, executive):
    trip = trip_in_review(api_client, db, fake_ai)
    link = db.scalar(select(DriverLink).where(DriverLink.trip_id == trip.id))
    old_expiry = link.expires_at

    act(api_client, trip, "retake")

    db.expire_all()
    assert db.get(DriverLink, link.id).expires_at != old_expiry


def test_the_driver_can_send_a_new_photo_after_an_office_retake(
    api_client, db, fake_ai, executive
):
    trip = make_trip(db)
    token = create_link(db, trip)
    db.commit()
    fake_ai.reading = clean_reading(
        trip, remarks={"text": "short", "kind": "shortage", "confidence": 0.9}
    )
    upload(api_client, token)
    act(api_client, trip, "retake")
    fake_ai.reading = clean_reading(trip)

    response = upload(api_client, token)

    assert response.json()["attempt_no"] == 2
    assert status_of(db, trip) == "verified"


def test_a_retake_past_the_cap_is_refused(api_client, db, fake_ai, executive):
    trip = trip_in_review(api_client, db, fake_ai, retakes_used=2)

    response = act(api_client, trip, "retake")

    assert response.status_code == 409
    assert status_of(db, trip) == "needs_review"
    assert audit(db, trip, "sms_sent") == []


def test_a_retake_on_a_stale_version_is_a_conflict(api_client, db, fake_ai, executive):
    trip = trip_in_review(api_client, db, fake_ai)

    assert act(api_client, trip, "retake", version=999).status_code == 409


@pytest.mark.parametrize("start", ["needs_review", "verified"])
def test_a_trip_can_be_marked_disputed(api_client, db, executive, start):
    trip = make_trip(db, pod_status=start)

    assert act(api_client, trip, "dispute").status_code == 200
    assert status_of(db, trip) == "disputed"
    assert audit(db, trip, "status_change")[0].actor_id == executive.id


@pytest.mark.parametrize("start", ["awaiting_pod", "checking", "retake_requested", "invoiced"])
def test_a_trip_in_any_other_status_cannot_be_disputed(api_client, db, executive, start):
    trip = make_trip(db, pod_status=start)

    assert act(api_client, trip, "dispute").status_code == 409
    assert status_of(db, trip) == start


def test_a_dispute_is_resolved_back_to_verified(api_client, db, fake_ai, executive):
    trip = trip_in_review(api_client, db, fake_ai)
    act(api_client, trip, "dispute")

    assert approve(api_client, trip).status_code == 200
    assert status_of(db, trip) == "verified"


def test_a_disputed_trip_can_be_corrected_before_resolving(api_client, db, fake_ai, executive):
    trip = trip_in_review(api_client, db, fake_ai)
    act(api_client, trip, "dispute")
    version = detail(api_client, trip)["version"]

    response = api_client.patch(
        f"/api/review/trips/{trip.id}/fields/lr_number", json={"value": "1", "version": version}
    )

    assert response.status_code == 200


def test_the_filters_list_each_status_on_its_own(api_client, db, executive):
    disputed = make_trip(db, pod_status="disputed")
    verified = make_trip(db, pod_status="verified")
    waiting = make_trip(db, pod_status="needs_review")

    assert listed(api_client, disputed, "disputed")
    assert not listed(api_client, disputed, "needs_review")
    assert listed(api_client, verified, "verified")
    assert not listed(api_client, verified, "disputed")
    assert listed(api_client, waiting, "needs_review")


def test_an_unknown_filter_is_refused(api_client, executive):
    assert api_client.get("/api/review/queue?filter=everything").status_code == 422


def test_pull_back_clears_who_verified_it(api_client, db, fake_ai, executive):
    trip = trip_in_review(api_client, db, fake_ai)
    approve(api_client, trip)

    assert act(api_client, trip, "pull-back").status_code == 200

    db.expire_all()
    trip = db.get(Trip, trip.id)
    assert trip.pod_status == "needs_review"
    assert trip.verified_at is None
    assert trip.verified_by is None


@pytest.mark.parametrize("action", ["pull-back", "dispute", "retake", "approve"])
def test_an_invoiced_trip_cannot_be_changed(api_client, db, executive, action):
    trip = make_trip(db, pod_status="invoiced")

    assert act(api_client, trip, action).status_code in (409, 422)
    assert status_of(db, trip) == "invoiced"
    assert audit(db, trip, "status_change") == []


def test_only_a_verified_trip_can_be_pulled_back(api_client, db, executive):
    trip = make_trip(db, pod_status="needs_review")

    assert act(api_client, trip, "pull-back").status_code == 409


def test_every_decision_is_in_the_audit_log(api_client, db, fake_ai, executive):
    trip = trip_in_review(api_client, db, fake_ai)
    act(api_client, trip, "dispute")
    approve(api_client, trip)
    act(api_client, trip, "pull-back")
    act(api_client, trip, "retake")

    db.expire_all()
    moves = db.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.trip_id == trip.id,
            AuditEvent.action == "status_change",
            AuditEvent.actor_id == executive.id,
        )
        .order_by(AuditEvent.id)
    ).all()
    assert [(event.from_status, event.to_status) for event in moves] == [
        ("needs_review", "disputed"),
        ("disputed", "verified"),
        ("verified", "needs_review"),
        ("needs_review", "retake_requested"),
    ]


def test_the_queue_flags_late_photos(api_client, db, fake_ai, executive):
    trip = make_trip(db)
    token = create_link(db, trip)
    db.commit()
    fake_ai.reading = clean_reading(trip)
    upload(api_client, token)
    upload(api_client, token)  # Late: the trip is already verified.

    items = api_client.get("/api/review/queue?filter=verified").json()
    item = next(row for row in items if row["trip_code"] == trip.trip_code)

    assert item["late_photos"] == 1
