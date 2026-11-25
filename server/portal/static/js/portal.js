/* Portal interactions. Progressive enhancement: every page works without this
   script (forms post, links navigate); the script only removes full reloads. */
(() => {
  "use strict";
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  /* ---------- Toasts ---------- */
  function toast(message, opts = {}) {
    const host = $("#toasts");
    if (!host) return;
    const el = document.createElement("div");
    el.className = "toast";
    el.setAttribute("role", "status");
    const text = document.createElement("span");
    text.textContent = message;
    el.append(text);
    const dismiss = () => {
      el.classList.add("leaving");
      setTimeout(() => el.remove(), 200);
    };
    if (opts.action) {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = opts.action;
      b.addEventListener("click", () => { dismiss(); opts.onAction && opts.onAction(); });
      el.append(b);
    }
    host.append(el);
    while (host.children.length > 3) host.firstElementChild.remove();
    const timer = setTimeout(dismiss, opts.timeout || 5000);
    el.addEventListener("pointerenter", () => clearTimeout(timer), { once: true });
  }
  window.portalToast = toast;

  /* ---------- Account menu ---------- */
  $$("details.menu").forEach((menu) => {
    document.addEventListener("pointerdown", (e) => { if (menu.open && !menu.contains(e.target)) menu.open = false; });
    menu.addEventListener("keydown", (e) => { if (e.key === "Escape") { menu.open = false; $("summary", menu).focus(); } });
  });

  /* ---------- Confirm destructive forms; show progress on slow ones ---------- */
  $$("form[data-confirm]").forEach((f) => f.addEventListener("submit", (e) => {
    if (!window.confirm(f.dataset.confirm)) e.preventDefault();
  }));
  $$("form[data-busy]").forEach((f) => f.addEventListener("submit", () => {
    const btn = $("button", f);
    btn.classList.add("is-loading");
    btn.setAttribute("aria-busy", "true");
  }));

  /* ---------- Live: a new session arrived from the phone ---------- */
  const body = document.body;
  if (body.hasAttribute("data-latest")) {
    let seen = body.dataset.latest;
    const poll = async () => {
      try {
        const res = await fetch("/live/latest", { credentials: "same-origin" });
        if (res.status === 401) return; // signed out: stop polling
        const d = res.ok ? await res.json() : null;
        if (d && d.session_id && d.session_id !== seen) {
          seen = d.session_id;
          const url = `/sessions/${encodeURIComponent(d.session_id)}`;
          const typing = document.activeElement && document.activeElement.matches("input, textarea, select");
          if (body.hasAttribute("data-follow") && !typing) { location.assign(url); return; }
          toast(`New attendance received for ${d.section}`, { action: "Open", onAction: () => location.assign(url), timeout: 60000 });
        }
      } catch (err) { /* portal unreachable: try again */ }
      setTimeout(poll, 3000);
    };
    setTimeout(poll, 3000);
  }

  /* ---------- Sign in ---------- */
  const signin = $("form[data-signin]");
  if (signin) signin.addEventListener("submit", () => {
    const btn = $("button[type=submit]", signin);
    btn.classList.add("is-loading");
    btn.setAttribute("aria-busy", "true");
    $("span", btn).textContent = "Signing in";
  });

  /* ---------- Generic table filtering (students, sessions) ---------- */
  $$("[data-filter-table]").forEach((input) => {
    const table = document.getElementById(input.dataset.filterTable);
    const empty = $(".empty-row", table);
    const rows = $$("tbody tr:not(.empty-row)", table);
    input.addEventListener("input", () => {
      const q = input.value.trim().toLowerCase();
      let shown = 0;
      rows.forEach((r) => { const hit = !q || r.textContent.toLowerCase().includes(q); r.classList.toggle("is-hidden", !hit); shown += hit; });
      if (empty) empty.classList.toggle("is-hidden", shown > 0);
    });
  });

  /* ---------- Attendance register ---------- */
  const reg = $("#register");
  if (!reg) return;
  const wrap = reg.closest(".table-wrap");
  const tbody = $("tbody", reg);
  const threshold = Number(reg.dataset.threshold || 75);
  const rows = () => $$("tr[data-roll]", tbody);
  const marksIn = (tr) => $$(".mark", tr);

  function recompute() {
    let sum = 0, counted = 0, low = 0;
    rows().forEach((tr) => {
      const marks = marksIn(tr);
      const present = marks.filter((m) => m.dataset.status === "present").length;
      const pct = marks.length ? Math.round((100 * present) / marks.length) : null;
      tr.dataset.pct = pct === null ? "" : pct;
      const cell = $(".pct", tr);
      if (cell) { cell.textContent = pct === null ? "—" : pct + "%"; cell.classList.toggle("low", pct !== null && pct < threshold); }
      tr.dataset.low = pct !== null && pct < threshold ? "1" : "0";
      tr.dataset.manual = marks.some((m) => m.dataset.source === "manual") ? "1" : "0";
      if (pct !== null) { sum += pct; counted++; if (pct < threshold) low++; }
    });
    $$("th.session", reg).forEach((th) => {
      const marks = $$(`.mark[data-session="${th.dataset.session}"]`, tbody);
      const p = marks.filter((m) => m.dataset.status === "present").length;
      const el = $(".n", th); if (el) el.textContent = `${p}/${marks.length}`;
    });
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    set("stat-avg", counted ? Math.round(sum / counted) : "—");
    set("stat-low", low);
    const lastTh = $$("th.session", reg).pop();
    if (lastTh) set("stat-last", $(".n", lastTh).textContent);
    const total = rows().length;
    $$("[data-filter] .count").forEach((c) => {
      const f = c.closest("[data-filter]").dataset.filter;
      c.textContent = f === "all" ? total : rows().filter((r) => (f === "low" ? r.dataset.low === "1" : r.dataset.manual === "1")).length;
    });
  }

  /* filter + search */
  let filter = "all";
  const search = $("#register-search");
  function applyFilter() {
    const q = search ? search.value.trim().toLowerCase() : "";
    let shown = 0;
    rows().forEach((tr) => {
      const ok = (!q || tr.dataset.name.includes(q) || tr.dataset.roll.toLowerCase().includes(q)) &&
        (filter === "all" || (filter === "low" && tr.dataset.low === "1") || (filter === "manual" && tr.dataset.manual === "1"));
      tr.classList.toggle("is-hidden", !ok); shown += ok;
    });
    const empty = $(".empty-row", tbody); if (empty) empty.classList.toggle("is-hidden", shown > 0);
  }
  if (search) search.addEventListener("input", applyFilter);
  $$("[data-filter]").forEach((b) => b.addEventListener("click", () => {
    filter = b.dataset.filter;
    $$("[data-filter]").forEach((x) => x.setAttribute("aria-pressed", x === b));
    applyFilter();
  }));

  /* sort */
  $$("th[data-sort] button", reg).forEach((btn) => btn.addEventListener("click", () => {
    const th = btn.closest("th");
    const key = th.dataset.sort;
    const dir = th.getAttribute("aria-sort") === "ascending" ? -1 : 1;
    $$("th[data-sort]", reg).forEach((x) => x.removeAttribute("aria-sort"));
    th.setAttribute("aria-sort", dir === 1 ? "ascending" : "descending");
    const val = (tr) => key === "pct" ? Number(tr.dataset.pct === "" ? -1 : tr.dataset.pct) : (key === "name" ? tr.dataset.name : tr.dataset.roll.toLowerCase());
    const sorted = rows().sort((a, b) => (val(a) > val(b) ? 1 : val(a) < val(b) ? -1 : 0) * dir);
    const empty = $(".empty-row", tbody);
    sorted.forEach((tr) => tbody.insertBefore(tr, empty));
  }));

  /* corrections: optimistic, with undo */
  const label = (m) => (m.dataset.status === "present" ? "P" : "A");
  const dates = {};
  $$("th.session", reg).forEach((th) => { dates[th.dataset.session] = th.dataset.date; });
  function paint(m, status, source) {
    m.dataset.status = status; m.dataset.source = source;
    m.className = `mark ${status}${source === "manual" ? " manual" : ""}`;
    m.textContent = label(m);
    const who = m.closest("tr").dataset.display;
    m.setAttribute("aria-label", `${who}, ${dates[m.dataset.session]}: ${status}${source === "manual" ? ", corrected" : ""}. Activate to mark ${status === "present" ? "absent" : "present"}.`);
    m.title = source === "manual" ? "Corrected manually" : "Recorded by face recognition";
  }
  async function send(m, status) {
    const url = `/sections/${encodeURIComponent(reg.dataset.section)}/sessions/${encodeURIComponent(m.dataset.session)}/students/${encodeURIComponent(m.closest("tr").dataset.roll)}`;
    const res = await fetch(url, { method: "POST", body: new URLSearchParams({ status }), redirect: "manual", credentials: "same-origin" });
    if (!(res.ok || res.type === "opaqueredirect")) throw new Error(String(res.status));
  }
  async function change(m, status, { silent = false } = {}) {
    const prev = { status: m.dataset.status, source: m.dataset.source };
    paint(m, status, "manual"); m.classList.add("is-pending"); recompute();
    try {
      await send(m, status);
      m.classList.remove("is-pending");
      if (!silent) {
        const tr = m.closest("tr");
        toast(`${tr.dataset.display} marked ${status} for ${dates[m.dataset.session]}`, {
          action: "Undo", onAction: () => change(m, prev.status, { silent: true }),
        });
      }
    } catch (err) {
      paint(m, prev.status, prev.source); m.classList.remove("is-pending"); recompute();
      toast("Could not save that correction. Check your connection and try again.");
    }
  }
  reg.addEventListener("click", (e) => {
    const m = e.target.closest(".mark");
    if (!m || m.closest(".legend")) return;
    e.preventDefault(); // the surrounding form is the no-JavaScript fallback
    change(m, m.dataset.status === "present" ? "absent" : "present");
  });

  $$(".mark", tbody).forEach((m) => paint(m, m.dataset.status, m.dataset.source));
  recompute();
  if (wrap) wrap.scrollLeft = wrap.scrollWidth;
})();
