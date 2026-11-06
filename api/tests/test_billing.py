"""The billing queue, exports and POD photos, through the HTTP API with the AI reader faked."""

from datetime import UTC, date, datetime
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from sqlalchemy import select

from app.billing import cycle_of
from app.driver_links import create_link
from app.models import AuditEvent, Client, ExportBatch, PodAttempt, Role, Trip
from app.rules import INDIA
from tests.factories import clean_reading, make_trip, make_user
from tests.test_attempts import JPEG, upload
from tests.test_review import PASSWORD, approve, audit, detail, edit, trip_in_review

ANOTHER_PHOTO = JPEG + b"another"


@pytest.fixture
def executive(api_client, db):
    user = make_user(db, Role.BILLING_EXECUTIVE, password=PASSWORD)
    api_client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    return user


def verified_trip(client, db, fake_ai, captured_at=None, **overrides):
    """A trip that reached verified the real way, through a clean photo."""
    trip = make_trip(db, **overrides)
    token = create_link(db, trip)
    db.commit()
    if captured_at is None:
        fake_ai.reading = clean_reading(trip)
        upload(client, token)
    else:
        # The paper's date must match the photo's, or the rule sends it to review.
        paper_date = {"value": captured_at.astimezone(INDIA).date(), "confidence": 0.99}
        fake_ai.reading = clean_reading(trip, delivery_date=paper_date)
        upload(client, token, captured_at=captured_at.isoformat())
    db.expire_all()
    return trip


def shortage_trip(client, db, fake_ai, text="6 cartons short", **overrides):
    trip = trip_in_review(client, db, fake_ai, **overrides)
    remarks = {"text": text, "kind": "shortage"}
    edit(client, trip, "remarks", remarks)
    approve(client, trip)
    db.expire_all()
    return trip


def queue(client, cycle=None):
    return client.get("/api/billing/queue", params={"cycle": cycle} if cycle else {}).json()


def listed_trips(body):
    return [trip for client in body["clients"] for trip in client["trips"]]


def export(client, *trips):
    return client.post("/api/billing/exports", json={"trip_ids": [str(trip.id) for trip in trips]})


def exported_vouchers(client, response):
    xml = client.get(f"/api/billing/exports/{response.json()['id']}/xml").text
    return ET.fromstring(xml).findall(".//VOUCHER")


def status_of(db, trip):
    db.expire_all()
    return db.get(Trip, trip.id).pod_status


@pytest.mark.parametrize(
    ("day", "start", "end"),
    [
        (date(2026, 11, 1), date(2026, 11, 1), date(2026, 11, 15)),
        (date(2026, 11, 15), date(2026, 11, 1), date(2026, 11, 15)),
        (date(2026, 11, 16), date(2026, 11, 16), date(2026, 11, 30)),
        (date(2026, 12, 31), date(2026, 12, 16), date(2026, 12, 31)),
        (date(2028, 2, 20), date(2028, 2, 16), date(2028, 2, 29)),
    ],
)
def test_the_two_cycles_of_a_month(day, start, end):
    noon = datetime(day.year, day.month, day.day, 12, tzinfo=INDIA)

    cycle = cycle_of(noon)

    assert (cycle.start, cycle.end) == (start, end)


def test_the_cycle_comes_from_india_time_not_utc():
    # 01:00 on the 16th in India is still the 15th in UTC.
    late_on_the_15th_utc = datetime(2026, 11, 15, 19, 30, tzinfo=UTC)

    assert cycle_of(late_on_the_15th_utc).start == date(2026, 11, 16)


def test_the_queue_groups_verified_trips_by_client(api_client, db, fake_ai, executive):
    first = verified_trip(api_client, db, fake_ai, freight_paise=3_850_000)
    second = verified_trip(
        api_client, db, fake_ai, client_id=first.client_id, freight_paise=3_600_000
    )
    other = verified_trip(api_client, db, fake_ai)

    body = queue(api_client)

    groups = {group["client_id"]: group for group in body["clients"]}
    same_client = groups[str(first.client_id)]["trips"]
    assert {trip["trip_code"] for trip in same_client} == {first.trip_code, second.trip_code}
    other_client = groups[str(other.client_id)]["trips"]
    assert [trip["trip_code"] for trip in other_client] == [other.trip_code]


def test_only_verified_trips_are_billable(api_client, db, fake_ai, executive):
    review = trip_in_review(api_client, db, fake_ai)
    verified = verified_trip(api_client, db, fake_ai)
    disputed = verified_trip(api_client, db, fake_ai)
    version = detail(api_client, disputed)["version"]
    api_client.post(f"/api/review/trips/{disputed.id}/dispute", json={"version": version})

    codes = {trip["trip_code"] for trip in listed_trips(queue(api_client))}

    assert verified.trip_code in codes
    assert review.trip_code not in codes
    assert disputed.trip_code not in codes


def test_a_trip_stays_in_its_delivery_cycle_however_late_it_is_approved(
    api_client, db, fake_ai, executive
):
    """Story 55: the first photo's time sets the cycle, even when the retake came much later."""
    earlier = datetime(2026, 10, 10, 6, tzinfo=UTC)
    trip = verified_trip(api_client, db, fake_ai, captured_at=earlier)

    body = queue(api_client, "2026-10-01")

    assert body["cycle_start"] == "2026-10-01"
    assert trip.trip_code in {row["trip_code"] for row in listed_trips(body)}


def test_the_cycle_switch_offers_every_cycle_holding_verified_trips(
    api_client, db, fake_ai, executive
):
    verified_trip(api_client, db, fake_ai, captured_at=datetime(2026, 9, 5, 6, tzinfo=UTC))
    verified_trip(api_client, db, fake_ai, captured_at=datetime(2026, 10, 20, 6, tzinfo=UTC))

    body = queue(api_client)

    starts = [cycle["start"] for cycle in body["cycles"]]
    assert "2026-09-01" in starts
    assert "2026-10-16" in starts
    assert starts == sorted(starts, reverse=True)
    assert body["cycle_start"] == starts[0]


def test_the_queue_counts_trips_still_in_review(api_client, db, fake_ai, executive):
    before = queue(api_client)["in_review"]
    trip_in_review(api_client, db, fake_ai)
    verified_trip(api_client, db, fake_ai)

    assert queue(api_client)["in_review"] == before + 1


def test_the_queue_reads_final_values(api_client, db, fake_ai, executive):
    trip = shortage_trip(api_client, db, fake_ai, text="Corrected: 6 short")

    row = next(
        item for item in listed_trips(queue(api_client)) if item["trip_code"] == trip.trip_code
    )

    assert row["remark"] == "Corrected: 6 short"


def test_an_export_makes_one_voucher_per_client(api_client, db, fake_ai, executive):
    first = verified_trip(api_client, db, fake_ai)
    second = verified_trip(api_client, db, fake_ai, client_id=first.client_id)
    other = verified_trip(api_client, db, fake_ai)

    response = export(api_client, first, second, other)

    assert response.status_code == 201
    assert response.json()["trip_count"] == 3
    vouchers = exported_vouchers(api_client, response)
    assert len(vouchers) == 2
    lines = sorted(len(v.findall("ALLLEDGERENTRIES.LIST")) - 1 for v in vouchers)
    assert lines == [1, 2]


def test_two_clients_sharing_a_ledger_name_keep_separate_vouchers(
    api_client, db, fake_ai, executive
):
    first = verified_trip(api_client, db, fake_ai)
    second = verified_trip(api_client, db, fake_ai)
    db.get(Client, first.client_id).tally_ledger_name = "Shared ledger"
    db.get(Client, second.client_id).tally_ledger_name = "Shared ledger"
    db.commit()

    assert len(exported_vouchers(api_client, export(api_client, first, second))) == 2


def test_a_line_carries_the_lr_and_eway_bill(api_client, db, fake_ai, executive):
    trip = verified_trip(api_client, db, fake_ai, freight_paise=3_850_000)

    voucher = exported_vouchers(api_client, export(api_client, trip))[0]

    line = voucher.findall("ALLLEDGERENTRIES.LIST")[1]
    assert line.findtext("AMOUNT") == "38500.00"
    assert trip.lr_number in line.findtext("NARRATION")
    assert trip.eway_bill_no in line.findtext("NARRATION")


def test_a_corrected_lr_is_what_gets_billed(api_client, db, fake_ai, executive):
    trip = trip_in_review(api_client, db, fake_ai)
    edit(api_client, trip, "lr_number", "CORRECTED-1")
    approve(api_client, trip)

    voucher = exported_vouchers(api_client, export(api_client, trip))[0]

    assert "CORRECTED-1" in voucher.findall("ALLLEDGERENTRIES.LIST")[1].findtext("NARRATION")


def test_a_shortage_bills_full_freight_with_the_remark_in_the_narration(
    api_client, db, fake_ai, executive
):
    trip = shortage_trip(api_client, db, fake_ai, freight_paise=4_120_000)

    voucher = exported_vouchers(api_client, export(api_client, trip))[0]

    assert "6 cartons short" in voucher.findtext("NARRATION")
    assert voucher.findall("ALLLEDGERENTRIES.LIST")[1].findtext("AMOUNT") == "41200.00"


def test_the_ledger_comes_from_the_client(api_client, db, fake_ai, executive):
    trip = verified_trip(api_client, db, fake_ai)

    voucher = exported_vouchers(api_client, export(api_client, trip))[0]

    assert voucher.findtext("PARTYLEDGERNAME").startswith("Test client")


def test_exporting_invoices_the_trip_and_records_it(api_client, db, fake_ai, executive):
    trip = verified_trip(api_client, db, fake_ai)

    response = export(api_client, trip)

    db.expire_all()
    saved = db.get(Trip, trip.id)
    assert saved.pod_status == "invoiced"
    assert saved.invoiced_at is not None
    assert str(saved.export_batch_id) == response.json()["id"]
    assert saved.voucher_no is not None
    moves = audit(db, trip, "status_change")
    assert moves[-1].to_status == "invoiced"
    assert moves[-1].actor_id == executive.id
    assert audit(db, trip, "exported")[0].detail["voucher_no"] == saved.voucher_no


def test_trips_on_one_voucher_share_its_number(api_client, db, fake_ai, executive):
    first = verified_trip(api_client, db, fake_ai)
    second = verified_trip(api_client, db, fake_ai, client_id=first.client_id)

    export(api_client, first, second)

    db.expire_all()
    assert db.get(Trip, first.id).voucher_no == db.get(Trip, second.id).voucher_no


def test_an_exported_trip_leaves_the_queue(api_client, db, fake_ai, executive):
    trip = verified_trip(api_client, db, fake_ai)

    export(api_client, trip)

    assert trip.trip_code not in {row["trip_code"] for row in listed_trips(queue(api_client))}


def test_an_export_is_refused_whole_and_names_the_trip(api_client, db, fake_ai, executive):
    good = verified_trip(api_client, db, fake_ai)
    moved = verified_trip(api_client, db, fake_ai)
    version = detail(api_client, moved)["version"]
    api_client.post(f"/api/review/trips/{moved.id}/pull-back", json={"version": version})
    batches = len(db.scalars(select(ExportBatch)).all())

    response = export(api_client, good, moved)

    assert response.status_code == 409
    assert moved.trip_code in response.json()["detail"]
    assert good.trip_code not in response.json()["detail"]
    assert status_of(db, good) == "verified"
    assert audit(db, good, "exported") == []
    assert len(db.scalars(select(ExportBatch)).all()) == batches


def test_a_second_export_of_the_same_trips_is_refused(api_client, db, fake_ai, executive):
    trip = verified_trip(api_client, db, fake_ai)
    export(api_client, trip)

    assert export(api_client, trip).status_code == 409


def test_an_export_covers_one_cycle(api_client, db, fake_ai, executive):
    first = verified_trip(api_client, db, fake_ai, captured_at=datetime(2026, 9, 5, 6, tzinfo=UTC))
    second = verified_trip(
        api_client, db, fake_ai, captured_at=datetime(2026, 10, 5, 6, tzinfo=UTC)
    )

    assert export(api_client, first, second).status_code == 422
    assert status_of(db, first) == "verified"


def test_an_empty_export_is_refused(api_client, executive):
    assert api_client.post("/api/billing/exports", json={"trip_ids": []}).status_code == 422


def test_an_unknown_trip_is_refused(api_client, executive):
    response = api_client.post(
        "/api/billing/exports", json={"trip_ids": ["00000000-0000-0000-0000-000000000000"]}
    )

    assert response.status_code == 404


def test_the_batch_records_its_cycle_and_totals(api_client, db, fake_ai, executive):
    first_day = datetime(2026, 9, 20, 6, tzinfo=UTC)
    second_day = datetime(2026, 9, 25, 6, tzinfo=UTC)
    first = verified_trip(api_client, db, fake_ai, freight_paise=100_00, captured_at=first_day)
    second = verified_trip(api_client, db, fake_ai, freight_paise=250_50, captured_at=second_day)

    response = export(api_client, first, second)

    assert response.json()["total_paise"] == 350_50
    db.expire_all()
    batch = db.get(ExportBatch, db.get(Trip, first.id).export_batch_id)
    assert (batch.cycle_start, batch.cycle_end) == (date(2026, 9, 16), date(2026, 9, 30))
    assert batch.created_by == executive.id


def test_a_redownload_returns_the_identical_xml(api_client, db, fake_ai, executive):
    trip = verified_trip(api_client, db, fake_ai)
    batch_id = export(api_client, trip).json()["id"]
    first = api_client.get(f"/api/billing/exports/{batch_id}/xml")

    # A later change to the client must not reach a voucher that has already been exported.
    db.expire_all()
    db.get(Client, trip.client_id).tally_ledger_name = "Renamed ledger"
    db.commit()
    second = api_client.get(f"/api/billing/exports/{batch_id}/xml")

    assert first.status_code == 200
    assert first.content == second.content
    assert "attachment" in first.headers["content-disposition"]
    assert first.headers["content-type"].startswith("application/xml")


def test_earlier_exports_are_listed_newest_first(api_client, db, fake_ai, executive):
    first = export(api_client, verified_trip(api_client, db, fake_ai)).json()
    second = export(api_client, verified_trip(api_client, db, fake_ai)).json()

    listed = api_client.get("/api/billing/exports").json()
    ids = [row["id"] for row in listed]

    assert ids.index(second["id"]) < ids.index(first["id"])
    assert listed[ids.index(first["id"])]["trip_count"] == 1
    assert listed[ids.index(first["id"])]["exported_at"] is not None


def test_the_zip_holds_one_photo_per_trip_by_voucher(api_client, db, fake_ai, executive):
    first = verified_trip(api_client, db, fake_ai)
    second = verified_trip(api_client, db, fake_ai)
    batch_id = export(api_client, first, second).json()["id"]

    response = api_client.get(f"/api/billing/exports/{batch_id}/photos")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    db.expire_all()
    names = ZipFile(BytesIO(response.content)).namelist()
    assert sorted(names) == sorted(
        f"{db.get(Trip, trip.id).voucher_no}/{trip.trip_code}.jpg" for trip in (first, second)
    )


def test_the_zip_uses_the_attempt_billing_used(api_client, db, fake_ai, executive):
    """A retake's photo is the one billed, and a late photo never replaces it."""
    trip = make_trip(db)
    token = create_link(db, trip)
    db.commit()
    fake_ai.reading = clean_reading(
        trip, remarks={"text": "short", "kind": "shortage", "confidence": 0.9}
    )
    upload(api_client, token)
    version = detail(api_client, trip)["version"]
    api_client.post(f"/api/review/trips/{trip.id}/retake", json={"version": version})
    fake_ai.reading = clean_reading(trip)
    upload(api_client, token, photo=ANOTHER_PHOTO)
    upload(api_client, token, photo=JPEG + b"late")
    assert status_of(db, trip) == "verified"

    batch_id = export(api_client, trip).json()["id"]
    response = api_client.get(f"/api/billing/exports/{batch_id}/photos")

    archive = ZipFile(BytesIO(response.content))
    assert archive.read(archive.namelist()[0]) == ANOTHER_PHOTO
    db.expire_all()
    attempts = db.scalars(select(PodAttempt.attempt_no).where(PodAttempt.trip_id == trip.id)).all()
    assert sorted(attempts) == [1, 2, 4]


def test_an_unknown_export_is_not_found(api_client, executive):
    no_id = "00000000-0000-0000-0000-000000000000"

    assert api_client.get(f"/api/billing/exports/{no_id}/xml").status_code == 404
    assert api_client.get(f"/api/billing/exports/{no_id}/photos").status_code == 404


def test_the_operations_head_cannot_export(api_client, db, fake_ai):
    executive = make_user(db, Role.BILLING_EXECUTIVE, password=PASSWORD)
    api_client.post("/api/auth/login", json={"email": executive.email, "password": PASSWORD})
    trip = verified_trip(api_client, db, fake_ai)
    head = make_user(db, Role.OPERATIONS_HEAD, password=PASSWORD)
    api_client.post("/api/auth/login", json={"email": head.email, "password": PASSWORD})

    assert export(api_client, trip).status_code == 403
    assert status_of(db, trip) == "verified"
    assert db.scalars(
        select(AuditEvent).where(AuditEvent.trip_id == trip.id, AuditEvent.action == "exported")
    ).all() == []
