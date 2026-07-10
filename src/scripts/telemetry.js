document.addEventListener('DOMContentLoaded', () => {
    // Wait for auth to be ready
    const checkAuth = setInterval(() => {
        if (window.AuthGuard && window.AuthGuard.isReady()) {
            clearInterval(checkAuth);
            if (window.AuthGuard.isAuthenticated()) {
                document.getElementById('auth-overlay').style.display = 'none';
                document.getElementById('main-ui').style.display = 'block';
                loadTelemetryData();
            } else {
                document.getElementById('main-ui').style.display = 'none';
                document.getElementById('auth-overlay').style.display = 'flex';
                window.AuthGuard.startUi('#firebaseui-auth-container');
            }
        }
    }, 100);
});

async function loadTelemetryData() {
    const token = window.AuthGuard.getIdToken();
    const apiUrl = window.__CONFIG__ && window.__CONFIG__.apiUrl;
    
    if (!apiUrl) {
        showError("API URL not configured.");
        return;
    }

    const baseUrl = apiUrl.replace(/\/prices\/?$/, '');
    
    try {
        const response = await fetch(baseUrl + '/roast-report?days=30', {
            headers: {
                'Authorization': 'Bearer ' + token
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        renderDashboard(data);
    } catch (e) {
        console.error("Failed to load telemetry:", e);
        showError("Failed to load telemetry data. " + e.message);
    }
}

function showError(msg) {
    document.getElementById('telemetry-content').innerHTML = `<div class="error-msg">${msg}</div>`;
}

function renderDashboard(data) {
    let html = '';

    // 1. Disable Candidates (Actionable items)
    if (data.disable_candidates && data.disable_candidates.length > 0) {
        html += `
            <div class="telemetry-card">
                <h2>⚠️ Review Candidates</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Template ID</th>
                            <th>Reason</th>
                            <th>Displays</th>
                            <th>Negative Rate</th>
                            <th>Repetitive</th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        data.disable_candidates.forEach(cand => {
            const stats = cand.stats;
            html += `
                <tr>
                    <td style="font-family:monospace; color:#3498db;">${cand.templateId}</td>
                    <td><span class="badge red">${cand.reason}</span></td>
                    <td>${stats.displayCount}</td>
                    <td>${(stats.negativeRate * 100).toFixed(1)}%</td>
                    <td>${stats.repetitiveCount}</td>
                </tr>
            `;
        });
        html += `</tbody></table></div>`;
    }

    // 2. Scenarios
    html += `
        <div class="telemetry-card">
            <h2>Scenario Triggers (Last 30 Days)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Scenario Key</th>
                        <th>Times Triggered</th>
                        <th>Positive Reactions</th>
                        <th>Negative Reactions</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    // Sort scenarios by displayed count descending
    const sortedScenarios = Object.entries(data.scenarios || {})
        .sort((a, b) => b[1].displayed - a[1].displayed);
        
    sortedScenarios.forEach(([key, stats]) => {
        html += `
            <tr>
                <td style="font-family:monospace; color:#2ecc71;">${key}</td>
                <td>${stats.displayed}</td>
                <td><span class="badge green">${stats.positive}</span></td>
                <td><span class="badge red">${stats.negative}</span></td>
            </tr>
        `;
    });
    
    if (sortedScenarios.length === 0) {
        html += `<tr><td colspan="4" style="text-align:center; color:#64748b;">No scenario data available.</td></tr>`;
    }
    html += `</tbody></table></div>`;

    // 3. Templates
    html += `
        <div class="telemetry-card">
            <h2>Template Performance</h2>
            <table>
                <thead>
                    <tr>
                        <th>Template ID</th>
                        <th>Displays</th>
                        <th>Positive Rate</th>
                        <th>Negative Rate</th>
                        <th>Copied</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    // Sort templates by display count
    const sortedTemplates = Object.entries(data.templates || {})
        .sort((a, b) => b[1].displayCount - a[1].displayCount);
        
    sortedTemplates.forEach(([tid, stats]) => {
        let posClass = stats.positiveRate > 0.3 ? 'green' : '';
        let negClass = stats.negativeRate > 0.3 ? 'red' : '';
        
        html += `
            <tr>
                <td style="font-family:monospace; font-size:0.8rem; color:#94a3b8;">${tid}</td>
                <td>${stats.displayCount}</td>
                <td><span class="badge ${posClass}">${(stats.positiveRate * 100).toFixed(1)}%</span></td>
                <td><span class="badge ${negClass}">${(stats.negativeRate * 100).toFixed(1)}%</span></td>
                <td>${stats.copiedCount}</td>
            </tr>
        `;
    });
    
    if (sortedTemplates.length === 0) {
        html += `<tr><td colspan="5" style="text-align:center; color:#64748b;">No template data available.</td></tr>`;
    }
    html += `</tbody></table></div>`;

    document.getElementById('telemetry-content').innerHTML = html;
}
