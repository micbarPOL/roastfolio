// Utility to track roast template performance events
window.RoastTracker = {
    recordEvent: function(payload) {
        // payload should contain: eventType, templateId (optional), scenarioKey (optional), reaction (optional)
        const token = window.AuthGuard && window.AuthGuard.getIdToken ? window.AuthGuard.getIdToken() : null;
        if (!token) {
            console.log("RoastTracker: No token, skipping event", payload.eventType);
            return;
        }

        // If templateId is missing, assume it's a legacy hardcoded string
        if (!payload.templateId) {
            payload.templateId = "legacy-hardcoded";
        }

        const apiUrl = window.__CONFIG__ && window.__CONFIG__.apiUrl;
        if (!apiUrl) return;

        // apiUrl is typically '.../prod/prices', but the tracking endpoint is at '.../prod/roast-events'
        const baseUrl = apiUrl.replace(/\/prices\/?$/, '');

        return fetch(baseUrl + '/roast-events', {
            method: 'POST',
            headers: {
                'Authorization': 'Bearer ' + token,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        }).catch(err => {
            console.error("RoastTracker failed to record event:", err);
        });
    }
};
