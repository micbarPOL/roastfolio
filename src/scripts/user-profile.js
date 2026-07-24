/**
 * user-profile.js — Roastfolio user profile client
 *
 * Wraps the /profile API Gateway endpoint.
 * Uses the Cognito idToken from localStorage as Bearer auth.
 * Caches the profile in sessionStorage to avoid repeated requests.
 *
 * Usage:
 *   const profile = await UserProfile.get();
 *   await UserProfile.updateSettings({ theme: 'dark' });
 *   await UserProfile.updateNickname('NewName');
 */
(function () {
    'use strict';

    var cfg         = window.__CONFIG__ || {};
    // Derive profile URL from apiUrl (replace /prices with /profile)
    var PROFILE_URL = (cfg.apiUrl || '').replace(/\/prices$/, '/profile');
    var CACHE_KEY   = 'roastfolio_profile';

    // Return a per-user cache key so switching accounts never serves stale data.
    function userCacheKey() {
        try {
            var u = window.AuthGuard && typeof AuthGuard.getUsername === 'function'
                    ? (AuthGuard.getUsername() || '') : '';
            return u ? (CACHE_KEY + '_' + u) : CACHE_KEY;
        } catch (_) { return CACHE_KEY; }
    }

    // ── Auth token ─────────────────────────────────────────────

    function getIdToken() {
        if (window.AuthGuard && typeof AuthGuard.getIdToken === 'function') {
            return AuthGuard.getIdToken();
        }
        return null;
    }

    // ── Session cache ───────────────────────────────────────────

    function getCached() {
        try {
            var raw = sessionStorage.getItem(userCacheKey());
            return raw ? JSON.parse(raw) : null;
        } catch (_) { return null; }
    }

    function setCached(profile) {
        try { sessionStorage.setItem(userCacheKey(), JSON.stringify(profile)); } catch (_) {}
    }

    function clearCache() {
        try { sessionStorage.removeItem(userCacheKey()); } catch (_) {}
    }

    // ── API helpers ─────────────────────────────────────────────

    function authHeaders() {
        var token = getIdToken();
        return {
            'Content-Type':  'application/json',
            'Authorization': token ? 'Bearer ' + token : ''
        };
    }

    /**
     * GET /profile — fetch (or auto-create on first login) the user profile.
     * Result is cached in sessionStorage for the browser session.
     * @param {boolean} [force=false] — skip cache
     */
    async function get(force) {
        if (!force) {
            var cached = getCached();
            if (cached) return cached;
        }
        if (!getIdToken()) {
            return null;
        }
        if (!PROFILE_URL) {
            console.warn('[UserProfile] No profile URL — config.js not loaded?');
            return null;
        }
        var resp    = await fetch(PROFILE_URL, { headers: authHeaders() });
        var profile = await resp.json();
        if (resp.ok) {
            setCached(profile);
            return profile;
        }
        console.error('[UserProfile] GET failed', resp.status, profile);
        return null;
    }

    /**
     * PUT /profile — partial update.
     * @param {object} updates — e.g. { nickname, settings, portfolioMeta }
     */
    async function put(updates) {
        clearCache();
        var resp    = await fetch(PROFILE_URL, {
            method:  'PUT',
            headers: authHeaders(),
            body:    JSON.stringify(updates)
        });
        var profile = await resp.json();
        if (resp.ok) {
            setCached(profile);
            return profile;
        }
        console.error('[UserProfile] PUT failed', resp.status, profile);
        throw new Error((profile && profile.error) || 'Profile update failed');
    }

    /**
     * Update just the nickname.
     * @param {string} nickname
     */
    function updateNickname(nickname) {
        return put({ nickname: nickname });
    }

    /**
     * Merge settings fields.  Only known keys are accepted by the backend.
     * Known keys: theme, currency, defaultWallet, notifications
     * @param {object} settings — partial settings map
     */
    function updateSettings(settings) {
        return put({ settings: settings });
    }

    /**
     * Update portfolioMeta (e.g. after prices sync).
     * @param {object} meta — { wallets, lastSyncAt, totalValuePLN }
     */
    function updatePortfolioMeta(meta) {
        return put({ portfolioMeta: meta });
    }

    /**
     * Update user's benchmark preference.
     * @param {string} benchmarkId — must be a valid key from the BENCHMARKS registry (e.g. "WIG", "SP500")
     */
    function updateBenchmark(benchmarkId) {
        return updateSettings({ benchmark: benchmarkId });
    }

    function updateRoastIntensity(intensity) {
        return updateSettings({ roastIntensity: intensity });
    }

    /**
     * Return the current user's benchmark ID from cached profile (default: "WIG").
     */
    async function getBenchmark() {
        const profile = await get();
        return (profile && profile.settings && profile.settings.benchmark)
            ? profile.settings.benchmark
            : 'WIG';
    }

    /**
     * Return the current user's roast intensity from cached profile (default: "sarcastic").
     */
    async function getRoastIntensity() {
        const profile = await get();
        return (profile && profile.settings && profile.settings.roastIntensity)
            ? profile.settings.roastIntensity
            : 'sarcastic';
    }

    /**
     * DELETE /profile — hard-delete the user's profile from DynamoDB.
     * Does NOT delete the Cognito account.
     */
    async function deleteProfile() {
        clearCache();
        var resp = await fetch(PROFILE_URL, {
            method:  'DELETE',
            headers: authHeaders()
        });
        return resp.ok;
    }

    /**
     * Return the current user's role (BASIC or ADVANCED).
     * Reads from cached profile; fetches if not cached.
     */
    async function getRole() {
        var profile = await get();
        return (profile && profile.role) ? profile.role : 'BASIC';
    }

    /**
     * Apply role-based UI guards.
     * Tabs with data-role="ADVANCED" are locked for BASIC users.
     * Wallet settings live in the Wallets tab; there is no separate header shortcut.
     */
    async function applyRoleGuard() {
        var profile = await get();

        // If profile exists but has no role field, clear cache and re-fetch once
        if (profile && !profile.role) {
            clearCache();
            profile = await get(true);
        }

        var role = (profile && profile.role) ? profile.role : 'BASIC';
        window.__USER_ROLE__ = role;

        var isAdvanced = role === 'ADVANCED';

        // Lock nav tabs that require ADVANCED
        document.querySelectorAll('[data-role="ADVANCED"]').forEach(function (btn) {
            if (isAdvanced) {
                btn.classList.remove('tab-locked');
                btn.title = '';
            } else {
                btn.classList.add('tab-locked');
                btn.title = 'Available for ADVANCED users';
            }
        });


    }

    // ── Expose globally ─────────────────────────────────────────

    window.UserProfile = {
        get:                 get,
        put:                 put,
        updateNickname:      updateNickname,
        updateSettings:      updateSettings,
        updatePortfolioMeta: updatePortfolioMeta,
        delete:              deleteProfile,
        clearCache:          clearCache,
        getRole:             getRole,
        applyRoleGuard:      applyRoleGuard,
        getBenchmark:        getBenchmark,
        updateBenchmark:     updateBenchmark,
        getRoastIntensity:   getRoastIntensity,
        updateRoastIntensity: updateRoastIntensity
    };

    // Auto-apply role guard once DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', applyRoleGuard);
    } else {
        applyRoleGuard();
    }

})();
