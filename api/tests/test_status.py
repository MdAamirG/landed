"""The status machine, against the seven-status diagram in docs/data-model.md."""

from itertools import product

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import ActorType, AuditEvent, PodStatus, Trip
from app.rules import ReasonCode
from app.status import SYSTEM, Actor, IllegalMove, check_move, move_trip
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
