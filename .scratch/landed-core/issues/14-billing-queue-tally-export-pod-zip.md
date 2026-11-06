# 14: Billing queue, Tally export, POD ZIP

**What to build:** A billing executive sees verified trips by client and cycle, selects some and exports them to Tally as draft vouchers, then downloads the POD photos as a ZIP. Landed never issues an invoice itself.

**Blocked by:** 12

**Status:** ready-for-agent

**Scheduled:** Sunday

**Spec stories:** 54 to 63, 71

- [ ] The screen matches `Billing.html`: trips by client, cycle switch, selection total, and the count of trips still in review
- [ ] A trip's cycle comes from its delivery date in India time, and delivery time is the first attempt's `captured_at` (spec assumption 1)
- [ ] The cycle switch offers any cycle holding verified trips (spec assumption 12)
- [ ] An export makes one draft Sales voucher per client, with a line per trip carrying the LR and e-way bill numbers
- [ ] A shortage trip bills full freight, and its remark goes in the voucher narration
- [ ] Billing reads `final_value`, and the ZIP uses the same attempt's photo (spec assumption 2)
- [ ] Exported trips move to `invoiced` and can't be changed
- [ ] An export is all or nothing, and it's refused and names the trips if any has stopped being `verified` (spec assumption 11)
- [ ] Earlier exports are listed, and a re-download returns the same stored XML
- [ ] Tests parse the XML and check grouping, lines, narration and totals
- [ ] Role checks cover these routes, and the operations head is refused on export
- [ ] Loading, empty and error states are in place
