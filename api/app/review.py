"""What a billing executive does to a POD: correct a field, approve it, reveal a contact.

Each change checks the version the executive was looking at, so two people can't save over each
other. Each one writes to audit_events in the same transaction. Status moves go through move_trip().
"""

from datetime import UTC, date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.driver_links import create_link
from app.intake import LAST_CHECKED_ATTEMPT_NO
from app.models import (
    ActorType,
    AuditEvent,
    PodAttempt,
    PodField,
    PodFieldName,
    PodStatus,
    Trip,
    User,
)
from app.rules import MAX_DISTANCE_KM, MAX_RETAKES, ReasonCode
from app.status import Actor, IllegalMove, move_trip

EDITABLE = {PodStatus.NEEDS_REVIEW, PodStatus.DISPUTED}  # Never after export.

LR_CODES = {ReasonCode.LR_MISMATCH, ReasonCode.LR_MISSING}


class QuantityValue(BaseModel):
    number: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    unit: Annotated[str, Field(min_length=1, max_length=40)]


class RemarksValue(BaseModel):
    text: Annotated[str, Field(max_length=500)]
    kind: Literal["none", "shortage", "damage", "other"]


Presence = Literal["present", "absent"]
LrNumber = Annotated[str, Field(min_length=1, max_length=40)]

# What each field may hold. The value arrives as plain JSON, so this is its validation.
FIELD_VALUES: dict[PodFieldName, TypeAdapter] = {
    PodFieldName.LR_NUMBER: TypeAdapter(LrNumber),
    PodFieldName.CONSIGNEE_STAMP: TypeAdapter(Presence),
    PodFieldName.QUANTITY_RECEIVED: TypeAdapter(QuantityValue),
    PodFieldName.REMARKS: TypeAdapter(RemarksValue),
    PodFieldName.DELIVERY_DATE: TypeAdapter(date),
    PodFieldName.SIGNATURE: TypeAdapter(Presence),
}


def latest_checked_attempt(session: Session, trip_id: UUID) -> PodAttempt | None:
    """The attempt Review and billing use. Late photos never count (spec assumption 2)."""
    return session.scalar(
        select(PodAttempt)
        .where(PodAttempt.trip_id == trip_id, PodAttempt.attempt_no <= LAST_CHECKED_ATTEMPT_NO)
        .order_by(PodAttempt.attempt_no.desc())
        .limit(1)
    )


def locked_trip(session: Session, trip_id: UUID, version: int) -> Trip:
    """The trip, locked, if it is still the version the executive saw."""
    trip = session.get(Trip, trip_id, with_for_update=True)
    if trip is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if trip.version != version:
        raise HTTPException(status.HTTP_409_CONFLICT, "Someone else saved this trip first")
    return trip


def is_filled(field: str, value: Any) -> bool:
    """A field can be approved only if it holds a real value. Remark text may be empty."""
    if value is None:
        return False
    if field == PodFieldName.QUANTITY_RECEIVED:
        return value.get("number") is not None and bool(value.get("unit"))
    if field == PodFieldName.REMARKS:
        return bool(value.get("kind"))
    return value != ""


def edit_field(
    session: Session, trip_id: UUID, field: PodFieldName, value: Any, version: int, user: User
) -> None:
    trip = locked_trip(session, trip_id, version)
    if trip.pod_status not in EDITABLE:
        raise HTTPException(status.HTTP_409_CONFLICT, "This trip can't be edited now")

    try:
        checked = FIELD_VALUES[field].dump_python(
            FIELD_VALUES[field].validate_python(value), mode="json"
        )
    except ValidationError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error

    attempt = latest_checked_attempt(session, trip.id)
    row = session.get(PodField, (attempt.id, field)) if attempt else None
    if row is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This trip has no reading to correct")

    before = row.final_value
    row.final_value = checked  # ai_value stays as it was, so the original reading is never lost.
    row.edited_by = user.id
    row.edited_at = datetime.now(UTC)
    trip.version += 1
    session.add(
        AuditEvent(
            trip_id=trip.id,
            actor_type=ActorType.USER,
            actor_id=user.id,
            action="field_edited",
            detail={"attempt_id": str(attempt.id), "field": field, "from": before, "to": checked},
        )
    )
    session.commit()


def move_by_hand(session: Session, trip: Trip, target: PodStatus, user: User) -> None:
    try:
        move_trip(session, trip, target, Actor(ActorType.USER, user.id))
    except IllegalMove as error:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    session.commit()


def ask_for_retake(session: Session, trip_id: UUID, version: int, user: User) -> str | None:
    """Returns a driver token for the mock SMS in DEMO_MODE, and None otherwise."""
    trip = locked_trip(session, trip_id, version)
    if trip.retakes_used >= MAX_RETAKES:
        raise HTTPException(status.HTTP_409_CONFLICT, "Both retakes have been used")
    move_by_hand(session, trip, PodStatus.RETAKE_REQUESTED, user)
    if not settings.demo_mode:
        return None

    # Only a hash of the driver's link is stored, so showing a link means making a new one.
    token = create_link(session, trip, Actor(ActorType.USER, user.id), sent=True)
    session.commit()
    return token


def mark_disputed(session: Session, trip_id: UUID, version: int, user: User) -> None:
    move_by_hand(session, locked_trip(session, trip_id, version), PodStatus.DISPUTED, user)


def pull_back(session: Session, trip_id: UUID, version: int, user: User) -> None:
    """How an executive corrects a POD the AI wrongly passed, before it is exported."""
    move_by_hand(session, locked_trip(session, trip_id, version), PodStatus.NEEDS_REVIEW, user)


def approve(session: Session, trip_id: UUID, version: int, user: User) -> None:
    """Also how a dispute is resolved: the same six fields must hold up either way."""
    trip = locked_trip(session, trip_id, version)
    attempt = latest_checked_attempt(session, trip.id)
    rows = (
        session.scalars(select(PodField).where(PodField.attempt_id == attempt.id)).all()
        if attempt
        else []
    )
    # Blank after an AI failure, so the executive fills them in from the photo first.
    filled = {row.field for row in rows if is_filled(row.field, row.final_value)}
    missing = [name.value for name in PodFieldName if name.value not in filled]
    if missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Fill in first: {', '.join(missing)}"
        )

    move_by_hand(session, trip, PodStatus.VERIFIED, user)


def reveal_contact(session: Session, trip_id: UUID, user: User) -> Trip:
    trip = session.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    session.add(
        AuditEvent(
            trip_id=trip.id,
            actor_type=ActorType.USER,
            actor_id=user.id,
            action="contact_revealed",
            detail={},  # Who and when are the record. The contact itself stays out of the log.
        )
    )
    session.commit()
    return trip


def trip_checks(trip: Trip, attempt: PodAttempt | None) -> list[dict[str, Any]]:
    """The plain-language checks shown under the fields."""
    codes = set(attempt.reason_codes) if attempt else set()
    distance = attempt.distance_km if attempt else None
    if distance is None:
        place = {"label": "No location on the photo", "ok": False}
    elif distance > MAX_DISTANCE_KM:
        place = {"label": f"Photo taken {distance:.1f} km from the consignee", "ok": False}
    else:
        place = {"label": "Photo taken at the consignee", "ok": True}

    lr_ok = attempt is not None and attempt.ai_status == "done" and not (codes & LR_CODES)
    return [
        {"label": "LR matches the trip" if lr_ok else "LR not matched to the trip", "ok": lr_ok},
        {"label": "E-way bill is linked", "ok": bool(trip.eway_bill_no)},
        place,
    ]
