// Aktualizacje: pozycja w menu bocznym dashboardu (na każdej stronie), gdy na GitHubie jest nowsza wersja.
// Stan i samą aktualizację robi pomocnik na hoście (scripts/updater.py); tu tylko pokazujemy i prosimy.

(function updateWidget() {
  if (typeof document === "undefined" || window.TARS_HQ_MOCK) return;
  const pageLoaded = Date.now() / 1000;
  let st = null, open = false, busy = false, err = "";

  const item = document.createElement("button");
  item.type = "button";
  item.className = "thq-upd";
  item.hidden = true;
  item.addEventListener("click", () => {
    if (st && st.state === "done" && (st.finished_at || 0) > pageLoaded) { location.reload(); return; }
    open = !open; render();
  });
  const panel = document.createElement("section");
  panel.className = "thq-upd-panel";
  panel.setAttribute("aria-label", "Aktualizacja TARS");
  panel.hidden = true;
  document.body.appendChild(panel);

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function btn(label, cls, onClick, disabled) {
    const b = el("button", cls, label);
    b.type = "button"; b.disabled = !!disabled; b.addEventListener("click", onClick);
    return b;
  }

  async function load() {
    try {
      st = await (await rawFetch(`${API_ROOT}/update`)).json();
    } catch (_) { /* dashboard się restartuje w trakcie aktualizacji: zostaje ostatni stan */ }
    render();
  }
  async function send(action) {
    busy = true; err = ""; render();
    try {
      await rawFetch(`${API_ROOT}/update`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action }),
      });
      if (action === "update") st = { ...st, pending: true, log: "Czekam na pomocnika aktualizacji…" };
    } catch (e) { err = e.message; }
    busy = false; render();
    setTimeout(load, 2500);
  }

  const justUpdated = () => st && st.state === "done" && (st.finished_at || 0) > pageLoaded;

  function label() {
    if (!st) return null;
    if (st.state === "updating" || (st.pending && st.state !== "done")) return ["⟳ Aktualizuję…", "is-busy"];
    if (justUpdated()) return ["✓ Odśwież stronę", "is-done"];
    if (st.state === "failed") return ["✗ Aktualizacja nieudana", "is-bad"];
    if (st.online && st.behind > 0) return [`⬆ Aktualizacja (${st.behind})`, ""];
    return null;
  }

  function render() {
    if (justUpdated() && !window.__tarsReloading) { window.__tarsReloading = true; setTimeout(() => location.reload(), 3000); }
    const l = label();
    item.hidden = !l;
    if (l) { item.textContent = l[0]; item.className = `thq-upd ${l[1]}`.trim(); }
    panel.hidden = !(open && l);
    if (panel.hidden) return;
    panel.replaceChildren();
    const head = el("header", "thq-upd-head");
    head.append(el("h2", null, "Aktualizacja TARS"), btn("×", "thq-upd-x", () => { open = false; render(); }));
    panel.append(head);
    if (justUpdated()) {
      // nowa wersja panelu jest już na serwerze: wczytujemy ją sami
      if (!window.__tarsReloading) { window.__tarsReloading = true; setTimeout(() => location.reload(), 3000); }
      panel.append(el("p", null, `Zaktualizowano do ${st.current}. Za chwilę strona odświeży się sama.`));
      const done = el("div", "thq-upd-actions");
      done.append(btn("Odśwież stronę", "thq-upd-go", () => location.reload()));
      panel.append(done);
      return;
    }
    if (st.state === "updating" || st.pending) {
      panel.append(el("p", null, "Pobieram i wdrażam nową wersję. Panel na chwilę się rozłączy; przebudowa obrazu trwa do kilku minut."));
    } else if (st.state === "failed") {
      panel.append(el("p", null, "Aktualizacja się nie udała. Ostatnie linie logu poniżej; wersja sprzed aktualizacji dalej działa."));
    } else {
      panel.append(el("p", null, `Gałąź ${st.branch}: ${st.current} → ${st.latest}. Nowe zmiany:`));
      const ul = el("ul", "thq-upd-list");
      for (const c of st.commits || []) {
        const li = el("li");
        li.append(el("code", null, c.sha), document.createTextNode(" " + c.subject));
        ul.append(li);
      }
      panel.append(ul);
    }
    if (st.log && (st.state === "updating" || st.state === "failed")) panel.append(el("pre", "thq-upd-log", st.log));
    if (err) panel.append(el("p", "thq-upd-err", err));
    const actions = el("div", "thq-upd-actions");
    if (st.state !== "updating" && !st.pending) {
      actions.append(btn(st.state === "failed" ? "Spróbuj ponownie" : "Aktualizuj teraz", "thq-upd-go", () => send("update"), busy));
      actions.append(btn("Sprawdź ponownie", "thq-upd-ghost", () => send("check"), busy));
    }
    panel.append(actions);
    const log = panel.querySelector(".thq-upd-log");
    if (log) log.scrollTop = log.scrollHeight;
  }

  // pozycja w menu nad sekcją System (Hermes może przerysować menu, więc pilnujemy miejsca)
  function mount() {
    const sys = document.querySelector("aside.fixed > div.shrink-0.flex.flex-col.border-t");
    if (sys && item.nextElementSibling !== sys) sys.parentElement.insertBefore(item, sys);
  }
  setInterval(mount, 1500);
  mount();
  load();
  (function poll() {
    const busyNow = st && (st.state === "updating" || st.pending);
    setTimeout(() => { load().finally(poll); }, busyNow || open ? 3000 : 20000);
  })();
})();
