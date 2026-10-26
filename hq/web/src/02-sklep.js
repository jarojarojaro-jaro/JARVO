// Sklep aplikacji (docs/HQ.md „Aplikacja”): jeden obiekt stanu, zmiany przez sklep.ustaw / sklep.zmien,
// odczyt w komponentach przez useSklep(wybór). Reduktory zdarzeń strumienia są czyste i leżą w 15-os.js.
// Ustawienia, układ podziału, szkice i ostatni wątek zostają w localStorage tej przeglądarki.

const Pamiec = {
  wez(klucz, domyslnie) {
    try { const v = localStorage.getItem(klucz); return v == null ? domyslnie : JSON.parse(v); } catch (_) { return domyslnie; }
  },
  daj(klucz, wartosc) {
    try { if (wartosc == null) localStorage.removeItem(klucz); else localStorage.setItem(klucz, JSON.stringify(wartosc)); } catch (_) { /* pełne albo zablokowane */ }
  },
};

function utworzSklep(poczatek) {
  let stan = poczatek;
  const sluchacze = new Set();
  const sklep = {
    stan: () => stan,
    // zmiana: funkcja (stan → nowy stan) albo obiekt scalany płytko z korzeniem
    ustaw(zmiana) {
      const nowy = typeof zmiana === "function" ? zmiana(stan) : { ...stan, ...zmiana };
      if (!nowy || nowy === stan) return;
      stan = nowy;
      sluchacze.forEach((f) => f());
    },
    // płytkie scalenie jednej gałęzi: sklep.zmien("pasek", {otwarty: true}); szuflada ustawień żyje w trasie (?u=)
    zmien(galaz, zmiana) {
      sklep.ustaw((s) => ({ ...s, [galaz]: typeof zmiana === "function" ? zmiana(s[galaz]) : { ...s[galaz], ...zmiana } }));
    },
    subskrybuj(f) { sluchacze.add(f); return () => sluchacze.delete(f); },
  };
  return sklep;
}

const USTAWIENIA_DOMYSLNE = { motyw: "system", szczegoly: false, gestosc: "wygodna", dzwiek: false, powiadomienia: false,
  zapytano_o_powiadomienia: false };

function stanPoczatkowy() {
  return {
    gotowe: false, wersja: null, silnik: null,
    agenci: {}, kolejnosc: [], wlasciciel: null, gotowosc: null,
    // lista wątków (docelowo jednolita lista §10.8): klucz „w:<id>” → {typ: "watek", watek}
    lista: { porzadek: [], wg_klucza: {}, filtr: "rozmowy", q: "", dalej: null, laduje: false, blad: null, wczytana: false },
    adresaci: {},      // "<panel>:<wątek|nowa>" → agent na jedną wiadomość (wybór w kompozytorze)
    os: {},            // wątek → {pozycje, przed, po, pelny, laduje}
    watki: {},         // wątek → Watek (pełny, otwarte wątki)
    przebiegi: {},     // id → Przebieg + tekst, kroki, komentarze, _kursor migawki (+ zgoda_wygasla, zgoda_odp)
    wysylane: {},      // wątek (albo „nowa”) → wiadomości w drodze [{klucz, tekst, pliki, obrazy, adresaci, ts, stan, blad}]
    podglad: null,     // plik w oknie podglądu {path, name, kind, …}
    pytanie: null,     // okno z pytaniem (praca w toku przy archiwum i koszu, trwałe usunięcie, wysyłka do wielu) + odpowiedz(wartość)
    karty: {},         // id karty kanbana → karta pracy z GET /karty (35-karty.js: etap, agent, teraz, wynik)
    decyzje: { liczba: 0 },
    strumien: { stan: "laczy", epoka: null, lider: false, wielokarty: false, nowa_wersja: false },
    podzial: Pamiec.wez("jarvo.podzial.v1", null) || { tryb: "jeden", panele: [], proporcja: 0.5, aktywny: 0 },
    ustawienia: { ...USTAWIENIA_DOMYSLNE, ...(Pamiec.wez("jarvo.ustawienia.v1", null) || {}) },
    szkice: Pamiec.wez("jarvo.szkice.v1", null) || {},
    pasek: { otwarty: false, zwiniety: !!Pamiec.wez("jarvo.pasek_zwiniety", false) },
    toasty: [], aktualizacja: null, stara_baza: false,
    funkcje: {}, blad_aplikacji: false,
    podpowiedzi: null,  // ekran startu: {tryb, podpowiedzi, czeka, wersja} z GET /podpowiedzi
    poznanie: null,     // „trwa”: pierwsze spotkanie otwarte (37-poznajmy.js) do „Do pracy”, „Pomiń” albo „Zrobię to później”
  };
}

const sklep = utworzSklep(stanPoczatkowy());

// zapis do localStorage tylko zmienionych gałęzi; szkice z opóźnieniem 500 ms (pisanie)
(() => {
  let byl = sklep.stan(), czasSzkicow = null;
  sklep.subskrybuj(() => {
    const s = sklep.stan();
    if (s.ustawienia !== byl.ustawienia) Pamiec.daj("jarvo.ustawienia.v1", s.ustawienia);
    if (s.podzial !== byl.podzial) Pamiec.daj("jarvo.podzial.v1", s.podzial);
    if (s.pasek.zwiniety !== byl.pasek.zwiniety) Pamiec.daj("jarvo.pasek_zwiniety", s.pasek.zwiniety || null);
    if (s.szkice !== byl.szkice) {
      clearTimeout(czasSzkicow);
      czasSzkicow = setTimeout(() => Pamiec.daj("jarvo.szkice.v1", sklep.stan().szkice), 500);
    }
    byl = s;
  });
})();

// równość płytka (tablice i obiekty jednego poziomu): wybór zwracający nowy obiekt nie przerysowuje bez potrzeby
function plytko(a, b) {
  if (Object.is(a, b)) return true;
  if (!a || !b || typeof a !== "object" || typeof b !== "object") return false;
  const ka = Object.keys(a), kb = Object.keys(b);
  return ka.length === kb.length && ka.every((k) => Object.is(a[k], b[k]));
}

function useSklep(wybor, rowne = Object.is) {
  const ostatni = useRef(null);
  const migawka = () => {
    const w = wybor(sklep.stan());
    if (ostatni.current && rowne(ostatni.current.w, w)) return ostatni.current.w;
    ostatni.current = { w };
    return w;
  };
  return React.useSyncExternalStore(sklep.subskrybuj, migawka);
}
