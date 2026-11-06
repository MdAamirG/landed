from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.demo import SAMPLE_CAPTURED_AT, sample_scenario
from app.driver_links import valid_driver_link
from app.intake import (
    LAST_CHECKED_ATTEMPT_NO,
    MAX_PHOTO_BYTES,
    accept_attempt,
    run_check,
    sweep_stuck_attempts,
)
from app.models import Client, DriverLink, PodAttempt, Trip, Vehicle
from app.schemas import AttemptForm, AttemptOut, DemoSampleOut, DriverTripOut

router = APIRouter(prefix="/driver")


def attempt_out(attempt: PodAttempt, trip: Trip) -> AttemptOut:
    return AttemptOut(
        attempt_id=attempt.id,
        attempt_no=attempt.attempt_no,
        outcome=attempt.outcome,
        reason_codes=attempt.reason_codes,
        retakes_used=trip.retakes_used,
    )


def retake_reasons(db: Session, trip: Trip) -> list[str]:
    """Why the driver is being asked for a new photo, from the latest checked attempt."""
    latest = db.scalar(
        select(PodAttempt)
        .where(PodAttempt.trip_id == trip.id, PodAttempt.attempt_no <= LAST_CHECKED_ATTEMPT_NO)
        .order_by(PodAttempt.attempt_no.desc())
        .limit(1)
    )
    if latest is not None and latest.reason_codes:
        return latest.reason_codes
    # An office retake, or seeded data, has a reason on the trip and none on an attempt.
    return [trip.status_reason] if trip.status_reason else []


def demo_sample(trip: Trip) -> DemoSampleOut | None:
    scenario = sample_scenario(trip)
    if scenario is None:
        return None
    return DemoSampleOut(
        scenario=scenario.id,
        captured_at=SAMPLE_CAPTURED_AT,
        gps_lat=trip.consignee_lat,
        gps_lng=trip.consignee_lng,
    )


@router.get("/trip", response_model=DriverTripOut)
def get_trip(
    link: Annotated[DriverLink, Depends(valid_driver_link)],
    db: Annotated[Session, Depends(get_db)],
) -> DriverTripOut:
    """The one trip this link opens. The token picks the trip, so no trip ID is ever accepted."""
    sweep_stuck_attempts(db, link.trip_id)
    trip = db.get_one(Trip, link.trip_id)
    return DriverTripOut(
        trip_code=trip.trip_code,
        registration_no=db.get_one(Vehicle, trip.vehicle_id).registration_no,
        client_name=db.get_one(Client, trip.client_id).name,
        origin=trip.origin,
        destination=trip.destination,
        lr_number=trip.lr_number,
        eway_bill_no=trip.eway_bill_no,
        pod_status=trip.pod_status,
        retakes_used=trip.retakes_used,
        reason_codes=retake_reasons(db, trip) if trip.pod_status == "retake_requested" else [],
        demo_sample=demo_sample(trip),
    )


@router.post("/attempts", response_model=AttemptOut)
def upload_attempt(
    form: Annotated[AttemptForm, Form()],
    photo: UploadFile,
    link: Annotated[DriverLink, Depends(valid_driver_link)],
    db: Annotated[Session, Depends(get_db)],
    background_tasks: BackgroundTasks,
) -> AttemptOut:
    """Stores the photo and returns at once. The phone polls the route below for the result."""
    data = photo.file.read(MAX_PHOTO_BYTES + 1)  # One byte over is enough to know it's too big.
    attempt, trip, needs_check = accept_attempt(db, link, form, data)
    if needs_check:
        background_tasks.add_task(run_check, attempt.id)
    return attempt_out(attempt, trip)


@router.get("/attempts/{attempt_id}", response_model=AttemptOut)
def get_attempt(
    attempt_id: UUID,
    link: Annotated[DriverLink, Depends(valid_driver_link)],
    db: Annotated[Session, Depends(get_db)],
) -> AttemptOut:
    sweep_stuck_attempts(db, link.trip_id)
    attempt = db.get(PodAttempt, attempt_id)
    if attempt is None or attempt.trip_id != link.trip_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND)  # The same for another trip's attempt.
    return attempt_out(attempt, db.get_one(Trip, link.trip_id))
