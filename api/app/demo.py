"""Demo mode: the five scenarios an assignment reviewer can run. See "Demo mode" in docs/data-model.md.

Render only deploys api/, so this holds what the API needs at runtime and samples/pods/scenarios.json
stays the record of what's on each sheet. A test keeps the two in step.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.driver_links import create_link
from app.models import Trip
from app.status import reset_demo_trip


@dataclass(frozen=True)
class Scenario:
    id: str  # The name of its sample photo and its entry in scenarios.json.
    trip_code: str
    title: str
    expected: str


SCENARIOS = [
    Scenario("clean", "TRP-70001", "Clean POD", "Verified, and the driver can leave"),
    Scenario("blurry", "TRP-70002", "Blurred photo", "A retake, while the driver is at the gate"),
    Scenario("no-stamp", "TRP-70003", "No consignee stamp", "A retake, for a stamped copy"),
    Scenario(
        "short-6-cartons",
        "TRP-70004",
        "Short by 6 cartons",
        "Sent to Review, because a shortage always is",
    ),
    Scenario("wrong-lr", "TRP-70005", "Wrong LR on the sheet", "Sent to Review, LR doesn't match"),
]

# The sample sheets are all dated 6 Nov 2026, and check 5 compares that with the capture date. This
# is noon that day in India. A sample sent with today's date would stop on date_mismatch instead of
# showing what its scenario is for.
SAMPLE_CAPTURED_AT = datetime(2026, 11, 6, 6, 30, tzinfo=UTC)


def require_demo_mode() -> None:
    """With DEMO_MODE off these routes don't exist as far as callers see, as with demo sign-in."""
    if not settings.demo_mode:
        raise HTTPException(status.HTTP_404_NOT_FOUND)


def start_scenario(session: Session, scenario_id: str) -> str:
    """Reset the scenario's trip and return a fresh driver token, the one time it is available."""
    scenario = next((row for row in SCENARIOS if row.id == scenario_id), None)
    trip = None
    if scenario is not None:
        trip = session.scalar(
            select(Trip).where(Trip.trip_code == scenario.trip_code, Trip.is_demo.is_(True))
        )
    if trip is None:  # An unknown scenario, or the seed hasn't run.
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    reset_demo_trip(session, trip)
    token = create_link(session, trip)  # Not an SMS: the reviewer asked for it on this screen.
    session.commit()
    return token


def sample_scenario(trip: Trip) -> Scenario | None:
    """The scenario whose sample photo this driver screen can offer. None outside demo mode."""
    if not (settings.demo_mode and trip.is_demo):
        return None
    return next((row for row in SCENARIOS if row.trip_code == trip.trip_code), None)
