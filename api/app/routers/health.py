import logging

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import HealthOut, PingOut

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/ping", response_model=PingOut)
def ping() -> PingOut:
    """For uptime monitors. It stays off the database, so Neon can suspend when idle."""
    return PingOut(status="ok")


@router.get("/health", response_model=HealthOut)
def health(response: Response, db: Session = Depends(get_db)) -> HealthOut:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        # The details go to the log, not the response: this route is public.
        logger.exception("Health check could not reach the database")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthOut(status="degraded", database="unreachable")
    return HealthOut(status="ok", database="reachable")
