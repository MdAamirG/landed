"""The daily trip file, through the HTTP API (story 78, spec assumption 15).

Each test builds its own file, with a client and branch of its own, so tests share nothing.
Expected values are written out by hand from the rows.
"""

import csv
import io
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.models import AuditEvent, Branch, Client, Driver, DriverLink, ImportBatch, Role, Trip, Vehicle
from app.trip_import import COLUMNS
from tests.factories import make_trip, make_user, unique_digits

PASSWORD = "correct horse battery"


@pytest.fixture
def signed_in(api_client, db):
    user = make_user(db, Role.BILLING_EXECUTIVE, password=PASSWORD)
    api_client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    return user


@pytest.fixture
def places(db) -> tuple[str, str]:
    """A client and a branch the file can name."""
    tag = unique_digits(8)
    client = Client(name=f"Import client {tag}", tally_ledger_name=f"Import client {tag}")
    branch = Branch(name=f"Import branch {tag}")
    db.add_all([client, branch])
    db.commit()
    return client.name, branch.name


def row(places: tuple[str, str], **overrides: str) -> dict[str, str]:
    """One good row, as the office's file would write it. Sample data only."""
    tag = unique_digits(8)
    client, branch = places
    values = {
        "trip_code": f"TRP-{tag}",
        "client": client,
        "branch": branch,
        "origin": "Chhatrapati Sambhajinagar",
        "destination": "Latur",
        "lr_number": f"LR-{tag}",
        "eway_bill_no": unique_digits(12),
        "vehicle": f"MH20 T{tag}",
        "ownership": "hired",
        "driver_name": "Sample Import Driver",
        "driver_phone": f"9{unique_digits(9)}",
        "driver_language": "mr",
        "qty_dispatched": "400",
        "qty_unit": "bags",
        "freight_rupees": "33800",
        "consignee_name": "Sample Consignee Latur",
        "consignee_phone": "9000000031",
        "consignee_lat": "18.4088",
        "consignee_lng": "76.5604",
        "dispatched_at": "2026-11-06 07:30",
        "expected_delivery_at": "2026-11-07 18:00",
    }
    return values | overrides


def csv_file(rows: list[dict[str, str]]) -> bytes:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode()


def check(client, data: bytes, filename: str = "trips_2026-11-06.csv"):
    return client.post("/api/trips/import/check", files={"file": (filename, data, "text/csv")})


@pytest.mark.usefixtures("signed_in")
def test_a_good_row_checks_as_ready_and_nothing_is_stored(api_client, db, places):
    good = row(places, freight_rupees="33800", eway_bill_no="3410 9922 0418")
    trips_before = db.scalar(select(func.count()).select_from(Trip))
    batches_before = db.scalar(select(func.count()).select_from(ImportBatch))

    response = check(api_client, csv_file([good]))

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "trips_2026-11-06.csv"
    assert body["rows_total"] == 1
    assert body["rows_ok"] == 1
    [checked] = body["rows"]
    assert checked["trip_code"] == good["trip_code"]
    assert checked["eway_bill_no"] == "341099220418"  # The spaces a person types are dropped.
    assert checked["freight_paise"] == 3_380_000
    assert checked["ownership"] == "hired"
    assert checked["problems"] == []
    assert db.scalar(select(func.count()).select_from(Trip)) == trips_before
    assert db.scalar(select(func.count()).select_from(ImportBatch)) == batches_before


def problems_by_code(body: dict) -> dict[str, list[str]]:
    return {checked["trip_code"]: checked["problems"] for checked in body["rows"]}


@pytest.mark.usefixtures("signed_in")
def test_a_row_without_an_e_way_bill_is_rejected_and_the_rest_are_ready(api_client, places):
    good = row(places)
    no_eway = row(places, eway_bill_no="")
    short_eway = row(places, eway_bill_no="34109922")

    body = check(api_client, csv_file([good, no_eway, short_eway])).json()

    assert body["rows_total"] == 3
    assert body["rows_ok"] == 1
    assert problems_by_code(body) == {
        good["trip_code"]: [],
        no_eway["trip_code"]: ["Add the e-way bill"],
        short_eway["trip_code"]: ["The e-way bill must be 12 digits"],
    }
    # A rejected row still shows its freight, so the executive can tell which trip it is.
    assert body["rows"][1]["freight_paise"] == 3_380_000


@pytest.mark.usefixtures("signed_in")
def test_a_repeated_lr_is_rejected_whether_on_file_or_earlier_in_the_file(api_client, db, places):
    on_file = make_trip(db)
    first = row(places)
    repeat = row(places, lr_number=first["lr_number"])
    old_lr = row(places, lr_number=on_file.lr_number)

    body = check(api_client, csv_file([first, repeat, old_lr])).json()

    assert problems_by_code(body) == {
        first["trip_code"]: [],
        repeat["trip_code"]: [f"Same LR as {first['trip_code']}"],
        old_lr["trip_code"]: [f"LR {on_file.lr_number} is already on {on_file.trip_code}"],
    }


@pytest.mark.usefixtures("signed_in")
def test_a_rejected_row_does_not_claim_its_lr_so_a_corrected_copy_can_go_in(api_client, places):
    broken = row(places, freight_rupees="lots")
    corrected = row(places, lr_number=broken["lr_number"])

    body = check(api_client, csv_file([broken, corrected])).json()

    assert problems_by_code(body) == {
        broken["trip_code"]: ["The freight must be an amount in rupees"],
        corrected["trip_code"]: [],
    }


@pytest.mark.usefixtures("signed_in")
def test_a_trip_code_already_on_file_or_twice_in_the_file_is_rejected(api_client, db, places):
    on_file = make_trip(db)
    old_code = row(places, trip_code=on_file.trip_code)
    first = row(places)
    twice = row(places, trip_code=first["trip_code"])

    rows = check(api_client, csv_file([old_code, first, twice])).json()["rows"]

    assert [checked["problems"] for checked in rows] == [
        [f"{on_file.trip_code} is already on file"],
        [],
        [f"{first['trip_code']} is in the file twice"],
    ]


@pytest.mark.usefixtures("signed_in")
def test_a_row_naming_an_unknown_client_or_branch_is_rejected(api_client, places):
    unknown_client = row(places, client="Company Nobody")
    unknown_branch = row(places, branch="Atlantis")
    other_case = row(places, client=places[0].upper())  # People type case differently.

    body = check(api_client, csv_file([unknown_client, unknown_branch, other_case])).json()

    assert problems_by_code(body) == {
        unknown_client["trip_code"]: ["No client called Company Nobody"],
        unknown_branch["trip_code"]: ["No branch called Atlantis"],
        other_case["trip_code"]: [],
    }
    assert body["rows"][2]["client_name"] == places[0]  # Shown as the office set it up.


def import_file(client, data: bytes, filename: str = "trips_2026-11-06.csv"):
    return client.post("/api/trips/import", files={"file": (filename, data, "text/csv")})


def trip_by_code(db, code: str) -> Trip | None:
    return db.scalar(select(Trip).where(Trip.trip_code == code))


def events(db, trip: Trip) -> list[str]:
    return list(
        db.scalars(select(AuditEvent.action).where(AuditEvent.trip_id == trip.id).order_by(AuditEvent.id))
    )


def test_an_import_adds_the_good_rows_each_with_a_driver_link_and_a_mock_sms(
    api_client, db, places, signed_in
):
    good = row(
        places,
        freight_rupees="33,800",
        qty_dispatched="24.5",
        dispatched_at="2026-11-06 07:30",
        expected_delivery_at="2026-11-07 18:00",
    )
    no_eway = row(places, eway_bill_no="")

    response = import_file(api_client, csv_file([good, no_eway]))

    assert response.status_code == 200
    body = response.json()
    assert body["rows_ok"] == 1
    assert [checked["imported"] for checked in body["rows"]] == [True, False]

    trip = trip_by_code(db, good["trip_code"])
    assert trip is not None
    assert trip.pod_status == "awaiting_pod"
    assert trip.freight_paise == 3_380_000
    assert trip.qty_dispatched == Decimal("24.5")
    # India time in the file, UTC in the database: 07:30 IST is 02:00 UTC.
    assert trip.dispatched_at == datetime(2026, 11, 6, 2, 0, tzinfo=UTC)
    assert trip.expected_delivery_at == datetime(2026, 11, 7, 12, 30, tzinfo=UTC)
    assert events(db, trip) == ["trip_imported", "driver_link_created", "sms_sent"]
    assert db.scalar(select(func.count()).select_from(DriverLink).where(DriverLink.trip_id == trip.id)) == 1
    assert trip_by_code(db, no_eway["trip_code"]) is None

    batch = db.get(ImportBatch, UUID(body["import_batch_id"]))
    assert batch.filename == "trips_2026-11-06.csv"
    assert batch.uploaded_by == signed_in.id
    assert (batch.rows_total, batch.rows_ok) == (2, 1)
    assert batch.errors == [
        {
            "first_line": 3,
            "trip_code": no_eway["trip_code"],
            "lr_number": no_eway["lr_number"],
            "problems": ["Add the e-way bill"],
        }
    ]


@pytest.mark.usefixtures("signed_in")
def test_importing_the_same_file_twice_adds_nothing_the_second_time(api_client, db, places):
    data = csv_file([row(places), row(places)])
    import_file(api_client, data)

    again = import_file(api_client, data).json()

    assert again["rows_ok"] == 0
    assert all("is already on file" in checked["problems"][0] for checked in again["rows"])


@pytest.mark.usefixtures("signed_in")
def test_a_new_vehicle_and_driver_are_created_on_first_sight_and_reused_after(
    api_client, db, places
):
    known = make_trip(db)  # Its lorry is own, its driver's phone is 9000000000.
    known_vehicle = db.get(Vehicle, known.vehicle_id)
    new_plate = f"MH20 N{unique_digits(6)}"
    new_phone = f"8{unique_digits(9)}"
    first = row(places, vehicle=new_plate, ownership="hired", driver_phone=new_phone)
    second = row(places, vehicle=new_plate.replace(" ", "").lower(), driver_phone=new_phone)
    on_known = row(
        places,
        vehicle=known_vehicle.registration_no,
        ownership="hired",  # The fleet's record says own, and wins.
        driver_phone="9000000000",
        driver_name="Another Name",
    )

    body = import_file(api_client, csv_file([first, second, on_known])).json()

    assert [checked["ownership"] for checked in body["rows"]] == ["hired", "hired", "own"]
    first_trip, second_trip, known_trip = (
        trip_by_code(db, r["trip_code"]) for r in (first, second, on_known)
    )
    assert first_trip.vehicle_id == second_trip.vehicle_id
    assert db.get(Vehicle, first_trip.vehicle_id).registration_no == new_plate
    assert first_trip.driver_id == second_trip.driver_id
    driver = db.get(Driver, first_trip.driver_id)
    assert (driver.name, driver.phone, driver.language) == ("Sample Import Driver", new_phone, "mr")
    assert known_trip.vehicle_id == known.vehicle_id
    assert db.scalar(select(Driver.phone).where(Driver.id == known_trip.driver_id)) == "9000000000"
    assert db.get(Driver, known_trip.driver_id).name != "Another Name"


@pytest.mark.usefixtures("signed_in")
def test_responses_carry_no_consignee_or_driver_contact(api_client, places):
    good = row(places, consignee_phone="9876543210", driver_phone="9123456780")
    data = csv_file([good])

    for response in (check(api_client, data), import_file(api_client, data)):
        text = response.text
        assert good["consignee_name"] not in text
        assert "9876543210" not in text
        assert good["driver_name"] not in text
        assert "9123456780" not in text


@pytest.mark.usefixtures("signed_in")
def test_the_driver_link_comes_back_only_in_demo_mode(api_client, places, monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", False)
    [plain] = import_file(api_client, csv_file([row(places)])).json()["rows"]
    monkeypatch.setattr(settings, "demo_mode", True)
    [demo] = import_file(api_client, csv_file([row(places)])).json()["rows"]

    assert plain["driver_token"] is None
    assert demo["driver_token"]
    assert api_client.get("/api/driver/trip", headers={"Authorization": f"Bearer {demo['driver_token']}"}).status_code == 200


@pytest.mark.usefixtures("signed_in")
@pytest.mark.parametrize(
    ("data", "detail"),
    [
        (b"trip_code,client\nTRP-1,Company B\n", "The file has no column for branch"),
        (b"\xff\xfe\x00not text", "This isn't a CSV file"),
        (",".join(COLUMNS).encode() + b"\n,,,\n", "The file has no trips in it."),
    ],
)
def test_a_file_that_cant_be_read_as_trips_is_refused_whole(api_client, data, detail):
    response = check(api_client, data)

    assert response.status_code == 400
    assert response.json()["detail"].startswith(detail)


@pytest.mark.usefixtures("signed_in")
def test_extra_columns_and_blank_lines_are_ignored_and_lines_are_counted_from_the_file(
    api_client, places
):
    first, second = row(places), row(places, eway_bill_no="")
    first["notes"] = "line one\nline two"  # A quoted cell running over two lines.
    second["notes"] = ""
    data = csv_file([first, second]).replace(b"\r\n" + second["trip_code"].encode(), b"\r\n\r\n" + second["trip_code"].encode())

    rows = check(api_client, data).json()["rows"]

    assert [(checked["first_line"], checked["last_line"]) for checked in rows] == [(2, 3), (5, 5)]


@pytest.mark.usefixtures("signed_in")
def test_blank_cells_are_reported_by_name_not_as_a_server_error(api_client, places):
    blank = row(places, freight_rupees="", eway_bill_no="")

    response = check(api_client, csv_file([blank]))

    assert response.status_code == 200
    [checked] = response.json()["rows"]
    assert checked["problems"] == ["Add the e-way bill", "Add the freight"]
    assert checked["freight_paise"] is None
