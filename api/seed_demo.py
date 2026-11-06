"""Seeds the five demo trips. Safe to run twice: a demo trip that exists stays as it is.

Each is a copy of the brief's trip to the same destination, with the LR number, e-way bill and
quantity from samples/pods/scenarios.json. They start at awaiting_pod, so none needs a seeded
photo: the reviewer sends the first one.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.demo import SCENARIOS
from app.models import PodStatus, Trip
from seed_trips import SampleTrip, Sheet, add_trip

SCENARIOS_FILE = Path(__file__).resolve().parents[1] / "samples" / "pods" / "scenarios.json"


def seed_demo(session: Session, sample_trips: list[SampleTrip]) -> None:
    """Add the demo trips to the session. The caller commits."""
    now = datetime.now(UTC)
    sheets = {sheet["id"]: sheet for sheet in json.loads(SCENARIOS_FILE.read_text())}

    for scenario in SCENARIOS:
        if session.scalar(select(Trip).filter_by(trip_code=scenario.trip_code)):
            continue
        sheet = sheets[scenario.id]
        details = sheet["trip"]
        like = next(trip for trip in sample_trips if trip.destination == details["destination"])
        sample = replace(
            like,
            code=scenario.trip_code,
            status=PodStatus.AWAITING_POD,
            status_reason=None,
            brief_remark=None,
            lr_number=details["lr_number"],
            eway_bill_no=details["eway_bill_no"],
            qty_dispatched=details["qty_dispatched"],
            qty_unit=details["qty_unit"],
            sheet=Sheet(sheet["image"]),
        )
        add_trip(session, sample, now, "demo scenario").is_demo = True
    session.flush()
