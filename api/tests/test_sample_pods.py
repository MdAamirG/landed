"""The sample PODs stay usable: the photo flow, accuracy script and demo all rely on samples/pods."""

import json
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

import pytest

from app.rules import INDIA, Facts, decide
from app.schemas import (
    DateReading,
    PodReading,
    PresenceReading,
    QuantityReading,
    RemarksReading,
    TextReading,
)
from seed import SAMPLE_TRIPS

PODS = Path(__file__).resolve().parents[2] / "samples" / "pods"
SCENARIOS = json.loads((PODS / "scenarios.json").read_text())

MAX_BYTES = 300_000
HIGH = 0.95

each_scenario = pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s["id"])


def perfect_reading(scenario: dict) -> PodReading:
    """What a model reading this sheet without error would return."""
    expected = scenario["reading"]
    return PodReading(
        lr_number=TextReading(value=scenario["sheet_lr_number"], confidence=HIGH),
        consignee_stamp=PresenceReading(value=expected["consignee_stamp"], confidence=HIGH),
        quantity_received=QuantityReading(
            number=expected["quantity_received"],
            unit=scenario["trip"]["qty_unit"],
            confidence=HIGH,
        ),
        remarks=RemarksReading(
            text=expected["remarks"], kind=expected["remarks_kind"], confidence=HIGH
        ),
        delivery_date=DateReading(value=expected["delivery_date"], confidence=HIGH),
        signature=PresenceReading(value=expected["signature"], confidence=HIGH),
        image_quality=expected["image_quality"],
    )


def test_all_five_scenarios_exist():
    assert [scenario["id"] for scenario in SCENARIOS] == [
        "clean",
        "blurry",
        "no-stamp",
        "short-6-cartons",
        "wrong-lr",
    ]


@each_scenario
def test_image_is_under_the_upload_limit(scenario):
    assert (PODS / scenario["image"]).stat().st_size < MAX_BYTES


@each_scenario
def test_scenario_reaches_its_expected_result(scenario):
    trip = scenario["trip"]
    delivered = date.fromisoformat(scenario["reading"]["delivery_date"])
    facts = Facts(
        lr_number=trip["lr_number"],
        qty_dispatched=Decimal(str(trip["qty_dispatched"])),
        qty_unit=trip["qty_unit"],
        retakes_used=0,
        distance_km=None,
        captured_at=datetime.combine(delivered, time(12), tzinfo=INDIA),
    )

    decision = decide(perfect_reading(scenario), facts)

    assert decision.status == scenario["expected_status"]
    assert decision.reason_codes == tuple(scenario["expected_reasons"])


def test_only_the_wrong_lr_sheet_differs_from_its_trip():
    different = [s["id"] for s in SCENARIOS if s["sheet_lr_number"] != s["trip"]["lr_number"]]

    assert different == ["wrong-lr"]


def test_lr_numbers_are_free_for_the_demo_trips():
    """trips.lr_number is unique, so a clash would stop the demo trips from being created."""
    numbers = [scenario["trip"]["lr_number"] for scenario in SCENARIOS]
    seeded = {sample.lr_number for sample in SAMPLE_TRIPS}

    assert len(set(numbers)) == len(numbers)
    assert not seeded.intersection(numbers)
