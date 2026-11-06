# 14: Billing queue, Tally export, POD ZIP

**What to build:** A billing executive sees verified trips by client and cycle, selects some and exports them to Tally as draft vouchers, then downloads the POD photos as a ZIP. Landed never issues an invoice itself.

**Blocked by:** 12

**Status:** ready-for-agent

**Scheduled:** Sunday

**Spec stories:** 54 to 63, 71

- [x] The screen matches `Billing.html`: trips by client, cycle switch, selection total, and the count of trips still in review
- [x] A trip's cycle comes from its delivery date in India time, and delivery time is the first attempt's `captured_at` (spec assumption 1)
- [x] The cycle switch offers any cycle holding verified trips (spec assumption 12)
- [x] An export makes one draft Sales voucher per client, with a line per trip carrying the LR and e-way bill numbers
- [x] A shortage trip bills full freight, and its remark goes in the voucher narration
- [x] Billing reads `final_value`, and the ZIP uses the same attempt's photo (spec assumption 2)
- [x] Exported trips move to `invoiced` and can't be changed
- [x] An export is all or nothing, and it's refused and names the trips if any has stopped being `verified` (spec assumption 11)
- [x] Earlier exports are listed, and a re-download returns the same stored XML
- [x] Tests parse the XML and check grouping, lines, narration and totals
- [x] Role checks cover these routes, and the operations head is refused on export
- [x] Loading, empty and error states are in place

## Comments

- The export time on "Earlier exports" comes from the batch's trips, which share one `invoiced_at`. `export_batches` has no time of its own, and this avoids a schema change.
- A batch whose demo trips were all reset drops out of "Earlier exports", because it has no trips left to date it. Its row and XML stay.
- "Download POD photos" isn't in the selection panel as in `Billing.html`. A ZIP belongs to an export, so it appears after the export and on each earlier one.
- Selection starts empty, unlike the design's sample. An export can't be undone, so each trip should be a choice.
- A trip with no attempt can't be dated, so it stays out of billing. That only applies to seeded rows until ticket 15 gives them photos, so until then seeded verified trips don't show here.
- Every remark goes in the narration, not only a shortage, so a note about damage isn't lost.
- The XML has not been imported into a real Tally. The structure follows Tally's voucher import format; the TDD should say this.
- Checked in the browser against the test branch: grouping, cycle switch, totals, export, both downloads, byte-identical re-download, the conflict message, and the empty, error and phone-width states.
