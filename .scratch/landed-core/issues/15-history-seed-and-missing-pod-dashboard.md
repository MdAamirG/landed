# 15: History seed and missing-POD dashboard

**What to build:** About 200 backdated trips give the dashboard real data to compute. Both office roles see trips with no usable POD, the three figures against their targets and POD-to-invoice days by branch, and they can resend a driver link from any missing-POD row. This doesn't depend on ticket 14, because the seed writes `invoiced_at` directly.

**Blocked by:** 03, 05, 06

**Status:** ready-for-agent

**Scheduled:** Sunday

**Spec stories:** 64 to 68, 70, 71, 79

- [x] The seed adds about 200 backdated trips sharing a few sample images, with sample data only
- [x] The brief's three seeded trips get photo attempts and `pod_fields` that fit their statuses, using the sample images, so TRP-66141 can be reviewed and approved. TRP-66120 is `verified` and TRP-66134 has one retake used, so each needs the attempts to match
- [x] Ticket 16's demo trips can reuse the code that adds these attempts
- [x] The screen matches `Dashboard.html`, with the changes in `docs/plan.md`
- [x] Figures are computed from the data, labelled as sample data, and exclude demo trips
- [x] The missing-POD list holds trips past expected delivery in `awaiting_pod` or `retake_requested`, with trips over 24 hours marked (spec assumption 8)
- [x] A trip with no POD counts as a miss on the 24-hour figure only once its expected delivery plus 24 hours has passed, so trips still on the road don't count (spec assumption 9)
- [x] Lost PODs use the same two statuses, 20 days after expected delivery (spec assumption 10)
- [x] POD-to-invoice days show the median by branch against the 4-day target
- [x] Every missing-POD row offers "Resend SMS link". A resend creates a new token, and the old link stays valid until it expires (spec assumption 5)
- [x] Both office roles can open the dashboard, and role checks cover these routes
- [x] Loading, empty and error states are in place

## Comments

- The figures cover 90 days, not the 30 in `Dashboard.html` (spec assumption 26). The seed spans about 30 days, so a 30-day window would empty out while reviewers are still looking.
- `create_link()` now counts 72 hours from now when that's later, because a resend on a long-overdue trip would otherwise make a link that had already expired (spec assumption 28). `make_driver_link.py` gets the same fix.
- `samples/pods/seeded-sheets.json` adds five sheets, so TRP-66120, 66134, 66141, 66137 and 66128 show their own LR numbers in Review. The five demo photos were not changed: re-running `photograph_pods.py` rebuilds them, so restore them with git if only the seeded sheets are wanted.
- "Mock SMS sent to" shows under the button for now. Ticket 16 adds the toast and "Open link" in `DEMO_MODE`.
- The "Client POD link" block from `Dashboard.html` waits for ticket 19.
- The top bar counts reload when you move between screens, so a count can lag behind an action until then.
