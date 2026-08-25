// 배포할 때마다 이 값만 올리면 된다. 앱이 새 버전을 알아채는 유일한 기준.
const APP_BUILD = '2026-08-26.1';
const CACHE_NAME = 'ladi-' + APP_BUILD;
const ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './icons/icon-192x192.png',
  './icons/icon-512x512.png'
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_NAME)
      // cache:'reload' — 설치할 때만큼은 HTTP 캐시를 무시하고 서버에서 새로 받는다.
      .then(cache => cache.addAll(ASSETS.map(u => new Request(u, { cache: 'reload' }))))
      .catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('message', e => {
  if (e.data === 'SKIP_WAITING') self.skipWaiting();
});

self.addEventListener('fetch', e => {
  const req = e.request;

  // Firestore·Firebase CDN 등 외부 요청은 서비스워커가 아예 건드리지 않는다.
  // (실시간 동기화 통신을 가로채면 오히려 깨질 수 있다.)
  if (req.method !== 'GET') return;
  let url;
  try { url = new URL(req.url); } catch (_) { return; }
  if (url.origin !== self.location.origin) return;

  // 앱이 버전 확인용으로 직접 부르는 sw.js는 그냥 통과시킨다.
  // (매번 다른 쿼리가 붙어 있어 가로채면 캐시에 쓰레기 항목만 쌓인다.)
  if (url.pathname.endsWith('/sw.js')) return;

  // 앱 화면(HTML)은 항상 네트워크 우선 — 그리고 HTTP 캐시까지 우회한다.
  // GitHub Pages가 index.html에 max-age=600을 붙이기 때문에, no-store로 받지 않으면
  // 방금 배포한 새 버전 대신 10분 묵은 사본이 나올 수 있다.
  if (req.mode === 'navigate') {
    e.respondWith(
      fetch(req.url, { cache: 'no-store' })
        .then(res => {
          const copy = res.clone();
          caches.open(CACHE_NAME).then(c => c.put('./index.html', copy)).catch(() => {});
          return res;
        })
        // 인터넷이 없을 때만 캐시본으로 버틴다.
        .catch(() => caches.match('./index.html').then(r => r || caches.match('./')))
    );
    return;
  }

  // 나머지 정적 자원(아이콘 등): 캐시로 즉시 보여주되 뒤에서 조용히 새로 받아둔다.
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
