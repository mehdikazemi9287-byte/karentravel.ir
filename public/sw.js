/* KarenSeir customer app service worker. Scope: /app only.
   Pages are always fetched from the network first so prices, trips and balances are never served stale;
   when the network is down the user gets a clear offline page instead of a browser error. API calls are not touched. */
const VERSION = 'ks-app-v1';
const OFFLINE_URL = '/offline.html';
const PRECACHE = [OFFLINE_URL, '/app-icons/icon-192.png', '/app-icons/icon-512.png'];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(VERSION).then(cache => cache.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  if (req.mode === 'navigate') {
    event.respondWith(fetch(req).catch(() => caches.match(OFFLINE_URL)));
    return;
  }
  const url = new URL(req.url);
  if (url.origin === self.location.origin && url.pathname.startsWith('/app-icons/')) {
    event.respondWith(caches.match(req).then(hit => hit || fetch(req)));
  }
});
