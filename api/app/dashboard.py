"""The missing-POD list and the three success figures from the brief."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import median
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, Row, and_, func, select
from sqlalchemy.orm import Session, aliased

from app.driver_links import create_link, demo_token
from app.intake import WAITING_FOR_A_PHOTO
from app.masking import mask_phone
from app.models import (
    ActorType,
    Branch,
    Client,
    Driver,
    PodAttempt,
    PodStatus,
    Trip,
    User,
    Vehicle,
)
from app.schemas import ResendOut
from app.status import Actor, send_mock_sms

TARGET_WINDOW = timedelta(hours=24)  # The brief: 80% of PODs in within 24 hours of delivery.
LOST_AFTER = timedelta(days=20)  # The top of the brief's 10 to 20 day range.
FIGURE_WINDOW = timedelta(days=90)  # Spec assumption 26.


# The first photo sets a trip's delivery time (spec assumption 1). Outer-joined here, because a
# trip with no photo yet is exactly what this screen is about.
first_attempt = aliased(PodAttempt)
IS_FIRST_ATTEMPT = and_(first_attempt.trip_id == Trip.id, first_attempt.attempt_no == 1)


@dataclass(frozen=True)
class MissingPod:
    trip_id: UUID
    trip_code: str
    registration_no: str
    ownership: str
    client_name: str
    destination: str
    branch_name: str
    since_delivery: timedelta

    @property
    def hours_since_delivery(self) -> int:
        return int(self.since_delivery / timedelta(hours=1))

    @property
    def over_24_hours(self) -> bool:
        return self.since_delivery > TARGET_WINDOW


def missing_conditions(now: datetime) -> tuple[ColumnElement[bool], ...]:
    """Spec assumption 8, shared so the list and the top bar's count can't disagree."""
    return (
        Trip.pod_status.in_(WAITING_FOR_A_PHOTO),
        Trip.expected_delivery_at < now,
        Trip.is_demo.is_(False),
    )


def missing_pods(session: Session, now: datetime) -> list[MissingPod]:
    """Oldest first, because that's the one to chase (story 64).

    A retake trip already has a photo, and its delivery time is that photo's (spec assumption 1).
    """
    rows = session.execute(
        select(
            Trip,
            Vehicle.registration_no,
            Vehicle.ownership,
            Client.name,
            Branch.name,
            first_attempt.captured_at,
        )
        .join(Vehicle, Trip.vehicle_id == Vehicle.id)
        .join(Client, Trip.client_id == Client.id)
        .join(Branch, Trip.branch_id == Branch.id)
        .outerjoin(first_attempt, IS_FIRST_ATTEMPT)
        .where(*missing_conditions(now))
    ).all()

    missing = [
        MissingPod(
            trip_id=trip.id,
            trip_code=trip.trip_code,
            registration_no=registration_no,
            ownership=ownership,
            client_name=client_name,
            destination=trip.destination,
            branch_name=branch_name,
            since_delivery=now - (captured_at or trip.expected_delivery_at),
        )
        for trip, registration_no, ownership, client_name, branch_name, captured_at in rows
    ]
    return sorted(missing, key=lambda row: row.since_delivery, reverse=True)


@dataclass(frozen=True)
class BranchDays:
    branch_name: str
    median_days: float


@dataclass(frozen=True)
class Figures:
    """None means there's nothing to measure yet, which is different from a measured zero."""

    within_24_hours_percent: float | None
    pod_to_invoice_days: float | None
    lost_or_disputed_percent: float | None
    branches: list[BranchDays]  # Only branches with an invoice, lowest median first.


def percent(part: int, whole: int) -> float | None:
    return round(100 * part / whole, 1) if whole else None


def days_to_invoice(trip: Row) -> float:
    return (trip.invoiced_at - trip.received_at) / timedelta(days=1)


def figures(session: Session, now: datetime) -> Figures:
    """The data model's three figures, over trips due in the window. Demo trips never count."""
    trips = session.execute(
        select(
            Trip.pod_status,
            Trip.expected_delivery_at,
            Trip.invoiced_at,
            Branch.name.label("branch_name"),
            first_attempt.captured_at,
            first_attempt.received_at,
        )
        .join(Branch, Trip.branch_id == Branch.id)
        .outerjoin(first_attempt, IS_FIRST_ATTEMPT)
        .where(Trip.is_demo.is_(False), Trip.expected_delivery_at >= now - FIGURE_WINDOW)
    ).all()

    # Spec assumption 9: a photo answers the question, and without one the trip is judged only
    # once its time is up, so a trip still on the road can't count against the figure.
    judged = [
        trip
        for trip in trips
        if trip.received_at or trip.expected_delivery_at + TARGET_WINDOW <= now
    ]
    in_time = [
        trip
        for trip in judged
        if trip.received_at and trip.received_at - trip.captured_at <= TARGET_WINDOW
    ]

    invoiced = [trip for trip in trips if trip.invoiced_at and trip.received_at]
    days_by_branch: dict[str, list[float]] = defaultdict(list)
    for trip in invoiced:
        days_by_branch[trip.branch_name].append(days_to_invoice(trip))
    branches = [
        BranchDays(name, round(median(days), 1)) for name, days in days_by_branch.items()
    ]

    # Spec assumption 27: only trips that have been delivered could be lost or disputed.
    delivered = [trip for trip in trips if trip.received_at or trip.expected_delivery_at <= now]
    lost_or_disputed = [
        trip
        for trip in delivered
        if trip.pod_status == PodStatus.DISPUTED
        or (
            trip.pod_status in WAITING_FOR_A_PHOTO
            and trip.expected_delivery_at + LOST_AFTER <= now  # Spec assumption 10.
        )
    ]

    return Figures(
        within_24_hours_percent=percent(len(in_time), len(judged)),
        pod_to_invoice_days=(
            round(median(days_to_invoice(trip) for trip in invoiced), 1) if invoiced else None
        ),
        lost_or_disputed_percent=percent(len(lost_or_disputed), len(delivered)),
        branches=sorted(branches, key=lambda branch: (branch.median_days, branch.branch_name)),
    )


def resend_link(session: Session, trip_id: UUID, user: User) -> ResendOut:
    """Spec assumption 5: only a hash is stored, so a resend makes a new token. The old link keeps
    working, because a phone may be holding a photo for it.
    """
    trip = session.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if trip.pod_status not in WAITING_FOR_A_PHOTO:
        raise HTTPException(status.HTTP_409_CONFLICT, "This trip isn't waiting for a photo")

    actor = Actor(ActorType.USER, user.id)
    token = create_link(session, trip, actor, sent=True)
    send_mock_sms(session, trip, actor, {"purpose": "resend"})
    session.commit()
    return ResendOut(
        sent_to=mask_phone(session.get_one(Driver, trip.driver_id).phone),
        driver_token=demo_token(token),
    )


@dataclass(frozen=True)
class QueueCounts:
    review: int
    billing: int
    missing_pods: int


def queue_counts(session: Session, now: datetime) -> QueueCounts:
    """For the top bar. Demo trips count in Review and Billing, where they appear."""

    def count(*conditions: ColumnElement[bool]) -> int:
        return session.scalar(select(func.count()).select_from(Trip).where(*conditions)) or 0

    return QueueCounts(
        review=count(Trip.pod_status == PodStatus.NEEDS_REVIEW),
        billing=count(Trip.pod_status == PodStatus.VERIFIED),
        missing_pods=count(*missing_conditions(now)),
    )
