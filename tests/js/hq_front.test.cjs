// Testy jednostkowe czystych modułów aplikacji Jarvo (hq/web/src): teksty i liczba mnoga, czas, trasy, skróty, motyw,
// sklep, reduktory osi i listy, bezpieczny Markdown (wektory XSS, drzewo, budżet czasu), pomocniki kompozytora i pierwszego spotkania. Bez przeglądarki i bez Reacta: pliki źródłowe sklejone jak w pakiecie i uruchomione
// w osobnym kontekście node:vm. Uruchomienie: `TZ=Europe/Warsaw node tests/js/hq_front.test.cjs` (pytest woła to samo
// w tests/test_hq_front.py). Wynik: „ok <liczba>” albo błąd z nazwą przypadku.
"use strict";
process.env.TZ = process.env.TZ || "Europe/Warsaw";
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert");

const SRC = path.join(__dirname, "..", "..", "hq", "web", "src");
const PLIKI = ["02-sklep.js", "03-trasa.js", "04-i18n.js", "05-skroty.js", "06-tokeny.js", "07-sciezki.js", "12-wzmianki.js",
  "13-markdown.js", "14-czas.js", "15-os.js", "33-komendy.js", "37-poznajmy.js", "64-raporty.js"];
const PRZED = `const React = {}; const useMemo = (f) => f(); const useRef = (v) => ({ current: v }); const useEffect = () => {};
let HQ_LANG = null; const isPL = () => T.wymus !== "en"; const Zasoby = { daj() {} };\n`;
const PO = "\n;({ T, SLOWNIK, Czas, Trasa, Skroty, Motyw, Os, Md, Pisanie, Wzmianki, utworzSklep, stanPoczatkowy, plytko, sklep, USTAWIENIA_DOMYSLNE, Poznanie, kwestiePoznania, Sciezki, kluczDnia, granicyDnia, siatkaMiesiaca, dniKalendarza, koloryRodzajow, cytatRaportu, ukladRaportu, Komendy });";
const kod = PRZED + PLIKI.map((f) => `// ---- ${f}\n` + fs.readFileSync(path.join(SRC, f), "utf8")).join("\n") + PO;
const kontekst = vm.createContext({ Intl, Date, Math, JSON, URLSearchParams, setTimeout, clearTimeout, console, Set, Map,
  encodeURIComponent, decodeURIComponent, Number, String, Object, Array, RegExp });
const M = vm.runInContext(kod, kontekst, { filename: "hq-front.js" });
const { T, SLOWNIK, Czas, Trasa, Skroty, Motyw, Os, Md, Pisanie, Wzmianki, utworzSklep, stanPoczatkowy, plytko, Poznanie, kwestiePoznania, Sciezki, kluczDnia, granicyDnia, siatkaMiesiaca, dniKalendarza, koloryRodzajow, cytatRaportu, ukladRaportu, Komendy } = M;

let ile = 0;
function test(nazwa, f) {
  try { f(); ile++; } catch (e) { console.error(`BŁĄD: ${nazwa}\n${e.stack}`); process.exit(1); }
}
const eq = (a, b) => assert.deepStrictEqual(JSON.parse(JSON.stringify(a)), b);
const ts = (s) => Date.parse(s) / 1000;          // czas lokalny (TZ=Europe/Warsaw) → sekundy

// ------------------------------------------------------------------------------------------------ teksty
test("T: liczba mnoga pl (one/few/many)", () => {
  T.wymus = "pl";
  assert.strictEqual(T("os.kroki", { n: 1 }), "1 krok");
  assert.strictEqual(T("os.kroki", { n: 2 }), "2 kroki");
  assert.strictEqual(T("os.kroki", { n: 5 }), "5 kroków");
  assert.strictEqual(T("os.kroki", { n: 22 }), "22 kroki");
  assert.strictEqual(T("os.kroki", { n: 12 }), "12 kroków");
  assert.strictEqual(T("watek.nieprzeczytane", { n: 3 }), "3 nowe wiadomości");
});
test("T: liczba mnoga en", () => {
  T.wymus = "en";
  assert.strictEqual(T("os.kroki", { n: 1 }), "1 step");
  assert.strictEqual(T("os.kroki", { n: 4 }), "4 steps");
  T.wymus = "pl";
});
test("T: brak klucza = klucz, brak parametru zostaje", () => {
  assert.strictEqual(T("nie.ma.takiego"), "nie.ma.takiego");
  assert.strictEqual(T("start.rano_imie", {}), SLOWNIK.pl["start.rano_imie"]);
  assert.ok(T("start.wieczor_imie", { imie: "Ola" }).includes("Ola"));
});
test("T: oba słowniki mają te same klucze i rodzaj wpisu", () => {
  eq(Object.keys(SLOWNIK.pl).sort(), Object.keys(SLOWNIK.en).sort());
  for (const k of Object.keys(SLOWNIK.pl)) assert.strictEqual(typeof SLOWNIK.pl[k], typeof SLOWNIK.en[k], k);
});

// ------------------------------------------------------------------------------------------------ czas
test("Czas.grupa: dziś, wczoraj, ten tydzień (od poniedziałku), wcześniej", () => {
  const teraz = ts("2026-10-21T12:00:00");          // środa
  assert.strictEqual(Czas.grupa(ts("2026-10-21T00:30:00"), teraz), "dzis");
  assert.strictEqual(Czas.grupa(ts("2026-10-20T23:59:00"), teraz), "wczoraj");
  assert.strictEqual(Czas.grupa(ts("2026-10-19T08:00:00"), teraz), "tydzien");
  assert.strictEqual(Czas.grupa(ts("2026-10-18T22:00:00"), teraz), "wczesniej");
  assert.strictEqual(Czas.grupa(ts("2026-10-21T18:00:00"), teraz), "dzis");      // zegar serwera do przodu
});
test("Czas.grupa: zmiana czasu (25 godzin w niedzielę)", () => {
  const teraz = ts("2026-10-26T12:00:00");          // poniedziałek po zmianie czasu
  assert.strictEqual(Czas.grupa(ts("2026-10-25T01:00:00"), teraz), "wczoraj");
  assert.strictEqual(Czas.grupa(ts("2026-10-24T23:00:00"), teraz), "wczesniej");
});
test("Czas.trwanie i odliczanie", () => {
  assert.strictEqual(Czas.trwanie(43), "0:43");
  assert.strictEqual(Czas.trwanie(3725), "1:02:05");
  assert.strictEqual(Czas.trwanie(-5), "0:00");
  eq(Czas.odliczanie(100, 40), { zostalo: 60, tekst: "1:00", minelo: false });
  assert.strictEqual(Czas.odliczanie(10, 40).minelo, true);
});
test("Czas.wzgledny", () => {
  const t = ts("2026-10-21T12:00:00");
  assert.strictEqual(Czas.wzgledny(t - 10, t), "teraz");
  assert.strictEqual(Czas.wzgledny(t - 300, t), "5 min temu");
  assert.strictEqual(Czas.wzgledny(t - 7200, t), "2 godz. temu");
  assert.strictEqual(Czas.wzgledny(ts("2026-10-20T09:00:00"), t), "wczoraj");
  T.wymus = "en";
  assert.strictEqual(Czas.wzgledny(t - 300, t), "5 min ago");
  T.wymus = "pl";
  assert.strictEqual(Czas.wzgledny(0, t), "");
});

// ------------------------------------------------------------------------------------------------ trasy
const W = "w_0123456789abcdef01234";
test("Trasa.parsuj", () => {
  eq(Trasa.parsuj(""), { widok: "start" });
  eq(Trasa.parsuj("#/"), { widok: "start" });
  eq(Trasa.parsuj(`#/r/${W}`), { widok: "watek", watek: W });
  eq(Trasa.parsuj(`#/r/${W}/m/p_12:3`), { widok: "watek", watek: W, pozycja: "p_12:3" });
  eq(Trasa.parsuj("#/r/w_zle"), { widok: "start" });
  eq(Trasa.parsuj("#/nowa"), { widok: "nowa" });
  eq(Trasa.parsuj("#/nowa/jarvo-web"), { widok: "nowa", agent: "jarvo-web" });
  eq(Trasa.parsuj("#/nowa/Zly!"), { widok: "start" });
  eq(Trasa.parsuj("#/s/jarvo/20261021_abc"), { widok: "sesja", profil: "jarvo", sesja: "20261021_abc" });
  eq(Trasa.parsuj("#/ustawienia/model/klucze"), { widok: "ustawienia", sekcja: "model", pod: "klucze" });
  eq(Trasa.parsuj("#/ustawienia"), { widok: "ustawienia" });
  eq(Trasa.parsuj("#/ustawienia/../x"), { widok: "ustawienia" });
  eq(Trasa.parsuj("#/?u=polaczenia"), { widok: "start" });                         // stare ?u= już nie istnieje
  eq(Trasa.parsuj("#/o/f:hermes"), { widok: "rozmowca", rozmowca: "f:hermes" });
  eq(Trasa.parsuj("#/o/zly"), { widok: "start" });
  eq(Trasa.parsuj("#/mozg"), { widok: "mozg" });
  eq(Trasa.parsuj("#/mozg/x"), { widok: "start" });
  eq(Trasa.parsuj("#/?u=wyglad"), { widok: "start" });                               // dawny ?u= nie otwiera szuflady
  eq(Trasa.parsuj("#/?n=edytor&p=a/b.mp4"), { widok: "start", n: "edytor", p: "a/b.mp4" });
  eq(Trasa.parsuj("#/?n=zlo"), { widok: "start" });
  eq(Trasa.parsuj("#/r/%E0%A4%A"), { widok: "start" });                             // zły zapis % nie wywraca
});
test("Trasa.zbuduj: w obie strony", () => {
  for (const t of [{ widok: "start" }, { widok: "watek", watek: W }, { widok: "watek", watek: W, pozycja: "x_1" },
    { widok: "nowa", agent: "jarvo-web" }, { widok: "sesja", profil: "jarvo", sesja: "s1" },
    { widok: "ustawienia", sekcja: "model", pod: "modele" }, { widok: "rozmowca", rozmowca: "s:omp-1" }, { widok: "mozg" },
    { widok: "watek", watek: W, n: "konwerter", p: "a b.png" }]) {
    eq(Trasa.parsuj(Trasa.zbuduj(t)), t);
  }
  assert.strictEqual(Trasa.zbuduj({ widok: "start" }), "#/");
  assert.strictEqual(Trasa.zbuduj({ widok: "rozmowca", rozmowca: "f:hermes" }), "#/o/f:hermes");
  assert.strictEqual(Trasa.zbuduj({ widok: "ustawienia", sekcja: "konto" }), "#/ustawienia/konto");
  assert.strictEqual(Trasa.zbuduj({ widok: "ustawienia", sekcja: "wyglad" }), "#/ustawienia/wyglad");
});

// ------------------------------------------------------------------------------------------------ skróty
test("Skroty.parsuj i opis", () => {
  eq(Skroty.parsuj("Mod+Shift+O"), { mod: true, shift: true, alt: false, klawisz: "O" });
  assert.strictEqual(Skroty.opis("Mod+Shift+O", false), "Ctrl+Shift+O");
  assert.strictEqual(Skroty.opis("Mod+Shift+O", true), "⌘⇧O");
  assert.strictEqual(Skroty.opis("Alt+ArrowUp", false), "Alt+↑");
  assert.strictEqual(Skroty.opis("Escape", true), "Esc");
});
test("Skroty.pasuje", () => {
  const k = (s) => Skroty.parsuj(s);
  const e = (o) => ({ ctrlKey: false, metaKey: false, shiftKey: false, altKey: false, key: "", code: "", ...o });
  assert.ok(Skroty.pasuje(e({ ctrlKey: true, shiftKey: true, key: "O", code: "KeyO" }), k("Mod+Shift+O"), false));
  assert.ok(!Skroty.pasuje(e({ ctrlKey: true, shiftKey: true, key: "O", code: "KeyO" }), k("Mod+Shift+O"), true));
  assert.ok(Skroty.pasuje(e({ metaKey: true, shiftKey: true, key: "o", code: "KeyO" }), k("Mod+Shift+O"), true));
  assert.ok(!Skroty.pasuje(e({ ctrlKey: true, key: "o", code: "KeyO" }), k("Mod+Shift+O"), false));
  assert.ok(Skroty.pasuje(e({ ctrlKey: true, shiftKey: true, key: "Ó", code: "KeyO" }), k("Mod+Shift+O"), false));
  assert.ok(Skroty.pasuje(e({ key: "/", code: "Slash" }), k("/"), false));
  assert.ok(!Skroty.pasuje(e({ key: "?", shiftKey: true, code: "Slash" }), k("/"), false));     // „?” to nie „/”
  assert.ok(Skroty.pasuje(e({ ctrlKey: true, key: ",", code: "Comma" }), k("Mod+,"), false));
  assert.ok(Skroty.pasuje(e({ ctrlKey: true, key: "/", code: "Slash" }), k("Mod+/"), false));
  assert.ok(Skroty.pasuje(e({ key: "F6" }), k("F6"), false));
  assert.ok(!Skroty.pasuje(e({ key: "F6", shiftKey: true }), k("F6"), false));
  assert.ok(Skroty.pasuje(e({ key: "F6", shiftKey: true }), k("Shift+F6"), false));
  assert.ok(Skroty.pasuje(e({ altKey: true, key: "ArrowUp" }), k("Alt+ArrowUp"), false));
  assert.ok(!Skroty.pasuje(e({ altKey: true, ctrlKey: true, key: "ArrowUp" }), k("Alt+ArrowUp"), false));
});
test("Skroty.dodaj / lista / usunięcie", () => {
  const usun = Skroty.dodaj({ komb: "Mod+K", opis: "skroty.szukaj", akcja: () => {} });
  assert.ok(Skroty.lista().some((s) => s.komb === "Mod+K"));
  usun();
  assert.ok(!Skroty.lista().some((s) => s.komb === "Mod+K"));
});

// ------------------------------------------------------------------------------------------------ motyw
test("Motyw.rozwiaz", () => {
  assert.strictEqual(Motyw.rozwiaz("system", true), "ciemny");
  assert.strictEqual(Motyw.rozwiaz("system", false), "jasny");
  assert.strictEqual(Motyw.rozwiaz("jasny", true), "jasny");
  assert.strictEqual(Motyw.rozwiaz("ciemny", false), "ciemny");
  assert.strictEqual(Motyw.rozwiaz("cokolwiek", true), "ciemny");
});

// ------------------------------------------------------------------------------------------------ sklep
test("utworzSklep: ustaw, zmien, subskrybuj, bez powiadomienia przy tym samym stanie", () => {
  const s = utworzSklep({ a: 1, b: { x: 1, y: 2 } });
  let n = 0;
  const off = s.subskrybuj(() => n++);
  s.ustaw({ a: 2 });
  eq(s.stan(), { a: 2, b: { x: 1, y: 2 } });
  s.zmien("b", { y: 3 });
  eq(s.stan().b, { x: 1, y: 3 });
  s.zmien("b", (b) => ({ ...b, x: 9 }));
  const przed = s.stan();
  s.ustaw((st) => st);
  assert.strictEqual(s.stan(), przed);
  assert.strictEqual(n, 3);
  off();
  s.ustaw({ a: 5 });
  assert.strictEqual(n, 3);
});
test("plytko", () => {
  assert.ok(plytko({ a: 1, b: "x" }, { a: 1, b: "x" }));
  assert.ok(!plytko({ a: 1 }, { a: 1, b: 2 }));
  assert.ok(!plytko({ a: {} }, { a: {} }));
  assert.ok(plytko([1, 2], [1, 2]));
  assert.ok(!plytko(null, {}));
});
test("stanPoczatkowy: kształt sklepu", () => {
  eq(Object.keys(stanPoczatkowy()).sort(), ["adresaci", "agenci", "aktualizacja", "blad_aplikacji", "decyzje", "dostep", "funkcje", "gotowe",
    "gotowosc", "inne_otwarte", "karty", "kolejnosc", "lista", "okno_aktualizacji", "os", "pasek", "podglad", "podpowiedzi", "podzial", "poznanie", "przebiegi", "pytanie", "raporty", "rozmowcy", "silnik",
    "stara_baza", "strumien", "szkice", "toasty", "ustawienia", "watki", "wersja", "wysylane"]);
  eq(stanPoczatkowy().lista.filtr, "rozmowy");
  eq(stanPoczatkowy().ustawienia.motyw, "ciemny");          // motyw TARS: ciemny domyślnie
  eq(Motyw.WYBORY, ["ciemny", "jasny", "system"]);
});

// ------------------------------------------------------------------------------------------------ oś: kursory
test("Os.porownaj", () => {
  assert.ok(Os.porownaj("e1.5", "e1.3") > 0);
  assert.ok(Os.porownaj("e1.3", "e1.5") < 0);
  assert.strictEqual(Os.porownaj("e1.3", "e1.3"), 0);
  assert.ok(Os.porownaj("e2.1", "e1.9") > 0);           // nowa epoka (restart serwera) jest późniejsza
  assert.ok(Os.porownaj(null, "e1.1") < 0);
  assert.ok(Os.porownaj("e1.1", null) > 0);
  assert.ok(Os.porownaj("a.b.10", "a.b.9") > 0);        // epoka z kropką: liczy się ostatnia część
});

// ------------------------------------------------------------------------------------------------ lista wątków
const w = (id, o = {}) => ({ id, tytul: id, aktywnosc_at: 100, przypiety: false, archiwum: false, usuniety_at: null, ...o });
const lista0 = () => stanPoczatkowy().lista;
test("Os.listaStrona: kolejność (przypięte, aktywność, id) i dopisywanie", () => {
  let l = Os.listaStrona(lista0(), { watki: [w("w_a", { aktywnosc_at: 50 }), w("w_b", { aktywnosc_at: 90 }),
    w("w_c", { aktywnosc_at: 10, przypiety: true }), w("w_d", { aktywnosc_at: 90 })], dalej: "k1" });
  eq(l.porzadek, ["w:w_c", "w:w_d", "w:w_b", "w:w_a"]);
  assert.strictEqual(l.dalej, "k1");
  assert.ok(l.wczytana && !l.laduje);
  l = Os.listaStrona(l, { watki: [w("w_e", { aktywnosc_at: 5 })], dalej: null }, true);
  eq(l.porzadek, ["w:w_c", "w:w_d", "w:w_b", "w:w_a", "w:w_e"]);
  assert.strictEqual(l.dalej, null);
  l = Os.listaStrona(l, { watki: [w("w_z")] });
  eq(l.porzadek, ["w:w_z"]);
});
test("Os.listaZmiana: wstawia, przesuwa, usuwa przy archiwizacji, nie dokleja w wyszukiwaniu", () => {
  let l = Os.listaStrona(lista0(), { watki: [w("w_a", { aktywnosc_at: 50 }), w("w_b", { aktywnosc_at: 40 })] });
  l = Os.listaZmiana(l, w("w_b", { aktywnosc_at: 60 }));
  eq(l.porzadek, ["w:w_b", "w:w_a"]);
  l = Os.listaZmiana(l, w("w_n", { aktywnosc_at: 70 }));
  eq(l.porzadek, ["w:w_n", "w:w_b", "w:w_a"]);
  l = Os.listaZmiana(l, w("w_a", { archiwum: true }));
  eq(l.porzadek, ["w:w_n", "w:w_b"]);
  l = Os.listaZmiana(l, w("w_t", { rodzaj: "test" }));
  eq(l.porzadek, ["w:w_n", "w:w_b"]);
  const q = { ...l, q: "faktura" };
  assert.strictEqual(Os.listaZmiana(q, w("w_x", { aktywnosc_at: 99 })), q);
  eq(Os.listaZmiana(q, w("w_b", { tytul: "nowy" })).wg_klucza["w:w_b"].watek.tytul, "nowy");
  eq(Os.listaUsun(l, "w_n").porzadek, ["w:w_b"]);
  assert.strictEqual(Os.listaUsun(l, "w_brak"), l);
  const arch = Os.listaStrona({ ...lista0(), filtr: "archiwum" }, { watki: [] });
  eq(Os.listaZmiana(arch, w("w_a", { archiwum: true })).porzadek, ["w:w_a"]);
  eq(Os.listaZmiana(arch, w("w_b")).porzadek, []);
});

// ------------------------------------------------------------------------------------------------ strony osi
const p = (id, o = {}) => ({ id, rodzaj: "agent", ts: 1, tekst: id, ...o });
test("Os.osStrona: najnowsza, starsze, nowsze, podmiana po id, pełna", () => {
  let os = Os.osStrona(null, { pozycje: [p("a"), p("b")], przed: "kp", po: "kn" });
  eq(os.pozycje.map((x) => x.id), ["a", "b"]);
  eq([os.przed, os.po], ["kp", "kn"]);
  os = Os.osStrona(os, { pozycje: [p("y"), p("z")], przed: "kp2" }, "przed");
  eq(os.pozycje.map((x) => x.id), ["y", "z", "a", "b"]);
  eq([os.przed, os.po], ["kp2", "kn"]);
  os = Os.osStrona(os, { pozycje: [p("b", { tekst: "B2" }), p("c")], po: "kn2" }, "po");
  eq(os.pozycje.map((x) => x.id), ["y", "z", "a", "b", "c"]);
  eq(os.pozycje[3].tekst, "B2");
  eq([os.przed, os.po], ["kp2", "kn2"]);
  os = Os.osStrona(os, { pozycje: [p("q")], pelny: true, po: "kn3" }, "po");
  eq(os.pozycje.map((x) => x.id), ["q"]);
});
test("Os.osWpis: nowy wpis na koniec, znany podmieniony", () => {
  const os = Os.osStrona(null, { pozycje: [p("a")] });
  const wpis = { id: "m1", rodzaj: "wlasciciel", tekst: "hej", utworzony_at: 5 };
  let n = Os.osWpis(os, wpis);
  eq(n.pozycje.map((x) => [x.id, x.rodzaj, x.tekst]), [["a", "agent", "a"], ["m1", "wlasciciel", "hej"]]);
  n = Os.osWpis(n, { ...wpis, tekst: "hej!" });
  eq(n.pozycje.length, 2);
  eq(n.pozycje[1].tekst, "hej!");
  assert.strictEqual(Os.osWpis(undefined, wpis), undefined);
});

// ------------------------------------------------------------------------------------------------ przebiegi
test("Os.zMigawki i przebieg: delty tylko po kursorze migawki", () => {
  const m = Os.zMigawki({ id: "p1", watek_id: W, agent: "jarvo", stan: "pracuje", tekst_dotad: "Ala", kroki_dotad: [], seq: "e1.10" });
  eq([m.tekst, m._kursor, "tekst_dotad" in m], ["Ala", "e1.10", false]);
  let pr = { p1: m };
  pr = Os.przebieg(pr, "przebieg.delta", { id: "p1", tekst: " ma" }, "e1.9");      // starsza: już w migawce
  eq(pr.p1.tekst, "Ala");
  pr = Os.przebieg(pr, "przebieg.delta", { id: "p1", tekst: " kota" }, "e1.11");
  eq(pr.p1.tekst, "Ala kota");
  pr = Os.przebieg(pr, "przebieg.stan", { przebieg: { id: "p1", stan: "czeka_na_zgode" } }, "e1.5");
  eq(pr.p1.stan, "czeka_na_zgode");
  pr = Os.przebieg(pr, "przebieg.narzedzie", { id: "p1", faza: "start", krok: { narzedzie: "terminal", ts: 7, czas_ms: null } }, "e1.12");
  pr = Os.przebieg(pr, "przebieg.narzedzie", { id: "p1", faza: "koniec", krok: { narzedzie: "terminal", ts: 7, czas_ms: 40 } }, "e1.13");
  eq(pr.p1.kroki, [{ narzedzie: "terminal", ts: 7, czas_ms: 40 }]);
  pr = Os.przebieg(pr, "przebieg.koniec", { id: "p1", stan: "blad", blad: { kod: "klucz" } }, "e1.2");
  eq([pr.p1.stan, pr.p1.blad.kod], ["blad", "klucz"]);
  const nowy = Os.przebieg({}, "przebieg.delta", { id: "p2", watek_id: W, agent: "jarvo-web", tekst: "x" }, "e1.1");
  eq([nowy.p2.tekst, nowy.p2.agent, nowy.p2.watek_id], ["x", "jarvo-web", W]);
  const pusty = {};
  assert.strictEqual(Os.przebieg(pusty, "przebieg.delta", { tekst: "x" }, "e1.1"), pusty);
  assert.strictEqual(Os.przebieg(pusty, "przebieg.nieznane", { id: "p3" }, "e1.1"), pusty);
});
test("Os.zastosujZdarzenie", () => {
  const s0 = stanPoczatkowy();
  let s = { ...s0, lista: Os.listaStrona(s0.lista, { watki: [w("w_a")] }), watki: { w_a: w("w_a") },
    os: { w_a: Os.osStrona(null, { pozycje: [] }) } };
  s = Os.zastosujZdarzenie(s, "watek.zmiana", { watek: w("w_a", { tytul: "Nowy", aktywnosc_at: 200 }) }, "e1.1");
  eq([s.lista.wg_klucza["w:w_a"].watek.tytul, s.watki.w_a.tytul], ["Nowy", "Nowy"]);
  s = Os.zastosujZdarzenie(s, "watek.wpis", { watek_id: "w_a", wpis: { id: "m1", rodzaj: "wlasciciel", tekst: "x", utworzony_at: 1 } });
  eq(s.os.w_a.pozycje.map((x) => x.id), ["m1"]);
  s = Os.zastosujZdarzenie(s, "przebieg.delta", { id: "p1", watek_id: "w_a", agent: "jarvo", tekst: "a" }, "e1.2");
  eq(s.przebiegi.p1.tekst, "a");
  s = Os.zastosujZdarzenie(s, "hello", { wersja: "abc", silnik: { stan: "ok" } });
  eq([s.wersja, s.silnik.stan], ["abc", "ok"]);
  s = Os.zastosujZdarzenie(s, "decyzje.zmiana", { liczba: 2 });
  eq(s.decyzje.liczba, 2);
  s = Os.zastosujZdarzenie(s, "watek.usuniety", { id: "w_a" });
  eq(s.lista.porzadek, []);
  assert.strictEqual(Os.zastosujZdarzenie(s, "nieznane", {}), s);
  assert.strictEqual(Os.zastosujZdarzenie(s, "watek.zmiana", null), s);
});

// ------------------------------------------------------------------------------------------------ widok osi
test("Os.widok: kroki zwinięte w trybie Prosty, pełne w Szczegółach", () => {
  const poz = [p("m1", { rodzaj: "wlasciciel" }), p("k1", { rodzaj: "kroki", agent: "jarvo", kroki: [1] }),
    p("k2", { rodzaj: "kroki", agent: "jarvo", kroki: [2, 3] }), p("k3", { rodzaj: "kroki", agent: "jarvo-web", kroki: [4] }),
    p("a1", { agent: "jarvo" })];
  const v = Os.widok(poz, []);
  eq(v.map((x) => x.id), ["m1", "k1", "k3", "a1"]);
  eq(v[1].kroki, [1, 2, 3]);
  eq(Os.widok(poz, [], { szczegoly: true }).map((x) => x.id), ["m1", "k1", "k2", "k3", "a1"]);
});
test("Os.widok: budzenia kart z wątku w karcie pracy, ostatnie „completed” jako koniec", () => {
  // pierwsza sesja 26.10: „Karta … · oddana do oceny” kilka razy pod rząd zamiast jednej karty agenta
  const przek = (n, id) => ({ id: `p${n}`, rodzaj: "przekazanie", ts: n, agent: "jarvo", karta: { task_id: id, tytul: "Audyt", agent: "jarvo-web" } });
  const budz = (n, id, status) => ({ id: `b${n}`, rodzaj: "budzenie", ts: n, agent: "jarvo", budzenie: { task_id: id, status } });
  const handed = "handed off for review; the implementation is done";
  const v = Os.widok([przek(1, "t_a"), przek(2, "t_b"), budz(3, "t_a", handed), budz(4, "t_a", handed), budz(5, "t_a", "completed"),
    budz(6, "t_b", handed), budz(7, "t_x", "completed"), budz(8, "t_a", "completed")], []);
  eq(v.map((x) => `${x.id}:${x.rodzaj}`), ["p1:przekazanie", "p2:przekazanie", "b7:budzenie", "b8:koniec"]);
  eq([...Os.kartyWatku([przek(1, "t_a"), { rodzaj: "przekazanie", karta: { task_id: null } }])], ["t_a"]);
  eq(Os.noweOdTad(v, 1), "b8");
  eq(v[0].koniec_nizej, true);                                                       // wynik w wiadomości niżej
  eq("koniec_nizej" in v[1], false);                                                 // bez niej karta pokazuje wynik
});

test("Os.widok: karty pod wiadomością, która je zapowiada; w trwającej turze od razu pod dymkiem", () => {
  const karta = (n, w) => ({ id: `p${n}`, rodzaj: "przekazanie", ts: n, agent: "jarvo", przebieg_id: "r1", w_toku: !!w,
    karta: { task_id: `t_${n}`, tytul: "x", agent: "jarvo-web" } });
  const kroki = (n, w) => ({ id: `k${n}`, rodzaj: "kroki", ts: n, agent: "jarvo", przebieg_id: "r1", w_toku: !!w, kroki: [n] });
  const wpis = { id: "e1", rodzaj: "wlasciciel", ts: 0 };
  const odp = { id: "a1", rodzaj: "agent", ts: 9, agent: "jarvo", przebieg_id: "r1", tekst: "Web robi audyt" };
  const v = Os.widok([wpis, kroki(1), karta(2), karta(3), kroki(4), odp], []);
  eq(v.map((x) => x.id), ["e1", "a1", "p2", "p3"]);
  eq(v[1].kroki, [1, 4]);
  eq(Os.widok([wpis, kroki(1), karta(2), karta(3), odp], [], { szczegoly: true }).map((x) => x.id), ["e1", "k1", "a1", "p2", "p3"]);
  // tura trwa: kroki w dymku, karty widać od razu pod nim
  const zywy = { id: "r1", stan: "pracuje", wpis_id: "e1", agent: "jarvo", tekst: "" };
  eq(Os.widok([wpis, kroki(1, true), karta(2, true), karta(3, true)], [zywy]).map((x) => x.id), ["e1", "z:r1", "p2", "p3"]);
});

test("Os.widok: trwająca praca pod ostatnim dopiskiem właściciela, nie wyżej w wątku", () => {
  // 24.11: dopisek do trwającej tury stał pod dymkiem, a praca szła dalej nad nim i wyglądało, że agent go nie widzi
  const e1 = { id: "e1", rodzaj: "wlasciciel", ts: 0 };
  const e2 = { id: "e2", rodzaj: "wlasciciel", ts: 5, wpis: { dane: { dopisane_do: "r1" } } };
  const e3 = { id: "e3", rodzaj: "wlasciciel", ts: 6 };
  const zywy = { id: "r1", stan: "pracuje", wpis_id: "e1", agent: "jarvo", tekst: "" };
  eq(Os.widok([e1, e2, e3], [zywy]).map((x) => x.id), ["e1", "e2", "z:r1", "e3"]);
  const dopisek = { id: "r2", stan: "wlaczony", wpis_id: "e3", dopisany_do: "r1", agent: "jarvo" };
  eq(Os.widok([e1, e2, e3], [zywy, dopisek]).map((x) => x.id), ["e1", "e2", "e3", "z:r1"]);
  // tura skończona: odpowiedź ma przebieg ostatniego dopisku (bez `dopisany_do` po wejściu do tury), dymek r1 znika,
  // a odpowiedź stoi pod dopiskami
  const q = { id: "r2", stan: "wlaczony", wpis_id: "e2", agent: "jarvo" };
  const odp = { id: "a1", rodzaj: "agent", ts: 7, agent: "jarvo", przebieg_id: "r2", przebiegi: ["r2"], tekst: "Wnioski" };
  eq(Os.widok([e1, e2, odp], [{ ...zywy, stan: "gotowe", tekst: "Wnioski" }, q]).map((x) => x.id), ["e1", "e2", "a1"]);
});

test("Os.widok: tura z Telegrama to jedna wiadomość, komentarze między narzędziami w krokach", () => {
  // 19.11: link z Telegrama, Jarvo komentował każdy krok („Sprawdzam…”, „Działa…”) i panel pokazał 15 wiadomości
  const wl = { id: "w1", rodzaj: "wlasciciel", ts: 0 };
  const k = (n, ts) => ({ id: `k${n}`, rodzaj: "kroki", ts, agent: "jarvo", kroki: [{ ts, narzedzie: `n${n}` }] });
  const a = (n, ts, tekst, extra = {}) => ({ id: `a${n}`, rodzaj: "agent", ts, agent: "jarvo", tekst, ...extra });
  const poz = [wl, k(1, 10), a(1, 10, "Sprawdzam."), k(2, 20), a(2, 20, "Działa."), a(3, 30, "Wynik: 82/100", { pliki: [{ path: "/r.md" }] }),
    { id: "w2", rodzaj: "wlasciciel", ts: 40 }, a(4, 50, "Następna tura")];
  const v = Os.widok(poz, []);
  eq(v.map((x) => x.id), ["w1", "a3", "w2", "a4"]);
  eq(v[1].tekst, "Wynik: 82/100");
  eq(v[1].ts, 10);                                                                    // nagłówek: początek tury
  eq(v[1].kroki.map((x) => x.komentarz || x.narzedzie), ["Sprawdzam.", "n1", "Działa.", "n2"]);
  eq(v[1].pliki, [{ path: "/r.md" }]);
  eq(Os.krokiPodsumowanie(v[1].kroki).n, 2);                                         // komentarze nie są krokami
  eq(Os.krokiPodsumowanie(v[1].kroki).ostatni.narzedzie, "n2");
  // Szczegóły: każda wiadomość osobno; tura w toku: kroki po ostatnim tekście też idą do wiadomości
  eq(Os.widok(poz, [], { szczegoly: true }).filter((x) => x.rodzaj === "agent").length, 4);
  eq(Os.widok([wl, a(1, 10, "Sprawdzam."), k(2, 20)], []).map((x) => x.id), ["w1", "a1"]);
  // inny przebieg albo prośba o „tak” nie skleja się z poprzednią wiadomością
  eq(Os.widok([wl, a(1, 10, "x", { przebieg_id: "r1" }), a(2, 20, "y", { przebieg_id: "r2" })], []).map((x) => x.id), ["w1", "a1", "a2"]);
  eq(Os.widok([wl, a(1, 10, "x"), a(2, 20, "Zrobić?", { czeka_na_tak: true })], []).map((x) => x.id), ["w1", "a1", "a2"]);
});

test("Os.stabilny i rowneAktywne: delta strumienia nie podmienia niezmienionych pozycji (memo osi, 20.11 „laguje”)", () => {
  const wl = { id: "w1", rodzaj: "wlasciciel", ts: 0 };
  const k = (n, ts) => ({ id: `k${n}`, rodzaj: "kroki", ts, agent: "jarvo", kroki: [{ ts, narzedzie: `n${n}` }] });
  const a = (n, ts, tekst, extra = {}) => ({ id: `a${n}`, rodzaj: "agent", ts, agent: "jarvo", tekst, ...extra });
  const poz = [wl, k(1, 10), a(1, 10, "Sprawdzam."), a(2, 20, "Wynik", { pliki: [{ path: "/r.md" }] }), { id: "w2", rodzaj: "wlasciciel", ts: 40 }];
  const zywy = { id: "p1", wpis_id: "w2", stan: "pracuje", tekst: "pi" };
  const v1 = Os.stabilny(Os.widok(poz, [zywy]), null);
  const mapa = new Map(v1.map((x) => [x.id, x]));
  // nowa delta: sklejona tura liczona od nowa (nowe obiekty kroków z komentarzem) wraca jako ten sam obiekt, dymek nowy
  const v2 = Os.stabilny(Os.widok(poz, [{ ...zywy, tekst: "pisze" }]), mapa);
  eq(v2.map((x) => x.id), ["w1", "a2", "w2", "z:p1"]);
  assert.ok(v2[1] === v1[1] && v2[0] === v1[0] && v2[2] === v1[2]);
  assert.ok(v2[3] !== v1[3]);
  eq(v2[3].przebieg.tekst, "pisze");
  // zmieniona pozycja (nowy tekst albo nowy krok w turze) dostaje nowy obiekt
  const v3 = Os.stabilny(Os.widok(poz.map((x) => (x.id === "a2" ? { ...x, tekst: "Wynik 2" } : x)), [zywy]), mapa);
  assert.ok(v3[1] !== v1[1] && v3[0] === v1[0]);
  const v4 = Os.stabilny(Os.widok([...poz.slice(0, 3), k(2, 15), ...poz.slice(3)], [zywy]), mapa);
  assert.ok(v4[1] !== v1[1]);
  eq(v4[1].kroki.map((x) => x.komentarz || x.narzedzie), ["Sprawdzam.", "n1", "n2"]);
  // pasek pracy: delta tekstu nie zmienia aktywnych przebiegów, zmiana stanu tak
  const p = { id: "p1", stan: "pracuje", agent: "jarvo", tekst: "a" };
  assert.ok(Os.rowneAktywne([p], [{ ...p, tekst: "ab" }]));
  assert.ok(!Os.rowneAktywne([p], [{ ...p, stan: "zatrzymywanie" }]));
  assert.ok(!Os.rowneAktywne([p], []));
});

test("Os.widok: tura omp w toku tylko w dymku, po końcu na osi (20.11: dymek „Kernel 17:21” i ta sama odpowiedź na osi)", () => {
  // oś pliku sesji omp nie zna `w_toku`: pozycje tury niosą tylko przebieg_id/przebiegi partii z panelu
  const wl = { id: "e1", rodzaj: "wlasciciel", ts: 100 };
  const kroki = (id, ts, n) => ({ id, rodzaj: "kroki", ts, agent: "s:gpu", przebieg_id: "p1", przebiegi: ["p1"], kroki: Array.from({ length: n }, (_, i) => ({ ts: ts + i, narzedzie: "bash" })) });
  const poz = [{ id: "o:a0", rodzaj: "agent", ts: 90, agent: "s:gpu", tekst: "Poprzednia tura" }, wl, kroki("o:k1", 101, 60),
    { id: "o:a1", rodzaj: "agent", ts: 200, agent: "s:gpu", tekst: "Move the helper", przebieg_id: "p1", przebiegi: ["p1"] }, kroki("o:a1:k", 200, 12)];
  const p = { id: "p1", wpis_id: "e1", agent: "s:gpu", stan: "pracuje", tekst: "Move the helper", kroki: [{ ts: 101, narzedzie: "bash" }] };
  const v = Os.widok(poz, [p]);
  eq(v.map((x) => x.id), ["o:a0", "e1", "z:p1"]);
  eq(v.filter((x) => String(x.tekst || (x.przebieg && x.przebieg.tekst) || "").includes("Move the helper")).length, 1);
  // koniec przebiegu: dymek znika, cała tura (72 kroki i odpowiedź) stoi na osi raz
  const po = Os.widok(poz, [{ ...p, stan: "gotowe" }]);
  eq(po.map((x) => x.id), ["o:a0", "e1", "o:a1"]);
  eq(po[2].kroki.length, 72);
  // karta pracy z trwającej tury dalej stoi pod dymkiem
  const karta = { id: "o:a1:p1", rodzaj: "przekazanie", ts: 150, agent: "s:gpu", przebieg_id: "p1", przebiegi: ["p1"], karta: { task_id: "t1" } };
  eq(Os.widok([...poz.slice(0, 3), karta, ...poz.slice(3)], [p]).map((x) => x.id), ["o:a0", "e1", "z:p1", "o:a1:p1"]);
});

test("Os.widok: żywy dymek za wpisem, schowane pozycje w toku, koniec po odpowiedzi", () => {
  const poz = [p("m1", { rodzaj: "wlasciciel" }), p("t1", { rodzaj: "agent", przebieg_id: "p1", w_toku: true }), p("m2", { rodzaj: "wlasciciel" })];
  const zywy = { id: "p1", wpis_id: "m1", stan: "pracuje", tekst: "pi" };
  eq(Os.widok(poz, [zywy]).map((x) => x.id), ["m1", "z:p1", "m2"]);
  const bezWpisu = { id: "p2", wpis_id: "brak", stan: "kolejka" };
  eq(Os.widok(poz, [zywy, bezWpisu]).map((x) => x.id), ["m1", "z:p1", "m2", "z:p2"]);
  eq(Os.widok(poz, [{ ...zywy, stan: "dopisany" }]).map((x) => x.id), ["m1", "t1", "m2"]);
  eq(Os.widok(poz, [{ ...zywy, zrodlo: "nadzor" }]).map((x) => x.id), ["m1", "t1", "m2"]);
  const gotowy = { ...zywy, stan: "gotowe", tekst: "pełna" };
  eq(Os.widok(poz, [gotowy]).map((x) => x.id), ["m1", "z:p1", "m2"]);
  const zOdp = poz.concat([p("a1", { rodzaj: "agent", przebieg_id: "p1" })]);
  eq(Os.widok(zOdp, [gotowy]).map((x) => x.id), ["m1", "t1", "m2", "a1"]);
  eq(Os.widok(poz, [{ ...zywy, stan: "zatrzymane", tekst: "" }]).map((x) => x.id), ["m1", "t1", "m2"]);
  // zatrzymany z odpowiedzią na osi: bez dymka, ostatnia pozycja agenta tego przebiegu niesie „Zatrzymane · Ponów”
  const stop = { ...zywy, stan: "zatrzymane", tekst: "Atr" };
  const v = Os.widok(zOdp, [stop]);
  eq(v.map((x) => x.id), ["m1", "t1", "m2", "a1"]);
  eq([!!v[1].zatrzymany, v[3].zatrzymany && v[3].zatrzymany.id], [false, "p1"]);
  eq(Os.widok(poz, [{ ...zywy, stan: "zatrzymane", tekst: "" }])[1].zatrzymany.id, "p1");
  // zatrzymany przed pierwszym słowem i bez pozycji agenta: pusty dymek z „Zatrzymane · Ponów”
  eq(Os.widok([poz[0], poz[2]], [{ ...zywy, stan: "zatrzymane", tekst: "" }]).map((x) => x.id), ["m1", "z:p1", "m2"]);
  // po Ponów (nowy przebieg z ponowienie_z) linia znika
  eq(Os.widok(zOdp, [stop, { id: "p9", wpis_id: "m1", stan: "gotowe", tekst: "x", ponowienie_z: "p1" }]).some((x) => x.zatrzymany), false);
});
test("Os.klasaBledu", () => {
  eq(Os.klasaBledu({ kod: "klucz" }), { rodzaj: "klucz", sekcja: "model", pod: "klucze", ponow: false });
  eq(Os.klasaBledu({ kod: "model" }).pod, "modele");
  eq(Os.klasaBledu({ kod: "limit_bramy" }).rodzaj, "brama");
  eq(Os.klasaBledu(null), { rodzaj: "inny", ponow: true });
});
test("Os.KONCOWE: siedem stanów końcowych i każdy stan ma tekst", () => {
  eq([...Os.KONCOWE].sort(), ["anulowane", "blad", "gotowe", "przerwane", "wlaczony", "zatrzymane", "zgubione"]);
  for (const st of ["kolejka", "wysylanie", "przyjety", "pracuje", "czeka_na_ture", "czeka_na_zgode", "zatrzymywanie",
    "dopisany", ...Os.KONCOWE]) assert.ok(SLOWNIK.pl[`przebieg.${st}`] && SLOWNIK.en[`przebieg.${st}`], st);
});

// ------------------------------------------------------------------------------------------------ oś: wysyłka i zgoda
test("Os.widok: wiadomości w drodze za osią, znikają po wpisie z tym kluczem; ponowiony przebieg schowany", () => {
  const poz = [p("m1", { rodzaj: "wlasciciel", wpis: { klucz: "k1" } })];
  const o1 = { klucz: "k1", tekst: "a", ts: 1 }, o2 = { klucz: "k2", tekst: "b", ts: 2 };
  eq(Os.widok(poz, [], { oczekujace: [o1, o2] }).map((x) => x.id), ["m1", "o:k2"]);
  const blad = { id: "p1", wpis_id: "m1", stan: "blad", tekst: "", blad: { kod: "x" } };
  eq(Os.widok(poz, [blad]).map((x) => x.id), ["m1", "z:p1"]);
  eq(Os.widok(poz, [blad, { id: "p2", wpis_id: "m1", stan: "pracuje", ponowienie_z: "p1" }]).map((x) => x.id), ["m1", "z:p2"]);
  eq(Os.widok(poz, [{ id: "p3", wpis_id: "m1", stan: "przerwane", tekst: "" }]).map((x) => x.id), ["m1", "z:p3"]);
});
test("Os.dodajPrzebiegi: nowy z odpowiedzi, znany zostaje z tekstem ze strumienia", () => {
  const s0 = { p1: { id: "p1", stan: "pracuje", tekst: "Ala ma", kroki: [1], komentarze: [], mysli: [] } };
  const s1 = Os.dodajPrzebiegi(s0, [{ id: "p1", stan: "wysylanie", tekst_dotad: "", seq: "e.1", agent: "a" }, { id: "p2", stan: "kolejka", agent: "b" }]);
  eq(s1.p1.tekst, "Ala ma"); eq(s1.p1.stan, "pracuje"); eq(s1.p1.agent, "a");
  eq(s1.p2.tekst, ""); eq(s1.p2.stan, "kolejka"); assert.ok(!("seq" in s1.p2) && !("tekst_dotad" in s1.p1));
  assert.strictEqual(Os.dodajPrzebiegi(s0, []), s0);
});
test("Os.scalPrzebieg: stan z serwera, tekst zostaje, koniec się nie cofa", () => {
  const s0 = { p1: { id: "p1", stan: "pracuje", tekst: "x", kroki: [], komentarze: [], mysli: [] } };
  const s1 = Os.scalPrzebieg(s0, { id: "p1", stan: "zatrzymywanie", tekst_dotad: "" });
  eq([s1.p1.stan, s1.p1.tekst], ["zatrzymywanie", "x"]);
  const s2 = Os.scalPrzebieg({ p1: { ...s0.p1, stan: "gotowe" } }, { id: "p1", stan: "pracuje" }, { zgoda_odp: { wybor: "once" } });
  eq([s2.p1.stan, s2.p1.zgoda_odp.wybor], ["gotowe", "once"]);
});
test("Os.przebieg: wygasła zgoda zostaje w zgoda_wygasla", () => {
  const z = { request_id: "r1", wygasa_at: 10, wybory: ["once", "deny"] };
  let s = Os.przebieg({}, "przebieg.zgoda", { id: "p1", watek_id: "w", agent: "a", zgoda: z }, "e.1");
  assert.ok(!s.p1.zgoda_wygasla);
  s = Os.przebieg(s, "przebieg.zgoda", { id: "p1", zgoda: { ...z, wygasla: true } }, "e.2");
  s = Os.przebieg(s, "przebieg.koniec", { id: "p1", stan: "gotowe" }, "e.3");
  eq([s.p1.stan, s.p1.zgoda_wygasla.request_id, s.p1.zgoda_wygasla.wygasla], ["gotowe", "r1", true]);
});
test("Os.noweOdTad: n pozycji od agentów od końca, nie dalej niż ostatnia wiadomość właściciela", () => {
  const poz = [p("m1", { rodzaj: "wlasciciel" }), p("a1", { rodzaj: "agent" }), p("k1", { rodzaj: "kroki" }), p("a2", { rodzaj: "agent" }),
    p("m2", { rodzaj: "wlasciciel" }), p("a3", { rodzaj: "agent" }), p("b1", { rodzaj: "budzenie" })];
  eq(Os.noweOdTad(poz, 0), null);
  eq(Os.noweOdTad(poz, 1), "b1");
  eq(Os.noweOdTad(poz, 2), "a3");
  eq(Os.noweOdTad(poz, 5), "a3");
});
test("Os.ryzyko, wyboryZgody, krokiPodsumowanie, doZatrzymania", () => {
  eq(Os.ryzyko({ klucz_wzorca: "rm -rf" }), "usun");
  eq(Os.ryzyko({ opis: "git push --force" }), "wysyla");
  eq(Os.ryzyko({ opis: "ls" }), "inne");
  for (const r of ["usun", "admin", "wysyla", "siec", "restart", "inne"]) assert.ok(SLOWNIK.pl[`zgoda.r_${r}`] && SLOWNIK.en[`zgoda.r_${r}`], r);
  eq(Os.wyboryZgody(["once", "session", "always", "deny"]), { widoczne: ["once", "session", "deny"], wiecej: ["always"] });
  eq(Os.wyboryZgody(null), { widoczne: ["once", "deny"], wiecej: [] });
  for (const w of ["once", "session", "always", "deny"]) assert.ok(SLOWNIK.pl[`zgoda.w_${w}`], w);
  eq(SLOWNIK.pl["zgoda.w_session"], "Zezwól do końca tej odpowiedzi");
  eq(Os.krokiPodsumowanie([{ ts: 10, czas_ms: 1500 }, { ts: 20, blad: true, czas_ms: 2600 }]), { n: 2, sekundy: 4, bledy: 1, ostatni: { ts: 20, blad: true, czas_ms: 2600 } });
  eq(Os.krokiPodsumowanie([{ ts: 10 }, { ts: 70 }]).sekundy, 60);
  eq(Os.doZatrzymania([{ id: 1, stan: "pracuje" }, { id: 2, stan: "gotowe" }, { id: 3, stan: "czeka_na_zgode" }, { id: 4, stan: "kolejka" }]).map((x) => x.id), [1, 3]);
});

// ------------------------------------------------------------------------------------------------ kompozytor
const AGENCI = [{ name: "jarvo", handle: "jarvo", nazwa: "Jarvo" }, { name: "jarvo-web", handle: "web", nazwa: "Web" },
  { name: "jarvo-lowca", handle: "lowca", nazwa: "Łowca", aliasy: ["lowca", "łowca"] }, { name: "jarvo-studio", handle: "studio", nazwa: "Studio" },
  { name: "jarvo-sherlock", handle: "sherlock", nazwa: "Sherlock" }, { name: "stary", handle: "stary", nazwa: "Stary", stan: "archiwum" }];
const ALIASY = Wzmianki.mapaAliasow(AGENCI), NAZWY = Wzmianki.nazwyAgentow(AGENCI);
test("Pisanie.adresat: wiodąca wzmianka wygrywa z wyborem, wybór na jedną wiadomość, środek zdania, nieznany", () => {
  const a = (t, w) => Pisanie.adresat(t, w, ALIASY, "jarvo", NAZWY);
  eq(a("@web popraw stopkę", null), { agenci: ["jarvo-web"], zrodlo: "tekst", adresaci: null, srodek: [], nieznany: null, bezposrednio: true, wielu: false });
  eq(a("@web popraw", "jarvo-studio").agenci, ["jarvo-web"]);
  eq(a("popraw stopkę", "jarvo-studio"), { agenci: ["jarvo-studio"], zrodlo: "wybor", adresaci: ["jarvo-studio"], srodek: [], nieznany: null, bezposrednio: true, wielu: false });
  eq(a("popraw stopkę", "jarvo").zrodlo, null);
  eq(a("niech @web to zrobi", null), { agenci: ["jarvo"], zrodlo: null, adresaci: null, srodek: ["jarvo-web"], nieznany: null, bezposrednio: false, wielu: false });
  eq(a("@nikt hej", null).nieznany, "nikt");
  eq(a("@Łowca szukaj piekarni", null).agenci, ["jarvo-lowca"]);
  // powyżej 3 adresatów kompozytor pyta przed wysłaniem (próg WIELU wspólny z serwerem)
  eq(a("@web @lowca @studio hej", null).wielu, false);
  const cztery = a("@web @lowca @studio @sherlock hej", null);
  eq([cztery.agenci.length, cztery.wielu], [4, true]);
  // z koordynatorem wśród wzmianek idzie tylko do niego: bez pytania
  eq(a("@jarvo @web @lowca @studio @sherlock hej", null).wielu, false);
});
test("Pisanie.wzmiankaPrzyKursorze i wstawWzmianke", () => {
  eq(Pisanie.wzmiankaPrzyKursorze("hej @we", 7), { od: 4, do: 7, q: "we" });
  eq(Pisanie.wzmiankaPrzyKursorze("@", 1), { od: 0, do: 1, q: "" });
  eq(Pisanie.wzmiankaPrzyKursorze("mail@we", 7), null);
  eq(Pisanie.wzmiankaPrzyKursorze("hej @web ", 9), null);
  eq(Pisanie.wzmiankaPrzyKursorze("(@ło", 4), { od: 1, do: 4, q: "ło" });
  eq(Pisanie.wstawWzmianke("hej @we reszta", { od: 4, do: 7 }, "web"), { tekst: "hej @web reszta", kursor: 9 });
  eq(Pisanie.wstawWzmianke("@", { od: 0, do: 1 }, "studio"), { tekst: "@studio ", kursor: 8 });
});
test("Pisanie.podpowiedzi: początek uchwytu, aliasu albo nazwy (bez ogonków), koordynator pierwszy, bez archiwalnych", () => {
  const n = (q) => Pisanie.podpowiedzi(AGENCI.slice().reverse(), q, "jarvo").map((a) => a.name);
  eq(n("lo"), ["jarvo-lowca"]);
  eq(n("Ło"), ["jarvo-lowca"]);
  eq(n("st"), ["jarvo-studio"]);
  eq(n("")[0], "jarvo");
  assert.ok(!n("").includes("stary"));
  eq(Pisanie.podpowiedzi(AGENCI, "", "jarvo", 2).length, 2);
});
test("Pisanie.klucz: 16 znaków z alfabetu klucza serwera", () => {
  const k = Pisanie.klucz(Uint8Array.from({ length: 16 }, (_, i) => i * 17));
  assert.match(k, /^[A-Za-z0-9_-]{16}$/);
  assert.strictEqual(Pisanie.klucz(Uint8Array.from({ length: 16 }, (_, i) => i * 17)), k);
});

// ------------------------------------------------------------------------------------------------ Markdown
const MD = (t) => JSON.parse(JSON.stringify(Md.parsuj(t)));
const wezly = (b, out = []) => {
  for (const x of b || []) { out.push(x); wezly(x.d, out); if (x.el) x.el.forEach((e) => wezly(e.d, out)); if (x.nag) x.nag.forEach((c) => wezly(c, out));
    if (x.wiersze) x.wiersze.forEach((w) => w.forEach((c) => wezly(c, out))); }
  return out;
};
const linki = (t) => wezly(MD(t)).filter((x) => x.t === "link" || x.t === "url" || x.t === "obraz").map((x) => x.href || x.src);
test("Md: drzewo podstawowych konstrukcji", () => {
  eq(MD("# Tytuł\n\nAkapit **gruby** i *kursywa* i `kod` i ~~skreśl~~"), [{ t: "h", n: 1, d: [{ t: "tekst", v: "Tytuł" }] },
    { t: "p", d: [{ t: "tekst", v: "Akapit " }, { t: "b", d: [{ t: "tekst", v: "gruby" }] }, { t: "tekst", v: " i " },
      { t: "i", d: [{ t: "tekst", v: "kursywa" }] }, { t: "tekst", v: " i " }, { t: "kod", v: "kod" }, { t: "tekst", v: " i " },
      { t: "s", d: [{ t: "tekst", v: "skreśl" }] }] }]);
  const b = MD("1. a\n2. b\n   - [x] c\n\n```js\nconst a = 1;\n```\n\n> cyt\n\n---\n\n| A | B |\n|:-|-:|\n| 1 | `x|y` |");
  eq(b.map((x) => x.t), ["lista", "kod", "cytat", "hr", "tabela"]);
  eq([b[0].uporzadkowana, b[0].el.length, b[1].jezyk, b[1].v], [true, 2, "js", "const a = 1;"]);
  eq(wezly(b[0].el[1].d).find((x) => x.t === "lista").el[0].zadanie, true);
  eq([b[4].wyr, b[4].wiersze[0][1]], [["left", "right"], [{ t: "kod", v: "x|y" }]]);
  eq(MD("linia\ndruga")[0].d.map((x) => x.t), ["tekst", "br", "tekst"]);
  eq(MD("snake_case_name")[0].d, [{ t: "tekst", v: "snake_case_name" }]);
});
test("Md: ścieżki floty, MEDIA i 📎 jako karty plików, obraz z dysku floty", () => {
  const p1 = wezly(MD("zobacz /opt/data/jarvo/workspaces/web/a.html."));
  assert.ok(p1.some((x) => x.t === "sciezka" && x.v === "/opt/data/jarvo/workspaces/web/a.html"));
  eq(MD("MEDIA:/opt/data/jarvo/inbox/a.pdf\n📎 /opt/data/jarvo/inbox/b.png"), [{ t: "pliki", sciezki: ["/opt/data/jarvo/inbox/a.pdf", "/opt/data/jarvo/inbox/b.png"] }]);
  assert.ok(!wezly(MD("/etc/passwd i /opt/data/jarvo/../../etc/passwd")).some((x) => x.t === "sciezka"));
  assert.ok(wezly(MD("![x](/opt/data/jarvo/inbox/a.png)")).some((x) => x.t === "obraz_plik"));
});
test("Sciezki: korzeń natywny Windows (litera dysku, „\\” i „/”, spacje, Git Bash) i alias /opt/data", () => {
  const K = "C:/Users/Michał Żółć/AppData/Local/Jarvo/dane";
  const sciezki = (t) => wezly(MD(t)).filter((x) => x.t === "sciezka").map((x) => x.v);
  try {
    eq(sciezki(`zobacz ${K}/jarvo/workspaces/web/a.html`), []);                // bez korzenia z serwera: tylko alias
    Sciezki.ustaw("C:\\Users\\Michał Żółć\\AppData\\Local\\Jarvo\\dane\\");
    eq(Sciezki.korzen(), K);
    eq(sciezki(`zobacz ${K}/jarvo/workspaces/web/a.html.`), [`${K}/jarvo/workspaces/web/a.html`]);
    const ukosniki = "c:\\Users\\Michał Żółć\\AppData\\Local\\Jarvo\\dane\\jarvo\\inbox\\2026-10-24\\foto.png";
    eq(sciezki(`plik: \`${ukosniki}\``), [ukosniki]);
    eq(sciezki("w Git Bash: /c/Users/Michał Żółć/AppData/Local/Jarvo/dane/jarvo/missions/M-1/RAPORT.md"),
      ["/c/Users/Michał Żółć/AppData/Local/Jarvo/dane/jarvo/missions/M-1/RAPORT.md"]);
    eq(sciezki("stara rozmowa: /opt/data/jarvo/workspaces/web/a.html"), ["/opt/data/jarvo/workspaces/web/a.html"]);
    // 24.11: wynik karty z <dane>/kanban/attachments jest ścieżką pliku (karta, podgląd); reszta kanbana nie
    eq(sciezki(`plik ${K}/kanban/attachments/t_962c5ccc/wynik_paczka_3.md i ${K}/kanban/kanban.db`),
      [`${K}/kanban/attachments/t_962c5ccc/wynik_paczka_3.md`]);
    eq(sciezki(`${K}/jarvo/../profiles/.env i D:/Users/Michał Żółć/AppData/Local/Jarvo/dane/jarvo/inbox/x.png`), []);
    eq(MD(`MEDIA:${K}/jarvo/workspaces/wideo/film-końcowy.mp4\n📎 C:\\Users\\inny\\x.pdf`),     // spacja tylko w korzeniu
      [{ t: "pliki", sciezki: [`${K}/jarvo/workspaces/wideo/film-końcowy.mp4`, "C:\\Users\\inny\\x.pdf"] }]);
    eq(Sciezki.krotka(`${K}/jarvo/workspaces/web/a.html`), "workspaces/web/a.html");
    eq(Sciezki.krotka("C:\\Users\\Michał Żółć\\AppData\\Local\\Jarvo\\dane\\jarvo\\inbox\\a.png"), "inbox\\a.png");
    eq(Sciezki.nazwa("C:\\x\\y\\plik.png"), "plik.png");
    eq(Sciezki.naDysk("/opt/data/jarvo/inbox/a.png"), `${K}/jarvo/inbox/a.png`);
    eq(Sciezki.naDysk("/c/Users/x"), "C:/Users/x");
    eq(Sciezki.doSystemu(`${K}/jarvo/inbox/a.png`), "C:\\Users\\Michał Żółć\\AppData\\Local\\Jarvo\\dane\\jarvo\\inbox\\a.png");
    Sciezki.ustaw("/home/ola/.jarvo/dane");                                 // macOS i Linux: bez „\” i bez liter dysku
    eq(sciezki("/home/ola/.jarvo/dane/jarvo/inbox/a.png i C:/x/jarvo/inbox/b.png"), ["/home/ola/.jarvo/dane/jarvo/inbox/a.png"]);
    eq([Sciezki.nazwa("/home/ola/a\\b.png"), Sciezki.naDysk("/c/x")], ["a\\b.png", "/c/x"]);
  } finally {
    Sciezki.ustaw(null);
  }
  eq([Sciezki.korzen(), Sciezki.nazwa("C:\\x\\a.png"), Sciezki.krotka("/opt/data/jarvo/inbox/a.png")], [null, "C:\\x\\a.png", "inbox/a.png"]);
});
test("Md: wektory XSS (linki, obrazy, surowy HTML, encje, rozbite schematy)", () => {
  const zle = ["javascript:alert(1)", "JaVaScRiPt:alert(1)", " javascript:alert(1)", "java\tscript:alert(1)", "data:text/html,<script>alert(1)</script>",
    "vbscript:msgbox(1)", "&#106;avascript:alert(1)", "javascript&colon;alert(1)", "//evil.example/x", "file:///etc/passwd", "\u0001javascript:alert(1)"];
  for (const u of zle) {
    eq(Md.bezpiecznyUrl(u), null);
    eq(linki(`[x](${u})`), []);
    eq(linki(`![x](${u})`), []);
  }
  eq(linki("[x](java\nscript:alert(1))"), []);
  eq(linki("<https://a.pl> [m](mailto:a@b.pl) [h](#/r/w_1) [s](https://a.pl/x?y=1)"), ["https://a.pl", "mailto:a@b.pl", "#/r/w_1", "https://a.pl/x?y=1"]);
  eq(linki("![i](data:image/png;base64,AAAA) ![s](data:image/svg+xml;base64,AAAA) ![r](https://tracker.example/p.gif)"), ["data:image/png;base64,AAAA"]);
  const html = MD("<script>alert(1)</script> <img src=x onerror=alert(1)> <a href=\"javascript:x\">a</a>");
  assert.ok(wezly(html).every((x) => x.t === "p" || x.t === "tekst" || x.t === "br"));
  assert.ok(wezly(html).some((x) => x.t === "tekst" && x.v.includes("<script>")));
  assert.ok(wezly(MD("[a](https://a.pl \"t\" onclick=x)")).every((x) => x.t !== "link" || /^https:\/\/a\.pl/.test(x.href)));
});
test("Md: budżet czasu (≤ 50 ms na 100 KB, z zapasem na wolną maszynę CI) i bardzo długi tekst", () => {
  const wejscia = ["**a ".repeat(25000), "[".repeat(100000), "`".repeat(100000), "*a ".repeat(33000), "# a" + " ".repeat(100000) + "b",
    "```" + "a".repeat(100000) + "`", ">".repeat(100000), "- ".repeat(50000), ("  ".repeat(10) + "- a\n").repeat(5000),
    "|".repeat(3000) + "\n" + "|-".repeat(1500) + "\n", "_a".repeat(50000), "~~a ".repeat(25000), "[a](".repeat(25000),
    "https://a.pl/".repeat(8000), "1. a\n".repeat(20000), "> - > - > - > - a\n".repeat(5000), "![](".repeat(25000), "<".repeat(100000)];
  for (const w of wejscia) {
    const t0 = Date.now();
    Md.parsuj(w);
    const ms = Date.now() - t0;
    assert.ok(ms < 250, `${JSON.stringify(w.slice(0, 12))}…: ${ms} ms`);
  }
  const duzy = "a".repeat(Md.MAKS + 10);
  eq(MD(duzy).map((x) => x.t), ["surowy"]);
});
test("Md: tabela najwyżej 50 kolumn i 10 000 komórek, brakujące komórki puste", () => {
  const wiersz = (n) => "|" + Array.from({ length: n }, (_, i) => `k${i}`).join("|") + "|";
  const sep = (n) => "|" + "-|".repeat(n);
  eq(MD(`${wiersz(50)}\n${sep(50)}\n${wiersz(50)}`)[0].t, "tabela");
  assert.ok(MD(`${wiersz(51)}\n${sep(51)}\n${wiersz(51)}`).every((x) => x.t !== "tabela"));
  const t = MD(`${wiersz(50)}\n${sep(50)}\n${(wiersz(50) + "\n").repeat(400)}`)[0];
  eq(t.t, "tabela");
  assert.ok((t.wiersze.length + 1) * t.nag.length <= 10000, `${t.wiersze.length} wierszy`);
  const krotki = MD("|a|b|c|\n|-|-|-|\n|x|\n")[0];
  eq(krotki.wiersze[0][1], []);
  eq(krotki.wiersze[0][2], []);
});
test("Md.granica: stały początek do ostatniej pustej linii poza blokiem kodu", () => {
  eq(Md.granica("a\n\nb"), 3);
  eq(Md.granica("a\n\nb\n\n```\nx\n\ny"), 6);
  eq(Md.granica("bez pustej linii"), 0);
});

// ------------------------------------------------------------------------------------------------ pierwsze spotkanie
test("Poznanie.link: rodzaj linku z wpisu", () => {
  eq(Poznanie.link("@kometa.pizza"), { rodzaj: "instagram", wartosc: "@kometa.pizza" });
  eq(Poznanie.link("https://www.instagram.com/kometa.pizza/"), { rodzaj: "instagram", wartosc: "@kometa.pizza" });
  eq(Poznanie.link("tiktok.com/@kometa"), { rodzaj: "tiktok", wartosc: "@kometa" });
  eq(Poznanie.link("https://kometapizza.pl/"), { rodzaj: "strona", wartosc: "kometapizza.pl" });
  eq(Poznanie.link("kometapizza.pl,"), { rodzaj: "strona", wartosc: "kometapizza.pl" });
  eq(Poznanie.link("https://maps.app.goo.gl/AbC123"), { rodzaj: "mapy", wartosc: "maps.app.goo.gl/AbC123" });
  eq(Poznanie.link("google.com/maps/place/Kometa"), { rodzaj: "mapy", wartosc: "google.com/maps/place/Kometa" });
  eq(Poznanie.link("google.com/search?q=x"), { rodzaj: "strona", wartosc: "google.com/search?q=x" });
  eq(Poznanie.link("facebook.com/kometapizza"), { rodzaj: "facebook", wartosc: "facebook.com/kometapizza" });
  eq(Poznanie.link("pizzeria"), null);
  eq(Poznanie.link("a b.pl"), null);
  eq(Poznanie.link(""), null);
});

test("Poznanie.linki: z tekstu, bez powtórek, najwyżej 6", () => {
  eq(Poznanie.linki("kometapizza.pl, @kometa.pizza\nKometapizza.pl i coś").map((l) => l.wartosc), ["kometapizza.pl", "@kometa.pizza"]);
  eq(Poznanie.linki(Array.from({ length: 9 }, (_, i) => `s${i}.pl`).join(" ")).length, 6);
});

test("Poznanie.zdanie: rośnie z odpowiedzi, notki pod podkreśleniami", () => {
  eq(Poznanie.zdanie({ imie: "" }), []);
  const tekst = (k) => k.map((x) => x.t).join("");
  eq(tekst(Poznanie.zdanie({ imie: "Kuba" })), "Cześć, jestem Kuba.");
  const pelne = Poznanie.zdanie({ imie: "Kuba", firma: "Pizzeria Kometa", zajecie: "pizzeria w Krakowie",
    linki: [{ rodzaj: "strona", wartosc: "kometapizza.pl" }, { rodzaj: "instagram", wartosc: "@kometa.pizza" }],
    cele: ["Więcej klientów", "Rolki i filmy", "Nowa strona"] });
  eq(tekst(pelne), "Cześć, jestem Kuba. Mam firmę Pizzeria Kometa: pizzeria w Krakowie. Znajdziesz mnie tu: kometapizza.pl i "
    + "@kometa.pizza. Zależy mi na: Więcej klientów, Rolki i filmy i Nowa strona.");
  eq(pelne.filter((x) => x.notka).map((x) => x.notka), ["imie", "firma", "zajecie", "strona", "instagram", "cel", "cel", "cel"]);
  eq(tekst(Poznanie.zdanie({ imie: "Ola", zajecie: "fotografia" }, false)), "Hi, I'm Ola. What I do: fotografia.");
  eq(Poznanie.imie("  Kuba!  "), "Kuba");
  eq(Poznanie.pole("a\u0000b\n  c", 80), "a b c");
});

test("kwestiePoznania: każdy krok ma tekst w obu językach, notki mają klucze", () => {
  for (const jezyk of ["pl", "en"]) {
    T.wymus = jezyk;
    for (const k of ["witaj", "imie", "firma", "linki", "cele", "mozg"]) {
      for (const [model, zapisane, start] of [[true, false, false], [false, false, false], [false, true, false], [true, true, true]]) {
        const z = kwestiePoznania(k, { imie: "Kuba", model, zapisane, start }, 9);
        assert.ok(z.length && z.every((x) => x && !/^poz\./.test(x) && !/\{/.test(x)), `${jezyk} ${k}: ${z}`);
      }
    }
    for (const n of ["imie", "firma", "zajecie", "strona", "instagram", "facebook", "tiktok", "youtube", "linkedin", "mapy", "inne", "cel"])
      assert.ok(!/^poz\./.test(T(`poz.notka.${n}`)), n);
    for (const c of ["klienci", "rolki", "strona", "reklamy", "papiery"]) assert.ok(!/^poz\./.test(T(`poz.cel.${c}`)), c);
  }
  T.wymus = "pl";
  eq(kwestiePoznania("witaj", {}, 9)[1].startsWith("Szefuję zespołowi 9 agentów."), true);
});

test("kwestiePoznania mózg: zapis, brak mózgu, start pierwszej sesji; teksty karty mózgu w obu językach", () => {
  T.wymus = "pl";
  eq(kwestiePoznania("mozg", { zapisane: true }, 9), ["Zapisałem. Teraz wiem, dla kogo pracuję.", T("poz.mozg")]);
  eq(kwestiePoznania("mozg", {}, 9), [T("poz.mozg")]);
  eq(kwestiePoznania("mozg", { model: true, start: true }, 9), ["Mam mózg. Zaczynam pierwszą sesję."]);
  for (const jezyk of ["pl", "en"]) {
    T.wymus = jezyk;
    for (const k of ["mam_mozg", "otwieram", "etykieta", "mozg_wybor", "ponow", "chatgpt_zaloguj", "chatgpt_jak", "chatgpt_krok1",
      "chatgpt_otworz", "chatgpt_krok2", "chatgpt_kopiuj", "chatgpt_skopiowane", "chatgpt_czekam", "chatgpt_laczy", "chatgpt_wygasl",
      "chatgpt_blad", "klucz_etykieta", "klucz_przyklad", "klucz_podlacz", "klucz_nieznany", "klucz_brak"])
      assert.ok(!/^poz\./.test(T(`poz.${k}`)), `${jezyk} poz.${k}`);
    assert.ok(!/\{/.test(T("poz.klucz_sprawdzam", { nazwa: "OpenAI" })), jezyk);
    for (const k of ["model_sesja", "pierwsza", "pierwsza_zacznij", "pierwsza_nie"]) assert.ok(!/^gotowosc\./.test(T(`gotowosc.${k}`)), `${jezyk} gotowosc.${k}`);
  }
  T.wymus = "pl";
});

test("Poznanie.dostawca: jak mozg.rozpoznaj na serwerze (przedrostek, kształt)", () => {
  const x = (n) => "x".repeat(n);
  eq(Poznanie.dostawca(`sk-or-v1-${x(40)}`), "OpenRouter");
  eq(Poznanie.dostawca(`sk-ant-api03-${x(40)}`), "Anthropic");
  eq(Poznanie.dostawca(`sk-proj-${x(40)}`), "OpenAI");
  eq(Poznanie.dostawca(`  sk-${x(30)}\n`), "OpenAI");
  eq(Poznanie.dostawca("sk-krotki"), null);
  eq(Poznanie.dostawca(`AIza${x(35)}`), null);
  eq(Poznanie.dostawca(`sk-${x(20)} ${x(20)}`), null);
  eq(Poznanie.dostawca(`sk-${x(400)}`), null);
  eq(Poznanie.dostawca(""), null);
});

test("Aktualizacje: trasa z dniem i rodzajem, dni kalendarza, kolory rodzajów, cytat do odpowiedzi", () => {
  eq(Trasa.parsuj("#/aktualizacje"), { widok: "aktualizacje" });
  eq(Trasa.parsuj("#/aktualizacje/jarvo-patrol"), { widok: "aktualizacje", rodzaj: "jarvo-patrol" });
  eq(Trasa.parsuj("#/aktualizacje/2026-11-18"), { widok: "aktualizacje", dzien: "2026-11-18" });
  eq(Trasa.parsuj("#/aktualizacje/2026-11-18/jarvo-patrol"), { widok: "aktualizacje", dzien: "2026-11-18", rodzaj: "jarvo-patrol" });
  eq(Trasa.parsuj("#/aktualizacje/2026-13-40"), { widok: "aktualizacje", rodzaj: "2026-13-40" });
  eq(Trasa.parsuj("#/aktualizacje/..%2Fx"), { widok: "aktualizacje" });
  assert.strictEqual(Trasa.zbuduj({ widok: "aktualizacje", rodzaj: "jarvo-daily-brief" }), "#/aktualizacje/jarvo-daily-brief");
  assert.strictEqual(Trasa.zbuduj({ widok: "aktualizacje", dzien: "2026-11-18", rodzaj: "jarvo-patrol" }), "#/aktualizacje/2026-11-18/jarvo-patrol");
  // dzień w strefie przeglądarki, także w dniu zmiany czasu (25 h): północ do północy
  assert.strictEqual(kluczDnia(ts("2026-11-18T23:59")), "2026-11-18");
  const zmiana = granicyDnia("2026-10-25");
  eq([zmiana.od, zmiana.przed - zmiana.od], [ts("2026-10-25T00:00"), 25 * 3600]);
  // siatka od poniedziałku, pełne tygodnie: listopad 2026 zaczyna się w niedzielę (6 dni października przed nim)
  const s11 = siatkaMiesiaca(2026, 10);
  eq([s11.length, s11[0].klucz, s11[6].klucz, s11[0].wMiesiacu, s11[6].wMiesiacu, s11[s11.length - 1].klucz], [42, "2026-10-26", "2026-11-01", false, true, "2026-12-06"]);
  assert.strictEqual(siatkaMiesiaca(2027, 1).length, 28);           // luty 2027: od poniedziałku, 4 tygodnie
  const w = (kiedy, rodzaj, nowy = false, blad = false) => ({ ts: ts(kiedy), rodzaj, nowy, blad });
  const dni = dniKalendarza([w("2026-11-18T07:50", "brief"), w("2026-11-18T14:47", "patrol", true), w("2026-11-18T19:00", "patrol", true, true), w("2026-11-17T07:50", "brief")]);
  eq(dni["2026-11-18"], { liczba: 3, nowe: 2, blad: true, rodzaje: ["brief", "patrol"] });
  eq(dni["2026-11-17"], { liczba: 1, nowe: 0, blad: false, rodzaje: ["brief"] });
  // kolory: stałe po id, różne dla różnych rodzajów
  const k = koloryRodzajow(["jarvo-patrol", "jarvo-daily-brief", "jarvo-weekly-review", "jarvo-patrol"]);
  eq(Object.keys(k).sort(), ["jarvo-daily-brief", "jarvo-patrol", "jarvo-weekly-review"]);
  assert.strictEqual(new Set(Object.values(k)).size, 3);
  assert.strictEqual(koloryRodzajow(["jarvo-patrol", "jarvo-daily-brief"])["jarvo-patrol"], k["jarvo-patrol"]);
  // cytat: rodzaj, numer briefu i czas, bez treści raportu; dziś sama godzina
  const r = { nazwa: "Patrol floty", ts: ts("2026-11-18T14:47"), tekst: "\n## ✅ **Monid** — oceniony\n\nreszta" };
  T.wymus = "pl";
  assert.strictEqual(cytatRaportu(r, ts("2026-11-18T20:00")), "> Odpowiadam na „Patrol floty” (14:47)\n\n");
  assert.strictEqual(cytatRaportu({ nazwa: "Poranny brief", ts: ts("2026-11-18T07:54"), tekst: "☀️ Brief B-2026-11-18 · Dzień dobry" },
    ts("2026-11-18T20:00")), "> Odpowiadam na „Poranny brief” B-2026-11-18 (07:54)\n\n");
  T.wymus = null;
  let s = stanPoczatkowy();
  s = Os.zastosujZdarzenie(s, "raporty.nowe", { nieprzeczytane: 3 });
  eq(s.raporty, { nieprzeczytane: 3, wersja: 1 });
  eq(Os.zastosujZdarzenie(s, "raporty.licznik", { nieprzeczytane: 0 }).raporty, { nieprzeczytane: 0, wersja: 1 });
});
test("ukladRaportu: sekcje z etykiet linii, decyzje z pogrubionym pytaniem i rekomendacją, treść bez zmian", () => {
  const brief = "☀️ Brief B-2026-11-21 · Dzień dobry. Stan floty:\nGotowe od wczoraj: 48 kart domkniętych.\nW toku: AssemblyAI (3 konta).\n"
    + "Czeka na Ciebie (5 decyzji):\n1. Monid: prosić ich o wynik testowy? Rekomenduję tak. Wisi od 3 dni.\n2. Już **pogrubione** zostaje\n"
    + "```\nUwaga: w kodzie bez zmian\n```\nOdpowiedz np. „1 ok”.";
  const u = ukladRaportu(brief);
  assert.ok(u.startsWith("☀️ Brief B-2026-11-21 · Dzień dobry. Stan floty:\n\n**Gotowe od wczoraj:** 48 kart domkniętych.\n\n**W toku:** AssemblyAI"), u);
  assert.ok(u.includes("#### Czeka na Ciebie (5 decyzji):\n\n1. **Monid: prosić ich o wynik testowy?** *Rekomenduję tak*. Wisi od 3 dni."), u);
  assert.ok(u.includes("2. Już **pogrubione** zostaje") && u.includes("```\nUwaga: w kodzie bez zmian\n```"), u);
  // bez znaczników Markdown treść jest ta sama (układ tylko dokłada pogrubienia, wyróżnienia, nagłówki i puste linie)
  const czysty = (t) => t.replace(/\*+|^#### /gm, "").replace(/\s+/g, " ").trim();
  assert.strictEqual(czysty(u), czysty(brief));
  assert.strictEqual(ukladRaportu(""), "");
});

// ------------------------------------------------------------------------------------------------ komendy po „/”
test("Komendy: komenda czy zwykły tekst (wektory wspólne z komendy.py), menu przy pisaniu nazwy", () => {
  const W = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "data", "komendy.json"), "utf8"));
  for (const [tekst, [nazwa, args]] of W.komendy) eq(Komendy.parsuj(tekst), { nazwa, args });
  for (const tekst of W.tekst) assert.strictEqual(Komendy.parsuj(tekst), null, JSON.stringify(tekst));
  assert.strictEqual(Komendy.pisana("/"), "");
  assert.strictEqual(Komendy.pisana("/Mo"), "mo");
  assert.strictEqual(Komendy.pisana("/model "), null);
  assert.strictEqual(Komendy.pisana("hej"), null);
  const lista = [
    { nazwa: "model", aliasy: [], panel: true, dziala: true }, { nazwa: "new", aliasy: ["reset"], panel: true, dziala: true },
    { nazwa: "compress", aliasy: ["compact"], panel: true, dziala: false }, { nazwa: "retry", aliasy: [], panel: false, dziala: false },
  ];
  eq(Komendy.podpowiedzi(lista, "").map((c) => c.nazwa), ["model", "new", "compress"]);    // sam „/”: bez reszty rejestru
  eq(Komendy.podpowiedzi(lista, "re").map((c) => c.nazwa), ["new", "retry"]);               // alias /reset i rejestr Hermesa
  eq(Komendy.podpowiedzi(lista, "x"), []);
  assert.strictEqual(Komendy.komendaModelu({ model: "gpt-5.4", provider: "openai-codex" }), "/model gpt-5.4 --provider openai-codex");
  assert.strictEqual(Komendy.komendaModelu({ model: "anthropic/claude-opus-5", provider: "" }), "/model anthropic/claude-opus-5");
  assert.ok(Komendy.zWpisu({ wpis: { dane: { typ: "komenda" } } }) && !Komendy.zWpisu({ wpis: { dane: { typ: "dolaczyl" } } }));
});

// ------------------------------------------------------------------------------------------------ okna i wersja
test("Bezwladnosc: otwarte okno nigdy nie usypia samego siebie (20.11: X i Anuluj w oknie aktualizacji)", () => {
  const wezel = (rodzic) => {
    const e = { rodzic, atr: new Set() };
    e.contains = (x) => { for (let y = x; y; y = y.rodzic) if (y === e) return true; return false; };
    e.toggleAttribute = (n, t) => { if (t) e.atr.add(n); else e.atr.delete(n); };
    e.querySelector = (s) => (s === ".j-glowna" ? glowna : null);
    return e;
  };
  const korzen = wezel(null), uklad = wezel(korzen), glowna = wezel(uklad), widok = wezel(glowna);
  const document = { querySelector: (s) => (s === "[data-jarvo-korzen] > .j-uklad" ? uklad : null),
    addEventListener() {}, removeEventListener() {} };
  const { Bezwladnosc } = vm.runInContext(fs.readFileSync(path.join(SRC, "20-ui.js"), "utf8") + "\n;({ Bezwladnosc });",
    vm.createContext({ document, React: { Component: class {} }, setTimeout, clearTimeout }), { filename: "20-ui.js" });
  const spi = (e) => e.atr.has("inert");
  const obokUkladu = wezel(korzen), wWidoku = wezel(widok);
  Bezwladnosc.okno(obokUkladu, true);                // okno w korzeniu (OknoPytania, OknoAktualizacji): układ śpi
  assert.ok(spi(uklad));
  Bezwladnosc.okno(obokUkladu, false);
  assert.ok(!spi(uklad));
  Bezwladnosc.okno(wWidoku, true);                   // okno w widoku Ustawień: przodkowie okna bez inert
  assert.ok(!spi(uklad) && !spi(glowna));
  Bezwladnosc.pasek(true);                           // wysunięty pasek na telefonie też nie usypia okna w głównej
  assert.ok(!spi(glowna));
  Bezwladnosc.okno(wWidoku, false);
  assert.ok(spi(glowna));
  Bezwladnosc.pasek(false);
  Bezwladnosc.warstwa(true);
  assert.ok(spi(uklad));
  Bezwladnosc.warstwa(false);
  assert.ok(!spi(uklad) && !spi(glowna));
});
test("WERSJA_PAKIETU: skrót rdzenia app-rdzen-<12 hex>.js (20.11: „Wersja Jarva” = „—”)", () => {
  const blok = /const WERSJA_PAKIETU = \(\(\) => \{[\s\S]*?\}\)\(\);/.exec(fs.readFileSync(path.join(SRC, "11-strumien.js"), "utf8"))[0];
  const wersja = (src) => vm.runInContext(`${blok}\nWERSJA_PAKIETU`, vm.createContext({ document: { currentScript: { src } } }));
  assert.strictEqual(wersja("http://127.0.0.1:9119/dashboard-plugins/jarvo-hq/dist/zasoby/app-rdzen-3e6309e88d82.js"), "3e6309e88d82");
  assert.strictEqual(wersja("/api/plugins/jarvo-hq/zasoby/app-0123456789ab.js"), "0123456789ab");   // pełny pakiet (demo)
  assert.strictEqual(wersja("/api/plugins/jarvo-hq/zasoby/app-baza-6c89e67a1ab9.js"), null);
});

// ------------------------------------------------------------------------------------------------ Mózg (63-mozg.js)
// czyste funkcje pakietu „mozg” w osobnym kontekście (atrapy Reacta, sklepu i trasy); dane jak z /graph po zmianach 20.11
const MOZG = (() => {
  const slad = { szkic: null, fokus: null, trasa: null };
  let stan = { szkice: { nowa: { tekst: "", pliki: [] } }, adresaci: { "0:nowa": "jarvo-web" } };
  const ctx = vm.createContext({ React: {}, Zasoby: { daj() {} }, html: () => null, cx: (...x) => x.filter(Boolean).join(" "),
    useState: (v) => [v, () => {}], useMemo: (f) => f(), useRef: (v) => ({ current: v }), useEffect: () => {}, zadanie: () => null,
    sklep: { ustaw: (f) => { stan = f(stan); slad.szkic = stan; } }, Fokus: { odloz: (c) => { slad.fokus = c; } }, Trasa: { idz: (t) => { slad.trasa = t; } },
    URLSearchParams, Date, Math, JSON, Map, Set, String, Number, Array, Object, RegExp, Infinity, encodeURIComponent });
  vm.runInContext("const isPL = () => globalThis.PL !== false; const L = (pl, en) => (isPL() ? pl : en);\n" + fs.readFileSync(path.join(SRC, "63-mozg.js"), "utf8")
    + "\n;globalThis.M = { MOZG_KATEGORIE, MOZG_BLEDY_PAMIECI, mozgMapa, mozgSekcje, mozgSzukaj, mozgTytul, mozgProste, mozgWycofana, mozgWyzej, mozgWstecz,"
    + " mozgPamiec, mozgBladPamieci, mozgProsba, mozgPopros, mozgWiki, mozgPodziel, mozgCzysty, mozgSciezkaSekcji, mozgHash, mozgStan };", ctx, { filename: "63-mozg.js" });
  return { ...ctx.M, ctx, slad };
})();
const mozgWezel = (id, o = {}) => {
  const t = MOZG.mozgTytul({ id, tytul: o.tytul || id.split("/").pop() });
  return { id, hub: false, typ: "", zmieniono: "", ...o, _t: t, _p: MOZG.mozgProste(t), _s: MOZG.mozgProste(`${t} ${o.tytul || ""} ${id}`) };
};
const MOZG_WEZLY = [
  mozgWezel("_hub-skarbiec", { hub: true, tytul: "Skarbiec", podsumowanie: "Całość w skrócie.", streszczono: "2026-11-20" }),
  mozgWezel("archiwum/agenci/jarvo-operator/_hub-operator", { hub: true, tytul: "Operator", status: "wycofana" }),
  mozgWezel("jarvo/_hub-jarvo", { hub: true, tytul: "Jarvo", podsumowanie: "Jarvo prowadzi flotę. Zasady: [[jarvo/zasady pracy]].", streszczono: "2026-11-20" }),
  ...["pamięć jarva", "zasady krytyczne", "kim jest jarvo", "zasady pracy", "jak działa jarvo"].map((t, i) =>
    mozgWezel(`jarvo/${t}`, { typ: "tozsamosc", zmieniono: `2026-11-1${i}`, edycja: t === "pamięć jarva" ? "pamiec" : "repo" })),
  mozgWezel("orzeczenia/_hub-orzeczenia", { hub: true, tytul: "Orzeczenia" }), mozgWezel("orzeczenia/jarvo", { typ: "orzeczenia" }),
  mozgWezel("orzeczenia/wszyscy", { typ: "orzeczenia" }),
  mozgWezel("user/_hub-ty", { hub: true, tytul: "Ty" }), mozgWezel("user/firma", { typ: "fakt", zmieniono: "2026-11-19" }),
  mozgWezel("user/pamięć jarva o tobie", { typ: "tozsamosc", edycja: "pamiec", pamiec: "user", zmieniono: "2026-11-01" }),
  mozgWezel("agenci/_hub-agenci", { hub: true, tytul: "Agenci" }), mozgWezel("agenci/jarvo-web/_hub-web", { hub: true, tytul: "🌐 Web (jarvo-web)" }),
  mozgWezel("agenci/jarvo-web/lekcja a", { typ: "lekcja" }), mozgWezel("agenci/jarvo-web/lekcja b", { typ: "lekcja" }),
  mozgWezel("fleet/arsenal", { tytul: "Arsenał" }), mozgWezel("fleet/skille/s1", { typ: "skill" }), mozgWezel("fleet/skille/s2", { typ: "skill" }),
  mozgWezel("fleet/skille/s3", { typ: "skill" }), mozgWezel("fleet/skille/s4", { typ: "skill" }),
  mozgWezel("podmioty/instabox", { typ: "podmiot", zmieniono: "2026-11-02" }),
  mozgWezel("podmioty/instabox stary", { typ: "podmiot", status: "wycofana", zmieniono: "2026-11-20" }),
  mozgWezel("archiwum/agenci/jarvo-operator/lekcja o", { typ: "lekcja", status: "wycofana" }),
  mozgWezel("archiwum/podmioty/instabox 2", { typ: "podmiot", status: "wycofana" }),
  mozgWezel("zrodla/jarvo-repo/HQ"),
];
test("Mózg: części w kolejności planu, Jarvo pierwsze, archiwum i źródła z boku, umiejętności ostatnie w Zespole", () => {
  const m = MOZG.mozgMapa(MOZG_WEZLY, MOZG.MOZG_KATEGORIE);
  eq(MOZG.MOZG_KATEGORIE.map((d) => d.k), ["jarvo", "ty", "projekty", "zespol", "swiat", "lekcje", "rozmowy", "zrodla", "archiwum"]);
  eq(MOZG.MOZG_KATEGORIE.map((d) => d.foldery), [["jarvo", "orzeczenia"], ["user"], ["projekty", "brands", "inspiracje"], ["agenci", "fleet"],
    ["podmioty"], ["pojecia", "bledy"], ["rozmowy", "briefy"], ["zrodla", "skrzynka", ""], ["archiwum"]]);
  eq(m.glowne.map((d) => [d.k, d.ile]), [["jarvo", 7], ["ty", 2], ["zespol", 7], ["swiat", 2]]);
  eq(m.kat.filter((d) => d.drugorzedna).map((d) => [d.k, d.ile]), [["zrodla", 1], ["archiwum", 2]]);
  const jarvo = m.kat.find((d) => d.k === "jarvo"), zespol = m.kat.find((d) => d.k === "zespol");
  eq(jarvo.grupy.map((g) => [g.k, g.nazwa, g.ile]), [["jarvo", "Tożsamość", 5], ["orzeczenia", "Twoje poprawki", 2]]);
  assert.strictEqual(jarvo.hub.id, "jarvo/_hub-jarvo");
  // fleet w całości jedną grupą „Umiejętności”, po agentach
  eq(zespol.grupy.map((g) => [g.k, g.nazwa, g.ile]), [["agenci/jarvo-web", "🌐 Web", 2], ["fleet", "Umiejętności", 5]]);
  eq(m.gdzie.get("fleet/skille/s1"), { kat: "zespol", grupa: "fleet" });
  // archiwum: grupy w układzie dawnej ścieżki, poza głównymi częściami i poza „Ostatnio zmienione”
  eq(m.kat.find((d) => d.k === "archiwum").grupy.map((g) => [g.k, g.nazwa]), [["archiwum/agenci", "Agenci"], ["archiwum", "Archiwum"]]);
  assert.ok(!m.glowne.some((d) => d.wezly.some((n) => n.id.startsWith("archiwum/"))));
});
test("Mózg: tożsamość pierwsza i w stałej kolejności (Jarvo od A do Z, kim jest, zasady, krytyczne, pamięć), wycofane szare i na końcu", () => {
  const m = MOZG.mozgMapa(MOZG_WEZLY, MOZG.MOZG_KATEGORIE);
  const jarvo = m.kat.find((d) => d.k === "jarvo"), ty = m.kat.find((d) => d.k === "ty"), swiat = m.kat.find((d) => d.k === "swiat");
  eq(MOZG.mozgSekcje(jarvo.grupy[0].wezly).map((s) => [s.nazwa, s.wezly.map((n) => n._t)]),
    [["Tożsamość i pamięć", ["jak działa jarvo", "kim jest jarvo", "zasady pracy", "zasady krytyczne", "pamięć jarva"]]]);
  eq(MOZG.mozgSekcje(ty.grupy[0].wezly).map((s) => s.t), ["tozsamosc", "fakt"]);   // pamięć o Tobie przed faktami
  const wyc = MOZG_WEZLY.find((n) => n.id === "podmioty/instabox stary");
  assert.ok(MOZG.mozgWycofana(wyc) && !MOZG.mozgWycofana(MOZG_WEZLY.find((n) => n.id === "archiwum/podmioty/instabox 2")));
  eq(MOZG.mozgSekcje(swiat.grupy[0].wezly)[0].wezly.map((n) => n.id), ["podmioty/instabox", "podmioty/instabox stary"]);   // nowsza, ale wycofana
  eq(MOZG.mozgSzukaj(MOZG_WEZLY, "instabox")[0].map((n) => n.id), ["podmioty/instabox", "podmioty/instabox stary", "archiwum/podmioty/instabox 2"]);
});
test("Mózg: „Najważniejsze” z podsumowania huba części i całego skarbca, [[linki]] w nim jako linki Mózgu", () => {
  const m = MOZG.mozgMapa(MOZG_WEZLY, MOZG.MOZG_KATEGORIE), jarvo = m.kat.find((d) => d.k === "jarvo");
  eq([jarvo.hub.podsumowanie, jarvo.hub.streszczono], ["Jarvo prowadzi flotę. Zasady: [[jarvo/zasady pracy]].", "2026-11-20"]);
  assert.strictEqual(m.korzen.id, "_hub-skarbiec");
  const cel = (t) => (t === "jarvo/zasady pracy" ? ["#/mozg?o=x", "Zasady pracy"] : null);
  assert.strictEqual(MOZG.mozgWiki(jarvo.hub.podsumowanie, cel), "Jarvo prowadzi flotę. Zasady: [Zasady pracy](#/mozg?o=x).");
  // strona notatki: streszczenie = pierwszy akapit, reszta wstępu i sekcje „## ” zwijane; „## ” w bloku kodu to nie sekcja
  eq(MOZG.mozgPodziel("**Skrót.** Zdanie.\n\nDruga część wstępu.\n## Kim jestem\ntekst\n```\n## nie\n```\n### pod\n## **Co mogę** ##\n\n## Gdzie co jest\nx"),
    { skrot: "**Skrót.** Zdanie.", wiecej: "Druga część wstępu.", sekcje: [{ tytul: "Kim jestem", tresc: "tekst\n```\n## nie\n```\n### pod" }, { tytul: "Gdzie co jest", tresc: "x" }] });
  eq(MOZG.mozgPodziel(""), { skrot: "", wiecej: "", sekcje: [] });
  // karta pod kursorem: czysty tekst bez [[linków]] i znaczników, ucięty na granicy słowa
  assert.strictEqual(MOZG.mozgCzysty("**SEOHost** blokuje [[podmioty/seohost|hosting]] i [[bledy/ftp ban]], `ssh`; [log](http://x)."),
    "SEOHost blokuje hosting i ftp ban, ssh; log.");
  assert.strictEqual(MOZG.mozgCzysty("jedno dwa trzy cztery", 12), "jedno dwa…");
  // wynik szukania z sekcją (GET /search: `notatka#Sekcja`) otwiera notatkę i przewija do sekcji ze spisu
  eq(MOZG.mozgSciezkaSekcji("jarvo/jak działa jarvo#Gdzie co jest"), ["jarvo/jak działa jarvo", "Gdzie co jest"]);
  eq(MOZG.mozgSciezkaSekcji("user/USER"), ["user/USER", ""]);
  eq(MOZG.mozgSciezkaSekcji("a#b#c"), ["a", "b#c"]);
});
test("Mózg: Wstecz = poprzedni widok Mózgu z historii, inaczej poziom wyżej", () => {
  const s = (o) => ({ z: "", k: "", g: "", o: "", ...o });
  eq(MOZG.mozgWstecz("#/mozg?k=jarvo", s({ k: "jarvo", g: "orzeczenia", o: "orzeczenia/jarvo" }), true), { stan: s({ k: "jarvo" }), historia: true });
  eq(MOZG.mozgWstecz("#/mozg", s({ k: "ty" }), false), { stan: s({}), historia: true });
  // poprzedni wpis spoza Mózgu (rozmowa) albo brak: poziom wyżej
  eq(MOZG.mozgWstecz("#/r/w_0123456789abcdef01234", s({ k: "jarvo", g: "orzeczenia", o: "orzeczenia/jarvo" }), true),
    { stan: s({ k: "jarvo", g: "orzeczenia" }), historia: false });
  eq(MOZG.mozgWstecz("", s({ k: "jarvo", g: "orzeczenia" }), true), { stan: s({ k: "jarvo" }), historia: false });
  eq(MOZG.mozgWstecz("", s({ k: "ty", g: "user" }), false), { stan: s({}), historia: false });   // jedna grupa = część
  assert.strictEqual(MOZG.mozgWstecz("", s({}), false), null);                                     // wejście: nic wyżej
  assert.strictEqual(MOZG.mozgWstecz("#/mozgx", s({}), false), null);
});
test("Mózg: edytor pamięci liczy znaki jak Hermes (wpisy złączone „\\n§\\n”), pilnuje limitu, 409 = zmieniona", () => {
  eq(MOZG.mozgPamiec([" a ", "", "  ", "bż"], 10), { wpisy: ["a", "bż"], uzyte: 6, ponad: 0, zly: -1 });
  eq(MOZG.mozgPamiec(["x".repeat(8), "yy"], 10), { wpisy: ["xxxxxxxx", "yy"], uzyte: 13, ponad: 3, zly: -1 });
  assert.strictEqual(MOZG.mozgPamiec(["😀"], 5).uzyte, 1);                  // znaki Unicode, nie jednostki UTF-16
  assert.strictEqual(MOZG.mozgPamiec(["ok", "a\n§\nb"], 99).zly, 1);
  assert.strictEqual(MOZG.mozgPamiec([], 10).uzyte, 0);
  assert.strictEqual(MOZG.mozgBladPamieci({ status: 409, kod: "zmieniona" }), "zmieniona");
  assert.strictEqual(MOZG.mozgBladPamieci({ status: 409, kod: "http_409" }), "zmieniona");
  assert.strictEqual(MOZG.mozgBladPamieci({ status: 400, kod: "limit" }), "limit");
  assert.strictEqual(MOZG.mozgBladPamieci({ status: 400, kod: "pusty_wpis" }), "pusty_wpis");
  assert.strictEqual(MOZG.mozgBladPamieci({ status: 500, kod: "http_500" }), "inny");
  assert.strictEqual(MOZG.mozgBladPamieci({ status: 503, kod: "zajeta" }), "zajeta");
  assert.strictEqual(MOZG.mozgBladPamieci({ status: 400, kod: "zly_wpis" }), "zly_wpis");
  assert.strictEqual(MOZG.mozgBladPamieci({ status: 0, kod: "siec" }), "inny");
  for (const [k, [pl, en]] of Object.entries(MOZG.MOZG_BLEDY_PAMIECI)) assert.ok(pl && en && !/[—–]/.test(pl + en), k);
});
test("Mózg: „Edytuj” w pliku Jarva = szkic nowej rozmowy do Jarva (bez wysyłania, bez dubla), ekran startu z kursorem", () => {
  assert.strictEqual(MOZG.mozgProsba("profiles/jarvo/SOUL.md", ""), "Zmiana w profiles/jarvo/SOUL.md: ");
  assert.strictEqual(MOZG.mozgProsba("profiles/jarvo/SOUL.md", "Zmiana w profiles/jarvo/SOUL.md: dopisz"), "Zmiana w profiles/jarvo/SOUL.md: dopisz");
  assert.strictEqual(MOZG.mozgProsba("a.md", "stary szkic"), "Zmiana w a.md: stary szkic");
  MOZG.mozgPopros("profiles/jarvo/ZASADY.md");
  eq([MOZG.slad.szkic.szkice.nowa.tekst, MOZG.slad.szkic.adresaci["0:nowa"], MOZG.slad.fokus, MOZG.slad.trasa],
    ["Zmiana w profiles/jarvo/ZASADY.md: ", null, "kompozytor", { widok: "start" }]);
  MOZG.ctx.PL = false;
  assert.strictEqual(MOZG.mozgProsba("x.md", ""), "Change in x.md: ");
  MOZG.ctx.PL = true;
});
test("Mózg: teksty interfejsu bez myślników „—” i „–”", () => {
  assert.ok(!/[—–]/.test(fs.readFileSync(path.join(SRC, "63-mozg.js"), "utf8")));
});

// ------------------------------------------------------------------------------------------------ podgląd na żywo
// rdzeń (41-na-zywo.js): urządzenie z kroku i przycisk; pakiet „podglad” (42-podglad.js): czyste funkcje okna
const NA_ZYWO = (() => {
  const ctx = vm.createContext({ React: {}, html: (s, ...v) => ({ s: s.join("|"), v }), cx: (...x) => x.filter(Boolean).join(" "),
    T: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k), L: (pl) => pl, useState: (v) => [typeof v === "function" ? v() : v, () => {}],
    useEffect: () => {}, useRef: (v) => ({ current: v }), useSklep: () => null, Leniwy: () => null, Ikona: () => null, Zasoby: { daj(o) { ctx.Z = o; } },
    Date, Math, JSON, Map, Set, Object, Array, Number, String, RegExp, isFinite, Uint8Array });
  vm.runInContext(fs.readFileSync(path.join(SRC, "41-na-zywo.js"), "utf8") + "\n;globalThis.M = { NaZywo, PrzyciskNaZywo, nazwaUrzadzenia };", ctx);
  vm.runInContext(fs.readFileSync(path.join(SRC, "42-podglad.js"), "utf8"), ctx);
  return { ...ctx.M, ...ctx.Z };
})();
test("Podgląd na żywo: urządzenie z bieżącego kroku (telefon z argumentem phone, computer_use, komputer)", () => {
  const u = NA_ZYWO.NaZywo.urzadzenie;
  eq(u({ narzedzie: "mcp__phone__act", args: { phone: "second", cmd: "tap", x: 540, y: 1200 } }),
    { rodzaj: "telefon", u: "second", punkt: { x: 540, y: 1200 }, cmd: "tap" });
  eq(u({ narzedzie: "mcp__phone_screen", args: { phone: "third", cmd: "screen" } }), { rodzaj: "telefon", u: "third", punkt: null, cmd: "screen" });
  eq(u({ narzedzie: "mcp__phone__ping" }), { rodzaj: "telefon", u: null, punkt: null, cmd: null });   // bez argumentu: serwer wie, który
  eq(u({ narzedzie: "computer_use", args: { cmd: "click", x: 10, y: 20 } }), { rodzaj: "komputer", u: "komputer", punkt: { x: 10, y: 20 }, cmd: "click" });
  eq(u({ narzedzie: "komputer" }), { rodzaj: "komputer", u: "komputer", punkt: null, cmd: null });
  for (const k of [{ narzedzie: "terminal", args: { phone: "first" } }, { narzedzie: "mcp__phone__list_phones" }, { narzedzie: "browser_click" },
    { komentarz: "myśl", narzedzie: "mcp__phone__act" }, null]) assert.strictEqual(u(k), null, JSON.stringify(k));
  // bieżący krok: ostatni krok narzędzia pracującego przebiegu, najnowszy z kilku; komentarze pomijane
  const p = (id, stan, kroki) => ({ id, stan, agent: "jarvo", kroki });
  const teraz = NA_ZYWO.NaZywo.teraz([
    p("a", "pracuje", [{ ts: 5, narzedzie: "mcp__phone__act", args: { phone: "first" } }, { ts: 6, komentarz: "patrzę" }]),
    p("b", "pracuje", [{ ts: 9, narzedzie: "mcp__phone__act", args: { phone: "second" } }, { ts: 10, narzedzie: "terminal" }]),
    p("c", "gotowe", [{ ts: 20, narzedzie: "computer_use" }])]);
  eq([teraz.u, teraz.pid, teraz.agent], ["first", "a", "jarvo"]);
  assert.strictEqual(NA_ZYWO.NaZywo.teraz([p("d", "pracuje", [{ ts: 1, narzedzie: "read_file" }])]), null);
  assert.ok(NA_ZYWO.NaZywo.rowne(teraz, { ...teraz }));
});
test("Podgląd na żywo: przycisk tylko przy urządzeniu, z nazwą; stoi od kroku na urządzeniu; drugi klik zamyka", () => {
  const { NaZywo, PrzyciskNaZywo } = NA_ZYWO;
  assert.strictEqual(PrzyciskNaZywo({ urz: NaZywo.urzadzenie({ narzedzie: "write_file" }) }), null);
  const b = PrzyciskNaZywo({ urz: NaZywo.urzadzenie({ narzedzie: "mcp__phone__act", args: { phone: "second" } }) });
  assert.ok(b && JSON.stringify(b).includes('"second"') && b.v.includes('podglad.telefon_n:{"n":"second"} · podglad.na_zywo'));
  assert.ok(PrzyciskNaZywo({ urz: NaZywo.urzadzenie({ narzedzie: "computer_use" }) }).v.includes("podglad.komputer · podglad.na_zywo"));
  let otwarte = null;
  const stop = NaZywo.sluchaj((s) => { otwarte = s; });
  b.v.find((x) => typeof x === "function")({ stopPropagation() {} });
  eq([otwarte.otwarte, otwarte.u], [true, "second"]);
  // przycisk czyta stan okna: otwarte = wciśnięty, klik zamyka
  const b2 = PrzyciskNaZywo({ urz: NaZywo.urzadzenie({ narzedzie: "mcp__phone__act", args: { phone: "second" } }) });
  b2.v.find((x) => typeof x === "function")({ stopPropagation() {} });
  assert.strictEqual(otwarte.otwarte, false);
  stop();
  // 24.11 właściciel: przycisk przy krokach skakał; pasek bierze ostatnie urządzenie z całego przebiegu, nie z bieżącego kroku
  const kroki = [{ narzedzie: "mcp__phone__act", args: { phone: "third" } }, { narzedzie: "read_file" }, { komentarz: "patrzę" }];
  eq(NaZywo.ostatnie(kroki).u, "third");
  assert.strictEqual(NaZywo.ostatnie([{ narzedzie: "read_file" }]), null);
});
test("Podgląd na żywo: kodek z SPS, punkt stuknięcia na obrazie (obrót), napisy stanów bez czarnego ekranu", () => {
  const { spsZKonfiguracji, kodekAvc, punktNaObrazie, napisPodgladu, kadrObrazu } = NA_ZYWO;
  // 24.11 właściciel: puste pasy nad i pod telefonem; kadr wpisany w pole, także powiększony, z ramką
  eq(kadrObrazu({ w: 436, h: 700 }, { w: 576, h: 1280 }, 5), { w: 320, h: 700 });
  eq(kadrObrazu({ w: 300, h: 900 }, { w: 288, h: 640 }, 5), { w: 300, h: 654 });
  assert.strictEqual(kadrObrazu(null, { w: 576, h: 1280 }, 5), null);
  const cfg = new Uint8Array([0, 0, 0, 1, 0x67, 0x42, 0xc0, 0x1f, 0xaa, 0, 0, 0, 1, 0x68, 0xce]);
  assert.strictEqual(kodekAvc(spsZKonfiguracji(cfg)), "avc1.42c01f");
  assert.strictEqual(spsZKonfiguracji(new Uint8Array([0, 0, 1, 0x68, 1])), null);
  eq(punktNaObrazie({ x: 360, y: 400 }, { szer: 720, wys: 1600 }, { w: 576, h: 1280 }), { x: 0.5, y: 0.25 });
  eq(punktNaObrazie({ x: 800, y: 360 }, { szer: 720, wys: 1600 }, { w: 1280, h: 576 }), { x: 0.5, y: 0.5 });   // obrócony
  assert.strictEqual(punktNaObrazie({ x: 900, y: 10 }, { szer: 720, wys: 1600 }, { w: 576, h: 1280 }), null);
  assert.strictEqual(punktNaObrazie({ x: 1, y: 1 }, null, { w: 1, h: 1 }), null);
  const s = { polaczenie: "otwarte", stan: "dziala", klatka: true, u: "second" };
  assert.strictEqual(napisPodgladu(s, "Telefon second", null), null);
  assert.strictEqual(napisPodgladu({ ...s, polaczenie: "laczy" }, "x", null), "Łączę…");
  assert.strictEqual(napisPodgladu({ ...s, ekran: { wlaczony: false } }, "x", null), "Ekran wygaszony");
  assert.strictEqual(napisPodgladu({ ...s, stan: "poza_siecia" }, "x", null), "Telefon poza siecią, łączę ponownie");
  assert.strictEqual(napisPodgladu({ ...s, klatka: false }, "Telefon second", null), "Łączę z: Telefon second");
  assert.strictEqual(napisPodgladu(s, "x", 10), "Skończył 10 s temu");
  assert.strictEqual(napisPodgladu({ ...s, bladObrazu: true }, "x", null).startsWith("Ta przeglądarka"), true);
  for (const f of ["41-na-zywo.js", "42-podglad.js"]) assert.ok(!/[—–]/.test(fs.readFileSync(path.join(SRC, f), "utf8")), f);
});

test("Podagenci w tle: licznik gotowych i czy któraś delegacja trwa", () => {
  const { stanPodagentow } = NA_ZYWO;
  eq(stanPodagentow([]), { gotowe: 0, przerwane: 0, razem: 0, trwa: false });
  const d = [{ koniec: false, zadania: [{ koniec: true }, { koniec: false }] }, { koniec: true, zadania: [{ koniec: true }] }];
  eq(stanPodagentow(d), { gotowe: 2, przerwane: 0, razem: 3, trwa: true });
  eq(stanPodagentow([{ ...d[0], koniec: true, zadania: [{ koniec: true }, { koniec: true, stan: "interrupted" }] }]),
    { gotowe: 1, przerwane: 1, razem: 2, trwa: false });
});

console.log(`ok ${ile}`);
