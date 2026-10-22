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
const PLIKI = ["02-sklep.js", "03-trasa.js", "04-i18n.js", "05-skroty.js", "06-tokeny.js", "12-wzmianki.js", "13-markdown.js",
  "14-czas.js", "15-os.js", "37-poznajmy.js"];
const PRZED = `const React = {}; const useMemo = (f) => f(); const useRef = (v) => ({ current: v }); const useEffect = () => {};
let HQ_LANG = null; const isPL = () => T.wymus !== "en";\n`;
const PO = "\n;({ T, SLOWNIK, Czas, Trasa, Skroty, Motyw, Os, Md, Pisanie, Wzmianki, utworzSklep, stanPoczatkowy, plytko, sklep, USTAWIENIA_DOMYSLNE, Poznanie, kwestiePoznania });";
const kod = PRZED + PLIKI.map((f) => `// ---- ${f}\n` + fs.readFileSync(path.join(SRC, f), "utf8")).join("\n") + PO;
const kontekst = vm.createContext({ Intl, Date, Math, JSON, URLSearchParams, setTimeout, clearTimeout, console, Set, Map,
  encodeURIComponent, decodeURIComponent, Number, String, Object, Array, RegExp });
const M = vm.runInContext(kod, kontekst, { filename: "hq-front.js" });
const { T, SLOWNIK, Czas, Trasa, Skroty, Motyw, Os, Md, Pisanie, Wzmianki, utworzSklep, stanPoczatkowy, plytko, Poznanie, kwestiePoznania } = M;

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
  eq(Trasa.parsuj("#/nowa/jarvo-web"), { widok: "nowa", agent: "jarvo-web" });
  eq(Trasa.parsuj("#/nowa/Zly!"), { widok: "start" });
  eq(Trasa.parsuj("#/s/jarvo/20261021_abc"), { widok: "sesja", profil: "jarvo", sesja: "20261021_abc" });
  eq(Trasa.parsuj("#/?u=polaczenia/klucze"), { widok: "start", u: "polaczenia", pod: "klucze" });
  eq(Trasa.parsuj(`#/r/${W}?u=wyglad`), { widok: "watek", watek: W, u: "wyglad" });
  eq(Trasa.parsuj("#/?u=../x"), { widok: "start" });
  eq(Trasa.parsuj("#/?n=edytor&p=a/b.mp4"), { widok: "start", n: "edytor", p: "a/b.mp4" });
  eq(Trasa.parsuj("#/?n=zlo"), { widok: "start" });
  eq(Trasa.parsuj("#/r/%E0%A4%A"), { widok: "start" });                             // zły zapis % nie wywraca
});
test("Trasa.zbuduj: w obie strony", () => {
  for (const t of [{ widok: "start" }, { widok: "watek", watek: W }, { widok: "watek", watek: W, pozycja: "x_1" },
    { widok: "nowa", agent: "jarvo-web" }, { widok: "sesja", profil: "jarvo", sesja: "s1" },
    { widok: "start", u: "polaczenia", pod: "modele" }, { widok: "watek", watek: W, n: "konwerter", p: "a b.png" }]) {
    eq(Trasa.parsuj(Trasa.zbuduj(t)), t);
  }
  assert.strictEqual(Trasa.zbuduj({ widok: "start" }), "#/");
  assert.strictEqual(Trasa.zbuduj({ widok: "watek", watek: W, u: "konto" }), `#/r/${W}?u=konto`);
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
  eq(Object.keys(stanPoczatkowy()).sort(), ["adresaci", "agenci", "aktualizacja", "blad_aplikacji", "decyzje", "funkcje", "gotowe",
    "gotowosc", "karty", "kolejnosc", "lista", "os", "pasek", "podglad", "podpowiedzi", "podzial", "poznanie", "przebiegi", "pytanie", "silnik",
    "stara_baza", "strumien", "szkice", "toasty", "ustawienia", "watki", "wersja", "wlasciciel", "wysylane"]);
  eq(stanPoczatkowy().lista.filtr, "rozmowy");
  eq(stanPoczatkowy().ustawienia.motyw, "system");
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
  eq(Os.klasaBledu({ kod: "klucz" }), { rodzaj: "klucz", sekcja: "polaczenia", pod: "klucze", ponow: false });
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
      for (const model of [true, false]) {
        const z = kwestiePoznania(k, { imie: "Kuba", model }, 9);
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

console.log(`ok ${ile}`);
