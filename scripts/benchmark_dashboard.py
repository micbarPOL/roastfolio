"""Compare dashboard versions with identical synthetic holdings, CDN bytes and API delays.

No AWS credentials, live portfolio data, users or emails are used. Baseline sources
are read from git into memory; the working tree is never switched or modified.
"""
import argparse
import copy
import gzip
import io
import json
import math
import mimetypes
import re
import socketserver
import statistics
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import server


def sources(ref):
    archive = subprocess.check_output(["git", "archive", f"{ref}:src"], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as entries:
        return {entry.name: entries.extractfile(entry).read() for entry in entries if entry.isfile()}


def payloads():
    """15 stocks, cash, 480 current-session minutes and 480 preceding minutes."""
    zone = ZoneInfo("Europe/Warsaw")
    now = datetime.now(zone)
    start = now.replace(hour=9, minute=0, second=0, microsecond=0)
    session_end = start + timedelta(hours=8)
    bars = []
    for minute in range(480):
        stamp = int((start + timedelta(minutes=minute)).timestamp())
        price = 100 * (1 + minute / 48000)
        bars.append({"t": stamp, "o": 100, "h": price, "l": 100, "c": price, "v": 1000})
    current = server._mock_prices("full")
    stocks = []
    for i in range(15):
        stock = copy.deepcopy(current["portfolioData"][0])
        stock.update(name=f"Synthetic {i}", ticker=f"SYNTH{i}", units=10,
                     priceOriginal=101, pricePLN=101, currentValue=1010,
                     purchaseValue=900, intradayFxRate=1)
        stock["todayBars"] = [[bar["t"] * 1000, bar["c"]] for bar in bars]
        stock["comparisonBars"] = [
            [stamp - 86400000, price] for stamp, price in stock["todayBars"]
        ] + stock["todayBars"]
        stock["intradayBaseline"] = {
            "openTime": int(start.timestamp() * 1000), "sessionStart": int(start.timestamp() * 1000),
            "openPrice": 100, "previousClose": 99,
        }
        stocks.append(stock)
    cash = copy.deepcopy(next(row for row in current["portfolioData"] if not row["ticker"]))
    current["portfolioData"] = stocks + [cash]
    current["walletHoldings"] = {"Demo Portfolio": stocks + [cash]}
    current["benchmarkData"] = {
        "intraday": bars, "daily": [], "weekly": [], "hourly": [], "monthly": [],
        "session": {"start": int(start.timestamp()), "end": int(session_end.timestamp()), "timeZone": str(zone)},
    }
    current["wigData"] = current["benchmarkData"]
    baseline = copy.deepcopy(current)
    for stock in baseline["portfolioData"]:
        stock.pop("comparisonBars", None)
        stock.pop("intradayBaseline", None)
        stock.pop("intradayFxRate", None)
    baseline["benchmarkData"].pop("session", None)
    lite = server._mock_prices("lite")
    return lite, baseline, current, int((session_end + timedelta(hours=2)).timestamp() * 1000)


COLLECT = """({now, cpuRate}) => {
    Date.now = () => now;
    localStorage.setItem('roastfolio.devAuth', '1');
    localStorage.setItem('roastfolio-theme', 'dark');
    window.benchmarkResult = {cpuRate, errors: [], longTasks: []};
    if (PerformanceObserver.supportedEntryTypes.includes('longtask')) {
        new PerformanceObserver(list => {
            for (const entry of list.getEntries()) benchmarkResult.longTasks.push(entry.duration);
        }).observe({type: 'longtask', buffered: true});
    }
    document.addEventListener('liveDataReady', event => {
        if (event.detail?.responseMode !== 'full') return;
        benchmarkResult.fullDataMs = performance.now();
        requestAnimationFrame(() => requestAnimationFrame(() => {
            benchmarkResult.readyMs = performance.now();
        }));
    });
}"""


def percentile(values, p):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * p) - 1)]


def summarize(rows):
    result = {}
    for key in ["readyMs", "fullDataMs", "longTaskMs", "synthesisMs", "chartRenderMs", "parseMs"]:
        values = [row[key] for row in rows if row[key] is not None]
        result[key] = {
            "median": round(statistics.median(values), 3),
            "p95": round(percentile(values, 0.95), 3),
        } if values else None
    return result


def run(args):
    historical = sources(args.baseline)
    current_sources = {str(path.relative_to(ROOT / "src")): path.read_bytes()
                       for path in (ROOT / "src").rglob("*") if path.is_file()}
    lite, old, new, now = payloads()
    old_bytes = json.dumps(old).encode()
    new_bytes = json.dumps(new).encode()
    cdn = {}
    for html in [historical["index.html"], current_sources["index.html"]]:
        for url in re.findall(rb'<script[^>]+src="(https://[^"]+)"', html):
            address = url.decode()
            if address not in cdn:
                with urllib.request.urlopen(address, timeout=30) as response:
                    cdn[address] = (response.read(), response.headers.get_content_type())
    class QuietHandler(server.InvestmentHandler):
        def log_message(self, *_args):
            pass
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), QuietHandler)
    server.PORT = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    origin = f"http://localhost:{server.PORT}"
    rows = []
    variants = ["baseline", "current-without-comparison", "current"]
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                for iteration in range(args.runs + 1):
                    # Alternate order to reduce warm-up/thermal ordering bias.
                    order = variants if iteration % 2 == 0 else list(reversed(variants))
                    for variant in order:
                        source = historical if variant == "baseline" else current_sources
                        payload = old if variant == "baseline" else new
                        context = browser.new_context(viewport={"width": 1440, "height": 900},
                                                      service_workers="block", reduced_motion="reduce")
                        page = context.new_page()
                        errors = []
                        failed_requests = []
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        page.on("requestfailed", lambda request: failed_requests.append({
                            "path": urlsplit(request.url).path, "failure": request.failure,
                        }))
                        session = context.new_cdp_session(page)
                        session.send("Emulation.setCPUThrottlingRate", {"rate": args.cpu_rate})
                        page.add_init_script(f"({COLLECT})({json.dumps({'now': now, 'cpuRate': args.cpu_rate})})")

                        def route_request(route):
                            url = route.request.url
                            parts = urlsplit(url)
                            if url in cdn:
                                content, content_type = cdn[url]
                                route.fulfill(body=content, content_type=content_type)
                                return
                            if parts.netloc != urlsplit(origin).netloc:
                                route.continue_()
                                return
                            path = unquote(parts.path).lstrip("/")
                            if path == "prices":
                                view = parse_qs(parts.query).get("view", ["full"])[0]
                                body = json.dumps(lite if view == "lite" else payload)
                                # The extra payload is also charged at the selected bandwidth.
                                time.sleep(args.api_delay_ms / 1000 + len(body.encode()) * 8 / (args.mbps * 1_000_000))
                                route.fulfill(body=body, content_type="application/json",
                                              headers={"Server-Timing": f"app;dur={args.api_delay_ms}",
                                                       "X-Response-Bytes": str(len(body.encode()))})
                            elif path == "scripts/config.js" or path == "refresh-status" or "." not in path:
                                route.continue_()
                            elif path == "scripts/intraday-comparison.js" and variant == "current-without-comparison":
                                route.fulfill(body="", content_type="application/javascript")
                            elif path in source:
                                route.fulfill(body=source[path], content_type=mimetypes.guess_type(path)[0] or "application/octet-stream")
                            else:
                                route.fulfill(status=404, body="Not in this source version")

                        page.route("**/*", route_request)
                        try:
                            page.goto(f"{origin}/index.html?devAuth=1", wait_until="load", timeout=60000)
                            page.wait_for_function("benchmarkResult.readyMs > 0", timeout=60000)
                            page.wait_for_selector("#dash-breakdown .sparkline-svg", timeout=30000)
                            if variant == "current":
                                page.wait_for_function("Chart.getChart('intraday-comparison-chart')", timeout=30000)
                            page.wait_for_timeout(100)
                            result = page.evaluate("""() => {
                                const telemetry = window.DashboardPerformance?.snapshot();
                                const samples = telemetry?.samples || [];
                                const durations = name => samples.filter(s => s.name === name).map(s => s.durationMs);
                                return {...benchmarkResult,
                                    longTaskMs: benchmarkResult.longTasks.reduce((a,b) => a+b, 0),
                                    synthesisMs: durations('intraday-synthesis').length
                                        ? Math.max(...durations('intraday-synthesis')) : null,
                                    chartRenderMs: samples.some(s => s.name === 'intraday-render' && s.status === 'ok')
                                        ? Math.max(...samples.filter(s => s.name === 'intraday-render' && s.status === 'ok')
                                            .map(s => s.durationMs)) : null,
                                    parseMs: durations('api-parse').length
                                        ? durations('api-parse').reduce((a,b) => a+b, 0) : null,
                                    telemetry};
                            }""")
                            if errors:
                                raise RuntimeError(f"{variant} script errors: {errors}")
                            if iteration:
                                rows.append({"variant": variant, "iteration": iteration, **result})
                            print(f"{variant} run {iteration}: ready={result['readyMs']:.1f}ms "
                                  f"chart={result['chartRenderMs']}ms", flush=True)
                        except Exception as error:
                            state = page.evaluate("""() => ({
                                measurement: window.benchmarkResult,
                                bootstrap: window.__walletBootstrapState,
                                status: document.getElementById('live-data-status')?.textContent
                            })""")
                            raise RuntimeError(
                                f"{variant} run {iteration} failed: {error}; "
                                f"errors={errors}; requests={failed_requests}; state={state}"
                            ) from error
                        finally:
                            context.close()
            finally:
                browser.close()
    finally:
        httpd.shutdown()
        httpd.server_close()
    summary = {variant: summarize([row for row in rows if row["variant"] == variant]) for variant in variants}
    baseline_ready = summary["baseline"]["readyMs"]["median"]
    current_ready = summary["current"]["readyMs"]["median"]
    return {
        "createdAt": datetime.now().astimezone().isoformat(),
        "baselineCommit": subprocess.check_output(["git", "rev-parse", args.baseline], cwd=ROOT, text=True).strip(),
        "currentBranch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
        "method": {"runsPerVariant": args.runs, "discardedWarmupsPerVariant": 1, "holdings": 15,
                   "currentSessionBarsPerStock": 480, "comparisonBarsPerStock": 960,
                   "cpuRate": args.cpu_rate, "apiDelayMs": args.api_delay_ms, "simulatedPayloadMbps": args.mbps,
                   "data": "Synthetic only; fixed mock API delay. Not a live Yahoo/AWS latency comparison.",
                   "readiness": "Two animation frames after full data application; excludes gauge animation completion.",
                   "cache": "Fresh browser context each sample; identical pre-fetched CDN script bytes; service workers blocked."},
        "payload": {
            "baselineBytes": len(old_bytes), "currentBytes": len(new_bytes),
            "baselineGzipBytes": len(gzip.compress(old_bytes)), "currentGzipBytes": len(gzip.compress(new_bytes)),
        },
        "summary": summary,
        "delta": {"readyMedianMs": round(current_ready - baseline_ready, 3),
                  "readyMedianPct": round((current_ready / baseline_ready - 1) * 100, 3),
                  "chartToggleObservedMedianMs": round(current_ready - summary["current-without-comparison"]["readyMs"]["median"], 3)},
        "samples": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default="50425ee")
    parser.add_argument("--runs", type=int, default=7)
    parser.add_argument("--cpu-rate", type=float, default=1)
    parser.add_argument("--api-delay-ms", type=float, default=100)
    parser.add_argument("--mbps", type=float, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.runs < 3 or args.cpu_rate < 1 or args.api_delay_ms < 0 or args.mbps <= 0:
        parser.error("Use at least 3 runs, CPU rate >=1, nonnegative delay and positive bandwidth.")
    report = run(args)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"summary": report["summary"], "delta": report["delta"], "payload": report["payload"]}, indent=2))
