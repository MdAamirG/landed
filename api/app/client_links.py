"""Client POD links: a read-only view of one client's PODs for its accounts team (story 77).

There's no table for these (spec assumption 14), so a link is a signed token that carries the
client and its expiry, and checking it needs no lookup. Nothing is stored, so a link can't be
revoked before it expires, which is why it lasts only 7 days. Each link made is logged.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import TOKEN_ALGORITHM
from app.billing import BillingRow, billing_rows, latest_attempts
from app.config import settings
from app.db import get_db
from app.models import ActorType, AuditEvent, Client, PodAttempt, PodStatus, Trip, User

CLIENT_LINK_LIFETIME = timedelta(days=7)

# The same secret signs office sessions, so the audience claim keeps the two apart: a session
# token has none and is refused here, and a client token has one and is refused as a session.
AUDIENCE = "client-pods"

# A client sees only proof the office has accepted. A POD still in review or disputed is the
# office's to settle first.
SHOWN = (PodStatus.VERIFIED, PodStatus.INVOICED)

# auto_error=False: a missing token gets the same 401 as a bad one.
bearer_token = HTTPBearer(auto_error=False)


def client_url(token: str) -> str:
    return f"{settings.web_origin}/c/{token}"


def make_client_link(session: Session, client_id: UUID, user: User) -> tuple[str, datetime]:
    """A new link's token and expiry, and an audit event saying who made it for which client."""
    client = session.get(Client, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such client")

    # Whole seconds, because the token's exp claim holds whole seconds.
    expires_at = (datetime.now(UTC) + CLIENT_LINK_LIFETIME).replace(microsecond=0)
    claims = {"sub": str(client.id), "aud": AUDIENCE, "exp": expires_at}
    token = jwt.encode(claims, settings.session_secret, algorithm=TOKEN_ALGORITHM)

    session.add(
        AuditEvent(
            trip_id=None,  # A link covers a client, not one trip.
            actor_type=ActorType.USER,
            actor_id=user.id,
            action="client_link_created",
            # The token stays out of the log: anyone who could read it could use it.
            detail={"client_id": str(client.id), "expires_at": expires_at.isoformat()},
        )
    )
    session.commit()
    return token, expires_at


def read_client_token(token: str) -> tuple[UUID, datetime] | None:
    """The client and expiry in a valid token. None if expired, tampered with or not one of ours."""
    try:
        claims = jwt.decode(
            token,
            settings.session_secret,
            algorithms=[TOKEN_ALGORITHM],  # Pinned, so a token can't pick its own algorithm.
            audience=AUDIENCE,
            options={"require": ["exp", "sub", "aud"]},
        )
        return UUID(claims["sub"]), datetime.fromtimestamp(claims["exp"], UTC)
    except (jwt.InvalidTokenError, ValueError):  # ValueError: a signed sub that isn't a UUID.
        return None


@dataclass(frozen=True)
class LinkedClient:
    client: Client
    expires_at: datetime


def linked_client(
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_token)],
) -> LinkedClient:
    """The client behind this request's link, or 401.

    The token comes in a header rather than the API path, as a driver's does, so it stays out of
    the API's request logs.
    """
    found = read_client_token(credentials.credentials) if credentials else None
    client = db.get(Client, found[0]) if found else None
    if found is None or client is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This link doesn't work")
    return LinkedClient(client, found[1])


def client_pods(session: Session, client: Client) -> list[BillingRow]:
    """The client's accepted PODs, newest delivery first. Reuses billing's reading of each POD,
    so the client sees the same LR and remark that went on the invoice.
    """
    rows = billing_rows(session, (Trip.client_id == client.id) & Trip.pod_status.in_(SHOWN))
    return sorted(rows, key=lambda row: row.delivered_at, reverse=True)


def pod_photo(session: Session, client: Client, trip_id: UUID) -> bytes:
    """The photo behind one of the client's PODs: the same one billing used (spec assumption 2).

    Any trip that isn't this client's, or isn't shown on its page, is a 404, so a client can't
    tell another client's trip from one that doesn't exist.
    """
    trip = session.get(Trip, trip_id)
    if trip is None or trip.client_id != client.id or trip.pod_status not in SHOWN:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    attempt_id = latest_attempts(session, [trip.id]).get(trip.id)
    photo = session.scalar(select(PodAttempt.image_bytes).where(PodAttempt.id == attempt_id))
    if photo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return photo
