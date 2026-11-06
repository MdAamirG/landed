"""Pydantic models for what the API sends and receives."""

from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.models import DeviceCheck, Ownership, PodFieldName, PodStatus, Role


class PingOut(BaseModel):
    status: Literal["ok"]


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["reachable", "unreachable"]


class AuthOptionsOut(BaseModel):
    demo_mode: bool


class LoginIn(BaseModel):
    email: str = Field(min_length=1, max_length=254)
    # The cap stops someone making the server hash a huge string.
    password: str = Field(min_length=1, max_length=128)


class DemoLoginIn(BaseModel):
    role: Role


class OfficeUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    email: str
    role: Role


class DriverTripOut(BaseModel):
    """What a driver may see. It lists fields one by one, so consignee details can't leak in."""

    trip_code: str
    registration_no: str
    client_name: str
    origin: str
    destination: str
    lr_number: str
    eway_bill_no: str
    pod_status: PodStatus
    retakes_used: int
    reason_codes: list[str]  # Why a retake was asked for. Empty for any other status.


class AttemptForm(BaseModel):
    """The form fields sent with a photo. The ID comes from the phone, so retries are safe."""

    attempt_id: UUID
    captured_at: AwareDatetime  # A time without a zone couldn't be stored as UTC.
    gps_lat: float | None = Field(default=None, ge=-90, le=90)
    gps_lng: float | None = Field(default=None, ge=-180, le=180)
    gps_accuracy_m: float | None = Field(default=None, ge=0)
    device_check: DeviceCheck | None = None


class AttemptOut(BaseModel):
    attempt_id: UUID
    attempt_no: int
    outcome: PodStatus | None  # Empty until the check finishes.
    reason_codes: list[str]
    retakes_used: int


class VersionIn(BaseModel):
    """The trip version on the executive's screen. A stale one gets a 409."""

    version: int


class FieldEditIn(VersionIn):
    value: Any  # Each field has its own shape, so app/review.py validates this one.


class ContactOut(BaseModel):
    name: str
    phone: str


class ReviewQueueItemOut(BaseModel):
    id: UUID
    trip_code: str
    destination: str
    client_name: str
    ownership: Ownership
    status_reason: str | None
    waiting_since: datetime


class ReviewFieldOut(BaseModel):
    field: PodFieldName
    ai_value: Any
    ai_confidence: float | None
    final_value: Any
    edited: bool


class ReviewAttemptOut(BaseModel):
    id: UUID
    attempt_no: int
    late: bool
    captured_at: datetime
    received_at: datetime
    size_bytes: int
    distance_km: float | None
    device_check: DeviceCheck | None
    ai_status: str | None
    ai_latency_ms: int | None
    reason_codes: list[str]
    clock_corrected: bool
    fields: list[ReviewFieldOut]


class TripCheckOut(BaseModel):
    label: str
    ok: bool


class ReviewTripOut(BaseModel):
    """An executive's view of a trip. Consignee and driver contacts here are always masked."""

    id: UUID
    trip_code: str
    version: int
    pod_status: PodStatus
    status_reason: str | None
    reason_codes: list[str]
    retakes_used: int
    origin: str
    destination: str
    client_name: str
    ownership: Ownership
    registration_no: str
    lr_number: str
    eway_bill_no: str
    qty_dispatched: float
    qty_unit: str
    consignee_name: str
    consignee_phone: str
    driver_name: str
    driver_phone: str
    current_attempt_id: UUID | None  # The one Review and billing use. Late photos never count.
    attempts: list[ReviewAttemptOut]
    checks: list[TripCheckOut]


# What the AI must return, field for field from docs/data-model.md. A value of None means the
# AI couldn't find it on the paper. The model reports its own confidence, which isn't calibrated.
Confidence = Annotated[float, Field(ge=0, le=1)]


class TextReading(BaseModel):
    value: str | None
    confidence: Confidence


class PresenceReading(BaseModel):
    value: Literal["present", "absent"]
    confidence: Confidence


class QuantityReading(BaseModel):
    number: float | None = Field(ge=0, allow_inf_nan=False)
    unit: str | None
    confidence: Confidence


class RemarksReading(BaseModel):
    text: str | None
    kind: Literal["none", "shortage", "damage", "other"]
    confidence: Confidence


class DateReading(BaseModel):
    value: date | None
    confidence: Confidence


class PodReading(BaseModel):
    lr_number: TextReading
    consignee_stamp: PresenceReading
    quantity_received: QuantityReading
    remarks: RemarksReading
    delivery_date: DateReading
    signature: PresenceReading
    image_quality: Literal["ok", "blurred", "dark"]

    @property
    def lowest_confidence(self) -> float:
        """Across the six fields. Kept here so a new field can't escape the confidence check."""
        return min(
            self.lr_number.confidence,
            self.consignee_stamp.confidence,
            self.quantity_received.confidence,
            self.remarks.confidence,
            self.delivery_date.confidence,
            self.signature.confidence,
        )
