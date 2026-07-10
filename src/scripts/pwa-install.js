/**
 * Roastfolio PWA Install Prompt
 *
 * • Android  — captures beforeinstallprompt and shows a native-feeling
 *              bottom sheet with a one-tap "Install" button.
 * • iPhone   — detects standalone mode absence and shows a step-by-step
 *              "Add to Home Screen" guide with the Share icon animation.
 *
 * Rules:
 *  - Never shown if already running as installed PWA.
 *  - Never shown if dismissed within the last 14 days.
 *  - Only shown after meaningful engagement: splashscreen gone + 8 s idle.
 */

(function () {
    'use strict';

    const STORAGE_KEY   = 'roastfolio_install_dismissed';
    const DISMISS_DAYS  = 14;
    const ENGAGE_DELAY  = 8000;   // ms after splash hides before prompt appears

    // ── Guards ────────────────────────────────────────────────────────────────

    // Already installed as PWA → never prompt
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches
                      || navigator.standalone === true;
    if (isStandalone) return;

    // Dismissed recently → skip
    const dismissed = localStorage.getItem(STORAGE_KEY);
    if (dismissed && Date.now() - Number(dismissed) < DISMISS_DAYS * 86400000) return;

    // ── Platform detection ────────────────────────────────────────────────────
    const ua          = navigator.userAgent;
    const isIOS       = /iPhone|iPad|iPod/.test(ua) && !window.MSStream;
    const isAndroid   = /Android/.test(ua);
    const isMobile    = isIOS || isAndroid;

    // Only show on mobile (desktop users can install via browser chrome)
    if (!isMobile) return;

    // ── Deferred install prompt (Android / Chrome) ────────────────────────────
    let deferredPrompt = null;
    window.addEventListener('beforeinstallprompt', e => {
        e.preventDefault();
        deferredPrompt = e;
    });

    // ── Build the UI ──────────────────────────────────────────────────────────

    function dismiss() {
        localStorage.setItem(STORAGE_KEY, String(Date.now()));
        const sheet = document.getElementById('pwa-install-sheet');
        if (sheet) {
            sheet.classList.remove('pwa-sheet-visible');
            setTimeout(() => sheet.remove(), 400);
        }
    }

    function buildSheet(platform) {
        const sheet = document.createElement('div');
        sheet.id = 'pwa-install-sheet';
        sheet.setAttribute('role', 'dialog');
        sheet.setAttribute('aria-modal', 'true');
        sheet.setAttribute('aria-label', 'Install Roastfolio');

        if (platform === 'ios') {
            sheet.innerHTML = `
                <div class="pwa-sheet-inner">
                    <button class="pwa-sheet-close" aria-label="Dismiss" id="pwa-dismiss-btn">✕</button>
                    <div class="pwa-sheet-icon-row">
                        <img src="data/logos/icon-192.png" alt="" class="pwa-sheet-app-icon">
                        <div>
                            <p class="pwa-sheet-title">Add to Home Screen</p>
                            <p class="pwa-sheet-sub">Install Roastfolio for instant access.</p>
                        </div>
                    </div>
                    <ol class="pwa-sheet-steps">
                        <li><span class="pwa-sheet-step-icon">1</span>Tap the <strong>Share</strong> button <span class="pwa-share-icon" aria-hidden="true">⎋</span> at the bottom of Safari</li>
                        <li><span class="pwa-sheet-step-icon">2</span>Scroll down and tap <strong>"Add to Home Screen"</strong></li>
                        <li><span class="pwa-sheet-step-icon">3</span>Tap <strong>"Add"</strong> — done!</li>
                    </ol>
                    <button class="pwa-sheet-dismiss-text" id="pwa-dismiss-btn-2">Maybe later</button>
                </div>`;
        } else {
            // Android / Chrome
            sheet.innerHTML = `
                <div class="pwa-sheet-inner">
                    <button class="pwa-sheet-close" aria-label="Dismiss" id="pwa-dismiss-btn">✕</button>
                    <div class="pwa-sheet-icon-row">
                        <img src="data/logos/icon-192.png" alt="" class="pwa-sheet-app-icon">
                        <div>
                            <p class="pwa-sheet-title">Install Roastfolio</p>
                            <p class="pwa-sheet-sub">Add to your home screen for a native experience.</p>
                        </div>
                    </div>
                    <div class="pwa-sheet-actions">
                        <button class="pwa-sheet-dismiss-text" id="pwa-dismiss-btn-2">Not now</button>
                        <button class="pwa-sheet-install-btn" id="pwa-install-btn">Install</button>
                    </div>
                </div>`;
        }

        document.body.appendChild(sheet);

        // Wire up close buttons
        ['pwa-dismiss-btn', 'pwa-dismiss-btn-2'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.addEventListener('click', dismiss);
        });

        // Android install button
        const installBtn = document.getElementById('pwa-install-btn');
        if (installBtn) {
            installBtn.addEventListener('click', async () => {
                if (!deferredPrompt) { dismiss(); return; }
                deferredPrompt.prompt();
                const { outcome } = await deferredPrompt.userChoice;
                deferredPrompt = null;
                if (outcome === 'accepted') {
                    localStorage.setItem(STORAGE_KEY, String(Date.now() + 3650 * 86400000)); // accepted → never show again
                }
                dismiss();
            });
        }

        // Swipe-down to dismiss (touch)
        let startY = 0;
        sheet.addEventListener('touchstart', e => { startY = e.touches[0].clientY; }, { passive: true });
        sheet.addEventListener('touchend',   e => {
            if (e.changedTouches[0].clientY - startY > 60) dismiss();
        }, { passive: true });

        // Animate in next frame
        requestAnimationFrame(() => {
            requestAnimationFrame(() => sheet.classList.add('pwa-sheet-visible'));
        });
    }

    // ── Show after engagement delay (after splash is gone) ───────────────────
    function schedulePrompt() {
        // If splash is still showing, wait for it to be gone first
        const splash = document.getElementById('splash-screen');
        if (splash && !splash.classList.contains('splash-hidden')) {
            splash.addEventListener('transitionend', () => {
                setTimeout(() => showPrompt(), ENGAGE_DELAY);
            }, { once: true });
        } else {
            setTimeout(() => showPrompt(), ENGAGE_DELAY);
        }
    }

    function showPrompt() {
        // Re-check dismissal in case user dismissed during the delay
        const d = localStorage.getItem(STORAGE_KEY);
        if (d && Date.now() - Number(d) < DISMISS_DAYS * 86400000) return;
        // Re-check standalone (user may have installed during delay)
        if (window.matchMedia('(display-mode: standalone)').matches) return;

        if (isIOS) {
            buildSheet('ios');
        } else if (isAndroid && deferredPrompt) {
            buildSheet('android');
        }
        // If Android but no deferredPrompt, browser will handle it natively
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', schedulePrompt);
    } else {
        schedulePrompt();
    }
})();
