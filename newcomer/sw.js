// 배포할 때마다 이 값만 올리면 된다. 앱이 새 버전을 알아채는 유일한 기준.
// index.html의 APP_BUILD와 반드시 같은 값이어야 한다.
const APP_BUILD = '2026-08-26.5';
const CACHE_NAME = 'ladi-newcomer-' + APP_BUILD;
const ASSETS = [
  './',
  './index.html',
  './manifest.json'
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(ASSETS.map(u => new Request(u, { cache: 'reload' }))))
      .catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k.startsWith('ladi-newcomer-') && k !== CACHE_NAME).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('message', e => {
  if (e.data === 'SKIP_WAITING') self.skipWaiting();
});

self.addEventListener('fetch', e => {
  const req = e.request;

  // Firestore·CDN 등 외부 요청은 건드리지 않는다. 실시간 동기화를 가로채면 깨질 수 있다.
  if (req.method !== 'GET') return;
  let url;
  try { url = new URL(req.url); } catch (_) { return; }
  if (url.origin !== self.location.origin) return;

  // 버전 확인용으로 앱이 직접 부르는 sw.js는 통과시킨다(캐시에 쓰레기가 쌓이지 않도록).
  if (url.pathname.endsWith('/sw.js')) return;

  // 앱 화면(HTML)은 항상 네트워크 우선 — GitHub Pages의 max-age=600을 우회한다.
  if (req.mode === 'navigate') {
    e.respondWith(
      fetch(req.url, { cache: 'no-store' })
        .then(res => {
          const copy = res.clone();
          caches.open(CACHE_NAME).then(c => c.put('./index.html', copy)).catch(() => {});
          return res;
        })
        .catch(() => caches.match('./index.html').then(r => r || caches.match('./')))
    );
    return;
  }

  e.respondWith(
    caches.match(req).then(cached => {
      const network = fetch(req).then(res => {
        if (res && res.ok) {
          const copy = res.clone();
          caches.open(CACHE_NAME).then(c => c.put(req, copy)).catch(() => {});
        }
        return res;
      }).catch(() => cached);
      return cached || network;
    })
  );
});
