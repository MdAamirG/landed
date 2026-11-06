# 10: Phone capture

**What to build:** Before a photo leaves the phone, it's checked for blur and brightness, compressed under 300 KB and given a printed strip with the time, coordinates and trip code. A photo that fails the phone check costs no retake, and after two failures the driver can send it anyway.

**Blocked by:** 07

**Status:** ready-for-agent

**Scheduled:** Saturday

**Spec stories:** 9, 10

- [x] A blurred or dark photo fails the phone check with no network needed, and the driver is asked for a new photo on the spot
- [x] After two failures the driver can send anyway, and `device_check` records the result
- [x] Compression gets the photo under 300 KB including the strip, recompressing at lower quality if needed
- [x] The strip sits below the receipt, not over it
- [x] GPS, accuracy and capture time are sent with the attempt, and a missing location doesn't stop the photo
- [x] `Checking.html` shows the phone check, the size change and the AI step

## Comments

- Thresholds came from the synthetic sample photos: sharpness was 12 for `blurry.jpg` and about 2,500 for the other four, so the limit of 30 separates them easily. Real photos will score differently, so tune this on the real Android phone. "Send anyway" covers a bad value until then.
- A 12-megapixel image of pure noise, the worst case for JPEG, compressed to 290 KB in 269 ms on a laptop. Not yet timed on a cheap phone.
- Camera and GPS on a real device are checked by hand, per the spec's "Not covered by automated tests".
- Migration `0002` adds the CHECK constraints on `ai_status`, `device_check` and `outcome`. The new code doesn't need them to run.
