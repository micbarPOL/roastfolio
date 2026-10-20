"""Browser contract for the shared API concurrency guard (api-throttle.js)."""
from pathlib import Path

import pytest

pytestmark = pytest.mark.browser
sync_api = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
API = "https://abc123.execute-api.us-west-2.amazonaws.com/prod"

STUB = """
window.__CONFIG__ = { apiUrl: '%s/prices' };
window.__net = { active: 0, peak: 0, calls: {} };
window.fetch = (input, init) => {
  const url = String(input);
  const path = url.includes('/prod') ? url.split('/prod')[1] : url;
  const n = (__net.calls[path] = (__net.calls[path] || 0) + 1);
  __net.active += 1;
  __net.peak = Math.max(__net.peak, __net.active);
  const signal = init && init.signal;
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => {
      __net.active -= 1;
      const json = (status, body) => new Response(JSON.stringify(body), {
        status, headers: { 'Content-Type': 'application/json' } });
      if (path.startsWith('/throttled') && n === 1) resolve(json(500, { message: 'Internal server error' }));
      else if (path.startsWith('/app-error')) resolve(json(500, { error: 'boom' }));
      else resolve(json(200, { ok: path }));
    }, 30);
    if (signal) signal.addEventListener('abort', () => { clearTimeout(t); __net.active -= 1;
      reject(new DOMException('aborted', 'AbortError')); });
  });
};
""" % API


@pytest.fixture
def page():
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.route("http://throttle.test/**", lambda route: route.fulfill(
            content_type="text/html", body="<html><body></body></html>",
        ))
        page.goto("http://throttle.test/")
        page.add_script_tag(content=STUB)
        page.add_script_tag(path=str(ROOT / "src/scripts/api-throttle.js"))
        yield page
        browser.close()


def test_api_requests_are_capped_below_lambda_pool(page):
    result = page.evaluate(f"""async () => {{
        const urls = Array.from({{ length: 16 }}, (_, i) => '{API}/item/' + i);
        const res = await Promise.all(urls.map(u => fetch(u)));
        return {{ statuses: res.map(r => r.status), peak: __net.peak, stats: ApiThrottle.stats() }};
    }}""")
    assert result["statuses"] == [200] * 16
    assert result["peak"] == page.evaluate("ApiThrottle.maxConcurrent") == 6
    assert result["stats"] == {"active": 0, "queued": 0}


def test_non_api_requests_bypass_the_queue(page):
    peak = page.evaluate("""async () => {
        await Promise.all(Array.from({ length: 12 }, (_, i) => fetch('https://cdn.example.com/x' + i)));
        return __net.peak;
    }""")
    assert peak == 12


def test_gateway_throttle_500_is_retried_for_get(page):
    result = page.evaluate(f"""async () => {{
        const r = await fetch('{API}/throttled');
        return [r.status, await r.json(), __net.calls['/throttled']];
    }}""")
    assert result == [200, {"ok": "/throttled"}, 2]


def test_application_500_and_non_idempotent_requests_are_not_retried(page):
    result = page.evaluate(f"""async () => [
        (await fetch('{API}/app-error')).status,
        (await fetch('{API}/throttled-put', {{ method: 'PUT', body: '{{}}' }})).status,
        __net.calls['/app-error'],
        __net.calls['/throttled-put'],
    ]""")
    assert result == [500, 500, 1, 1]


def test_queued_request_honours_abort(page):
    result = page.evaluate(f"""async () => {{
        const blockers = Array.from({{ length: 6 }}, (_, i) => fetch('{API}/block/' + i));
        const ctrl = new AbortController();
        const queued = fetch('{API}/queued', {{ signal: ctrl.signal }});
        ctrl.abort();
        let name = 'resolved';
        try {{ await queued; }} catch (e) {{ name = e.name; }}
        await Promise.all(blockers);
        return [name, __net.calls['/queued'] || 0, ApiThrottle.stats()];
    }}""")
    assert result == ["AbortError", 0, {"active": 0, "queued": 0}]
