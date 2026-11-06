"""The missing-POD dashboard, through the HTTP API. Expected values are worked out by hand."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.driver_links import create_link
from app.models import AuditEvent, Branch, DriverLink, Role
from tests.factories import make_attempt, make_trip, make_user

PASSWORD = "correct horse battery"


def hours_ago(hours: float) -> datetime:
    return datetime.now(UTC) - timedelta(hours=hours)


def days_ago(days: float) -> datetime:
    return datetime.now(UTC) - timedelta(days=days)


@pytest.fixture
def signed_in(empty_db, api_client, db):
    """Named after empty_db, so the emptying can't remove this user."""
    user = make_user(db, Role.OPERATIONS_HEAD, password=PASSWORD)
    api_client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    return user


def dashboard(client) -> dict:
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    return response.json()


def missing_codes(client) -> list[str]:
    return [row["trip_code"] for row in dashboard(client)["missing"]]


@pytest.mark.usefixtures("signed_in")
def test_the_list_holds_trips_past_expected_delivery_still_waiting_for_a_photo(api_client, db):
    waiting = make_trip(db, expected_delivery_at=hours_ago(3))
    retake = make_trip(db, expected_delivery_at=hours_ago(3), pod_status="retake_requested")
    make_trip(db, expected_delivery_at=hours_ago(-3))  # Still on the road.
    make_trip(db, expected_delivery_at=hours_ago(3), pod_status="needs_review")
    make_trip(db, expected_delivery_at=hours_ago(3), pod_status="verified")
    make_trip(db, expected_delivery_at=hours_ago(3), pod_status="checking")

    assert sorted(missing_codes(api_client)) == sorted([waiting.trip_code, retake.trip_code])


@pytest.mark.usefixtures("signed_in")
def test_demo_trips_stay_off_the_list(api_client, db):
    make_trip(db, expected_delivery_at=hours_ago(3), is_demo=True)

    assert missing_codes(api_client) == []


@pytest.mark.usefixtures("signed_in")
def test_the_oldest_comes_first_and_trips_over_24_hours_are_marked(api_client, db):
    recent = make_trip(db, expected_delivery_at=hours_ago(5))
    oldest = make_trip(db, expected_delivery_at=hours_ago(31))

    rows = dashboard(api_client)["missing"]

    assert [row["trip_code"] for row in rows] == [oldest.trip_code, recent.trip_code]
    assert [row["hours_since_delivery"] for row in rows] == [31, 5]
    assert [row["over_24_hours"] for row in rows] == [True, False]


@pytest.mark.usefixtures("signed_in")
def test_a_trip_with_a_photo_counts_from_the_first_photo_not_expected_delivery(api_client, db):
    trip = make_trip(db, expected_delivery_at=hours_ago(2), pod_status="retake_requested")
    make_attempt(db, trip, captured_at=hours_ago(30), received_at=hours_ago(29))

    assert dashboard(api_client)["missing"][0]["hours_since_delivery"] == 30


@pytest.mark.usefixtures("signed_in")
def test_a_row_shows_the_trip_without_any_contact_details(api_client, db):
    trip = make_trip(db, expected_delivery_at=hours_ago(3), destination="Raipur")

    row = dashboard(api_client)["missing"][0]

    assert row["trip_id"] == str(trip.id)
    assert row["destination"] == "Raipur"
    assert row["registration_no"].startswith("TEST ")
    assert row["ownership"] == "own"
    assert row["client_name"].startswith("Test client ")
    assert row["branch_name"].startswith("Test branch ")
    assert "Test Consignee" not in api_client.get("/api/dashboard").text
    assert "9000000000" not in api_client.get("/api/dashboard").text


def delivered_trip(db, delay_hours: float, **overrides):
    """A trip whose first photo reached us delay_hours after it was taken."""
    taken_at = days_ago(3)
    trip = make_trip(db, expected_delivery_at=taken_at, pod_status="verified", **overrides)
    make_attempt(db, trip, taken_at, received_at=taken_at + timedelta(hours=delay_hours))
    return trip


def invoiced_trip(db, days_to_invoice: float, received_days_ago: float = 30, **overrides):
    received_at = days_ago(received_days_ago)
    trip = make_trip(
        db,
        expected_delivery_at=received_at,
        pod_status="invoiced",
        invoiced_at=received_at + timedelta(days=days_to_invoice),
        **overrides,
    )
    make_attempt(db, trip, captured_at=received_at, received_at=received_at)
    return trip


@pytest.mark.usefixtures("signed_in")
def test_the_24_hour_figure_counts_a_missing_pod_only_once_its_24_hours_have_passed(api_client, db):
    delivered_trip(db, delay_hours=1)
    delivered_trip(db, delay_hours=24)  # Exactly on the line still counts as in time.
    delivered_trip(db, delay_hours=25)
    make_trip(db, expected_delivery_at=hours_ago(25))  # Missing, and past its 24 hours: a miss.
    make_trip(db, expected_delivery_at=hours_ago(5))  # Missing, but it still has time.
    make_trip(db, expected_delivery_at=hours_ago(-5))  # Still on the road.

    assert dashboard(api_client)["within_24_hours_percent"] == 50.0  # 2 of 4.


@pytest.mark.usefixtures("signed_in")
def test_pod_to_invoice_days_is_the_median_overall_and_by_branch(api_client, db):
    first = invoiced_trip(db, days_to_invoice=2)
    invoiced_trip(db, days_to_invoice=4, branch_id=first.branch_id)
    invoiced_trip(db, days_to_invoice=6, branch_id=first.branch_id)
    other = invoiced_trip(db, days_to_invoice=8)
    delivered_trip(db, delay_hours=1)  # Not invoiced yet, so it has no days to count.

    body = dashboard(api_client)

    assert body["pod_to_invoice_days"] == 5.0  # The median of 2, 4, 6 and 8.
    assert body["branches"] == [
        {"branch_name": first_branch_name(db, first), "median_days": 4.0},
        {"branch_name": first_branch_name(db, other), "median_days": 8.0},
    ]


def first_branch_name(db, trip) -> str:
    return db.get(Branch, trip.branch_id).name


@pytest.mark.usefixtures("signed_in")
def test_lost_or_disputed_counts_disputes_and_pods_missing_for_20_days(api_client, db):
    make_trip(db, expected_delivery_at=days_ago(3), pod_status="disputed")
    make_trip(db, expected_delivery_at=days_ago(21))  # Lost, never photographed.
    make_trip(db, expected_delivery_at=days_ago(21), pod_status="retake_requested")  # Also lost.
    make_trip(db, expected_delivery_at=days_ago(19))  # Late, but not lost yet.
    make_trip(db, expected_delivery_at=days_ago(21), pod_status="verified")
    make_trip(db, expected_delivery_at=days_ago(21), pod_status="invoiced")
    make_trip(db, expected_delivery_at=hours_ago(-5))  # On the road, so not part of the base.

    assert dashboard(api_client)["lost_or_disputed_percent"] == 50.0  # 3 of 6.


@pytest.mark.usefixtures("signed_in")
def test_demo_trips_stay_out_of_every_figure(api_client, db):
    delivered_trip(db, delay_hours=1, is_demo=True)
    invoiced_trip(db, days_to_invoice=2, is_demo=True)
    make_trip(db, expected_delivery_at=days_ago(3), pod_status="disputed", is_demo=True)

    body = dashboard(api_client)

    assert body["within_24_hours_percent"] is None
    assert body["pod_to_invoice_days"] is None
    assert body["lost_or_disputed_percent"] is None
    assert body["branches"] == []


@pytest.mark.usefixtures("signed_in")
def test_figures_cover_a_rolling_window_but_the_list_never_forgets_a_trip(api_client, db):
    invoiced_trip(db, days_to_invoice=2, received_days_ago=91)
    old = make_trip(db, expected_delivery_at=days_ago(91))
    invoiced_trip(db, days_to_invoice=6, received_days_ago=89)

    body = dashboard(api_client)

    assert body["window_days"] == 90
    assert body["pod_to_invoice_days"] == 6.0
    assert body["lost_or_disputed_percent"] == 0.0
    assert [row["trip_code"] for row in body["missing"]] == [old.trip_code]


@pytest.mark.usefixtures("signed_in")
def test_with_no_trips_the_figures_are_empty_rather_than_zero(api_client):
    body = dashboard(api_client)

    assert body["missing"] == []
    assert body["within_24_hours_percent"] is None
    assert body["pod_to_invoice_days"] is None
    assert body["lost_or_disputed_percent"] is None
    assert body["branches"] == []


def resend(client, trip_id):
    return client.post(f"/api/dashboard/trips/{trip_id}/resend-link")


def links_of(db, trip) -> list[DriverLink]:
    db.expire_all()
    return list(db.scalars(select(DriverLink).where(DriverLink.trip_id == trip.id)))


def events_of(db, trip, action: str) -> list[AuditEvent]:
    return list(
        db.scalars(
            select(AuditEvent).where(AuditEvent.trip_id == trip.id, AuditEvent.action == action)
        )
    )


def test_a_resend_adds_a_link_and_leaves_the_old_one_working(api_client, db, signed_in):
    trip = make_trip(db, expected_delivery_at=hours_ago(3))
    old_token = create_link(db, trip)
    db.commit()

    response = resend(api_client, trip.id)

    assert response.status_code == 200
    assert len(links_of(db, trip)) == 2
    assert driver_trip_status(api_client, old_token) == 200


def driver_trip_status(client, token: str) -> int:
    return client.get("/api/driver/trip", headers={"Authorization": f"Bearer {token}"}).status_code


def test_a_resend_records_when_it_went_but_a_plain_new_link_does_not(api_client, db, signed_in):
    trip = make_trip(db, expected_delivery_at=hours_ago(3))
    create_link(db, trip)
    db.commit()

    resend(api_client, trip.id)

    sent = [link.sent_at is not None for link in links_of(db, trip)]
    assert sorted(sent) == [False, True]


def test_a_resend_says_who_got_it_with_the_phone_masked(api_client, db, signed_in):
    trip = make_trip(db, expected_delivery_at=hours_ago(3))

    assert resend(api_client, trip.id).json() == {"sent_to": "+91 90••• ••000"}


def test_a_resend_is_logged_without_the_token(api_client, db, signed_in):
    trip = make_trip(db, expected_delivery_at=hours_ago(3))

    resend(api_client, trip.id)

    sms = events_of(db, trip, "sms_sent")
    assert [event.detail["purpose"] for event in sms] == ["resend"]
    assert sms[0].actor_type == "user"
    assert sms[0].actor_id == signed_in.id
    assert events_of(db, trip, "driver_link_created")[0].actor_id == signed_in.id


def test_a_resent_link_is_not_born_expired_on_a_long_overdue_trip(api_client, db, signed_in):
    """The list exists for exactly these trips, and an expired link would be no use to them."""
    trip = make_trip(db, expected_delivery_at=days_ago(10))

    resend(api_client, trip.id)

    assert links_of(db, trip)[0].expires_at > datetime.now(UTC) + timedelta(hours=71)


def test_a_trip_that_no_longer_needs_a_photo_can_not_be_resent(api_client, db, signed_in):
    trip = make_trip(db, expected_delivery_at=hours_ago(3), pod_status="verified")

    assert resend(api_client, trip.id).status_code == 409
    assert links_of(db, trip) == []


def test_resending_an_unknown_trip_finds_nothing(api_client, signed_in):
    assert resend(api_client, uuid4()).status_code == 404


def test_the_top_bar_sweeps_stuck_attempts_so_its_review_count_is_honest(api_client, db, signed_in):
    trip = make_trip(db, pod_status="checking")
    long_ago = hours_ago(1)
    attempt = make_attempt(db, trip, captured_at=long_ago, received_at=long_ago)
    attempt.ai_status = "pending"
    db.commit()

    assert api_client.get("/api/dashboard/counts").json()["review"] == 1


def test_the_top_bar_counts_each_queue(api_client, db, signed_in):
    make_trip(db, pod_status="needs_review")
    make_trip(db, pod_status="verified")
    make_trip(db, pod_status="verified")
    make_trip(db, expected_delivery_at=hours_ago(3))

    assert api_client.get("/api/dashboard/counts").json() == {
        "review": 1,
        "billing": 2,
        "missing_pods": 1,
    }
