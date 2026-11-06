# 03: Sample POD images

**What to build:** A rendered LR template and the five scenarios, so the build isn't blocked while real photos are made: clean, blurry, no stamp, "short by 6 cartons" and wrong LR number. Printed and photographed versions follow, because real photos are the ones used to tune the threshold.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent, except the part marked ready-for-human below

**Scheduled:** Friday night, after 01 and 04

## ready-for-agent

- [x] An LR template renders with sample names and numbers only
- [x] The five scenarios are in `samples/pods/`, each with its LR number recorded so the demo trips in ticket 16 can match it
- [x] Each scenario is under 300 KB
- [x] The template prints cleanly on A4, ready for the human part below

## ready-for-human

These are Aamir's steps, due by Saturday midday. Ticket 07 needs only the rendered images. Ticket 09's final numbers need these photos.

- [x] Print the five scenarios, then stamp, sign and write on them as each one requires
- [x] Photograph them on a phone and add the photos to `samples/pods/`

Replaced on 7 Nov 2026: nobody printed or photographed these sheets. `samples/pods/photos/` holds synthetic phone-style photos, made from the rendered sheets by `samples/photograph_pods.py`. Accuracy measured on them is a first estimate, and it's labelled as an assumption in `docs/data-model.md`.
