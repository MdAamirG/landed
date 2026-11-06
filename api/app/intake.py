"""Attempt intake and the background check.

accept_attempt() stores a photo from a valid driver link and returns at once. run_check() then
calls the AI, runs the decision rule and applies the result. They are separate so a weak network
can't lose a check that is already running.
"""

import hashlib
import logging
from datetime import UTC, datetime, timedelta
from math import asin, cos, radians, sin, sqrt
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import ai
from app.db import SessionLocal
from app.models import ActorType, AuditEvent, DriverLink, PodAttempt, PodField, PodStatus, Trip
from app.rules import Facts, decide
from app.schemas import AttemptForm, PodReading
from app.status import SYSTEM, Actor, IllegalMove, move_trip

logger = logging.getLogger(__name__)

MAX_PHOTO_BYTES = 300_000
MAX_UPLOADS_PER_HOUR = 10  # Also caps Gemini calls if a link leaks.
EARTH_RADIUS_KM = 6371

ATTEMPT_RECEIVED = "attempt_received"  # The audit action the upload limit counts.


def image_type(data: bytes) -> str | None:
    """The media type from the file's first bytes. Filenames and headers can claim anything."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def check_photo(data: bytes) -> None:
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "The photo is over 300 KB")
    if image_type(data) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "That file isn't an image")


def distance_km(lat_1: float, lng_1: float, lat_2: float, lng_2: float) -> float:
    """Distance along the ground, by the haversine formula."""
    lat_gap = radians(lat_2 - lat_1)
    lng_gap = radians(lng_2 - lng_1)
    a = sin(lat_gap / 2) ** 2 + cos(radians(lat_1)) * cos(radians(lat_2)) * sin(lng_gap / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def distance_from_consignee(form: AttemptForm, trip: Trip) -> float | None:
    """None when the phone has no location. Dead zones are expected, so that isn't a problem."""
    if form.gps_lat is None or form.gps_lng is None:
        return None
    return distance_km(form.gps_lat, form.gps_lng, trip.consignee_lat, trip.consignee_lng)


def check_upload_limit(session: Session, trip: Trip, now: datetime) -> None:
    # Counted from the audit log, so a fresh link or a demo reset can't clear the count.
    uploads = session.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(
            AuditEvent.trip_id == trip.id,
            AuditEvent.action == ATTEMPT_RECEIVED,
            AuditEvent.at > now - timedelta(hours=1),
        )
    )
    if uploads >= MAX_UPLOADS_PER_HOUR:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many uploads for this trip")


def next_attempt_no(session: Session, trip: Trip) -> int:
    highest = session.scalar(
        select(func.max(PodAttempt.attempt_no)).where(PodAttempt.trip_id == trip.id)
    )
    return (highest or 0) + 1


def accept_attempt(
    session: Session, link: DriverLink, form: AttemptForm, photo: bytes
) -> tuple[PodAttempt, Trip, bool]:
    """Store the attempt and commit. Also says whether it is new, so a repeat isn't rechecked."""
    check_photo(photo)

    # Locked first, so two photos arriving together can't take the same attempt number, and the
    # same photo sent twice at once can't get past the repeat check.
    trip = session.get_one(Trip, link.trip_id, with_for_update=True)

    existing = session.get(PodAttempt, form.attempt_id)
    if existing is not None:
        if existing.trip_id != trip.id:
            raise HTTPException(status.HTTP_409_CONFLICT, "That attempt ID is already in use")
        session.commit()  # Lets go of the lock.
        return existing, trip, False  # A repeat costs nothing, and doesn't count to the limit.

    now = datetime.now(UTC)
    check_upload_limit(session, trip, now)

    attempt = PodAttempt(
        id=form.attempt_id,
        trip_id=trip.id,
        attempt_no=next_attempt_no(session, trip),
        image_bytes=photo,
        size_bytes=len(photo),
        sha256=hashlib.sha256(photo).hexdigest(),
        captured_at=form.captured_at,
        received_at=now,
        gps_lat=form.gps_lat,
        gps_lng=form.gps_lng,
        gps_accuracy_m=form.gps_accuracy_m,
        distance_km=distance_from_consignee(form, trip),
        ai_status="pending",
    )
    session.add(attempt)
    session.flush()
    session.add(
        AuditEvent(
            trip_id=trip.id,
            actor_type=ActorType.DRIVER_LINK,
            actor_id=link.id,
            action=ATTEMPT_RECEIVED,
            detail={"attempt_id": str(attempt.id), "attempt_no": attempt.attempt_no},
        )
    )
    try:
        move_trip(session, trip, PodStatus.CHECKING, Actor(ActorType.DRIVER_LINK, link.id))
    except IllegalMove as error:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    session.commit()
    return attempt, trip, True


def field_values(reading: PodReading | None) -> dict[str, tuple[object, float | None]]:
    """The six fields as stored, each as (value, confidence). Blank when the AI failed."""
    if reading is None:
        names = (
            "lr_number",
            "consignee_stamp",
            "quantity_received",
            "remarks",
            "delivery_date",
            "signature",
        )
        return {name: (None, None) for name in names}

    quantity = reading.quantity_received
    remarks = reading.remarks
    date_read = reading.delivery_date.value
    return {
        "lr_number": (reading.lr_number.value, reading.lr_number.confidence),
        "consignee_stamp": (reading.consignee_stamp.value, reading.consignee_stamp.confidence),
        "quantity_received": (
            {"number": quantity.number, "unit": quantity.unit},
            quantity.confidence,
        ),
        "remarks": ({"text": remarks.text, "kind": remarks.kind}, remarks.confidence),
        "delivery_date": (
            date_read.isoformat() if date_read else None,
            reading.delivery_date.confidence,
        ),
        "signature": (reading.signature.value, reading.signature.confidence),
    }


def apply_result(session: Session, attempt: PodAttempt, trip: Trip, result: ai.AiResult) -> None:
    """Run the decision rule on an AI result and save everything together. Caller commits."""
    decision = decide(
        result.reading,
        Facts(
            lr_number=trip.lr_number,
            qty_dispatched=trip.qty_dispatched,
            qty_unit=trip.qty_unit,
            retakes_used=trip.retakes_used,
            distance_km=attempt.distance_km,
            captured_at=attempt.captured_at,
        ),
    )

    attempt.ai_status = "done" if result.reading else "failed"
    attempt.ai_model = result.model
    attempt.ai_latency_ms = result.latency_ms
    attempt.ai_raw = result.raw
    attempt.outcome = decision.status
    attempt.reason_codes = [code.value for code in decision.reason_codes]

    for field, (value, confidence) in field_values(result.reading).items():
        session.add(
            PodField(
                attempt_id=attempt.id,
                field=field,
                ai_value=value,
                ai_confidence=confidence,
                final_value=value,  # Stays the same unless an executive corrects it.
            )
        )
    move_trip(session, trip, decision.status, SYSTEM, decision.reason)


def run_check(attempt_id: UUID) -> None:
    """The background task. It opens its own sessions, because the request's has closed."""
    with SessionLocal() as session:
        attempt = session.get_one(PodAttempt, attempt_id)
        image, trip_id = attempt.image_bytes, attempt.trip_id

    # No database connection is held during the AI call, which can take 20 seconds.
    result = ai.read_pod(image, image_type(image))

    with SessionLocal() as session:
        trip = session.get_one(Trip, trip_id, with_for_update=True)
        attempt = session.get_one(PodAttempt, attempt_id)
        # A late result must not overwrite a person's decision, or a newer attempt's check.
        if trip.pod_status != PodStatus.CHECKING or attempt.ai_status != "pending":
            logger.info("Dropped a late AI result for attempt %s", attempt_id)
            return
        apply_result(session, attempt, trip, result)
        session.commit()
