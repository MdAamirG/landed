# 12: Review: read, correct, approve

**What to build:** A billing executive works through PODs that need a person. Each one shows the photo beside the editable AI fields, and the executive can correct a field and approve. Consignee contacts stay masked unless revealed, and each reveal is logged.

**Blocked by:** 05, 07

**Status:** ready-for-agent

**Scheduled:** Saturday

**Spec stories:** 38 to 44, 51 to 53, 71

- [ ] The queue lists `needs_review` trips, oldest first, with the reason
- [ ] The screen matches `Review.html`: photo, fields with confidence, trip checks and every reason code
- [ ] Each attempt's reading can be seen, and Review uses the highest-numbered checked attempt (spec assumption 2)
- [ ] An edit keeps `ai_value`, sets `final_value`, and writes who and when to `audit_events`
- [ ] Approve moves the trip to `verified` and sets `verified_at` and `verified_by`
- [ ] Approve is refused until all six fields are filled in (spec assumption 7)
- [ ] A stale `version` returns 409 and the screen reloads the trip
- [ ] Every response masks consignee name and phone and driver phone, and the one reveal endpoint writes an audit event
- [ ] Role checks cover these routes, and the operations head is refused on approve
- [ ] Loading, empty and error states follow `States.html`
