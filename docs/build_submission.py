# /// script
# requires-python = ">=3.12"
# dependencies = ["markdown==3.8"]
# ///
"""Builds the submission ZIP: the TDD as a PDF, plus deployment.md.

Run with: uv run docs/build_submission.py

The brief wants the TDD as a PDF or Word file. docs/tdd.md stays the source, so the TDD can be read
and reviewed in the repo, and this prints it to PDF with Chrome, as samples/render_pods.py does for
the LR sheets. uv installs the one package it needs on the fly, so the API's requirements don't grow.
Output goes to submission/, which git ignores.
"""

import subprocess
import tempfile
import zipfile
from pathlib import Path

import markdown

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "submission"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"  # macOS only, like render_pods.py.

PDF_NAME = "Landed-TDD.pdf"
ZIP_NAME = "Landed-submission.zip"

# Print styles only. Fonts follow design/tokens.css, with system fallbacks if Google Fonts can't load.
STYLE = """
@import url("https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;600&family=Geist+Mono&family=Noto+Sans+Devanagari&display=swap");
@page { size: A4; margin: 18mm 16mm; }
body { font: 10pt/1.5 "Instrument Sans", "Noto Sans Devanagari", -apple-system, sans-serif; color: #1f1d1a; }
h1 { font-size: 20pt; margin: 0 0 8pt; }
h2 { font-size: 14pt; margin: 18pt 0 6pt; border-bottom: 1px solid #d9d4cc; padding-bottom: 3pt; }
h3 { font-size: 11pt; margin: 12pt 0 4pt; }
h1, h2, h3 { break-after: avoid; }
a { color: #c2543c; }
code, pre { font-family: "Geist Mono", ui-monospace, monospace; font-size: 8.5pt; }
pre { background: #f4f1ec; padding: 8pt; line-height: 1.3; break-inside: avoid; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0; font-size: 9pt; }
th, td { border: 1px solid #d9d4cc; padding: 3pt 5pt; text-align: left; vertical-align: top; }
th { background: #f4f1ec; }
tr { break-inside: avoid; }
li { margin: 2pt 0; }
"""


def tdd_html() -> str:
    body = markdown.markdown(
        (REPO / "docs" / "tdd.md").read_text(), extensions=["tables", "fenced_code"]
    )
    return f'<!doctype html><html lang="en"><meta charset="utf-8"><title>Landed TDD</title><style>{STYLE}</style>{body}</html>'


def print_pdf(html: str, output: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "tdd.html"
        page.write_text(html)
        subprocess.run(
            [
                CHROME,
                "--headless=new",
                "--no-pdf-header-footer",
                "--virtual-time-budget=5000",  # Gives the web fonts time to load before printing.
                f"--print-to-pdf={output}",
                page.as_uri(),
            ],
            check=True,
            capture_output=True,
        )


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    pdf = OUT / PDF_NAME
    print_pdf(tdd_html(), pdf)
    with zipfile.ZipFile(OUT / ZIP_NAME, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(pdf, PDF_NAME)
        archive.write(REPO / "deployment.md", "deployment.md")
    print(f"Wrote {pdf.relative_to(REPO)} and {(OUT / ZIP_NAME).relative_to(REPO)}")
