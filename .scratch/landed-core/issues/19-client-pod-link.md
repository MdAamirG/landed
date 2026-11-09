# 19: Client POD link

**What to build:** An office user makes a read-only link that lets a client view its PODs for 7 days. This is third on the cut list.

**Blocked by:** 15

**Status:** done

**Scheduled:** Only if time remains

**Spec stories:** 77

- [x] The link is signed and stateless, expires after 7 days and adds no table (spec assumptions 14 and 49)
- [x] Each link made is logged
- [x] It shows only that client's PODs, read-only, with consignee details masked (spec assumption 48)
- [x] An expired or tampered link is refused, proven by tests through the HTTP API
- [x] Loading, empty and error states are in place
