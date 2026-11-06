"""The schema from docs/data-model.md, as the migration actually builds it."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import Base, DriverLink, PodAttempt, PodField, Trip
from tests.factories import make_trip

TWELVE_TABLES = {
    "trips",
    "pod_attempts",
    "pod_fields",
    "driver_links",
    "users",
    "clients",
    "branches",
    "vehicles",
    "drivers",
    "import_batches",
    "export_batches",
    "audit_events",
}


def attempt_values(trip_id, **overrides):
    values = {
        "id": uuid4(),
        "trip_id": trip_id,
        "attempt_no": 1,
        "image_bytes": b"photo",
        "size_bytes": 5,
        "sha256": "0" * 64,
        "captured_at": datetime.now(UTC),
    }
    return values | overrides


def test_the_migration_creates_the_twelve_tables(db):
    tables = set(inspect(db.connection()).get_table_names())

    assert tables - {"alembic_version"} == TWELVE_TABLES


def test_the_models_and_the_migration_agree(db):
    context = MigrationContext.configure(db.connection())

    assert compare_metadata(context, Base.metadata) == []


def test_trips_has_the_indexes_the_data_model_lists(db):
    indexed = [index["column_names"] for index in inspect(db.connection()).get_indexes("trips")]

    assert ["pod_status"] in indexed
    assert ["client_id", "pod_status"] in indexed
    assert ["eway_bill_no"] in indexed


def test_a_new_trip_starts_awaiting_pod_on_version_1(db):
    trip = make_trip(db)
    db.refresh(trip)

    assert trip.pod_status == "awaiting_pod"
    assert trip.retakes_used == 0
    assert trip.version == 1
    assert trip.is_demo is False


def test_a_factory_trip_is_visible_to_other_sessions(db):
    # API requests and the background check open their own sessions, so factories must commit.
    trip = make_trip(db)

    with SessionLocal() as other_session:
        assert other_session.get(Trip, trip.id) is not None


@pytest.mark.parametrize("field", ["trip_code", "lr_number"])
def test_trip_code_and_lr_number_are_unique(db, field):
    first = make_trip(db)

    with pytest.raises(IntegrityError):
        make_trip(db, **{field: getattr(first, field)})


@pytest.mark.parametrize(
    "bad_values",
    [
        pytest.param({"pod_status": "approved"}, id="a status outside the seven"),
        pytest.param({"retakes_used": 3}, id="more than two retakes"),
        pytest.param({"eway_bill_no": "12345"}, id="e-way bill too short"),
        pytest.param({"eway_bill_no": "12345678901X"}, id="e-way bill not digits"),
    ],
)
def test_the_database_refuses_an_invalid_trip(db, bad_values):
    with pytest.raises(IntegrityError):
        make_trip(db, **bad_values)


def test_a_repeated_attempt_id_is_refused(db):
    # Offline retries depend on this: the phone's UUID can only be stored once.
    trip = make_trip(db)
    first = attempt_values(trip.id)
    db.add(PodAttempt(**first))
    db.flush()
    db.expunge_all()  # Forget the first row, so Postgres refuses the repeat, not SQLAlchemy.

    db.add(PodAttempt(**(first | {"attempt_no": 2})))
    with pytest.raises(IntegrityError):
        db.flush()


def test_a_repeated_attempt_number_on_a_trip_is_refused(db):
    trip = make_trip(db)
    db.add(PodAttempt(**attempt_values(trip.id)))
    db.flush()

    db.add(PodAttempt(**attempt_values(trip.id)))
    with pytest.raises(IntegrityError):
        db.flush()


def test_one_field_row_per_field_per_attempt(db):
    trip = make_trip(db)
    attempt = PodAttempt(**attempt_values(trip.id))
    db.add(attempt)
    db.flush()
    db.add(PodField(attempt_id=attempt.id, field="lr_number", ai_value="LR-1", ai_confidence=0.9))
    db.flush()
    db.expunge_all()  # Forget the first row, so Postgres refuses the repeat, not SQLAlchemy.

    db.add(PodField(attempt_id=attempt.id, field="lr_number", ai_value="LR-2", ai_confidence=0.9))
    with pytest.raises(IntegrityError):
        db.flush()


def test_a_driver_token_hash_is_stored_once(db):
    trip = make_trip(db)
    expires_at = datetime.now(UTC)
    db.add(DriverLink(trip_id=trip.id, token_hash="same", expires_at=expires_at))
    db.flush()

    db.add(DriverLink(trip_id=trip.id, token_hash="same", expires_at=expires_at))
    with pytest.raises(IntegrityError):
        db.flush()
