# 15: History seed and missing-POD dashboard

**What to build:** About 200 backdated trips give the dashboard real data to compute. Both office roles see trips with no usable POD, the three figures against their targets and POD-to-invoice days by branch, and they can resend a driver link from any missing-POD row. This doesn't depend on ticket 14, because the seed writes `invoiced_at` directly.

**Blocked by:** 05, 06

**Status:** ready-for-agent

**Scheduled:** Sunday

**Spec stories:** 64 to 68, 70, 71, 79

- [ ] The seed adds about 200 backdated trips sharing a few sample images, with sample data only
- [ ] The screen matches `Dashboard.html`, with the changes in `docs/plan.md`
- [ ] Figures are computed from the data, labelled as sample data, and exclude demo trips
- [ ] The missing-POD list holds trips past expected delivery in `awaiting_pod` or `retake_requested`, with trips over 24 hours marked (spec assumption 8)
- [ ] A trip with no POD counts as a miss on the 24-hour figure only once its expected delivery plus 24 hours has passed, so trips still on the road don't count (spec assumption 9)
- [ ] Lost PODs use the same two statuses, 20 days after expected delivery (spec assumption 10)
- [ ] POD-to-invoice days show the median by branch against the 4-day target
- [ ] Every missing-POD row offers "Resend SMS link". A resend creates a new token, and the old link stays valid until it expires (spec assumption 5)
- [ ] Both office roles can open the dashboard, and role checks cover these routes
- [ ] Loading, empty and error states are in place
