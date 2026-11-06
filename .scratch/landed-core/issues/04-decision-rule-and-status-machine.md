# 04: Decision rule and status machine

**What to build:** The two pieces of logic everything else relies on. The decision rule turns an AI reading into a status, a reason and every matched reason code. The status machine is the only way to move a trip's status, and it writes each move to `audit_events`. This ticket isn't a vertical slice: it's pure logic, built first so ticket 07 fits in one context window.

**Blocked by:** 01

**Status:** ready-for-agent

**Scheduled:** Friday night, after 01

**Spec stories:** 28 to 35, 37

- [ ] `decide()` applies the nine checks in the order given in `docs/data-model.md`, and has no I/O
- [ ] The first match sets the status and reason, and `reason_codes` keeps every check that matched
- [ ] A table of cases covers every check, a remark at high confidence, a missing location versus a far one, confidence just below and exactly at 0.80, and the retake cap
- [ ] The status machine allows only the moves in the seven-status diagram and refuses the rest
- [ ] Each move writes an audit event in the same transaction, with the actor and the from and to statuses
- [ ] Pulling a trip back from `verified` clears `verified_at` and `verified_by`
