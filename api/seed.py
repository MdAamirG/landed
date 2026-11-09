"""Seeds the brief's sample data, the demo trips and the history. Safe to run twice: rows that exist stay as they are.

Run with: cd api && python seed.py

Reviewers' clicks move the sample trips on (an approve, a retake, an export), and seeded times age
with the clock. To start again from the brief's states, run: cd api && python seed.py --fresh
That empties every table first, so it refuses unless DEMO_MODE is on.

The trip ID, client, vehicle, destination, freight, status and remark come from the brief.
LR numbers, e-way bill numbers and the 400 cartons match the approved screens in design/screens.
Everything else is an assumption, because the brief's sample shows none of it: sample names,
phone numbers, the other quantities, branches and times. No real person's data.
"""

import argparse
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import DEMO_EMAILS, hash_password
from app.config import settings
from app.db import SessionLocal
from app.models import Base, Language, Ownership, PodStatus, Role, User
from app.rules import ReasonCode
from seed_demo import seed_demo
from seed_history import seed_history
from seed_trips import SHEET_DATE, SampleTrip, Sheet, get_or_create, seed_trip

# Not a secret: deployment.md gives reviewers the demo logins, as the brief asks.
DEMO_PASSWORD = "landed-demo"


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
        sheet=Sheet("trp-66120.jpg", paper_date=SHEET_DATE),
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
        sheet=Sheet(
            "trp-66134.jpg", (ReasonCode.STAMP_MISSING,), stamp="absent", paper_date=SHEET_DATE
        ),
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
        sheet=Sheet(
            "trp-66141.jpg",
            (ReasonCode.SHORTAGE_REMARK, ReasonCode.QTY_SHORT),
            qty_received=394,
            remark="Short by 6 cartons",
            remark_kind="shortage",
            paper_date=SHEET_DATE,
        ),
    ),
]

DEMO_USERS = [
    ("Sample Billing Executive", DEMO_EMAILS[Role.BILLING_EXECUTIVE], Role.BILLING_EXECUTIVE),
    ("Sample Operations Head", DEMO_EMAILS[Role.OPERATIONS_HEAD], Role.OPERATIONS_HEAD),
]


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


def clear_everything(session: Session) -> None:
    """Empties every table, users included; the seed adds the demo logins back.

    Only for a demo database. DEMO_MODE is the switch that says the data is sample data, so with it
    off this refuses rather than risk deleting real trips. TRUNCATE ... CASCADE saves ordering the
    tables by foreign key, and it runs in the caller's transaction, so a seed that fails afterwards
    rolls the old data back.
    """
    if not settings.demo_mode:
        raise RuntimeError("Not emptying the database: DEMO_MODE is off, so it may hold real trips")
    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    session.execute(text(f"TRUNCATE {tables} CASCADE"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--fresh", action="store_true", help="empty every table first (demo databases only)"
    )
    fresh = parser.parse_args().fresh

    with SessionLocal() as session:
        if fresh:
            clear_everything(session)
        seed(session)
        seed_demo(session, SAMPLE_TRIPS)
        seed_history(session)
        session.commit()  # One transaction: the old rows go only if the new ones arrive.
    print("Fresh seed complete." if fresh else "Seed complete.")


if __name__ == "__main__":
    main()
