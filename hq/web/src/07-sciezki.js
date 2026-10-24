// Ścieżki plików floty w tekście i w UI (docs/NATYWNIE.md W12; bliźniak serwera: hq/plugin/sciezki.py). Kontener
// trzyma dane w /opt/data, instalacja natywna w faktycznym korzeniu (C:/Users/Michał Żółć/AppData/Local/Jarvo/dane,
// ~/.jarvo/dane), który podaje serwer (`katalog_danych` w GET /app i GET /host). Rozpoznajemy oba: /opt/data zostaje
// dla starych rozmów. Korzeń z literą dysku: litera dowolnej wielkości, separatory „/” i „\” (też mieszane), zapis
// Git Bash (/c/Users/…); spacje tylko w samym korzeniu, dalej ścieżka biegnie do pierwszego odstępu. Bez korzenia
// z serwera (demo, starszy serwer) zostaje samo /opt/data, czyli te same wyrażenia co przed instalacją natywną.
// Wyrażenia są składane raz na korzeń (`wzor`), bez zagnieżdżonych kwantyfikatorów: korzeń to stały napis.
const Sciezki = (() => {
  const ALIAS = "/opt/data";
  const KATALOGI = "(?:workspaces|missions|knowledge|inbox)";
  const DYSK = /^([A-Za-z]):(?:[\\/]|$)/;
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&");
  let korzen = null;                  // faktyczny korzeń z „/”, bez końcowego; null = tylko alias
  let pamiec = new Map();

  // korzeń z serwera: C:\x\dane i C:/x/dane/ → C:/x/dane; alias, pusty albo względny = tylko /opt/data
  function ustaw(k) {
    let s = typeof k === "string" ? k.trim() : "";
    if (DYSK.test(s)) s = s.replace(/\\/g, "/");
    s = s.replace(/\/+$/, "");
    const nowy = s && s !== ALIAS && (s.startsWith("/") || DYSK.test(s)) ? s : null;
    if (nowy !== korzen) { korzen = nowy; pamiec = new Map(); }
  }
  const zDyskiem = () => !!korzen && DYSK.test(korzen);
  const sep = () => (zDyskiem() ? "[\\\\/]" : "\\/");

  // źródło wyrażenia korzenia natywnego (bez separatora na końcu); null, gdy korzeń to alias
  function zrodloKorzenia() {
    if (!korzen) return null;
    const cz = korzen.split("/").filter(Boolean);
    if (!zDyskiem()) return cz.map((c) => "\\/" + esc(c)).join("");
    const l = cz[0][0], litera = `[${l.toUpperCase()}${l.toLowerCase()}]`;
    return `(?:${litera}:|\\/${litera})` + cz.slice(1).map((c) => sep() + esc(c)).join("");
  }
  // gotowe wyrażenie (albo źródło) dla bieżącego korzenia; `zrob` dostaje źródła {poczatek, korzen, alias}
  function wzor(klucz, zrob) {
    if (!pamiec.has(klucz)) {
      const z = zrodloKorzenia();
      const alias = `${esc(ALIAS)}\\/jarvo\\/${KATALOGI}\\/`;
      const natywny = z ? `${z}${sep()}jarvo${sep()}${KATALOGI}${sep()}` : null;
      // początek ścieżki pliku floty: <korzeń>/jarvo/<workspaces|missions|knowledge|inbox>/
      pamiec.set(klucz, zrob({ poczatek: natywny ? `(?:${natywny}|${alias})` : alias, korzen: z, alias }));
    }
    return pamiec.get(klucz);
  }

  // cały napis to ścieżka pliku floty (`calosc` = do końca napisu, inaczej sam początek jak dawne FLEET_PATH)
  const flota = (s, calosc = true) => wzor(calosc ? "flota" : "flota-poczatek",
    ({ poczatek }) => new RegExp(`^${poczatek}[^\\s\`'"<>()]+${calosc ? "$" : ""}`)).test(String(s || ""));
  // linia „MEDIA:/ścieżka” (plik od agenta, konwencja Hermesa) albo „📎 /ścieżka” (załącznik); grupa 1 = ścieżka.
  // Korzeń natywny może mieć spacje (cała linia to jedna ścieżka), inne ścieżki do pierwszego odstępu
  const linia = () => wzor("linia", ({ korzen: z }) => {
    const natywne = z ? `${z}${sep()}[^\\s"'\`]+?|` + (zDyskiem() ? "[A-Za-z]:[\\\\/][^\\s\"'`]+?|" : "") : "";
    return new RegExp(`^\\s*(?:MEDIA:\\s*|📎\\s*)["'\`]?(${natywne}\\/[^\\s"'\`]+?)["'\`]?[.,;]?\\s*$`, "u");
  });
  // ścieżka do pokazania: bez <korzeń>/jarvo/ (workspaces/web/a.html)
  const krotka = (s) => String(s || "").replace(wzor("krotka", ({ korzen: z, alias }) => new RegExp(
    `^(?:${z ? `${z}${sep()}jarvo${sep()}|` : ""}${esc(ALIAS)}\\/jarvo\\/)`)), "");
  // nazwa pliku: ostatni człon (przy korzeniu z literą dysku także po „\”)
  const nazwa = (s) => String(s || "").split(zDyskiem() ? /[\\/]/ : "/").pop();
  // stara ścieżka /opt/data/… pod faktyczny korzeń, zapis Git Bash /c/… jako C:/… (jak sciezki.na_dysk)
  function naDysk(s) {
    s = String(s || "");
    if (korzen && (s === ALIAS || s.startsWith(ALIAS + "/"))) return korzen + s.slice(ALIAS.length);
    const m = zDyskiem() ? /^\/([A-Za-z])(?=\/|$)/.exec(s) : null;
    return m ? `${m[1].toUpperCase()}:${s.slice(2) || "/"}` : s;
  }
  // ścieżka do wklejenia w Eksploratorze, PowerShellu albo cmd: na dysku Windows z „\”
  const doSystemu = (s) => (DYSK.test(String(s || "")) ? String(s).replace(/\//g, "\\") : String(s || ""));

  return { ALIAS, ustaw, korzen: () => korzen, wzor, flota, linia, krotka, nazwa, naDysk, doSystemu };
})();
