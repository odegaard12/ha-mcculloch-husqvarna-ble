// Service worker de «Mi robot»: guarda la carcasa de la app para que abra al instante y
// sin red; los datos (/api/) van siempre a la red y nunca se sirven de caché.
const CACHE = 'mi-robot-v9';
const SHELL = ['./', 'static/manifest.webmanifest', 'static/icon-192.png?v=6', 'static/icon-512.png?v=6', 'static/robot.webp?v=6'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.pathname.includes('/api/')) return;
  // Red primero (para recibir siempre la última versión) y caché si no hay red.
  e.respondWith(
    fetch(e.request).then(r => {
      if (r.ok && url.origin === location.origin) { const copy = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); }
      return r;
    }).catch(() => caches.match(e.request).then(r => r || caches.match('/')))
  );
});
