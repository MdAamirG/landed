# Landed

**Bill the POD from the gate.** A truck driver photographs the signed lorry receipt at the consignee's gate, an AI checks it while the driver is still there, and billing exports verified trips to Tally with the photo attached.

**Live app:** <https://landed-lovat.vercel.app> · **Demo logins and setup:** [deployment.md](deployment.md) · **Design document:** [docs/tdd.md](docs/tdd.md)

[![Landed product demo: click to watch the full video](docs/media/landed-demo.gif)](docs/media/landed-demo.mp4)

*The GIF is a preview. Click it for the full 2-minute demo with sound ([MP4](docs/media/landed-demo.mp4)).*

## The problem

Company A runs a full-truckload fleet out of Chhatrapati Sambhajinagar. It can't bill a trip until the signed lorry receipt comes back, often 10 to 20 days after delivery, and clients reject invoices without one. POD-to-invoice takes 18 days, and 1.5% of PODs are lost or disputed. The brief puts the cost at **₹1.02 crore a year**.

## What it does

| Feature | What happens |
| --- | --- |
| **Daily trip import** | The billing executive uploads the day's trip file. Each row is checked (missing e-way bill, duplicate LR) before anything is imported, and every driver gets an SMS link. |
| **Driver link, no app to install** | One big button, Hindi, Marathi and English voice prompts, no forms. The phone checks the photo is sharp and bright, shrinks it under 300 KB and prints the trip, time and GPS on a strip below it. |
| **Works with no signal** | The photo waits on the phone and sends itself when the network is back. The app reopens offline. |
| **AI check at the gate** | Gemini reads six fields: LR number, consignee stamp, quantity, remarks, date and signature. A fixed rule decides: a fixable problem gets a retake (two at most), anything that needs judgement goes to a person. |
| **Review desk** | The photo beside what the AI read, every reason listed, every field editable. Approve, ask for a retake, mark disputed or pull back. Consignee contacts are masked, and every reveal is logged. |
| **Billing and Tally** | Verified trips by client and billing cycle. Export makes one draft voucher per client in Tally XML, plus a ZIP of the POD photos. Nothing is ever sent to a client automatically. |
| **Missing PODs dashboard** | Trips delivered with no POD, the share in within 24 hours, POD-to-invoice days by branch, and a one-click resend of the SMS link. |
| **Client POD link** | A signed, read-only link for one client that lasts 7 days, with names masked and no phone numbers. |
| **Two office roles** | The billing executive runs the whole flow. The operations head sees what's missing and can resend links, and is refused approve and export. |

## How the AI check works

The model suggests; a fixed, pure function decides. `decide()` in [`api/app/rules.py`](api/app/rules.py) runs nine checks in order. The first match sets the status, and every match is kept as a reason for the reviewer.

1. The AI failed, timed out or broke the schema: **a person** (the photo is kept)
2. Blurred, dark, or a field not found: **retake**, or a person after two retakes
3. The LR number doesn't match the trip: **a person**
4. Taken more than 2 km from the consignee: **a person**
5. The paper's date is more than a day from the photo's: **a person**
6. Any remark, at any confidence: **a person**
7. Quantity short, over or in another unit: **a person**
8. Any field below 0.80 confidence: **a person**
9. Otherwise: **verified**

The reply is constrained by a JSON schema generated from a Pydantic model and validated again on arrival. On the readable sample sheets, all 324 field readings were right, with a median of 2.5 s per check ([docs/accuracy.md](docs/accuracy.md)). These are synthetic sheets, not real creased paper.

## Architecture

```
 Driver's phone                    Office browser
 (driver link, PWA)                (sign-in, Review, Billing, Missing PODs)
        \                                /
         \        one React app         /
          +------ on Vercel -----------+
                     |  /api/* rewritten to Render (same origin)
                     v
             FastAPI on Render (Singapore)
             status.move_trip()  rules.decide()  ai.read_pod()
                     |                        |
                     v                        v
         Postgres on Neon (ap-southeast-1)   Gemini vision
         12 tables, photos as bytea          (structured output)
```

- **Seven trip statuses**, and one function, `move_trip()`, is the only code that changes them. It refuses any move outside the state machine and writes the audit event in the same transaction.
- **The upload returns at once** and the AI check runs in the background; the phone polls every 2 seconds.
- **Security:** roles checked on every office route, a hashed token per driver link, Pydantic on every input, masked personal data (DPDP Act 2023) and an append-only audit log.

The full reasoning behind each choice is in [docs/tdd.md](docs/tdd.md).

## Stack

- **API:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, pytest
- **Database:** Postgres on Neon
- **AI:** Gemini vision through the `google-genai` SDK, with structured output
- **Web:** React, Vite and TypeScript; one app with the driver PWA and the office screens; plain CSS, no UI kit
- **Hosting:** Render for the API, Vercel for the web app

## Run it locally

You need Python 3.12, [uv](https://docs.astral.sh/uv/), Node 22 or newer, a Gemini API key and two Postgres databases (one for the app, one for the tests). The full steps are in [deployment.md](deployment.md); in short:

```bash
cp .env.example .env
```

```bash
cd api && uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements-dev.txt
```

```bash
cd api && .venv/bin/alembic upgrade head && .venv/bin/python seed.py
```

```bash
cd api && .venv/bin/uvicorn app.main:app --reload
```

```bash
cd web && npm ci && npm run dev
```

Then open <http://localhost:5173>. The sign-in screen has a button per demo role, and `/demo` opens the driver side with five scenarios.

## Tests

702 API tests run against a real Postgres test branch, with only the AI faked, and 28 web tests cover the offline photo queue and the voice prompts.

```bash
cd api && .venv/bin/pytest
```

```bash
cd web && npm run typecheck && npm test
```

## Limits

Honest notes, in full in [docs/tdd.md](docs/tdd.md#10-limits):

- The AI accuracy comes from synthetic sheets, not real photographed paper.
- The Tally XML hasn't been imported into a real Tally.
- The voice prompts still need a native Hindi and Marathi speaker's check.
- SMS is mocked, and the demo runs on sample data with no real personal data.

---

Built by Mohamed Aamir as a take-home build, November 2026. Demo video music: Sascha Ende, ende.app (CC BY 4.0).
