/* Dashboard mockup behaviour. Static data only; nothing here talks to the app. */
(() => {
  const root = document.documentElement;
  const $ = (selector, scope = document) => scope.querySelector(selector);
  const $$ = (selector, scope = document) => Array.from(scope.querySelectorAll(selector));
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const params = new URLSearchParams(location.search);
  const later = (fn, ms) => (reduced ? fn() : setTimeout(fn, ms));

  /* Theme */
  function setTheme(theme) {
    root.dataset.theme = theme;
    $$("[data-theme-choice]").forEach((btn) => btn.setAttribute("aria-pressed", String(btn.dataset.themeChoice === theme)));
  }
  $$("[data-theme-choice]").forEach((btn) => btn.addEventListener("click", () => setTheme(btn.dataset.themeChoice)));
  if (params.get("theme") === "light") setTheme("light");

  /* Sidebar collapse (D-012): labels fade first, then the width swaps instantly */
  const app = $(".app");
  const sidebar = $(".sidebar-nav");
  const collapseBtn = $(".sidebar-collapse");
  function setSidebar(collapsed) {
    const apply = () => {
      sidebar.dataset.state = collapsed ? "collapsed" : "expanded";
      app.dataset.sidebar = collapsed ? "collapsed" : "expanded";
      collapseBtn.setAttribute("aria-pressed", String(collapsed));
    };
    if (collapsed) {
      sidebar.dataset.state = "collapsing";
      later(apply, 150);
    } else {
      apply();
    }
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

  /* Segmented controls: arrow keys, aria-selected, optional panels via aria-controls */
  function select(tab) {
    const list = tab.closest('[role="tablist"]');
    $$('[role="tab"]', list).forEach((other) => {
      const on = other === tab;
      other.setAttribute("aria-selected", String(on));
      other.tabIndex = on ? 0 : -1;
      const panel = other.getAttribute("aria-controls") && document.getElementById(other.getAttribute("aria-controls"));
      if (panel) panel.hidden = !on;
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

  /* Gauge (D-006) */
  const gauge = $(".gauge-widget");
  const setNeedle = (angle) => gauge.style.setProperty("--angle", `${angle}deg`);
  gauge.addEventListener("tabchange", (event) => {
    gauge.dataset.mode = event.detail.dataset.mode;
    setNeedle(event.detail.dataset.angle);
  });
  $$(".wallet-dial").forEach((dial) => {
    const target = dial.style.getPropertyValue("--angle");
    dial.style.setProperty("--angle", "-90deg");
    later(() => dial.style.setProperty("--angle", target), 250);
  });

  /* Roast reactions stay hidden until the card is tapped (D-007) */
  const roastToggle = $(".roast-toggle");
  roastToggle.addEventListener("click", () => {
    const open = roastToggle.getAttribute("aria-expanded") !== "true";
    roastToggle.setAttribute("aria-expanded", String(open));
    $("#roast-reactions").hidden = !open;
  });

  /* Disclosures: wallet accordion and benchmark lists */
  $$(".wallet-toggle, .disclosure").forEach((btn) => {
    btn.addEventListener("click", () => {
      const open = btn.getAttribute("aria-expanded") !== "true";
      btn.setAttribute("aria-expanded", String(open));
      document.getElementById(btn.getAttribute("aria-controls")).hidden = !open;
    });
  });

  /* Movers 1D / 1Y */
  $('[data-field="mover-range-toggle"]').addEventListener("tabchange", (event) => {
    const key = `data-${event.detail.dataset.range}`;
    $$(".mover-row .spark-line").forEach((line) => line.setAttribute("points", line.getAttribute(key)));
  });

  /* Benchmark chart, generated from a seeded series so every load looks the same */
  const SVG_NS = "http://www.w3.org/2000/svg";
  const fmt = (n) => n.toLocaleString("pl-PL", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  function series(seed, count, start, drift, vol) {
    let s = seed;
    const rand = () => ((s = (s * 1664525 + 1013904223) % 4294967296) / 4294967296) - 0.5;
    const out = [];
    let price = start;
    for (let i = 0; i < count; i++) {
      const open = price;
      price = Math.max(1, price * (1 + drift + rand() * vol));
      out.push({ o: open, c: price, h: Math.max(open, price) * (1 + Math.abs(rand()) * vol * 0.4), l: Math.min(open, price) * (1 - Math.abs(rand()) * vol * 0.4) });
    }
    return out;
  }
  const RANGES = {
    "1D": { data: series(7, 40, 118420.15, 0.00015, 0.0016), change: "+0.62%", up: true },
    YTD: { data: series(11, 90, 134000, -0.0011, 0.008), change: "-12.40%", up: false },
    "1Y": { data: series(23, 120, 121000, -0.0006, 0.009), change: "-8.15%", up: false },
  };
  const state = { range: "1D", type: "line" };
  const chart = $(".bench-svg");
  const el = (name, attrs) => {
    const node = document.createElementNS(SVG_NS, name);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
    return node;
  };
  function renderChart() {
    const { data, change, up } = RANGES[state.range];
    chart.replaceChildren();
    const lo = Math.min(...data.map((d) => d.l));
    const hi = Math.max(...data.map((d) => d.h));
    const x = (i) => 10 + (i / (data.length - 1)) * 780;
    const y = (v) => 14 + (1 - (v - lo) / (hi - lo)) * 200;
    for (let g = 0; g < 4; g++) chart.append(el("line", { class: "grid-line", x1: 0, x2: 800, y1: 14 + g * 67, y2: 14 + g * 67 }));
    if (state.type === "line") {
      const points = data.map((d, i) => `${x(i).toFixed(1)},${y(d.c).toFixed(1)}`);
      chart.append(el("path", { class: "bench-area", d: `M${points.join(" L")} L790,230 L10,230 Z` }));
      chart.append(el("polyline", { class: "bench-line", points: points.join(" ") }));
    } else {
      const width = Math.max(2, (780 / data.length) * 0.6);
      data.forEach((d, i) => {
        const cls = d.c >= d.o ? "candle-up" : "candle-down";
        chart.append(el("line", { class: cls, x1: x(i), x2: x(i), y1: y(d.h), y2: y(d.l), "stroke-width": 1, "vector-effect": "non-scaling-stroke" }));
        chart.append(el("rect", { class: cls, x: x(i) - width / 2, y: Math.min(y(d.o), y(d.c)), width, height: Math.max(1, Math.abs(y(d.o) - y(d.c))) }));
      });
    }
    const last = data[data.length - 1];
    const badge = $('[data-field="bench-change"]');
    badge.textContent = change;
    badge.className = `bench-change num ${up ? "up" : "down"}`;
    $('[data-field="bench-ohlc"]').innerHTML = [["O", last.o], ["H", last.h], ["L", last.l], ["C", last.c]]
      .map(([label, value]) => `<span class="num">${label} ${fmt(value).replace(/ /g, "&nbsp;")}</span>`).join(" ");
  }
  $('[data-field="bench-range"]').addEventListener("tabchange", (event) => { state.range = event.detail.dataset.range; renderChart(); });
  $('[data-field="bench-type"]').addEventListener("tabchange", (event) => { state.type = event.detail.dataset.type; renderChart(); });
  renderChart();

  /* Total value counts up on load; the final text is already in the markup */
  const total = $("[data-countup]");
  if (total && !reduced) {
    const finalText = total.innerHTML;
    const target = Number(total.dataset.countup);
    const decimals = Number(total.dataset.decimals || 0);
    const start = performance.now();
    const duration = 250;
    const frame = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const value = target * (1 - Math.pow(1 - t, 3));
      total.innerHTML = t < 1
        ? `${value.toLocaleString("pl-PL", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).replace(/\s/g, "&nbsp;")}&nbsp;PLN`
        : finalText;
      if (t < 1) requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
  }

  /* Initial sweep of the main needle, progress bars and one price flash */
  const initialAngle = $('.gauge-head [role="tab"][aria-selected="true"]').dataset.angle;
  setNeedle(-90);
  later(() => setNeedle(initialAngle), 250);
  later(() => document.body.classList.add("is-ready"), 60);
  later(() => $(".mover-row").classList.add("flash"), 1200);

  /* States for review: ?state=loading | empty | ath */
  const view = params.get("state");
  if (view) document.body.dataset.state = view;
  if (view === "empty") $('[data-field="state-empty"]').hidden = false;
  if (view === "ath") $('[data-field="ath-celebration"]').hidden = false;
})();
