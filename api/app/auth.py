"""Office sign-in: password checks, the session token and the role checks routes depend on.

Drivers don't come through here. They have no accounts, and their links are checked separately.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Role, User

SESSION_COOKIE = "landed_session"
SESSION_LIFETIME = timedelta(hours=8)  # A working day, so staff sign in once a shift.
TOKEN_ALGORITHM = "HS256"

# The seeded demo accounts. seed.py creates them, and the demo buttons sign in as them.
DEMO_EMAILS = {
    Role.BILLING_EXECUTIVE: "billing@example.com",
    Role.OPERATIONS_HEAD: "ops@example.com",
}

hasher = PasswordHasher()
# Checked when the email is unknown, so that case takes as long as a wrong password
# and response time can't reveal which emails have accounts.
UNKNOWN_USER_HASH = hasher.hash("no account has this password")


def hash_password(password: str) -> str:
    return hasher.hash(password)


def password_matches(user: User | None, password: str) -> bool:
    stored_hash = user.password_hash if user else UNKNOWN_USER_HASH
    try:
        hasher.verify(stored_hash, password)
    except VerifyMismatchError:
        return False
    return user is not None


def make_session_token(user: User) -> str:
    # Only the user ID goes in. The role is read from the database on every request,
    # so a changed role takes effect at once rather than when the token expires.
    now = datetime.now(UTC)
    claims = {"sub": str(user.id), "iat": now, "exp": now + SESSION_LIFETIME}
    return jwt.encode(claims, settings.session_secret, algorithm=TOKEN_ALGORITHM)


def read_session_token(token: str) -> UUID | None:
    """The user ID in a valid token. None if it is expired, tampered with or not ours."""
    try:
        claims = jwt.decode(
            token,
            settings.session_secret,
            algorithms=[TOKEN_ALGORITHM],  # Pinned, so a token can't pick its own algorithm.
            options={"require": ["exp", "sub"]},
        )
    except jwt.InvalidTokenError:
        return None
    return UUID(claims["sub"])


def set_session_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        make_session_token(user),
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,  # Page scripts can't read it, so an XSS bug can't steal the session.
        samesite="lax",  # Another site can't make a browser POST with this cookie.
        secure=settings.cookie_secure,
    )


def clear_session_cookie(response: Response) -> None:
    # Only the cookie goes. The token itself can't be cancelled and stays valid until it
    # expires, which is why the lifetime is short.
    response.delete_cookie(
        SESSION_COOKIE, httponly=True, samesite="lax", secure=settings.cookie_secure
    )


def current_user(
    db: Annotated[Session, Depends(get_db)],
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> User:
    """The signed-in user, or 401. A token for a deleted user fails here too."""
    user_id = read_session_token(session_token) if session_token else None
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    return user


def require_role(*roles: Role) -> Callable[[User], User]:
    """A route dependency: 401 if not signed in, 403 if signed in with another role."""

    def check_role(user: Annotated[User, Depends(current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role can't do this")
        return user

    return check_role
