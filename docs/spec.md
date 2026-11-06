# Spec: Landed core build

Status: ready for agent. The rules live in `docs/data-model.md`, the screens in `docs/design.md`, the build order in `docs/plan.md`, and the words in `GLOSSARY.md`. If this spec and `docs/data-model.md` disagree, the data model wins until one of them is changed on purpose.

## Problem Statement

Company A, a full-truckload transporter in Chhatrapati Sambhajinagar, can't bill a trip until the signed paper comes back, often 10 to 20 days after delivery and from up to 800 km away. Photos sent on WhatsApp get lost, and clients reject any invoice without a POD. POD-to-invoice takes 18 days, and 1.5% of PODs are lost or disputed. The brief puts the cost at ₹1.02 crore a year.

Each group feels this differently:

- **Drivers** have low-cost phones, may not read well, won't install an app if they're hired, and lose signal on highways. Once they leave the gate, a bad photo can't be fixed cheaply.
- **Billing executives** chase paper and photos, and they can't tell a usable POD from an unusable one without opening each one.
- **The operations head** can't see which trips have no POD until the paper fails to arrive.

## Solution

At the gate, the driver opens the driver link from an SMS and presses one big button to photograph the POD. No install, no login and no forms are involved. The phone checks the photo for blur and brightness, compresses it under 300 KB, prints GPS and time on a strip below the receipt, and sends it. If there's no signal, the photo waits on the phone and sends itself later.

While the driver is still there, a vision model reads six fields from the photo. A fixed decision rule then turns that reading into a status. If the driver can fix the problem, they are asked for a retake, at most two times. Anything that needs judgement goes to a billing executive, including every shortage or damage remark, low confidence and AI failure. The AI never moves money.

The billing executive reviews the photo beside the editable fields and approves, corrects, asks for a retake or marks the trip disputed. Verified trips appear in a billing queue by client and cycle, and they export to Tally as draft vouchers with a ZIP of POD photos. A dashboard shows trips with no POD and the three figures from the brief's success targets.

## User Stories

### Driver: at the gate

1. As a driver, I want to open my trip from an SMS link without installing anything, so that I can use the phone I already have.
2. As a hired driver, I want the same link as an own driver, so that nobody has to set me up separately.
3. As a driver, I want the link to open only my trip, so that I never have to search or sign in.
4. As a driver, I want to see the trip code, number plate, route, LR and e-way bill, so that I know I'm on the right trip.
5. As a driver, I want one big button to photograph the POD, so that I know what to do without reading.
6. As a driver, I want icons and a clear colour for success or retake, so that I understand the result if I don't read well.
7. As a driver, I want spoken prompts in Hindi or Marathi, so that I'm told what to do in my own language.
8. As a driver, I want to switch language and replay a prompt, so that I can hear it again at a noisy gate.
9. As a driver, I want a blurred or dark photo caught on the phone, so that I can fix it at once and not lose a retake.
10. As a driver, I want to send a photo anyway after two phone check failures, so that a bad threshold can't trap me at the gate.
11. As a driver, I want to see when the check is finished, so that I know whether I can leave.
12. As a driver, I want a green done screen when the POD is verified, so that I can drive on.
13. As a driver, I want the same green done screen with "Sent to office" when a person must decide, so that I'm not kept waiting for something I can't fix.
14. As a driver, I want a retake screen that shows the reason and which fields failed, so that I know what to photograph better.
15. As a driver, I want to see how many retakes I've used, so that I know where I stand.
16. As a driver, I want "You can go, we'll SMS if needed" when there's no result after 30 seconds, so that a slow check doesn't hold up the truck.
17. As a driver, I want to see "done" and no camera button if I reopen a finished trip, so that I don't send photos for no reason.
18. As a driver, I want an expired or revoked link to tell me to call the office, so that I know how to get a new one.

### Driver: no signal

19. As a driver in a dead zone, I want to take the photo with no network, so that the highway doesn't stop me finishing the job.
20. As a driver, I want to see that the photo is saved on the phone and will send by itself, so that I can trust it and move on.
21. As a driver, I want a new shot to replace an unsent one, so that the office receives my best photo.
22. As a driver, I want a saved photo to send when signal returns while the app is open, so that I don't have to remember to do it.
23. As a driver, I want a saved photo to send when I reopen the app, so that closing the app doesn't lose it.
24. As a driver, I want a dropped connection in mid-send to do no harm, so that a retry never creates a duplicate POD.
25. As a driver with no location fix, I want my photo accepted anyway, so that a dead zone doesn't count against me.
26. As a driver with a wrong phone clock, I want my photo accepted, so that a bad setting doesn't block delivery.

### AI check

27. As a billing executive, I want the AI check to read LR number, consignee stamp, quantity received, remarks, delivery date and signature, so that I only look at what needs a person.
28. As a billing executive, I want a mismatched LR number sent to me, so that a wrong sheet is never billed.
29. As a billing executive, I want a photo taken more than 2 km from the consignee flagged, so that a photo taken elsewhere gets a second look.
30. As a billing executive, I want a paper date more than 1 day from the photo date flagged, so that an old LR isn't passed as new.
31. As a billing executive, I want any shortage, damage or other remark sent to me whatever the confidence, so that "seal broken" never passes on its own.
32. As a billing executive, I want a short or mismatched quantity sent to me, so that a difference from dispatch isn't missed.
33. As a billing executive, I want low-confidence readings sent to me, so that an unsure AI doesn't verify a POD.
34. As a billing executive, I want an AI failure or timeout sent to me with the photo kept, so that the trip keeps moving when the model is down.
35. As a billing executive, I want every matched reason kept, so that I see all the problems and not only the first.
36. As a billing executive, I want a trip stuck in Checking to reach me after 60 seconds, so that a server restart can't strand it.
37. As a billing executive, I want the third failed attempt sent to me rather than back to the driver, so that retakes stop at two.

### Review

38. As a billing executive, I want a queue of PODs that need a person, oldest first with the reason shown, so that I know what to work on next.
39. As a billing executive, I want the photo beside the fields it was read from, so that the image stays the source of truth.
40. As a billing executive, I want to see what the AI read on each attempt, so that I can see what changed between tries.
41. As a billing executive, I want to correct any field, so that billing uses the right value.
42. As a billing executive, I want the AI's value kept next to my correction, so that the original reading is never lost.
43. As a billing executive, I want every edit logged with who and when, so that a change can be traced.
44. As a billing executive, I want to approve a POD, so that it moves to the billing queue.
45. As a billing executive, I want to ask for a retake, so that the driver gets an SMS and can send a better photo.
46. As a billing executive, I want the retake button disabled once two are used, so that I know to approve, correct or dispute instead.
47. As a billing executive, I want to mark a POD disputed, so that it stays out of billing until resolved.
48. As a billing executive, I want a Disputed filter, so that I can find and resolve open disputes.
49. As a billing executive, I want to pull a trip back from Verified, so that I can correct a POD the AI wrongly passed before export.
50. As a billing executive, I want late photos kept and flagged but not checked, so that nothing is lost and no status moves by surprise.
51. As a billing executive, I want a conflict message if someone saved the trip first, so that we don't overwrite each other.
52. As a billing executive, I want consignee names and phones masked by default, so that personal data is shown only when needed.
53. As a billing executive, I want a logged reveal of the consignee contact, so that I can call when I need to and the access is on record.

### Billing

54. As a billing executive, I want verified trips grouped by client and cycle, so that I can bill the way clients are billed.
55. As a billing executive, I want a trip's cycle to come from its delivery date, so that a late approval doesn't move it to the wrong period.
56. As a billing executive, I want to see how many trips are still in review, so that I can finish them before exporting.
57. As a billing executive, I want to select trips and see the total, so that I know what I'm about to export.
58. As a billing executive, I want one draft voucher per client per export, with a line per trip, so that Tally receives grouped entries.
59. As a billing executive, I want each line to carry the LR and e-way bill numbers, so that a client can match it to the trip.
60. As a billing executive, I want a shortage remark in the voucher narration, so that the trip bills full freight and the note isn't lost.
61. As a billing executive, I want to download the POD photos for an export as a ZIP, so that I can attach them to invoices.
62. As a billing executive, I want earlier exports listed and the same XML returned on download, so that a re-download can't create different vouchers.
63. As a billing executive, I want an exported trip locked, so that nothing changes after it's in Tally.

### Dashboard and missing PODs

64. As an operations head, I want a list of trips with no usable POD and the time since delivery, so that I can act on the oldest.
65. As an operations head, I want trips over 24 hours marked, so that I can see which ones have missed the target.
66. As an operations head, I want to resend the driver link from any missing-POD row, so that I can act even though the driver's phone is masked.
67. As an operations head, I want PODs within 24 hours, POD-to-invoice days and lost or disputed shown against the targets, so that I can see whether Landed is paying off.
68. As an operations head, I want POD-to-invoice days by branch, so that I know which branch needs help.
69. As an operations head, I want to be refused on approve and export, so that review stays with the billing desk.
70. As a billing executive, I want the same dashboard, so that the core build works with only my role.
71. As an office user, I want a real loading, empty and error state in every data region, so that I can always tell what's happening.

### Access, safety and audit

72. As an office user, I want to sign in with email and password, so that only staff can open the office screens.
73. As the transporter, I want every office route to check the role and every driver route to check the token, so that a guessed URL opens nothing.
74. As the transporter, I want driver tokens stored only as hashes, so that a database leak doesn't expose working links.
75. As the transporter, I want uploads limited to 10 an hour per trip, so that a leaked link can't run up Gemini costs.
76. As the transporter, I want every status change, field edit, reveal, export and retake request in an append-only log, so that any dispute can be traced.
77. As a client's accounts team, I want a read-only link to view PODs, so that I can check proof without asking for it (optional depth).
78. As a billing executive, I want to import the daily trip file and see row-level errors, so that one bad row doesn't block the rest (optional depth).

### Demo

79. As an assignment reviewer, I want realistic seeded data, so that the app doesn't look empty.
80. As an assignment reviewer, I want to pick one of five demo scenarios and run it against the real AI check, so that I can see each path work.
81. As an assignment reviewer, I want to reset a demo trip, so that I can try it again.
82. As an assignment reviewer, I want a "Mock SMS sent" toast with an "Open link" button, so that I can follow a link without a real SMS.
83. As an assignment reviewer, I want demo trips kept out of the dashboard figures, so that a reset can't move them.
84. As an assignment reviewer, I want demo logins for both office roles, so that I can try each one without an account.

## Implementation Decisions

### Modules

- **Decision rule.** A pure function with no I/O. It takes an AI reading, or a failure, plus the trip facts the rule needs, and returns the status, the reason and every matched reason code. All nine checks and their order come from `docs/data-model.md`.
- **Status machine.** One place that moves a trip's status. It refuses any move outside the seven-status diagram and writes the audit event in the same transaction. Nothing else writes `pod_status`.
- **AI reader.** A deep module with one small interface: given image bytes, return a validated reading or a failure. It hides the SDK, the structured output schema, the second Pydantic validation and the 20-second timeout. A reply that doesn't fit the schema is a failure. This interface is where tests swap in a fake.
- **Attempt intake.** Takes a photo from a valid driver token. It handles idempotency, the size and image checks, the rate limit, late photos, attempt numbering and the wrong-clock case. Then it schedules the background check and returns at once.
- **Tally export.** Turns selected trips into stored XML, with one Sales voucher per client and a line per trip. It doesn't depend on HTTP.
- **Routers.** Thin layers for auth, driver, review, billing, dashboard and trips. Validation and role checks live here; rules don't.
- **Pending-photo queue.** A TypeScript module with no UI. It holds one pending photo per trip in IndexedDB, replaces it on a new capture, and sends with the same attempt ID each time. It clears a photo only once the server has confirmed it. Storage and network are passed in, so it can be tested without a browser.
- **Capture pipeline.** Phone check, canvas compression under 300 KB, and the printed strip. It recompresses at lower quality if the result is over the limit.
- **Web app.** One React app with two areas, driver and office, using plain CSS and the design tokens. The driver area is a PWA whose shell is cached after the first visit.

### Schema and data

- Twelve tables as listed in `docs/data-model.md`, created through Alembic.
- Each AI field is stored twice, as `ai_value` and `final_value`. Billing reads `final_value`.
- Money is in paise as integers and times are in UTC. Screens show rupees and India time.
- `trips.version` gives optimistic locking. A stale save returns a conflict and the screen reloads the trip.
- Photos are `bytea` for the demo. `image_key` keeps a later move to object storage small.

### API contracts

- `POST` of an attempt is idempotent on the phone's attempt ID. A repeat returns the first result, stores nothing new and doesn't count toward the rate limit.
- The upload returns at once. The phone polls every 2 seconds for the status.
- Every response masks consignee name and phone and driver phone. One logged reveal endpoint is the only way to see a consignee contact.
- Office routes use a short-lived token in an http-only cookie, reached through a Vercel rewrite from `/api/*` to Render, so it stays first-party and CORS isn't needed.
- The status codes below are the contract:

| Case | Response |
| --- | --- |
| Not signed in, or a bad driver token | 401 |
| Wrong role | 403 |
| Stale `version`, or a move the status machine refuses | 409 |
| Photo over 300 KB | 413 |
| Upload rate limit reached | 429 |
| Input fails validation | 422 |

### Background check

- The upload saves the attempt and moves the trip to `checking`. A background task calls the AI reader, runs the decision rule and applies the result in one transaction.
- A late result must not overwrite a person's decision. The task applies its result only if the trip is still in `checking` for that attempt.

### Config

- `.env.example` lists `DEMO_MODE`, which turns on the demo rules, and `DATABASE_URL_TEST`, the test branch's URL.
- The app uses `DATABASE_URL_POOLED` and Alembic uses `DATABASE_URL`. Connection details follow CLAUDE.md.

## Testing Decisions

A good test here calls what a real caller calls and checks what a real caller can see: the response, and the status, fields and audit events that follow. It shouldn't reach into private functions or assert how something was done. It should still pass after a refactor that keeps the behaviour.

There are three seams, agreed with Aamir. There is no prior art yet, since the repo has no code, so the first tests set the pattern.

### Seam 1: the HTTP API

Tests call FastAPI's test client against a real Postgres database, with only the AI reader faked. This is the main seam, and most tests belong here.

- **Database.** A separate Neon branch, reached through `DATABASE_URL_TEST`. This Mac has no local Postgres or Docker, the schema uses `jsonb` and `bytea`, and idempotency depends on real unique constraints, so SQLite would prove less. The cost is that tests need network and run a little slower.
- **Safety check.** The suite refuses to run if `DATABASE_URL_TEST` is unset, or if its host matches the host in `DATABASE_URL` or `DATABASE_URL_POOLED`, because it empties tables.
- **Start of each run.** The suite runs the Alembic migrations on the test branch, then empties the tables. `DATABASE_URL_TEST` is the branch's direct URL, because migrations don't run through the pooler.
- **Isolation.** Each test creates its own trips through small factories, so tests don't share state. The background check opens its own session, so a wrapping transaction that rolls back would hide its writes.
- **Fake AI reader.** Tests choose its reply for each case: a clean reading, a failure, a timeout or a malformed reply.

This seam covers:

- Upload idempotency: the same attempt ID sent twice stores one attempt and returns the first result.
- Attempt intake: size limit, image check, rate limit, late photos and the wrong clock.
- Status moves: every allowed move, plus refused moves such as `invoiced` back to `verified`.
- Retake cap: a third failed attempt goes to `needs_review`, and an office retake past the cap is refused.
- The 60-second rule for stuck attempts.
- Role checks: each office route for each role, and each driver route with a bad, expired or revoked token and with another trip's token.
- Masking: consignee and driver contacts are absent from every response, and a reveal writes an audit event.
- Tally export: parse the XML and check voucher grouping, lines, LR and e-way bill numbers, narration, totals and that a re-download returns identical XML.
- Stale `version` on a save.
- Demo reset: it touches only `is_demo` rows, and seeded history is unchanged.
- The edge cases table in `docs/data-model.md`, one test per row that reaches the server.

### Seam 2: the decision rule

The decision rule is a pure function, so it gets a table of cases: one for every check and every order that matters. These include a remark at high confidence, a location that's missing rather than far, confidence just below and exactly at 0.80, and the retake cap. The fast feedback suits a rule with this many branches, and CLAUDE.md requires it.

### Seam 3: the pending-photo queue

Vitest tests with fake storage and a fake network. This is a new seam, and it's worth having because offline capture is the brief's hard part and is on the never-cut list.

It covers one pending photo per trip, a new capture replacing an unsent one, the same attempt ID on every retry, keeping the photo after a failed send, and clearing it only after the server confirms.

### Not covered by automated tests

- The real Gemini call. A separate script reports accuracy per field on the sample photos and is used to tune the threshold. It's a measurement, not a test.
- Camera, compression and service worker behaviour on real devices. These are checked by hand on a real Android phone over mobile data, with airplane mode on and off.

## Out of Scope

From the brief:

- Live GPS tracking
- Trip planning
- Fuel and driver expense accounting

Mocked, as the brief allows:

- Real SMS sending
- A live Tally connection; Landed exports XML only
- Payments

Decided against for this build:

- Sending or issuing invoices; Landed creates draft vouchers only
- Deductions and GST
- Disputes after invoicing, which would need a Tally reversal
- Keypad phones; those trips stay on the missing-POD list
- Object storage for photos
- Background Sync (stretch goal), so a closed app sends nothing until it's reopened

## Further Notes

### Cut order

If time runs short, cut in this order: landing page, trip CSV import, client POD link, operations head role. Never cut the retake flow, the review screen or offline capture. Stories 77 and 78 are on that list. If the operations head role goes, stories 64 to 68 still work for the billing executive through story 70, and story 69 drops out. Voice prompts are built last. Deadline: submit by Sunday evening, 8 Nov 2026.

### Assumptions this spec adds

The docs leave these open. Each is a default to follow unless changed, and each belongs in the TDD's labelled assumptions along with the list in `docs/data-model.md`. Aamir has accepted 3, 5, 8 and 9.

1. **Delivery time.** A trip's delivery time is the first attempt's `captured_at`, even after a retake. This matches how the data model measures the 24-hour figure.
2. **Which attempt counts.** Review and billing use the highest-numbered checked attempt, so late photos never count. The POD ZIP uses the same photo.
3. **Stuck attempts.** Render's free tier has no reliable scheduler, so the 60-second rule runs on read. A driver poll and an office queue or dashboard load each sweep for stuck attempts.
4. **SMS on retakes.** Every move to `retake_requested` sends a mock SMS, whether the system or a person made it. This is what makes "we'll SMS if needed" true.
5. **Resending a link.** Only a hash is stored, so a resend must create a new token. The old link stays valid until it expires, so a phone with a pending photo can still send it. A retake renews every unrevoked link on the trip.
6. **Expired link with a pending photo.** The server refuses the send and the phone keeps the photo. It tells the driver to call the office.
7. **Approving a blank POD.** After an AI failure the fields are empty. Approve is refused until the executive has filled in all six.
8. **Missing-POD list.** It holds trips past expected delivery in `awaiting_pod` or `retake_requested`. A trip waiting on a retake is in nobody's queue otherwise, because Review shows only `needs_review`.
9. **24-hour figure.** A trip with no POD counts as a miss only once its expected delivery plus 24 hours has passed, so trips still on the road don't count against the figure. The data model's formula only sees trips with a photo, which would flatter the figure.
10. **Lost PODs.** The same two statuses apply to "still missing" when counting a lost POD.
11. **Export conflicts.** An export is all or nothing. If any selected trip has stopped being `verified`, the export is refused and names the trips.
12. **Older cycles.** The cycle switch offers any cycle holding verified trips, so one left over from an earlier cycle doesn't disappear.
13. **Attempt numbering.** Intake locks the trip row while it assigns `attempt_no`, so two different photos arriving together can't collide.
14. **Client POD link.** There's no table for it and the twelve-table count stands, so it's a signed, stateless link that expires after 7 days. It can't be revoked early. Each one made is logged.
15. **Trip import.** Each imported trip gets a driver link and a mock SMS. A row naming an unknown client or branch is rejected, and a new vehicle or driver is created on first sight.
16. **Demo role buttons.** The sign-in screen shows them only in `DEMO_MODE`.

### Screen changes

`docs/plan.md` lists the agreed changes from the approved designs. The main ones are "Resend SMS link" on every missing-POD row in place of "Call driver", "Mark disputed" and a Disputed filter in Review, and the green done screen for `needs_review`.

### Limits to state in the TDD

- Masking can't cover the photo itself, which shows the stamp and possibly a signature.
- Photos go to Google for the AI check. The terms for this key's tier still need checking.
- The first open of a driver link needs network.
- The model's confidence isn't calibrated, so 0.80 is a starting value tuned on sample photos.
