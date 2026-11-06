"""Pydantic models for what the API sends and receives."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import PodStatus, Role


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
