# 07: Photo to first result

**What to build:** A driver with signal photographs the POD and gets a result while still at the gate. The upload saves the attempt and returns at once, the real Gemini check runs in the background, the decision rule sets the status, and the phone polls until it can show the result.

**Blocked by:** 03, 04, 06

**Status:** ready-for-agent

**Scheduled:** Saturday

**Spec stories:** 5, 6, 11, 12, 13, 16, 24, 25, 27, 34, 35, 75

- [x] The AI reader has one small interface: image bytes in, a validated reading or a failure out. It uses structured output, validates again with Pydantic, and has a 20-second limit
- [x] Settings follow `CLAUDE.md`: model from `GEMINI_MODEL`, and no `temperature`, `top_p` or `top_k`
- [x] The prompt asks for empty remark text when the paper has no remark, because `decide()` sends any remark text to a person, even "nil"
- [x] A failure, a timeout or a reply that doesn't fit the schema counts as `ai_unavailable`, and the photo is kept
- [x] A repeated attempt ID stores nothing new, returns the first result and doesn't count toward the rate limit
- [x] Intake refuses anything over 300 KB or that isn't an image by its content, and limits uploads to 10 an hour per trip, counted from `audit_events`
- [x] Intake locks the trip row while it assigns `attempt_no` (spec assumption 13)
- [x] The background task applies its result only if the trip is still in `checking` for that attempt
- [x] AI values go to `pod_fields`, and each attempt keeps its raw reply, latency and model
- [x] A missing location is accepted and marked "no location"
- [x] The phone polls every 2 seconds and shows the green done screen, "Sent to office", or "You can go, we'll SMS if needed" after 30 seconds
- [x] Tests run through the HTTP API with the AI reader faked, including a repeated attempt ID

## Comments

- Checked against the real model with the five sample photos: all five gave the expected reading, in about two seconds each.
- `move_trip()` now adds to `retakes_used` on every move to `retake_requested`, so an office retake (ticket 13) counts as well.
- The upload sends the camera file as it is until ticket 10 adds compression, so a real phone photo gets a 413 until then.
- A photo for a trip that isn't waiting for one gets a 409 until ticket 08 stores it as a late photo.
