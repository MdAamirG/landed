# 13: Review: retake, dispute, pull back

**What to build:** The rest of the billing executive's decisions: ask for a retake, mark a POD disputed and resolve it, and pull a trip back from `verified` before export. Late photos show up here with a flag.

**Blocked by:** 08, 12

**Status:** ready-for-agent

**Scheduled:** Sunday

**Spec stories:** 45 to 50, 71

- [x] Ask for a retake sends the driver a mock SMS and counts toward the cap of two
- [x] Past the cap, the server refuses and the button is disabled
- [x] Mark disputed works from `needs_review` and `verified`, and a disputed trip stays out of billing
- [x] Resolving moves a disputed trip to `verified`
- [x] A Disputed filter lists open disputes
- [x] Pull back moves a `verified` trip to `needs_review`, and an `invoiced` trip can't be changed
- [x] Late photos are flagged in Review
- [x] Each action writes to `audit_events`, and tests run through the HTTP API
- [x] Loading, empty and error states cover the Disputed filter

## Comments

- A Verified filter was added beyond the ticket, because a trip can only be pulled back if an executive can reach it (spec assumption 19).
- Resolving a dispute uses Approve, so the six-field check applies either way. A dispute has no second route out, and the button reads "Resolve and approve" (spec assumption 20).
- A seeded disputed trip has no photo, so "Resolve and approve" stays disabled on it until ticket 15's seeding gives it a real attempt.
- A trip the rule passed or a person pulled back has no reason code, so its row shows no reason tag.
- Checked in the browser against the test branch: both filters, pull back, mark disputed, retake, the disabled button past the cap, and the empty and error states.
