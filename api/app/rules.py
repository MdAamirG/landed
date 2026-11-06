"""The AI decision rule from docs/data-model.md: a pure function with no I/O.

decide() turns an AI reading into a status. The AI only suggests values; this fixed rule decides,
so the outcome can be explained and tested without calling a model.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from zoneinfo import ZoneInfo

from app.models import PodStatus
from app.schemas import PodReading

MAX_RETAKES = 2  # Fixed by the brief.

# Starting values to tune on the sample photos, as the data model says.
MAX_DISTANCE_KM = 2
MAX_DATE_GAP_DAYS = 1
MIN_CONFIDENCE = 0.80

INDIA = ZoneInfo("Asia/Kolkata")


class ReasonCode(StrEnum):
    """Every reason a POD can be stopped for. The list is also in docs/data-model.md."""

    AI_UNAVAILABLE = "ai_unavailable"
    PHOTO_BLURRED = "photo_blurred"
    PHOTO_DARK = "photo_dark"
    STAMP_MISSING = "stamp_missing"
    SIGNATURE_MISSING = "signature_missing"
    LR_MISSING = "lr_missing"
    QUANTITY_MISSING = "quantity_missing"
    DATE_MISSING = "date_missing"
    RETAKE_CAP_REACHED = "retake_cap_reached"
    LR_MISMATCH = "lr_mismatch"
    LOCATION_FAR = "location_far"
    DATE_MISMATCH = "date_mismatch"
    SHORTAGE_REMARK = "shortage_remark"
    DAMAGE_REMARK = "damage_remark"
    OTHER_REMARK = "other_remark"
    QTY_SHORT = "qty_short"
    QTY_MISMATCH = "qty_mismatch"
    LOW_CONFIDENCE = "low_confidence"


REMARK_CODES = {
    "shortage": ReasonCode.SHORTAGE_REMARK,
    "damage": ReasonCode.DAMAGE_REMARK,
    "other": ReasonCode.OTHER_REMARK,
}


@dataclass(frozen=True)
class Facts:
    """What the rule needs from the trip and the attempt."""

    lr_number: str
    qty_dispatched: Decimal
    qty_unit: str
    retakes_used: int
    distance_km: float | None  # None when the phone had no location.
    captured_at: datetime


@dataclass(frozen=True)
class Decision:
    status: PodStatus
    reason_codes: tuple[ReasonCode, ...] = ()  # Every match, so the executive sees them all.

    @property
    def reason(self) -> ReasonCode | None:
        """The first match, which becomes the trip's status_reason. None when verified."""
        return self.reason_codes[0] if self.reason_codes else None


def is_blank(text: str | None) -> bool:
    return not (text or "").strip()


def normalised(text: str) -> str:
    return text.strip().casefold()


def india_date(moment: datetime) -> date:
    return moment.astimezone(INDIA).date()


def quantity_is_missing(reading: PodReading) -> bool:
    return reading.quantity_received.number is None or is_blank(reading.quantity_received.unit)


def problems_the_driver_can_fix(reading: PodReading) -> list[ReasonCode]:
    """Check 2: a retake can fix these while the driver is still at the gate."""
    problems = []
    if reading.image_quality == "blurred":
        problems.append(ReasonCode.PHOTO_BLURRED)
    if reading.image_quality == "dark":
        problems.append(ReasonCode.PHOTO_DARK)
    if reading.consignee_stamp.value == "absent":
        problems.append(ReasonCode.STAMP_MISSING)
    if reading.signature.value == "absent":
        problems.append(ReasonCode.SIGNATURE_MISSING)
    if is_blank(reading.lr_number.value):
        problems.append(ReasonCode.LR_MISSING)
    if quantity_is_missing(reading):
        problems.append(ReasonCode.QUANTITY_MISSING)
    if reading.delivery_date.value is None:
        problems.append(ReasonCode.DATE_MISSING)
    return problems


def quantity_problem(reading: PodReading, facts: Facts) -> ReasonCode | None:
    """Check 7. A missing quantity is already check 2, so it isn't a mismatch as well."""
    if quantity_is_missing(reading):
        return None
    quantity = reading.quantity_received
    if normalised(quantity.unit) != normalised(facts.qty_unit):
        return ReasonCode.QTY_MISMATCH
    # Through str, because Decimal(23.9) keeps the float's rounding error and reads as short.
    received = Decimal(str(quantity.number))
    if received < facts.qty_dispatched:
        return ReasonCode.QTY_SHORT
    if received > facts.qty_dispatched:
        return ReasonCode.QTY_MISMATCH
    return None


def problems_for_a_person(reading: PodReading, facts: Facts) -> list[ReasonCode]:
    """Checks 3 to 8, in order. A retake can't settle these, so someone has to decide."""
    problems = []

    lr_read = reading.lr_number.value
    if not is_blank(lr_read) and normalised(lr_read) != normalised(facts.lr_number):
        problems.append(ReasonCode.LR_MISMATCH)

    # A missing location doesn't count, because dead zones are expected.
    if facts.distance_km is not None and facts.distance_km > MAX_DISTANCE_KM:
        problems.append(ReasonCode.LOCATION_FAR)

    paper_date = reading.delivery_date.value
    if paper_date is not None:
        days_apart = abs((paper_date - india_date(facts.captured_at)).days)
        if days_apart > MAX_DATE_GAP_DAYS:
            problems.append(ReasonCode.DATE_MISMATCH)

    # Whatever the confidence: a remark like "seal broken" never passes on its own.
    if reading.remarks.kind != "none":
        problems.append(REMARK_CODES[reading.remarks.kind])

    quantity = quantity_problem(reading, facts)
    if quantity:
        problems.append(quantity)

    if reading.lowest_confidence < MIN_CONFIDENCE:
        problems.append(ReasonCode.LOW_CONFIDENCE)

    return problems


def decide(reading: PodReading | None, facts: Facts) -> Decision:
    """Apply the nine checks. A reading of None means the AI failed, timed out or misbehaved."""
    if reading is None:
        return Decision(PodStatus.NEEDS_REVIEW, (ReasonCode.AI_UNAVAILABLE,))

    fixable = problems_the_driver_can_fix(reading)
    for_a_person = problems_for_a_person(reading, facts)

    if fixable and facts.retakes_used < MAX_RETAKES:
        return Decision(PodStatus.RETAKE_REQUESTED, (*fixable, *for_a_person))

    if fixable:
        return Decision(
            PodStatus.NEEDS_REVIEW, (ReasonCode.RETAKE_CAP_REACHED, *fixable, *for_a_person)
        )

    if for_a_person:
        return Decision(PodStatus.NEEDS_REVIEW, tuple(for_a_person))

    return Decision(PodStatus.VERIFIED)
