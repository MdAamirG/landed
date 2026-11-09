from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from app.auth import require_role
from app.db import get_db
from app.models import Role, User
from app.schemas import ImportOut, ImportRowOut
from app.trip_import import (
    MAX_FILE_BYTES,
    CheckedRow,
    check_rows,
    import_rows,
    read_file,
    stored_filename,
)

router = APIRouter(prefix="/trips")

# Only the billing executive imports trips (the roles table in docs/data-model.md).
BillingUser = Annotated[User, Depends(require_role(Role.BILLING_EXECUTIVE))]
Db = Annotated[Session, Depends(get_db)]


def file_bytes(file: UploadFile) -> bytes:
    return file.file.read(MAX_FILE_BYTES + 1)  # One byte over is enough to know it's too big.


def result(file: UploadFile, checked: list[CheckedRow], batch_id: UUID | None = None) -> ImportOut:
    return ImportOut(
        filename=stored_filename(file.filename),
        rows_total=len(checked),
        rows_ok=sum(row.ok for row in checked),
        rows=[ImportRowOut.model_validate(row) for row in checked],
        import_batch_id=batch_id,
    )


@router.post("/import/check", response_model=ImportOut)
def check_file(file: UploadFile, _: BillingUser, db: Db) -> ImportOut:
    """What would happen to each row. Stores nothing, so the executive can look before importing."""
    return result(file, check_rows(db, read_file(file_bytes(file))))


@router.post("/import", response_model=ImportOut)
def import_file(file: UploadFile, user: BillingUser, db: Db) -> ImportOut:
    """The screen sends the same file again, so nothing is held on the server between the steps."""
    batch, checked = import_rows(db, file.filename, read_file(file_bytes(file)), user)
    return result(file, checked, batch.id)
