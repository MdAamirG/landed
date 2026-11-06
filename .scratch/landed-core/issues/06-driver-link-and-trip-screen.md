# 06: Driver link and trip screen

**What to build:** A driver opens the link for one trip and sees that trip, with no install and no login. The link carries a token whose hash is stored, and it expires 72 hours after expected delivery. A finished trip shows "done", and an expired or revoked link tells the driver to call the office.

**Blocked by:** 01

**Status:** ready-for-agent

**Scheduled:** Saturday

**Spec stories:** 1 to 4, 17, 18, 74

- [x] The trip screen matches `Driver_Home.html`: trip code, number plate, route, LR, e-way bill and the one big button, which is wired up in ticket 07
- [x] Only a hash of the token is stored, and no response or audit event carries the token
- [x] A token opens one trip only. A bad, expired or revoked token is refused, proven by tests through the HTTP API
- [x] Consignee details don't appear in any driver response
- [x] A finished trip shows "done" with no camera button
- [x] An expired or revoked link shows the call-the-office message
- [x] The screen works at phone width with the driver design rules in `docs/design.md`

## Comments

- `api/app/driver_links.py` holds token creation, the keyed hash and the route dependency. Ticket 15's resend and ticket 16's demo reset call `create_link()`. Add new driver routes to `DRIVER_ROUTES` in `test_route_access.py`.
- The phone sends the token in an `Authorization` header, so it stays out of the API's request logs. It is still in the page URL, which Vercel's logs can see.
- No office screen creates links yet, so `api/make_driver_link.py` prints one for a trip code.
- The language switch and speaker button in `Driver_Home.html` belong to ticket 17, and the location and network row to tickets 10 and 11.
