# 13: Review: retake, dispute, pull back

**What to build:** The rest of the billing executive's decisions: ask for a retake, mark a POD disputed and resolve it, and pull a trip back from `verified` before export. Late photos show up here with a flag.

**Blocked by:** 08, 12

**Status:** ready-for-agent

**Scheduled:** Sunday

**Spec stories:** 45 to 50, 71

- [ ] Ask for a retake sends the driver a mock SMS and counts toward the cap of two
- [ ] Past the cap, the server refuses and the button is disabled
- [ ] Mark disputed works from `needs_review` and `verified`, and a disputed trip stays out of billing
- [ ] Resolving moves a disputed trip to `verified`
- [ ] A Disputed filter lists open disputes
- [ ] Pull back moves a `verified` trip to `needs_review`, and an `invoiced` trip can't be changed
- [ ] Late photos are flagged in Review
- [ ] Each action writes to `audit_events`, and tests run through the HTTP API
- [ ] Loading, empty and error states cover the Disputed filter
