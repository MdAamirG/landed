from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    DEMO_EMAILS,
    clear_session_cookie,
    current_user,
    password_matches,
    set_session_cookie,
)
from app.config import settings
from app.db import get_db
from app.models import User
from app.schemas import AuthOptionsOut, DemoLoginIn, LoginIn, OfficeUserOut

router = APIRouter(prefix="/auth")


@router.get("/options", response_model=AuthOptionsOut)
def options() -> AuthOptionsOut:
    """Public: the sign-in screen asks this before anyone is signed in."""
    return AuthOptionsOut(demo_mode=settings.demo_mode)


@router.post("/login", response_model=OfficeUserOut)
def login(body: LoginIn, response: Response, db: Annotated[Session, Depends(get_db)]) -> User:
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if not password_matches(user, body.password):
        # One message for both cases, so this can't be used to find out who has an account.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    set_session_cookie(response, user)
    return user


@router.post("/demo-login", response_model=OfficeUserOut)
def demo_login(
    body: DemoLoginIn, response: Response, db: Annotated[Session, Depends(get_db)]
) -> User:
    """The demo role buttons. With DEMO_MODE off this route doesn't exist as far as callers see."""
    if not settings.demo_mode:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    user = db.scalar(select(User).where(User.email == DEMO_EMAILS[body.role]))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The demo users haven't been seeded")
    set_session_cookie(response, user)
    return user


# Public on purpose: someone whose token has expired must still be able to clear the cookie.
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    clear_session_cookie(response)


@router.get("/me", response_model=OfficeUserOut)
def me(user: Annotated[User, Depends(current_user)]) -> User:
    return user
