# 10: Phone capture

**What to build:** Before a photo leaves the phone, it's checked for blur and brightness, compressed under 300 KB and given a printed strip with the time, coordinates and trip code. A photo that fails the phone check costs no retake, and after two failures the driver can send it anyway.

**Blocked by:** 07

**Status:** ready-for-agent

**Scheduled:** Saturday

**Spec stories:** 9, 10

- [ ] A blurred or dark photo fails the phone check with no network needed, and the driver is asked for a new photo on the spot
- [ ] After two failures the driver can send anyway, and `device_check` records the result
- [ ] Compression gets the photo under 300 KB including the strip, recompressing at lower quality if needed
- [ ] The strip sits below the receipt, not over it
- [ ] GPS, accuracy and capture time are sent with the attempt, and a missing location doesn't stop the photo
- [ ] `Checking.html` shows the phone check, the size change and the AI step
