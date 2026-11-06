"""Small builders, so each test makes its own rows and shares nothing with other tests."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import Branch, Client, Driver, Role, Trip, User, Vehicle
from app.rules import INDIA
from app.schemas import PodReading


def unique_digits(length: int) -> str:
    """Random digits, for values that must be unique across tests."""
    return str(uuid4().int)[:length]


def clean_reading(trip: Trip, **overrides) -> PodReading:
    """What the AI would read from a perfect POD for this trip. Overrides replace whole fields."""
    today = datetime.now(UTC).astimezone(INDIA).date()
    values = {
        "lr_number": {"value": trip.lr_number, "confidence": 0.99},
        "consignee_stamp": {"value": "present", "confidence": 0.99},
        "quantity_received": {
            "number": float(trip.qty_dispatched),
            "unit": trip.qty_unit,
            "confidence": 0.99,
        },
        "remarks": {"text": "", "kind": "none", "confidence": 0.99},
        "delivery_date": {"value": today, "confidence": 0.99},
        "signature": {"value": "present", "confidence": 0.99},
        "image_quality": "ok",
    }
    return PodReading.model_validate(values | overrides)


def make_user(
    session: Session,
    role: Role = Role.BILLING_EXECUTIVE,
    password: str = "unused",
    email: str | None = None,
) -> User:
    """An office user. Hashes the password for real, so the user can sign in through the API."""
    tag = unique_digits(8)
    user = User(
        name=f"Test user {tag}",
        email=email or f"{tag}@example.com",
        password_hash=hash_password(password),
        role=role,
    )
    session.add(user)
    session.commit()
    return user


def make_trip(session: Session, **overrides) -> Trip:
    """A valid trip with its own client, branch, vehicle and driver. Sample data only."""
    tag = unique_digits(8)
    client = Client(name=f"Test client {tag}", tally_ledger_name=f"Test client {tag}")
    branch = Branch(name=f"Test branch {tag}")
    vehicle = Vehicle(registration_no=f"TEST {tag}", ownership="own")
    driver = Driver(name=f"Test driver {tag}", phone="9000000000", language="hi")
    session.add_all([client, branch, vehicle, driver])
    session.flush()

    now = datetime.now(UTC)
    values = {
        "trip_code": f"TRP-{tag}",
        "client_id": client.id,
        "branch_id": branch.id,
        "vehicle_id": vehicle.id,
        "driver_id": driver.id,
        "origin": "Chhatrapati Sambhajinagar",
        "destination": "Nagpur",
        "lr_number": f"LR-{tag}",
        "eway_bill_no": unique_digits(12),
        "qty_dispatched": 100,
        "qty_unit": "bags",
        "freight_paise": 3_200_000,
        "consignee_name": "Test Consignee",
        "consignee_phone": "9000000001",
        "consignee_lat": 21.1458,
        "consignee_lng": 79.0882,
        "dispatched_at": now - timedelta(days=2),
        "expected_delivery_at": now,
    }
    trip = Trip(**(values | overrides))
    session.add(trip)
    # Commit, not flush: API requests run on their own session and must be able to see this row.
    session.commit()
    return trip
