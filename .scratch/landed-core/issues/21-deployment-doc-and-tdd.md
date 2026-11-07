# 21: deployment.md and TDD

**What to build:** The two submission documents the brief asks for, ready for Aamir to check and submit. The real-phone test, the choice of Render plan and the submission itself are Aamir's and aren't part of this ticket.

**Blocked by:** 02, 09, 11, 13, 14, 15, 16

**Status:** ready-for-agent

**Scheduled:** Sunday, last

- [ ] `deployment.md` covers running locally step by step, how it's deployed, the environment variable names and the demo logins
- [ ] The TDD has the GitHub URL and live link at the top
- [ ] The TDD covers the architecture and why, the data model, the main flows, how the AI part works, the key screens and why, and what was cut and what comes next
- [ ] Every assumption is labelled, from `docs/data-model.md` and the 16 in `docs/spec.md`
- [ ] The limits in `docs/spec.md` are stated, after checking the Gemini terms for this key's tier
- [ ] The accuracy numbers from ticket 09 are included

## Comments

- From ticket 09: the numbers are in `docs/accuracy.md`. Say they're a first estimate on synthetic sheets. Don't quote "100%" alone: it's 324 of 324 on readable sheets, and the blurred sheet is where the model invented values at high confidence. The point worth making is that the fixed checks against the trip protect billing, not the model's confidence.
