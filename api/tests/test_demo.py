"""Demo mode: the five demo trips, the scenario picker's routes and the sample photo's details."""

import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.demo import SAMPLE_CAPTURED_AT, SCENARIOS
from app.driver_links import create_link
from app.models import AuditEvent, DriverLink, Role, Trip
from app.rules import india_date
from seed import SAMPLE_TRIPS, seed
from seed_demo import seed_demo
from tests.factories import make_trip, make_user
from tests.test_attempts import upload
from tests.test_review import PASSWORD
from tests.test_sample_pods import perfect_reading

SHEETS = json.loads(
    (Path(__file__).resolve().parents[2] / "samples" / "pods" / "scenarios.json").read_text()
)
SHEET_BY_ID = {sheet["id"]: sheet for sheet in SHEETS}

each_scenario = pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda row: row.id)


@pytest.fixture
def demo_on(monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", True)


@pytest.fixture
def demo_off(monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", False)


@pytest.fixture
def seeded(empty_db, db):
    seed(db)
    seed_demo(db, SAMPLE_TRIPS)
    db.commit()


def demo_trip(db, scenario) -> Trip:
    db.expire_all()
    return db.scalar(select(Trip).where(Trip.trip_code == scenario.trip_code))


def start(client, scenario_id: str):
    return client.post(f"/api/demo/scenarios/{scenario_id}/start")


def driver_trip(client, token: str):
    return client.get("/api/driver/trip", headers={"Authorization": f"Bearer {token}"})


def test_the_scenarios_match_the_sample_sheets():
    assert [scenario.id for scenario in SCENARIOS] == [sheet["id"] for sheet in SHEETS]


def test_the_sample_capture_time_falls_on_every_sheets_date():
    for sheet in SHEETS:
        assert india_date(SAMPLE_CAPTURED_AT).isoformat() == sheet["reading"]["delivery_date"]


@each_scenario
@pytest.mark.usefixtures("seeded")
def test_each_scenario_has_a_demo_trip_with_its_sheets_details(db, scenario):
    trip = demo_trip(db, scenario)
    details = SHEET_BY_ID[scenario.id]["trip"]

    assert trip.is_demo
    assert trip.pod_status == "awaiting_pod"
    assert trip.lr_number == details["lr_number"]
    assert trip.eway_bill_no == details["eway_bill_no"]
    assert float(trip.qty_dispatched) == details["qty_dispatched"]
    assert trip.qty_unit == details["qty_unit"]
    assert trip.destination == details["destination"]


@pytest.mark.usefixtures("seeded")
def test_seeding_the_demo_trips_again_adds_nothing_and_keeps_their_state(db):
    trip = demo_trip(db, SCENARIOS[0])
    trip.pod_status = "needs_review"
    db.commit()

    seed_demo(db, SAMPLE_TRIPS)
    db.commit()

    assert db.scalar(select(func.count()).select_from(Trip).where(Trip.is_demo)) == len(SCENARIOS)
    assert demo_trip(db, SCENARIOS[0]).pod_status == "needs_review"


@pytest.mark.usefixtures("demo_off")
def test_nothing_runs_with_demo_mode_off(api_client, db):
    assert api_client.get("/api/demo/scenarios").status_code == 404
    assert start(api_client, "clean").status_code == 404


@pytest.mark.usefixtures("demo_off", "seeded")
def test_a_demo_trip_offers_no_sample_with_demo_mode_off(api_client, db):
    token = create_link(db, demo_trip(db, SCENARIOS[0]))
    db.commit()

    assert driver_trip(api_client, token).json()["demo_sample"] is None


@pytest.mark.usefixtures("demo_on")
def test_the_picker_lists_the_five_scenarios(api_client):
    listed = api_client.get("/api/demo/scenarios").json()

    assert [row["id"] for row in listed] == [scenario.id for scenario in SCENARIOS]
    assert all(row["title"] and row["expected"] and row["trip_code"] for row in listed)


@pytest.mark.usefixtures("demo_on", "seeded")
def test_picking_a_scenario_gives_a_working_link_and_kills_the_last_one(api_client, db):
    first = start(api_client, "clean").json()["driver_token"]
    second = start(api_client, "clean").json()["driver_token"]

    assert driver_trip(api_client, first).status_code == 401
    assert driver_trip(api_client, second).status_code == 200
    trip = demo_trip(db, SCENARIOS[0])
    links = select(func.count()).select_from(DriverLink).where(DriverLink.trip_id == trip.id)
    assert db.scalar(links) == 1


@pytest.mark.usefixtures("demo_on", "seeded")
def test_picking_a_scenario_is_logged_without_the_token(api_client, db):
    token = start(api_client, "clean").json()["driver_token"]

    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.trip_id == demo_trip(db, SCENARIOS[0]).id)
        .order_by(AuditEvent.id)
    ).all()
    assert [event.action for event in events] == ["seeded", "demo_reset", "driver_link_created"]
    assert all(token not in json.dumps(event.detail) for event in events)


@pytest.mark.usefixtures("demo_on", "seeded")
def test_an_unknown_scenario_is_not_found(api_client):
    assert start(api_client, "nothing-like-this").status_code == 404


@pytest.mark.usefixtures("demo_on", "empty_db")
def test_picking_a_scenario_before_the_seed_has_run_is_not_found(api_client):
    assert start(api_client, "clean").status_code == 404


@pytest.mark.usefixtures("demo_on", "empty_db")
def test_a_real_trip_with_a_demo_trip_code_is_never_reset(api_client, db):
    trip = make_trip(db, trip_code=SCENARIOS[0].trip_code, pod_status="verified")

    assert start(api_client, "clean").status_code == 404
    db.expire_all()
    assert db.get_one(Trip, trip.id).pod_status == "verified"


@each_scenario
@pytest.mark.usefixtures("demo_on", "seeded")
def test_a_demo_trips_driver_screen_offers_its_sample_at_the_gate(api_client, db, scenario):
    token = start(api_client, scenario.id).json()["driver_token"]

    sample = driver_trip(api_client, token).json()["demo_sample"]

    trip = demo_trip(db, scenario)
    assert sample["scenario"] == scenario.id
    assert sample["gps_lat"] == trip.consignee_lat
    assert sample["gps_lng"] == trip.consignee_lng


@pytest.mark.usefixtures("demo_on", "empty_db")
def test_a_real_trip_offers_no_sample_even_in_demo_mode(api_client, db):
    token = create_link(db, make_trip(db))
    db.commit()

    assert driver_trip(api_client, token).json()["demo_sample"] is None


@each_scenario
@pytest.mark.usefixtures("demo_on", "seeded")
def test_a_sample_sent_as_the_screen_offers_it_lands_where_its_scenario_says(
    api_client, db, fake_ai, scenario
):
    """The whole path but the model: the details the screen sends, then the real decision rule."""
    token = start(api_client, scenario.id).json()["driver_token"]
    sample = driver_trip(api_client, token).json()["demo_sample"]
    fake_ai.reading = perfect_reading(SHEET_BY_ID[scenario.id])

    response = upload(
        api_client,
        token,
        captured_at=sample["captured_at"],
        gps_lat=sample["gps_lat"],
        gps_lng=sample["gps_lng"],
    )

    result = api_client.get(
        f"/api/driver/attempts/{response.json()['attempt_id']}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    expected = SHEET_BY_ID[scenario.id]
    assert result["outcome"] == expected["expected_status"]
    assert result["reason_codes"] == expected["expected_reasons"]


@pytest.mark.usefixtures("demo_on", "seeded")
def test_a_demo_trip_can_be_followed_into_review_and_billing(api_client, db, fake_ai):
    user = make_user(db, Role.BILLING_EXECUTIVE, password=PASSWORD)
    api_client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})

    for scenario_id in ("short-6-cartons", "clean"):
        token = start(api_client, scenario_id).json()["driver_token"]
        sample = driver_trip(api_client, token).json()["demo_sample"]
        fake_ai.reading = perfect_reading(SHEET_BY_ID[scenario_id])
        upload(
            api_client,
            token,
            captured_at=sample["captured_at"],
            gps_lat=sample["gps_lat"],
            gps_lng=sample["gps_lng"],
        )

    in_review = api_client.get("/api/review/queue?filter=needs_review").json()
    assert "TRP-70004" in [row["trip_code"] for row in in_review]

    queue = api_client.get("/api/billing/queue").json()
    codes = [trip["trip_code"] for client in queue["clients"] for trip in client["trips"]]
    assert "TRP-70001" in codes
