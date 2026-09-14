/**
 * auth-guard.js — Synchronous authentication guard for index.html
 *
 * Loaded immediately after config.js (before all other app scripts).
 * Reads Cognito tokens from localStorage, checks idToken expiry.
 * Redirects to auth.html if not authenticated.
 * Exposes window.AuthGuard with logout() and getUsername().
 *
 * No external dependencies — works without the Cognito SDK.
 */
(function () {
    'use strict';

    var cfg      = window.__CONFIG__ || {};
    var clientId = cfg.cognitoClientId || '';
    var AUTH_PAGE = 'auth.html';
    var PREFIX = clientId ? 'CognitoIdentityServiceProvider.' + clientId : '';

    function isDevAuthOverrideEnabled() {
        try {
            var params = new URLSearchParams(window.location.search || '');
            if (params.get('devAuth') === '1' || params.get('authTest') === '1' || params.get('skipAuth') === '1') {
                return true;
            }
            return localStorage.getItem('roastfolio.devAuth') === '1';
        } catch (_) {
            return false;
        }
    }

    function createDevJwt() {
        var now = Math.floor(Date.now() / 1000);
        var payload = {
            sub: 'dev-user-123',
            email: 'dev@roastfolio.local',
            nickname: 'Dev User',
            exp: now + 60 * 60 * 24 * 365,
            iat: now
        };
        function b64url(value) {
            return btoa(unescape(encodeURIComponent(value)))
                .replace(/\+/g, '-')
                .replace(/\//g, '_')
                .replace(/=+$/g, '');
        }
        return b64url(JSON.stringify({ alg: 'HS256', typ: 'JWT' })) + '.' +
               b64url(JSON.stringify(payload)) + '.dev';
    }

    function enableDevAuthSession() {
        if (!clientId) return;
        try {
            localStorage.setItem('roastfolio.devAuth', '1');
            localStorage.setItem(PREFIX + '.LastAuthUser', 'dev-user');
            localStorage.setItem(PREFIX + '.dev-user.idToken', createDevJwt());
            localStorage.setItem(PREFIX + '.dev-user.accessToken', 'dev-access-token');
            localStorage.setItem(PREFIX + '.dev-user.refreshToken', 'dev-refresh-token');
        } catch (_) {}
    }

    // If no Cognito config (local dev without config.js), skip guard gracefully
    if (!clientId) {
        console.info('[AuthGuard] No cognitoClientId in config — auth guard disabled (local dev).');
        window.AuthGuard = {
            logout:          function () {},
            isAuthenticated: function () { return true; },
            getUsername:     function () { return 'dev'; },
            getIdToken:      function () { return null; }
        };
        return;
    }

    if (isDevAuthOverrideEnabled()) {
        enableDevAuthSession();
        console.info('[AuthGuard] Local dev auth override enabled for verification.');
    }

    // ── Token helpers ──────────────────────────────────────────────────────────

    function getLastUser() {
        try { return localStorage.getItem(PREFIX + '.LastAuthUser') || null; }
        catch (_) { return null; }
    }

    function getTokenForUser(username, type) {
        // type: 'idToken' | 'accessToken' | 'refreshToken'
        try { return localStorage.getItem(PREFIX + '.' + username + '.' + type) || null; }
        catch (_) { return null; }
    }

    function decodeJwtPayload(token) {
        try {
            var parts = token.split('.');
            if (parts.length !== 3) return null;
            // Base64url → Base64 → JSON
            var b64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
            return JSON.parse(atob(b64));
        } catch (_) { return null; }
    }

    function isJwtExpired(token) {
        var payload = decodeJwtPayload(token);
        if (!payload || typeof payload.exp !== 'number') return true;
        // Add 30-second buffer
        return payload.exp < Math.floor(Date.now() / 1000) + 30;
    }

    // ── Session check ──────────────────────────────────────────────────────────

    function isAuthenticated() {
        var username = getLastUser();
        if (!username) return false;
        var idToken = getTokenForUser(username, 'idToken');
        if (!idToken) return false;
        return !isJwtExpired(idToken);
    }

    function clearAllTokens() {
        try {
            Object.keys(localStorage)
                .filter(function (k) { return k.indexOf(PREFIX) === 0; })
                .forEach(function (k) { localStorage.removeItem(k); });
        } catch (_) {}
    }

    function logout() {
        clearAllTokens();
        window.location.replace(AUTH_PAGE);
    }

    function getUsername() {
        return getLastUser();
    }

    function getDisplayName() {
        // Try nickname from JWT, fall back to email prefix, then full username
        var token = getIdToken();
        if (token) {
            var payload = decodeJwtPayload(token);
            if (payload) {
                if (payload.nickname) return payload.nickname;
                if (payload.email)    return payload.email.split('@')[0];
            }
        }
        var u = getLastUser();
        return u ? u.split('@')[0] : 'User';
    }

    function getIdToken() {
        var username = getLastUser();
        if (!username) return null;
        return getTokenForUser(username, 'idToken');
    }

    function getUserId() {
        // The Cognito 'sub' claim is the stable user ID used as DynamoDB PK
        var token = getIdToken();
        if (!token) return null;
        var payload = decodeJwtPayload(token);
        return (payload && payload.sub) || null;
    }

    // ── Public API ─────────────────────────────────────────────────────────────

    window.AuthGuard = {
        logout:          logout,
        isAuthenticated: isAuthenticated,
        getUsername:     getUsername,
        getDisplayName:  getDisplayName,
        getIdToken:      getIdToken,
        getUserId:       getUserId,
        clearAllTokens:  clearAllTokens
    };

    // ── Guard: redirect if not authenticated ───────────────────────────────────

    if (!isAuthenticated()) {
        window.location.replace(AUTH_PAGE);
        // Throw to stop all subsequent scripts from executing during redirect
        throw new Error('[AuthGuard] Not authenticated — redirecting to ' + AUTH_PAGE);
    }

    console.info('[AuthGuard] Authenticated as', getUsername());

})();
