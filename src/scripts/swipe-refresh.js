/**
 * Roastfolio — Pull-to-Refresh
 *
 * Pull down from the very top of the page to trigger a live price refresh.
 * Shows an animated indicator that follows the finger, spins while fetching,
 * then fades out on completion.
 *
 * Only active on touch devices. Desktop is unaffected.
 */

(function () {
    'use strict';

    if (!('ontouchstart' in window)) return;   // desktop — do nothing

    // ── Config ────────────────────────────────────────────────────────────────
    const TRIGGER_PX  = 68;   // pull distance to arm the trigger
    const MAX_PULL_PX = 100;  // max visual travel
    const RESISTANCE  = 0.40; // elastic feel (lower = heavier)

    // ── State ─────────────────────────────────────────────────────────────────
    let startY     = 0;
    let pulling    = false;
    let triggered  = false;
    let refreshing = false;

    // ── Indicator element ─────────────────────────────────────────────────────
    // Centred with left:50%/translateX(-50%) — JS only moves top, never touches X
    const indicator = document.createElement('div');
    indicator.id = 'ptr-indicator';
    indicator.setAttribute('aria-hidden', 'true');
    indicator.innerHTML = [
        '<div class="ptr-inner">',
        '  <svg class="ptr-spinner" viewBox="0 0 24 24" fill="none"',
        '       stroke="currentColor" stroke-width="2.2" stroke-linecap="round">',
        '    <circle cx="12" cy="12" r="9" stroke-dasharray="56.5"',
        '            stroke-dashoffset="42" opacity="0.25"/>',
        '    <path d="M12 3 a9 9 0 0 1 9 9"/>',
        '  </svg>',
        '</div>'
    ].join('');
    document.body.appendChild(indicator);

    // ── Helpers ───────────────────────────────────────────────────────────────
    function getScrollTop() {
        return Math.max(
            window.scrollY || 0,
            document.documentElement.scrollTop || 0,
            document.body.scrollTop || 0
        );
    }

    function isAtTop() {
        return getScrollTop() <= 2;
    }

    // Move indicator vertically — `top` starts at -56px (hidden above viewport)
    function setIndicatorTop(px) {
        indicator.style.top = 'calc(-56px + ' + px + 'px)';
    }

    function setProgress(ratio) {
        var spinner = indicator.querySelector('.ptr-spinner');
        if (spinner) spinner.style.transform = 'rotate(' + Math.min(ratio, 1) * 270 + 'deg)';
    }

    function resetIndicator() {
        indicator.classList.remove('ptr-visible', 'ptr-ready', 'ptr-spinning', 'ptr-done');
        setIndicatorTop(0);
    }

    // ── Touch handlers ────────────────────────────────────────────────────────
    document.addEventListener('touchstart', function (e) {
        if (refreshing) return;
        startY    = e.touches[0].clientY;
        pulling   = false;
        triggered = false;
    }, { passive: true });

    document.addEventListener('touchmove', function (e) {
        if (refreshing) return;
        var dy = e.touches[0].clientY - startY;

        if (dy <= 0 || !isAtTop()) {
            if (pulling) { pulling = false; resetIndicator(); }
            return;
        }

        pulling = true;
        var travel = Math.min(dy * RESISTANCE, MAX_PULL_PX);
        setIndicatorTop(travel);
        setProgress(travel / TRIGGER_PX);
        indicator.classList.add('ptr-visible');
        triggered = travel >= TRIGGER_PX;
        indicator.classList.toggle('ptr-ready', triggered);
    }, { passive: true });

    document.addEventListener('touchend', function () {
        if (!pulling) return;
        pulling = false;

        if (!triggered) { resetIndicator(); return; }

        // ── Fire refresh ──────────────────────────────────────────────────────
        refreshing = true;
        indicator.classList.add('ptr-spinning');
        indicator.classList.remove('ptr-ready');
        setIndicatorTop(TRIGGER_PX);

        var done = function () {
            indicator.classList.add('ptr-done');
            setTimeout(function () {
                refreshing = false;
                resetIndicator();
            }, 700);
        };

        if (typeof window.refreshLivePrices === 'function') {
            window.refreshLivePrices().then(done).catch(done);
        } else {
            window.location.reload();
        }
    }, { passive: true });
})();
