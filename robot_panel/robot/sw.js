// Service worker de «Mi robot»: guarda la carcasa de la app para que abra al instante y
// sin red; los datos (api/) van siempre a la red y nunca se sirven de caché.
// Rutas relativas al ámbito del worker: funciona en la raíz (Pi) y bajo el ingress de HA.
const CACHE = 'mi-robot-v20';
const SHELL = ['./', 'static/manifest.webmanifest', 'static/icon-192.png?v=6', 'static/icon-512.png?v=6',
               'static/robot.svg', 'static/robot.webp?v=6'];
const SCOPE = new URL(self.registration.scope).pathname;

self.addEventListener('install', e => {
  // de uno en uno: si falta alguno (p. ej. la foto, que no va en el repo) el resto se guarda igual
  e.waitUntil(caches.open(CACHE).then(c => Promise.all(SHELL.map(u => c.add(u).catch(() => {}))))
    .then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

// Avisos push: los manda la Pi cuando el robot tiene un problema (ver push.py)
self.addEventListener('push', e => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (_) { d = {body: e.data ? e.data.text() : ''}; }
  e.waitUntil(self.registration.showNotification(d.title || 'Mi robot', {
    body: d.body || '', tag: d.tag || 'robot', renotify: true,
    icon: 'static/icon-192.png?v=6', badge: 'static/icon-192.png?v=6', data: {url: d.url || './'},
  }));
});
// Al tocar el aviso: si la app ya está abierta, se trae al frente; si no, se abre
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = new URL(e.notification.data?.url || './', self.registration.scope).href;
  e.waitUntil(clients.matchAll({type: 'window', includeUncontrolled: true}).then(cs => {
    for (const c of cs) if (c.url.startsWith(self.registration.scope)) return c.focus();
    return clients.openWindow(url);
  }));
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  const rel = url.pathname.startsWith(SCOPE) ? url.pathname.slice(SCOPE.length) : url.pathname;
  if (e.request.method !== 'GET' || url.origin !== location.origin || rel.startsWith('api/')) return;
  // Red primero (para recibir siempre la última versión) y caché si no hay red.
  e.respondWith(
    fetch(e.request).then(r => {
      if (r.ok) { const copy = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); }
      return r;
    }).catch(() => caches.match(e.request).then(r => r || caches.match(SCOPE)))
  );
});
