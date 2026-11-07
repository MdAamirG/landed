# 09: Accuracy script and threshold tuning

**What to build:** A script runs the real Gemini check over the sample photos and reports accuracy per field. Those numbers set the confidence threshold and go in the TDD. This is a measurement, not a test, so it stays out of `pytest`.

**Blocked by:** 07

**Status:** done

**Scheduled:** Sunday, after 16. The final numbers need the photographs from ticket 03's ready-for-human part

**Spec stories:** 33

- [x] The script compares each field read with the expected values for each scenario and prints accuracy per field
- [x] It runs on the rendered images, and on the real photos once they're in `samples/pods/`
- [x] The 0.80 threshold is confirmed or changed based on the real photos, and the change reaches `docs/data-model.md` if it moves
- [x] If stamps or handwritten remarks are misread, the image resolution setting is raised before any move to a bigger model
- [x] The numbers are saved for the TDD

## Comments

- From ticket 03: no real photos are coming. The synthetic photos in `samples/pods/photos/` replace them, so read "real photos" above as those. Label the numbers as a first estimate in the TDD.
- Done on 7 Nov 2026 with 60 real calls: 3 runs of 10 sheets in 2 sets, no failures. All 324 readable field readings were right. The numbers are in `docs/accuracy.md` and the replies in `samples/pods/accuracy-raw.json`.
- 0.80 stays. It stopped 1 of the 11 wrong readings on the blurred sheet, but no sheet was wrongly verified, because the image quality flag and the checks against the trip caught them. 0.95 would stop 8 of the 11 and no right reading on these sheets, but the lowest right reading is exactly 0.95, so there's no margin, and the evidence is one synthetic sheet. Worth doing again on real photos.
- Image resolution stays where it is: no stamp or handwritten remark was misread.
- The measurement sends the photo files as they are. A real upload goes through the phone's compression and strip first, so it's a close stand-in, not the same bytes.
