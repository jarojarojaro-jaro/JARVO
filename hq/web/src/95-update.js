// Aktualizacje: pozycja w menu bocznym dashboardu (na każdej stronie), gdy na GitHubie jest nowsza wersja.
// Stan i samą aktualizację robi pomocnik na hoście (scripts/updater.py); tu tylko pokazujemy i prosimy.

(function updateWidget() {
  if (typeof document === "undefined" || window.JARVO_HQ_MOCK) return;
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
  panel.setAttribute("aria-label", L("Aktualizacja Jarvo", "Jarvo update"));
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
      if (action === "update") st = { ...st, pending: true, log: L("Czekam na pomocnika aktualizacji…", "Waiting for the update helper…") };
    } catch (e) { err = e.message; }
    busy = false; render();
    setTimeout(load, 2500);
  }

  const justUpdated = () => st && st.state === "done" && (st.finished_at || 0) > pageLoaded;

  function label() {
    if (!st) return null;
    if (st.state === "updating" || (st.pending && st.state !== "done")) return [L("⟳ Aktualizuję…", "⟳ Updating…"), "is-busy"];
    if (justUpdated()) return [L("✓ Odśwież stronę", "✓ Reload page"), "is-done"];
    if (st.state === "failed") return [L("✗ Aktualizacja nieudana", "✗ Update failed"), "is-bad"];
    if (st.state === "stalled") return [L("⚠ Aktualizacja utknęła", "⚠ Update stalled"), "is-bad"];
    if (st.online && st.behind > 0) return [`⬆ ${L("Aktualizacja", "Update")} (${st.behind})`, ""];
    return null;
  }

  function render() {
    if (justUpdated() && !window.__jarvoReloading) { window.__jarvoReloading = true; setTimeout(() => location.reload(), 3000); }
    const l = label();
    item.hidden = !l;
    if (l) { item.textContent = l[0]; item.className = `thq-upd ${l[1]}`.trim(); }
    panel.hidden = !(open && l);
    if (panel.hidden) return;
    panel.replaceChildren();
    const head = el("header", "thq-upd-head");
    head.append(el("h2", null, L("Aktualizacja Jarvo", "Jarvo update")), btn("×", "thq-upd-x", () => { open = false; render(); }));
    panel.append(head);
    if (justUpdated()) {
      // nowa wersja panelu jest już na serwerze: wczytujemy ją sami
      if (!window.__jarvoReloading) { window.__jarvoReloading = true; setTimeout(() => location.reload(), 3000); }
      panel.append(el("p", null, L(`Zaktualizowano do ${st.current}. Za chwilę strona odświeży się sama.`, `Updated to ${st.current}. The page will reload itself in a moment.`)));
      const done = el("div", "thq-upd-actions");
      done.append(btn(L("Odśwież stronę", "Reload page"), "thq-upd-go", () => location.reload()));
      panel.append(done);
      return;
    }
    if (st.state === "stalled") {
      const min = Math.round((st.silent_for || 0) / 60);
      panel.append(el("p", null, L(
        `Pomocnik aktualizacji nie odzywa się od ${min} min (zamknięty terminal/WSL, restart komputera albo zawieszony build). Wersja sprzed aktualizacji dalej działa. Uruchom go ponownie: lokalnie bash scripts/local-up.sh, na serwerze sudo systemctl restart jarvo-updater, i kliknij „Spróbuj ponownie”.`,
        `The update helper has been silent for ${min} min (closed terminal/WSL, reboot or a hung build). The previous version keeps running. Restart it: locally bash scripts/local-up.sh, on a server sudo systemctl restart jarvo-updater, then click "Try again".`)));
    } else if (st.state === "updating" || st.pending) {
      const since = st.started_at ? Math.max(0, Math.round((Date.now() / 1000 - st.started_at) / 60)) : null;
      panel.append(el("p", null, L("Pobieram i wdrażam nową wersję. Panel na chwilę się rozłączy; przebudowa obrazu trwa do kilku minut." + (since != null ? ` Trwa ${since} min.` : ""), "Downloading and deploying the new version. The panel will disconnect briefly; an image rebuild takes up to a few minutes." + (since != null ? ` Running for ${since} min.` : ""))));
    } else if (st.state === "failed") {
      panel.append(el("p", null, L("Aktualizacja się nie udała. Ostatnie linie logu poniżej; wersja sprzed aktualizacji dalej działa.", "The update failed. Last log lines below; the previous version keeps running.")));
    } else {
      panel.append(el("p", null, L(`Gałąź ${st.branch}: ${st.current} → ${st.latest}. Nowe zmiany:`, `Branch ${st.branch}: ${st.current} → ${st.latest}. New changes:`)));
      const ul = el("ul", "thq-upd-list");
      for (const c of st.commits || []) {
        const li = el("li");
        li.append(el("code", null, c.sha), document.createTextNode(" " + c.subject));
        ul.append(li);
      }
      panel.append(ul);
    }
    if (st.log && (st.state === "updating" || st.state === "failed" || st.state === "stalled")) panel.append(el("pre", "thq-upd-log", st.log));
    if (err) panel.append(el("p", "thq-upd-err", err));
    const actions = el("div", "thq-upd-actions");
    if (st.state === "stalled" || (st.state !== "updating" && !st.pending)) {
      actions.append(btn(st.state === "failed" || st.state === "stalled" ? L("Spróbuj ponownie", "Try again") : L("Aktualizuj teraz", "Update now"), "thq-upd-go", () => send("update"), busy));
      actions.append(btn(L("Sprawdź ponownie", "Check again"), "thq-upd-ghost", () => send("check"), busy));
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
