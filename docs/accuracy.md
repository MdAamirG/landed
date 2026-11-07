# Accuracy on the sample sheets

Built by `api/measure_accuracy.py` from 60 replies: 3 run(s) of 10 sheets in 2 sets, on `gemini-3.5-flash-lite`, with the threshold at 0.80. AI failures: 0.

**This is a first estimate.** The sheets are synthetic and nobody photographed printed paper. The photos come straight from `samples/photograph_pods.py`, without the phone's compression and strip. The model's confidence isn't calibrated.

## Accuracy per field

The blurred sheet isn't scored here, because the model is told not to guess at it.

### rendered

| Field | Right | Accuracy | Lowest confidence when right | Highest when wrong |
| --- | --- | --- | --- | --- |
| `lr_number` | 27 of 27 | 100.0% | 1.00 | none |
| `consignee_stamp` | 27 of 27 | 100.0% | 1.00 | none |
| `quantity_received` | 27 of 27 | 100.0% | 0.99 | none |
| `remarks` | 27 of 27 | 100.0% | 0.99 | none |
| `delivery_date` | 27 of 27 | 100.0% | 0.98 | none |
| `signature` | 27 of 27 | 100.0% | 1.00 | none |

### photos

| Field | Right | Accuracy | Lowest confidence when right | Highest when wrong |
| --- | --- | --- | --- | --- |
| `lr_number` | 27 of 27 | 100.0% | 1.00 | none |
| `consignee_stamp` | 27 of 27 | 100.0% | 1.00 | none |
| `quantity_received` | 27 of 27 | 100.0% | 0.98 | none |
| `remarks` | 27 of 27 | 100.0% | 0.98 | none |
| `delivery_date` | 27 of 27 | 100.0% | 0.95 | none |
| `signature` | 27 of 27 | 100.0% | 1.00 | none |

## What each threshold would do

Every field reading from the readable sheets, in both sets. A right reading stopped costs a person a look. A wrong reading passed is the one that matters, though other checks may still catch it.

| Threshold | Right readings stopped | Wrong readings passed |
| --- | --- | --- |
| 0.50 | 0 | 0 |
| 0.60 | 0 | 0 |
| 0.70 | 0 | 0 |
| 0.80 | 0 | 0 |
| 0.85 | 0 | 0 |
| 0.90 | 0 | 0 |
| 0.95 | 0 | 0 |

## Does each scenario land where it should

Status is what matters: it decides where the trip goes. Extra reasons are expected on a blurred sheet, because `decide()` lists every check that failed.

| Set | Scenario | Right status | Exact reasons too | What it did otherwise |
| --- | --- | --- | --- | --- |
| rendered | `clean` | 3 of 3 | 3 of 3 | none |
| rendered | `blurry` | 1 of 3 | 0 of 3 | needs_review |
| rendered | `no-stamp` | 3 of 3 | 3 of 3 | none |
| rendered | `short-6-cartons` | 3 of 3 | 3 of 3 | none |
| rendered | `wrong-lr` | 3 of 3 | 3 of 3 | none |
| photos | `clean` | 3 of 3 | 3 of 3 | none |
| photos | `blurry` | 3 of 3 | 0 of 3 | none |
| photos | `no-stamp` | 3 of 3 | 3 of 3 | none |
| photos | `short-6-cartons` | 3 of 3 | 3 of 3 | none |
| photos | `wrong-lr` | 3 of 3 | 3 of 3 | none |

## The blurred sheet

The model called it blurred in 4 of 6 replies. These are the only wrong readings in the measurement, so they're the only evidence about what the threshold catches. `None` means the model said it couldn't read that field.

| Threshold | Right readings stopped | Wrong readings passed |
| --- | --- | --- |
| 0.50 | 0 | 11 |
| 0.60 | 0 | 11 |
| 0.70 | 0 | 10 |
| 0.80 | 0 | 10 |
| 0.85 | 0 | 9 |
| 0.90 | 0 | 8 |
| 0.95 | 0 | 3 |

- rendered, run 1, `blurry`, `delivery_date`: read {'value': '2024-11-04'} at 0.90
- photos, run 1, `blurry`, `lr_number`: read {'value': '48392'} at 0.90
- photos, run 1, `blurry`, `quantity_received`: read {'number': 214.0, 'unit': 'Pallets'} at 0.85
- photos, run 1, `blurry`, `delivery_date`: read {'value': '2024-11-04'} at 0.90
- rendered, run 2, `blurry`, `delivery_date`: read {'value': '2024-11-04'} at 0.90
- photos, run 2, `blurry`, `quantity_received`: read {'number': 5.0, 'unit': 'bundles'} at 0.80
- photos, run 2, `blurry`, `delivery_date`: read {'value': None} at 0.95
- rendered, run 3, `blurry`, `delivery_date`: read {'value': '2024-11-04'} at 0.90
- photos, run 3, `blurry`, `lr_number`: read {'value': '48362'} at 0.95
- photos, run 3, `blurry`, `quantity_received`: read {'number': 219.0, 'unit': 'Pallets'} at 0.60
- photos, run 3, `blurry`, `delivery_date`: read {'value': None} at 0.95

## Every misread on a readable sheet

None.

## Time taken

Median 2.5 s, slowest 12.8 s, against the 20-second limit.
