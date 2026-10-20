(function () {
    'use strict';

    const STORAGE_KEY = 'roastfolio-dashboard-performance-v1';
    const LIMIT = 20;
    const names = new Set([
        'bootstrap', 'api-headers', 'api-body', 'api-parse', 'data-apply',
        'dashboard-render', 'intraday-synthesis', 'intraday-render',
    ]);
    const milestones = {};
    const samples = [];
    const paints = {};
    const longTasks = { count: 0, durationMs: 0 };
    const observers = [];
    const supported = typeof PerformanceObserver === 'undefined' ? [] : PerformanceObserver.supportedEntryTypes || [];
    let storageWarning = false;

    function snapshot() {
        const navigation = performance.getEntriesByType('navigation')[0];
        const resources = performance.getEntriesByType('resource').filter(entry => {
            const url = new URL(entry.name, location.href);
            return url.origin === location.origin && /\.(js|css)$/.test(url.pathname);
        });
        return {
            schemaVersion: 1,
            recordedAt: new Date().toISOString(),
            release: document.querySelector('link[rel="manifest"]')?.href.split('?v=')[1] || 'unknown',
            viewport: { width: innerWidth, height: innerHeight },
            visibility: document.visibilityState,
            milestones: { ...milestones },
            paints: { ...paints },
            longTasks: { ...longTasks },
            navigation: navigation ? {
                type: navigation.type, ttfbMs: navigation.responseStart - navigation.requestStart,
                domContentLoadedMs: navigation.domContentLoadedEventEnd,
                loadMs: navigation.loadEventEnd,
            } : null,
            assets: {
                count: resources.length,
                transferBytes: resources.reduce((sum, entry) => sum + entry.transferSize, 0),
                decodedBytes: resources.reduce((sum, entry) => sum + entry.decodedBodySize, 0),
            },
            samples: samples.map(sample => ({ ...sample })),
            supported: {
                longTasks: supported.includes('longtask'),
                lcp: supported.includes('largest-contentful-paint'),
            },
        };
    }

    function history() {
        try {
            const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
            return Array.isArray(value) ? value.slice(-LIMIT) : [];
        } catch (error) {
            if (!storageWarning) console.warn('Dashboard timing history unavailable', error);
            storageWarning = true;
            return [];
        }
    }

    const previous = history();
    function persist() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify([...previous, snapshot()].slice(-LIMIT)));
        } catch (error) {
            if (!storageWarning) console.warn('Dashboard timings could not be saved', error);
            storageWarning = true;
        }
    }

    function record(name, durationMs, details = {}) {
        if (!names.has(name) || !Number.isFinite(durationMs) || durationMs < 0) return;
        const sample = { name, durationMs, atMs: performance.now() };
        if (['lite', 'full', 'history'].includes(details.view)) sample.view = details.view;
        if (['ok', 'error', 'unavailable'].includes(details.status)) sample.status = details.status;
        for (const key of ['responseBytes', 'serverMs', 'pointCount', 'holdingCount']) {
            if (Number.isFinite(details[key]) && details[key] >= 0) sample[key] = details[key];
        }
        samples.push(sample);
        if (samples.length > 120) samples.shift();
    }

    function mark(name) {
        if (!['bootstrap-ready', 'cached-ready', 'lite-ready', 'full-ready', 'intraday-ready'].includes(name)) return;
        if (milestones[name] == null) milestones[name] = performance.now();
        persist();
    }

    for (const type of ['paint', 'largest-contentful-paint', 'longtask']) {
        if (!supported.includes(type)) continue;
        const observer = new PerformanceObserver(list => {
            for (const entry of list.getEntries()) {
                if (type === 'longtask') {
                    longTasks.count++;
                    longTasks.durationMs += entry.duration;
                } else if (type === 'largest-contentful-paint') {
                    paints.lcpMs = entry.startTime;
                } else if (entry.name === 'first-contentful-paint') {
                    paints.fcpMs = entry.startTime;
                }
            }
        });
        observer.observe({ type, buffered: true });
        observers.push(observer);
    }

    window.DashboardPerformance = {
        record, mark, snapshot,
        export() {
            persist();
            const blob = new Blob([JSON.stringify({ sessions: history() }, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = 'roastfolio-dashboard-performance.json';
            link.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        },
        clear() {
            previous.length = 0;
            try { localStorage.removeItem(STORAGE_KEY); }
            catch (error) { console.warn('Dashboard timing history could not be cleared', error); }
        },
    };
    document.addEventListener('visibilitychange', persist);
    window.addEventListener('pagehide', persist);
})();
