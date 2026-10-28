/**
 * api-throttle.js — Shared guard for browser requests to the Roastfolio API.
 *
 * The AWS account has a small Lambda concurrency pool shared by every
 * environment. A cold dashboard load can burst past it, and API Gateway then
 * answers throttled invocations with a generic 500. This wrapper caps
 * concurrent API requests and retries idempotent requests rejected that way.
 *
 * Must load before any script that calls the API. Non-API requests pass
 * through untouched.
 */
(function () {
  'use strict';

  if (typeof window === 'undefined' || typeof window.fetch !== 'function') return;
  if (window.ApiThrottle) return;

  const MAX_CONCURRENT = 6;
  const RETRY_DELAYS_MS = [600, 1500, 3500];
  const RETRYABLE_STATUSES = new Set([429, 502, 503, 504]);
  const nativeFetch = window.fetch.bind(window);

  let active = 0;
  const waiting = [];

  function configuredApiOrigin() {
    const cfg = window.__CONFIG__ || window.APP_CONFIG || {};
    try {
      return cfg.apiUrl ? new URL(cfg.apiUrl, window.location.href).origin : '';
    } catch (_) {
      return '';
    }
  }

  function requestInfo(input, init) {
    const isRequest = typeof Request !== 'undefined' && input instanceof Request;
    const rawUrl = isRequest ? input.url : String(input);
    const method = String((init && init.method) || (isRequest ? input.method : 'GET')).toUpperCase();
    const signal = (init && init.signal) || (isRequest ? input.signal : null);
    let url;
    try {
      url = new URL(rawUrl, window.location.href);
    } catch (_) {
      url = null;
    }
    return { isRequest, url, method, signal };
  }

  function isApiUrl(url) {
    if (!url) return false;
    const origin = configuredApiOrigin();
    if (origin && url.origin === origin) return true;
    return /\.execute-api\.[a-z0-9-]+\.amazonaws\.com$/i.test(url.hostname);
  }

  function abortError() {
    try {
      return new DOMException('The operation was aborted.', 'AbortError');
    } catch (_) {
      const err = new Error('The operation was aborted.');
      err.name = 'AbortError';
      return err;
    }
  }

  function acquire(signal) {
    if (signal && signal.aborted) return Promise.reject(abortError());
    if (active < MAX_CONCURRENT) {
      active += 1;
      return Promise.resolve();
    }
    return new Promise((resolve, reject) => {
      const entry = { resolve, reject, signal, onAbort: null };
      if (signal) {
        entry.onAbort = () => {
          const idx = waiting.indexOf(entry);
          if (idx !== -1) waiting.splice(idx, 1);
          reject(abortError());
        };
        signal.addEventListener('abort', entry.onAbort, { once: true });
      }
      waiting.push(entry);
    });
  }

  function release() {
    const next = waiting.shift();
    if (next) {
      if (next.signal && next.onAbort) next.signal.removeEventListener('abort', next.onAbort);
      next.resolve();
      return;
    }
    active = Math.max(0, active - 1);
  }

  function wait(ms, signal) {
    return new Promise((resolve, reject) => {
      if (signal && signal.aborted) {
        reject(abortError());
        return;
      }
      const onAbort = () => {
        clearTimeout(timer);
        reject(abortError());
      };
      const timer = setTimeout(() => {
        if (signal) signal.removeEventListener('abort', onAbort);
        resolve();
      }, ms);
      if (signal) signal.addEventListener('abort', onAbort, { once: true });
    });
  }

  // API Gateway reports Lambda throttling as {"message":"Internal server error"};
  // application errors from the Lambda use {"error": ...} and are not retried.
  async function isGatewayThrottle(response) {
    if (RETRYABLE_STATUSES.has(response.status)) return true;
    if (response.status !== 500) return false;
    try {
      const body = await response.clone().json();
      return !!body && body.message === 'Internal server error' && !('error' in body);
    } catch (_) {
      return false;
    }
  }

  async function guardedFetch(input, init) {
    const info = requestInfo(input, init);
    if (!isApiUrl(info.url)) return nativeFetch(input, init);

    const idempotent = info.method === 'GET' || info.method === 'HEAD';
    const maxAttempts = idempotent ? RETRY_DELAYS_MS.length + 1 : 1;

    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      await acquire(info.signal);
      let response;
      try {
        response = await nativeFetch(info.isRequest ? input.clone() : input, init);
      } finally {
        release();
      }
      const lastAttempt = attempt === maxAttempts - 1;
      if (lastAttempt || !(await isGatewayThrottle(response))) return response;
      const base = RETRY_DELAYS_MS[attempt];
      await wait(base + Math.floor(Math.random() * base * 0.3), info.signal);
    }
    throw new Error('api-throttle: unreachable');
  }

  window.fetch = guardedFetch;
  window.ApiThrottle = {
    maxConcurrent: MAX_CONCURRENT,
    stats() {
      return { active, queued: waiting.length };
    },
  };
})();
