# 18: Trip CSV import

**What to build:** A billing executive uploads the daily trip file and sees a check for each row. Bad rows are rejected with their reason, and the rest still import. This is second on the cut list.

**Blocked by:** 05, 06

**Status:** ready-for-agent

**Scheduled:** Only if time remains

**Spec stories:** 78

- [ ] The screen matches `Trips.html`, with the "Driver gets" column replaced by own or hired
- [ ] A row with no e-way bill, or that repeats an LR number, is rejected with its reason
- [ ] A row naming an unknown client or branch is rejected, and a new vehicle or driver is created on first sight (spec assumption 15)
- [ ] Each imported trip gets a driver link and a mock SMS (spec assumption 15)
- [ ] `import_batches` records the file, the counts and the errors
- [ ] Role checks cover these routes, and loading, empty and error states are in place
