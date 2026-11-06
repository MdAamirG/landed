# Deployment

The web app runs on Vercel, the API on Render's free tier in Singapore, and the database on Neon in `ap-southeast-1`. The browser only ever talks to Vercel: `vercel.json` forwards `/api/*` to Render, so the sign-in cookie stays first-party and CORS isn't needed.

## Set up the database

Run these from a laptop, with `.env` holding the Neon URLs. `DATABASE_URL` is the direct URL, because migrations shouldn't run through the pooler. Render's free tier has no shell, one-off jobs or pre-deploy step, so a migration can't run there.

```bash
cd api && .venv/bin/alembic upgrade head
```

```bash
cd api && .venv/bin/python seed.py
```

The seed is safe to run twice. When a later commit adds a migration, run it before pushing that commit, so the new code never meets the old schema.

## Deploy the API on Render

1. In Render, choose **New**, then **Blueprint**, and connect the repo. Render reads `render.yaml`.
2. When asked, paste `DATABASE_URL`, `DATABASE_URL_POOLED`, `GEMINI_API_KEY`, `SESSION_SECRET` and `DRIVER_LINK_SECRET` from your local `.env`. The two secrets must be the same everywhere, so don't generate new ones. Enter `pending` for `WEB_ORIGIN` and `false` for `DEMO_MODE`: nothing reads either yet. `render.yaml` sets `GEMINI_MODEL`.
3. Check the service URL before deploying the web app. It's `https://landed-api-80b4.onrender.com`. Render chooses that address, so a recreated service may get a different one. If it changes, put the new URL in `vercel.json` and push, and use it for the uptime monitor below.

Each push that changes `api/` deploys again.

## Deploy the web app on Vercel

1. In Vercel, import the repo. Leave **Root Directory** as the repo root.
    - `vercel.json` and `.vercelignore` depend on that. A `web` root can't reach `design/tokens.css`, and the build needs it.
    - The repo root has no framework for Vercel to detect, so `vercel.json` sets `framework` to null and names the build commands itself.
2. Add no environment variables. The rewrite is in `vercel.json`, and `VITE_API_URL` only serves the local dev proxy.
3. Check that the build log lists no Python functions. `.vercelignore` keeps `api/` out, so Vercel doesn't try to run it.
4. Set `WEB_ORIGIN` on Render to the Vercel URL, `https://landed-lovat.vercel.app`.

Open `https://landed-lovat.vercel.app`. "API reachable" means the browser reached Render through the rewrite, and Render reached Neon.

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
| `GEMINI_MODEL` | Render, local | Gemini model name |
| `SESSION_SECRET` | Render, local | Signs office sessions |
| `DRIVER_LINK_SECRET` | Render, local | Protects driver links |
| `WEB_ORIGIN` | Render, local | The web app's URL |
| `DEMO_MODE` | Render, local | Turns on the demo rules |
| `PYTHON_VERSION` | Render | Python version for the build, set in `render.yaml` |
| `VITE_API_URL` | Local | Where the Vite dev proxy sends `/api` |
| `DATABASE_URL_TEST` | Local | Neon test branch, direct URL, for `pytest` |
