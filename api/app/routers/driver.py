from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.driver_links import valid_driver_link
from app.models import Client, DriverLink, Trip, Vehicle
from app.schemas import DriverTripOut

router = APIRouter(prefix="/driver")


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
