# 11: Offline capture

**What to build:** A driver in a dead zone takes the photo and is told it's saved and will send by itself. It sends on reconnect, on app open and every 30 seconds while the app is open, with the same attempt ID each time. This is the brief's hard part and is never cut.

**Blocked by:** 10

**Status:** ready-for-agent

**Scheduled:** Saturday

**Spec stories:** 19 to 24

- [x] The pending-photo queue is a TypeScript module with no UI, holding one pending photo per trip in IndexedDB
- [x] Vitest covers one photo per trip, a new capture replacing an unsent one, the same attempt ID on every retry, keeping the photo after a failed send, and clearing it only after the server confirms
- [x] Storage and network are passed in, so the tests need no browser
- [x] The driver area is a PWA with a manifest, and its shell is cached after the first visit
- [x] The Offline screen matches `Offline.html`
- [x] The trip stays `awaiting_pod` until a photo arrives, and "saved on the phone" is never a trip status
- [x] If the link has expired, the server refuses the send, the phone keeps the photo and the driver is told to call the office (spec assumption 6)

## Comments

- Tested on a production build with the servers really killed, not a simulated offline. The API went down, then the web server too. The page was reloaded with nothing running: it opened from the service worker, remembered the trip and kept the photo. With both back it sent by itself on the 30-second retry. The server held one attempt with the original ID, the real AI verified it, and the 104-second gap was recorded. That test found a real bug: the shell's script and stylesheet missed the cache because of `Vary: Origin`, which left a blank screen.
- Still to do by hand: a real Android phone with airplane mode on and off (plan, Sunday). `navigator.onLine` and the `online` event were not exercised here, because the test killed servers instead of the phone's network. The 30-second timer did the sending.
- `Offline.html`'s "ठीक है, Done" button became "Take a new photo". Done has nothing to do in a browser tab, and the data model needs a way to replace an unsent photo.
- The retry only runs for the trip whose link is open. A photo pending on another trip waits until its link is opened.
- The manifest uses an SVG icon, so the app works as a PWA but Chrome may not offer to install it. The driver flow never needs an install.
