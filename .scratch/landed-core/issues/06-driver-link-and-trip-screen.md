# 06: Driver link and trip screen

**What to build:** A driver opens the link for one trip and sees that trip, with no install and no login. The link carries a token whose hash is stored, and it expires 72 hours after expected delivery. A finished trip shows "done", and an expired or revoked link tells the driver to call the office.

**Blocked by:** 01

**Status:** ready-for-agent

**Scheduled:** Saturday

**Spec stories:** 1 to 4, 17, 18, 74

- [ ] The trip screen matches `Driver_Home.html`: trip code, number plate, route, LR, e-way bill and the one big button, which is wired up in ticket 07
- [ ] Only a hash of the token is stored, and no response or audit event carries the token
- [ ] A token opens one trip only. A bad, expired or revoked token is refused, proven by tests through the HTTP API
- [ ] Consignee details don't appear in any driver response
- [ ] A finished trip shows "done" with no camera button
- [ ] An expired or revoked link shows the call-the-office message
- [ ] The screen works at phone width with the driver design rules in `docs/design.md`
