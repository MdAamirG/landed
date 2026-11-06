from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.driver_links import valid_driver_link
from app.intake import MAX_PHOTO_BYTES, accept_attempt, run_check
from app.models import Client, DriverLink, PodAttempt, Trip, Vehicle
from app.schemas import AttemptForm, AttemptOut, DriverTripOut

router = APIRouter(prefix="/driver")


def attempt_out(attempt: PodAttempt, trip: Trip) -> AttemptOut:
    return AttemptOut(
        attempt_id=attempt.id,
        attempt_no=attempt.attempt_no,
        outcome=attempt.outcome,
        reason_codes=attempt.reason_codes,
        retakes_used=trip.retakes_used,
    )


@router.get("/trip", response_model=DriverTripOut)
def get_trip(
    link: Annotated[DriverLink, Depends(valid_driver_link)],
    db: Annotated[Session, Depends(get_db)],
) -> DriverTripOut:
    """The one trip this link opens. The token picks the trip, so no trip ID is ever accepted."""
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
    attempt, trip, is_new = accept_attempt(db, link, form, data)
    if is_new:
        background_tasks.add_task(run_check, attempt.id)
    return attempt_out(attempt, trip)


@router.get("/attempts/{attempt_id}", response_model=AttemptOut)
def get_attempt(
    attempt_id: UUID,
    link: Annotated[DriverLink, Depends(valid_driver_link)],
    db: Annotated[Session, Depends(get_db)],
) -> AttemptOut:
    attempt = db.get(PodAttempt, attempt_id)
    if attempt is None or attempt.trip_id != link.trip_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND)  # The same for another trip's attempt.
    return attempt_out(attempt, db.get_one(Trip, link.trip_id))
