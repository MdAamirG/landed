"""A demo reset removes one demo trip's photos and links, and nothing belonging to any other trip."""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import func, select

from app.db import SessionLocal
from app.driver_links import create_link
from app.intake import MAX_UPLOADS_PER_HOUR, fail_stuck_attempt, run_check
from app.models import (
    AuditEvent,
    DriverLink,
    ExportBatch,
    PodAttempt,
    PodField,
    Trip,
)
from app.status import IllegalMove, reset_demo_trip
from seed import seed
from tests.factories import clean_reading, make_trip, make_user
from tests.test_attempts import upload


def demo_trip_with_a_photo(api_client, db, fake_ai) -> Trip:
    """A demo trip that has really been through intake, so it has every row a reset must remove."""
    trip = make_trip(db, is_demo=True)
    token = create_link(db, trip)
    db.commit()
    fake_ai.reading = clean_reading(trip)
    assert upload(api_client, token).status_code == 200
    db.expire_all()
    return db.get_one(Trip, trip.id)


def rows_of(db, model, trip) -> int:
    return db.scalar(select(func.count()).select_from(model).where(model.trip_id == trip.id))


def field_rows_of(db, trip) -> int:
    return db.scalar(
        select(func.count())
        .select_from(PodField)
        .join(PodAttempt, PodField.attempt_id == PodAttempt.id)
        .where(PodAttempt.trip_id == trip.id)
    )


def test_a_reset_removes_the_trips_attempts_fields_and_links(api_client, db, fake_ai):
    trip = demo_trip_with_a_photo(api_client, db, fake_ai)
    assert (rows_of(db, PodAttempt, trip), field_rows_of(db, trip)) == (1, 6)
    assert rows_of(db, DriverLink, trip) == 1

    reset_demo_trip(db, trip)
    db.commit()

    assert (rows_of(db, PodAttempt, trip), field_rows_of(db, trip)) == (0, 0)
    assert rows_of(db, DriverLink, trip) == 0


def test_a_reset_kills_the_old_link(api_client, db):
    trip = make_trip(db, is_demo=True)
    token = create_link(db, trip)
    db.commit()

    reset_demo_trip(db, trip)
    db.commit()

    response = api_client.get("/api/driver/trip", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_the_upload_limit_carries_on_across_a_reset(api_client, db, fake_ai):
    trip = demo_trip_with_a_photo(api_client, db, fake_ai)
    for _ in range(MAX_UPLOADS_PER_HOUR - 1):
        db.add(
            AuditEvent(
                trip_id=trip.id,
                actor_type="driver_link",
                action="attempt_received",
                detail={"attempt_id": "x"},
            )
        )
    reset_demo_trip(db, trip)
    token = create_link(db, trip)
    db.commit()

    assert upload(api_client, token).status_code == 429


def everything_outside(db, demo_trip: Trip) -> dict[str, list[tuple]]:
    """Every column of every row not belonging to the demo trip, in a form that can be compared."""

    def columns_of(row) -> tuple:
        return tuple(getattr(row, column.key) for column in row.__table__.columns)

    def rows(model, *conditions) -> list[tuple]:
        found = db.scalars(select(model).where(*conditions))
        return sorted((columns_of(row) for row in found), key=str)

    db.expire_all()
    other_attempts = select(PodAttempt.id).where(PodAttempt.trip_id != demo_trip.id)
    return {
        "trips": rows(Trip, Trip.id != demo_trip.id),
        "attempts": rows(PodAttempt, PodAttempt.trip_id != demo_trip.id),
        "fields": rows(PodField, PodField.attempt_id.in_(other_attempts)),
        "links": rows(DriverLink, DriverLink.trip_id != demo_trip.id),
        "audit": rows(AuditEvent, AuditEvent.trip_id != demo_trip.id),
        "exports": rows(ExportBatch),
    }


@pytest.mark.usefixtures("empty_db")
def test_a_reset_leaves_seeded_history_and_export_batches_exactly_as_they_were(
    api_client, db, fake_ai
):
    seed(db)
    db.commit()
    seeded = db.scalars(select(Trip).where(Trip.is_demo.is_(False))).all()
    assert seeded  # The proof is empty otherwise.
    for trip in seeded:
        create_link(db, trip)
    batch = ExportBatch(
        cycle_start=date(2026, 11, 1),
        cycle_end=date(2026, 11, 15),
        created_by=make_user(db).id,
        trip_count=1,
        total_paise=3_200_000,
        xml="<ENVELOPE />",
    )
    db.add(batch)
    db.flush()
    demo_trip = demo_trip_with_a_photo(api_client, db, fake_ai)
    demo_trip.export_batch_id = batch.id
    demo_trip.voucher_no = "V-1"
    db.commit()
    before = everything_outside(db, demo_trip)

    reset_demo_trip(db, demo_trip)
    db.commit()

    assert everything_outside(db, demo_trip) == before


def test_a_refused_reset_removes_nothing(api_client, db, fake_ai):
    trip = make_trip(db)
    token = create_link(db, trip)
    db.commit()
    fake_ai.reading = clean_reading(trip)
    upload(api_client, token)
    db.expire_all()

    with pytest.raises(IllegalMove):
        reset_demo_trip(db, db.get_one(Trip, trip.id))

    assert rows_of(db, PodAttempt, trip) == 1
    assert rows_of(db, DriverLink, trip) == 1


def test_a_check_still_running_during_a_reset_is_dropped(api_client, db, fake_ai):
    trip = make_trip(db, is_demo=True)
    token = create_link(db, trip)
    db.commit()
    fake_ai.reading = clean_reading(trip)

    def a_reviewer_resets_during_the_check():
        with SessionLocal() as session:
            reset_demo_trip(session, session.get_one(Trip, trip.id))
            session.commit()

    fake_ai.during_call = a_reviewer_resets_during_the_check

    assert upload(api_client, token).status_code == 200  # The background check ran and survived.

    db.expire_all()
    assert db.get_one(Trip, trip.id).pod_status == "awaiting_pod"
    assert rows_of(db, PodAttempt, trip) == 0


def attempt_row(db, trip) -> PodAttempt:
    return db.scalar(select(PodAttempt).where(PodAttempt.trip_id == trip.id))


def test_a_check_that_starts_after_a_reset_is_dropped(db, fake_ai, api_client):
    trip = demo_trip_with_a_photo(api_client, db, fake_ai)
    attempt_id = attempt_row(db, trip).id
    calls = fake_ai.calls
    reset_demo_trip(db, trip)
    db.commit()

    run_check(attempt_id)

    assert fake_ai.calls == calls


def test_a_stuck_attempt_removed_by_a_reset_is_ignored(db, fake_ai, api_client):
    trip = demo_trip_with_a_photo(api_client, db, fake_ai)
    attempt_id = attempt_row(db, trip).id
    reset_demo_trip(db, trip)
    db.commit()

    fail_stuck_attempt(db, attempt_id)

    assert db.get_one(Trip, trip.id).pod_status == "awaiting_pod"


def test_a_reset_trip_can_start_again_with_attempt_number_one(api_client, db, fake_ai):
    trip = demo_trip_with_a_photo(api_client, db, fake_ai)
    reset_demo_trip(db, trip)
    token = create_link(db, trip)
    db.commit()

    response = upload(api_client, token, captured_at=datetime.now(UTC).isoformat())

    assert response.json()["attempt_no"] == 1
    db.expire_all()
    assert db.get_one(Trip, trip.id).pod_status == "verified"
