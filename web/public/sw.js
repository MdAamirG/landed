// The service worker that lets a driver reopen the app with no signal. Handwritten rather than
// generated, because the job is small: keep the app's own files. It never touches /api, so a stale
// answer can't reach anyone, and photos waiting to send live in IndexedDB rather than here.

const SHELL = "landed-shell";

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

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;
  if (request.mode === "navigate") event.respondWith(page(request));
  else if (url.pathname.startsWith("/assets/")) event.respondWith(asset(request));
});
