# Landed: Technical Design Document

**GitHub:** <https://github.com/MdAamirG/landed>

**Live app:** <https://landed-lovat.vercel.app> (demo logins are in `deployment.md`; both use the password `landed-demo`)

Mohamed Aamir, take-home build for brief 1: road transport fleet POD capture and billing. Written 8 November 2026.

## 1. What this is

Company A, a full-truckload transporter in Chhatrapati Sambhajinagar, can't bill a trip until the signed lorry receipt comes back, often 10 to 20 days after delivery. POD-to-invoice takes 18 days, and 1.5% of PODs are lost or disputed. The brief puts the cost at ₹1.02 crore a year.

Landed moves the proof to the consignee's gate. The driver opens a link from an SMS, presses one big button and photographs the signed receipt. The phone checks the photo, shrinks it under 300 KB and prints GPS and time on a strip below it. If there's no signal, it keeps the photo and sends it later. While the driver is still at the gate, a vision model reads six fields, and a fixed rule decides what happens next. If the driver can fix the problem, they're asked for a retake, at most twice. Anything that needs judgement goes to a billing executive, who can correct any field. Verified trips export to Tally as draft vouchers with a ZIP of the POD photos, and a dashboard shows which trips still have no POD.

The brief's core build is the slice that must work end to end. All of it is built and deployed:

| Core build item | Where it is |
| --- | --- |
| Driver POD capture, with GPS and time | Driver link: one button, phone check, compression, printed strip |
| Offline capture with compressed upload (the brief's hard part) | One photo per trip kept in IndexedDB, sent on reconnect, on app open and every 30 seconds |
| AI check with retake prompt | Gemini reads the photo in the background; `decide()` sets the status; retakes cap at two |
| Review queue | Photo beside the editable fields, approve, retake, dispute, pull back, logged contact reveal |
| Billing queue with export | Verified trips by client and cycle, Tally XML export, POD photo ZIP |
| Missing-POD dashboard | Trips with no POD, the three target figures, POD-to-invoice days by branch, resend link |
| Roles: driver and billing executive | Driver links per trip; email and password sign-in for the office; operations head added as depth |

Beyond the core, drivers hear spoken prompts in Hindi, Marathi or English, which the brief's constraints ask for (section 6), and a billing executive can import the daily trip file (section 4).

## 2. Architecture and why

```
 Driver's phone                    Office browser
 (driver link, PWA)                (sign-in, Review, Billing, Missing PODs)
        \                                /
         \        one React app         /
          +------ on Vercel -----------+
                     |  /api/* rewritten to Render (same origin, so the
                     |  sign-in cookie is first-party and CORS isn't needed)
                     v
             FastAPI on Render (Singapore)
             routers -> intake, review, billing, dashboard
             status.move_trip()  rules.decide()  ai.read_pod()
                     |                        |
                     v                        v
         Postgres on Neon (ap-southeast-1)   Gemini vision
         12 tables, photos as bytea          (structured output)
```

| Choice | Why |
| --- | --- |
| **A web link, not an installed app** | The brief says hired drivers won't install an app. A link in an SMS works for own and hired drivers alike, so one path covers the "SMS upload link" must-have and the driver app. The driver area is a PWA, so it reopens with no signal after the first visit. |
| **One React app with two areas** | Driver screens and office screens share the API client, the design tokens and one deploy. Splitting them would double the build setup for no gain at this size. |
| **FastAPI, Pydantic v2, SQLAlchemy 2** | Pydantic validates every input and also defines the schema Gemini must return, so the same model checks requests and AI replies. Sync SQLAlchemy keeps the code plain; the load is a few uploads a minute. |
| **Postgres on Neon** | The data is relational: trips, attempts, fields and an audit log. Postgres gives real unique constraints, which upload idempotency depends on, plus `jsonb` for AI replies. Neon has a free tier and cheap branches, so the tests get their own database. |
| **Render in Singapore, next to Neon** | Every request makes several queries. Putting the API in the same region as the database keeps each one a few milliseconds. |
| **Vercel rewrite from `/api/*` to Render** | The browser only talks to one origin. The session cookie stays first-party, which mobile browsers increasingly require, and CORS is never needed. |
| **AI check as a background task, phone polls every 2 seconds** | The upload returns as soon as the photo is safely stored, so a weak network can't lose a check that's already running. Polling is simpler than websockets and survives a dropped connection. |
| **Stuck checks swept on read** | Render's free tier has no reliable scheduler. Each driver poll and office page load sweeps for attempts stuck in checking over 60 seconds and sends them to a person. A restart can't strand a trip. |
| **Photos as `bytea` in Postgres** | Each photo is under 300 KB, and the demo holds about 35 MB. One store keeps backup and access control simple. `image_key` is already a column, so moving to object storage later is a small change. |
| **One function moves a trip's status** | `move_trip()` in `status.py` is the only code that writes `pod_status`. It refuses any move outside the state machine and writes the audit event in the same transaction, so the rules can't be bypassed by a new route. |

The API is split by job, so each rule has one home:

| Module | Job |
| --- | --- |
| `rules.py` | `decide()`: the AI decision rule. Pure, no I/O |
| `status.py` | `move_trip()`: the state machine and its audit event |
| `ai.py` | The Gemini call, the time limit, schema validation. Never raises |
| `intake.py` | Stores an attempt (idempotent, size and type checks, rate limit, late photos, wrong clock), then the background check |
| `review.py` | Field edits, approve, retake, dispute, pull back, reveal, each with its audit event |
| `masking.py` | How names and phones appear in every response |
| `billing.py`, `tally.py` | Cycles, the billing queue, the export, the XML and the POD ZIP |
| `dashboard.py` | The missing-POD list, the three figures, resend |
| `driver_links.py`, `auth.py` | Driver tokens; office passwords, the session cookie and `require_role()` |
| `client_links.py` | The signed 7-day client POD link and the PODs it shows |
| `demo.py` | The five demo scenarios |

## 3. Data model

Twelve tables in Postgres. `trips` is the centre: a trip has up to three checked photo attempts, each attempt has six field readings, and every change lands in `audit_events`.

| Table | What it holds |
| --- | --- |
| `trips` | Trip code, client, branch, vehicle, driver, route, LR and e-way bill numbers, quantity dispatched, freight in paise, consignee (masked), consignee location, expected delivery, `pod_status`, `status_reason`, `retakes_used`, verified by and when, export batch and voucher, `is_demo`, `version` |
| `pod_attempts` | One photo: its UUID from the phone, attempt number, the image, size, hash, when it was taken and received, GPS, distance from the consignee, the phone check result, the AI reply, latency, outcome and every reason code |
| `pod_fields` | One row per field per attempt: `ai_value`, `ai_confidence`, `final_value`, who edited it and when |
| `driver_links` | A keyed hash of each driver token, its expiry and revocation |
| `users` | Office staff, with an argon2 password hash and a role |
| `clients`, `branches`, `vehicles`, `drivers` | Reference data. Vehicles are own or hired; drivers have a language |
| `import_batches` | One per daily trip file: who uploaded it, the counts, and each rejected row's problems |
| `export_batches` | One per Tally export: cycle, count, total and the stored XML |
| `audit_events` | Append-only: every status change, field edit, reveal, export, retake request and mock SMS |

Decisions that shape it:

- **Trip and photo are separate.** Each attempt keeps its own AI reading, so the reviewer sees what changed between tries.
- **Every AI field is stored twice.** `ai_value` is what the model read, `final_value` is what billing uses. A correction never loses the original reading, and the edit is in the audit log.
- **The phone makes the attempt ID.** It's a UUID created at capture. An offline photo retried five times is stored once, because the ID is the primary key.
- **Money in paise as integers, times in UTC.** Screens show rupees and India time. No float ever touches freight.
- **`version` on trips.** Two executives saving the same trip can't overwrite each other: the second gets a 409 and the screen reloads.
- **Delivery time is when the photo is taken at the gate**, so the 24-hour target measures upload delay directly.

### Trip statuses

A trip has one of seven statuses. Only `verified` trips reach billing, and `invoiced` means a draft voucher was exported. Landed never issues an invoice itself.

| From | To | Who | When |
| --- | --- | --- | --- |
| `awaiting_pod` | `checking` | System | A photo arrives |
| `checking` | `verified` | System | Passes all nine checks |
| `checking` | `retake_requested` | System | The driver can fix it, under the cap |
| `checking` | `needs_review` | System | A person must decide |
| `retake_requested` | `checking` | System | A new photo arrives |
| `needs_review` | `verified` | Billing executive | Approves, after filling any blank field |
| `needs_review` | `retake_requested` | Billing executive | Asks for a retake, under the cap |
| `needs_review` | `disputed` | Billing executive | The client disputes it |
| `disputed` | `verified` | Billing executive | Resolved |
| `verified` | `needs_review` | Billing executive | Pulls back a POD the AI wrongly passed |
| `verified` | `disputed` | Billing executive | The client disputes it |
| `verified` | `invoiced` | Billing executive | Exported to Tally |

Any other move is refused with a 409. A photo that arrives in any other status is kept as a late photo, numbered 4 and up and flagged in Review, but it's never sent to Gemini and doesn't move the status.

## 4. Main flows

### Driver at the gate, with signal

1. The driver opens the link from the SMS. It shows the trip code, number plate, route, LR and e-way bill numbers, and one big button labelled "फोटो लें". A speaker button plays a short spoken prompt in Hindi, Marathi or English, starting from the driver's language, and each later screen speaks its own (section 6).
2. The phone checks brightness and sharpness on a small copy of the photo. A blurred or dark photo is caught at once, with no network, and doesn't use up a retake. After two failures the driver can send it anyway, so a bad threshold can't trap them at the gate.
3. The phone shrinks the photo until it fits under 300 KB, lowering JPEG quality first and size second, because text stays readable at 1600 px. It draws a strip below the receipt with the time, GPS and trip code, so the proof stays with the image in the POD ZIP.
4. The upload stores the attempt, moves the trip to `checking` and returns at once. The phone polls every 2 seconds.
5. The driver sees one of three results: a green done screen, a retake screen with the reason and which fields failed, or the same green screen with "Sent to office" when a person must decide, because the driver can't fix that. With no result after 30 seconds, the driver is told they can go and will get an SMS if needed.

### Driver in a dead zone

The photo is kept in IndexedDB, one per trip; a new shot replaces an unsent one. The screen says "Saved on the phone, sends by itself". The phone sends it when signal returns, when the app is reopened and every 30 seconds while it's open. Every retry carries the same attempt ID, so a send that drops halfway can't create a duplicate. The photo is cleared only after the server confirms it. A missing location fix doesn't count against the driver, and a phone with a wrong clock has its time replaced by the server's time and the attempt flagged.

### Billing executive in Review

Review lists trips that need a person, oldest first, with the reason. The photo sits beside the six fields, each with the AI's value and confidence, and every attempt's reading is one click away. The executive can correct any field, approve, ask for a retake (disabled once two are used), mark the trip disputed or reveal the consignee's contact, which is logged. A Verified filter lets them pull back a trip the AI passed wrongly, before export. After an AI failure the fields are blank, and approve stays refused until all six are filled.

### Billing and export

Billing groups verified trips by client and by cycle, the 1st to 15th and the 16th to month end, taken from the delivery date. A late approval therefore doesn't move a trip to the wrong period. The executive selects trips, sees the total and exports. Each export makes one draft Sales voucher per client, with a line per trip carrying its LR and e-way bill numbers; a shortage remark goes in the narration and the trip bills full freight. The XML is stored, so downloading it again returns the same file, and exported trips are locked. The POD ZIP holds the photo each line was approved on, strip included.

### Trip import

The billing executive chooses the day's CSV file. The server checks every row and stores nothing: Pydantic reads each cell, then the row is checked against the trips on file and the rows above it. A row with no e-way bill, a repeated LR or trip code, or an unknown client or branch is rejected with its reason, and the rest are ready. Import sends the same file again, so nothing waits on the server between the steps, and the check runs afresh. Each new trip gets a driver link and a mock SMS, and a new lorry or driver is created the first time it appears. `import_batches` records the file, the counts and each rejected row's problems, without consignee or driver details. Importing a file twice adds nothing the second time, because every row is already on file.

### Missing PODs

The dashboard lists trips past expected delivery that are still waiting for a photo or a retake, with the hours since delivery and those over 24 hours marked. Every row has "Resend SMS link". The driver's phone is masked, so a "Call driver" button would have been dead. Three figures sit against the brief's targets: PODs within 24 hours (target 80%), POD-to-invoice days (target 4, also by branch) and lost or disputed (target 0.5%). Figures come from the data, over trips due in the last 90 days. Demo trips are left out of them.

## 5. How the AI part works

### The call

`ai.py` sends the photo to `gemini-3.5-flash-lite` with a short prompt that says what each field means on an Indian lorry receipt, and tells the model never to guess. The reply is constrained by a JSON schema generated from the Pydantic model `PodReading`. It's validated with Pydantic again on arrival, because structured output shapes a reply but doesn't guarantee it. A reply that doesn't fit, an error, a quota refusal or anything over 20 seconds all count as one answer: the AI is unavailable, and a person looks at the photo. Temperature and sampling settings are left at the model's defaults, as Google's notes for this model family advise. Every raw reply is kept on the attempt, so a disputed decision can be traced to what the model actually said.

The model returns six fields, each with a confidence from 0 to 1, plus an image quality flag:

| Field | Value |
| --- | --- |
| `lr_number` | Text |
| `consignee_stamp` | Present or absent |
| `quantity_received` | Number and unit |
| `remarks` | Text, plus a kind: none, shortage, damage or other |
| `delivery_date` | Date |
| `signature` | Present or absent |
| `image_quality` | OK, blurred or dark |

### The decision rule

The model suggests; a fixed, pure function decides. `decide()` in `rules.py` runs nine checks in order. The first match sets the status, and every match is kept as a reason code, so the reviewer sees all the problems at once. Checks the driver can fix come first, because the driver is still at the gate.

| # | Check | Result |
| --- | --- | --- |
| 1 | The AI call failed, timed out or didn't fit the schema | Needs review: `ai_unavailable`. The photo is kept |
| 2 | Blurred or dark, or stamp, signature, LR, quantity or date not found | Retake, or needs review with `retake_cap_reached` once two retakes are used |
| 3 | The LR number doesn't match the trip | Needs review: `lr_mismatch` |
| 4 | Taken more than 2 km from the consignee | Needs review: `location_far`. A missing location is skipped |
| 5 | The paper date is more than 1 day from the photo date | Needs review: `date_mismatch` |
| 6 | Any remark, or remark text labelled "none" | Needs review, whatever the confidence |
| 7 | Quantity below dispatch, above it or in another unit | Needs review: `qty_short` or `qty_mismatch` |
| 8 | Any field below 0.80 confidence | Needs review: `low_confidence` |
| 9 | Otherwise | Verified |

### When it's wrong or unsure

The brief asks what happens when the AI is wrong. The answer is layered, and none of it trusts the model's own confidence alone:

- **The image stays the source of truth.** Review always shows the photo beside the fields, and every reading is kept.
- **Checks against the trip catch wrong readings.** LR number, quantity, date and location are compared with what the trip file says, not with the model's confidence.
- **Remarks always go to a person.** A shortage or damage remark never passes on its own, even at full confidence.
- **Failure is safe.** An outage, a quota limit or a malformed reply sends the trip to Review with the photo kept. The trip keeps moving.
- **A wrong "verified" can be undone.** The executive pulls the trip back from Verified before export.
- **The AI never sends anything.** It can't invoice, and exports are draft vouchers a person creates.
- **Retakes cap at two.** The third failed attempt goes to a person, not back to the driver.

### Accuracy

`api/measure_accuracy.py` sent 10 sample sheets (the five demo scenarios and five seeded trips' sheets) in two sets, as clean renders and as synthetic phone photos, to the real model three times: 60 calls, with no AI failures. The photos skipped the phone's compression and strip, so they're a close stand-in for a real upload, not the same bytes. The full report is `docs/accuracy.md`.

- **On the readable sheets, all 324 field readings were right** (6 fields × 9 readable sheets per run × 2 sets × 3 runs). The lowest confidence on any right reading was 0.95, on one delivery date.
- **The blurred sheet is the important result.** The model was told not to guess, yet it invented values at high confidence: 11 wrong readings, most at 0.85 or above. A 0.80 threshold stopped 1 of them. The image quality flag and the checks against the trip are what stopped the sheet from being verified, and no sheet was wrongly verified.
- **Every scenario landed in the right status** except the rendered blurred sheet, which went to Review instead of a retake in 2 of 3 runs. That's the safe direction: a person looks, rather than a bad sheet passing.
- **Time:** median 2.5 seconds, slowest 12.8 seconds, against the 20-second limit.

So I kept the threshold at 0.80. Raising it to 0.95 would sit exactly on the lowest right reading, on evidence from one synthetic sheet. The point is that billing is protected by the fixed checks, not by the model's confidence. These are a first estimate on synthetic sheets. Nobody printed and photographed real paper, so this can't show how the model does on a real, creased, rain-marked receipt.

### Cost and abuse

Uploads are limited to 10 an hour per trip, counted from the audit log, so a leaked link, a fresh link or a demo reset can't run up Gemini calls. A repeated attempt ID doesn't count. In demo mode that caps Gemini at 50 calls an hour across the five demo trips.

## 6. UI and design decisions

The client asked for minimal design, and many drivers don't read well. The design follows from those two facts. The approved designs are static HTML in `design/screens/`, and every colour and font comes from `design/tokens.css`.

- **Paper and ink.** Warm grey paper, dark ink, one primary button per screen. The lorry receipt is drawn as stationery, because that's the object everyone in this business already knows.
- **Coral means settled.** Coral is kept for "Verified", links and focus rings, and never used as a fill. One colour with one meaning stays readable.
- **Green and ochre on driver screens only.** The brief asks for a clear success and retake colour. Coral would read as an error at a gate, so drivers see green for done and ochre for retake.
- **Type:** Instrument Sans throughout, Noto Sans Devanagari for Hindi, and Geist Mono for trip codes, LR numbers, amounts and times, so figures line up in columns.
- **No decoration without a job.** No gradients, no cards inside cards, no emoji as icons, no labels in capitals.
- **Spoken prompts for drivers who don't read well.** Nine short prompts, one per driver situation, play as each screen opens and again from a speaker button, for a noisy gate. The switch changes the driver's language on the server, so the next trip starts in it. Hindi and English play stored audio files; the page caches them, so they work in a dead zone. Marathi is spoken by the phone's own voice for now, and any file that can't play falls back to the phone's speech. The words are in `docs/voice-prompts.md`.

| Screen | What it looks like, and why |
| --- | --- |
| **Driver home** | The trip, then one huge button labelled "फोटो लें" with a camera icon. No forms and no menus. The driver checks one thing (is this my trip?) and does one thing. Location and network state show as icons, so the driver knows before shooting whether it will send now. A language switch (हिंदी, मराठी, English) and a speaker button sit above the trip. |
| **Checking** | The photo, then three steps ticking off: phone check, compressed and sent, AI reading. The driver can see progress and that the photo left the phone, which matters more than speed. |
| **Retake** | Ochre, "फिर से फोटो लें", the reason, six field checks with a tick or cross, and "Retake 1 of 2". The driver learns what to fix, not just that it failed. |
| **Done** | A big green tick and "हो गया". When a person must decide, the same green screen says "Sent to office", because the driver can't fix that and shouldn't wait at the gate. |
| **Saved on the phone** | Says the photo is safe and will send by itself, and shows it queued. Trust is the point: a driver who doubts it will resend on WhatsApp. |
| **Sign in** | Email and password, one button per demo role and a QR code to the driver demo, so a reviewer on a laptop can try the phone side in seconds. |
| **Review** | Queue on the left, the photo large in the middle, fields on the right with the AI's value and confidence. The photo is the evidence, so it gets the most space. Reason codes are written as plain sentences. The consignee contact is masked behind a logged reveal. |
| **Billing** | A table grouped by client, a cycle switch, a running total of the selection and one export button. Tables before cards: billing people compare rows. The count of trips still in review sits above, so nobody exports a cycle that isn't finished. |
| **Missing PODs** | Three figures against their targets, then the list, oldest first, with over-24-hour rows marked and "Resend SMS link" on each. On a phone each row stacks, so Resend stays in reach. |
| **Client PODs** | What a client's link opens: the client's checked PODs in one table, with "View POD" opening the photo over the page. No sign-in and nothing to change, and a dead link says to ask the transporter for a new one. Made from the "Client POD link" panel under the branch bars on Missing PODs. |
| **Trips** | The day's file, checked row by row before anything is imported. A bad row is marked with its reason in plain words, and the rest still import. The "Driver gets" column became own or hired, because every driver gets the SMS link. |

Office screens use a top bar with at most four destinations, not a sidebar. The operations head sees only Missing PODs, since that role can't approve or export. Review, Billing, Missing PODs and Trips each have loading (skeleton rows), empty (what belongs here) and error (what broke and what to do) states.

## 7. Security, privacy and audit

- **Office sign-in:** email and password, hashed with argon2. The session is a signed token in an http-only, SameSite cookie that lasts 8 hours. It holds only the user ID, and the role is read from the database on every request, so a changed role applies at once.
- **Roles on every route:** `require_role()` guards each office route. The operations head is refused on approve and export with a 403. Tests call every office route as every role.
- **Client POD links:** a signed token for one client that lasts 7 days and opens only reads: that client's checked PODs, with the consignee as initials and no phone. Each link made writes an audit event without the token. Tests refuse expired, tampered, unsigned and forged links, and a session token in place of one.
- **Driver links:** a random token per trip. Only a keyed HMAC-SHA256 hash is stored, so a database leak alone gives no working link. A link opens one trip only, expires 72 hours after expected delivery, and is checked on every driver route.
- **Personal data (DPDP Act 2023):** consignee name and phone and the driver's phone are masked in every API response. One endpoint reveals a consignee's contact, and each reveal writes an audit event. Seed data uses sample names and numbers only.
- **Validated inputs:** Pydantic on every request; uploads must be an image under 300 KB.
- **Append-only audit log:** every status change, field edit, reveal, export, retake request and mock SMS, with who and when.
- **Secrets:** environment variables only. `.env` is ignored by git and `.env.example` lists names only.

## 8. Testing

The tests follow four seams, chosen to test what a caller can see rather than how the code does it.

1. **The HTTP API (the main seam).** FastAPI's test client against a real Postgres test branch on Neon, with only the AI reader faked. SQLite would prove less, because idempotency depends on real unique constraints and the schema uses `jsonb` and `bytea`. The suite refuses to run if the test database shares a host with the app's, because it empties tables. It covers upload idempotency, intake limits, every allowed and refused status move, the retake cap, stuck attempts, role checks on every route, masking and reveal logging, stale versions, demo reset, the trip file's row checks and the edge cases in the data model.
2. **The decision rule.** `decide()` is pure, so it has a table of cases for every check and every order that matters, including a remark at high confidence, a missing location versus a far one, and confidence just below and exactly at 0.80.
3. **The pending-photo queue.** Vitest with fake storage and a fake network: one photo per trip, replacement, the same attempt ID on every retry, and clearing only after the server confirms.
4. **Voice prompts.** Vitest with a fake speaker: which prompt a retake plays, the audio file first, the phone's speech when the file can't play, silence when the browser blocks sound or a newer prompt cuts in, and a file on disk for every prompt.

The Tally export test parses the XML and checks voucher grouping, lines, LR and e-way bill numbers, narration, totals and that a re-download is identical. On 9 November 2026 there were 326 pytest test functions (674 cases with parameters) and 28 Vitest tests. The real Gemini call is measured, not tested (section 5).

## 9. Assumptions

The brief leaves many details open. Each assumption below is labelled so it can be checked with Company A. A1 to A13 come from `docs/data-model.md`; S1 to S50 come from `docs/spec.md` and keep its numbering.

### Data model assumptions

- **A1.** "Retakes are capped at two" means at most three photos per trip.
- **A2.** A trip is delivered when its photo is taken at the gate. A trip with no photo uses its expected delivery time from the trip file.
- **A3.** The trip file carries the branch, the quantity dispatched and the consignee's location. The brief's sample data shows none of these.
- **A4.** The branches (Sambhajinagar, Pune, Nagpur) are sample names.
- **A5.** Every client bills on the same two cycles a month: the 1st to 15th and the 16th to month end.
- **A6.** The confidence threshold is 0.80, the location radius 2 km, the date tolerance 1 day and the AI time limit 20 seconds. All four are starting values to tune. The threshold was checked on synthetic photos only, and the slowest of 60 calls took 12.8 seconds.
- **A7.** A driver link lasts until 72 hours after expected delivery, because an 800 km run can take about three days.
- **A8.** "Basic phones" means low-cost Android phones with a camera and a browser. Keypad phones aren't supported, so those trips stay on the missing-POD list.
- **A9.** A POD is lost once it's still missing 20 days after expected delivery, the top of the brief's 10 to 20 day range.
- **A10.** A shortage trip bills full freight, with the remark in the narration. Deductions and GST are out of scope.
- **A11.** A trip's billing cycle comes from its delivery date, not the day it was approved.
- **A12.** SMS, Tally and payments are mocked, as the brief allows.
- **A13.** The sample POD photos are synthetic: rendered sheets given a desk, an angle, uneven light, noise and compression by `samples/photograph_pods.py`. Nobody printed or photographed them, so accuracy and the threshold measured on them are a first estimate, not a field result.

### Spec assumptions

- **S1. Delivery time.** It's the first attempt's capture time, even after a retake.
- **S2. Which attempt counts.** Review, billing and the POD ZIP use the highest-numbered checked attempt, so late photos never count.
- **S3. Stuck attempts.** The 60-second rule runs on read, because Render's free tier has no reliable scheduler.
- **S4. SMS on retakes.** Every move to `retake_requested` sends a mock SMS, whether the system or a person made it.
- **S5. Resending a link.** Only a hash is stored, so a resend creates a new token. The old link stays valid until it expires, so a phone with a pending photo can still send it. A retake renews every unrevoked link on the trip.
- **S6. Expired link with a pending photo.** The server refuses the send, the phone keeps the photo and tells the driver to call the office.
- **S7. Approving a blank POD.** After an AI failure, approve is refused until all six fields are filled.
- **S8. Missing-POD list.** It holds trips past expected delivery in `awaiting_pod` or `retake_requested`, because a trip waiting on a retake is otherwise in nobody's queue.
- **S9. 24-hour figure.** A trip with no POD counts as a miss once expected delivery plus 24 hours has passed, so trips still on the road don't count against it. The data model's formula only sees trips with a photo, which would flatter the figure.
- **S10. Lost PODs.** The same two statuses count as "still missing" for a lost POD.
- **S11. Export conflicts.** An export is all or nothing. If any selected trip is no longer verified, it's refused and names the trips.
- **S12. Older cycles.** The cycle switch offers any cycle that still holds verified trips.
- **S13. Attempt numbering.** Intake locks the trip row while it numbers an attempt, so two photos arriving together can't collide.
- **S14. Client POD link.** A signed, stateless link expiring after 7 days, with no new table. It can't be revoked early, and each one made is logged.
- **S15. Trip import.** Each imported trip gets a driver link and a mock SMS. A row naming an unknown client or branch is rejected, and a new vehicle or driver is created on first sight.
- **S16. Demo role buttons.** The sign-in screen shows them only in demo mode.
- **S17. Session length.** An office session lasts 8 hours, one working day. The role is read from the database on each request.
- **S18. Operations head's top bar.** It shows only Missing PODs. The server enforces roles either way.
- **S19. Verified filter.** Review lists verified trips too, so an executive can reach one to pull it back before export.
- **S20. Resolving a dispute.** Resolve is approve: it moves the trip to `verified` with the same six-field check.
- **S21. Freight ledger.** The brief names no sales ledger, so every trip credits one called "Freight Income". The client's side uses its Tally ledger name.
- **S22. Voucher numbers.** `LND-` plus the first eight characters of the batch ID and the voucher's position, so no sequence is needed and Tally never sees a number twice.
- **S23. Voucher date.** The day of the export, in India time. The cycle still comes from the delivery date.
- **S24. One cycle per export.** An export spanning two cycles is refused, since a batch records one cycle.
- **S25. Export time.** Read from the trips' shared `invoiced_at`, because `export_batches` has no time column.
- **S26. Figure window.** The figures cover trips due in the last 90 days, not the 30 in the approved design. The seed spans about 30 days, so a 30-day window would empty as the demo ages during review. The missing-POD list has no window, so an old trip is never forgotten.
- **S27. Lost-or-disputed base.** The percentage is out of delivered trips: those with a photo or past expected delivery. A trip still on the road can't be lost yet, so it doesn't dilute the figure.
- **S28. Resending on an overdue trip.** A new link lasts 72 hours from now if that's later than 72 hours after expected delivery, so resending on a long-overdue trip doesn't make a link that's already expired. Only trips still waiting for a photo can be resent.
- **S29. Seeded history.** Seeded invoiced trips have an invoice time but no export batch, so they feed the figures but don't appear under "Earlier exports". Most seeded trips share one sample photo, so their LR numbers don't match it. The trips a reviewer meets first in Review have their own sheets.
- **S30. Demo routes.** The scenario picker has no sign-in, because a reviewer opens it from a QR code. It answers 404 with demo mode off. Picking a scenario costs no Gemini call, and the upload limit counts from the audit log, so a reset can't get round it.
- **S31. Sample photos.** A sample is sent with its sheet's date and the consignee's location, so it shows its scenario rather than a date or location problem. The phone check still runs, but a failure can't stop a sample, because the blurred one has to reach the AI check; it's recorded as sent anyway. A reviewer's own photo keeps its real time and place, so it may go to Review for that reason.
- **S32. Two reviewers on one scenario.** The demo trips are shared, so a second reviewer picking a scenario kills the first one's link, and the first sees the "call the office" screen. Picking the scenario again recovers it.
- **S33. Links in a mock SMS.** In demo mode an office retake makes a new link to show in the toast. A retake the system asks for shows none, because the driver is already on that screen.
- **S34. Resetting an exported demo trip.** The export keeps its stored XML, count and total. The trip leaves the POD ZIP, and an export holding only demo trips drops off "Earlier exports", because that list is read through the trips.
- **S35. The language switch changes the driver.** It sets the driver's language, so their next trip starts in it, and logs the change. With no signal the phone keeps the choice and sends it the next time the link opens.
- **S36. The switch changes the voice, not the screen.** Driver screens keep their Hindi headline with English beside it, as approved, and the switch sits on the trip screen only, as designed.
- **S37. Nine prompts, and English too.** The brief asks for Hindi or Marathi; English is there because the approved switch offers it.
- **S38. Marathi is spoken by the phone.** macOS has no Marathi voice and the Gemini key has no speech model, so Marathi has no audio files yet. Hindi and English files come from macOS voices, standing in for recordings.
- **S39. When a prompt plays.** As a screen opens. Phones block sound before the first tap, so a freshly opened link is silent until the driver taps the speaker or the switch.
- **S40. Check, then import.** The Trips screen checks the file and stores nothing; the import sends the same file again and the server checks it afresh. Only a file that can't be read as trips is refused whole. Otherwise each row stands alone. Two imports adding the same trip at once: the second is refused whole and checked again.
- **S41. The file's columns.** The brief names no format, so the file has one row per trip with the columns in the sample file. Times are India time and freight is in rupees. Other columns are ignored, client and branch names match whatever their case, a trip code must be new and delivery can't be before dispatch.
- **S42. Repeats within a file.** Only a row that will import claims its trip code and LR, so a corrected copy below a broken row still goes in.
- **S43. Who a driver is.** A driver is known by phone number. A known driver keeps the name and language on file. A blank language means Hindi.
- **S44. A known lorry keeps its record.** Matched by registration number, ignoring spaces and case. The fleet's own or hired wins over the row's.
- **S45. The rows to fix** are copied out of the chosen file in the browser, so consignee details never come back in a response.
- **S46. Every driver gets the link**, own or hired.
- **S47. Who makes a client link.** Both office roles, from the Missing PODs screen. The data model gives it to the operations head, and the billing executive has the same dashboard. A client picker sits beside "Copy link", because a link opens one client.
- **S48. What a client sees.** Its verified and invoiced trips, newest first: LR and remark as billing read them, e-way bill, route, delivery date, the consignee's initials and whether it's invoiced. Nothing in review or disputed, and no phone number. The photo is the one billing used, opened one at a time.
- **S49. How the link is signed.** A JWT with the client ID and expiry, signed with the session secret so no new secret is needed. An audience claim keeps client links and sessions from being swapped. Changing the session secret ends every client link too.
- **S50. The token travels in a header**, like a driver's, so it stays out of the API's request logs. Expired, tampered and unknown links all get the same refusal.

## 10. Limits

Honest notes on what this build doesn't do, or hasn't proven.

- **The AI was measured on synthetic sheets only.** Every readable field was right, so the measurement can't show what the threshold would catch on real photos. The model's confidence isn't calibrated. Stamp, signature and remarks have no trip value to check against, so confidence is their only guard, and no wrong reading of those was seen.
- **Photos go to Google on the free tier.** The Gemini key is on the unpaid tier. Google's Gemini API terms (effective 23 March 2026) say that unpaid-tier prompts and images may be used to improve Google's products, that human reviewers may read them, and that personal information shouldn't be sent. That's acceptable for this demo, because every sheet is synthetic and holds sample names. Real PODs carry consignee names, stamps and signatures, which are personal data under the DPDP Act, so production must use a paid, billed project, where Google doesn't use content to improve its products and processing falls under its data processing terms. Free-tier quotas are also small and shared across the project; when one runs out, every check goes to Review through rule 1, which is safe but slow.
- **Masking can't cover the photo**, which shows the consignee's stamp and possibly a signature.
- **The Tally XML has never been imported into a real Tally.** It follows Tally's import format and the tests parse it, but the first real import may need adjustments.
- **Not yet tested on a real Android phone over mobile data.** Camera capture, compression, the service worker and airplane mode still need that check. The phone's blur and brightness limits came from the synthetic photos and need tuning on real phones.
- **The first open of a driver link needs network**, because a PWA can't cache itself before its first visit. The SMS goes out at dispatch to make that likely.
- **The voice prompts haven't been checked by native speakers.** The words are mine, the Hindi and English voices are synthetic, and Marathi depends on the phone having a Marathi voice. A Hindi and a Marathi speaker should check the words and record them before drivers rely on them.
- **A closed app sends nothing until it's reopened.** Background Sync would fix this and was left as a stretch goal.
- **Sessions can't be cancelled early.** Sign out clears the cookie, but a copied token works until it expires, which is why sessions last 8 hours.
- **Sign-in has no attempt limit**, so password guessing is only slowed by the argon2 hash.
- **Seeded data ages.** Missing-POD rows are dated relative to the day of seeding, so hours since delivery grow, trips cross the 24-hour mark and later the 20-day lost mark, and the figures move with them.
- **Free hosting.** Render's free tier sleeps after 15 minutes idle and takes about a minute to wake; an uptime monitor keeps it awake. A restart during a check loses that check, and the 60-second rule sends it to a person.
- **Disputes after invoicing aren't handled**, because they'd need a Tally reversal.

## 11. What I cut, and what I'd do next

I built the core slice first and cut from the optional depth, in the order planned before building: landing page, trip CSV import, client POD link, operations head role. The operations head role, the trip import and the client POD link made it in. Never cut: the retake flow, the review screen and offline capture.

| Cut | Why, and what's there instead |
| --- | --- |
| **Landing page** | Not part of the core build. |
| **Real SMS, real Tally connection, payments** | Mocked, as the brief allows. Every SMS writes an audit event, and demo mode shows the link in a toast. |

Next, in order:

1. **Field test on real phones and real paper** with a few drivers on one route: tune the phone's blur limits, re-run the accuracy script on real PODs, and set the confidence threshold from that.
2. **Move to a paid Gemini project** before any real POD is sent (section 10), and add a real SMS gateway, which in India needs DLT registration of the sender and templates.
3. **Native recordings of the voice prompts**, checked by a Hindi and a Marathi speaker, and **the trip import tried on the client's real daily file**, whose format is my assumption (S41).
4. **Import the XML into a real Tally** with the billing team, and fix what it rejects.
5. **Photos to object storage**, using the existing `image_key` column, once volume grows: about 2,200 trips a month at up to 300 KB each is roughly 0.5 GB of photos a month.
6. **Background Sync**, so a closed app still sends its photo.
7. **Hardening:** a sign-in attempt limit, server-side session revocation, branch scoping for the operations head, and disputes after invoicing with a Tally reversal.
