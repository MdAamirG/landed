"""The accuracy script's scoring. The measurement itself calls the real model and stays out of here."""

from dataclasses import asdict

import pytest

from app.ai import AiResult
from measure_accuracy import (
    field_results,
    load_sheets,
    normalised,
    outcome_of,
    report,
    threshold_rows,
    to_record,
)
from tests.test_sample_pods import perfect_reading

SHEETS = {sheet["id"]: sheet for sheet in load_sheets()}
SCENARIO_IDS = ["clean", "blurry", "no-stamp", "short-6-cartons", "wrong-lr"]


def changed(reading, field: str, **values):
    """A copy of the reading with one field changed."""
    return reading.model_copy(update={field: getattr(reading, field).model_copy(update=values)})


def test_every_sheet_can_be_scored():
    assert len(SHEETS) == 10


@pytest.mark.parametrize("sheet_id", SCENARIO_IDS)
def test_a_perfect_reading_scores_right_on_all_six_fields(sheet_id):
    sheet = SHEETS[sheet_id]

    results = field_results(perfect_reading(sheet), sheet)

    assert len(results) == 6
    assert all(right for right, _ in results.values())


@pytest.mark.parametrize(
    ("field", "values"),
    [
        ("lr_number", {"value": "48399"}),
        ("consignee_stamp", {"value": "absent"}),
        ("quantity_received", {"number": 799}),
        ("quantity_received", {"unit": "cartons"}),
        ("remarks", {"kind": "damage"}),
        ("remarks", {"text": "seal broken"}),
        ("delivery_date", {"value": None}),
        ("signature", {"value": "absent"}),
    ],
)
def test_a_misread_scores_wrong_on_that_field_alone(field, values):
    sheet = SHEETS["clean"]

    results = field_results(changed(perfect_reading(sheet), field, **values), sheet)

    assert [name for name, (right, _) in results.items() if not right] == [field]


def test_the_wrong_lr_sheet_is_scored_against_what_is_on_the_paper():
    sheet = SHEETS["wrong-lr"]

    results = field_results(perfect_reading(sheet), sheet)

    assert results["lr_number"][0] is True  # 48350 is printed, so reading it is right.


def test_punctuation_and_case_are_not_misreads():
    assert normalised("Short by 6 Cartons.") == normalised("short by 6 cartons")


def test_an_empty_remark_matches_no_remark():
    assert normalised("") == normalised(None)


@pytest.mark.parametrize("sheet_id", SCENARIO_IDS)
def test_the_real_rule_gives_each_scenarios_expected_outcome(sheet_id):
    sheet = SHEETS[sheet_id]

    assert outcome_of(perfect_reading(sheet), sheet) == (
        sheet["expected_status"],
        sheet["expected_reasons"],
    )


def test_a_failed_call_goes_to_review_and_has_no_fields():
    record = to_record("photos", SHEETS["clean"], 1, AiResult(None, {}, "fake", None))

    assert (record.outcome, record.reasons) == ("needs_review", ["ai_unavailable"])
    assert record.fields == {}


def test_a_threshold_counts_both_ways_of_being_wrong():
    records = [
        {
            "fields": {
                "lr_number": {"right": True, "confidence": 0.75},
                "signature": {"right": False, "confidence": 0.85},
            }
        }
    ]

    by_threshold = {row[0]: row[1:] for row in threshold_rows(records)}

    assert by_threshold[0.80] == (1, 1)
    assert by_threshold[0.70] == (0, 1)
    assert by_threshold[0.90] == (1, 0)


def test_the_report_handles_a_failed_call_and_says_it_is_an_estimate():
    sheet = SHEETS["clean"]
    good = AiResult(perfect_reading(sheet), {}, "fake", 2000)
    records = [
        asdict(to_record("photos", sheet, 1, good)),
        asdict(to_record("photos", sheet, 2, AiResult(None, {}, "fake", None))),
    ]

    text = report(records, "fake", 2)

    assert "first estimate" in text
    assert "AI failures: 1" in text
    assert "`clean` | 1 of 2 | 1 of 2 | needs_review |" in text


def test_the_report_counts_a_right_status_with_extra_reasons_as_right_status_only():
    sheet = SHEETS["blurry"]
    reading = changed(perfect_reading(sheet), "lr_number", value="48392", confidence=0.9)
    records = [asdict(to_record("photos", sheet, 1, AiResult(reading, {}, "fake", 2000)))]

    text = report(records, "fake", 1)

    assert "`blurry` | 1 of 1 | 0 of 1 | none |" in text
    assert "read {'value': '48392'} at 0.90" in text
