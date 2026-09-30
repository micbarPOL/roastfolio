// Suppress external browser extension warnings (e.g., Grammarly, runtime.lastError):
(function() {
    if (typeof window === 'undefined') return;

    const isExtensionNoise = function(val) {
        if (!val) return false;
        let text = '';
        if (typeof val === 'string') {
            text = val;
        } else if (typeof val === 'object') {
            try {
                text = [
                    val.message,
                    val.stack,
                    val.filename,
                    val.name,
                    val.reason ? (val.reason.message || val.reason.stack || String(val.reason)) : null,
                    String(val)
                ].filter(Boolean).join(' ');
            } catch (_) {
                text = String(val);
            }
        } else {
            text = String(val);
        }
        const lower = text.toLowerCase();
        return lower.includes('could not establish connection. receiving end does not exist') ||
               lower.includes('runtime.lasterror') ||
               lower.includes('extension context invalidated') ||
               lower.includes('grammarly') ||
               lower.includes('kbfnbcaeplbcioakkpcpgfkobkghlhen') ||
               lower.includes('data-gramm') ||
               lower.includes('chrome-extension://') ||
               lower.includes('moz-extension://') ||
               lower.includes('safari-extension://') ||
               lower.includes('safari-web-extension://');
    };

    const origError = console.error;
    console.error = function(...args) {
        if (args.some(isExtensionNoise)) return;
        return origError.apply(console, args);
    };
    const origWarn = console.warn;
    console.warn = function(...args) {
        if (args.some(isExtensionNoise)) return;
        return origWarn.apply(console, args);
    };

    window.addEventListener('error', function(event) {
        if (isExtensionNoise(event?.message) || isExtensionNoise(event?.filename) || isExtensionNoise(event?.error)) {
            event.preventDefault();
            event.stopImmediatePropagation();
        }
    }, true);
    window.addEventListener('unhandledrejection', function(event) {
        if (isExtensionNoise(event?.reason)) {
            event.preventDefault();
            event.stopImmediatePropagation();
        }
    }, true);

    try {
        if (window.chrome && window.chrome.runtime) {
            const runtime = window.chrome.runtime;
            if (typeof runtime.sendMessage === 'function') {
                const origSend = runtime.sendMessage.bind(runtime);
                runtime.sendMessage = function(...args) {
                    const lastArg = args[args.length - 1];
                    if (typeof lastArg !== 'function') {
                        args.push(function() {
                            try { const _ = runtime.lastError; } catch (_) {}
                        });
                    } else {
                        const userCb = lastArg;
                        args[args.length - 1] = function(...cbArgs) {
                            try { const _ = runtime.lastError; } catch (_) {}
                            return userCb.apply(this, cbArgs);
                        };
                    }
                    try {
                        return origSend(...args);
                    } catch (_) {
                        try { const _ = runtime.lastError; } catch (_) {}
                    }
                };
            }
        }
    } catch (_) {}

    // Disable Grammarly globally across the document and dynamically created inputs
    function disableGrammarly(el) {
        if (!el || el.nodeType !== 1) return;
        try {
            const tag = el.tagName ? el.tagName.toLowerCase() : '';
            if (tag === 'input' || tag === 'textarea' || el.isContentEditable || el.hasAttribute('contenteditable')) {
                el.setAttribute('data-gramm', 'false');
                el.setAttribute('data-gram', 'false');
                el.setAttribute('data-gramm_editor', 'false');
                el.setAttribute('data-enable-grammarly', 'false');
                el.setAttribute('spellcheck', 'false');
            } else if (tag === 'html' || tag === 'body' || tag === 'form') {
                el.setAttribute('data-gramm', 'false');
                el.setAttribute('data-gram', 'false');
                el.setAttribute('data-gramm_editor', 'false');
                el.setAttribute('data-enable-grammarly', 'false');
            }
            if (tag.startsWith('grammarly-') || el.classList?.contains('gr_') || el.hasAttribute('data-grammarly-shadow-root')) {
                try {
                    el.remove();
                } catch (_) {
                    el.style.setProperty('display', 'none', 'important');
                    el.style.setProperty('visibility', 'hidden', 'important');
                    el.style.setProperty('pointer-events', 'none', 'important');
                }
            }
        } catch (_) {}
    }

    try {
        if (typeof document !== 'undefined') {
            if (document.documentElement) disableGrammarly(document.documentElement);
            if (document.body) disableGrammarly(document.body);

            // Inject CSS to ensure Grammarly injected overlays stay completely hidden
            const style = document.createElement('style');
            style.setAttribute('data-roastfolio-antigrammarly', 'true');
            style.textContent = 'grammarly-extension,grammarly-popups,grammarly-mirror,grammarly-editor-plugin,[data-grammarly-shadow-root],.gr_{display:none!important;visibility:hidden!important;opacity:0!important;pointer-events:none!important;width:0!important;height:0!important;}';
            (document.head || document.documentElement).appendChild(style);

            const scanAll = function() {
                if (document.body) disableGrammarly(document.body);
                const nodes = document.querySelectorAll('input, textarea, form, [contenteditable], grammarly-extension, grammarly-popups, grammarly-mirror, [data-grammarly-shadow-root]');
                for (let i = 0; i < nodes.length; i++) {
                    disableGrammarly(nodes[i]);
                }
            };

            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', scanAll);
            } else {
                scanAll();
            }

            if (typeof MutationObserver !== 'undefined') {
                const observer = new MutationObserver(function(mutations) {
                    for (let i = 0; i < mutations.length; i++) {
                        const m = mutations[i];
                        for (let j = 0; j < m.addedNodes.length; j++) {
                            const node = m.addedNodes[j];
                            if (node.nodeType === 1) {
                                disableGrammarly(node);
                                if (node.querySelectorAll) {
                                    const sub = node.querySelectorAll('input, textarea, form, [contenteditable], grammarly-extension, grammarly-popups, grammarly-mirror, [data-grammarly-shadow-root]');
                                    for (let k = 0; k < sub.length; k++) {
                                        disableGrammarly(sub[k]);
                                    }
                                }
                            }
                        }
                    }
                });
                observer.observe(document.documentElement, { childList: true, subtree: true });
            }

            window.addEventListener('focusin', function(e) {
                if (e.target && e.target.nodeType === 1) {
                    disableGrammarly(e.target);
                }
            }, true);
        }
    } catch (_) {}
})();

window.__CONFIG__ = {
    apiUrl: "https://f49clnr1qf.execute-api.us-west-2.amazonaws.com/prod/prices",
    cognitoPoolId: "us-west-2_YE8bspYWP",
    cognitoUserPoolId: "us-west-2_YE8bspYWP",
    cognitoClientId: "60m41qcesricibi2huv48imsnt",
    cognitoRegion: "us-west-2"
};

