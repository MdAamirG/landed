"""decide() against the nine checks in docs/data-model.md, in their order."""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models import PodStatus
from app.rules import Facts, ReasonCode, decide
from app.schemas import (
    DateReading,
    PodReading,
    PresenceReading,
    QuantityReading,
    RemarksReading,
    TextReading,
)

DOCS = Path(__file__).resolve().parents[2] / "docs"

HIGH = 0.95

# 6 Nov 2026, 13:10 in India.
CAPTURED_AT = datetime(2026, 11, 6, 7, 40, tzinfo=UTC)


def facts(**overrides) -> Facts:
    values = {
        "lr_number": "48213",
        "qty_dispatched": Decimal("400"),
        "qty_unit": "cartons",
        "retakes_used": 0,
        "distance_km": 0.4,
        "captured_at": CAPTURED_AT,
    }
    return Facts(**(values | overrides))


def reading(**overrides) -> PodReading:
    """A reading that passes every check, so each case changes only what it's testing."""
    values = {
        "lr_number": TextReading(value="48213", confidence=HIGH),
        "consignee_stamp": PresenceReading(value="present", confidence=HIGH),
        "quantity_received": QuantityReading(number=400, unit="cartons", confidence=HIGH),
        "remarks": RemarksReading(text=None, kind="none", confidence=HIGH),
        "delivery_date": DateReading(value=date(2026, 11, 6), confidence=HIGH),
        "signature": PresenceReading(value="present", confidence=HIGH),
        "image_quality": "ok",
    }
    return PodReading(**(values | overrides))


NO_STAMP = {"consignee_stamp": PresenceReading(value="absent", confidence=HIGH)}
SHORT_REMARK = {"remarks": RemarksReading(text="Short by 6", kind="shortage", confidence=HIGH)}
WRONG_LR = {"lr_number": TextReading(value="99999", confidence=HIGH)}
SHORT_QTY = {"quantity_received": QuantityReading(number=394, unit="cartons", confidence=HIGH)}
UNSURE_LR = {"lr_number": TextReading(value="48213", confidence=0.5)}


def test_a_clean_reading_is_verified_with_no_reasons():
    decision = decide(reading(), facts())

    assert decision.status == PodStatus.VERIFIED
    assert decision.reason is None
    assert decision.reason_codes == ()


def test_check_1_an_ai_failure_goes_to_a_person():
    decision = decide(None, facts())

    assert decision.status == PodStatus.NEEDS_REVIEW
    assert decision.reason == "ai_unavailable"
    assert decision.reason_codes == ("ai_unavailable",)


@pytest.mark.parametrize(
    ("change", "code"),
    [
        pytest.param({"image_quality": "blurred"}, "photo_blurred", id="blurred"),
        pytest.param({"image_quality": "dark"}, "photo_dark", id="dark"),
        pytest.param(NO_STAMP, "stamp_missing", id="no stamp"),
        pytest.param(
            {"signature": PresenceReading(value="absent", confidence=HIGH)},
            "signature_missing",
            id="no signature",
        ),
        pytest.param(
            {"lr_number": TextReading(value=None, confidence=HIGH)}, "lr_missing", id="no LR"
        ),
        pytest.param(
            {"lr_number": TextReading(value="  ", confidence=HIGH)}, "lr_missing", id="blank LR"
        ),
        pytest.param(
            {"quantity_received": QuantityReading(number=None, unit=None, confidence=HIGH)},
            "quantity_missing",
            id="no quantity",
        ),
        pytest.param(
            {"quantity_received": QuantityReading(number=400, unit="  ", confidence=HIGH)},
            "quantity_missing",
            id="blank unit",
        ),
        pytest.param(
            {"delivery_date": DateReading(value=None, confidence=HIGH)},
            "date_missing",
            id="no date",
        ),
    ],
)
class TestCheck2FixableByTheDriver:
    @pytest.mark.parametrize("retakes_used", [0, 1])
    def test_asks_for_a_retake_while_retakes_remain(self, change, code, retakes_used):
        decision = decide(reading(**change), facts(retakes_used=retakes_used))

        assert decision.status == PodStatus.RETAKE_REQUESTED
        assert decision.reason == code
        assert decision.reason_codes == (code,)

    def test_goes_to_a_person_once_two_retakes_are_used(self, change, code):
        decision = decide(reading(**change), facts(retakes_used=2))

        assert decision.status == PodStatus.NEEDS_REVIEW
        assert decision.reason == "retake_cap_reached"
        assert decision.reason_codes == ("retake_cap_reached", code)


def test_check_3_a_different_lr_number_goes_to_a_person():
    decision = decide(reading(**WRONG_LR), facts())

    assert decision.status == PodStatus.NEEDS_REVIEW
    assert decision.reason == "lr_mismatch"


def test_check_3_ignores_case_and_surrounding_spaces():
    decision = decide(
        reading(lr_number=TextReading(value=" ab-48213 ", confidence=HIGH)),
        facts(lr_number="AB-48213"),
    )

    assert decision.status == PodStatus.VERIFIED


@pytest.mark.parametrize(
    ("distance_km", "status", "reason"),
    [
        pytest.param(2.01, PodStatus.NEEDS_REVIEW, "location_far", id="just over 2 km"),
        pytest.param(2.0, PodStatus.VERIFIED, None, id="exactly 2 km"),
        pytest.param(None, PodStatus.VERIFIED, None, id="location missing, not far"),
    ],
)
def test_check_4_location(distance_km, status, reason):
    decision = decide(reading(), facts(distance_km=distance_km))

    assert (decision.status, decision.reason) == (status, reason)


@pytest.mark.parametrize(
    ("paper_date", "captured_at", "status", "reason"),
    [
        pytest.param(
            date(2026, 11, 8), CAPTURED_AT, PodStatus.NEEDS_REVIEW, "date_mismatch", id="2 days on"
        ),
        pytest.param(
            date(2026, 11, 4), CAPTURED_AT, PodStatus.NEEDS_REVIEW, "date_mismatch", id="2 days ago"
        ),
        pytest.param(date(2026, 11, 5), CAPTURED_AT, PodStatus.VERIFIED, None, id="1 day ago"),
        pytest.param(date(2026, 11, 7), CAPTURED_AT, PodStatus.VERIFIED, None, id="1 day on"),
        # 19:00 UTC on 5 Nov is already 00:30 on 6 Nov in India.
        pytest.param(
            date(2026, 11, 7),
            datetime(2026, 11, 5, 19, 0, tzinfo=UTC),
            PodStatus.VERIFIED,
            None,
            id="passes only in India time",
        ),
        pytest.param(
            date(2026, 11, 4),
            datetime(2026, 11, 5, 19, 0, tzinfo=UTC),
            PodStatus.NEEDS_REVIEW,
            "date_mismatch",
            id="fails only in India time",
        ),
    ],
)
def test_check_5_date_on_the_paper(paper_date, captured_at, status, reason):
    change = {"delivery_date": DateReading(value=paper_date, confidence=HIGH)}

    decision = decide(reading(**change), facts(captured_at=captured_at))

    assert (decision.status, decision.reason) == (status, reason)


@pytest.mark.parametrize(
    ("kind", "code"),
    [
        ("shortage", "shortage_remark"),
        ("damage", "damage_remark"),
        ("other", "other_remark"),
    ],
)
def test_check_6_a_remark_at_full_confidence_still_goes_to_a_person(kind, code):
    remarks = RemarksReading(text="seal broken", kind=kind, confidence=1.0)

    decision = decide(reading(remarks=remarks), facts())

    assert decision.status == PodStatus.NEEDS_REVIEW
    assert decision.reason == code


@pytest.mark.parametrize(
    ("number", "unit", "status", "reason"),
    [
        pytest.param(394, "cartons", PodStatus.NEEDS_REVIEW, "qty_short", id="below dispatched"),
        pytest.param(401, "cartons", PodStatus.NEEDS_REVIEW, "qty_mismatch", id="above dispatched"),
        pytest.param(400, "bags", PodStatus.NEEDS_REVIEW, "qty_mismatch", id="another unit"),
        pytest.param(394, "bags", PodStatus.NEEDS_REVIEW, "qty_mismatch", id="unit beats short"),
        pytest.param(400, " Cartons ", PodStatus.VERIFIED, None, id="unit case and spaces"),
    ],
)
def test_check_7_quantity(number, unit, status, reason):
    quantity = QuantityReading(number=number, unit=unit, confidence=HIGH)

    decision = decide(reading(quantity_received=quantity), facts())

    assert (decision.status, decision.reason) == (status, reason)


def test_check_7_a_decimal_quantity_is_not_short_of_the_same_amount():
    # As binary floats, 23.9 sits just under the Decimal 23.900 from the database.
    quantity = QuantityReading(number=23.9, unit="tonnes", confidence=HIGH)

    decision = decide(
        reading(quantity_received=quantity),
        facts(qty_dispatched=Decimal("23.900"), qty_unit="tonnes"),
    )

    assert decision.status == PodStatus.VERIFIED


@pytest.mark.parametrize(
    "change",
    [
        pytest.param({"lr_number": TextReading(value="48213", confidence=0.79)}, id="LR"),
        pytest.param(
            {"consignee_stamp": PresenceReading(value="present", confidence=0.79)}, id="stamp"
        ),
        pytest.param(
            {"quantity_received": QuantityReading(number=400, unit="cartons", confidence=0.79)},
            id="quantity",
        ),
        pytest.param(
            {"remarks": RemarksReading(text=None, kind="none", confidence=0.79)}, id="remarks"
        ),
        pytest.param(
            {"delivery_date": DateReading(value=date(2026, 11, 6), confidence=0.79)}, id="date"
        ),
        pytest.param(
            {"signature": PresenceReading(value="present", confidence=0.79)}, id="signature"
        ),
    ],
)
def test_check_8_any_field_just_below_the_threshold_goes_to_a_person(change):
    decision = decide(reading(**change), facts())

    assert decision.status == PodStatus.NEEDS_REVIEW
    assert decision.reason == "low_confidence"
    assert decision.reason_codes == ("low_confidence",)


def test_check_8_exactly_at_the_threshold_passes():
    lr_number = TextReading(value="48213", confidence=0.80)

    assert decide(reading(lr_number=lr_number), facts()).status == PodStatus.VERIFIED


def test_fixable_checks_come_first_because_the_driver_is_still_at_the_gate():
    decision = decide(reading(**NO_STAMP, **SHORT_REMARK), facts())

    assert decision.status == PodStatus.RETAKE_REQUESTED
    assert decision.reason == "stamp_missing"
    assert decision.reason_codes == ("stamp_missing", "shortage_remark")


def test_the_first_match_sets_the_reason_and_every_match_is_kept():
    decision = decide(
        reading(**WRONG_LR, **SHORT_REMARK, **SHORT_QTY),
        facts(distance_km=5),
    )

    assert decision.status == PodStatus.NEEDS_REVIEW
    assert decision.reason == "lr_mismatch"
    assert decision.reason_codes == (
        "lr_mismatch",
        "location_far",
        "shortage_remark",
        "qty_short",
    )


def test_low_confidence_is_kept_alongside_other_reasons():
    decision = decide(reading(**UNSURE_LR, **SHORT_REMARK), facts())

    assert decision.reason == "shortage_remark"
    assert decision.reason_codes == ("shortage_remark", "low_confidence")


def test_at_the_retake_cap_every_other_problem_is_still_kept():
    decision = decide(reading(**NO_STAMP, **SHORT_REMARK), facts(retakes_used=2))

    assert decision.status == PodStatus.NEEDS_REVIEW
    assert decision.reason == "retake_cap_reached"
    assert decision.reason_codes == ("retake_cap_reached", "stamp_missing", "shortage_remark")


def test_a_missing_value_is_not_also_reported_as_a_mismatch():
    change = {
        "lr_number": TextReading(value=None, confidence=HIGH),
        "quantity_received": QuantityReading(number=None, unit=None, confidence=HIGH),
        "delivery_date": DateReading(value=None, confidence=HIGH),
    }

    decision = decide(reading(**change), facts())

    assert decision.reason_codes == ("lr_missing", "quantity_missing", "date_missing")


@pytest.mark.parametrize(
    "number",
    [float("nan"), float("inf"), -1],
    ids=["not a number", "infinite", "negative"],
)
def test_a_reply_with_an_impossible_quantity_does_not_fit_the_shape(number):
    # The AI reader treats a reply that doesn't fit as a failure, which is check 1.
    with pytest.raises(ValidationError):
        QuantityReading(number=number, unit="cartons", confidence=HIGH)


@pytest.mark.parametrize("confidence", [-0.1, 1.1, float("nan")])
def test_a_reply_with_an_impossible_confidence_does_not_fit_the_shape(confidence):
    with pytest.raises(ValidationError):
        TextReading(value="48213", confidence=confidence)


def test_every_reason_code_is_recorded_in_the_data_model():
    data_model = (DOCS / "data-model.md").read_text()

    assert [code for code in ReasonCode if f"`{code}`" not in data_model] == []
