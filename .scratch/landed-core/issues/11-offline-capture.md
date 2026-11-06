# 11: Offline capture

**What to build:** A driver in a dead zone takes the photo and is told it's saved and will send by itself. It sends on reconnect, on app open and every 30 seconds while the app is open, with the same attempt ID each time. This is the brief's hard part and is never cut.

**Blocked by:** 10

**Status:** ready-for-agent

**Scheduled:** Saturday

**Spec stories:** 19 to 24

- [ ] The pending-photo queue is a TypeScript module with no UI, holding one pending photo per trip in IndexedDB
- [ ] Vitest covers one photo per trip, a new capture replacing an unsent one, the same attempt ID on every retry, keeping the photo after a failed send, and clearing it only after the server confirms
- [ ] Storage and network are passed in, so the tests need no browser
- [ ] The driver area is a PWA with a manifest, and its shell is cached after the first visit
- [ ] The Offline screen matches `Offline.html`
- [ ] The trip stays `awaiting_pod` until a photo arrives, and "saved on the phone" is never a trip status
- [ ] If the link has expired, the server refuses the send, the phone keeps the photo and the driver is told to call the office (spec assumption 6)
