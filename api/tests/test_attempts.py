"""Photos reaching the server and the AI check, through the HTTP API with the AI reader faked."""

from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.db import SessionLocal
from app.driver_links import create_link
from app.intake import MAX_PHOTO_BYTES, MAX_UPLOADS_PER_HOUR, distance_km
from app.models import AuditEvent, PodAttempt, PodField, Trip
from tests.factories import clean_reading, make_trip

JPEG = b"\xff\xd8\xff\xe0" + b"photo" * 200


@pytest.fixture
def trip(db):
    return make_trip(db)


@pytest.fixture
def token(db, trip):
    value = create_link(db, trip)
    db.commit()
    return value


def upload(client, token, *, photo=JPEG, attempt_id=None, **form):
    data = {
        "attempt_id": str(attempt_id or uuid4()),
        "captured_at": datetime.now(UTC).isoformat(),
    }
    return client.post(
        "/api/driver/attempts",
        data=data | form,
        files={"photo": ("pod.jpg", BytesIO(photo), "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )


def poll(client, token, attempt_id):
    return client.get(
        f"/api/driver/attempts/{attempt_id}", headers={"Authorization": f"Bearer {token}"}
    )


def reload_trip(db, trip) -> Trip:
    db.expire_all()
    return db.get_one(Trip, trip.id)


def attempts_for(db, trip) -> list[PodAttempt]:
    db.expire_all()
    return db.scalars(
        select(PodAttempt).where(PodAttempt.trip_id == trip.id).order_by(PodAttempt.attempt_no)
    ).all()


def test_a_clean_photo_is_verified_by_the_ai(api_client, db, trip, token, fake_ai):
    fake_ai.reading = clean_reading(trip)

    response = upload(api_client, token, gps_lat=21.1458, gps_lng=79.0882, gps_accuracy_m=12)

    assert response.status_code == 200
    assert response.json()["attempt_no"] == 1
    assert response.json()["outcome"] is None  # Answered before the check ran.

    result = poll(api_client, token, response.json()["attempt_id"]).json()
    assert result["outcome"] == "verified"
    assert result["reason_codes"] == []

    trip = reload_trip(db, trip)
    assert trip.pod_status == "verified"
    assert trip.verified_by is None
    assert trip.verified_at is not None


def test_the_attempt_keeps_the_photo_and_the_ai_call_details(api_client, db, trip, token, fake_ai):
    fake_ai.reading = clean_reading(trip)

    upload(api_client, token, gps_lat=21.1458, gps_lng=79.0882, gps_accuracy_m=12)

    attempt = attempts_for(db, trip)[0]
    assert attempt.image_bytes == JPEG
    assert attempt.size_bytes == len(JPEG)
    assert attempt.gps_accuracy_m == 12
    assert attempt.distance_km == pytest.approx(0, abs=0.01)
    assert attempt.ai_status == "done"
    assert attempt.ai_model == "fake-model"
    assert attempt.ai_latency_ms == 1234
    assert attempt.ai_raw["lr_number"]["value"] == trip.lr_number


def test_each_ai_field_is_stored_as_read_and_as_final(api_client, db, trip, token, fake_ai):
    fake_ai.reading = clean_reading(trip)

    upload(api_client, token)

    attempt = attempts_for(db, trip)[0]
    fields = {
        row.field: row
        for row in db.scalars(select(PodField).where(PodField.attempt_id == attempt.id))
    }
    assert set(fields) == {
        "lr_number",
        "consignee_stamp",
        "quantity_received",
        "remarks",
        "delivery_date",
        "signature",
    }
    assert fields["lr_number"].ai_value == trip.lr_number
    assert fields["lr_number"].ai_confidence == 0.99
    assert fields["quantity_received"].ai_value == {
        "number": float(trip.qty_dispatched),
        "unit": trip.qty_unit,
    }
    assert all(row.final_value == row.ai_value for row in fields.values())


def test_a_fixable_problem_asks_for_a_retake_and_uses_one(api_client, db, trip, token, fake_ai):
    fake_ai.reading = clean_reading(
        trip, consignee_stamp={"value": "absent", "confidence": 0.95}
    )

    response = upload(api_client, token)

    result = poll(api_client, token, response.json()["attempt_id"]).json()
    assert result["outcome"] == "retake_requested"
    assert result["reason_codes"] == ["stamp_missing"]
    assert result["retakes_used"] == 1
    assert reload_trip(db, trip).status_reason == "stamp_missing"


def test_a_shortage_remark_goes_to_a_person_at_any_confidence(api_client, db, trip, token, fake_ai):
    fake_ai.reading = clean_reading(
        trip, remarks={"text": "short by 6", "kind": "shortage", "confidence": 1.0}
    )

    upload(api_client, token)

    assert reload_trip(db, trip).pod_status == "needs_review"
    assert reload_trip(db, trip).status_reason == "shortage_remark"


def test_a_failed_ai_call_keeps_the_photo_and_goes_to_a_person(
    api_client, db, trip, token, fake_ai
):
    fake_ai.reading = None

    upload(api_client, token)

    trip = reload_trip(db, trip)
    attempt = attempts_for(db, trip)[0]
    assert trip.pod_status == "needs_review"
    assert trip.status_reason == "ai_unavailable"
    assert attempt.image_bytes == JPEG
    assert attempt.ai_status == "failed"
    fields = db.scalars(select(PodField).where(PodField.attempt_id == attempt.id)).all()
    assert len(fields) == 6
    assert all(row.ai_value is None and row.ai_confidence is None for row in fields)


def test_a_photo_far_from_the_consignee_goes_to_a_person(api_client, db, trip, token, fake_ai):
    fake_ai.reading = clean_reading(trip)

    upload(api_client, token, gps_lat=19.8762, gps_lng=75.3433)

    assert reload_trip(db, trip).status_reason == "location_far"


def test_a_missing_location_is_accepted_and_marked(api_client, db, trip, token, fake_ai):
    fake_ai.reading = clean_reading(trip)

    upload(api_client, token)

    attempt = attempts_for(db, trip)[0]
    assert attempt.gps_lat is None
    assert attempt.distance_km is None
    assert reload_trip(db, trip).pod_status == "verified"


def test_a_repeated_attempt_id_stores_nothing_new(api_client, db, trip, token, fake_ai):
    fake_ai.reading = clean_reading(trip)
    attempt_id = uuid4()

    first = upload(api_client, token, attempt_id=attempt_id)
    second = upload(api_client, token, attempt_id=attempt_id, photo=JPEG + b"different")

    assert second.status_code == first.status_code == 200
    assert second.json()["attempt_id"] == str(attempt_id)
    assert second.json()["outcome"] == "verified"  # The first result, now that it has one.
    assert len(attempts_for(db, trip)) == 1
    assert attempts_for(db, trip)[0].image_bytes == JPEG
    assert fake_ai.calls == 1


def test_a_repeat_does_not_count_toward_the_limit(api_client, db, trip, token, fake_ai):
    fake_ai.reading = clean_reading(trip)
    attempt_id = uuid4()

    for _ in range(MAX_UPLOADS_PER_HOUR + 2):
        assert upload(api_client, token, attempt_id=attempt_id).status_code == 200

    uploads = db.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(AuditEvent.trip_id == trip.id, AuditEvent.action == "attempt_received")
    )
    assert uploads == 1


def test_another_trips_attempt_id_is_refused(api_client, db, trip, token, fake_ai):
    fake_ai.reading = clean_reading(trip)
    attempt_id = uuid4()
    upload(api_client, token, attempt_id=attempt_id)
    other_token = create_link(db, make_trip(db))
    db.commit()

    assert upload(api_client, other_token, attempt_id=attempt_id).status_code == 409
    assert poll(api_client, other_token, attempt_id).status_code == 404


def test_uploads_stop_at_the_hourly_limit(api_client, db, trip, token, fake_ai):
    db.add_all(
        AuditEvent(trip_id=trip.id, actor_type="driver_link", action="attempt_received", detail={})
        for _ in range(MAX_UPLOADS_PER_HOUR)
    )
    db.commit()

    assert upload(api_client, token).status_code == 429
    assert attempts_for(db, trip) == []


def test_uploads_older_than_an_hour_do_not_count(api_client, db, trip, token, fake_ai):
    fake_ai.reading = clean_reading(trip)
    long_ago = datetime.now(UTC) - timedelta(hours=1, minutes=1)
    db.add_all(
        AuditEvent(
            trip_id=trip.id,
            actor_type="driver_link",
            action="attempt_received",
            detail={},
            at=long_ago,
        )
        for _ in range(MAX_UPLOADS_PER_HOUR)
    )
    db.commit()

    assert upload(api_client, token).status_code == 200


def test_a_photo_over_the_limit_is_refused(api_client, db, trip, token, fake_ai):
    too_big = JPEG + b"x" * MAX_PHOTO_BYTES

    assert upload(api_client, token, photo=too_big).status_code == 413
    assert attempts_for(db, trip) == []
    assert fake_ai.calls == 0


def test_a_photo_exactly_at_the_limit_is_accepted(api_client, db, trip, token, fake_ai):
    fake_ai.reading = clean_reading(trip)
    at_limit = JPEG + b"x" * (MAX_PHOTO_BYTES - len(JPEG))

    assert upload(api_client, token, photo=at_limit).status_code == 200


def test_a_file_that_only_claims_to_be_an_image_is_refused(api_client, db, trip, token, fake_ai):
    response = upload(api_client, token, photo=b"%PDF-1.7 not a photo at all")

    assert response.status_code == 422
    assert attempts_for(db, trip) == []


@pytest.mark.parametrize(
    "form",
    [
        {"attempt_id": "not-a-uuid"},
        {"captured_at": "yesterday"},
        {"captured_at": "2026-11-07T10:00:00"},  # No time zone.
        {"gps_lat": "91"},
        {"gps_lng": "-181"},
    ],
)
def test_bad_form_fields_are_refused(api_client, db, trip, token, fake_ai, form):
    assert upload(api_client, token, **form).status_code == 422


def test_an_upload_with_a_bad_token_stores_nothing(api_client, db, trip, fake_ai):
    assert upload(api_client, "not-a-real-token").status_code == 401
    assert attempts_for(db, trip) == []


def test_a_late_result_does_not_overwrite_a_change_made_meanwhile(
    api_client, db, trip, token, fake_ai
):
    fake_ai.reading = clean_reading(trip)

    def a_person_decides_during_the_check():
        with SessionLocal() as session:
            live_trip = session.get_one(Trip, trip.id)
            live_trip.pod_status = "needs_review"
            session.commit()

    fake_ai.during_call = a_person_decides_during_the_check

    upload(api_client, token)

    assert reload_trip(db, trip).pod_status == "needs_review"
    assert attempts_for(db, trip)[0].outcome is None


def test_distance_matches_a_known_route():
    # Sambhajinagar to Pune is about 210 km in a straight line.
    assert distance_km(19.8762, 75.3433, 18.5204, 73.8567) == pytest.approx(216, abs=10)
