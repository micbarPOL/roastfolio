/**
 * Roastfolio Service Worker
 *
 * Strategy:
 *  - Cache static shell (HTML, CSS, JS bundles, icons) on install.
 *  - Serve cached assets first for instant load; fall back to network.
 *  - Never cache Lambda/API calls or any cross-origin CDN scripts so live
 *    data always comes from the network and stale prices are never shown.
 */

const CACHE_NAME = 'roastfolio-v64';

// Assets that live locally and rarely change — cache on install
const PRECACHE = [
    '/',
    '/index.html',
    '/auth.html',
    '/styles/main.css',
    '/scripts/auth-guard.js',
    '/scripts/auth.js',
    '/scripts/user-profile.js',
    '/scripts/portfolios.js',
    '/scripts/ledger-transactions.js',
    '/scripts/manage.js',
    '/scripts/dashboard.js',
    '/scripts/chart.js',
    '/scripts/benchmark-chart.js',
    '/scripts/portfolio-chart.js',

    '/scripts/statistics.js',
    '/scripts/transactions.js',
    '/scripts/wig-chart.js',
    '/scripts/live-data.js',
    '/scripts/pwa-install.js',
    '/scripts/swipe-refresh.js',
    '/data/logos/icon-192.png',
    '/data/logos/icon-192-maskable.png',
    '/data/logos/icon-512.png',
    '/data/logos/icon-512-maskable.png',
    '/data/logos/apple-touch-icon.png',
];

// Patterns that must always hit the network — never cache these
const NEVER_CACHE = [
    /lambda/, /amazonaws\.com/, /cloudfront\.net/,
    /cdn\.jsdelivr\.net/, /unpkg\.com/,
    /cognito-idp\./, /cognito\.amazonaws\.com/,
    /localhost:808\d/,
];

function isNeverCached(url) {
    return NEVER_CACHE.some(pattern => pattern.test(url));
}

function isShellAsset(url, request) {
    if (request.mode === 'navigate') return true;
    try {
        const parsed = new URL(url);
        return (
            parsed.origin === self.location.origin &&
            (
                parsed.pathname === '/' ||
                parsed.pathname.endsWith('.html') ||
                parsed.pathname.endsWith('.css') ||
                parsed.pathname.endsWith('.js') ||
                parsed.pathname.endsWith('.json')
            )
        );
    } catch (_) {
        return false;
    }
}

// ── Install: precache shell ────────────────────────────────────────────────
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(PRECACHE))
    );
    self.skipWaiting();
});

// ── Activate: remove stale caches ─────────────────────────────────────────
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys
                    .filter(k => k !== CACHE_NAME)
                    .map(k => caches.delete(k))
            )
        )
    );
    self.clients.claim();
});

self.addEventListener('message', event => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});

// ── Fetch: cache-first for same-origin static, network-only for live data ──
self.addEventListener('fetch', event => {
    const { request } = event;
    const url = request.url;

    // Always go to the network for live/external calls, and ignore non-http schemes (like chrome-extension://)
    if (isNeverCached(url) || request.method !== 'GET' || !url.startsWith('http')) {
        return; // let browser handle normally
    }

    // App shell should prefer fresh network responses so mobile/PWA picks up UI changes.
    if (isShellAsset(url, request)) {
        event.respondWith(
            fetch(request)
                .then(res => {
                    const clone = res.clone();
                    caches.open(CACHE_NAME).then(c => c.put(request, clone));
                    return res;
                })
                .catch(() => caches.match(request))
        );
        return;
    }

    // data-*.js / portfolio-data-*.js are regenerated frequently — revalidate
    const isDynamic = /\/(data|portfolio-data)[\w-]*\.js(\?|$)/.test(url);
    if (isDynamic) {
        event.respondWith(
            fetch(request).then(res => {
                const clone = res.clone();
                caches.open(CACHE_NAME).then(c => c.put(request, clone));
                return res;
            }).catch(() => caches.match(request))
        );
        return;
    }

    // Static shell: cache-first
    event.respondWith(
        caches.match(request).then(cached => {
            if (cached) return cached;
            return fetch(request).then(res => {
                const clone = res.clone();
                caches.open(CACHE_NAME).then(c => c.put(request, clone));
                return res;
            });
        })
    );
});
