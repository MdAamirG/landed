"""Renders the sample PODs from pods/scenarios.json.

Run with: python3 samples/render_pods.py

It writes one filled-in JPEG per scenario, plus print/lr-sheets.pdf: five A4 pages with the
consignee's part left blank, for the printed versions. It also renders pods/seeded-sheets.json,
the sheets for seeded trips a reviewer opens in Review, so each photo shows its trip's LR number.

Needs Chrome and macOS's sips, and no Python packages. It only runs when the samples change,
so a browser is a simpler way to lay out a form than adding an image library to the API.
"""

import json
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from string import Template

SAMPLES = Path(__file__).resolve().parent
PODS = SAMPLES / "pods"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

MAX_BYTES = 300_000  # The upload limit, from the brief.
JPEG_QUALITY = "72"

# A4 at Chrome's 96 CSS pixels to the inch, scaled up so small print stays readable.
PAGE_WIDTH, PAGE_HEIGHT = 794, 1123
SCALE = "1.5"

SHEET = Template((SAMPLES / "lr-sheet.html").read_text())
STYLE = (SAMPLES / "lr-sheet.css").read_text()


def india_date(iso_date: str) -> str:
    return date.fromisoformat(iso_date).strftime("%d/%m/%Y")


def sheet_html(scenario: dict, blank: bool) -> str:
    trip, reading = scenario["trip"], scenario["reading"]

    classes = []
    if blank:
        classes.append("print")
    if reading["consignee_stamp"] == "absent":
        classes.append("no-stamp")
    if reading["image_quality"] == "blurred" and not blank:
        classes.append("blurred")

    return SHEET.substitute(
        trip,
        id=scenario["id"],
        classes=" ".join(classes),
        lr_number=scenario["sheet_lr_number"],  # Differs from the trip's on the wrong-LR sheet.
        lr_date=india_date(trip["lr_date"]),
        consignee_upper=trip["consignee_name"].upper(),
        quantity_received=f"{reading['quantity_received']} {trip['qty_unit']}",
        delivery_date=india_date(reading["delivery_date"]),
        remarks=reading["remarks"] or "",  # Blank, not "nil": any remark text goes to a person.
    )


def write_page(path: Path, sheets: list[str]) -> Path:
    body = "\n".join(sheets)
    path.write_text(f'<!doctype html><meta charset="utf-8"><style>{STYLE}</style><body>{body}')
    return path


def run_chrome(page: Path, profile: Path, *options: str) -> None:
    subprocess.run(
        [
            CHROME,
            "--headless=new",
            "--hide-scrollbars",
            f"--user-data-dir={profile}",  # A throwaway profile, so this never touches yours.
            *options,
            page.as_uri(),
        ],
        check=True,
        capture_output=True,
    )


def render_image(scenario: dict, workdir: Path) -> None:
    page = write_page(workdir / f"{scenario['id']}.html", [sheet_html(scenario, blank=False)])
    png = workdir / f"{scenario['id']}.png"
    run_chrome(
        page,
        workdir / "profile",
        f"--window-size={PAGE_WIDTH},{PAGE_HEIGHT}",
        f"--force-device-scale-factor={SCALE}",
        f"--screenshot={png}",
    )

    jpeg = PODS / scenario["image"]
    subprocess.run(
        ["sips", "-s", "format", "jpeg", "-s", "formatOptions", JPEG_QUALITY, png, "--out", jpeg],
        check=True,
        capture_output=True,
    )

    size = jpeg.stat().st_size
    if size >= MAX_BYTES:
        raise SystemExit(f"{jpeg.name} is {size} bytes, over the {MAX_BYTES} limit.")
    print(f"{jpeg.name}: {size // 1024} KB")


def render_print_file(scenarios: list[dict], workdir: Path) -> None:
    sheets = [sheet_html(scenario, blank=True) for scenario in scenarios]
    page = write_page(workdir / "print.html", sheets)

    output = PODS / "print" / "lr-sheets.pdf"
    output.parent.mkdir(exist_ok=True)
    run_chrome(
        page,
        workdir / "profile",
        "--no-pdf-header-footer",
        f"--print-to-pdf={output}",
    )
    print(f"{output.name}: {output.stat().st_size // 1024} KB")


def main() -> None:
    scenarios = json.loads((PODS / "scenarios.json").read_text())
    seeded = json.loads((PODS / "seeded-sheets.json").read_text())
    with tempfile.TemporaryDirectory() as folder:
        workdir = Path(folder)
        for scenario in scenarios + seeded:
            render_image(scenario, workdir)
        render_print_file(scenarios, workdir)


if __name__ == "__main__":
    main()
