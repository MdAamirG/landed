from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import require_role
from app.dashboard import FIGURE_WINDOW, figures, missing_pods, queue_counts, resend_link
from app.db import get_db
from app.intake import sweep_stuck_attempts
from app.models import Role, User
from app.schemas import BranchDaysOut, DashboardOut, MissingPodOut, QueueCountsOut, ResendOut

router = APIRouter(prefix="/dashboard")

# Both office roles: the core build works with only the billing executive (story 70).
OfficeUser = Annotated[User, Depends(require_role(Role.BILLING_EXECUTIVE, Role.OPERATIONS_HEAD))]
Db = Annotated[Session, Depends(get_db)]


@router.get("", response_model=DashboardOut)
def dashboard(_: OfficeUser, db: Db) -> DashboardOut:
    sweep_stuck_attempts(db)  # Spec assumption 3: the 60-second rule runs on read.
    now = datetime.now(UTC)
    found = figures(db, now)
    return DashboardOut(
        window_days=FIGURE_WINDOW.days,
        missing=[MissingPodOut.model_validate(row) for row in missing_pods(db, now)],
        within_24_hours_percent=found.within_24_hours_percent,
        pod_to_invoice_days=found.pod_to_invoice_days,
        lost_or_disputed_percent=found.lost_or_disputed_percent,
        branches=[BranchDaysOut.model_validate(branch) for branch in found.branches],
    )


@router.get("/counts", response_model=QueueCountsOut)
def counts(_: OfficeUser, db: Db) -> QueueCountsOut:
    sweep_stuck_attempts(db)  # Keeps the Review count honest, as Billing's in-review count does.
    return QueueCountsOut.model_validate(queue_counts(db, datetime.now(UTC)))


@router.post("/trips/{trip_id}/resend-link", response_model=ResendOut)
def resend(trip_id: UUID, user: OfficeUser, db: Db) -> ResendOut:
    return resend_link(db, trip_id, user)
