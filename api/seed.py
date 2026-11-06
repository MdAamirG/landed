"""Seeds the brief's sample data. Safe to run twice: rows that already exist are left alone.

Run with: cd api && python seed.py

The trip ID, client, vehicle, destination, freight, status and remark come from the brief.
LR numbers, e-way bill numbers and the 400 cartons match the approved screens in design/screens.
Everything else is an assumption, because the brief's sample shows none of it: sample names,
phone numbers, the other quantities, branches and times. No real person's data.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import DEMO_EMAILS, hash_password
from app.db import SessionLocal
from app.models import (
    ActorType,
    AuditEvent,
    Branch,
    Client,
    Driver,
    Language,
    Ownership,
    PodStatus,
    Role,
    Trip,
    User,
    Vehicle,
)
from app.rules import ReasonCode

# Not a secret: deployment.md gives reviewers the demo logins, as the brief asks.
DEMO_PASSWORD = "landed-demo"

ORIGIN = "Chhatrapati Sambhajinagar"


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


SAMPLE_TRIPS = [
    SampleTrip(
        code="TRP-66120",
        client="Company B",
        registration_no="MH20 EL 4521",
        ownership=Ownership.OWN,
        destination="Nagpur",
        freight_paise=3_850_000,
        status=PodStatus.VERIFIED,
        status_reason=None,
        brief_remark=None,
        branch="Sambhajinagar",
        driver="Sample Driver One",
        driver_phone="9000000011",
        driver_language=Language.HINDI,
        lr_number="48190",
        eway_bill_no="341099217690",
        qty_dispatched=800,
        qty_unit="bags",
        consignee_name="Sample Consignee Nagpur",
        consignee_phone="9000000021",
        consignee_lat=21.1458,
        consignee_lng=79.0882,
    ),
    SampleTrip(
        code="TRP-66134",
        client="Company C",
        registration_no="MH20 GT 7718",
        ownership=Ownership.OWN,
        destination="Pune",
        freight_paise=2_600_000,
        status=PodStatus.RETAKE_REQUESTED,
        status_reason=ReasonCode.STAMP_MISSING,
        brief_remark="Stamp not visible",
        branch="Pune",
        driver="Sample Driver Two",
        driver_phone="9000000012",
        driver_language=Language.MARATHI,
        lr_number="48207",
        eway_bill_no="341099217735",
        qty_dispatched=24,
        qty_unit="tonnes",
        consignee_name="Sample Consignee Chakan",
        consignee_phone="9000000022",
        consignee_lat=18.7606,
        consignee_lng=73.8636,
    ),
    SampleTrip(
        code="TRP-66141",
        client="Company D",
        registration_no="MH17 BY 3092",
        ownership=Ownership.HIRED,
        destination="Indore",
        freight_paise=4_120_000,
        status=PodStatus.NEEDS_REVIEW,
        status_reason=ReasonCode.SHORTAGE_REMARK,
        brief_remark="Short by 6 cartons",
        branch="Nagpur",
        driver="Sample Driver Three",
        driver_phone="9000000013",
        driver_language=Language.HINDI,
        lr_number="48213",
        eway_bill_no="341099217712",
        qty_dispatched=400,
        qty_unit="cartons",
        consignee_name="Sample Consignee Indore",
        consignee_phone="9000000023",
        consignee_lat=22.7196,
        consignee_lng=75.8577,
    ),
]

DEMO_USERS = [
    ("Sample Billing Executive", DEMO_EMAILS[Role.BILLING_EXECUTIVE], Role.BILLING_EXECUTIVE),
    ("Sample Operations Head", DEMO_EMAILS[Role.OPERATIONS_HEAD], Role.OPERATIONS_HEAD),
]


def get_or_create(session: Session, model, lookup: dict, **values):
    """Find a row by its natural key, or add it. This is what makes the seed repeatable."""
    row = session.scalar(select(model).filter_by(**lookup))
    if row is None:
        row = model(**lookup, **values)
        session.add(row)
        session.flush()
    return row


def seed_trip(session: Session, sample: SampleTrip, now: datetime) -> None:
    if session.scalar(select(Trip.id).filter_by(trip_code=sample.code)):
        return

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
        qty_dispatched=sample.qty_dispatched,
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
            detail={"source": "brief sample data", "remark": sample.brief_remark},
        )
    )


def seed(session: Session) -> None:
    """Add the sample data to the session. The caller commits."""
    now = datetime.now(UTC)
    password_hash = hash_password(DEMO_PASSWORD)

    for name, email, role in DEMO_USERS:
        get_or_create(
            session, User, {"email": email}, name=name, password_hash=password_hash, role=role
        )
    for sample in SAMPLE_TRIPS:
        seed_trip(session, sample, now)
    session.flush()


if __name__ == "__main__":
    with SessionLocal() as session:
        seed(session)
        session.commit()
    print("Seed complete.")
