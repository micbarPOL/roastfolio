// Suppress external browser extension warnings such as:
// "Unchecked runtime.lastError: Could not establish connection. Receiving end does not exist."
(function() {
    if (typeof window === 'undefined') return;

    const isExtensionNoise = function(msg) {
        if (!msg) return false;
        const s = typeof msg === 'string' ? msg : (msg.message || String(msg));
        return s.includes('Could not establish connection. Receiving end does not exist') ||
               s.includes('runtime.lastError');
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
        if (isExtensionNoise(event?.message)) {
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
})();

window.__CONFIG__ = {
    apiUrl: "https://f49clnr1qf.execute-api.us-west-2.amazonaws.com/prod/prices",
    cognitoPoolId: "us-west-2_YE8bspYWP",
    cognitoUserPoolId: "us-west-2_YE8bspYWP",
    cognitoClientId: "60m41qcesricibi2huv48imsnt",
    cognitoRegion: "us-west-2"
};

