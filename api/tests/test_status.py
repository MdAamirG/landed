"""The status machine, against the seven-status diagram in docs/data-model.md."""

from datetime import UTC, date, datetime
from itertools import product

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import ActorType, AuditEvent, ExportBatch, PodStatus, Trip
from app.rules import ReasonCode
from app.status import SYSTEM, Actor, IllegalMove, check_move, move_trip, reset_demo_trip
from tests.factories import make_trip, make_user

# Copied from the diagram, so this table can disagree with the code.
DIAGRAM = {
    (PodStatus.AWAITING_POD, PodStatus.CHECKING): ActorType.DRIVER_LINK,
    (PodStatus.CHECKING, PodStatus.VERIFIED): ActorType.SYSTEM,
    (PodStatus.CHECKING, PodStatus.RETAKE_REQUESTED): ActorType.SYSTEM,
    (PodStatus.CHECKING, PodStatus.NEEDS_REVIEW): ActorType.SYSTEM,
    (PodStatus.RETAKE_REQUESTED, PodStatus.CHECKING): ActorType.DRIVER_LINK,
    (PodStatus.NEEDS_REVIEW, PodStatus.VERIFIED): ActorType.USER,
    (PodStatus.NEEDS_REVIEW, PodStatus.RETAKE_REQUESTED): ActorType.USER,
    (PodStatus.NEEDS_REVIEW, PodStatus.DISPUTED): ActorType.USER,
    (PodStatus.DISPUTED, PodStatus.VERIFIED): ActorType.USER,
    (PodStatus.VERIFIED, PodStatus.NEEDS_REVIEW): ActorType.USER,
    (PodStatus.VERIFIED, PodStatus.DISPUTED): ActorType.USER,
    (PodStatus.VERIFIED, PodStatus.INVOICED): ActorType.USER,
}

ALL_CASES = list(product(PodStatus, PodStatus, ActorType))


@pytest.mark.parametrize(("current", "target"), DIAGRAM)
def test_every_move_on_the_diagram_is_allowed_for_its_actor(current, target):
    check_move(current, target, DIAGRAM[(current, target)])


@pytest.mark.parametrize(
    ("current", "target", "actor_type"),
    [case for case in ALL_CASES if DIAGRAM.get(case[:2]) != case[2]],
)
def test_every_other_move_is_refused(current, target, actor_type):
    with pytest.raises(IllegalMove):
        check_move(current, target, actor_type)


def test_invoiced_is_final():
    with pytest.raises(IllegalMove):
        check_move(PodStatus.INVOICED, PodStatus.VERIFIED, ActorType.USER)


def test_the_system_can_never_invoice_a_trip():
    with pytest.raises(IllegalMove):
        check_move(PodStatus.VERIFIED, PodStatus.INVOICED, ActorType.SYSTEM)


def events_for(session, trip):
    return session.scalars(select(AuditEvent).where(AuditEvent.trip_id == trip.id)).all()


def test_a_move_changes_the_status_and_writes_an_audit_event(db):
    trip = make_trip(db, pod_status="checking")

    move_trip(db, trip, PodStatus.NEEDS_REVIEW, SYSTEM, reason=ReasonCode.SHORTAGE_REMARK)

    assert trip.pod_status == "needs_review"
    assert trip.status_reason == "shortage_remark"
    event = events_for(db, trip)[0]
    assert (event.from_status, event.to_status) == ("checking", "needs_review")
    assert (event.actor_type, event.actor_id) == ("system", None)
    assert event.action == "status_change"
    assert event.detail == {"reason": "shortage_remark"}


def test_a_move_records_who_made_it(db):
    user = make_user(db)
    trip = make_trip(db, pod_status="needs_review")

    move_trip(db, trip, PodStatus.DISPUTED, Actor(ActorType.USER, user.id))

    event = events_for(db, trip)[0]
    assert (event.actor_type, event.actor_id) == ("user", user.id)


def test_the_status_and_its_audit_event_share_a_transaction(db):
    trip = make_trip(db, pod_status="checking")

    move_trip(db, trip, PodStatus.VERIFIED, SYSTEM)
    db.rollback()

    with SessionLocal() as other_session:
        assert other_session.get(Trip, trip.id).pod_status == "checking"
        assert events_for(other_session, trip) == []


def test_a_refused_move_changes_nothing(db):
    trip = make_trip(db, pod_status="invoiced")

    with pytest.raises(IllegalMove):
        move_trip(db, trip, PodStatus.VERIFIED, SYSTEM)

    assert trip.pod_status == "invoiced"
    assert events_for(db, trip) == []


def test_a_move_bumps_the_version_so_a_stale_save_conflicts(db):
    trip = make_trip(db, pod_status="checking")

    move_trip(db, trip, PodStatus.NEEDS_REVIEW, SYSTEM)

    assert trip.version == 2


def test_the_ai_verifying_leaves_verified_by_empty(db):
    trip = make_trip(db, pod_status="checking")

    move_trip(db, trip, PodStatus.VERIFIED, SYSTEM)

    assert trip.verified_at is not None
    assert trip.verified_by is None


def test_an_executive_verifying_is_recorded(db):
    user = make_user(db)
    trip = make_trip(db, pod_status="needs_review")

    move_trip(db, trip, PodStatus.VERIFIED, Actor(ActorType.USER, user.id))

    assert trip.verified_at is not None
    assert trip.verified_by == user.id


def test_pulling_a_trip_back_from_verified_clears_who_verified_it(db):
    user = make_user(db)
    actor = Actor(ActorType.USER, user.id)
    trip = make_trip(db, pod_status="needs_review")
    move_trip(db, trip, PodStatus.VERIFIED, actor)

    move_trip(db, trip, PodStatus.NEEDS_REVIEW, actor)

    assert trip.verified_at is None
    assert trip.verified_by is None


def test_a_stale_copy_of_a_trip_cannot_slip_past_the_rules(db):
    # Someone else moved the trip after this session read it, as with a late AI result.
    user = make_user(db)
    actor = Actor(ActorType.USER, user.id)
    trip = make_trip(db, pod_status="checking")

    with SessionLocal() as other_session:
        stale_trip = other_session.get(Trip, trip.id)

        move_trip(db, trip, PodStatus.NEEDS_REVIEW, SYSTEM)
        move_trip(db, trip, PodStatus.DISPUTED, actor)
        db.commit()

        assert stale_trip.pod_status == "checking"
        with pytest.raises(IllegalMove):
            move_trip(other_session, stale_trip, PodStatus.VERIFIED, SYSTEM)


def exported_demo_values(db) -> dict:
    """Everything a demo trip can pick up on its way to invoiced."""
    user = make_user(db)
    batch = ExportBatch(
        cycle_start=date(2026, 11, 1),
        cycle_end=date(2026, 11, 15),
        created_by=user.id,
        trip_count=1,
        total_paise=3_200_000,
        xml="<ENVELOPE />",
    )
    db.add(batch)
    db.flush()
    now = datetime.now(UTC)
    return {
        "is_demo": True,
        "status_reason": "shortage_remark",
        "retakes_used": 2,
        "verified_at": now,
        "verified_by": user.id,
        "export_batch_id": batch.id,
        "voucher_no": "V-1",
        "invoiced_at": now,
    }


@pytest.mark.parametrize("status", list(PodStatus))
def test_a_demo_reset_returns_the_trip_to_the_start_from_any_status(db, status):
    trip = make_trip(db, pod_status=status, **exported_demo_values(db))

    reset_demo_trip(db, trip)

    assert trip.pod_status == "awaiting_pod"
    assert trip.status_reason is None
    assert trip.retakes_used == 0
    assert (trip.verified_at, trip.verified_by) == (None, None)
    assert (trip.export_batch_id, trip.voucher_no, trip.invoiced_at) == (None, None, None)


def test_a_demo_reset_adds_to_the_audit_log_and_keeps_what_was_there(db):
    # The 10-an-hour upload limit counts from this log, so a reset must not clear it.
    trip = make_trip(db, pod_status="checking", is_demo=True)
    move_trip(db, trip, PodStatus.NEEDS_REVIEW, SYSTEM)

    reset_demo_trip(db, trip)

    first, reset = events_for(db, trip)
    assert first.action == "status_change"
    assert reset.action == "demo_reset"
    assert (reset.from_status, reset.to_status) == ("needs_review", "awaiting_pod")
    assert (reset.actor_type, reset.actor_id) == ("system", None)


def test_a_demo_reset_bumps_the_version(db):
    trip = make_trip(db, pod_status="verified", is_demo=True)

    reset_demo_trip(db, trip)

    assert trip.version == 2


def test_a_demo_reset_refuses_a_real_trip_and_changes_nothing(db):
    trip = make_trip(db, pod_status="verified", retakes_used=1)

    with pytest.raises(IllegalMove):
        reset_demo_trip(db, trip)

    assert trip.pod_status == "verified"
    assert trip.retakes_used == 1
    assert events_for(db, trip) == []


def test_a_stale_copy_cannot_reset_a_trip_that_is_no_longer_a_demo_trip(db):
    trip = make_trip(db, pod_status="verified", is_demo=True)

    with SessionLocal() as other_session:
        stale_trip = other_session.get(Trip, trip.id)
        trip.is_demo = False
        db.commit()

        assert stale_trip.is_demo is True
        with pytest.raises(IllegalMove):
            reset_demo_trip(other_session, stale_trip)
