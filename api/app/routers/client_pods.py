from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_role
from app.client_links import (
    LinkedClient,
    client_pods,
    client_url,
    linked_client,
    make_client_link,
    pod_photo,
)
from app.db import get_db
from app.intake import image_type
from app.masking import mask_name
from app.models import Client, PodStatus, Role, User
from app.schemas import ClientLinkIn, ClientLinkOut, ClientOut, ClientPodOut, ClientPodsOut

router = APIRouter()

# Both office roles. The data model gives the link to the operations head, and story 70 gives the
# billing executive the same dashboard, which is where the link is made (spec assumption 47).
OfficeUser = Annotated[User, Depends(require_role(Role.BILLING_EXECUTIVE, Role.OPERATIONS_HEAD))]
Linked = Annotated[LinkedClient, Depends(linked_client)]
Db = Annotated[Session, Depends(get_db)]


@router.get("/client-links/clients", response_model=list[ClientOut])
def clients(_: OfficeUser, db: Db) -> list[Client]:
    return list(db.scalars(select(Client).order_by(Client.name)))


@router.post("/client-links", response_model=ClientLinkOut, status_code=status.HTTP_201_CREATED)
def create_link(body: ClientLinkIn, user: OfficeUser, db: Db) -> ClientLinkOut:
    token, expires_at = make_client_link(db, body.client_id, user)
    return ClientLinkOut(url=client_url(token), expires_at=expires_at)


# The client's own routes. No sign-in: the link is the only key, and it opens only reads.


@router.get("/client-pods", response_model=ClientPodsOut)
def pods(linked: Linked, db: Db) -> ClientPodsOut:
    return ClientPodsOut(
        client_name=linked.client.name,
        expires_at=linked.expires_at,
        pods=[
            ClientPodOut(
                trip_id=row.trip.id,
                trip_code=row.trip.trip_code,
                lr_number=row.lr_number,
                eway_bill_no=row.trip.eway_bill_no,
                origin=row.trip.origin,
                destination=row.trip.destination,
                consignee_name=mask_name(row.trip.consignee_name),
                delivered_at=row.delivered_at,
                remark=row.remark,
                invoiced=row.trip.pod_status == PodStatus.INVOICED,
                voucher_no=row.trip.voucher_no,
            )
            for row in client_pods(db, linked.client)
        ],
    )


@router.get("/client-pods/trips/{trip_id}/photo")
def photo(trip_id: UUID, linked: Linked, db: Db) -> Response:
    data = pod_photo(db, linked.client, trip_id)
    # private: a shared cache must never hand one client's photo to someone else.
    return Response(data, media_type=image_type(data), headers={"Cache-Control": "private"})
