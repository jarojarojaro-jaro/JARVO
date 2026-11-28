// Trasy w aplikacji (docs/HQ.md „Aplikacja”): ścieżka dashboardu to dokładnie /jarvo, więc widok niesie hash.
//   #/                     start          #/nowa[/<agent>]           nowa rozmowa (bez agenta: „Do:” domyślnie Jarvo)
//   #/o/<rozmówca>         stała rozmowa z rozmówcą (klucz f:<profil> albo s:<wpis>, centrum §4)
//   #/r/<watek>            wątek          #/r/<watek>/m/<pozycja>    wątek przewinięty do pozycji
//   #/s/<profil>/<sesja>   obca sesja (tylko odczyt)
//   #/mozg                 Mózg Jarva (pakiet „mozg” na żądanie)
//   #/aktualizacje[/<dzień RRRR-MM-DD>][/<rodzaj>]   Aktualizacje: raporty z dnia (domyślnie najnowszy dzień z raportami),
//                          filtr rodzaju = id zadania crona (pakiet „raporty”)
//   #/os[/<dzień RRRR-MM-DD>]  Oś floty: zadania floty z dnia (domyślnie dziś), pakiet „osfloty”
//   #/ustawienia[/<sekcja>[/<pod>]]   strona Ustawień      …?n=<narzędzie>&p=<ścieżka>   narzędzie na pełny ekran
// parsuj/zbuduj są czyste (testy node); reszta dotyka location i sessionStorage.

const Trasa = (() => {
  const WATEK = /^w_[0-9a-f]{21}$/, PROFIL = /^[a-z0-9-]{1,64}$/, SESJA = /^[A-Za-z0-9_.:-]{1,128}$/;
  const POZYCJA = /^[A-Za-z0-9_:.-]{1,200}$/, SEKCJA = /^[a-z0-9-]{1,32}$/, ROZMOWCA = /^[fs]:[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/;
  const RODZAJ = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/, DZIEN = /^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$/;
  const NARZEDZIA = ["edytor", "animacja", "konwerter", "wiedza"];
  const KLUCZ_PO_LOGOWANIU = "jarvo.po_logowaniu";
  const dekoduj = (s) => { try { return decodeURIComponent(s); } catch (_) { return ""; } };

  function parsuj(hash) {
    const h = String(hash || "").replace(/^#/, "");
    const i = h.indexOf("?");
    const cz = (i < 0 ? h : h.slice(0, i)).split("/").filter(Boolean).map(dekoduj);
    const q = new URLSearchParams(i < 0 ? "" : h.slice(i + 1));
    let t = { widok: "start" };
    const [a, b, c, d] = cz;
    if (a === "nowa" && !b) t = { widok: "nowa" };
    else if (a === "nowa" && PROFIL.test(b || "")) t = { widok: "nowa", agent: b };
    else if (a === "o" && ROZMOWCA.test(b || "")) t = { widok: "rozmowca", rozmowca: b };
    else if (a === "r" && WATEK.test(b || "")) {
      t = { widok: "watek", watek: b };
      if (c === "m" && POZYCJA.test(d || "")) t.pozycja = d;
    } else if (a === "s" && PROFIL.test(b || "") && SESJA.test(c || "")) t = { widok: "sesja", profil: b, sesja: c };
    else if (a === "mozg" && !b) t = { widok: "mozg" };
    else if (a === "os" && (!b || (DZIEN.test(b) && !c))) t = b ? { widok: "os", dzien: b } : { widok: "os" };
    else if (a === "aktualizacje") {
      t = { widok: "aktualizacje" };
      const [dz, rodz] = DZIEN.test(b || "") ? [b, c] : [null, b];
      if (dz) t.dzien = dz;
      if (RODZAJ.test(rodz || "") && !DZIEN.test(rodz)) t.rodzaj = rodz;
    } else if (a === "ustawienia") {
      t = { widok: "ustawienia" };
      if (SEKCJA.test(b || "")) { t.sekcja = b; if (SEKCJA.test(c || "")) t.pod = c; }
    }
    const n = q.get("n");
    if (NARZEDZIA.includes(n)) { t.n = n; if (q.get("p")) t.p = q.get("p"); }
    return t;
  }

  function zbuduj(t) {
    t = t || {};
    const e = encodeURIComponent;
    let s = "#/";
    if (t.widok === "nowa") s += t.agent ? `nowa/${e(t.agent)}` : "nowa";
    else if (t.widok === "rozmowca" && t.rozmowca) s += `o/${e(t.rozmowca).replace(/%3A/g, ":")}`;
    else if (t.widok === "watek" && t.watek) s += `r/${e(t.watek)}` + (t.pozycja ? `/m/${e(t.pozycja)}` : "");
    else if (t.widok === "sesja" && t.profil && t.sesja) s += `s/${e(t.profil)}/${e(t.sesja)}`;
    else if (t.widok === "mozg") s += "mozg";
    else if (t.widok === "os") s += "os" + (t.dzien ? `/${e(t.dzien)}` : "");
    else if (t.widok === "aktualizacje") s += "aktualizacje" + (t.dzien ? `/${e(t.dzien)}` : "") + (t.rodzaj ? `/${e(t.rodzaj)}` : "");
    else if (t.widok === "ustawienia") s += "ustawienia" + (t.sekcja ? `/${e(t.sekcja)}${t.pod ? "/" + e(t.pod) : ""}` : "");
    const q = [];
    if (t.n) { q.push(`n=${e(t.n)}`); if (t.p) q.push(`p=${e(t.p)}`); }
    return q.length ? `${s}?${q.join("&")}` : s;
  }

  // ---- przeglądarka
  const sluchacze = new Set();
  const powiadom = () => sluchacze.forEach((f) => f());
  const biezaca = () => parsuj(location.hash);

  // iPhone i iPad: przesunięcie od lewej krawędzi to systemowe „wstecz” Safari, którego strona nie zatrzyma; z wpisami
  // historii w panelu ten sam ruch otwierał pasek i cofał widok naraz (26.11: „double swipe”). Tam przejścia w panelu
  // zastępują wpis zamiast dokładać nowy, więc krawędź otwiera tylko pasek.
  const bezHistorii = typeof navigator !== "undefined" && (/iPad|iPhone|iPod/.test(navigator.userAgent || "")
    || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1));

  // przejście: obiekt trasy, zmiana częściowa ({...biezaca, ...zmiana}) albo gotowy hash
  function idz(cel, { zastap = false, scal = false } = {}) {
    const hash = typeof cel === "string" ? cel : zbuduj(scal ? { ...biezaca(), ...cel } : cel);
    if (hash === (location.hash || "#/")) return;
    if (zastap || bezHistorii) {
      history.replaceState(zastap ? history.state : null, "", location.pathname + location.search + hash);
      powiadom();
    } else location.hash = hash;
  }
  // linki panelu (#/…) na iPhonie też zastępują wpis: przechwycenie kliknięcia, zanim przeglądarka doda wpis historii
  if (bezHistorii && typeof document !== "undefined") {
    document.addEventListener("click", (e) => {
      const a = e.target && e.target.closest && e.target.closest("a[href^='#/']");
      if (!a || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey
        || (a.target && a.target !== "_self")) return;
      e.preventDefault();
      idz(a.getAttribute("href"));
    });
  }

  function sluchaj(f) {
    if (!sluchacze.size) window.addEventListener("hashchange", powiadom);
    sluchacze.add(f);
    return () => { sluchacze.delete(f); if (!sluchacze.size) window.removeEventListener("hashchange", powiadom); };
  }

  // przed przejściem na logowanie (401) i raz po powrocie z niego
  function zapamietaj() {
    try { sessionStorage.setItem(KLUCZ_PO_LOGOWANIU, location.hash || ""); } catch (_) { /* tryb prywatny */ }
  }
  // Hermes przy wczytaniu strony dopisuje ?profile= i gubi hash, więc link prosto do wątku albo Ustawień
  // (/jarvo#/r/…) otwierałby start. Pierwszy widok dokumentu bierze hash z adresu wczytania (Navigation Timing),
  // tylko gdy dokument wczytano na /jarvo; kolejne wejścia na /jarvo w tym samym dokumencie już nie.
  let startDokumentu = true;
  function hashStartu() {
    if (!startDokumentu) return "";
    startDokumentu = false;
    try {
      const n = performance.getEntriesByType("navigation")[0];
      const u = n && new URL(n.name);
      return u && /\/jarvo\/?$/.test(u.pathname) ? u.hash : "";
    } catch (_) { return ""; }
  }
  function przywroc() {
    let h = "";
    try { h = sessionStorage.getItem(KLUCZ_PO_LOGOWANIU) || ""; sessionStorage.removeItem(KLUCZ_PO_LOGOWANIU); } catch (_) { /* jw. */ }
    h = hashStartu() || h;                                // świeży link wygrywa ze starym hashem sprzed logowania
    if (h && h !== "#/" && (!location.hash || location.hash === "#/")) idz(zbuduj(parsuj(h)), { zastap: true });
  }

  return { parsuj, zbuduj, biezaca, idz, sluchaj, zapamietaj, przywroc, bezHistorii };
})();

// trasa w komponencie: przerysowanie przy każdej zmianie hasha
function useTrasa() {
  const hash = React.useSyncExternalStore(Trasa.sluchaj, () => location.hash);
  return useMemo(() => Trasa.parsuj(hash), [hash]);
}
