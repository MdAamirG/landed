"""Shared by the seed scripts: adds a sample trip, and the photo attempt its status came from.

The seed bypasses the status machine and the AI, so it stores the same rows they would: an attempt
with its six fields, and an audit event.
"""

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intake import field_values
from app.models import (
    ActorType,
    AiStatus,
    AuditEvent,
    Branch,
    Client,
    DeviceCheck,
    Driver,
    Language,
    Ownership,
    PodAttempt,
    PodField,
    PodStatus,
    Trip,
    Vehicle,
)
from app.rules import ReasonCode, india_date
from app.schemas import PodReading

PHOTOS = Path(__file__).resolve().parents[1] / "samples" / "pods" / "photos"

ORIGIN = "Chhatrapati Sambhajinagar"
SEEDED_MODEL = "seeded"  # Marks a reading no model made, wherever an attempt shows its model.
CONFIDENCE = 0.95  # Well above the 0.80 threshold: these sheets read cleanly.
KM_FROM_THE_GATE = 0.1  # Inside the 2 km radius, so the location check passes.
TAKEN_BEFORE_DUE = timedelta(minutes=30)
UPLOAD_DELAY = timedelta(minutes=4)


@dataclass(frozen=True)
class Sheet:
    """What's on one paper POD, and what the decision rule made of it."""

    photo: str
    reason_codes: tuple[ReasonCode, ...] = ()
    stamp: str = "present"
    qty_received: float | None = None  # Empty when it matches what was dispatched.
    remark: str = ""
    remark_kind: str = "none"
    # The date written on the paper. Empty for a sheet shared by many trips, whose reading then
    # takes the photo's date, so it still passes the date check.
    paper_date: date | None = None


@dataclass(frozen=True)
class SampleTrip:
    code: str
    client: str
    registration_no: str
    ownership: Ownership
    destination: str
    freight_paise: int
    status: PodStatus
    status_reason: ReasonCode | None
    brief_remark: str | None
    branch: str
    driver: str
    driver_phone: str
    driver_language: Language
    lr_number: str
    eway_bill_no: str
    qty_dispatched: int
    qty_unit: str
    consignee_name: str
    consignee_phone: str
    consignee_lat: float
    consignee_lng: float
    sheet: Sheet


SHEET_DATE = date(2026, 11, 6)  # Printed on every sheet in samples/pods/seeded-sheets.json.


def get_or_create(session: Session, model, lookup: dict, **values):
    """Find a row by its natural key, or add it. This is what makes the seed repeatable."""
    row = session.scalar(select(model).filter_by(**lookup))
    if row is None:
        row = model(**lookup, **values)
        session.add(row)
        session.flush()
    return row


@lru_cache
def photo_bytes(name: str) -> bytes:
    return (PHOTOS / name).read_bytes()


def reading_for(trip: Trip, sheet: Sheet, captured_at: datetime) -> PodReading:
    """What the AI would read from this sheet."""
    quantity = sheet.qty_received if sheet.qty_received is not None else float(trip.qty_dispatched)
    delivery_date = sheet.paper_date or india_date(captured_at)
    return PodReading.model_validate(
        {
            "lr_number": {"value": trip.lr_number, "confidence": CONFIDENCE},
            "consignee_stamp": {"value": sheet.stamp, "confidence": CONFIDENCE},
            "quantity_received": {
                "number": quantity,
                "unit": trip.qty_unit,
                "confidence": CONFIDENCE,
            },
            "remarks": {
                "text": sheet.remark,
                "kind": sheet.remark_kind,
                "confidence": CONFIDENCE,
            },
            "delivery_date": {"value": delivery_date, "confidence": CONFIDENCE},
            "signature": {"value": "present", "confidence": CONFIDENCE},
            "image_quality": "ok",
        }
    )


def add_attempt(
    session: Session,
    trip: Trip,
    sheet: Sheet,
    outcome: PodStatus,
    captured_at: datetime,
    received_at: datetime,
) -> None:
    """Store the first photo of a trip with the six fields the AI check would have saved."""
    photo = photo_bytes(sheet.photo)
    reading = reading_for(trip, sheet, captured_at)
    attempt = PodAttempt(
        id=uuid4(),
        trip_id=trip.id,
        attempt_no=1,
        image_bytes=photo,
        size_bytes=len(photo),
        sha256=hashlib.sha256(photo).hexdigest(),
        captured_at=captured_at,
        received_at=received_at,
        gps_lat=trip.consignee_lat,
        gps_lng=trip.consignee_lng,
        gps_accuracy_m=12,
        distance_km=KM_FROM_THE_GATE,
        device_check=DeviceCheck.PASSED,
        ai_status=AiStatus.DONE,
        ai_model=SEEDED_MODEL,
        ai_raw=reading.model_dump(mode="json"),
        outcome=outcome,
        reason_codes=[code.value for code in sheet.reason_codes],
    )
    session.add(attempt)
    session.flush()  # Written now: the models have no relationships to order the inserts by.
    for field, (value, confidence) in field_values(reading).items():
        session.add(
            PodField(
                attempt_id=attempt.id,
                field=field,
                ai_value=value,
                ai_confidence=confidence,
                final_value=value,
            )
        )


def seed_trip(
    session: Session, sample: SampleTrip, now: datetime, source: str = "brief sample data"
) -> None:
    trip = session.scalar(select(Trip).filter_by(trip_code=sample.code))
    if trip is None:
        trip = add_trip(session, sample, now, source)

    # A trip seeded before photos existed gets one, unless someone has since moved it on.
    has_photo = session.scalar(select(PodAttempt.id).filter_by(trip_id=trip.id).limit(1))
    if not has_photo and trip.pod_status == sample.status:
        captured_at = trip.expected_delivery_at - TAKEN_BEFORE_DUE
        # A dispute comes from the client later, so what the check itself decided was verified.
        disputed = sample.status == PodStatus.DISPUTED
        outcome = PodStatus.VERIFIED if disputed else sample.status
        add_attempt(session, trip, sample.sheet, outcome, captured_at, captured_at + UPLOAD_DELAY)
        session.flush()


def add_trip(session: Session, sample: SampleTrip, now: datetime, source: str) -> Trip:
    client = get_or_create(
        session, Client, {"name": sample.client}, tally_ledger_name=sample.client
    )
    branch = get_or_create(session, Branch, {"name": sample.branch})
    vehicle = get_or_create(
        session, Vehicle, {"registration_no": sample.registration_no}, ownership=sample.ownership
    )
    driver = get_or_create(
        session,
        Driver,
        {"phone": sample.driver_phone},
        name=sample.driver,
        language=sample.driver_language,
    )

    trip = Trip(
        trip_code=sample.code,
        client_id=client.id,
        branch_id=branch.id,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        origin=ORIGIN,
        destination=sample.destination,
        lr_number=sample.lr_number,
        eway_bill_no=sample.eway_bill_no,
        qty_dispatched=Decimal(sample.qty_dispatched),
        qty_unit=sample.qty_unit,
        freight_paise=sample.freight_paise,
        consignee_name=sample.consignee_name,
        consignee_phone=sample.consignee_phone,
        consignee_lat=sample.consignee_lat,
        consignee_lng=sample.consignee_lng,
        dispatched_at=now - timedelta(days=3),
        expected_delivery_at=now - timedelta(days=1),
        pod_status=sample.status,
        status_reason=sample.status_reason,
        # A move to retake_requested uses up one of the two retakes.
        retakes_used=1 if sample.status == PodStatus.RETAKE_REQUESTED else 0,
        # verified_by stays empty: the sample trip counts as verified by the AI.
        verified_at=now if sample.status == PodStatus.VERIFIED else None,
    )
    session.add(trip)
    session.flush()

    # The seed bypasses the status machine, so it writes the audit event itself.
    session.add(
        AuditEvent(
            trip_id=trip.id,
            actor_type=ActorType.SYSTEM,
            action="seeded",
            to_status=sample.status,
            detail={"source": source, "remark": sample.brief_remark},
        )
    )
    return trip
