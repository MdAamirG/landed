# Build plan

Deadline: about Sunday night, 8 Nov 2026. Submit by Sunday evening. The brief lets you resubmit until the deadline.

## How we work

- Small commits on `main`, with a push after each working slice
- Show Aamir the diff before each commit, and wait for the go-ahead
- Run the tests before every push

## Before code

- [x] Public GitHub repo, first commit of this folder
- [x] Neon project (use the pooled connection string, `sslmode=require`)
- [x] Gemini API key
- [x] Render account (API) and Vercel account (web)
- [x] Rendered LR template and the five scenarios (clean, blurry, no stamp, "short by 6 cartons", wrong LR number) in `samples/pods/`, so the build isn't blocked
- [x] Synthetic phone-style photos of the five scenarios in `samples/pods/photos/`, in place of Aamir printing and photographing them. The threshold is tuned on these, as a first estimate

The days below follow the tickets in `.scratch/landed-core/issues/`, in the order listed. The tickets hold the acceptance criteria.

## Friday night: foundation

Tickets 01, 04, 03, 02.

- [x] FastAPI app, config from environment, health route
- [x] SQLAlchemy models for the twelve tables in `docs/data-model.md`, Alembic migration
- [x] Seed script: the brief's 3 trips, 3 clients, 3 branches, demo users
- [x] `decide()` in `api/app/rules.py`: the decision rule as a pure function, with a pytest case for every rule and edge case
- [x] Deploy the API to Render's free tier in Singapore, next to Neon, with an uptime ping to `/api/ping` every 10 minutes, and run the seed against Neon
- [x] Vercel rewrite from `/api/*` to Render, so the sign-in cookie is first-party and CORS isn't needed

## Saturday: sign-in, driver side and first review

Tickets 05, 06, 07, 08, 10, 11, 12.

- [x] Office login (email and password, http-only cookie) and role checks
- [x] Driver link tokens (hashed, expiring 72 hours after expected delivery) and the upload endpoint (idempotent on attempt ID, 300 KB limit, image type check, returns at once)
- [x] Gemini vision call returning the Pydantic schema, in a background task, with a 20-second timeout, the `ai_unavailable` fallback and the 60-second rule for stuck attempts
- [x] Driver PWA: trip screen, camera (`<input type="file" accept="image/*" capture="environment">`), canvas compression under 300 KB with the GPS and time strip below the receipt, phone-side blur and brightness check with send-anyway after two failures, IndexedDB queue holding one pending photo per trip, retry on reconnect, on app open and every 30 seconds, polling every 2 seconds, result screens
- [x] Review screen: photo beside editable fields, every reason code, approve, reveal contact (logged)

## Sunday: rest of review, billing, dashboard, demo, submit

Tickets 13, 14, 15, 16, 09, 21.

- [x] Review actions: ask for retake, mark disputed, pull back from verified, Disputed filter
- [x] Billing queue by client and cycle (from delivery date), Tally XML export with one voucher per client per export, POD photos ZIP
- [x] History seed: about 200 backdated trips sharing a few sample images. The dashboard needs that many: one dispute in 18 trips is 5.6%, and 0.6% takes at least 167. It shows whatever the data computes
- [x] Missing-POD dashboard, open to the billing executive and the operations head
- [x] Demo mode behind `DEMO_MODE`: five demo trips, scenario picker, reset limited to `is_demo` rows with a test proving seeded history is untouched, mock SMS toast
- [x] Script reporting accuracy per field on the sample photos; tune the confidence threshold and put the numbers in the TDD
- [ ] Loading, empty and error states on every data region
- [ ] Test on a real Android phone over mobile data, airplane mode on and off
- [ ] Aamir decides whether to move Render to a paid plan before submitting
- [x] `deployment.md` and the TDD (GitHub URL and live link at the top). The TDD is `docs/tdd.md`; `uv run docs/build_submission.py` builds the PDF and the ZIP
- [ ] Submit

## Only if time remains

Tickets 17 to 20.

- [ ] Voice prompts: about 8 short prompts in Hindi and Marathi as cached audio files. Browser speech is the fallback. A Hindi and Marathi speaker checks them. Built on 8 Nov 2026 (ticket 17); waiting on the speaker check in `docs/voice-prompts.md`
- [x] Trip CSV import. Built on 9 Nov 2026 (ticket 18): the Trips screen checks the file row by row, then imports the good rows
- [x] Client POD link. Built on 9 Nov 2026 (ticket 19): a signed 7-day link from the Missing PODs screen opens a read-only list of one client's checked PODs
- [ ] Landing page

## Stretch

- Background Sync, so a closed app can still send queued photos

## Screen changes from the approved designs

- `Trips.html`: replace the "Driver gets" column with own or hired, and send every driver the SMS link. Built (ticket 18) with these differences: the counts read "22 ready, 2 to fix", because a row can have several problems; "checked at" in place of "uploaded at", since nothing is stored until import; a duplicate is marked like any other problem; and in demo mode each imported row has its own "Mock SMS sent" and "Open link" in place of a toast, since one import sends many
- `Dashboard.html`: every missing-POD row shows "Resend SMS link", because the driver's phone is masked and "Call driver" would be a dead button. The figures cover 90 days, not 30 (spec assumption 26). The client POD link (ticket 19) adds a client picker beside "Copy link", because a link opens one client, and shows the link to copy by hand when the browser has no clipboard. On a phone each row becomes a stacked block, so Resend stays in reach
- `Review.html`: add "Mark disputed", a Disputed filter and a flag for late photos
- `Main.html`: "Open the driver demo" leads to the five-scenario picker
- Office screens: a "Mock SMS sent" toast with an "Open link" button in demo mode
- Driver result screen: `needs_review` uses the green done screen, with "Sent to office"

## Cut in this order if behind

1. Landing page (ship it after submitting)
2. Trip CSV import (seed the data instead)
3. Client POD link
4. Operations head role

Never cut: the retake flow, the review screen, offline capture.
