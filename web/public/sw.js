// The service worker that lets a driver reopen the app with no signal. Handwritten rather than
// generated, because the job is small: keep the app's own files. It never touches /api, so a stale
// answer can't reach anyone, and photos waiting to send live in IndexedDB rather than here.

const SHELL = "landed-shell";
const VOICE = "landed-voice"; // Filled by the page: see keepVoiceFilesOnPhone in useVoice.tsx.

// The page that registers this worker loaded before it existed, so nothing from that visit passed
// through it. Fetch the app's files now, or the very first visit would leave nothing to work with.
async function cacheTheShell() {
  const cache = await caches.open(SHELL);
  const response = await fetch("/index.html", { cache: "no-cache" });
  const html = await response.clone().text();
  await cache.put("/index.html", response);
  const assets = [...html.matchAll(/(?:src|href)="(\/assets\/[^"]+)"/g)].map((match) => match[1]);
  await cache.addAll(assets);
}

self.addEventListener("install", (event) => {
  event.waitUntil(cacheTheShell().then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

// A page is network first, so a new release shows up as soon as there is signal.
async function page(request) {
  const cache = await caches.open(SHELL);
  try {
    const response = await fetch(request);
    if (response.ok) await cache.put("/index.html", response.clone());
    return response;
  } catch {
    return (await cache.match("/index.html")) ?? Response.error();
  }
}

// Files in /assets have a hash in their name, so a stored copy can never be out of date. That also
// makes ignoreVary safe, and it is needed: the stored files say "Vary: Origin", and the page loads
// them with crossorigin, so a plain match misses and the app comes up blank in a dead zone.
async function asset(request) {
  const cache = await caches.open(SHELL);
  const stored = await cache.match(request, { ignoreVary: true });
  if (stored) return stored;
  const response = await fetch(request);
  if (response.ok) await cache.put(request, response.clone());
  return response;
}

// A voice prompt plays from the phone at once, signal or not. With signal, the stored copy is
// refreshed in the background, so a re-recorded prompt reaches the phone by its next play. The
// refresh asks for the whole file: the audio player's own request asks for a byte range, and a
// partial answer can't be stored.
// The whole file answers the player's range request. Chrome on Android plays that; Safari may
// not, and then the page speaks the words instead.
async function voice(event) {
  const cache = await caches.open(VOICE);
  const url = new URL(event.request.url).pathname;
  const fresh = fetch(url)
    .then(async (response) => {
      if (response.ok) await cache.put(url, response.clone());
      return response;
    })
    .catch(() => null);
  event.waitUntil(fresh); // Keeps the worker alive until the refresh is stored.
  return (await cache.match(url)) ?? (await fresh) ?? Response.error();
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;
  if (request.mode === "navigate") event.respondWith(page(request));
  else if (url.pathname.startsWith("/assets/")) event.respondWith(asset(request));
  else if (url.pathname.startsWith("/voice/")) event.respondWith(voice(event));
});
