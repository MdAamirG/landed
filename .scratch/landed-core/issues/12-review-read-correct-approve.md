# 12: Review: read, correct, approve

**What to build:** A billing executive works through PODs that need a person. Each one shows the photo beside the editable AI fields, and the executive can correct a field and approve. Consignee contacts stay masked unless revealed, and each reveal is logged.

**Blocked by:** 05, 07

**Status:** ready-for-agent

**Scheduled:** Saturday

**Spec stories:** 38 to 44, 51 to 53, 71

- [x] The queue lists `needs_review` trips, oldest first, with the reason
- [x] The screen matches `Review.html`: photo, fields with confidence, trip checks and every reason code
- [x] Each attempt's reading can be seen, and Review uses the highest-numbered checked attempt (spec assumption 2)
- [x] An edit keeps `ai_value`, sets `final_value`, and writes who and when to `audit_events`
- [x] Approve moves the trip to `verified` and sets `verified_at` and `verified_by`
- [x] Approve is refused until all six fields are filled in (spec assumption 7)
- [x] A stale `version` returns 409 and the screen reloads the trip
- [x] Every response masks consignee name and phone and driver phone, and the one reveal endpoint writes an audit event
- [x] Role checks cover these routes, and the operations head is refused on approve
- [x] Loading, empty and error states follow `States.html`

## Comments

- Changes on one trip run one after another, each with the version the last one returned. Clicking Approve right after typing saves the field on blur first, and without this Approve hit a false conflict. A real conflict from another person still gets the 409 and a reload.
- `Review.html` merges the stamp and date into one input. They are separate here, because they are separate fields with separate confidences.
- An AI failure's blank fields fill in through the same controls. Saving is on blur, or on change for a select.
- The seeded `TRP-66141` is in `needs_review` with no attempt, so Review shows "No photo has arrived" and refuses approval. Ticket 15's seeding of photo attempts gives it a real photo.
- The top bar's counts from the design aren't in yet. They need the billing and missing-POD figures, so they fit ticket 15.
