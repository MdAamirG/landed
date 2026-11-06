"""The seed puts the brief's sample data in place. Expected values are copied from docs/brief.md."""

import pytest
from argon2 import PasswordHasher
from sqlalchemy import func, select

from app.models import AuditEvent, Branch, Client, Driver, Trip, User, Vehicle
from seed import DEMO_PASSWORD, seed

pytestmark = pytest.mark.usefixtures("empty_db")


def count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


def trip_by_code(db, code: str) -> Trip:
    return db.scalar(select(Trip).where(Trip.trip_code == code))


@pytest.mark.parametrize(
    ("code", "client", "registration", "ownership", "destination", "freight_paise", "status"),
    [
        ("TRP-66120", "Company B", "MH20 EL 4521", "own", "Nagpur", 3_850_000, "verified"),
        ("TRP-66134", "Company C", "MH20 GT 7718", "own", "Pune", 2_600_000, "retake_requested"),
        ("TRP-66141", "Company D", "MH17 BY 3092", "hired", "Indore", 4_120_000, "needs_review"),
    ],
)
def test_seed_creates_the_briefs_three_trips(
    db, code, client, registration, ownership, destination, freight_paise, status
):
    seed(db)

    trip = trip_by_code(db, code)
    assert db.get(Client, trip.client_id).name == client
    vehicle = db.get(Vehicle, trip.vehicle_id)
    assert (vehicle.registration_no, vehicle.ownership) == (registration, ownership)
    assert trip.destination == destination
    assert trip.freight_paise == freight_paise
    assert trip.pod_status == status


def test_seed_gives_each_trip_a_rule_reason_not_the_papers_wording(db):
    seed(db)

    assert trip_by_code(db, "TRP-66120").status_reason is None
    assert trip_by_code(db, "TRP-66134").status_reason == "stamp_missing"
    assert trip_by_code(db, "TRP-66141").status_reason == "shortage_remark"


def test_the_audit_log_keeps_the_briefs_remarks(db):
    seed(db)

    remarks = {event.detail["remark"] for event in db.scalars(select(AuditEvent))}
    assert remarks == {None, "Stamp not visible", "Short by 6 cartons"}


def test_seeded_trips_match_the_approved_screens(db):
    seed(db)

    assert trip_by_code(db, "TRP-66120").lr_number == "48190"  # Billing.html
    chakan = trip_by_code(db, "TRP-66134")  # Driver_Home.html
    assert (chakan.lr_number, chakan.eway_bill_no) == ("48207", "341099217735")
    indore = trip_by_code(db, "TRP-66141")  # Review.html
    assert (indore.lr_number, indore.eway_bill_no) == ("48213", "341099217712")
    assert (indore.qty_dispatched, indore.qty_unit) == (400, "cartons")


def test_seeded_statuses_are_consistent_with_their_rules(db):
    seed(db)

    verified = trip_by_code(db, "TRP-66120")
    assert verified.verified_at is not None
    assert verified.verified_by is None  # The AI verified it, not a person.
    assert trip_by_code(db, "TRP-66134").retakes_used == 1


def test_seed_creates_the_supporting_rows(db):
    seed(db)

    assert count(db, Client) == 3
    assert count(db, Branch) == 3
    assert count(db, Vehicle) == 3
    assert count(db, Driver) == 3
    assert set(db.scalars(select(Branch.name))) == {"Sambhajinagar", "Pune", "Nagpur"}


def test_seed_creates_demo_office_users_for_both_roles_with_hashed_passwords(db):
    seed(db)

    users = db.scalars(select(User)).all()
    assert sorted(user.role for user in users) == ["billing_executive", "operations_head"]
    for user in users:
        assert DEMO_PASSWORD not in user.password_hash
        assert PasswordHasher().verify(user.password_hash, DEMO_PASSWORD)


def test_each_seeded_status_is_on_the_audit_log(db):
    seed(db)

    events = db.scalars(select(AuditEvent)).all()
    assert sorted(event.to_status for event in events) == [
        "needs_review",
        "retake_requested",
        "verified",
    ]
    assert {event.actor_type for event in events} == {"system"}


def test_seeding_twice_changes_nothing(db):
    seed(db)
    seed(db)

    assert count(db, Trip) == 3
    assert count(db, Client) == 3
    assert count(db, User) == 2
    assert count(db, AuditEvent) == 3
