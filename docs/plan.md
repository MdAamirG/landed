# Build plan

Deadline: about Sunday night, 8 Nov 2026. Submit by Sunday evening. The brief lets you resubmit until the deadline.

## Before code

- [ ] Public GitHub repo, first commit of this folder
- [ ] Neon project (use the pooled connection string, `sslmode=require`)
- [ ] Gemini API key
- [ ] Render account (API) and Vercel account (web)
- [ ] 4–5 printed test lorry receipts, photographed: clean, blurry, no stamp, "short by 6 cartons", wrong LR number. Save them in `samples/pods/`

## Friday night: backend core

- [ ] FastAPI app, config from environment, health route
- [ ] SQLAlchemy models for the twelve tables in `docs/data-model.md`, Alembic migration
- [ ] Seed script: the brief's 3 trips plus about 15 more, 3 clients, 3 branches, demo users
- [ ] `decide()` in `api/app/rules.py`: the decision rule as a pure function, with a pytest case for every rule and edge case
- [ ] Office login (email and password, http-only cookie) and role checks
- [ ] Driver link tokens (hashed, 72 hours) and the upload endpoint (idempotent on attempt ID, 300 KB limit, image type check)
- [ ] Deploy the API to Render and run the seed against Neon

## Saturday: AI and driver side

- [ ] Gemini vision call returning the Pydantic schema, with a 20-second timeout and the `ai_unavailable` fallback
- [ ] Run it on the sample photos; tune the confidence threshold
- [ ] Driver PWA: trip screen, camera (`<input type="file" accept="image/*" capture="environment">`), canvas compression under 300 KB, phone-side blur and brightness check, IndexedDB queue that uploads when online, result screens
- [ ] Review screen: photo beside editable fields, approve, ask for retake, reveal contact (logged)

## Sunday: billing, polish, submit

- [ ] Billing queue by client and cycle, Tally XML export, POD photos ZIP
- [ ] Missing-POD dashboard
- [ ] Loading, empty and error states on every data region
- [ ] Test on a real Android phone over mobile data, airplane mode on and off
- [ ] `deployment.md` and the TDD (GitHub URL and live link at the top)
- [ ] Submit

## Cut in this order if behind

1. Landing page (ship it after submitting)
2. Trip CSV import (seed the data instead)
3. Client POD link
4. Operations head role

Never cut: the retake flow, the review screen, offline capture.
