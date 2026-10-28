/* History mockup behaviour (Appendix C). Deterministic sample data only. */
(() => {
  const root = document.documentElement;
  const $ = (selector, scope = document) => scope.querySelector(selector);
  const $$ = (selector, scope = document) => Array.from(scope.querySelectorAll(selector));
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const params = new URLSearchParams(location.search);
  const later = (fn, ms) => (reduced ? fn() : setTimeout(fn, ms));
  const NS = "http://www.w3.org/2000/svg";

  /* Theme */
  function setTheme(theme) {
    root.dataset.theme = theme;
    $$("[data-theme-choice]").forEach((btn) => btn.setAttribute("aria-pressed", String(btn.dataset.themeChoice === theme)));
  }
  $$("[data-theme-choice]").forEach((btn) => btn.addEventListener("click", () => setTheme(btn.dataset.themeChoice)));
  if (params.get("theme") === "light") setTheme("light");

  /* Sidebar collapse (D-012) */
  const app = $(".app");
  const sidebar = $(".sidebar-nav");
  const collapseBtn = $(".sidebar-collapse");
  function setSidebar(collapsed) {
    const apply = () => {
      sidebar.dataset.state = collapsed ? "collapsed" : "expanded";
      app.dataset.sidebar = collapsed ? "collapsed" : "expanded";
      collapseBtn.setAttribute("aria-pressed", String(collapsed));
    };
    if (collapsed) { sidebar.dataset.state = "collapsing"; later(apply, 150); } else { apply(); }
  }
  collapseBtn.addEventListener("click", () => setSidebar(sidebar.dataset.state === "expanded"));
  addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "b") {
      event.preventDefault();
      setSidebar(sidebar.dataset.state === "expanded");
    }
  });
  if (matchMedia("(min-width: 768px) and (max-width: 1023px)").matches) setSidebar(true);

  /* Mobile drawer */
  const drawer = $(".mobile-side-drawer");
  const backdrop = $(".drawer-backdrop");
  const setDrawer = (open) => { drawer.hidden = !open; backdrop.hidden = !open; };
  $(".drawer-open").addEventListener("click", () => setDrawer(true));
  $(".drawer-close").addEventListener("click", () => setDrawer(false));
  backdrop.addEventListener("click", () => setDrawer(false));

  /* Tab lists and segmented controls */
  function select(tab) {
    const list = tab.closest('[role="tablist"]');
    $$('[role="tab"]', list).forEach((other) => {
      const on = other === tab;
      other.setAttribute("aria-selected", String(on));
      other.tabIndex = on ? 0 : -1;
    });
    // Several tabs may control one shared panel (the recap periods), so hide only panels the selected tab does not own.
    const own = tab.getAttribute("aria-controls");
    $$('[role="tab"]', list).forEach((other) => {
      const id = other.getAttribute("aria-controls");
      const panel = id && document.getElementById(id);
      if (panel) panel.hidden = id !== own;
    });
    list.dispatchEvent(new CustomEvent("tabchange", { detail: tab, bubbles: true }));
  }
  $$('[role="tablist"]').forEach((list) => {
    list.addEventListener("click", (event) => {
      const tab = event.target.closest('[role="tab"]');
      if (tab) select(tab);
    });
    list.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
      const tabs = $$('[role="tab"]', list);
      const next = tabs[(tabs.indexOf(document.activeElement) + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length];
      next.focus();
      select(next);
    });
  });

  /* ---------- Formatting ---------- */
  const group = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, "\u00a0");
  function pln(v, sign = false) {
    const abs = Math.abs(v);
    const whole = Math.floor(abs + 1e-9);
    const cents = String(Math.round((abs - whole) * 100)).padStart(2, "0");
    const s = v < 0 ? "-" : sign ? "+" : "";
    return `${s}${group(whole)},${cents === "100" ? "99" : cents}\u00a0PLN`;
  }
  const pct = (v, sign = true) => `${v < 0 ? "-" : sign ? "+" : ""}${Math.abs(v).toFixed(2)}%`;
  const tone = (el, v) => { el.classList.toggle("up", v >= 0); el.classList.toggle("down", v < 0); };
  const iso = (d) => d.toISOString().slice(0, 10);
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  /* ---------- Sample data (seeded so screenshots are stable) ---------- */
  function rng(seed) { let s = seed; return () => ((s = (s * 16807) % 2147483647) - 1) / 2147483646; }
  const TODAY = new Date(Date.UTC(2026, 8, 14));
  const DAYS = 1300;
  const rand = rng(42);
  const days = [], value = [], invested = [], bench = { s1: [], s2: [], s3: [], s4: [] }, deposits = [];
  let v = 120000, cap = 120000, b = { s1: 1, s2: 1, s3: 1, s4: 1 }, twr = 1;
  const twrSeries = [];
  for (let i = 0; i < DAYS; i++) {
    const d = new Date(TODAY.getTime() - (DAYS - 1 - i) * 86400000);
    const r = (rand() - 0.47) * 0.018;
    twr *= 1 + r;
    v *= 1 + r;
    if (i > 0 && d.getUTCDate() === 2 && d.getUTCMonth() % 2 === 0) { v += 6000; cap += 6000; deposits.push(i); }
    days.push(d); value.push(v); invested.push(cap); twrSeries.push(twr);
    b.s1 *= 1 + r * 0.7 + (rand() - 0.5) * 0.008; b.s2 *= 1 + (rand() - 0.46) * 0.014; b.s3 *= 1 + (rand() - 0.47) * 0.011; b.s4 *= 1 + r * 0.6 + (rand() - 0.505) * 0.009;
    for (const k of Object.keys(bench)) bench[k].push(b[k]);
  }
  // scale so "today" matches the hero
  const k0 = 348520.5 / value[DAYS - 1];
  for (let i = 0; i < DAYS; i++) value[i] *= k0;
  const RANGES = { ALL: DAYS, "5Y": DAYS, "3Y": 1095, "1Y": 365, YTD: 257, "1M": 30, "1W": 7 };
  const LABEL = { ALL: "since you started", "5Y": "in the last five years", "3Y": "in the last three years", "1Y": "in the last year", YTD: "this year", "1M": "in the last month", "1W": "in the last week" };

  const state = { range: "1Y", scale: 1, wallet: "All wallets", returnMode: "pct", monthly: "gain", daily: "pct", series: new Set(["s1"]) };

  /* ---------- SVG helpers ---------- */
  const el = (name, attrs) => { const n = document.createElementNS(NS, name); for (const [a, val] of Object.entries(attrs)) n.setAttribute(a, val); return n; };
  function scaler(svg, values, pad = 0.08) {
    const [, , w, h] = svg.getAttribute("viewBox").split(" ").map(Number);
    let lo = Math.min(...values), hi = Math.max(...values);
    const span = hi - lo || 1;
    lo -= span * pad; hi += span * pad;
    return { w, h, y: (val) => h - ((val - lo) / (hi - lo)) * h, lo, hi };
  }
  const path = (xs, ys) => xs.map((x, i) => `${i ? "L" : "M"}${x.toFixed(1)} ${ys[i].toFixed(1)}`).join(" ");
  function axis(name, labels) {
    const box = $(`[data-axis="${name}"]`);
    box.replaceChildren(...labels.map((t) => Object.assign(document.createElement("span"), { textContent: t })));
  }
  function axisDates(slice) {
    const n = slice.length, span = (slice[n - 1] - slice[0]) / 86400000;
    return [0, 0.25, 0.5, 0.75, 1].map((f) => {
      const d = slice[Math.round(f * (n - 1))];
      return span > 400 ? `${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}` : `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
    });
  }
  function bars(svg, vals, cls) {
    const s = scaler(svg, [0, ...vals], 0.06);
    const step = s.w / vals.length, gap = Math.min(4, step * 0.25), zero = s.y(0);
    svg.replaceChildren(el("line", { class: "zero-line", x1: 0, x2: s.w, y1: zero, y2: zero }),
      ...vals.map((val, i) => el("rect", { class: `bar ${cls ? cls(val, i) : val >= 0 ? "up" : "down"}`, x: i * step + gap / 2, width: Math.max(1, step - gap), y: Math.min(zero, s.y(val)), height: Math.max(1, Math.abs(s.y(val) - zero)) })));
  }

  /* ---------- Overview ---------- */
  function window_() { const n = RANGES[state.range]; return [DAYS - n, DAYS]; }

  function renderValue() {
    const [a, z] = window_();
    const vals = value.slice(a, z).map((x) => x * state.scale);
    const inv = invested.slice(a, z).map((x) => x * state.scale);
    const svg = $('[data-chart="value"] svg');
    const s = scaler(svg, [...vals, ...inv]);
    const xs = vals.map((_, i) => (i / (vals.length - 1)) * s.w);
    const line = path(xs, vals.map(s.y));
    svg.replaceChildren(
      ...[0.25, 0.5, 0.75].map((f) => el("line", { class: "grid-line", x1: 0, x2: s.w, y1: s.h * f, y2: s.h * f })),
      el("path", { class: "area", d: `${line} L${s.w} ${s.h} L0 ${s.h} Z` }),
      el("path", { class: "line is-invested", d: path(xs, inv.map(s.y)) }),
      el("path", { class: "line", d: line }),
      ...deposits.filter((i) => i >= a && i < z).map((i) => el("circle", { class: "deposit", cx: xs[i - a], cy: s.y(vals[i - a]), r: 4 })),
      el("line", { class: "cursor-line", x1: 0, x2: 0, y1: 0, y2: s.h, visibility: "hidden" }),
      el("circle", { class: "cursor-dot", cx: 0, cy: 0, r: 5, visibility: "hidden" }),
    );
    svg._data = { xs, vals, inv, s, a };
    axis("value", axisDates(days.slice(a, z)));

    const start = vals[0], end = vals[vals.length - 1];
    const dep = inv[inv.length - 1] - inv[0];
    const gain = end - start, market = gain - dep;
    $('[data-h="wallet"]').textContent = state.wallet;
    $('[data-h="total"]').textContent = pln(end);
    $('[data-h="gain"]').textContent = pln(gain, true);
    $('[data-h="gain-pct"]').textContent = pct((gain / start) * 100);
    $$(".hx-deltas .pill-delta").forEach((p) => tone(p, gain));
    $(".hx-deltas use").setAttribute("href", gain >= 0 ? "#i-arrow-up" : "#i-arrow-down");
    $('[data-h="range-label"]').textContent = LABEL[state.range];
    $('[data-h="invested"]').textContent = pln(inv[inv.length - 1]);
    $('[data-h="deposits"]').textContent = pln(dep, true);
    $('[data-h="market"]').textContent = pln(market, true);
    tone($('[data-h="market"]'), market);
  }

  /* Scrub the value chart (D-043) */
  const plot = $('[data-chart="value"]');
  const readout = $(".hx-readout", plot);
  function scrub(clientX) {
    const svg = $("svg", plot);
    const { xs, vals, inv, s, a } = svg._data;
    const box = svg.getBoundingClientRect();
    const fx = Math.min(1, Math.max(0, (clientX - box.left) / box.width));
    const i = Math.round(fx * (xs.length - 1));
    const x = xs[i];
    const cl = $(".cursor-line", svg), dot = $(".cursor-dot", svg);
    cl.setAttribute("x1", x); cl.setAttribute("x2", x); cl.setAttribute("visibility", "visible");
    dot.setAttribute("cx", x); dot.setAttribute("cy", s.y(vals[i])); dot.setAttribute("visibility", "visible");
    $('[data-r="date"]', readout).textContent = iso(days[a + i]);
    $('[data-r="value"]', readout).textContent = pln(vals[i]);
    $('[data-r="invested"]', readout).textContent = `Invested ${pln(inv[i])}`;
    readout.hidden = false;
    const px = fx * box.width, rw = readout.offsetWidth;
    readout.style.setProperty("--rx", `${Math.round(px + rw + 16 > box.width ? px - rw - 12 : px + 12)}px`);
  }
  function endScrub() {
    readout.hidden = true;
    $$(".cursor-line, .cursor-dot", plot).forEach((n) => n.setAttribute("visibility", "hidden"));
  }
  plot.addEventListener("pointermove", (e) => scrub(e.clientX));
  plot.addEventListener("pointerdown", (e) => scrub(e.clientX));
  plot.addEventListener("pointerleave", endScrub);

  function renderReturn() {
    const [a, z] = window_();
    const svg = $('[data-chart="return"] svg');
    const pctMode = state.returnMode === "pct";
    const port = pctMode
      ? twrSeries.slice(a, z).map((x) => (x / twrSeries[a] - 1) * 100)
      : value.slice(a, z).map((x, i) => (x - invested[a + i] - (value[a] - invested[a])) * state.scale);
    const series = { port };
    if (pctMode) for (const key of Object.keys(bench)) series[key] = bench[key].slice(a, z).map((x) => (x / bench[key][a] - 1) * 100);
    const visible = [port, ...[...state.series].filter(() => pctMode).map((key) => series[key])].flat();
    const s = scaler(svg, [0, ...visible]);
    const xs = port.map((_, i) => (i / (port.length - 1)) * s.w);
    const nodes = [el("line", { class: "zero-line", x1: 0, x2: s.w, y1: s.y(0), y2: s.y(0) })];
    for (const key of ["s4", "s3", "s2", "s1"]) {
      if (!series[key]) continue;
      const p = el("path", { class: `series ${key}`, d: path(xs, series[key].map(s.y)) });
      if (!state.series.has(key)) p.setAttribute("data-off", "");
      nodes.push(p);
    }
    nodes.push(el("path", { class: "series s-port", d: path(xs, port.map(s.y)) }));
    svg.replaceChildren(...nodes);
    axis("return", axisDates(days.slice(a, z)));

    const endPort = $('[data-end="port"]');
    endPort.textContent = pctMode ? pct(port[port.length - 1]) : pln(port[port.length - 1], true);
    tone(endPort, port[port.length - 1]);
    for (const key of Object.keys(bench)) {
      const wrap = $(`[data-end-wrap="${key}"]`);
      wrap.hidden = !pctMode || !state.series.has(key);
      if (series[key]) { const dd = $(`[data-end="${key}"]`); dd.textContent = pct(series[key][series[key].length - 1]); tone(dd, series[key][series[key].length - 1]); }
    }
    $('[data-note="pln"]').hidden = pctMode;
    $('[data-field="history-benchmark-series"]').hidden = !pctMode;
  }

  function renderMonthly() {
    const [a] = window_();
    const months = [];
    for (let i = Math.max(a, 1); i < DAYS; i++) {
      const d = days[i];
      if (i === DAYS - 1 || days[i + 1].getUTCMonth() !== d.getUTCMonth()) {
        const startIdx = months.length ? months[months.length - 1].end : Math.max(a, 1);
        months.push({ end: i, d, gain: (twrSeries[i] / twrSeries[startIdx] - 1) * 100, flow: (invested[i] - invested[startIdx]) * state.scale });
      }
    }
    const list = months.slice(-Math.max(6, Math.min(60, months.length)));
    const svg = $(".hx-monthly .hx-bars-svg");
    if (state.monthly === "gain") bars(svg, list.map((m) => m.gain));
    else bars(svg, list.map((m) => m.flow), () => "flow");
    const ticks = [0, Math.floor(list.length / 2), list.length - 1].map((i) => `${MONTHS[list[i].d.getUTCMonth()]} ${String(list[i].d.getUTCFullYear()).slice(2)}`);
    axis("monthly", ticks);
    svg.setAttribute("aria-label", `Monthly ${state.monthly === "gain" ? "return" : "deposits"} for the last ${list.length} months`);
    const row = $('[data-stat="monthly"]');
    if (state.monthly === "gain") {
      const g = list.map((m) => m.gain);
      row.innerHTML = `Best <strong class="num up">${pct(Math.max(...g))}</strong> Worst <strong class="num down">${pct(Math.min(...g))}</strong> Positive <strong class="num">${g.filter((x) => x >= 0).length} of ${g.length}</strong>`;
    } else {
      const f = list.map((m) => m.flow);
      row.innerHTML = `Deposited <strong class="num">${pln(f.reduce((x, y) => x + y, 0))}</strong> Months with a deposit <strong class="num">${f.filter((x) => x > 0).length} of ${f.length}</strong>`;
    }
  }

  function renderDaily() {
    const [a] = window_();
    const n = Math.min(90, DAYS - a - 1);
    const idx = Array.from({ length: n }, (_, i) => DAYS - n + i);
    const vals = idx.map((i) => (state.daily === "pct" ? (twrSeries[i] / twrSeries[i - 1] - 1) * 100 : (value[i] - value[i - 1] - (invested[i] - invested[i - 1])) * state.scale));
    const svg = $(".hx-daily .hx-scatter-svg");
    const s = scaler(svg, [0, ...vals], 0.12);
    const step = s.w / n, best = vals.indexOf(Math.max(...vals)), worst = vals.indexOf(Math.min(...vals));
    const avg = vals.reduce((x, y) => x + y, 0) / n;
    const dot = (cls, i) => { const x = (i + 0.5) * step, y = s.y(vals[i]); return el("line", { class: cls, x1: x, x2: x, y1: y, y2: y }); };
    const tone_ = (val) => (val >= 0 ? "up" : "down");
    svg.replaceChildren(
      el("line", { class: "zero-line", x1: 0, x2: s.w, y1: s.y(0), y2: s.y(0) }),
      el("line", { class: "avg-line", x1: 0, x2: s.w, y1: s.y(avg), y2: s.y(avg) }),
      dot(`dot-halo ${tone_(vals[best])}`, best), dot(`dot-halo ${tone_(vals[worst])}`, worst),
      ...vals.map((val, i) => dot(`dot ${tone_(val)}${i === best ? " is-best" : i === worst ? " is-worst" : ""}`, i)),
    );
    svg.setAttribute("aria-label", `Daily change for the last ${n} sessions, one dot per session`);
    axis("daily", [days[idx[0]], days[idx[Math.floor(n / 2)]], days[idx[n - 1]]].map((d) => `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`));
    const fmt = state.daily === "pct" ? (x) => pct(x) : (x) => pln(x, true);
    $('[data-stat="daily"]').innerHTML = `Best <strong class="num up">${fmt(vals[best])}</strong> Worst <strong class="num down">${fmt(vals[worst])}</strong> Up days <strong class="num">${Math.round((vals.filter((x) => x >= 0).length / n) * 100)}%</strong> Average <strong class="num">${fmt(avg)}</strong>`;
  }

  function renderOverview() { renderValue(); renderReturn(); renderMonthly(); renderDaily(); }

  $('[data-field="history-range"]').addEventListener("tabchange", (e) => { state.range = e.detail.dataset.range; renderOverview(); });
  $('[data-field="history-wallet-filter"]').addEventListener("tabchange", (e) => { state.scale = Number(e.detail.dataset.scale); state.wallet = e.detail.textContent; renderOverview(); });
  $('[data-field="history-return-mode"]').addEventListener("tabchange", (e) => { state.returnMode = e.detail.dataset.mode; renderReturn(); });
  $('[data-field="history-monthly-metric"]').addEventListener("tabchange", (e) => { state.monthly = e.detail.dataset.metric; renderMonthly(); });
  $('[data-field="history-daily-mode"]').addEventListener("tabchange", (e) => { state.daily = e.detail.dataset.mode; renderDaily(); });
  $$(".series-chip[data-series]").forEach((chip) => chip.addEventListener("click", () => {
    if (chip.getAttribute("aria-disabled") === "true") return;
    const key = chip.dataset.series;
    if (state.series.has(key)) state.series.delete(key); else state.series.add(key);
    chip.setAttribute("aria-pressed", String(state.series.has(key)));
    renderReturn();
  }));

  /* Sticky filter bar gets a hairline once it sticks (D-042) */
  const filters = $(".hx-filters");
  const markStuck = () => { if (filters.offsetParent) filters.toggleAttribute("data-stuck", filters.getBoundingClientRect().top <= 0.5 && scrollY > 0); };
  addEventListener("scroll", markStuck, { passive: true });

  /* ---------- Summaries ---------- */
  const journey = (() => {
    const r = rng(7), port = [0], wig = [0];
    for (let i = 1; i <= 20; i++) { port.push(port[i - 1] + (r() - 0.38) * 0.9); wig.push(wig[i - 1] + (r() - 0.42) * 0.6); }
    const pk = 4.12 / port[20], wk = 2.2 / wig[20];
    const dates = [];
    for (let d = 1; d <= 31; d++) { const dt = new Date(Date.UTC(2026, 7, d)); if (dt.getUTCDay() % 6) dates.push(iso(dt)); }
    return { port: port.map((x) => x * pk), wig: wig.map((x) => x * wk), dates: dates.slice(-21) };
  })();
  function renderJourney() {
    const svg = $('[data-chart="journey"] svg');
    const s = scaler(svg, [0, ...journey.port, ...journey.wig]);
    const xs = journey.port.map((_, i) => (i / 20) * s.w);
    svg.replaceChildren(
      el("line", { class: "zero-line", x1: 0, x2: s.w, y1: s.y(0), y2: s.y(0) }),
      el("path", { class: "rc-lead", d: `${path(xs, journey.port.map(s.y))} ${path([...xs].reverse(), [...journey.wig].reverse().map(s.y)).replace("M", "L")} Z` }),
      el("path", { class: "series s1", d: path(xs, journey.wig.map(s.y)) }),
      el("path", { class: "series s-port", d: path(xs, journey.port.map(s.y)) }),
      el("line", { class: "cursor-line", x1: 0, x2: 0, y1: 0, y2: s.h }),
      el("circle", { class: "cursor-dot", r: 5 }),
    );
    svg._s = { s, xs };
    setJourney(Number($("#rc-scrub").value));
  }
  function setJourney(i) {
    const svg = $('[data-chart="journey"] svg');
    const { s, xs } = svg._s;
    $(".cursor-line", svg).setAttribute("x1", xs[i]);
    $(".cursor-line", svg).setAttribute("x2", xs[i]);
    $(".cursor-dot", svg).setAttribute("cx", xs[i]);
    $(".cursor-dot", svg).setAttribute("cy", s.y(journey.port[i]));
    const gap = journey.port[i] - journey.wig[i];
    $('[data-j="date"]').textContent = journey.dates[i];
    $('[data-j="port"]').textContent = pct(journey.port[i]);
    $('[data-j="bench"]').textContent = pct(journey.wig[i]);
    $('[data-j="gap"]').textContent = `${gap < 0 ? "-" : "+"}${Math.abs(gap).toFixed(2)} pp`;
  }
  $("#rc-scrub").addEventListener("input", (e) => setJourney(Number(e.target.value)));

  function renderSeason() {
    const vals = [1.2, -0.8, 2.4, 0.3, -1.9, 1.1, -0.4, 0.9, 1.6, 2.2];
    bars($(".rc-season-svg"), vals, (val, i) => (i === vals.length - 1 ? "is-now" : val >= 0 ? "up" : "down"));
    axis("season", ["2017", "2021", "2026"]);
  }

  /* Poster sparkline: the month's journey drawn in ink (D-047) */
  function renderSpark() {
    const svg = $(".rc-poster-spark");
    const s = scaler(svg, [...journey.port, ...journey.wig], 0.1);
    const xs = journey.port.map((_, i) => (i / 20) * s.w);
    svg.replaceChildren(
      el("path", { class: "ghost", d: path(xs, journey.wig.map(s.y)) }),
      el("path", { class: "ink", d: path(xs, journey.port.map(s.y)), pathLength: 1 }),
      el("circle", { class: "end", cx: xs[20], cy: s.y(journey.port[20]), r: 5 }),
    );
  }

  /* Period navigator (D-048): Monthly | Yearly, a timeline strip, previous and next */
  const WIG = { "2025-10": 0.9, "2025-11": 0.4, "2025-12": 1.6, "2026-01": 1.4, "2026-02": -2.6, "2026-03": 2.1, "2026-04": 1.5, "2026-05": 0.2, "2026-06": 1.9, "2026-07": -0.6, "2026-08": 2.2, "2026-09": 0.5, 2024: 1.4, 2025: 21.8, 2026: 7.9 };
  const strips = { month: $('[data-strip="month"]'), year: $('[data-strip="year"]') };
  let kind = "month";
  const periods = () => $$(".rc-period", strips[kind]);
  function showPeriod(tab) {
    const twr = Number(tab.dataset.twr), gap = twr - WIG[tab.dataset.period];
    const live = tab.hasAttribute("data-live");
    const words = kind === "year" ? (live ? "So far." : "Wrapped.") : live ? "Live MTD." : "Wrapped.";
    $('[data-rc="month"]').textContent = tab.dataset.label;
    $('[data-rc="kind"]').textContent = words;
    $('[data-rc="edition"]').textContent = kind === "year" ? "Yearly audit" : "Monthly audit";
    $('[data-rc="twr"]').textContent = pct(twr);
    $('[data-rc="mini-month"]').textContent = tab.dataset.label;
    $('[data-rc="mini-kind"]').textContent = words;
    $('[data-rc="mini-twr"]').textContent = pct(twr);
    const mood = Math.abs(twr) < 0.05 ? "flat" : twr > 0 ? "up" : "down";
    $$(".rc-poster").forEach((poster) => { poster.dataset.mood = mood; });
    const sticker = $('[data-rc="sticker"]');
    sticker.hidden = gap <= 0;
    $("strong", sticker).firstChild.textContent = `+${gap.toFixed(1)}`;
    const list = periods(), i = list.indexOf(tab);
    $('[data-step="-1"]').disabled = i === 0;
    $('[data-step="1"]').disabled = i === list.length - 1;
    const strip = strips[kind];
    strip.scrollLeft = tab.offsetLeft - strip.offsetLeft - (strip.clientWidth - tab.offsetWidth) / 2;
    strip.toggleAttribute("data-overflow", strip.scrollWidth > strip.clientWidth + 1);
  }
  $$(".rc-strip").forEach((strip) => strip.addEventListener("tabchange", (e) => showPeriod(e.detail)));
  $('[data-field="recap-period-type"]').addEventListener("tabchange", (e) => {
    kind = e.detail.dataset.kind;
    strips.month.hidden = kind !== "month";
    strips.year.hidden = kind !== "year";
    showPeriod($('.rc-period[aria-selected="true"]', strips[kind]));
  });
  $$(".rc-step").forEach((btn) => btn.addEventListener("click", () => {
    const list = periods(), i = list.indexOf($('.rc-period[aria-selected="true"]', strips[kind]));
    const next = list[i + Number(btn.dataset.step)];
    if (next) select(next);
  }));

  /* ---------- Boot ---------- */
  renderOverview();
  renderJourney();
  renderSeason();
  renderSpark();
  addEventListener("resize", () => { if (!readout.hidden) endScrub(); });

  const current = () => $('.rc-period[aria-selected="true"]', strips[kind]);
  $(".hx-sections").addEventListener("tabchange", (e) => { if (e.detail.id === "tab-summaries") showPeriod(current()); });
  showPeriod(current());

  /* Review states: ?tab=summaries, ?period=yearly, ?state=loading|empty, ?range=5Y */
  if (params.get("tab") === "summaries") select($("#tab-summaries"));
  if (params.get("period") === "yearly") select($("#rc-kind-year"));
  const range = params.get("range");
  if (range) { const tab = $(`[data-range="${range}"]`); if (tab) select(tab); }
  const view = params.get("state");
  if (view) document.body.dataset.state = view;
})();
