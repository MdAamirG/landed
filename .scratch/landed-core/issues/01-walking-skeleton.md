# 01: Walking skeleton and test harness

**What to build:** The API starts, reports its health and has the twelve-table schema in place through a migration. The brief's three trips are seeded, and the web app shows that it can reach the API. `pytest` runs against the Neon test branch, so every later ticket has a harness to build on.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

**Scheduled:** Friday night, first

- [x] Config reads from the environment. The app uses `DATABASE_URL_POOLED` and Alembic uses `DATABASE_URL`, with the driver settings in `CLAUDE.md`
- [x] A health route reports that the API is up and can reach the database
- [x] One Alembic migration creates the twelve tables in `docs/data-model.md`, with their indexes and unique constraints
- [x] The seed creates the brief's 3 trips, 3 clients, 3 branches, their vehicles and drivers, and demo office users, using sample names and numbers only
- [x] The web app loads with `design/tokens.css` and shows whether the API is reachable
- [x] Each `pytest` run applies the migrations to the test branch, then empties the tables
- [x] The suite refuses to run if `DATABASE_URL_TEST` is unset, or if its host matches the host in `DATABASE_URL` or `DATABASE_URL_POOLED`. A test proves both refusals
