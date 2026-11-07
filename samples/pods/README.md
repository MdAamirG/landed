# Sample PODs

Five lorry receipts, one per demo scenario. Every name and number is a sample.

`scenarios.json` is the one record of them. For each scenario it holds the demo trip, the LR number on the sheet, what the sheet says and the result the decision rule should give. A test checks each scenario against `decide()`.

| Scenario | Trip's LR | Sheet's LR | Expected result |
| --- | --- | --- | --- |
| `clean` | 48301 | 48301 | Verified |
| `blurry` | 48302 | 48302 | Retake requested, `photo_blurred` |
| `no-stamp` | 48303 | 48303 | Retake requested, `stamp_missing` |
| `short-6-cartons` | 48304 | 48304 | Needs review, `shortage_remark` and `qty_short` |
| `wrong-lr` | 48305 | 48350 | Needs review, `lr_mismatch` |

The rendered sheets are dated 6 Nov 2026. Check 5 compares that date with the photo's capture date, so a rendered sheet needs a capture date within a day of it.

## Seeded trips' sheets

`seeded-sheets.json` holds five more sheets, in the same shape, for the seeded trips a reviewer opens in Review: the brief's three and two more. Each shows that trip's own LR number, so the photo agrees with the fields beside it. The history seed's other trips share `photos/clean.jpg`, so their LR numbers don't match it; the seed exists for the figures, not for reading those sheets.

## Printing and photographing

`print/lr-sheets.pdf` has five A4 pages, in the order of the table, with the consignee's part left blank. Print at 100%, then fill in each page. Use the date you take the photo as the date of delivery.

| Page | Quantity received | Remarks | Signature | Stamp | Photo |
| --- | --- | --- | --- | --- | --- |
| 1 `clean` | 800 bags | Leave blank | Yes | Yes | Sharp |
| 2 `blurry` | 24 tonnes | Leave blank | Yes | Yes | Out of focus or moving |
| 3 `no-stamp` | 24 tonnes | Leave blank | Yes | No | Sharp |
| 4 `short-6-cartons` | 394 cartons | Short by 6 cartons | Yes | Yes | Sharp |
| 5 `wrong-lr` | 800 bags | Leave blank | Yes | Yes | Sharp |

Leave the remarks empty on the clean sheets. Writing "nil" sends the POD to a person, because any remark text does.

Save the photos as `photos/<scenario>.jpg`, for example `photos/no-stamp.jpg`.

## Phone-style photos

`photos/` holds one phone-style photo per scenario, made by `samples/photograph_pods.py` from the rendered sheets: the sheet on a desk at a slight angle, with uneven light, a shadow, camera noise and JPEG compression. The `blurry` one also gets camera shake. Each is under 300 KB, and a fixed seed per scenario makes them the same on every run.

They are synthetic, not photographs of printed paper. Accuracy measured on them is a first estimate, and the TDD labels it that way. Photographing the printed sheets (above) would replace them with a stronger test.

```bash
pip install pillow numpy
python3 samples/photograph_pods.py
```

## Measuring accuracy

`api/measure_accuracy.py` runs the real model over both sets and saves every reply to `accuracy-raw.json`. `docs/accuracy.md` is the report built from it. On a blurred sheet `decide()` lists every failed check, so `expected_reasons` is the first reason and more can follow it. The status is what has to match.

## Rendering again

After changing `scenarios.json` or the template (`samples/lr-sheet.html` and `samples/lr-sheet.css`):

```bash
python3 samples/render_pods.py
```

It needs Chrome and macOS's `sips`, and no Python packages.
