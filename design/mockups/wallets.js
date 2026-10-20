/* Wallets mockup behaviour (Appendix B). Static data only. */
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

  /* Sidebar collapse: labels fade first, then the width swaps instantly (D-012) */
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

  /* Segmented controls and tab lists, optionally driving panels through aria-controls */
  function select(tab) {
    const list = tab.closest('[role="tablist"]');
    $$('[role="tab"]', list).forEach((other) => {
      const on = other === tab;
      other.setAttribute("aria-selected", String(on));
      other.tabIndex = on ? 0 : -1;
      const id = other.getAttribute("aria-controls");
      const panel = id && document.getElementById(id);
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
  $$("[data-select-tab]").forEach((btn) => btn.addEventListener("click", () => {
    const tab = document.getElementById(btn.dataset.selectTab);
    if (tab) { select(tab); tab.scrollIntoView({ block: "nearest", behavior: reduced ? "auto" : "smooth" }); }
  }));

  /* Disclosures, including the "New wallet" inline form */
  $$(".disclosure, .w-new").forEach((btn) => {
    btn.addEventListener("click", () => {
      const open = btn.getAttribute("aria-expanded") !== "true";
      btn.setAttribute("aria-expanded", String(open));
      const panel = document.getElementById(btn.getAttribute("aria-controls"));
      panel.hidden = !open;
      if (open) $("input", panel)?.focus();
    });
  });
  $$("form").forEach((form) => form.addEventListener("submit", (event) => event.preventDefault()));

  /* Wallet switcher (D-036): All wallets is read-only (D-038) */
  const page = $(".app");
  $(".w-switcher").addEventListener("tabchange", (event) => {
    const chip = event.detail;
    const all = chip.dataset.wallet === "all";
    $('[data-field="wallet-name"]').textContent = chip.dataset.name;
    $('[data-field="wallet-total"]').innerHTML = chip.dataset.total;
    $('[data-w="pln"]').innerHTML = chip.dataset.pln;
    $('[data-w="pct"]').textContent = chip.dataset.pct;
    $$('.tx-sheet [data-w="name"]').forEach((node) => { node.textContent = chip.dataset.name; });
    $(".w-readonly-note").hidden = !all;
    if (all) page.dataset.readonly = ""; else delete page.dataset.readonly;
    $$("[data-open-tx]").forEach((btn) => { btn.disabled = all; });
  });

  /* Transaction sheet (D-039) */
  const sheet = $(".tx-sheet");
  const sheetBackdrop = $(".sheet-backdrop");
  let opener = null;
  function setSheet(open, from) {
    sheet.hidden = !open;
    sheetBackdrop.hidden = !open;
    document.body.style.overflow = open ? "hidden" : "";
    if (open) { opener = from; $(".tx-close", sheet).focus(); } else if (opener) { opener.focus(); }
  }
  $$("[data-open-tx]").forEach((btn) => btn.addEventListener("click", () => setSheet(true, btn)));
  $$(".tx-close").forEach((btn) => btn.addEventListener("click", () => setSheet(false)));
  sheetBackdrop.addEventListener("click", () => setSheet(false));
  addEventListener("keydown", (event) => { if (event.key === "Escape" && !sheet.hidden) setSheet(false); });
  const HINTS = {
    Buy: "Buying adds to an existing holding or creates a new one.",
    Sell: "Selling reduces the holding. Realized profit uses the average cost (AVCO).",
    Deposit: "Deposits add cash to this wallet.",
    Withdrawal: "Withdrawals take cash out of this wallet.",
    Dividend: "Dividends add cash and count towards the holding's return.",
  };
  $('[data-field="tx-type"]').addEventListener("tabchange", (event) => {
    const type = event.detail.dataset.type;
    $$('.tx-sheet [data-w="type"]').forEach((node) => { node.textContent = type; });
    $(".tx-hint").textContent = HINTS[type];
  });
  $$(".trade-btn").forEach((btn) => btn.addEventListener("click", () => {
    const type = btn.classList.contains("is-sell") ? "Sell" : "Buy";
    $(`[data-field="tx-type"] [data-type="${type}"]`).click();
    setSheet(true, btn);
  }));

  /* Quick entry examples fill the input */
  $$(".qe-examples .chip-btn").forEach((chip) => chip.addEventListener("click", () => {
    $('[data-field="quick-entry-input"]').value = chip.textContent;
  }));

  /* Cemetery filter */
  $('[data-field="cemetery-filter"]').addEventListener("change", (event) => {
    const want = { "Still held": "active", Closed: "closed" }[event.target.value];
    $$(".g-table tbody tr").forEach((row) => { row.hidden = Boolean(want) && row.dataset.status !== want; });
  });

  /* States for review: ?state=loading | empty, ?wallet=all */
  const view = params.get("state");
  if (view) document.body.dataset.state = view;
  if (params.get("wallet") === "all") $('.w-chip[data-wallet="all"]').click();
})();
