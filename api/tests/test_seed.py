"""The seed puts the brief's sample data in place. Expected values are copied from docs/brief.md."""

from datetime import datetime, time

import pytest
from argon2 import PasswordHasher
from sqlalchemy import delete, func, select

from app.models import (
    AuditEvent,
    Branch,
    Client,
    Driver,
    PodAttempt,
    PodField,
    Trip,
    User,
    Vehicle,
)
from app.rules import INDIA, Facts, decide
from app.schemas import PodReading
from seed import DEMO_PASSWORD, seed
from seed_trips import PHOTOS, SHEET_DATE

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


def test_each_seeded_field_agrees_with_the_date_on_its_sheet(db):
    seed(db)

    dates = db.scalars(select(PodField.ai_value).where(PodField.field == "delivery_date")).all()
    assert dates == [SHEET_DATE.isoformat()] * 3


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


def attempts_of(db, trip) -> list[PodAttempt]:
    return list(db.scalars(select(PodAttempt).where(PodAttempt.trip_id == trip.id)))


def rule_result(attempt: PodAttempt, trip: Trip):
    """What the real decision rule makes of the stored reading, had the photo come in on the day
    the sheet is dated. The seed itself runs on any day, so its capture time can't be used here.
    """
    return decide(
        PodReading.model_validate(attempt.ai_raw),
        Facts(
            lr_number=trip.lr_number,
            qty_dispatched=trip.qty_dispatched,
            qty_unit=trip.qty_unit,
            retakes_used=0,
            distance_km=attempt.distance_km,
            captured_at=datetime.combine(SHEET_DATE, time(12), tzinfo=INDIA),
        ),
    )


@pytest.mark.parametrize(
    ("code", "status", "reasons", "photo"),
    [
        ("TRP-66120", "verified", [], "trp-66120.jpg"),
        ("TRP-66134", "retake_requested", ["stamp_missing"], "trp-66134.jpg"),
        ("TRP-66141", "needs_review", ["shortage_remark", "qty_short"], "trp-66141.jpg"),
    ],
)
def test_each_brief_trip_has_the_photo_its_status_came_from(db, code, status, reasons, photo):
    seed(db)

    trip = trip_by_code(db, code)
    attempts = attempts_of(db, trip)
    assert [attempt.attempt_no for attempt in attempts] == [1]
    attempt = attempts[0]
    assert attempt.outcome == status
    assert attempt.reason_codes == reasons
    assert attempt.ai_status == "done"
    assert attempt.image_bytes == (PHOTOS / photo).read_bytes()
    assert attempt.size_bytes == len(attempt.image_bytes)

    decision = rule_result(attempt, trip)
    assert decision.status == status
    assert [code.value for code in decision.reason_codes] == reasons


def test_each_seeded_photo_has_all_six_fields(db):
    seed(db)

    fields = db.scalars(select(PodField)).all()
    assert len(fields) == 3 * 6
    assert all(field.final_value == field.ai_value for field in fields)


def test_seeding_twice_adds_no_second_photo(db):
    seed(db)
    seed(db)

    assert count(db, PodAttempt) == 3
    assert count(db, PodField) == 3 * 6


def test_a_trip_seeded_before_photos_existed_gets_one(db):
    """The live database already holds the brief's trips, with no attempts."""
    seed(db)
    db.execute(delete(PodField))
    db.execute(delete(PodAttempt))

    seed(db)

    assert count(db, PodAttempt) == 3


def test_a_trip_that_has_moved_on_is_left_alone(db):
    seed(db)
    db.execute(delete(PodField))
    db.execute(delete(PodAttempt))
    trip = trip_by_code(db, "TRP-66141")
    trip.pod_status = "verified"

    seed(db)

    assert attempts_of(db, trip) == []


def test_the_brief_trip_in_review_can_be_approved_and_reach_billing(api_client, db):
    seed(db)
    db.commit()
    signed_in = api_client.post(
        "/api/auth/login", json={"email": "billing@example.com", "password": DEMO_PASSWORD}
    )
    assert signed_in.status_code == 200
    trip = trip_by_code(db, "TRP-66141")

    approved = api_client.post(
        f"/api/review/trips/{trip.id}/approve", json={"version": trip.version}
    )

    assert approved.status_code == 200
    queue = api_client.get("/api/billing/queue").json()
    codes = {t["trip_code"] for client in queue["clients"] for t in client["trips"]}
    assert codes == {"TRP-66120", "TRP-66141"}
