"""Isolated frontend/API regressions; requires Playwright and Chromium, no AWS."""
from pathlib import Path

import pytest

pytestmark = pytest.mark.browser

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


HTML = """<!doctype html><html><body>
<div class="user-field-group"><div class="mgmt-benchmark-row">
<select id="mgmt-benchmark-select" onchange="_mgmt.saveBenchmark(this.value)">
<option value="WIG">WIG (Warsaw Stock Exchange)</option>
<option value="SP500">S&amp;P 500 (US large-cap)</option>
</select><span id="mgmt-benchmark-saved" style="display:none">Saved</span>
</div></div></body></html>"""

HARNESS = """() => {
    window.__CONFIG__ = {apiUrl: 'https://benchmark.test/api/prices/'};
    window.testState = {
        profile: {role: 'BASIC', settings: {benchmark: 'WIG'}},
        token: 'authenticated-id-token', requests: [], dialogs: [], consent: true,
        postStatus: 'accepted', statuses: [], reloads: [], refreshes: 0,
        aborted: [], hold: null, release: null,
    };
    const t = window.testState;
    window.AuthGuard = {getIdToken: () => t.token, getUsername: () => 'test-user'};
    window.BENCHMARK_ID = 'WIG';
    window.confirm = message => {
        t.dialogs.push({message, savedBenchmark: t.profile.settings.benchmark});
        return t.consent;
    };
    window.refreshLivePrices = async () => {
        t.refreshes++;
        if (t.refreshError) throw new Error('Dashboard unavailable');
    };
    window.initMonthlyAudit = async force => {
        t.reloads.push(force);
        if (t.reloadError) throw new Error('Monthly view unavailable');
    };
    window.fetch = async (url, options = {}) => {
        const path = new URL(url).pathname;
        const method = options.method || 'GET';
        const key = method + ' ' + path;
        t.requests.push({url, method, headers: options.headers,
            body: options.body ? JSON.parse(options.body) : null});
        if (t.hold === key) await new Promise((resolve, reject) => {
            t.release = resolve;
            options.signal?.addEventListener('abort', () => {
                t.aborted.push(key);
                reject(new DOMException('Aborted', 'AbortError'));
            }, {once: true});
        });
        if (t.networkError === key) throw new TypeError('Offline');
        if (t.httpError === key) return new Response('Service unavailable', {status: 503});
        let data;
        if (path.endsWith('/profile')) {
            if (method === 'PUT') Object.assign(t.profile.settings, JSON.parse(options.body).settings);
            data = t.profile;
        } else if (path.endsWith('/benchmarks')) {
            data = {benchmarks: [{id:'WIG',name:'WIG'}, {id:'FTSE100',name:'FTSE 100'}]};
        } else if (path.endsWith('/monthly-wraps/recalculate')) {
            data = t.invalidJob ? {} : {job_id: 'job/with spaces?', benchmark_id: t.profile.settings.benchmark,
                status: method === 'POST' ? t.postStatus : (t.statuses.shift() || 'running')};
        } else throw new Error('Unexpected API request: ' + url);
        return new Response(JSON.stringify(data), {status: 200, headers: {'Content-Type':'application/json'}});
    };
}"""


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as runtime:
        instance = runtime.chromium.launch(headless=True)
        yield instance
        instance.close()


@pytest.fixture
def page(browser):
    context = browser.new_context()
    tab = context.new_page()
    tab.route("https://benchmark.test/**", lambda route: route.fulfill(body=HTML, content_type="text/html"))
    tab.goto("https://benchmark.test/")
    tab.clock.install()
    tab.evaluate(HARNESS)
    for script in ("user-profile.js", "manage.js"):
        tab.add_script_tag(content=(ROOT / "src/scripts" / script).read_text())
    tab.evaluate("window.dispatchEvent(new Event('roastfolio:auth'))")
    tab.wait_for_function("document.querySelector('option[value=FTSE100]') !== null")
    tab.evaluate("testState.requests = []")
    yield tab
    context.close()


def save(page, benchmark="SP500"):
    page.evaluate("benchmark => _mgmt.saveBenchmark(benchmark)", benchmark)


def requests(page, method=None, endpoint="/monthly-wraps/recalculate"):
    return [item for item in page.evaluate("testState.requests")
            if endpoint in item["url"] and (method is None or item["method"] == method)]


def feedback(page):
    return page.locator("#mgmt-benchmark-saved").inner_text()


def test_decline_keeps_preference_without_rewriting_history(page):
    page.evaluate("testState.consent = false; localStorage.setItem('lambda_cache', 'stale')")
    # Exercise the actual select handler, not only the exposed function.
    page.select_option("#mgmt-benchmark-select", "SP500")
    page.wait_for_function("testState.dialogs.length === 1")
    assert page.evaluate("testState.profile.settings.benchmark") == "SP500"
    assert page.evaluate("BENCHMARK_ID") == "SP500"
    assert page.evaluate("BENCHMARK_NAME") == "S&P 500"
    assert len(requests(page, "PUT", "/profile")) == 1
    assert not requests(page)
    assert page.evaluate("localStorage.getItem('lambda_cache')") is None
    assert "were not changed" in feedback(page)
    assert page.locator("#mgmt-benchmark-select").is_enabled()
    assert page.evaluate("testState.refreshes") == 1
    assert not page.evaluate("testState.reloads")


def test_consent_posts_after_success_with_id_token_and_tracks_completion(page):
    page.evaluate("testState.statuses = ['running', 'completed']")
    save(page)
    dialog = page.evaluate("testState.dialogs[0]")
    assert dialog["savedBenchmark"] == "SP500"
    assert "monthly reports only" in dialog["message"]
    assert "not all analytics or portfolio snapshots" in dialog["message"]
    mutations = [item for item in page.evaluate("testState.requests") if item["method"] != "GET"]
    assert [item["method"] for item in mutations] == ["PUT", "POST"]
    assert mutations[1]["body"] == {"consent": True}
    assert mutations[1]["headers"]["Authorization"] == "Bearer authenticated-id-token"
    assert mutations[1]["headers"]["Content-Type"] == "application/json"
    assert mutations[1]["url"] == "https://benchmark.test/api/monthly-wraps/recalculate"
    assert "queued" in feedback(page)
    page.clock.run_for(3000)
    assert "Recalculating historical monthly summaries" in feedback(page)
    poll = requests(page, "GET")[0]
    assert poll["url"].endswith("?job_id=job%2Fwith%20spaces%3F")
    assert poll["headers"]["Authorization"] == "Bearer authenticated-id-token"
    page.clock.run_for(3000)
    assert "summaries recalculated" in feedback(page)
    assert page.evaluate("testState.reloads") == [True]
    page.clock.run_for(180000)
    assert len(requests(page, "GET")) == 2


def test_same_benchmark_does_not_save_ask_or_start_job(page):
    save(page, "WIG")
    assert not requests(page, endpoint="/profile")
    assert not requests(page)
    assert not page.evaluate("testState.dialogs")
    assert "unchanged" in feedback(page)


@pytest.mark.parametrize("failure", ["httpError", "networkError"])
def test_failed_save_restores_selection_and_never_requests_consent(page, failure):
    page.evaluate("key => { testState[key] = 'PUT /api/profile'; }", failure)
    save(page)
    assert not requests(page)
    assert not page.evaluate("testState.dialogs")
    assert page.locator("#mgmt-benchmark-select").input_value() == "WIG"
    assert page.locator("#mgmt-benchmark-select").is_enabled()
    assert page.evaluate("BENCHMARK_ID") == "WIG"
    assert "Could not save" in feedback(page)


def test_profile_failure_does_not_guess_previous_benchmark(page):
    page.evaluate("UserProfile.clearCache(); testState.httpError = 'GET /api/profile'")
    save(page)
    assert not requests(page, "PUT", "/profile")
    assert not requests(page)
    assert not page.evaluate("testState.dialogs")


@pytest.mark.parametrize("failure", ["httpError", "networkError"])
def test_job_submission_failure_keeps_saved_benchmark(page, failure):
    page.evaluate("key => { testState[key] = 'POST /api/monthly-wraps/recalculate'; }", failure)
    save(page)
    assert page.evaluate("testState.profile.settings.benchmark") == "SP500"
    assert page.locator("#mgmt-benchmark-select").input_value() == "SP500"
    assert "Benchmark saved" in feedback(page)
    assert "could not be confirmed" in feedback(page)
    page.clock.run_for(180000)
    assert len(requests(page, "POST")) == 1  # Never retry a mutation automatically.
    assert not requests(page, "GET")


@pytest.mark.parametrize("status, message, reloads", [
    ("completed", "summaries recalculated", [True]),
    ("completed_with_errors", "finished with errors", [True]),
    ("failed", "recalculation failed", []),
])
@pytest.mark.parametrize("immediate", [True, False])
def test_terminal_status_feedback_and_cleanup(page, status, message, reloads, immediate):
    page.evaluate("args => { if (args.immediate) testState.postStatus = args.status; else testState.statuses = [args.status]; }",
                  {"status": status, "immediate": immediate})
    save(page)
    if not immediate:
        page.clock.run_for(3000)
    assert message in feedback(page)
    assert page.evaluate("testState.reloads") == reloads
    assert page.locator("#mgmt-benchmark-saved").get_attribute("role") == "status"
    polls = len(requests(page, "GET"))
    page.clock.run_for(180000)
    assert len(requests(page, "GET")) == polls


def test_dashboard_refresh_failure_does_not_block_consented_job(page):
    page.evaluate("testState.refreshError = true; testState.postStatus = 'completed'")
    save(page)
    assert len(requests(page, "POST")) == 1
    assert "summaries recalculated" in feedback(page)


def test_monthly_reload_failure_is_not_reported_as_save_failure(page):
    page.evaluate("testState.reloadError = true; testState.postStatus = 'completed'")
    save(page)
    assert "could not be refreshed" in feedback(page)
    assert page.evaluate("BENCHMARK_ID") == "SP500"


@pytest.mark.parametrize("failure", ["httpError", "networkError"])
def test_status_failure_stops_polling_without_resubmitting_job(page, failure):
    page.evaluate("key => { testState[key] = 'GET /api/monthly-wraps/recalculate'; }", failure)
    save(page)
    page.clock.run_for(3000)
    assert "Could not check" in feedback(page)
    page.clock.run_for(180000)
    assert len(requests(page, "GET")) == 1
    assert len(requests(page, "POST")) == 1


def test_polling_has_wall_clock_bound_and_aborts_stalled_fetch(page):
    page.evaluate("testState.hold = 'GET /api/monthly-wraps/recalculate'")
    save(page)
    page.clock.run_for(3000)
    assert len(requests(page, "GET")) == 1
    page.clock.run_for(120000)
    assert "monitoring stopped" in feedback(page)
    assert page.evaluate("testState.aborted") == ["GET /api/monthly-wraps/recalculate"]
    page.clock.run_for(180000)
    assert len(requests(page, "GET")) == 1


@pytest.mark.parametrize("event", ["hidden", "pagehide", "auth"])
def test_inactive_page_cleans_up_and_ignores_late_status(page, event):
    page.evaluate("testState.hold = 'GET /api/monthly-wraps/recalculate'")
    save(page)
    page.clock.run_for(3000)
    page.evaluate("""event => {
        if (event === 'hidden') {
            Object.defineProperty(document, 'hidden', {configurable:true, value:true});
            document.dispatchEvent(new Event('visibilitychange'));
        } else window.dispatchEvent(new Event(event === 'auth' ? 'roastfolio:auth' : event));
    }""", event)
    assert page.evaluate("testState.aborted") == ["GET /api/monthly-wraps/recalculate"]
    page.evaluate("testState.release?.()")
    page.clock.run_for(180000)
    assert len(requests(page, "GET")) == 1
    assert not page.evaluate("testState.reloads")


def test_pending_save_disables_input_and_deduplicates_calls(page):
    page.evaluate("() => { testState.hold = 'PUT /api/profile'; window.saving = _mgmt.saveBenchmark('SP500'); }")
    page.wait_for_function("testState.release !== null")
    assert page.locator("#mgmt-benchmark-select").is_disabled()
    assert "Saving benchmark" in feedback(page)
    save(page)
    assert len(requests(page, "PUT", "/profile")) == 1
    page.evaluate("testState.release(); window.saving")
    assert len(requests(page, "POST")) == 1
    assert page.locator("#mgmt-benchmark-select").is_enabled()


def test_leaving_during_save_never_starts_a_job_after_late_response(page):
    page.evaluate("() => { testState.hold = 'PUT /api/profile'; window.saving = _mgmt.saveBenchmark('SP500'); }")
    page.wait_for_function("testState.release !== null")
    page.evaluate("window.dispatchEvent(new Event('pagehide')); testState.release(); window.saving")
    assert not requests(page)
    assert not page.evaluate("testState.dialogs")


def test_registry_adds_ftse_once_and_restores_saved_selection(page):
    page.evaluate("testState.profile.settings.benchmark = 'FTSE100'; UserProfile.clearCache(); window.dispatchEvent(new Event('roastfolio:auth'))")
    page.wait_for_function("document.getElementById('mgmt-benchmark-select').value === 'FTSE100'")
    assert page.locator("option[value=FTSE100]").count() == 1
    assert page.locator("option[value=FTSE100]").inner_text() == "FTSE 100"
    assert page.locator("option[value=WIG]").count() == 1
    assert page.locator("option[value=SP500]").count() == 1
    assert not requests(page)


def test_api_requires_explicit_consent_authentication_and_job_id(page):
    errors = page.evaluate("""async () => {
        const errors = [];
        for (const consent of [false, undefined, 'true', 1]) {
            try { await UserProfile.recalculateMonthlySummaries(consent); }
            catch (error) { errors.push(error.message); }
        }
        try { await UserProfile.getMonthlyRecalculationStatus(''); }
        catch (error) { errors.push(error.message); }
        testState.token = null;
        try { await UserProfile.recalculateMonthlySummaries(true); }
        catch (error) { errors.push(error.message); }
        try { await UserProfile.getMonthlyRecalculationStatus('job'); }
        catch (error) { errors.push(error.message); }
        return errors;
    }""")
    assert len(errors) == 7
    assert not requests(page)


def test_invalid_status_is_not_a_false_success(page):
    page.evaluate("testState.invalidJob = true")
    save(page)
    assert "Could not check" in feedback(page)
    assert not page.evaluate("testState.reloads")
    page.clock.run_for(180000)
    assert not requests(page, "GET")