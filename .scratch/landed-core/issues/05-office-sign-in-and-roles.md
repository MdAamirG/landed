# 05: Office sign-in and roles

**What to build:** A billing executive or operations head signs in with email and password, reaches the office area and signs out. The server checks the role on every office route, and the checks are tested on every route that exists so far. Later office tickets add their routes to the same test.

**Blocked by:** 01

**Status:** ready-for-agent

**Scheduled:** Saturday

**Spec stories:** 72, 73, 84

- [ ] The sign-in screen matches `Main.html`, with loading and error states
- [ ] Passwords are stored hashed, and a session is a short-lived token in an http-only cookie
- [ ] The top bar shows the four destinations, the signed-in role and sign out
- [ ] Not signed in returns 401 and the wrong role returns 403, proven by a test through the HTTP API
- [ ] The demo role buttons appear only in `DEMO_MODE` (spec assumption 16)
