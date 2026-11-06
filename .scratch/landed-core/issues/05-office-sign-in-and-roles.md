# 05: Office sign-in and roles

**What to build:** A billing executive or operations head signs in with email and password, reaches the office area and signs out. The server checks the role on every office route, and the checks are tested on every route that exists so far. Later office tickets add their routes to the same test.

**Blocked by:** 01

**Status:** ready-for-agent

**Scheduled:** Saturday

**Spec stories:** 72, 73, 84

- [x] The sign-in screen matches `Main.html`, with loading and error states
- [x] Passwords are stored hashed, and a session is a short-lived token in an http-only cookie
- [x] The top bar shows the four destinations, the signed-in role and sign out
- [x] Not signed in returns 401 and the wrong role returns 403, proven by a test through the HTTP API
- [x] The demo role buttons appear only in `DEMO_MODE` (spec assumption 16)

## Comments

- The role check test is `api/tests/test_route_access.py`. It fails if any API route is missing from its lists, so a later ticket has to state who can use a new route. Add office routes to `OFFICE_ROUTES`.
- The operations head's top bar shows only Missing PODs, because the data model gives that role none of the other three screens. The billing executive gets all four. A typed URL for a screen outside the role shows a "can't open this page" notice.
- The walking skeleton's health screen moved to `/status`, because `/` now leads to the office.
- `Main.html`'s QR and "Open the driver demo" block is left for ticket 16, because the scenario picker it links to doesn't exist yet.
