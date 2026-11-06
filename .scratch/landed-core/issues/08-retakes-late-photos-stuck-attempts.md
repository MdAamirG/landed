# 08: Retakes, late photos and stuck attempts

**What to build:** When a photo can be fixed, the driver sees why and takes another, up to two retakes. Photos that arrive when a trip isn't waiting for one are kept without moving the status, and an attempt stuck in `checking` reaches a person.

**Blocked by:** 07

**Status:** ready-for-agent

**Scheduled:** Saturday

**Spec stories:** 14, 15, 26, 36, 37

- [ ] The retake screen matches `Retake.html`: the reason, the six field checks and "Retake 1 of 2"
- [ ] A third failed attempt goes to `needs_review` with `retake_cap_reached`
- [ ] Every move to `retake_requested` sends a mock SMS and writes `sms_sent` without the token (spec assumption 4)
- [ ] A retake renews every unrevoked link on the trip to 72 hours from then (spec assumption 5)
- [ ] A photo arriving when the trip isn't `awaiting_pod` or `retake_requested` is a late photo: numbered 4 and up, stored, flagged and not sent to Gemini, with the status unchanged
- [ ] An attempt in `checking` for over 60 seconds counts as `ai_unavailable`. The sweep runs on driver polls and on office queue and dashboard loads (spec assumption 3)
- [ ] A photo dated after it arrived has `captured_at` replaced by `received_at` and is flagged
- [ ] Tests run through the HTTP API with the AI reader faked
