# 09: Accuracy script and threshold tuning

**What to build:** A script runs the real Gemini check over the sample photos and reports accuracy per field. Those numbers set the confidence threshold and go in the TDD. This is a measurement, not a test, so it stays out of `pytest`.

**Blocked by:** 07

**Status:** ready-for-agent

**Scheduled:** Sunday, after 16. The final numbers need the photographs from ticket 03's ready-for-human part

**Spec stories:** 33

- [ ] The script compares each field read with the expected values for each scenario and prints accuracy per field
- [ ] It runs on the rendered images, and on the real photos once they're in `samples/pods/`
- [ ] The 0.80 threshold is confirmed or changed based on the real photos, and the change reaches `docs/data-model.md` if it moves
- [ ] If stamps or handwritten remarks are misread, the image resolution setting is raised before any move to a bigger model
- [ ] The numbers are saved for the TDD
