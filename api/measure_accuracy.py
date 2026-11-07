"""Measures the real Gemini check on the sample sheets, per field. It's a measurement, not a test,
so it stays out of pytest. It makes real paid calls and never touches the database.

Run with: cd api && .venv/bin/python measure_accuracy.py --runs 3

Each run reads every sheet in both sets: "rendered" (clean images straight from the template) and
"photos" (the synthetic phone-style ones). The model isn't deterministic, so more runs give a truer
picture. Every reply goes to samples/pods/accuracy-raw.json, and docs/accuracy.md is built from that
file, so --report-only can redo the report without spending anything.
"""

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from statistics import median
from time import sleep

from app import ai
from app.config import settings
from app.intake import image_type
from app.rules import INDIA, MIN_CONFIDENCE, Facts, decide
from app.schemas import PodReading

REPO_ROOT = Path(__file__).resolve().parents[1]
PODS = REPO_ROOT / "samples" / "pods"
RAW_FILE = PODS / "accuracy-raw.json"
REPORT_FILE = REPO_ROOT / "docs" / "accuracy.md"

SETS = {"rendered": PODS, "photos": PODS / "photos"}
FIELDS = (
    "lr_number",
    "consignee_stamp",
    "quantity_received",
    "remarks",
    "delivery_date",
    "signature",
)
THRESHOLDS = (0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.95)
PAUSE_SECONDS = 4  # Between calls, to stay under the free tier's requests-per-minute limit.


def normalised(text: str | None) -> str:
    """For comparing words: "Short by 6 cartons." and "short by 6 cartons" are the same reading."""
    return re.sub(r"[^a-z0-9]+", " ", (text or "").casefold()).strip()


def field_results(reading: PodReading, sheet: dict) -> dict[str, tuple[bool, float]]:
    """For each field: whether the reading matches the sheet, and the model's confidence."""
    expected = sheet["reading"]
    quantity = reading.quantity_received
    remarks = reading.remarks
    delivery = reading.delivery_date.value
    return {
        "lr_number": (
            normalised(reading.lr_number.value) == normalised(sheet["sheet_lr_number"]),
            reading.lr_number.confidence,
        ),
        "consignee_stamp": (
            reading.consignee_stamp.value == expected["consignee_stamp"],
            reading.consignee_stamp.confidence,
        ),
        "quantity_received": (
            quantity.number == expected["quantity_received"]
            and normalised(quantity.unit) == normalised(sheet["trip"]["qty_unit"]),
            quantity.confidence,
        ),
        "remarks": (
            remarks.kind == expected["remarks_kind"]
            and normalised(remarks.text) == normalised(expected["remarks"]),
            remarks.confidence,
        ),
        "delivery_date": (
            delivery is not None and delivery.isoformat() == expected["delivery_date"],
            reading.delivery_date.confidence,
        ),
        "signature": (
            reading.signature.value == expected["signature"],
            reading.signature.confidence,
        ),
    }


def outcome_of(reading: PodReading | None, sheet: dict) -> tuple[str, list[str]]:
    """What the real decision rule makes of this reading, on the sheet's own date with no GPS."""
    trip = sheet["trip"]
    delivered = date.fromisoformat(sheet["reading"]["delivery_date"])
    decision = decide(
        reading,
        Facts(
            lr_number=trip["lr_number"],
            qty_dispatched=Decimal(str(trip["qty_dispatched"])),
            qty_unit=trip["qty_unit"],
            retakes_used=0,
            distance_km=None,
            captured_at=datetime.combine(delivered, time(12), tzinfo=INDIA),
        ),
    )
    return decision.status.value, [code.value for code in decision.reason_codes]


@dataclass(frozen=True)
class Record:
    """One reply to one sheet. fields is empty when the AI failed."""

    set: str
    sheet: str
    run: int
    latency_ms: int | None
    image_quality: str | None
    fields: dict[str, dict]  # Field name to {"right": bool, "confidence": float, "read": ...}.
    outcome: str
    reasons: list[str]
    expected_outcome: str | None  # Only the five scenarios state one.
    expected_reasons: list[str] | None


def to_record(set_name: str, sheet: dict, run: int, result: ai.AiResult) -> Record:
    reading = result.reading
    outcome, reasons = outcome_of(reading, sheet)
    fields = {}
    if reading is not None:
        for field, (right, confidence) in field_results(reading, sheet).items():
            read = reading.model_dump(mode="json")[field]
            read.pop("confidence")
            fields[field] = {"right": right, "confidence": confidence, "read": read}
    return Record(
        set=set_name,
        sheet=sheet["id"],
        run=run,
        latency_ms=result.latency_ms,
        image_quality=reading.image_quality if reading else None,
        fields=fields,
        outcome=outcome,
        reasons=reasons,
        expected_outcome=sheet.get("expected_status"),
        expected_reasons=sheet.get("expected_reasons"),
    )


def load_sheets() -> list[dict]:
    return [
        *json.loads((PODS / "scenarios.json").read_text()),
        *json.loads((PODS / "seeded-sheets.json").read_text()),
    ]


def measure(runs: int) -> list[Record]:
    sheets = load_sheets()
    records = []
    for run in range(1, runs + 1):
        for set_name, folder in SETS.items():
            for sheet in sheets:
                image = (folder / sheet["image"]).read_bytes()
                result = ai.read_pod(image, image_type(image))
                record = to_record(set_name, sheet, run, result)
                records.append(record)
                print(f"run {run} {set_name:8} {sheet['id']:16} {record.outcome} {record.reasons}")
                sleep(PAUSE_SECONDS)
    return records


def readable(records: list[dict], sheets: dict[str, dict]) -> list[dict]:
    """Records whose sheet can be read. A blurred sheet is judged only on its outcome: "never guess"
    means the model should say it can't read one, and that mustn't count as a misread.
    """
    return [row for row in records if sheets[row["sheet"]]["reading"]["image_quality"] == "ok"]


def percent(part: int, whole: int) -> str:
    return f"{100 * part / whole:.1f}%" if whole else "n/a"


def field_rows(records: list[dict]) -> list[tuple[str, int, int, float | None, float | None]]:
    """(field, right, total, lowest confidence when right, highest confidence when wrong)."""
    rows = []
    for field in FIELDS:
        found = [row["fields"][field] for row in records if row["fields"]]
        right = [item["confidence"] for item in found if item["right"]]
        wrong = [item["confidence"] for item in found if not item["right"]]
        rows.append(
            (field, len(right), len(found), min(right, default=None), max(wrong, default=None))
        )
    return rows


def threshold_rows(records: list[dict]) -> list[tuple[float, int, int]]:
    """For each threshold: right readings it would stop, and wrong readings it would let through."""
    items = [item for row in records for item in row["fields"].values()]
    rows = []
    for threshold in THRESHOLDS:
        stopped = sum(item["right"] and item["confidence"] < threshold for item in items)
        passed = sum(not item["right"] and item["confidence"] >= threshold for item in items)
        rows.append((threshold, stopped, passed))
    return rows


def shown(value: float | None) -> str:
    return "none" if value is None else f"{value:.2f}"


def misreads(records: list[dict]) -> list[str]:
    """One line per wrong reading, keeping repeats: how often a misread happens is the point."""
    return [
        f"- {row['set']}, run {row['run']}, `{row['sheet']}`, `{field}`: read {item['read']} at "
        f"{item['confidence']:.2f}"
        for row in records
        for field, item in row["fields"].items()
        if not item["right"]
    ]


def report(records: list[dict], model: str, runs: int) -> str:
    sheets = {sheet["id"]: sheet for sheet in load_sheets()}
    failed = [row for row in records if not row["fields"]]
    lines = [
        "# Accuracy on the sample sheets",
        "",
        f"Built by `api/measure_accuracy.py` from {len(records)} replies: {runs} run(s) of "
        f"{len(sheets)} sheets in {len(SETS)} sets, on `{model}`, with the threshold at "
        f"{MIN_CONFIDENCE:.2f}. AI failures: {len(failed)}.",
        "",
        "**This is a first estimate.** The sheets are synthetic and nobody photographed printed "
        "paper. The photos come straight from `samples/photograph_pods.py`, without the phone's "
        "compression and strip. The model's confidence isn't calibrated.",
        "",
        "## Accuracy per field",
        "",
        "The blurred sheet isn't scored here, because the model is told not to guess at it.",
        "",
    ]
    for set_name in SETS:
        rows = readable([row for row in records if row["set"] == set_name], sheets)
        lines += [
            f"### {set_name}",
            "",
            "| Field | Right | Accuracy | Lowest confidence when right | Highest when wrong |",
            "| --- | --- | --- | --- | --- |",
        ]
        for field, right, total, lowest, highest in field_rows(rows):
            lines.append(
                f"| `{field}` | {right} of {total} | {percent(right, total)} | {shown(lowest)} "
                f"| {shown(highest)} |"
            )
        lines.append("")

    lines += [
        "## What each threshold would do",
        "",
        "Every field reading from the readable sheets, in both sets. A right reading stopped "
        "costs a person a look. A wrong reading passed is the one that matters, though other "
        "checks may still catch it.",
        "",
        "| Threshold | Right readings stopped | Wrong readings passed |",
        "| --- | --- | --- |",
    ]
    for threshold, stopped, passed in threshold_rows(readable(records, sheets)):
        lines.append(f"| {threshold:.2f} | {stopped} | {passed} |")

    scored = [row for row in records if row["expected_outcome"]]
    lines += [
        "",
        "## Does each scenario land where it should",
        "",
        "Status is what matters: it decides where the trip goes. Extra reasons are expected on a "
        "blurred sheet, because `decide()` lists every check that failed.",
        "",
        "| Set | Scenario | Right status | Exact reasons too | What it did otherwise |",
        "| --- | --- | --- | --- | --- |",
    ]
    for set_name in SETS:
        for sheet_id in dict.fromkeys(row["sheet"] for row in scored):
            rows = [row for row in scored if (row["set"], row["sheet"]) == (set_name, sheet_id)]
            right = [row for row in rows if row["outcome"] == row["expected_outcome"]]
            exact = [row for row in right if row["reasons"] == row["expected_reasons"]]
            others = sorted({row["outcome"] for row in rows if row not in right})
            lines.append(
                f"| {set_name} | `{sheet_id}` | {len(right)} of {len(rows)} "
                f"| {len(exact)} of {len(rows)} | {', '.join(others) or 'none'} |"
            )

    unreadable = [row for row in records if row not in readable(records, sheets)]
    flagged = sum(row["image_quality"] == "blurred" for row in unreadable)
    lines += [
        "",
        "## The blurred sheet",
        "",
        f"The model called it blurred in {flagged} of {len(unreadable)} replies. These are the only "
        "wrong readings in the measurement, so they're the only evidence about what the threshold "
        "catches. `None` means the model said it couldn't read that field.",
        "",
        "| Threshold | Right readings stopped | Wrong readings passed |",
        "| --- | --- | --- |",
    ]
    for threshold, stopped, passed in threshold_rows(unreadable):
        lines.append(f"| {threshold:.2f} | {stopped} | {passed} |")
    lines += ["", *misreads(unreadable)]

    latencies = [row["latency_ms"] for row in records if row["latency_ms"] is not None]
    lines += [
        "",
        "## Every misread on a readable sheet",
        "",
        *(misreads(readable(records, sheets)) or ["None."]),
        "",
        "## Time taken",
        "",
        f"Median {median(latencies) / 1000:.1f} s, slowest {max(latencies) / 1000:.1f} s, "
        f"against the 20-second limit.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--report-only", action="store_true", help="Rebuild from the saved replies")
    options = parser.parse_args()

    if options.report_only:
        saved = json.loads(RAW_FILE.read_text())
    else:
        records = [asdict(record) for record in measure(options.runs)]
        saved = {"model": settings.gemini_model, "runs": options.runs, "records": records}
        RAW_FILE.write_text(json.dumps(saved, indent=1) + "\n")

    text = report(saved["records"], saved["model"], saved["runs"])
    REPORT_FILE.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
