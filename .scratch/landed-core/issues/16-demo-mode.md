# 16: Demo mode

**What to build:** With `DEMO_MODE` on, an assignment reviewer picks one of five scenarios, runs it through the real Gemini check and resets it to try again. Mock SMS sends show a toast with an "Open link" button. Seeded history is never touched.

**Blocked by:** 03, 08, 12, 15

**Status:** ready-for-agent

**Scheduled:** Sunday

**Spec stories:** 79 to 84

- [ ] Five demo trips exist, one per scenario, each with an LR number matching its sample photo. They use ticket 15's code for seeding photo attempts where a scenario needs one
- [ ] "Open the driver demo" leads to the scenario picker
- [ ] Picking a scenario resets that trip through `reset_demo_trip()`, removes its attempts, fields and links, and creates a fresh link
- [ ] The reviewer can use the sample photo or take a real one
- [ ] A reset touches only `is_demo` rows, and a test proves seeded history is unchanged
- [ ] A reset adds a `demo_reset` audit event, and the upload count carries on
- [ ] Demo trips stay out of the dashboard figures but appear in Review and Billing
- [ ] The API returns the link once, and office screens show "Mock SMS sent" with "Open link"
- [ ] Nothing here runs when `DEMO_MODE` is off

## Comments

- From ticket 03: `samples/pods/scenarios.json` holds each demo trip's details and LR number. The sample sheets are dated 6 Nov 2026, and check 5 compares that with the capture date. When a reviewer uses a sample photo, send the scenario's `delivery_date` as `captured_at`. Otherwise the clean sheet goes to review with `date_mismatch` instead of verifying. A reviewer's own photo keeps its real capture time.
- From ticket 05: the sign-in screen doesn't have `Main.html`'s QR and "Open the driver demo" block yet. Add it here, shown only in `DEMO_MODE`, in `web/src/office/SignIn.tsx` below the demo role buttons.
