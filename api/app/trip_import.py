"""The daily trip file (story 78, spec assumption 15).

A check reads the file and says what's wrong with each row, and stores nothing. An import runs the
same check again, because the trips on file may have changed since, then adds the good rows. A bad
row never blocks the rest. Each new trip gets a driver link and a mock SMS.
"""

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import PurePath
from typing import Annotated
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    Field,
    StringConstraints,
    TypeAdapter,
    ValidationError,
    model_validator,
)
from pydantic_core import ErrorDetails
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.driver_links import create_link, demo_token
from app.models import (
    ActorType,
    AuditEvent,
    Branch,
    Client,
    Driver,
    ImportBatch,
    Language,
    Ownership,
    PodStatus,
    Trip,
    User,
    Vehicle,
)
from app.rules import INDIA
from app.status import Actor, send_mock_sms

# About 100 trips a day (2,200 a month in the brief), so these leave plenty of room while stopping
# someone making the server read a huge upload.
MAX_FILE_BYTES = 1_000_000
MAX_ROWS = 1_000


# A cell is text, so each type below says how a person's typing becomes a value.


def without(characters: str) -> BeforeValidator:
    """Drops separators people type into numbers, such as the spaces in "3410 9922 0418"."""
    return BeforeValidator(lambda value: re.sub(f"[{characters}]", "", value))


def india_time_to_utc(moment: datetime) -> datetime:
    """The file is written in India time, so a time without a zone is read as India time."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=INDIA)
    return moment.astimezone(UTC)


Cell = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Phone = Annotated[
    str,
    without(r"\s\-"),
    BeforeValidator(lambda value: value.removeprefix("+91")),
    StringConstraints(pattern=r"^[0-9]{10}$"),
]
IndiaTime = Annotated[datetime, AfterValidator(india_time_to_utc)]
Rupees = Annotated[Decimal, without(","), Field(ge=0, max_digits=12, decimal_places=2)]


def paise(rupees: Decimal) -> int:
    return int(rupees * 100)


rupees_cell = TypeAdapter(Rupees)  # Reads the freight alone, for a row that fails elsewhere.


class TripRowIn(BaseModel):
    """One row of the file. A blank cell is left out before this runs, so it counts as missing."""

    trip_code: Cell
    client: Cell
    branch: Cell
    origin: Cell
    destination: Cell
    lr_number: Cell
    eway_bill_no: Annotated[str, without(r"\s"), StringConstraints(pattern=r"^[0-9]{12}$")]
    # Stored in capitals with single spaces, as the seeded fleet is: "MH20 EL 4521".
    vehicle: Annotated[Cell, AfterValidator(lambda value: " ".join(value.upper().split()))]
    ownership: Ownership
    driver_name: Cell
    driver_phone: Phone
    driver_language: Language = Language.HINDI  # An assumption: most of the brief's drivers.
    qty_dispatched: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    qty_unit: Cell
    freight_rupees: Rupees
    consignee_name: Cell
    consignee_phone: Phone
    consignee_lat: float = Field(ge=-90, le=90)
    consignee_lng: float = Field(ge=-180, le=180)
    dispatched_at: IndiaTime
    expected_delivery_at: IndiaTime

    @model_validator(mode="after")
    def delivery_follows_dispatch(self) -> "TripRowIn":
        if self.expected_delivery_at < self.dispatched_at:
            raise ValueError("Expected delivery is before dispatch")
        return self

    @property
    def freight_paise(self) -> int:
        return paise(self.freight_rupees)


COLUMNS = tuple(TripRowIn.model_fields)
OPTIONAL_COLUMNS = {"driver_language"}

# How each column is named in a problem, and what to say when its cell can't be read.
LABELS = {
    "trip_code": "trip code",
    "client": "client",
    "branch": "branch",
    "origin": "origin",
    "destination": "destination",
    "lr_number": "LR number",
    "eway_bill_no": "e-way bill",
    "vehicle": "vehicle",
    "ownership": "own or hired",
    "driver_name": "driver's name",
    "driver_phone": "driver's phone",
    "driver_language": "driver's language",
    "qty_dispatched": "quantity",
    "qty_unit": "unit",
    "freight_rupees": "freight",
    "consignee_name": "consignee's name",
    "consignee_phone": "consignee's phone",
    "consignee_lat": "consignee's latitude",
    "consignee_lng": "consignee's longitude",
    "dispatched_at": "dispatch time",
    "expected_delivery_at": "expected delivery",
}
UNREADABLE = {
    "eway_bill_no": "The e-way bill must be 12 digits",
    "ownership": "Own or hired must say own or hired",
    "driver_phone": "The driver's phone must be 10 digits",
    "consignee_phone": "The consignee's phone must be 10 digits",
    "driver_language": "The driver's language must be hi, mr or en",
    "qty_dispatched": "The quantity must be a number above 0",
    "freight_rupees": "The freight must be an amount in rupees",
    "dispatched_at": "Write the dispatch time like 2026-11-06 07:30",
    "expected_delivery_at": "Write expected delivery like 2026-11-07 18:00",
}


def problem(error: ErrorDetails) -> str:
    """Pydantic's messages are for developers, so each becomes a sentence a billing clerk can act on."""
    if not error["loc"]:  # A check across columns, which carries its own sentence.
        return str(error["ctx"]["error"])
    column = str(error["loc"][0])
    if error["type"] == "missing":
        return f"Add the {LABELS[column]}"
    return UNREADABLE.get(column, f"Check the {LABELS[column]}")


@dataclass
class RawRow:
    first_line: int  # Lines in the file, which a quoted cell can stretch past one.
    last_line: int
    cells: dict[str, str]  # Only known columns with something in them.


def read_file(data: bytes) -> list[RawRow]:
    """The file's rows, or a 400 that says what's wrong with the file as a whole."""
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The file is over 1 MB. Split it in two.")
    try:
        text = data.decode("utf-8-sig")  # -sig: Excel's "CSV UTF-8" starts with a byte-order mark.
        reader = csv.reader(io.StringIO(text, newline=""))
        header = [name.strip().lower() for name in next(reader, [])]
        missing = [name for name in COLUMNS if name not in header and name not in OPTIONAL_COLUMNS]
        if missing:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"The file has no column for {', '.join(missing)}. Start from the sample file.",
            )

        rows: list[RawRow] = []
        last_line = reader.line_num
        for values in reader:
            first_line, last_line = last_line + 1, reader.line_num
            # Other columns are ignored, so a sheet with extra notes still imports.
            cells = {
                name: value.strip()
                for name, value in zip(header, values)
                if name in COLUMNS and value.strip()
            }
            if not cells:  # A blank line, or the empty rows a spreadsheet leaves at the end.
                continue
            rows.append(RawRow(first_line, last_line, cells))
            if len(rows) > MAX_ROWS:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, f"The file has over {MAX_ROWS} trips. Split it."
                )
    except (UnicodeDecodeError, csv.Error):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "This isn't a CSV file. Save it as CSV UTF-8 and try again."
        ) from None
    if not rows:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The file has no trips in it.")
    return rows


def plate_key(registration_no: str) -> str:
    """"MH20EL4521" and "mh20 el 4521" are the same lorry."""
    return "".join(registration_no.split()).upper()


@dataclass
class CheckedRow:
    """One row's check. The screen sees the first fields; the import uses the rest."""

    first_line: int
    last_line: int
    trip_code: str
    lr_number: str
    eway_bill_no: str
    client_name: str
    destination: str
    registration_no: str
    ownership: str
    freight_paise: int | None
    problems: list[str]
    imported: bool = False
    driver_token: str | None = None
    row: TripRowIn | None = None  # Empty when a cell couldn't be read.
    client_id: UUID | None = None
    branch_id: UUID | None = None
    vehicle: Vehicle | None = field(default=None, repr=False)  # Empty for a new lorry.

    @property
    def ok(self) -> bool:
        return not self.problems


def parse(raw: RawRow) -> tuple[TripRowIn | None, list[str]]:
    try:
        return TripRowIn.model_validate(raw.cells), []
    except ValidationError as error:
        return None, [problem(detail) for detail in error.errors()]


def freight_shown(cell: str | None) -> int | None:
    if cell is None:  # A blank cell: there is nothing to show.
        return None
    try:
        return paise(rupees_cell.validate_python(cell))
    except ValidationError:
        return None


def as_shown(raw: RawRow, problems: list[str]) -> CheckedRow:
    """A row whose cells couldn't all be read shows them as typed, so the person can find it."""
    cells = raw.cells
    return CheckedRow(
        first_line=raw.first_line,
        last_line=raw.last_line,
        trip_code=cells.get("trip_code", ""),
        lr_number=cells.get("lr_number", ""),
        eway_bill_no=cells.get("eway_bill_no", ""),
        client_name=cells.get("client", ""),
        destination=cells.get("destination", ""),
        registration_no=cells.get("vehicle", ""),
        ownership=cells.get("ownership", ""),
        freight_paise=freight_shown(cells.get("freight_rupees")),
        problems=problems,
    )


def check_rows(session: Session, raw_rows: list[RawRow]) -> list[CheckedRow]:
    """Each row's problems, against the trips on file and the rows above it in the file."""
    parsed = [parse(raw) for raw in raw_rows]
    readable = [row for row, _ in parsed if row]

    # The client and branch lists are short and set up by the office, so a row must name one of
    # them (spec assumption 15). Case is forgiven, since people type it differently.
    clients = {client.name.casefold(): client for client in session.scalars(select(Client))}
    branches = {branch.name.casefold(): branch for branch in session.scalars(select(Branch))}
    # The whole fleet is about 340 lorries, so one read is simpler than a lookup per row.
    fleet = {plate_key(vehicle.registration_no): vehicle for vehicle in session.scalars(select(Vehicle))}
    codes_on_file = set(
        session.scalars(
            select(Trip.trip_code).where(Trip.trip_code.in_([row.trip_code for row in readable]))
        )
    )
    lrs_on_file = {
        lr_number: trip_code
        for lr_number, trip_code in session.execute(
            select(Trip.lr_number, Trip.trip_code).where(
                Trip.lr_number.in_([row.lr_number for row in readable])
            )
        )
    }

    # Only a row that will import claims its trip code and LR, so if the first copy of an LR is
    # rejected for another reason, a later corrected copy can still go in.
    claimed_codes: set[str] = set()
    claimed_lrs: dict[str, str] = {}
    checked = []
    for raw, (row, problems) in zip(raw_rows, parsed):
        if row is None:
            checked.append(as_shown(raw, problems))
            continue

        client = clients.get(row.client.casefold())
        branch = branches.get(row.branch.casefold())
        if client is None:
            problems.append(f"No client called {row.client}")
        if branch is None:
            problems.append(f"No branch called {row.branch}")
        if row.trip_code in codes_on_file:
            problems.append(f"{row.trip_code} is already on file")
        elif row.trip_code in claimed_codes:
            problems.append(f"{row.trip_code} is in the file twice")
        if row.lr_number in lrs_on_file:
            problems.append(f"LR {row.lr_number} is already on {lrs_on_file[row.lr_number]}")
        elif row.lr_number in claimed_lrs:
            problems.append(f"Same LR as {claimed_lrs[row.lr_number]}")
        if not problems:
            claimed_codes.add(row.trip_code)
            claimed_lrs[row.lr_number] = row.trip_code

        vehicle = fleet.get(plate_key(row.vehicle))
        checked.append(
            CheckedRow(
                first_line=raw.first_line,
                last_line=raw.last_line,
                trip_code=row.trip_code,
                lr_number=row.lr_number,
                eway_bill_no=row.eway_bill_no,
                client_name=client.name if client else row.client,
                destination=row.destination,
                registration_no=vehicle.registration_no if vehicle else row.vehicle,
                # A known lorry keeps the fleet's record. The row's word only sets up a new one.
                ownership=vehicle.ownership if vehicle else row.ownership,
                freight_paise=row.freight_paise,
                problems=problems,
                row=row,
                client_id=client.id if client else None,
                branch_id=branch.id if branch else None,
                vehicle=vehicle,
            )
        )
    return checked


def stored_filename(filename: str | None) -> str:
    """Only the file's own name, not the folder it came from on someone's computer."""
    return PurePath(filename or "trips.csv").name[:200] or "trips.csv"


def import_rows(
    session: Session, filename: str | None, raw_rows: list[RawRow], user: User
) -> tuple[ImportBatch, list[CheckedRow]]:
    """Adds the good rows as trips, each with a driver link and a mock SMS, in one transaction."""
    checked = check_rows(session, raw_rows)
    good = [row for row in checked if row.ok]
    actor = Actor(ActorType.USER, user.id)

    batch = ImportBatch(
        filename=stored_filename(filename),
        uploaded_by=user.id,
        rows_total=len(checked),
        rows_ok=len(good),
        # No consignee or driver details: the trip code and LR are enough to find the row.
        errors=[
            {
                "first_line": row.first_line,
                "trip_code": row.trip_code,
                "lr_number": row.lr_number,
                "problems": row.problems,
            }
            for row in checked
            if not row.ok
        ],
    )
    session.add(batch)

    try:
        session.flush()
        new_vehicles: dict[str, Vehicle] = {}
        drivers = driver_lookup(session, good)
        for checked_row in good:
            row = checked_row.row
            assert row is not None and checked_row.client_id and checked_row.branch_id
            vehicle = checked_row.vehicle or new_vehicles.get(plate_key(row.vehicle))
            if vehicle is None:  # First sight of this lorry (spec assumption 15).
                vehicle = Vehicle(registration_no=row.vehicle, ownership=row.ownership)
                session.add(vehicle)
                new_vehicles[plate_key(row.vehicle)] = vehicle
            driver = drivers.get(row.driver_phone)
            if driver is None:  # First sight of this driver, known by phone number.
                driver = Driver(
                    name=row.driver_name, phone=row.driver_phone, language=row.driver_language
                )
                session.add(driver)
                drivers[row.driver_phone] = driver
            session.flush()

            trip = Trip(
                trip_code=row.trip_code,
                client_id=checked_row.client_id,
                branch_id=checked_row.branch_id,
                vehicle_id=vehicle.id,
                driver_id=driver.id,
                origin=row.origin,
                destination=row.destination,
                lr_number=row.lr_number,
                eway_bill_no=row.eway_bill_no,
                qty_dispatched=row.qty_dispatched,
                qty_unit=row.qty_unit,
                freight_paise=row.freight_paise,
                consignee_name=row.consignee_name,
                consignee_phone=row.consignee_phone,
                consignee_lat=row.consignee_lat,
                consignee_lng=row.consignee_lng,
                dispatched_at=row.dispatched_at,
                expected_delivery_at=row.expected_delivery_at,
                # A new trip starts here. move_trip() moves an existing trip between statuses,
                # so creating one doesn't go through it; the trip_imported event records it.
                pod_status=PodStatus.AWAITING_POD,
            )
            session.add(trip)
            session.flush()
            session.add(
                AuditEvent(
                    trip_id=trip.id,
                    actor_type=actor.type,
                    actor_id=actor.id,
                    action="trip_imported",
                    to_status=PodStatus.AWAITING_POD,
                    detail={"import_batch_id": str(batch.id)},
                )
            )
            # The SMS goes out at dispatch, so the link has loaded once before a dead zone.
            token = create_link(session, trip, actor, sent=True)
            send_mock_sms(session, trip, actor, {"purpose": "import"})
            checked_row.imported = True
            checked_row.driver_token = demo_token(token)
        session.commit()
    except IntegrityError:
        # Two imports of the same rows at once: the unique trip code or LR stops the second.
        session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Some of these trips were added while you were importing. Check the file again.",
        ) from None
    return batch, checked


def driver_lookup(session: Session, rows: list[CheckedRow]) -> dict[str, Driver]:
    """Drivers already on file, by phone. The phone is what stays the same across trips."""
    phones = [row.row.driver_phone for row in rows if row.row]
    found: dict[str, Driver] = {}
    for driver in session.scalars(select(Driver).where(Driver.phone.in_(phones))):
        found.setdefault(driver.phone, driver)
    return found

