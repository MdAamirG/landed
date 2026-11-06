from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth import require_role
from app.billing import (
    BillingRow,
    billing_queue,
    export_summaries,
    export_trips,
    pod_photos_zip,
)
from app.db import get_db
from app.intake import sweep_stuck_attempts
from app.models import ExportBatch, Role, User
from app.schemas import (
    BillingClientOut,
    BillingCycleOut,
    BillingQueueOut,
    BillingTripOut,
    ExportIn,
    ExportOut,
)

router = APIRouter(prefix="/billing")

BillingExecutive = Annotated[User, Depends(require_role(Role.BILLING_EXECUTIVE))]
Db = Annotated[Session, Depends(get_db)]


def clients_out(rows: list[BillingRow]) -> list[BillingClientOut]:
    """Groups rows under their client. Rows arrive sorted, so the order carries through."""
    clients: dict[UUID, BillingClientOut] = {}
    for row in rows:
        client = clients.setdefault(
            row.client.id,
            BillingClientOut(client_id=row.client.id, client_name=row.client.name, trips=[]),
        )
        client.trips.append(
            BillingTripOut(
                id=row.trip.id,
                trip_code=row.trip.trip_code,
                destination=row.trip.destination,
                lr_number=row.lr_number,
                remark=row.remark,
                freight_paise=row.trip.freight_paise,
            )
        )
    return list(clients.values())


def download(content: bytes | str, media_type: str, filename: str) -> Response:
    return Response(
        content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/queue", response_model=BillingQueueOut)
def queue(_: BillingExecutive, db: Db, cycle: date | None = None) -> BillingQueueOut:
    sweep_stuck_attempts(db)  # Spec assumption 3, and it keeps the in-review count honest.
    found = billing_queue(db, cycle)
    return BillingQueueOut(
        cycles=[
            BillingCycleOut(start=item.start, end=item.end, trip_count=count)
            for item, count in found.cycles
        ],
        cycle_start=found.cycle.start if found.cycle else None,
        clients=clients_out(found.rows),
        in_review=found.in_review,
    )


@router.get("/exports", response_model=list[ExportOut])
def exports(_: BillingExecutive, db: Db) -> list[ExportOut]:
    return [ExportOut.model_validate(row) for row in export_summaries(db)]


@router.post("/exports", response_model=ExportOut, status_code=status.HTTP_201_CREATED)
def create_export(body: ExportIn, user: BillingExecutive, db: Db) -> ExportOut:
    batch_id = export_trips(db, body.trip_ids, user)
    return ExportOut.model_validate(export_summaries(db, ExportBatch.id == batch_id)[0])


def stored_batch(db: Session, batch_id: UUID) -> ExportBatch:
    batch = db.get(ExportBatch, batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return batch


@router.get("/exports/{batch_id}/xml")
def export_xml(batch_id: UUID, _: BillingExecutive, db: Db) -> Response:
    """Returns the stored XML, never a fresh build, so a re-download can't change a voucher."""
    batch = stored_batch(db, batch_id)
    return download(batch.xml, "application/xml", f"landed-tally-{batch.id.hex[:8]}.xml")


@router.get("/exports/{batch_id}/photos")
def export_photos(batch_id: UUID, _: BillingExecutive, db: Db) -> Response:
    batch = stored_batch(db, batch_id)
    photos = pod_photos_zip(db, batch.id)
    return download(photos, "application/zip", f"landed-pods-{batch.id.hex[:8]}.zip")
