// Akcje aplikacji (docs/HQ.md „Aplikacja”): zwykłe funkcje, które pytają API i wkładają wynik do sklepu. Reduktory są
// czyste w 15-os.js; tu tylko kolejność wywołań, łączenie zapytań i błędy dla właściciela.

// agent z /fleet (surowy fleet.json) w kształcie Agent z GET /agenci, gdy tej trasy nie ma (starszy serwer)
const agentZFloty = (a, i) => ({
  name: a.name, handle: a.handle || "", aliasy: a.aliasy || [], nazwa: a.short || a.title || a.name,
  nazwa_en: (a.en && (a.en.short || a.en.title)) || a.short || a.name, opis: a.description || "",
  opis_en: (a.en && a.en.description) || "", rola: a.rola || "", rola_en: (a.en && a.en.rola) || "", pokoj: a.room || "",
  emoji: a.emoji || "", rodzaj: a.kind || "", barwa: i % 10,
});

// krótka rola agenta w bieżącym języku (fleet.yaml `rola`); bez niej pierwsze zdanie opisu
function rolaAgenta(a) {
  if (!a) return "";
  const r = (!isPL() && a.rola_en) || a.rola;
  if (r) return r;
  const o = String((!isPL() && a.opis_en) || a.opis || "");
  const zdanie = o.split(/(?<=[.!?])\s/)[0] || "";
  return zdanie.length > 90 ? zdanie.slice(0, 88).trimEnd() + "…" : zdanie;
}

// nazwa agenta w bieżącym języku (nieznany agent, np. testowy: nazwa profilu)
function nazwaAgenta(nazwa) {
  const a = sklep.stan().agenci[nazwa];
  if (!a) return nazwa || "";
  return (!isPL() && a.nazwa_en) || a.nazwa || nazwa;
}

const akcje = {
  ustawAgentow(lista) {
    const agenci = {};
    (lista || []).forEach((a, i) => { agenci[a.name] = { barwa: i % 10, ...a }; });
    sklep.ustaw({ agenci, kolejnosc: (lista || []).map((a) => a.name) });
  },

  // pierwsza sesja (docs/HQ.md „Pierwsze spotkanie”): serwer zakłada ją raz na instalację; tu jedno żądanie naraz,
  // potem start aplikacji odświeżony (gotowosc.pierwsza_sesja) i przejście do wątku. Błąd idzie do wołającego.
  zacznijPierwszaSesje() {
    if (akcje._pierwsza) return akcje._pierwsza;
    akcje._pierwsza = (async () => {
      try {
        const r = await api.pierwszaSesja(isPL() ? "pl" : "en");
        sklep.ustaw({ poznanie: null });
        akcje.wczytajAplikacje();
        if (r && r.watek_id) Trasa.idz({ widok: "watek", watek: r.watek_id });
        return r;
      } finally {
        akcje._pierwsza = null;
      }
    })();
    return akcje._pierwsza;
  },

  // start aplikacji: GET /app (agenci, właściciel, gotowość, funkcje); bez tej trasy (404) agenci z /fleet i stan
  // aktualizacji. Inny błąd: pasek „Nie udało się wczytać Jarva” z ponowieniem i samo ponowienie po 2, 4, 8, 15, 30 s.
  async wczytajAplikacje() {
    clearTimeout(akcje._appCzas);
    try {
      const a = await api.aplikacja();
      akcje._appProba = 0;
      akcje.ustawAgentow(a.agenci);
      sklep.ustaw({ wlasciciel: a.wlasciciel || null, gotowosc: a.gotowosc || null, aktualizacja: a.aktualizacja || null,
        decyzje: { liczba: a.decyzje || 0 }, funkcje: a.funkcje || {}, wersja: a.wersja || null, blad_aplikacji: false });
    } catch (e) {
      if (e.status === 401) return;
      if (e.status !== 404) {
        const proba = (akcje._appProba = (akcje._appProba || 0) + 1);
        sklep.ustaw({ blad_aplikacji: true });
        akcje._appCzas = setTimeout(() => akcje.wczytajAplikacje(), [2, 4, 8, 15, 30][Math.min(4, proba - 1)] * 1000);
        return;
      }
      sklep.ustaw({ blad_aplikacji: false });
      const [a, u] = await Promise.all([api.agenci().catch(() => null), api.aktualizacjaStan().catch(() => null)]);
      if (a && a.agenci) akcje.ustawAgentow(a.agenci);
      else {
        const f = await api.flotaAgenci().catch(() => null);
        akcje.ustawAgentow(((f && f.agents) || []).map(agentZFloty));
      }
      if (u) sklep.ustaw({ aktualizacja: u });
    }
  },

  // stan aktualizacji (GET /update): odznaka „⬆ N” w stopce paska i Ustawienia › System
  async wczytajAktualizacje() {
    try { sklep.ustaw({ aktualizacja: await api.aktualizacjaStan() }); } catch (_) { /* dashboard się restartuje: zostaje ostatni stan */ }
  },
  // „Aktualizuj” (§15.3): gdy = "wolne" czeka na koniec pracy agentów, "teraz" prosi pomocnika od razu; cancel odwołuje
  async aktualizuj(action, gdy) {
    try {
      await api.aktualizacja(action, gdy);
      const praca = ((sklep.stan().aktualizacja || {}).praca || {}).aktywne || 0;
      Komunikaty.pokaz(T(action === "cancel" ? "akt.odwolana" : gdy === "wolne" ? "akt.po_pracy_ok" : praca ? "akt.zlecona_praca" : "akt.zlecona"));
      if (action === "update" && gdy !== "wolne") sklep.ustaw((s) => ({ ...s, aktualizacja: { ...(s.aktualizacja || {}), pending: true } }));
      return true;
    } catch (e) { akcje._blad(e); return false; } finally { akcje.wczytajAktualizacje(); }
  },

  // ekran startu: „Czeka na Ciebie” i startery (GET /podpowiedzi); jedno zapytanie naraz, następne zebrane w jedno
  async wczytajPodpowiedzi() {
    if (akcje._podp) { akcje._podpJeszcze = true; return; }
    akcje._podp = true;
    try { sklep.ustaw({ podpowiedzi: await api.podpowiedzi("start") }); } catch (_) { /* start bez podpowiedzi */ } finally {
      akcje._podp = false;
      if (akcje._podpJeszcze) { akcje._podpJeszcze = false; akcje.wczytajPodpowiedzi(); }
    }
  },
  // reakcja na podpowiedź (pokazana, kliknieta, odrzucona, nigdy); klucz = ta sama reakcja raz (np. pokazana raz dziennie)
  reakcja(id, rodzaj, klucz) {
    return api.reakcja(id, rodzaj, klucz).then(() => true, () => false);
  },

  // lista wątków: pierwsza strona albo następna (dopisz); jedno zapytanie naraz, nowsze wyszukiwanie wygrywa
  async wczytajListe({ dopisz = false } = {}) {
    const l = sklep.stan().lista;
    if (dopisz && (!l.dalej || l.laduje)) return;
    const numer = (akcje._lista = (akcje._lista || 0) + 1);
    sklep.zmien("lista", { laduje: true, blad: null });
    try {
      const odp = await api.rozmowy.lista({ filtr: l.filtr, q: l.q.trim(), limit: 50, przed: dopisz ? l.dalej : null });
      if (numer !== akcje._lista) return;
      sklep.ustaw((s) => ({ ...s, lista: Os.listaStrona(s.lista, odp, dopisz) }));
      if (!dopisz && window.performance && performance.mark) performance.mark("jarvo:lista");
    } catch (e) {
      if (numer === akcje._lista) sklep.zmien("lista", { laduje: false, blad: e.tekst ? e.tekst() : String(e) });
    }
  },

  szukaj(q) {
    sklep.zmien("lista", { q });
    clearTimeout(akcje._szukaj);
    akcje._szukaj = setTimeout(() => akcje.wczytajListe(), 250);
  },

  // wątek otwarty w widoku: migawka wątku, osi i aktywnych przebiegów bez rwania (Strumien.migawka)
  // Migawka wątku: wątek, oś i przebiegi z tekstem do chwili `seq`: aktywne, nieudane do ponowienia (karta z „Ponów”
  // po przeładowaniu) i te, które w sklepie wciąż wyglądają na trwające, choć wątek nie słuchał strumienia (przebieg
  // skończył się, gdy był zamknięty: bez tego dymek kręciłby się do przeładowania strony).
  otworzWatek(id) {
    return Strumien.migawka(id, async () => {
      const [w, os] = await Promise.all([api.rozmowy.wez(id), api.rozmowy.os(id)]);
      const ids = new Set((w.watek.przebiegi_aktywne || []).map((p) => p.id));
      for (const p of Object.values(sklep.stan().przebiegi)) if (p.watek_id === id && !Os.KONCOWE.has(p.stan)) ids.add(p.id);
      const pelne = await Promise.all([...ids].map((pid) => api.przebiegi.wez(pid).then((r) => r.przebieg, () => null)));
      return { seq: w.seq, watek: w.watek, os, pelne: pelne.filter(Boolean), ponowienia: w.watek.przebiegi_do_ponowienia || [] };
    }, (r) => sklep.ustaw((s) => ({
      ...s,
      watki: { ...s.watki, [id]: r.watek },
      os: { ...s.os, [id]: Os.osStrona(null, r.os) },
      przebiegi: { ...Os.dodajPrzebiegi(s.przebiegi, r.ponowienia), ...Object.fromEntries(r.pelne.map((p) => [p.id, Os.zMigawki(p)])) },
    })));
  },
  // wyjście z wątku: zakończone przebiegi bez kart (zgoda wygasła, odpowiedź na zgodę) wypadają ze sklepu, żeby nie
  // rósł z każdym otwartym wątkiem; następne otwarcie bierze świeżą migawkę
  zapomnijWatek(id) {
    sklep.ustaw((s) => {
      const zostaja = Object.entries(s.przebiegi).filter(([, p]) => p.watek_id !== id || !Os.KONCOWE.has(p.stan) || p.zgoda_wygasla);
      return zostaja.length === Object.keys(s.przebiegi).length ? s : { ...s, przebiegi: Object.fromEntries(zostaja) };
    });
  },

  // nowe pozycje osi po watek.os / przebieg.koniec: najwyżej jedno zapytanie na wątek, następne zebrane w jedno
  dociagnijOs(id, pelny) {
    const k = (akcje._os = akcje._os || {});
    const st = k[id] || (k[id] = { trwa: false, jeszcze: false, pelny: false });
    st.pelny = st.pelny || !!pelny;
    if (st.trwa) { st.jeszcze = true; return; }
    st.trwa = true;
    const os0 = sklep.stan().os[id], calosc = st.pelny || !os0 || !os0.po;
    st.pelny = false;
    api.rozmowy.os(id, calosc ? {} : { po: os0.po }).then((odp) => {
      sklep.ustaw((s) => ({ ...s, os: { ...s.os, [id]: Os.osStrona(calosc ? null : s.os[id], odp, calosc ? undefined : "po") } }));
    }, () => {}).finally(() => {
      st.trwa = false;
      if (st.jeszcze) { st.jeszcze = false; akcje.dociagnijOs(id); }
    });
  },

  // ------------------------------------------------------------------------------------------- wysyłka
  // Dymek właściciela od razu (wysylane w sklepie), potem POST. Bez wątku (`watek` null): POST /rozmowy z pierwszą
  // wiadomością i przejście do nowego wątku. Ten sam `klucz` przy ponowieniu = ta sama wiadomość na serwerze.
  async wyslij({ watek = null, tekst = "", pliki = [], obrazy = [], adresaci = null, koordynator = "jarvo", klucz = null }) {
    const k = watek || "nowa";
    klucz = klucz || Pisanie.klucz(crypto.getRandomValues(new Uint8Array(16)));
    const o = { klucz, tekst, pliki, obrazy, adresaci, koordynator, ts: Date.now() / 1000, stan: "wysylanie", blad: null };
    const zmienO = (s, f) => ({ ...s.wysylane, [k]: (s.wysylane[k] || []).flatMap((x) => (x.klucz === klucz ? f(x) : [x])) });
    sklep.ustaw((s) => ({ ...s, wysylane: { ...s.wysylane, [k]: (s.wysylane[k] || []).filter((x) => x.klucz !== klucz).concat([o]) } }));
    if (window.performance && performance.mark) performance.mark("jarvo:babel");
    const cialo = { tekst, klucz, zalaczniki: pliki.map((p) => p.path), obrazy: obrazy.map((x) => ({ nazwa: x.nazwa, dane: x.dane })) };
    if (adresaci) cialo.adresaci = adresaci;
    try {
      if (!watek) {
        const odp = await api.rozmowy.utworz({ tytul: "", koordynator, wiadomosc: cialo });
        const id = odp.watek.id;
        sklep.ustaw((s) => ({ ...s, wysylane: zmienO(s, () => []),
          watki: { ...s.watki, [id]: odp.watek },
          os: s.os[id] ? s.os : { ...s.os, [id]: Os.osStrona(null, { pozycje: odp.wpis ? [Os.zWpisu(odp.wpis)] : [] }) },
          przebiegi: Os.dodajPrzebiegi(s.przebiegi, odp.przebiegi), lista: Os.listaZmiana(s.lista, odp.watek) }));
        akcje.ostrzezenia(odp.ostrzezenia, koordynator);
        Fokus.odloz("kompozytor");
        Trasa.idz({ widok: "watek", watek: id });
        return id;
      }
      const odp = await api.rozmowy.wyslij(watek, cialo);
      sklep.ustaw((s) => ({ ...s, wysylane: zmienO(s, () => []),
        os: s.os[watek] && odp.wpis ? { ...s.os, [watek]: Os.osWpis(s.os[watek], odp.wpis) } : s.os,
        przebiegi: Os.dodajPrzebiegi(s.przebiegi, odp.przebiegi) }));
      akcje.ostrzezenia(odp.ostrzezenia, koordynator);
      return watek;
    } catch (e) {
      sklep.ustaw((s) => ({ ...s, wysylane: zmienO(s, (x) => [{ ...x, stan: "blad", blad: e.tekst ? e.tekst() : String(e), kod: e.kod || null }]) }));
      return null;
    }
  },
  ponowWysylke(k, klucz) {
    const o = (sklep.stan().wysylane[k] || []).find((x) => x.klucz === klucz);
    if (o) akcje.wyslij({ ...o, watek: k === "nowa" ? null : k });
  },
  // „Usuń” na nieudanej wiadomości: dymek znika, treść wraca do kompozytora (gdy jest pusty)
  porzucWysylke(k, klucz) {
    const o = (sklep.stan().wysylane[k] || []).find((x) => x.klucz === klucz);
    sklep.ustaw((s) => ({ ...s, wysylane: { ...s.wysylane, [k]: (s.wysylane[k] || []).filter((x) => x.klucz !== klucz) } }));
    if (o) akcje.doKompozytora(k, { tekst: o.tekst, tylkoPusty: true });
  },
  // wiadomość do kompozytora wątku `k` (Odpowiedz, przywrócony tekst, ↑): kompozytor nasłuchuje „jarvo-kompozytor”
  doKompozytora(k, szczegoly) {
    window.dispatchEvent(new CustomEvent("jarvo-kompozytor", { detail: { k, ...szczegoly } }));
  },
  // „Odpowiedz: Web”: wybór adresata na jedną wiadomość w kompozytorze tego wątku
  odpowiedz(watek, agent, panel = 0) {
    sklep.zmien("adresaci", { [`${panel}:${watek || "nowa"}`]: agent });
    akcje.doKompozytora(watek || "nowa", { fokus: true });
  },
  ostrzezenia(lista, koordynator = "jarvo") {
    for (const o of lista || []) {
      const [rodzaj, reszta] = [o.split(":")[0], o.slice(o.indexOf(":") + 1)];
      if (rodzaj === "nieznany") Komunikaty.pokaz(T("wysylka.nieznany", { nazwa: reszta, koord: nazwaAgenta(koordynator) }));
      else if (rodzaj === "dopisz_niemozliwe") Komunikaty.pokaz(T("wysylka.dopisz_niemozliwe"));
      else if (rodzaj === "wielu") Komunikaty.pokaz(T("wysylka.wielu", { n: Number(reszta) || 0 }));
    }
  },

  // ------------------------------------------------------------------------------------------- przebiegi
  _przebieg(p, dodatki) {
    if (p) sklep.ustaw((s) => ({ ...s, przebiegi: Os.scalPrzebieg(s.przebiegi, p, dodatki) }));
  },
  _blad(e) { Komunikaty.pokaz(e && e.tekst ? e.tekst() : String(e), { rodzaj: "blad" }); },
  // Stop (i Esc Esc): wszystkie pracujące przebiegi wątku, także nadzór; kolejka członka czeka (wstrzymane)
  async zatrzymaj(watek) {
    const s = sklep.stan();
    const lista = Os.doZatrzymania(Object.values(s.przebiegi).filter((p) => p.watek_id === watek));
    await Promise.all(lista.map((p) => api.przebiegi.stop(p.id).then((r) => akcje._przebieg(r && r.przebieg), (e) => {
      if (e.kod !== "nieaktywny") akcje._blad(e);
    })));
    return lista.length;
  },
  async zgoda(p, wybor) {
    const z = p.zgoda || {};
    try {
      const r = await api.przebiegi.zgoda(p.id, wybor, z.request_id);
      const a = document.activeElement, wKarcie = !!(a && a.closest && a.closest(".j-zgoda"));
      akcje._przebieg(r && r.przebieg, { zgoda_odp: { wybor, request_id: z.request_id } });
      if (wKarcie) Fokus.odloz(`[data-zgoda-po="${CSS.escape(p.id)}"]`);
    } catch (e) {
      if (e.kod === "zgoda_wygasla") akcje._przebieg({ id: p.id }, { zgoda: { ...z, wygasla: true }, zgoda_wygasla: { ...z, wygasla: true } });
      else akcje._blad(e);
    }
  },
  async ponow(pid) {
    try {
      const r = await api.przebiegi.ponow(pid);
      if (r && r.przebieg) sklep.ustaw((s) => ({ ...s, przebiegi: Os.dodajPrzebiegi(s.przebiegi, [r.przebieg]) }));
    } catch (e) { akcje._blad(e); }
  },
  async wyslijTeraz(pid) {
    try { const r = await api.przebiegi.wyslijTeraz(pid); akcje._przebieg(r && r.przebieg); } catch (e) { akcje._blad(e); }
  },
  async anuluj(pid) {
    try { const r = await api.przebiegi.anuluj(pid); akcje._przebieg(r && r.przebieg); } catch (e) { akcje._blad(e); }
  },

  // ------------------------------------------------------------------------------------------- wątki
  // okno z pytaniem; obietnica z odpowiedzią (null = Anuluj)
  zapytaj(pytanie) {
    return new Promise((ok) => sklep.ustaw({ pytanie: { ...pytanie, odpowiedz: (w) => { sklep.ustaw({ pytanie: null }); ok(w); } } }));
  },
  // archiwum i kosz przy pracy w toku: 409 praca_trwa → „zatrzymać czy zostawić?”, potem to samo z wyborem
  async _zPraca(fn) {
    try { return await fn(undefined); } catch (e) {
      if (e.status !== 409 || e.kod !== "praca_trwa") throw e;
      const praca = await akcje.zapytaj({ rodzaj: "praca", dane: e.dane });
      return praca ? fn(praca) : null;
    }
  },
  _watek(w) {
    if (w) sklep.ustaw((s) => ({ ...s, lista: Os.listaZmiana(s.lista, w), watki: s.watki[w.id] ? { ...s.watki, [w.id]: { ...s.watki[w.id], ...w } } : s.watki }));
  },
  async zmienWatek(id, zmiana) {
    try { const r = await api.rozmowy.zmien(id, zmiana); akcje._watek(r && r.watek); return true; } catch (e) { akcje._blad(e); return false; }
  },
  async archiwizuj(id, archiwum = true) {
    try {
      const r = await akcje._zPraca((praca) => api.rozmowy.zmien(id, praca ? { archiwum, praca } : { archiwum }));
      if (!r) return;
      akcje._watek(r.watek);
      if (archiwum) {
        akcje._poUsunieciu(id);
        Komunikaty.pokaz(T("watek.w_archiwum"), { etykieta: T("ui.cofnij"), akcja: () => akcje.archiwizuj(id, false) });
      }
    } catch (e) { akcje._blad(e); }
  },
  async doKosza(id) {
    try {
      const r = await akcje._zPraca((praca) => api.rozmowy.usun(id, { praca }).then(() => true));
      if (!r) return;
      sklep.ustaw((s) => ({ ...s, lista: Os.listaUsun(s.lista, id) }));
      akcje._poUsunieciu(id);
      Komunikaty.pokaz(T("watek.w_koszu"), { etykieta: T("ui.cofnij"), akcja: () => akcje.przywroc(id) });
    } catch (e) { akcje._blad(e); }
  },
  async usunNaZawsze(id) {
    if (!(await akcje.zapytaj({ rodzaj: "usun" }))) return;
    try {
      await api.rozmowy.usun(id, { trwale: true, praca: "zatrzymaj" });
      sklep.ustaw((s) => ({ ...s, lista: Os.listaUsun(s.lista, id) }));
      akcje._poUsunieciu(id);
    } catch (e) { akcje._blad(e); }
  },
  async przywroc(id) {
    try { const r = await api.rozmowy.przywroc(id); akcje._watek(r && r.watek); } catch (e) { akcje._blad(e); }
  },
  // otwarty wątek zniknął z listy (archiwum, kosz): widok wraca na start
  // fokus: na start (kompozytor) albo na sąsiedni wiersz listy, żeby nie spadł na <body>
  _poUsunieciu(id) {
    if (Trasa.biezaca().watek === id) { Fokus.odloz("kompozytor"); Trasa.idz({ widok: "start" }); return; }
    const a = document.activeElement, wiersz = a && a.closest && a.closest(".j-wiersz-l");
    const zWiersza = wiersz && wiersz.querySelector(`[data-watek="${CSS.escape(id)}"]`);
    if (a && a !== document.body && document.contains(a) && !zWiersza) return;
    const wiersze = [...document.querySelectorAll(".j-wiersz-w[data-watek]")].map((x) => x.dataset.watek);
    const i = wiersze.indexOf(id), obok = wiersze[i + 1] || wiersze[i - 1] || wiersze.find((x) => x !== id);
    Fokus.odloz(obok ? `.j-wiersz-w[data-watek="${CSS.escape(obok)}"]` : "kompozytor");
  },
  filtrListy(filtr) {
    sklep.zmien("lista", { filtr, q: "", porzadek: [], wg_klucza: {}, dalej: null, wczytana: false });
    akcje.wczytajListe();
  },
  async eksport(id) {
    try { const r = await api.rozmowy.eksport(id); pobierzBlob(r.blob, r.nazwa); } catch (e) { akcje._blad(e); }
  },
  podglad(plik) { sklep.ustaw({ podglad: plik || null }); },

  async wczesniejsze(id) {
    const os = sklep.stan().os[id];
    if (!os || !os.przed || os.laduje) return;
    sklep.ustaw((s) => ({ ...s, os: { ...s.os, [id]: { ...s.os[id], laduje: true } } }));
    try {
      const odp = await api.rozmowy.os(id, { przed: os.przed });
      sklep.ustaw((s) => ({ ...s, os: { ...s.os, [id]: Os.osStrona(s.os[id], odp, "przed") } }));
    } catch (_) {
      sklep.ustaw((s) => ({ ...s, os: { ...s.os, [id]: { ...s.os[id], laduje: false } } }));
    }
  },
};
