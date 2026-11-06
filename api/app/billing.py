"""The billing queue, exports and POD photos. tally.py builds the XML; this picks what goes in."""

import calendar
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from io import BytesIO
from typing import Any
from uuid import UUID, uuid4
from zipfile import ZIP_STORED, ZipFile

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, Row, and_, func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session, aliased

from app.intake import LAST_CHECKED_ATTEMPT_NO, image_type
from app.models import (
    ActorType,
    AuditEvent,
    Client,
    ExportBatch,
    PodAttempt,
    PodField,
    PodFieldName,
    PodStatus,
    Trip,
    User,
)
from app.rules import INDIA
from app.status import Actor, move_trip
from app.tally import Voucher, VoucherLine, build_xml

PHOTO_EXTENSIONS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}

EARLIER_EXPORTS_SHOWN = 20


@dataclass(frozen=True, order=True)
class Cycle:
    """Every client bills on the same two cycles: the 1st to 15th and the 16th to month end."""

    start: date
    end: date


def cycle_of(delivered_at: datetime) -> Cycle:
    """Uses India's date: a delivery at 01:00 on the 16th in India is still the 15th in UTC."""
    day = delivered_at.astimezone(INDIA).date()
    if day.day <= 15:
        return Cycle(day.replace(day=1), day.replace(day=15))
    last_day = calendar.monthrange(day.year, day.month)[1]
    return Cycle(day.replace(day=16), day.replace(day=last_day))


@dataclass(frozen=True)
class BillingRow:
    trip: Trip
    client: Client
    cycle: Cycle
    lr_number: str
    remark: str | None


def latest_attempts(session: Session, trip_ids: list[UUID]) -> dict[UUID, UUID]:
    """Each trip's highest checked attempt (spec assumption 2), so billing and the ZIP agree.

    Names columns rather than the PodAttempt entity, which would load every photo's bytes.
    """
    rows = session.execute(
        select(PodAttempt.trip_id, PodAttempt.id)
        .where(PodAttempt.trip_id.in_(trip_ids), PodAttempt.attempt_no <= LAST_CHECKED_ATTEMPT_NO)
        .order_by(PodAttempt.trip_id, PodAttempt.attempt_no.desc())
        .ext(distinct_on(PodAttempt.trip_id))
    )
    return {trip_id: attempt_id for trip_id, attempt_id in rows}


def remark_note(remarks: dict[str, Any] | None) -> str | None:
    """Any remark goes on the voucher, not only a shortage, so a note about damage isn't lost."""
    if not remarks or remarks.get("kind") in (None, "none"):
        return None
    return remarks.get("text") or f"{remarks['kind'].capitalize()} remark"


def billing_rows(session: Session, condition: ColumnElement[bool]) -> list[BillingRow]:
    """Trips with what billing needs from their PODs, always from final_value.

    The join needs a first attempt, because that's what sets the delivery time and so the cycle
    (spec assumption 1). Every trip that reaches a person or billing has one.
    """
    first = aliased(PodAttempt)
    found = session.execute(
        select(Trip, Client, first.captured_at)
        .join(Client, Trip.client_id == Client.id)
        .join(first, and_(first.trip_id == Trip.id, first.attempt_no == 1))
        .where(condition)
    ).all()

    attempts = latest_attempts(session, [trip.id for trip, _, _ in found])
    fields = session.execute(
        select(PodField.attempt_id, PodField.field, PodField.final_value).where(
            PodField.attempt_id.in_(attempts.values()),
            PodField.field.in_([PodFieldName.LR_NUMBER, PodFieldName.REMARKS]),
        )
    ).all()
    finals = {(attempt_id, field): value for attempt_id, field, value in fields}

    rows = []
    for trip, client, delivered_at in found:
        attempt_id = attempts.get(trip.id)
        rows.append(
            BillingRow(
                trip=trip,
                client=client,
                cycle=cycle_of(delivered_at),
                lr_number=finals.get((attempt_id, PodFieldName.LR_NUMBER)) or trip.lr_number,
                remark=remark_note(finals.get((attempt_id, PodFieldName.REMARKS))),
            )
        )
    return rows


@dataclass(frozen=True)
class BillingQueue:
    cycles: list[tuple[Cycle, int]]  # Newest first, each with its verified trip count.
    cycle: Cycle | None
    rows: list[BillingRow]  # The chosen cycle's verified trips, by client and then trip.
    in_review: int


def billing_queue(session: Session, wanted_start: date | None) -> BillingQueue:
    rows = billing_rows(
        session, Trip.pod_status.in_([PodStatus.VERIFIED, PodStatus.NEEDS_REVIEW])
    )
    verified = [row for row in rows if row.trip.pod_status == PodStatus.VERIFIED]
    counts = Counter(row.cycle for row in verified)  # Spec assumption 12: any cycle with trips.
    cycles = sorted(counts, reverse=True)

    # A cycle that has just been exported in full has gone, so this falls back to the newest.
    cycle = next((c for c in cycles if c.start == wanted_start), cycles[0] if cycles else None)
    in_review = [row for row in rows if row.trip.pod_status == PodStatus.NEEDS_REVIEW]
    return BillingQueue(
        cycles=[(c, counts[c]) for c in cycles],
        cycle=cycle,
        rows=sorted(
            (row for row in verified if row.cycle == cycle),
            key=lambda row: (row.client.name, row.trip.trip_code),
        ),
        # With no cycle to compare against, every trip in review is still worth pointing out.
        in_review=sum(1 for row in in_review if cycle is None or row.cycle == cycle),
    )


def build_vouchers(rows: list[BillingRow], batch_id: UUID, today: date) -> list[Voucher]:
    """One voucher per client, numbered from the batch so Tally never sees a number twice."""
    clients = sorted({row.client.id: row.client for row in rows}.values(), key=lambda c: c.name)
    return [
        Voucher(
            number=f"LND-{batch_id.hex[:8].upper()}-{position}",
            voucher_date=today,
            party_ledger=client.tally_ledger_name,
            lines=tuple(
                VoucherLine(
                    trip_code=row.trip.trip_code,
                    lr_number=row.lr_number,
                    eway_bill_no=row.trip.eway_bill_no,
                    freight_paise=row.trip.freight_paise,
                    remark=row.remark,
                )
                for row in sorted(rows, key=lambda row: row.trip.trip_code)
                if row.client.id == client.id
            ),
        )
        for position, client in enumerate(clients, start=1)
    ]


def refuse_if_not_exportable(rows: list[BillingRow], trips: list[Trip]) -> None:
    """All or nothing (spec assumption 11): naming the trips tells the executive what moved."""
    usable = {row.trip.id for row in rows}
    moved = sorted(
        trip.trip_code
        for trip in trips
        if trip.pod_status != PodStatus.VERIFIED or trip.id not in usable
    )
    if moved:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Nothing was exported, because these trips aren't verified: {', '.join(moved)}",
        )
    if len({row.cycle for row in rows}) > 1:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Export one cycle at a time")


def export_trips(session: Session, trip_ids: list[UUID], user: User) -> UUID:
    """Writes the batch, its stored XML and every trip's move in one transaction."""
    # Locked in ID order, so two overlapping exports wait for each other instead of deadlocking.
    trips = session.scalars(
        select(Trip).where(Trip.id.in_(trip_ids)).order_by(Trip.id).with_for_update()
    ).all()
    if len(trips) != len(set(trip_ids)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A selected trip no longer exists")

    rows = billing_rows(session, Trip.id.in_(trip_ids))
    refuse_if_not_exportable(rows, list(trips))

    batch_id = uuid4()
    vouchers = build_vouchers(rows, batch_id, datetime.now(UTC).astimezone(INDIA).date())
    cycle = rows[0].cycle
    session.add(
        ExportBatch(
            id=batch_id,
            cycle_start=cycle.start,
            cycle_end=cycle.end,
            created_by=user.id,
            trip_count=len(rows),
            total_paise=sum(voucher.total_paise for voucher in vouchers),
            xml=build_xml(vouchers),
        )
    )
    session.flush()  # The trips below point to this row.

    voucher_numbers = {
        line.trip_code: voucher.number for voucher in vouchers for line in voucher.lines
    }
    actor = Actor(ActorType.USER, user.id)
    for trip in trips:
        move_trip(session, trip, PodStatus.INVOICED, actor)
        trip.export_batch_id = batch_id
        trip.voucher_no = voucher_numbers[trip.trip_code]
        session.add(
            AuditEvent(
                trip_id=trip.id,
                actor_type=actor.type,
                actor_id=actor.id,
                action="exported",
                detail={"batch_id": str(batch_id), "voucher_no": trip.voucher_no},
            )
        )
    session.commit()
    return batch_id


def export_summaries(session: Session, *conditions: ColumnElement[bool]) -> list[Row]:
    """Newest first. The batch has no time of its own: its trips share one invoiced_at."""
    exported_at = func.min(Trip.invoiced_at).label("exported_at")
    return list(
        session.execute(
            select(ExportBatch.id, ExportBatch.trip_count, ExportBatch.total_paise, exported_at)
            .join(Trip, Trip.export_batch_id == ExportBatch.id)
            .where(*conditions)
            .group_by(ExportBatch.id)
            .order_by(exported_at.desc())
            .limit(EARLIER_EXPORTS_SHOWN)
        ).all()
    )


def pod_photos_zip(session: Session, batch_id: UUID) -> bytes:
    """One folder per voucher, ready to attach. Stored, not compressed: JPEGs don't shrink.

    Built in memory, which is fine at 300 KB a photo: even 200 trips is only 60 MB.
    """
    trips = session.execute(
        select(Trip.id, Trip.trip_code, Trip.voucher_no).where(Trip.export_batch_id == batch_id)
    ).all()
    attempts = latest_attempts(session, [trip.id for trip in trips])
    photos = dict(
        session.execute(
            select(PodAttempt.id, PodAttempt.image_bytes).where(
                PodAttempt.id.in_(attempts.values())
            )
        ).all()
    )

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_STORED) as archive:
        for trip in trips:
            photo = photos.get(attempts.get(trip.id))
            if photo:
                extension = PHOTO_EXTENSIONS.get(image_type(photo) or "", "")
                archive.writestr(f"{trip.voucher_no}/{trip.trip_code}{extension}", photo)
    return buffer.getvalue()
