"""The history seed. It stores about 200 photos, so it runs once for the whole module."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Driver, PodAttempt, PodField, Trip
from seed import DEMO_PASSWORD, seed
from seed_history import seed_history
from tests.conftest import empty_tables

DESIGN_ROWS = ["TRP-66144", "TRP-66147", "TRP-66149", "TRP-66151", "TRP-66153", "TRP-66155"]


@pytest.fixture(scope="module", autouse=True)
def history():
    empty_tables()
    with SessionLocal() as session:
        seed(session)
        seed_history(session)
        session.commit()


@pytest.fixture
def signed_in_client(api_client):
    response = api_client.post(
        "/api/auth/login", json={"email": "billing@example.com", "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200
    return api_client


def test_about_200_backdated_trips_all_sample_and_none_demo(db):
    trips = db.scalars(select(Trip)).all()
    drivers = db.scalars(select(Driver)).all()

    assert 190 <= len(trips) <= 230
    assert not any(trip.is_demo for trip in trips)
    assert all(trip.consignee_name.startswith("Sample ") for trip in trips)
    assert all(trip.consignee_phone.startswith("90000") for trip in trips)
    assert all(driver.name.startswith("Sample ") for driver in drivers)
    assert all(driver.phone.startswith("90000") for driver in drivers)


def test_trips_share_a_few_images(db):
    assert db.scalar(select(func.count(func.distinct(PodAttempt.sha256)))) <= 6


def test_no_invoice_is_dated_in_the_future_or_before_its_photo(db):
    rows = db.execute(
        select(Trip.invoiced_at, PodAttempt.received_at)
        .join(PodAttempt, PodAttempt.trip_id == Trip.id)
        .where(Trip.pod_status == "invoiced")
    ).all()

    assert len(rows) > 100
    now = datetime.now(UTC)
    assert all(received_at < invoiced_at < now for invoiced_at, received_at in rows)


def test_every_trip_with_a_pod_status_past_waiting_has_a_photo(db):
    without_a_photo = db.scalars(
        select(Trip.trip_code)
        .outerjoin(PodAttempt, PodAttempt.trip_id == Trip.id)
        .where(PodAttempt.id.is_(None), Trip.pod_status != "awaiting_pod")
    ).all()

    assert without_a_photo == []


def test_the_dashboard_computes_believable_figures(signed_in_client):
    body = signed_in_client.get("/api/dashboard").json()

    assert 60 <= body["within_24_hours_percent"] <= 85
    assert 4 <= body["pod_to_invoice_days"] <= 7
    assert 0 < body["lost_or_disputed_percent"] <= 1
    branches = {row["branch_name"]: row["median_days"] for row in body["branches"]}
    assert set(branches) == {"Sambhajinagar", "Pune", "Nagpur"}
    assert branches["Sambhajinagar"] < branches["Pune"] < branches["Nagpur"]


def test_the_missing_list_matches_the_design_and_leaves_out_trips_on_the_road(signed_in_client):
    rows = signed_in_client.get("/api/dashboard").json()["missing"]

    codes = [row["trip_code"] for row in rows]
    # The brief's retake trip belongs here too (spec assumption 8).
    assert sorted(codes) == sorted([*DESIGN_ROWS, "TRP-66134"])
    assert [row["trip_code"] for row in rows if row["trip_code"] in DESIGN_ROWS] == DESIGN_ROWS
    hours = {row["trip_code"]: row["hours_since_delivery"] for row in rows}
    assert hours["TRP-66144"] == 31
    assert hours["TRP-66155"] == 2


def test_verified_history_reaches_billing(signed_in_client, db):
    verified = db.scalar(select(func.count()).select_from(Trip).where(Trip.pod_status == "verified"))

    cycles = signed_in_client.get("/api/billing/queue").json()["cycles"]

    assert verified > 0
    assert sum(cycle["trip_count"] for cycle in cycles) == verified


def test_the_queue_counts_add_up(signed_in_client, db):
    counts = signed_in_client.get("/api/dashboard/counts").json()

    assert counts["missing_pods"] == 7
    assert counts["review"] == 2


def test_a_seeded_dispute_can_be_resolved(signed_in_client, db):
    trip = db.scalar(select(Trip).where(Trip.pod_status == "disputed"))
    attempt = db.scalar(select(PodAttempt).where(PodAttempt.trip_id == trip.id))
    assert attempt.outcome == "verified"  # The AI passed it: the client disputed it afterwards.

    response = signed_in_client.post(
        f"/api/review/trips/{trip.id}/approve", json={"version": trip.version}
    )

    assert response.status_code == 200


def test_running_it_again_adds_nothing(db):
    def counts():
        return [db.scalar(select(func.count()).select_from(model)) for model in (Trip, PodField)]

    before = counts()
    seed_history(db)

    assert counts() == before
