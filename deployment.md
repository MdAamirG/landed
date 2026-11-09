# Deployment

- **Live app:** https://landed-lovat.vercel.app
- **Code:** https://github.com/MdAamirG/landed

## Demo logins

Both office accounts use the password `landed-demo`. They hold sample data only.

| Role | Email | What it can do |
| --- | --- | --- |
| Billing executive | `billing@example.com` | Review, Billing, Missing PODs: the whole core build |
| Operations head | `ops@example.com` | Missing PODs and resending driver links. Approving and exporting are refused |

The sign-in screen also has one button per role, so you don't have to type these.

Drivers have no login. Each trip has its own link, sent by SMS, and the SMS is mocked. To try the driver side:

- **On a phone:** scan the QR code on the sign-in screen, or open https://landed-lovat.vercel.app/demo. Pick one of the five scenarios, then send its sample photo or take your own. Both go through the real Gemini check.
- **From the office:** "Ask for retake" in Review and "Resend SMS link" in Missing PODs show a "Mock SMS sent" toast. Its "Open link" button opens the link the driver would have received.

The API sleeps after 15 minutes without traffic on Render's free tier. If the first page takes about a minute, that's Render waking up. See "Keep the API awake" below.

## Run it locally

You need Python 3.12, [uv](https://docs.astral.sh/uv/) (or plain `venv` and `pip`), Node 22 or newer, a Gemini API key and two Postgres databases. The steps use Neon, as production does: one branch for the app and a second branch for the tests, because the tests empty every table.

1. Copy the example environment file to `.env` at the repo root, and fill it in. The table at the end says what each variable is.

```bash
cp .env.example .env
```

- For local work, set `WEB_ORIGIN=http://localhost:5173`, `VITE_API_URL=http://localhost:8000` and `DEMO_MODE=true`.
- `SESSION_SECRET` and `DRIVER_LINK_SECRET` must each be at least 32 characters. This makes one:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

2. Install the API's packages.

```bash
cd api && uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements-dev.txt
```

3. Create the tables, then add the sample data. The seed adds the brief's three trips, the two demo logins, the five demo trips and about 200 backdated trips for the dashboard. It takes about a minute against Neon and is safe to run twice.

```bash
cd api && .venv/bin/alembic upgrade head
```

```bash
cd api && .venv/bin/python seed.py
```

4. Start the API. It reads `.env` from the repo root.

```bash
cd api && .venv/bin/uvicorn app.main:app --reload
```

5. In a second terminal, start the web app, then open http://localhost:5173. Vite forwards `/api` to `VITE_API_URL`, so the browser only talks to one origin, as it does on Vercel.

```bash
cd web && npm ci && npm run dev
```

6. Optional: print a driver link for any seeded trip. Only a hash is stored, so each run makes a new link.

```bash
cd api && .venv/bin/python make_driver_link.py TRP-66134
```

### Tests

The API tests run against the database in `DATABASE_URL_TEST`. They refuse to start if it's unset or has the same host as the app's database, because they migrate it and empty its tables. The whole suite makes network calls to Neon and takes a while, so run one file while working.

```bash
cd api && .venv/bin/pytest
```

```bash
cd api && .venv/bin/pytest tests/test_rules.py
```

```bash
cd web && npm run typecheck && npm test
```

The tests never call Gemini: they swap in a fake reader. The real model is measured separately, with paid calls, and the result is in `docs/accuracy.md`.

```bash
cd api && .venv/bin/python measure_accuracy.py --runs 3
```

## How it's deployed

The web app runs on Vercel, the API on Render's free tier in Singapore, and the database on Neon in `ap-southeast-1`. The browser only ever talks to Vercel: `vercel.json` forwards `/api/*` to Render, so the sign-in cookie stays first-party and CORS isn't needed.

## Set up the database

Run these from a laptop, with `.env` holding the Neon URLs. `DATABASE_URL` is the direct URL, because migrations shouldn't run through the pooler. Render's free tier has no shell, one-off jobs or pre-deploy step, so a migration can't run there.

```bash
cd api && .venv/bin/alembic upgrade head
```

```bash
cd api && .venv/bin/python seed.py
```

The seed adds the brief's trips, the five demo trips and the history. It's safe to run twice, and it leaves rows that already exist as they are. When a later commit adds a migration, run it before pushing that commit, so the new code never meets the old schema.

Reviewers' clicks change the sample trips. An approve takes TRP-66141 out of Review, a retake sends it to Missing PODs, and an export marks trips invoiced. Seeded times are set from the day of seeding, so they also age. To put everything back as the brief describes, with fresh times, empty the database and seed it again. This deletes every row in one transaction, so it refuses unless `DEMO_MODE` is `true`. It takes about a minute and a quarter against Neon. Run it close to when reviewers will look.

```bash
cd api && .venv/bin/python seed.py --fresh
```

## Deploy the API on Render

1. In Render, choose **New**, then **Blueprint**, and connect the repo. Render reads `render.yaml`.
2. When asked, paste `DATABASE_URL`, `DATABASE_URL_POOLED`, `GEMINI_API_KEY`, `SESSION_SECRET` and `DRIVER_LINK_SECRET` from your local `.env`. The two secrets must be the same everywhere, so don't generate new ones. Enter `pending` for `WEB_ORIGIN` until the web app has its URL. Set `DEMO_MODE` to `true` for a reviewer's build, or `false` to turn off the demo role buttons, the driver demo and the links shown after a mock SMS. `render.yaml` sets `GEMINI_MODEL`.
3. Check the service URL before deploying the web app. It's `https://landed-api-80b4.onrender.com`. Render chooses that address, so a recreated service may get a different one. If it changes, put the new URL in `vercel.json` and push, and use it for the uptime monitor below.

Each push that changes `api/` deploys again.

## Deploy the web app on Vercel

1. In Vercel, import the repo. Leave **Root Directory** as the repo root.
    - `vercel.json` and `.vercelignore` depend on that. A `web` root can't reach `design/tokens.css`, and the build needs it.
    - The repo root has no framework for Vercel to detect, so `vercel.json` sets `framework` to null and names the build commands itself.
2. Add no environment variables. The rewrite is in `vercel.json`, and `VITE_API_URL` only serves the local dev proxy.
3. Check that the build log lists no Python functions. `.vercelignore` keeps `api/` out, so Vercel doesn't try to run it.
4. Set `WEB_ORIGIN` on Render to the Vercel URL, `https://landed-lovat.vercel.app`.

Open `https://landed-lovat.vercel.app/status`. "API reachable" means the browser reached Render through the rewrite, and Render reached Neon.

## Keep the API awake

Render's free tier spins a service down after 15 minutes without traffic, and waking it takes about a minute. Set an uptime monitor to call this URL every 10 minutes:

```
https://landed-api-80b4.onrender.com/api/ping
```

Use `/api/ping`, not `/api/health`. The ping doesn't touch the database, so Neon can still suspend when idle. `/api/health` runs a query, which would use up most of Neon's free compute hours.

A month has at most 744 hours, which fits within Render's 750 free hours as long as this is the only free service running in the workspace.

## Environment variables

Names only. `.env.example` lists all of these except `PYTHON_VERSION`, which only Render's build uses.

| Name | Where | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | Render, local | Neon direct URL, for migrations |
| `DATABASE_URL_POOLED` | Render, local | Neon pooled URL, for the app |
| `GEMINI_API_KEY` | Render, local | Gemini vision |
| `GEMINI_MODEL` | Render, local | Gemini model name. Defaults to `gemini-3.5-flash-lite` |
| `SESSION_SECRET` | Render, local | Signs office sessions. At least 32 characters, or the API won't start |
| `DRIVER_LINK_SECRET` | Render, local | Protects driver links. At least 32 characters |
| `WEB_ORIGIN` | Render, local | The web app's URL. Any value not starting `http://` makes the session cookie Secure |
| `DEMO_MODE` | Render, local | Turns on the demo rules |
| `PYTHON_VERSION` | Render | Python version for the build, set in `render.yaml` |
| `VITE_API_URL` | Local | Where the Vite dev proxy sends `/api` |
| `DATABASE_URL_TEST` | Local | Neon test branch, direct URL, for `pytest` |
