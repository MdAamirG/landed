"""The twelve tables in docs/data-model.md.

Allowed values are text columns with CHECK constraints rather than Postgres enums, because
changing a CHECK in a migration is simpler than altering an enum type.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Double,
    ForeignKey,
    Identity,
    Index,
    LargeBinary,
    MetaData,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class PodStatus(StrEnum):
    AWAITING_POD = "awaiting_pod"
    CHECKING = "checking"
    RETAKE_REQUESTED = "retake_requested"
    NEEDS_REVIEW = "needs_review"
    VERIFIED = "verified"
    DISPUTED = "disputed"
    INVOICED = "invoiced"


class Role(StrEnum):
    BILLING_EXECUTIVE = "billing_executive"
    OPERATIONS_HEAD = "operations_head"


class Ownership(StrEnum):
    OWN = "own"
    HIRED = "hired"


class Language(StrEnum):
    HINDI = "hi"
    MARATHI = "mr"
    ENGLISH = "en"


class ActorType(StrEnum):
    USER = "user"
    DRIVER_LINK = "driver_link"
    SYSTEM = "system"


class AiStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"  # A late photo, which never goes to the AI.


class DeviceCheck(StrEnum):
    """What the phone's own blur and brightness check said. Empty on an old or fake client."""

    PASSED = "passed"
    SENT_ANYWAY = "sent_anyway"  # It failed twice, and the driver sent the photo regardless.


class PodFieldName(StrEnum):
    """The six fields the AI reads. image_quality has no confidence, so it stays in ai_raw."""

    LR_NUMBER = "lr_number"
    CONSIGNEE_STAMP = "consignee_stamp"
    QUANTITY_RECEIVED = "quantity_received"
    REMARKS = "remarks"
    DELIVERY_DATE = "delivery_date"
    SIGNATURE = "signature"


def one_of(column: str, allowed: type[StrEnum]) -> CheckConstraint:
    """A CHECK that the column holds one of the enum's values."""
    values = ", ".join(f"'{member.value}'" for member in allowed)
    return CheckConstraint(f"{column} IN ({values})", name=column)


class Base(DeclarativeBase):
    # Fixed names, so a later migration can refer to a constraint without looking it up.
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_N_name)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )
    # Times are always stored with a zone, and the app writes UTC.
    type_annotation_map = {datetime: DateTime(timezone=True)}


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(Text, unique=True)


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(Text, unique=True)
    tally_ledger_name: Mapped[str] = mapped_column(Text)


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (one_of("ownership", Ownership),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    registration_no: Mapped[str] = mapped_column(Text, unique=True)
    ownership: Mapped[str] = mapped_column(Text)


class Driver(Base):
    __tablename__ = "drivers"
    __table_args__ = (one_of("language", Language),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(Text)
    phone: Mapped[str] = mapped_column(Text)  # Personal data: masked like the consignee's.
    language: Mapped[str] = mapped_column(Text)


class User(Base):
    """Office staff only. Drivers have no accounts."""

    __tablename__ = "users"
    __table_args__ = (one_of("role", Role),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    branch_id: Mapped[UUID | None] = mapped_column(ForeignKey("branches.id"))


class ImportBatch(Base):
    """One per daily trip file."""

    __tablename__ = "import_batches"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    filename: Mapped[str] = mapped_column(Text)
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    rows_total: Mapped[int]
    rows_ok: Mapped[int]
    errors: Mapped[list[Any]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))


class ExportBatch(Base):
    """One export. It can hold vouchers for several clients."""

    __tablename__ = "export_batches"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    cycle_start: Mapped[date] = mapped_column(Date)
    cycle_end: Mapped[date] = mapped_column(Date)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    trip_count: Mapped[int]
    total_paise: Mapped[int] = mapped_column(BigInteger)
    xml: Mapped[str] = mapped_column(Text)  # Stored, so a re-download returns identical XML.


class Trip(Base):
    __tablename__ = "trips"
    __table_args__ = (
        one_of("pod_status", PodStatus),
        CheckConstraint("retakes_used BETWEEN 0 AND 2", name="retakes_used"),
        CheckConstraint("eway_bill_no ~ '^[0-9]{12}$'", name="eway_bill_no"),
        CheckConstraint("freight_paise >= 0", name="freight_paise"),
        Index(None, "client_id", "pod_status"),  # None: the naming convention supplies the name.
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    trip_code: Mapped[str] = mapped_column(Text, unique=True)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id"))
    branch_id: Mapped[UUID] = mapped_column(ForeignKey("branches.id"))
    vehicle_id: Mapped[UUID] = mapped_column(ForeignKey("vehicles.id"))
    driver_id: Mapped[UUID] = mapped_column(ForeignKey("drivers.id"))
    origin: Mapped[str] = mapped_column(Text)
    destination: Mapped[str] = mapped_column(Text)
    lr_number: Mapped[str] = mapped_column(Text, unique=True)
    eway_bill_no: Mapped[str] = mapped_column(Text, index=True)
    qty_dispatched: Mapped[Decimal] = mapped_column(Numeric(12, 3))  # Tonnes can be fractional.
    qty_unit: Mapped[str] = mapped_column(Text)
    freight_paise: Mapped[int] = mapped_column(BigInteger)
    consignee_name: Mapped[str] = mapped_column(Text)  # Personal data: masked in every response.
    consignee_phone: Mapped[str] = mapped_column(Text)  # Personal data: masked in every response.
    consignee_lat: Mapped[float] = mapped_column(Double)
    consignee_lng: Mapped[float] = mapped_column(Double)
    dispatched_at: Mapped[datetime]
    expected_delivery_at: Mapped[datetime]
    pod_status: Mapped[str] = mapped_column(
        Text, index=True, server_default=PodStatus.AWAITING_POD.value
    )
    status_reason: Mapped[str | None] = mapped_column(Text)
    retakes_used: Mapped[int] = mapped_column(server_default=text("0"))
    verified_at: Mapped[datetime | None]
    verified_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))  # Empty if the AI did.
    export_batch_id: Mapped[UUID | None] = mapped_column(ForeignKey("export_batches.id"))
    voucher_no: Mapped[str | None] = mapped_column(Text)  # Shared by trips on the same voucher.
    invoiced_at: Mapped[datetime | None]
    is_demo: Mapped[bool] = mapped_column(server_default=text("false"))
    version: Mapped[int] = mapped_column(server_default=text("1"))  # Blocks overlapping saves.


class PodAttempt(Base):
    """One photo. Attempt numbers 1 to 3 are checked; 4 and up are late photos."""

    __tablename__ = "pod_attempts"
    __table_args__ = (
        UniqueConstraint("trip_id", "attempt_no"),
        CheckConstraint("attempt_no >= 1", name="attempt_no"),
        one_of("device_check", DeviceCheck),
        one_of("ai_status", AiStatus),
        one_of("outcome", PodStatus),
    )

    # No default: the phone makes this ID, which is what makes offline retries safe.
    id: Mapped[UUID] = mapped_column(primary_key=True)
    trip_id: Mapped[UUID] = mapped_column(ForeignKey("trips.id"))
    attempt_no: Mapped[int]
    image_bytes: Mapped[bytes | None] = mapped_column(LargeBinary)
    image_key: Mapped[str | None] = mapped_column(Text)  # For a later move to object storage.
    size_bytes: Mapped[int]
    sha256: Mapped[str] = mapped_column(Text)
    captured_at: Mapped[datetime]  # From the phone.
    received_at: Mapped[datetime] = mapped_column(server_default=func.now())  # From the server.
    gps_lat: Mapped[float | None] = mapped_column(Double)
    gps_lng: Mapped[float | None] = mapped_column(Double)
    gps_accuracy_m: Mapped[float | None] = mapped_column(Double)
    distance_km: Mapped[float | None] = mapped_column(Double)
    device_check: Mapped[str | None] = mapped_column(Text)
    ai_status: Mapped[str | None] = mapped_column(Text)
    ai_model: Mapped[str | None] = mapped_column(Text)
    ai_latency_ms: Mapped[int | None]
    ai_raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    outcome: Mapped[str | None] = mapped_column(Text)
    reason_codes: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))


class PodField(Base):
    """One field of one attempt: what the AI read, and the value billing uses."""

    __tablename__ = "pod_fields"
    __table_args__ = (one_of("field", PodFieldName),)

    attempt_id: Mapped[UUID] = mapped_column(ForeignKey("pod_attempts.id"), primary_key=True)
    field: Mapped[str] = mapped_column(Text, primary_key=True)
    # jsonb because quantity is a number and unit, and remarks are text and a kind.
    ai_value: Mapped[Any | None] = mapped_column(JSONB)
    ai_confidence: Mapped[float | None] = mapped_column(Double)
    final_value: Mapped[Any | None] = mapped_column(JSONB)
    edited_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    edited_at: Mapped[datetime | None]


class DriverLink(Base):
    __tablename__ = "driver_links"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    trip_id: Mapped[UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)  # The token itself is never stored.
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    sent_at: Mapped[datetime | None]


class AuditEvent(Base):
    """Append-only: status changes, field edits, reveals, exports and retake requests."""

    __tablename__ = "audit_events"
    __table_args__ = (
        one_of("actor_type", ActorType),
        # The upload limit counts a trip's recent uploads from this table.
        Index(None, "trip_id", "action", "at"),
    )

    # A growing number, so events keep their order even within one transaction's timestamp.
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    trip_id: Mapped[UUID | None] = mapped_column(ForeignKey("trips.id"))
    actor_type: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[UUID | None]  # A user or a driver link, so no foreign key. Empty for system.
    action: Mapped[str] = mapped_column(Text)
    from_status: Mapped[str | None] = mapped_column(Text)
    to_status: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    at: Mapped[datetime] = mapped_column(server_default=func.now())
