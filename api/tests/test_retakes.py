"""Retakes, late photos, stuck attempts and wrong clocks, through the HTTP API."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.db import SessionLocal
from app.driver_links import create_link
from app.models import AuditEvent, DriverLink, PodAttempt, PodField, Trip
from app.status import LINK_LIFETIME
from tests.factories import clean_reading, make_trip
from tests.test_attempts import JPEG, attempts_for, poll, reload_trip, upload


def linked_trip(db, **overrides):
    trip = make_trip(db, **overrides)
    token = create_link(db, trip)
    db.commit()
    return trip, token


def no_stamp(trip):
    return clean_reading(trip, consignee_stamp={"value": "absent", "confidence": 0.95})


def events(db, trip, action: str) -> list[AuditEvent]:
    db.expire_all()
    return db.scalars(
        select(AuditEvent)
        .where(AuditEvent.trip_id == trip.id, AuditEvent.action == action)
        .order_by(AuditEvent.id)
    ).all()


def open_trip(client, token):
    return client.get("/api/driver/trip", headers={"Authorization": f"Bearer {token}"})


def test_two_retakes_then_a_third_failure_goes_to_a_person(api_client, db, fake_ai):
    trip, token = linked_trip(db)
    fake_ai.reading = no_stamp(trip)

    assert upload(api_client, token).json()["attempt_no"] == 1
    assert reload_trip(db, trip).pod_status == "retake_requested"
    assert reload_trip(db, trip).retakes_used == 1

    assert upload(api_client, token).json()["attempt_no"] == 2
    assert reload_trip(db, trip).pod_status == "retake_requested"
    assert reload_trip(db, trip).retakes_used == 2

    assert upload(api_client, token).json()["attempt_no"] == 3

    trip = reload_trip(db, trip)
    assert trip.pod_status == "needs_review"
    assert trip.status_reason == "retake_cap_reached"
    assert trip.retakes_used == 2
    assert attempts_for(db, trip)[-1].reason_codes == ["retake_cap_reached", "stamp_missing"]


def test_a_good_retake_verifies_the_trip(api_client, db, fake_ai):
    trip, token = linked_trip(db)
    fake_ai.reading = no_stamp(trip)
    upload(api_client, token)

    fake_ai.reading = clean_reading(trip)
    response = upload(api_client, token)

    assert response.json()["attempt_no"] == 2
    assert reload_trip(db, trip).pod_status == "verified"


def test_the_driver_is_told_why_and_how_many_retakes_are_used(api_client, db, fake_ai):
    trip, token = linked_trip(db)
    fake_ai.reading = no_stamp(trip)
    upload(api_client, token)

    body = open_trip(api_client, token).json()

    assert body["pod_status"] == "retake_requested"
    assert body["reason_codes"] == ["stamp_missing"]
    assert body["retakes_used"] == 1


def test_a_trip_not_in_retake_shows_no_reasons(api_client, db, fake_ai):
    trip, token = linked_trip(db)
    fake_ai.reading = clean_reading(
        trip, remarks={"text": "short by 6", "kind": "shortage", "confidence": 1.0}
    )
    upload(api_client, token)

    assert open_trip(api_client, token).json()["reason_codes"] == []


def test_a_retake_with_no_attempt_reports_the_trips_reason(api_client, db):
    # The seed's retake trip has no attempt, as an office retake has no new one.
    _trip, token = linked_trip(
        db, pod_status="retake_requested", status_reason="stamp_missing", retakes_used=1
    )

    assert open_trip(api_client, token).json()["reason_codes"] == ["stamp_missing"]


def test_a_retake_writes_a_mock_sms_without_the_token(api_client, db, fake_ai):
    trip, token = linked_trip(db)
    fake_ai.reading = no_stamp(trip)

    upload(api_client, token)

    sent = events(db, trip, "sms_sent")
    assert len(sent) == 1
    assert sent[0].detail == {"purpose": "retake", "reason": "stamp_missing"}
    assert token not in str(sent[0].detail)


def test_no_sms_when_no_retake_is_asked_for(api_client, db, fake_ai):
    trip, token = linked_trip(db)
    fake_ai.reading = clean_reading(trip)

    upload(api_client, token)

    assert events(db, trip, "sms_sent") == []


def test_a_retake_renews_every_unrevoked_link(api_client, db, fake_ai):
    trip, token = linked_trip(db, expected_delivery_at=datetime.now(UTC) - timedelta(hours=70))
    create_link(db, trip)
    create_link(db, trip)
    db.commit()
    links = db.scalars(select(DriverLink).where(DriverLink.trip_id == trip.id)).all()
    revoked = links[-1]
    revoked.revoked_at = datetime.now(UTC)
    old_expiry = revoked.expires_at
    db.commit()
    fake_ai.reading = no_stamp(trip)

    started = datetime.now(UTC)
    upload(api_client, token)

    db.expire_all()
    renewed = [link for link in links if link.id != revoked.id]
    assert all(link.expires_at >= started + LINK_LIFETIME for link in renewed)
    assert db.get(DriverLink, revoked.id).expires_at == old_expiry


def test_a_late_photo_is_stored_but_changes_nothing(api_client, db, fake_ai):
    trip, token = linked_trip(db, pod_status="verified")
    version_before = trip.version

    response = upload(api_client, token)

    assert response.status_code == 200
    assert response.json()["attempt_no"] == 4
    assert response.json()["outcome"] == "verified"
    assert fake_ai.calls == 0

    attempt = attempts_for(db, trip)[0]
    assert attempt.ai_status == "skipped"
    assert attempt.image_bytes == JPEG
    trip = reload_trip(db, trip)
    assert trip.pod_status == "verified"
    assert trip.version == version_before
    assert events(db, trip, "attempt_received")[0].detail["late"] is True


def test_late_photos_keep_counting_up_from_four(api_client, db, fake_ai):
    trip, token = linked_trip(db, pod_status="invoiced")

    numbers = [upload(api_client, token).json()["attempt_no"] for _ in range(3)]

    assert numbers == [4, 5, 6]


def test_a_second_photo_during_a_check_is_a_late_photo(api_client, db, fake_ai):
    trip, token = linked_trip(db, pod_status="checking")

    response = upload(api_client, token)

    assert response.json()["attempt_no"] == 4
    assert fake_ai.calls == 0
    assert reload_trip(db, trip).pod_status == "checking"


def test_a_retake_after_a_late_photo_keeps_a_checked_number(api_client, db, fake_ai):
    trip, token = linked_trip(db)
    fake_ai.reading = clean_reading(
        trip, remarks={"text": "short by 6", "kind": "shortage", "confidence": 1.0}
    )
    upload(api_client, token)  # Attempt 1, now in needs_review.
    upload(api_client, token)  # Attempt 4, late.

    live_trip = reload_trip(db, trip)
    live_trip.pod_status = "retake_requested"
    db.commit()
    fake_ai.reading = clean_reading(trip)

    assert upload(api_client, token).json()["attempt_no"] == 2
    assert reload_trip(db, trip).pod_status == "verified"


def stuck_attempt(db, trip, seconds_ago: int) -> PodAttempt:
    now = datetime.now(UTC)
    attempt = PodAttempt(
        id=uuid4(),
        trip_id=trip.id,
        attempt_no=1,
        image_bytes=JPEG,
        size_bytes=len(JPEG),
        sha256="unused",
        captured_at=now - timedelta(seconds=seconds_ago),
        received_at=now - timedelta(seconds=seconds_ago),
        ai_status="pending",
    )
    db.add(attempt)
    db.commit()
    return attempt


def test_an_attempt_stuck_over_60_seconds_goes_to_a_person(api_client, db):
    trip, token = linked_trip(db, pod_status="checking")
    attempt = stuck_attempt(db, trip, seconds_ago=61)

    result = poll(api_client, token, attempt.id).json()

    assert result["outcome"] == "needs_review"
    assert result["reason_codes"] == ["ai_unavailable"]
    assert reload_trip(db, trip).status_reason == "ai_unavailable"
    db.expire_all()
    assert db.get(PodAttempt, attempt.id).ai_status == "failed"
    fields = db.scalars(select(PodField).where(PodField.attempt_id == attempt.id)).all()
    assert len(fields) == 6


def test_opening_the_link_also_sweeps_a_stuck_attempt(api_client, db):
    trip, token = linked_trip(db, pod_status="checking")
    stuck_attempt(db, trip, seconds_ago=61)

    assert open_trip(api_client, token).json()["pod_status"] == "needs_review"


def test_a_check_under_60_seconds_is_left_alone(api_client, db):
    trip, token = linked_trip(db, pod_status="checking")
    attempt = stuck_attempt(db, trip, seconds_ago=30)

    assert poll(api_client, token, attempt.id).json()["outcome"] is None
    assert reload_trip(db, trip).pod_status == "checking"


def test_a_driver_poll_sweeps_only_its_own_trip(api_client, db):
    trip, token = linked_trip(db, pod_status="checking")
    other_trip, _other_token = linked_trip(db, pod_status="checking")
    stuck_attempt(db, other_trip, seconds_ago=61)

    open_trip(api_client, token)

    assert reload_trip(db, other_trip).pod_status == "checking"
    assert reload_trip(db, trip).pod_status == "checking"


def test_a_real_result_after_the_sweep_is_dropped(api_client, db, fake_ai):
    trip, token = linked_trip(db)
    fake_ai.reading = clean_reading(trip)

    def the_sweep_gets_there_first():
        # The check takes so long that the sweep sends the attempt to a person meanwhile.
        with SessionLocal() as session:
            attempt = session.scalar(select(PodAttempt).where(PodAttempt.trip_id == trip.id))
            attempt.received_at = datetime.now(UTC) - timedelta(seconds=61)
            session.commit()
        open_trip(api_client, token)

    fake_ai.during_call = the_sweep_gets_there_first

    upload(api_client, token)

    assert reload_trip(db, trip).pod_status == "needs_review"
    assert attempts_for(db, trip)[0].ai_status == "failed"


def test_a_photo_dated_after_it_arrived_uses_the_arrival_time(api_client, db, fake_ai):
    trip, token = linked_trip(db)
    fake_ai.reading = clean_reading(trip)
    future = datetime.now(UTC) + timedelta(hours=5)

    upload(api_client, token, captured_at=future.isoformat())

    attempt = attempts_for(db, trip)[0]
    assert attempt.captured_at == attempt.received_at
    assert events(db, trip, "attempt_received")[0].detail["wrong_clock"] == future.isoformat()


def test_a_normal_clock_is_kept_and_not_flagged(api_client, db, fake_ai):
    trip, token = linked_trip(db)
    fake_ai.reading = clean_reading(trip)
    earlier = datetime.now(UTC) - timedelta(minutes=5)

    upload(api_client, token, captured_at=earlier.isoformat())

    attempt = attempts_for(db, trip)[0]
    assert attempt.captured_at == earlier
    assert events(db, trip, "attempt_received")[0].detail["wrong_clock"] is None


def test_sweeps_leave_trip_rows_consistent_with_the_audit_log(api_client, db):
    trip, token = linked_trip(db, pod_status="checking")
    stuck_attempt(db, trip, seconds_ago=61)

    open_trip(api_client, token)

    changes = events(db, trip, "status_change")
    assert [(event.from_status, event.to_status) for event in changes] == [
        ("checking", "needs_review")
    ]
    assert db.get(Trip, trip.id).version == 2  # Trips start at 1, and one move adds one.
