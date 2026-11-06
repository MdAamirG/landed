# 08: Retakes, late photos and stuck attempts

**What to build:** When a photo can be fixed, the driver sees why and takes another, up to two retakes. Photos that arrive when a trip isn't waiting for one are kept without moving the status, and an attempt stuck in `checking` reaches a person.

**Blocked by:** 07

**Status:** ready-for-agent

**Scheduled:** Saturday

**Spec stories:** 14, 15, 26, 36, 37

- [x] The retake screen matches `Retake.html`: the reason, the six field checks and "Retake 1 of 2"
- [x] A third failed attempt goes to `needs_review` with `retake_cap_reached`
- [x] Every move to `retake_requested` sends a mock SMS and writes `sms_sent` without the token (spec assumption 4)
- [x] A retake renews every unrevoked link on the trip to 72 hours from then (spec assumption 5)
- [x] A photo arriving when the trip isn't `awaiting_pod` or `retake_requested` is a late photo: numbered 4 and up, stored, flagged and not sent to Gemini, with the status unchanged
- [x] An attempt in `checking` for over 60 seconds counts as `ai_unavailable`. The sweep runs on driver polls and on office queue and dashboard loads (spec assumption 3)
- [x] A photo dated after it arrived has `captured_at` replaced by `received_at` and is flagged
- [x] Tests run through the HTTP API with the AI reader faked

## Comments

- The retake effects are in `move_trip()`, so ticket 13's office retake gets the count, the link renewal and the mock SMS without extra code. The mock SMS can't include the link, because only its hash is stored. A real SMS would need a new token, as a resend does.
- `sweep_stuck_attempts()` runs on driver polls for that trip. Tickets 12 and 15 call it with no trip ID on queue and dashboard loads.
- A late photo has `ai_status` set to `skipped` and an attempt number of 4 or more, which is how Review can flag it. A wrong clock is in the `attempt_received` audit event as `wrong_clock`, holding the phone's time.
