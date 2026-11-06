from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_role
from app.db import get_db
from app.intake import LAST_CHECKED_ATTEMPT_NO, image_type, sweep_stuck_attempts
from app.masking import mask_name, mask_phone
from app.models import (
    AuditEvent,
    Client,
    Driver,
    PodAttempt,
    PodField,
    PodFieldName,
    PodStatus,
    Role,
    Trip,
    User,
    Vehicle,
)
from app.review import (
    approve,
    ask_for_retake,
    edit_field,
    latest_checked_attempt,
    mark_disputed,
    pull_back,
    reveal_contact,
    trip_checks,
)
from app.schemas import (
    ContactOut,
    FieldEditIn,
    ReviewAttemptOut,
    ReviewFieldOut,
    ReviewQueueItemOut,
    ReviewTripOut,
    RetakeOut,
    VersionIn,
)

router = APIRouter(prefix="/review")

BillingExecutive = Annotated[User, Depends(require_role(Role.BILLING_EXECUTIVE))]
Db = Annotated[Session, Depends(get_db)]


def wrong_clock_attempts(db: Session, trip_id: UUID) -> set[str]:
    events = db.scalars(
        select(AuditEvent).where(
            AuditEvent.trip_id == trip_id, AuditEvent.action == "attempt_received"
        )
    )
    return {event.detail["attempt_id"] for event in events if event.detail.get("wrong_clock")}


def attempt_out(db: Session, attempt: PodAttempt, wrong_clock: set[str]) -> ReviewAttemptOut:
    fields = db.scalars(select(PodField).where(PodField.attempt_id == attempt.id)).all()
    by_name = {row.field: row for row in fields}
    return ReviewAttemptOut(
        id=attempt.id,
        attempt_no=attempt.attempt_no,
        late=attempt.attempt_no > LAST_CHECKED_ATTEMPT_NO,
        captured_at=attempt.captured_at,
        received_at=attempt.received_at,
        size_bytes=attempt.size_bytes,
        distance_km=attempt.distance_km,
        device_check=attempt.device_check,
        ai_status=attempt.ai_status,
        ai_latency_ms=attempt.ai_latency_ms,
        reason_codes=attempt.reason_codes,
        clock_corrected=str(attempt.id) in wrong_clock,
        # Listed from the enum, so the fields always arrive in the same order.
        fields=[
            ReviewFieldOut(
                field=name,
                ai_value=by_name[name].ai_value,
                ai_confidence=by_name[name].ai_confidence,
                final_value=by_name[name].final_value,
                edited=by_name[name].edited_at is not None,
            )
            for name in PodFieldName
            if name in by_name
        ],
    )


def trip_out(db: Session, trip: Trip) -> ReviewTripOut:
    attempts = db.scalars(
        select(PodAttempt).where(PodAttempt.trip_id == trip.id).order_by(PodAttempt.attempt_no)
    ).all()
    current = latest_checked_attempt(db, trip.id)
    wrong_clock = wrong_clock_attempts(db, trip.id)
    vehicle = db.get_one(Vehicle, trip.vehicle_id)
    driver = db.get_one(Driver, trip.driver_id)
    return ReviewTripOut(
        id=trip.id,
        trip_code=trip.trip_code,
        version=trip.version,
        pod_status=trip.pod_status,
        status_reason=trip.status_reason,
        reason_codes=current.reason_codes if current else [],
        retakes_used=trip.retakes_used,
        origin=trip.origin,
        destination=trip.destination,
        client_name=db.get_one(Client, trip.client_id).name,
        ownership=vehicle.ownership,
        registration_no=vehicle.registration_no,
        lr_number=trip.lr_number,
        eway_bill_no=trip.eway_bill_no,
        qty_dispatched=float(trip.qty_dispatched),
        qty_unit=trip.qty_unit,
        consignee_name=mask_name(trip.consignee_name),
        consignee_phone=mask_phone(trip.consignee_phone),
        driver_name=driver.name,
        driver_phone=mask_phone(driver.phone),
        current_attempt_id=current.id if current else None,
        attempts=[attempt_out(db, attempt, wrong_clock) for attempt in attempts],
        checks=trip_checks(trip, current),
    )


@router.get("/queue", response_model=list[ReviewQueueItemOut])
def queue(
    _: BillingExecutive,
    db: Db,
    filter: Literal["needs_review", "disputed", "verified"] = "needs_review",
) -> list[ReviewQueueItemOut]:
    sweep_stuck_attempts(db)  # Spec assumption 3: the 60-second rule runs on read.
    trips = db.execute(
        select(Trip, Client.name, Vehicle.ownership)
        .join(Client, Trip.client_id == Client.id)
        .join(Vehicle, Trip.vehicle_id == Vehicle.id)
        .where(Trip.pod_status == PodStatus(filter))
    ).all()
    late_photos = dict(
        db.execute(
            select(PodAttempt.trip_id, func.count())
            .where(PodAttempt.attempt_no > LAST_CHECKED_ATTEMPT_NO)
            .group_by(PodAttempt.trip_id)
        ).all()
    )

    items = []
    for trip, client_name, ownership in trips:
        attempt = latest_checked_attempt(db, trip.id)
        items.append(
            ReviewQueueItemOut(
                id=trip.id,
                trip_code=trip.trip_code,
                destination=trip.destination,
                client_name=client_name,
                ownership=ownership,
                status_reason=trip.status_reason,
                waiting_since=attempt.received_at if attempt else trip.expected_delivery_at,
                late_photos=late_photos.get(trip.id, 0),
            )
        )
    return sorted(items, key=lambda item: item.waiting_since)


@router.get("/trips/{trip_id}", response_model=ReviewTripOut)
def get_trip(trip_id: UUID, _: BillingExecutive, db: Db) -> ReviewTripOut:
    trip = db.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return trip_out(db, trip)


@router.get("/attempts/{attempt_id}/photo")
def get_photo(attempt_id: UUID, _: BillingExecutive, db: Db) -> Response:
    attempt = db.get(PodAttempt, attempt_id)
    if attempt is None or attempt.image_bytes is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return Response(
        attempt.image_bytes,
        media_type=image_type(attempt.image_bytes),
        headers={"Cache-Control": "private, max-age=3600"},  # A stored photo never changes.
    )


@router.patch("/trips/{trip_id}/fields/{field}", response_model=ReviewTripOut)
def correct_field(
    trip_id: UUID, field: PodFieldName, body: FieldEditIn, user: BillingExecutive, db: Db
) -> ReviewTripOut:
    edit_field(db, trip_id, field, body.value, body.version, user)
    return trip_out(db, db.get_one(Trip, trip_id))


@router.post("/trips/{trip_id}/approve", response_model=ReviewTripOut)
def approve_trip(trip_id: UUID, body: VersionIn, user: BillingExecutive, db: Db) -> ReviewTripOut:
    approve(db, trip_id, body.version, user)
    return trip_out(db, db.get_one(Trip, trip_id))


@router.post("/trips/{trip_id}/retake", response_model=RetakeOut)
def retake_trip(trip_id: UUID, body: VersionIn, user: BillingExecutive, db: Db) -> RetakeOut:
    token = ask_for_retake(db, trip_id, body.version, user)
    trip = trip_out(db, db.get_one(Trip, trip_id))
    return RetakeOut(**trip.model_dump(), driver_token=token)


@router.post("/trips/{trip_id}/dispute", response_model=ReviewTripOut)
def dispute_trip(trip_id: UUID, body: VersionIn, user: BillingExecutive, db: Db) -> ReviewTripOut:
    mark_disputed(db, trip_id, body.version, user)
    return trip_out(db, db.get_one(Trip, trip_id))


@router.post("/trips/{trip_id}/pull-back", response_model=ReviewTripOut)
def pull_back_trip(trip_id: UUID, body: VersionIn, user: BillingExecutive, db: Db) -> ReviewTripOut:
    pull_back(db, trip_id, body.version, user)
    return trip_out(db, db.get_one(Trip, trip_id))


@router.post("/trips/{trip_id}/reveal", response_model=ContactOut)
def reveal(trip_id: UUID, user: BillingExecutive, db: Db) -> ContactOut:
    """The only route that returns a consignee's real contact. Each call is logged."""
    trip = reveal_contact(db, trip_id, user)
    return ContactOut(name=trip.consignee_name, phone=trip.consignee_phone)
