// Trasy w aplikacji (docs/HQ.md „Aplikacja”): ścieżka dashboardu to dokładnie /jarvo, więc widok niesie hash.
//   #/                     start          #/nowa/<agent>             nowa rozmowa, pierwsza wiadomość do agenta
//   #/r/<watek>            wątek          #/r/<watek>/m/<pozycja>    wątek przewinięty do pozycji
//   #/s/<profil>/<sesja>   obca sesja (tylko odczyt)
//   …?u=<sekcja>[/<pod>]   szuflada ustawień      …?n=<narzędzie>&p=<ścieżka>   narzędzie na pełny ekran
// parsuj/zbuduj są czyste (testy node); reszta dotyka location i sessionStorage.

const Trasa = (() => {
  const WATEK = /^w_[0-9a-f]{21}$/, PROFIL = /^[a-z0-9-]{1,64}$/, SESJA = /^[A-Za-z0-9_.:-]{1,128}$/;
  const POZYCJA = /^[A-Za-z0-9_:.-]{1,200}$/, SEKCJA = /^[a-z0-9-]{1,32}$/;
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
    if (a === "nowa" && PROFIL.test(b || "")) t = { widok: "nowa", agent: b };
    else if (a === "r" && WATEK.test(b || "")) {
      t = { widok: "watek", watek: b };
      if (c === "m" && POZYCJA.test(d || "")) t.pozycja = d;
    } else if (a === "s" && PROFIL.test(b || "") && SESJA.test(c || "")) t = { widok: "sesja", profil: b, sesja: c };
    const [s, pod] = (q.get("u") || "").split("/");
    if (SEKCJA.test(s || "")) { t.u = s; if (SEKCJA.test(pod || "")) t.pod = pod; }
    const n = q.get("n");
    if (NARZEDZIA.includes(n)) { t.n = n; if (q.get("p")) t.p = q.get("p"); }
    return t;
  }

  function zbuduj(t) {
    t = t || {};
    const e = encodeURIComponent;
    let s = "#/";
    if (t.widok === "nowa" && t.agent) s += `nowa/${e(t.agent)}`;
    else if (t.widok === "watek" && t.watek) s += `r/${e(t.watek)}` + (t.pozycja ? `/m/${e(t.pozycja)}` : "");
    else if (t.widok === "sesja" && t.profil && t.sesja) s += `s/${e(t.profil)}/${e(t.sesja)}`;
    const q = [];
    if (t.u) q.push(`u=${e(t.u)}${t.pod ? "/" + e(t.pod) : ""}`);
    if (t.n) { q.push(`n=${e(t.n)}`); if (t.p) q.push(`p=${e(t.p)}`); }
    return q.length ? `${s}?${q.join("&")}` : s;
  }

  // ---- przeglądarka
  const sluchacze = new Set();
  const powiadom = () => sluchacze.forEach((f) => f());
  const biezaca = () => parsuj(location.hash);

  // przejście: obiekt trasy, zmiana częściowa ({...biezaca, ...zmiana}) albo gotowy hash
  function idz(cel, { zastap = false, scal = false } = {}) {
    const hash = typeof cel === "string" ? cel : zbuduj(scal ? { ...biezaca(), ...cel } : cel);
    if (hash === (location.hash || "#/")) return;
    if (zastap) { history.replaceState(history.state, "", location.pathname + location.search + hash); powiadom(); }
    else location.hash = hash;
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
  // Hermes przy wczytaniu strony dopisuje ?profile= i gubi hash, więc link prosto do wątku albo szuflady
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

  return { parsuj, zbuduj, biezaca, idz, sluchaj, zapamietaj, przywroc };
})();

// trasa w komponencie: przerysowanie przy każdej zmianie hasha
function useTrasa() {
  const hash = React.useSyncExternalStore(Trasa.sluchaj, () => location.hash);
  return useMemo(() => Trasa.parsuj(hash), [hash]);
}
