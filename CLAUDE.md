# Landed

A take-home build for a job application: a proof-of-delivery (POD) capture and billing app for a full-truckload transporter in Chhatrapati Sambhajinagar. A driver photographs the signed lorry receipt at the consignee's gate, a vision model checks it while the driver is still there, and billing invoices from verified PODs.

The candidate (Aamir) must explain every design choice in an interview. Prefer simple, readable code over clever code, and explain non-obvious choices in short comments.

## Read first

- `docs/brief.md`: the client brief and the assignment rules. Use only what it says; label every assumption.
- `docs/data-model.md`: the schema, the seven trip statuses, the AI decision rule, roles and edge cases. This is decided; follow it.
- `docs/spec.md`: the problem, user stories, test seams and the assumptions added to the data model.
- `docs/design.md` and `design/screens/*.html`: the approved screens and design rules.
- `docs/plan.md`: the build order and the cut list. Tick items off as they land.

## Stack

- API: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, pytest.
- Database: Postgres on Neon. Photos stored as `bytea` for the demo.
    - `.env` has two URLs. The app uses `DATABASE_URL_POOLED`; Alembic migrations use `DATABASE_URL` (direct), because migrations should not run through the pooler.
    - Driver: psycopg 3 (`psycopg[binary]`), sync SQLAlchemy. Rewrite the scheme `postgresql://` to `postgresql+psycopg://` in `config.py`, keep `sslmode` and `channel_binding` as they are, and pass `prepare_threshold=None` in `connect_args` so the pooler never sees prepared statements. Don't use asyncpg; it rejects those URL parameters.
- AI: Gemini vision through the `google-genai` SDK, model from `GEMINI_MODEL` (default `gemini-3.5-flash-lite`).
    - Use structured output (a response JSON schema from the Pydantic model) and validate the reply with Pydantic again.
    - Leave thinking at its default minimal level. Don't set `temperature`, `top_p` or `top_k`: Google's notes for this model family say to remove them.
    - If stamps or handwritten remarks are misread, raise the image resolution setting before switching to a bigger model.
- Web: React + Vite + TypeScript, one app with two areas: the driver PWA (mobile-first, works offline) and the office screens. Plain CSS using `design/tokens.css`; no UI kit.
- Hosting: Render for the API, Vercel for the web app.

## Layout

```
api/
  app/
    main.py config.py db.py models.py schemas.py
    auth.py       # passwords, the session cookie, require_role()
    driver_links.py # driver tokens: created, hashed, checked on each driver route
    rules.py      # decide(): the AI decision rule, pure, no I/O
    status.py     # move_trip(): the only code that changes pod_status
    ai.py         # Gemini call, timeout, schema validation
    intake.py     # stores an attempt, then the background check
    review.py     # field edits, approve, reveal, each with its audit event
    masking.py    # how names and phones appear in responses
    tally.py      # Tally XML export
    routers/      # health, auth, driver, review, billing, dashboard, trips
  tests/
  seed.py
  alembic/
web/
  src/driver/ src/office/ src/lib/
  public/manifest.webmanifest
design/  docs/  samples/pods/
```

## Rules

- Statuses move only through the state machine in `docs/data-model.md`. Write every status change and field edit to `audit_events`.
- The AI never sends an invoice. Shortage or damage remarks, low confidence and AI failures always go to `needs_review`. Retakes cap at two.
- Money in paise as integers; times in UTC; show rupees and India time.
- Mask consignee name and phone in every response; reveal only through the logged endpoint.
- Validate every input with Pydantic. Check the role on every office route and the driver token on every driver route.
- Secrets only in environment variables. Keep `.env.example` current with names, never values. Never commit `.env`.
- No real personal data anywhere. Seed data uses sample names and numbers.
- Write tests for `rules.decide()`, upload idempotency, role checks and the Tally export before calling a feature done.
- Commit small and often with clear messages. The reviewers read the history.

## Commands

Fill these in once the project exists:

- API: `cd api && uvicorn app.main:app --reload`
- Tests: `cd api && pytest`
- Web: `cd web && npm run dev`
- Web tests: `cd web && npm test`
- Migrate: `cd api && alembic upgrade head`
- Seed: `cd api && python seed.py`
- Deploy: see `deployment.md`

## Agent skills

### Issue tracker

Issues live as local markdown files under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default labels, recorded as `Status:` lines in ticket files. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
