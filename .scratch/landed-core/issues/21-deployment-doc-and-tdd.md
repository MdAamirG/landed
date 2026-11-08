# 21: deployment.md and TDD

**What to build:** The two submission documents the brief asks for, ready for Aamir to check and submit. The real-phone test, the choice of Render plan and the submission itself are Aamir's and aren't part of this ticket.

**Blocked by:** 02, 09, 11, 13, 14, 15, 16

**Status:** done

**Scheduled:** Sunday, last

- [x] `deployment.md` covers running locally step by step, how it's deployed, the environment variable names and the demo logins
- [x] The TDD has the GitHub URL and live link at the top
- [x] The TDD covers the architecture and why, the data model, the main flows, how the AI part works, the key screens and why, and what was cut and what comes next
- [x] Every assumption is labelled, from `docs/data-model.md` and the 16 in `docs/spec.md`
- [x] The limits in `docs/spec.md` are stated, after checking the Gemini terms for this key's tier
- [x] The accuracy numbers from ticket 09 are included

## Comments

- From ticket 09: the numbers are in `docs/accuracy.md`. Say they're a first estimate on synthetic sheets. Don't quote "100%" alone: it's 324 of 324 on readable sheets, and the blurred sheet is where the model invented values at high confidence. The point worth making is that the fixed checks against the trip protect billing, not the model's confidence.
- Done on 8 Nov 2026. The TDD is `docs/tdd.md`; `uv run docs/build_submission.py` prints it to PDF and zips it with `deployment.md` into `submission/`, which git ignores. The spec now has 34 assumptions, not 16, so the TDD labels all of them (S1 to S34) plus the data model's (A1 to A13).
- The Gemini key is on the free tier (Aamir, 8 Nov 2026). Google's terms, effective 23 March 2026, let unpaid-tier content be used to improve products and read by human reviewers, and say not to send personal data. The TDD says that's fine for synthetic sheets and that production needs a paid project.
- Still Aamir's: the real-phone test, the production seed, the Render plan and submitting. If the phone test happens, update the "Not yet tested on a real Android phone" limit in the TDD and rebuild the PDF.
