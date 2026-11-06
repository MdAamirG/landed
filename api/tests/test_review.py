"""The review desk, through the HTTP API with the AI reader faked."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.driver_links import create_link
from app.models import AuditEvent, PodAttempt, PodField, Role, Trip
from tests.factories import clean_reading, make_trip, make_user
from tests.test_attempts import JPEG, upload

PASSWORD = "correct horse battery"


@pytest.fixture
def executive(api_client, db):
    user = make_user(db, Role.BILLING_EXECUTIVE, password=PASSWORD)
    api_client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    return user


def trip_in_review(api_client, db, fake_ai, **overrides):
    """A real trip that reached needs_review the real way: a photo with a shortage remark."""
    trip = make_trip(db, **overrides)
    token = create_link(db, trip)
    db.commit()
    fake_ai.reading = clean_reading(
        trip, remarks={"text": "short by 6", "kind": "shortage", "confidence": 0.95}
    )
    upload(api_client, token)
    db.expire_all()
    return trip


def failed_trip(api_client, db, fake_ai):
    """A trip whose AI call failed, so its six fields are blank."""
    trip = make_trip(db)
    token = create_link(db, trip)
    db.commit()
    fake_ai.reading = None
    upload(api_client, token)
    db.expire_all()
    return trip


def detail(client, trip):
    return client.get(f"/api/review/trips/{trip.id}").json()


def edit(client, trip, field, value, version=None):
    version = detail(client, trip)["version"] if version is None else version
    return client.patch(
        f"/api/review/trips/{trip.id}/fields/{field}", json={"value": value, "version": version}
    )


def approve(client, trip, version=None):
    version = detail(client, trip)["version"] if version is None else version
    return client.post(f"/api/review/trips/{trip.id}/approve", json={"version": version})


def audit(db, trip, action):
    db.expire_all()
    return db.scalars(
        select(AuditEvent).where(AuditEvent.trip_id == trip.id, AuditEvent.action == action)
    ).all()


ALL_FIELDS = {
    "lr_number": "48213",
    "consignee_stamp": "present",
    "quantity_received": {"number": 394, "unit": "cartons"},
    "remarks": {"text": "", "kind": "none"},
    "delivery_date": "2026-11-06",
    "signature": "present",
}


def test_the_queue_lists_needs_review_trips_oldest_first(api_client, db, fake_ai, executive):
    old = trip_in_review(api_client, db, fake_ai)
    new = trip_in_review(api_client, db, fake_ai)
    db.scalar(select(PodAttempt).where(PodAttempt.trip_id == old.id)).received_at = datetime.now(
        UTC
    ) - timedelta(hours=2)
    db.commit()
    verified = make_trip(db, pod_status="verified")

    codes = [item["trip_code"] for item in api_client.get("/api/review/queue").json()]

    assert codes.index(old.trip_code) < codes.index(new.trip_code)
    assert verified.trip_code not in codes


def test_a_queue_item_gives_the_reason(api_client, db, fake_ai, executive):
    trip = trip_in_review(api_client, db, fake_ai)

    items = api_client.get("/api/review/queue").json()
    item = next(row for row in items if row["trip_code"] == trip.trip_code)

    assert item["status_reason"] == "shortage_remark"
    assert item["ownership"] == "own"


def test_the_queue_sweeps_stuck_attempts_on_every_trip(api_client, db, executive):
    trip = make_trip(db, pod_status="checking")
    now = datetime.now(UTC)
    db.add(
        PodAttempt(
            id=uuid4(),
            trip_id=trip.id,
            attempt_no=1,
            image_bytes=JPEG,
            size_bytes=len(JPEG),
            sha256="unused",
            captured_at=now - timedelta(minutes=2),
            received_at=now - timedelta(minutes=2),
            ai_status="pending",
        )
    )
    db.commit()

    codes = [item["trip_code"] for item in api_client.get("/api/review/queue").json()]

    assert trip.trip_code in codes


def test_the_detail_shows_every_reason_field_and_check(api_client, db, fake_ai, executive):
    trip = trip_in_review(api_client, db, fake_ai)

    body = detail(api_client, trip)

    assert body["reason_codes"] == ["shortage_remark"]
    assert len(body["attempts"]) == 1
    fields = {row["field"]: row for row in body["attempts"][0]["fields"]}
    assert len(fields) == 6
    assert fields["remarks"]["ai_value"] == {"text": "short by 6", "kind": "shortage"}
    assert fields["remarks"]["ai_confidence"] == 0.95
    assert {check["label"] for check in body["checks"]} >= {
        "LR matches the trip",
        "E-way bill is linked",
    }


def test_review_uses_the_highest_checked_attempt_and_keeps_each_reading(
    api_client, db, fake_ai, executive
):
    trip = make_trip(db)
    token = create_link(db, trip)
    db.commit()
    fake_ai.reading = clean_reading(trip, signature={"value": "absent", "confidence": 0.9})
    upload(api_client, token)
    fake_ai.reading = clean_reading(
        trip, remarks={"text": "short", "kind": "shortage", "confidence": 0.95}
    )
    upload(api_client, token)
    upload(api_client, token)  # Late: the trip is already in needs_review.

    body = detail(api_client, trip)

    assert [attempt["attempt_no"] for attempt in body["attempts"]] == [1, 2, 4]
    assert [attempt["late"] for attempt in body["attempts"]] == [False, False, True]
    assert body["current_attempt_id"] == body["attempts"][1]["id"]
    first_signature = next(
        row for row in body["attempts"][0]["fields"] if row["field"] == "signature"
    )
    assert first_signature["ai_value"] == "absent"


def test_a_wrong_clock_is_flagged_on_the_attempt(api_client, db, fake_ai, executive):
    trip = make_trip(db)
    token = create_link(db, trip)
    db.commit()
    fake_ai.reading = None
    future = datetime.now(UTC) + timedelta(hours=5)

    upload(api_client, token, captured_at=future.isoformat())

    assert detail(api_client, trip)["attempts"][0]["clock_corrected"] is True


def test_the_photo_is_served_as_an_image(api_client, db, fake_ai, executive):
    trip = trip_in_review(api_client, db, fake_ai)
    attempt_id = detail(api_client, trip)["current_attempt_id"]

    response = api_client.get(f"/api/review/attempts/{attempt_id}/photo")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content == JPEG


def test_an_edit_keeps_the_ai_value_and_is_logged(api_client, db, fake_ai, executive):
    trip = trip_in_review(api_client, db, fake_ai)

    response = edit(api_client, trip, "lr_number", "99999")

    assert response.status_code == 200
    row = next(
        field
        for field in response.json()["attempts"][0]["fields"]
        if field["field"] == "lr_number"
    )
    assert row["ai_value"] == trip.lr_number
    assert row["final_value"] == "99999"
    assert row["edited"] is True

    stored = db.scalar(select(PodField).where(PodField.field == "lr_number").join(
        PodAttempt, PodField.attempt_id == PodAttempt.id
    ).where(PodAttempt.trip_id == trip.id))
    assert stored.edited_by == executive.id
    assert stored.edited_at is not None

    events = audit(db, trip, "field_edited")
    assert len(events) == 1
    assert events[0].actor_id == executive.id
    assert events[0].detail["field"] == "lr_number"
    assert events[0].detail["from"] == trip.lr_number
    assert events[0].detail["to"] == "99999"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("lr_number", ""),
        ("consignee_stamp", "maybe"),
        ("quantity_received", {"number": -1, "unit": "bags"}),
        ("quantity_received", {"number": 5}),
        ("remarks", {"text": "x", "kind": "angry"}),
        ("delivery_date", "soon"),
        ("signature", None),
    ],
)
def test_a_bad_value_is_refused_and_changes_nothing(
    api_client, db, fake_ai, executive, field, value
):
    trip = trip_in_review(api_client, db, fake_ai)
    version = detail(api_client, trip)["version"]

    assert edit(api_client, trip, field, value).status_code == 422
    assert detail(api_client, trip)["version"] == version
    assert audit(db, trip, "field_edited") == []


def test_an_unknown_field_is_refused(api_client, db, fake_ai, executive):
    trip = trip_in_review(api_client, db, fake_ai)

    assert edit(api_client, trip, "freight", "1").status_code == 422


def test_an_edit_on_a_stale_version_gets_a_conflict(api_client, db, fake_ai, executive):
    trip = trip_in_review(api_client, db, fake_ai)
    stale = detail(api_client, trip)["version"]
    edit(api_client, trip, "lr_number", "11111", version=stale)

    response = edit(api_client, trip, "lr_number", "22222", version=stale)

    assert response.status_code == 409
    field = next(
        row
        for row in detail(api_client, trip)["attempts"][0]["fields"]
        if row["field"] == "lr_number"
    )
    assert field["final_value"] == "11111"


def test_approve_on_a_stale_version_gets_a_conflict(api_client, db, fake_ai, executive):
    trip = trip_in_review(api_client, db, fake_ai)
    stale = detail(api_client, trip)["version"]
    edit(api_client, trip, "lr_number", "11111", version=stale)

    assert approve(api_client, trip, version=stale).status_code == 409
    db.expire_all()
    assert db.get(Trip, trip.id).pod_status == "needs_review"


def test_approve_verifies_the_trip_and_names_who(api_client, db, fake_ai, executive):
    trip = trip_in_review(api_client, db, fake_ai)

    response = approve(api_client, trip)

    assert response.status_code == 200
    db.expire_all()
    trip = db.get(Trip, trip.id)
    assert trip.pod_status == "verified"
    assert trip.verified_by == executive.id
    assert trip.verified_at is not None


def test_approve_is_refused_until_all_six_fields_are_filled(api_client, db, fake_ai, executive):
    trip = failed_trip(api_client, db, fake_ai)

    refused = approve(api_client, trip)
    assert refused.status_code == 422
    assert "lr_number" in refused.json()["detail"]

    for field, value in list(ALL_FIELDS.items())[:-1]:
        assert edit(api_client, trip, field, value).status_code == 200
    assert approve(api_client, trip).status_code == 422

    assert edit(api_client, trip, "signature", "present").status_code == 200
    assert approve(api_client, trip).status_code == 200


def test_a_trip_with_no_reading_cannot_be_approved_or_edited(api_client, db, executive):
    trip = make_trip(db, pod_status="needs_review")

    assert approve(api_client, trip).status_code == 422
    assert edit(api_client, trip, "lr_number", "1").status_code == 409


def test_an_approved_trip_can_no_longer_be_edited(api_client, db, fake_ai, executive):
    trip = trip_in_review(api_client, db, fake_ai)
    approve(api_client, trip)

    assert edit(api_client, trip, "lr_number", "1").status_code == 409


def test_an_invoiced_trip_cannot_be_approved(api_client, db, fake_ai, executive):
    trip = trip_in_review(api_client, db, fake_ai)
    live = db.get(Trip, trip.id)
    live.pod_status = "invoiced"
    db.commit()

    assert approve(api_client, trip).status_code == 409


def test_contacts_stay_masked_in_every_review_response(api_client, db, fake_ai, executive):
    trip = trip_in_review(
        api_client,
        db,
        fake_ai,
        consignee_name="Sample Consignee Gate",
        consignee_phone="9000000099",
    )

    responses = [
        api_client.get("/api/review/queue"),
        api_client.get(f"/api/review/trips/{trip.id}"),
        edit(api_client, trip, "lr_number", "1"),
        approve(api_client, trip),
    ]

    for response in responses:
        assert "Sample Consignee Gate" not in response.text
        assert "9000000099" not in response.text
        assert "9000000000" not in response.text  # The driver's phone.
    body = responses[1].json()
    assert body["consignee_name"] == "S. C. G."
    assert body["consignee_phone"] == "+91 90••• ••099"
    assert body["driver_phone"] == "+91 90••• ••000"


def test_a_reveal_returns_the_contact_and_logs_who_asked(api_client, db, fake_ai, executive):
    trip = trip_in_review(
        api_client, db, fake_ai, consignee_name="Sample Gate", consignee_phone="9000000099"
    )

    response = api_client.post(f"/api/review/trips/{trip.id}/reveal")

    assert response.json() == {"name": "Sample Gate", "phone": "9000000099"}
    events = audit(db, trip, "contact_revealed")
    assert len(events) == 1
    assert events[0].actor_id == executive.id
    assert "9000000099" not in str(events[0].detail)


def test_each_reveal_is_logged(api_client, db, fake_ai, executive):
    trip = trip_in_review(api_client, db, fake_ai)

    api_client.post(f"/api/review/trips/{trip.id}/reveal")
    api_client.post(f"/api/review/trips/{trip.id}/reveal")

    assert len(audit(db, trip, "contact_revealed")) == 2


def test_the_operations_head_cannot_approve_a_real_trip(api_client, db, fake_ai):
    ops = make_user(db, Role.OPERATIONS_HEAD, password=PASSWORD)
    api_client.post("/api/auth/login", json={"email": ops.email, "password": PASSWORD})
    trip = trip_in_review(api_client, db, fake_ai)

    response = api_client.post(f"/api/review/trips/{trip.id}/approve", json={"version": 1})

    assert response.status_code == 403
    db.expire_all()
    assert db.get(Trip, trip.id).pod_status == "needs_review"


@pytest.mark.parametrize(
    ("path", "method"),
    [("trips", "get"), ("attempts", "photo")],
)
def test_an_unknown_id_is_a_404(api_client, executive, path, method):
    suffix = "" if method == "get" else "/photo"
    url = f"/api/review/{path}/{uuid4()}{suffix}"

    assert api_client.get(url).status_code == 404
