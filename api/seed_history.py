"""About 200 backdated trips, so the dashboard has real data to compute. Sample data only.

The figures aren't stored anywhere: every one is computed from these rows, the same way as for
real trips. The numbers below only shape the sample, and all of them are assumptions. A fixed
random seed means every run makes the same trips, and running it twice adds nothing.

Most trips share one photo, to keep this small and quick. Its LR number won't match theirs, which
is fine for figures. TRP-66128 and TRP-66137 have their own sheets, because Review shows them first.
"""

import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ActorType,
    AuditEvent,
    Branch,
    Client,
    Driver,
    Language,
    Ownership,
    PodStatus,
    Trip,
    Vehicle,
)
from app.rules import ReasonCode
from seed_trips import (
    ORIGIN,
    SHEET_DATE,
    SampleTrip,
    Sheet,
    add_attempt,
    get_or_create,
    seed_trip,
)

SOURCE = "history seed"
RANDOM_SEED = 66120  # Any fixed number. This one is the brief's first trip.
HISTORY_TRIPS = 195
OLDEST_DAYS = 30
NEWEST_DAYS = 3.5  # Past the slowest upload below, so no photo arrives in the future.

ON_TIME_SHARE = 0.76  # Below the 80% target: the dashboard should have something to show.
ON_TIME_UPLOAD_HOURS = (0.1, 20)
LATE_UPLOAD_HOURS = (25, 72)

# Typical days from POD to invoice, set around the approved design's figures.
INVOICE_DAYS = {"Sambhajinagar": 4.1, "Pune": 5.8, "Nagpur": 6.9}
INVOICE_SPREAD_DAYS = 1.5

SHARED_SHEET = Sheet("clean.jpg")

# Each branch's destinations, with the map position the location check would use.
PLACES = {
    "Sambhajinagar": {
        "Jalna": (19.8347, 75.8816),
        "Beed": (18.9891, 75.7601),
        "Nagpur": (21.1458, 79.0882),
    },
    "Pune": {
        "Pune": (18.5204, 73.8567),
        "Indore": (22.7196, 75.8577),
        "Nashik": (19.9975, 73.7898),
    },
    "Nagpur": {
        "Raipur": (21.2514, 81.6296),
        "Akola": (20.7002, 77.0082),
        "Amravati": (20.9374, 77.7796),
    },
}

# Each client's usual load, which is what its POD quantity has to match.
LOADS = {"Company B": (800, "bags"), "Company C": (24, "tonnes"), "Company D": (400, "cartons")}

VEHICLES = [
    ("MH20 EL 4521", Ownership.OWN),
    ("MH20 GT 7718", Ownership.OWN),
    ("MH17 BY 3092", Ownership.HIRED),
    ("MH20 CK 1180", Ownership.HIRED),
    ("MH20 DX 6604", Ownership.OWN),
    ("MH20 FA 2093", Ownership.OWN),
    ("MH04 KL 5527", Ownership.HIRED),
    ("MH31 BR 8846", Ownership.OWN),
]


@dataclass(frozen=True)
class TripPlan:
    """Who ran a trip and where. The design's missing-POD rows are written out this way."""

    code: str
    registration_no: str
    client: str
    destination: str
    branch: str
    hours_overdue: float = 0  # For a trip with no photo. Negative: it isn't due yet.


MISSING_ROWS = [  # The rows of Dashboard.html.
    TripPlan("TRP-66144", "MH20 EL 4521", "Company B", "Jalna", "Sambhajinagar", 31),
    TripPlan("TRP-66147", "MH17 BY 3092", "Company D", "Indore", "Pune", 26),
    TripPlan("TRP-66149", "MH20 CK 1180", "Company C", "Raipur", "Nagpur", 25),
    TripPlan("TRP-66151", "MH20 GT 7718", "Company C", "Pune", "Pune", 9),
    TripPlan("TRP-66153", "MH20 DX 6604", "Company B", "Akola", "Nagpur", 5),
    TripPlan("TRP-66155", "MH20 EL 4521", "Company B", "Beed", "Sambhajinagar", 2),
]

# Due later, so these must stay off the list and out of the figures.
ON_THE_ROAD = [
    TripPlan("TRP-66156", "MH20 FA 2093", "Company B", "Nagpur", "Sambhajinagar", -6),
    TripPlan("TRP-66157", "MH04 KL 5527", "Company D", "Indore", "Pune", -20),
    TripPlan("TRP-66158", "MH31 BR 8846", "Company C", "Raipur", "Nagpur", -30),
    TripPlan("TRP-66159", "MH20 CK 1180", "Company C", "Nashik", "Pune", -44),
]

REVIEW_AND_DISPUTE = [
    SampleTrip(
        code="TRP-66137",
        client="Company B",
        registration_no="MH20 DX 6604",
        ownership=Ownership.OWN,
        destination="Akola",
        freight_paise=2_950_000,
        status=PodStatus.NEEDS_REVIEW,
        status_reason=ReasonCode.DAMAGE_REMARK,
        brief_remark=None,
        branch="Nagpur",
        driver="Sample Driver Eight",
        driver_phone="9000000018",
        driver_language=Language.MARATHI,
        lr_number="48209",
        eway_bill_no="341099217741",
        qty_dispatched=800,
        qty_unit="bags",
        consignee_name="Sample Consignee Akola",
        consignee_phone="9000000027",
        consignee_lat=20.7002,
        consignee_lng=77.0082,
        sheet=Sheet(
            "trp-66137.jpg",
            (ReasonCode.DAMAGE_REMARK,),
            remark="12 bags torn",
            remark_kind="damage",
            paper_date=SHEET_DATE,
        ),
    ),
    SampleTrip(
        code="TRP-66128",
        client="Company C",
        registration_no="MH20 CK 1180",
        ownership=Ownership.HIRED,
        destination="Raipur",
        freight_paise=3_400_000,
        status=PodStatus.DISPUTED,
        status_reason=None,
        brief_remark=None,
        branch="Nagpur",
        driver="Sample Driver Nine",
        driver_phone="9000000019",
        driver_language=Language.HINDI,
        lr_number="48196",
        eway_bill_no="341099217722",
        qty_dispatched=24,
        qty_unit="tonnes",
        consignee_name="Sample Consignee Raipur",
        consignee_phone="9000000028",
        consignee_lat=21.2514,
        consignee_lng=81.6296,
        sheet=Sheet("trp-66128.jpg", paper_date=SHEET_DATE),
    ),
]


class Fleet:
    """The rows every trip points to, looked up once rather than once per trip."""

    def __init__(self, session: Session):
        self.clients = {
            name: get_or_create(session, Client, {"name": name}, tally_ledger_name=name).id
            for name in LOADS
        }
        self.branches = {
            name: get_or_create(session, Branch, {"name": name}).id for name in PLACES
        }
        self.vehicles = {
            number: get_or_create(
                session, Vehicle, {"registration_no": number}, ownership=ownership
            ).id
            for number, ownership in VEHICLES
        }
        # One driver for each vehicle, so a vehicle's trips read like one person's.
        self.drivers = {
            number: get_or_create(
                session,
                Driver,
                {"phone": f"90000001{position:02d}"},
                name=f"Sample Driver {position + 10}",
                language=Language.HINDI if position % 2 else Language.MARATHI,
            ).id
            for position, (number, _) in enumerate(VEHICLES)
        }


def add_history_trip(
    session: Session,
    fleet: Fleet,
    rng: random.Random,
    number: int,
    plan: TripPlan,
    expected_delivery_at: datetime,
    status: PodStatus,
) -> Trip:
    quantity, unit = LOADS[plan.client]
    lat, lng = PLACES[plan.branch][plan.destination]
    trip = Trip(
        trip_code=plan.code,
        client_id=fleet.clients[plan.client],
        branch_id=fleet.branches[plan.branch],
        vehicle_id=fleet.vehicles[plan.registration_no],
        driver_id=fleet.drivers[plan.registration_no],
        origin=ORIGIN,
        destination=plan.destination,
        lr_number=str(47000 + number),
        eway_bill_no=f"3410993{number:05d}",
        qty_dispatched=Decimal(quantity),
        qty_unit=unit,
        freight_paise=rng.randrange(22_000, 44_500, 500) * 100,
        consignee_name=f"Sample Consignee {plan.destination}",
        consignee_phone=f"90000002{number % 100:02d}",
        consignee_lat=lat,
        consignee_lng=lng,
        dispatched_at=expected_delivery_at - timedelta(days=2),
        expected_delivery_at=expected_delivery_at,
        pod_status=status,
    )
    session.add(trip)
    session.flush()  # Written now: the models have no relationships to order the inserts by.
    return trip


def history_code(number: int) -> str:
    return f"TRP-{65800 + number}"


def seeded_event(trip_id: UUID, status: PodStatus, at: datetime) -> AuditEvent:
    return AuditEvent(
        trip_id=trip_id,
        actor_type=ActorType.SYSTEM,
        action="seeded",
        to_status=status,
        detail={"source": SOURCE},
        at=at,
    )


def add_delivered_trip(
    session: Session, fleet: Fleet, rng: random.Random, number: int, now: datetime
) -> None:
    branch = rng.choice(list(PLACES))
    destination = rng.choice(list(PLACES[branch]))
    delivered_at = now - timedelta(days=rng.uniform(NEWEST_DAYS, OLDEST_DAYS))

    on_time = rng.random() < ON_TIME_SHARE
    upload_hours = rng.uniform(*(ON_TIME_UPLOAD_HOURS if on_time else LATE_UPLOAD_HOURS))
    received_at = delivered_at + timedelta(hours=upload_hours)
    invoice_days = INVOICE_DAYS[branch] + rng.uniform(-INVOICE_SPREAD_DAYS, INVOICE_SPREAD_DAYS)
    invoiced_at = received_at + timedelta(days=invoice_days)

    # Anything whose invoice would land in the future is still in the billing queue.
    status = PodStatus.INVOICED if invoiced_at < now else PodStatus.VERIFIED
    plan = TripPlan(
        history_code(number), rng.choice(VEHICLES)[0], rng.choice(list(LOADS)), destination, branch
    )
    due_at = delivered_at + timedelta(hours=rng.uniform(0, 6))
    trip = add_history_trip(session, fleet, rng, number, plan, due_at, status)
    trip.verified_at = received_at
    trip.invoiced_at = invoiced_at if status == PodStatus.INVOICED else None
    session.add(seeded_event(trip.id, status, received_at))
    add_attempt(session, trip, SHARED_SHEET, PodStatus.VERIFIED, delivered_at, received_at)


def add_waiting_trip(
    session: Session, fleet: Fleet, rng: random.Random, number: int, plan: TripPlan, now: datetime
) -> None:
    due_at = now - timedelta(hours=plan.hours_overdue)
    trip = add_history_trip(session, fleet, rng, number, plan, due_at, PodStatus.AWAITING_POD)
    session.add(seeded_event(trip.id, PodStatus.AWAITING_POD, trip.dispatched_at))


def seed_history(session: Session, commit_every: int | None = None) -> None:
    """Add the history to the session. The caller commits.

    With commit_every, it also commits after that many trips, so a dropped connection loses one
    small batch, not the lot. Trips that exist are skipped, so a second run finishes the job.
    """
    now = datetime.now(UTC)
    rng = random.Random(RANDOM_SEED)
    known = set(session.scalars(select(Trip.trip_code)))
    fleet = Fleet(session)

    for sample in REVIEW_AND_DISPUTE:
        seed_trip(session, sample, now, SOURCE)

    for number in range(HISTORY_TRIPS):
        if history_code(number) not in known:
            add_delivered_trip(session, fleet, rng, number, now)
        if commit_every and (number + 1) % commit_every == 0:
            session.commit()

    for number, plan in enumerate(MISSING_ROWS + ON_THE_ROAD, start=HISTORY_TRIPS):
        if plan.code not in known:
            add_waiting_trip(session, fleet, rng, number, plan, now)
    session.flush()
