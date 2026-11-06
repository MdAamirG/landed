"""Driver links: the signed links that open one trip for its driver. Drivers have no accounts.

Only a keyed hash of each token is stored, so a database leak alone doesn't give anyone a working
link. The token itself exists in the SMS and in the URL, and never in a response or audit event.
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import AuditEvent, DriverLink, Trip
from app.status import LINK_LIFETIME, SYSTEM, Actor

# auto_error=False: we answer a missing token with the same 401 as a bad one.
bearer_token = HTTPBearer(auto_error=False)


def hash_token(token: str) -> str:
    key = settings.driver_link_secret.encode()
    return hmac.new(key, token.encode(), hashlib.sha256).hexdigest()


def create_link(session: Session, trip: Trip, actor: Actor = SYSTEM) -> str:
    """Add a link for the trip and return its token, the one time it is available. Caller commits."""
    token = secrets.token_urlsafe(32)
    link = DriverLink(
        trip_id=trip.id,
        token_hash=hash_token(token),
        expires_at=trip.expected_delivery_at + LINK_LIFETIME,
    )
    session.add(link)
    session.flush()
    session.add(
        AuditEvent(
            trip_id=trip.id,
            actor_type=actor.type,
            actor_id=actor.id,
            action="driver_link_created",
            detail={"link_id": str(link.id), "expires_at": link.expires_at.isoformat()},
        )
    )
    session.flush()
    return token


def driver_url(token: str) -> str:
    return f"{settings.web_origin}/d/{token}"


def valid_driver_link(
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_token)],
) -> DriverLink:
    """The link behind this request, or 401. The phone can't tell why, and doesn't need to:
    a bad, expired or revoked link all mean the same thing to a driver, which is call the office.
    """
    link = None
    if credentials:
        link = db.scalar(
            select(DriverLink).where(DriverLink.token_hash == hash_token(credentials.credentials))
        )
    if link is None or link.revoked_at is not None or link.expires_at <= datetime.now(UTC):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This link doesn't work")
    return link
