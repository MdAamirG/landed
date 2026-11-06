"""Small builders, so each test makes its own rows and shares nothing with other tests."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import Branch, Client, Driver, Role, Trip, User, Vehicle


def unique_digits(length: int) -> str:
    """Random digits, for values that must be unique across tests."""
    return str(uuid4().int)[:length]


def make_user(session: Session, role: Role = Role.BILLING_EXECUTIVE) -> User:
    """An office user. The hash is a placeholder, because nothing signs in with it."""
    tag = unique_digits(8)
    user = User(
        name=f"Test user {tag}", email=f"{tag}@example.com", password_hash="unused", role=role
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
