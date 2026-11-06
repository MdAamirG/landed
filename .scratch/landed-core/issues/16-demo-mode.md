# 16: Demo mode

**What to build:** With `DEMO_MODE` on, an assignment reviewer picks one of five scenarios, runs it through the real Gemini check and resets it to try again. Mock SMS sends show a toast with an "Open link" button. Seeded history is never touched.

**Blocked by:** 03, 08, 12

**Status:** ready-for-agent

**Scheduled:** Sunday

**Spec stories:** 79 to 84

- [ ] Five demo trips exist, one per scenario, each with an LR number matching its sample photo
- [ ] "Open the driver demo" leads to the scenario picker
- [ ] Picking a scenario resets that trip and creates a fresh link
- [ ] The reviewer can use the sample photo or take a real one
- [ ] A reset touches only `is_demo` rows, and a test proves seeded history is unchanged
- [ ] A reset adds a `demo_reset` audit event, and the upload count carries on
- [ ] Demo trips stay out of the dashboard figures but appear in Review and Billing
- [ ] The API returns the link once, and office screens show "Mock SMS sent" with "Open link"
- [ ] Nothing here runs when `DEMO_MODE` is off
