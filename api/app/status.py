"""The status machine: the one place that moves a trip's pod_status.

It refuses any move outside the diagram in docs/data-model.md and writes the audit event in the
same transaction. The caller commits, so a status and its audit event land together or not at all.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ActorType, AuditEvent, PodStatus, Trip
from app.rules import ReasonCode


@dataclass(frozen=True)
class Actor:
    type: ActorType
    id: UUID | None = None  # A user or a driver link. Empty for the system.


SYSTEM = Actor(ActorType.SYSTEM)

# For each status: who may move a trip out of it, and where to. Keeping the actor here means the
# system can't approve a trip a person is reviewing, and only a person can invoice one.
MOVES: dict[PodStatus, tuple[ActorType, frozenset[PodStatus]]] = {
    PodStatus.AWAITING_POD: (ActorType.DRIVER_LINK, frozenset({PodStatus.CHECKING})),
    PodStatus.CHECKING: (
        ActorType.SYSTEM,
        frozenset({PodStatus.VERIFIED, PodStatus.RETAKE_REQUESTED, PodStatus.NEEDS_REVIEW}),
    ),
    PodStatus.RETAKE_REQUESTED: (ActorType.DRIVER_LINK, frozenset({PodStatus.CHECKING})),
    PodStatus.NEEDS_REVIEW: (
        ActorType.USER,
        frozenset({PodStatus.VERIFIED, PodStatus.RETAKE_REQUESTED, PodStatus.DISPUTED}),
    ),
    PodStatus.DISPUTED: (ActorType.USER, frozenset({PodStatus.VERIFIED})),
    PodStatus.VERIFIED: (
        ActorType.USER,
        frozenset({PodStatus.NEEDS_REVIEW, PodStatus.DISPUTED, PodStatus.INVOICED}),
    ),
    # Nothing leaves invoiced: disputes after invoicing would need a Tally reversal.
}


class IllegalMove(Exception):
    """The move isn't on the diagram, or this actor can't make it. Routes return 409."""


def check_move(current: PodStatus, target: PodStatus, actor_type: ActorType) -> None:
    allowed_actor, targets = MOVES.get(current, (None, frozenset()))
    if target not in targets:
        raise IllegalMove(f"A trip can't move from {current} to {target}.")
    if actor_type != allowed_actor:
        raise IllegalMove(f"Only {allowed_actor} can move a trip out of {current}.")


def move_trip(
    session: Session,
    trip: Trip,
    target: PodStatus,
    actor: Actor,
    reason: ReasonCode | None = None,
) -> None:
    """Move the trip and add its audit event. Raises IllegalMove and changes nothing if refused."""
    # Lock and re-read the row, so the check sees the real status even if this copy is stale.
    # This can't tell attempts apart: the background check must still confirm that its attempt
    # is the one being checked before it calls this.
    session.refresh(trip, with_for_update=True)
    current = PodStatus(trip.pod_status)
    check_move(current, target, actor.type)

    trip.pod_status = target
    trip.status_reason = reason
    trip.version += 1  # A move is a save, so an executive's open copy of this trip goes stale.

    if target == PodStatus.VERIFIED:
        trip.verified_at = datetime.now(UTC)
        trip.verified_by = actor.id  # Stays empty when the AI verified the trip.
    elif current == PodStatus.VERIFIED and target == PodStatus.NEEDS_REVIEW:
        trip.verified_at = None
        trip.verified_by = None

    session.add(
        AuditEvent(
            trip_id=trip.id,
            actor_type=actor.type,
            actor_id=actor.id,
            action="status_change",
            from_status=current,
            to_status=target,
            detail={"reason": reason} if reason else {},
        )
    )
    session.flush()
