// Mózg Jarva (#/mozg, docs/HQ.md „Mózg”): wiedza poukładana w kilka głównych części (Jarvo, Ty, Projekty i marki, …),
// w części grupy (agent, folder), w grupie notatki według rodzaju. Wejście = kafle części z liczbą i jednym zdaniem,
// dalej krok po kroku z okruszkami i strzałką „Wstecz”; stan w adresie (#/mozg?k=<część>&g=<grupa>&o=<notatka>&z=<źródło>).
// Na wejściu części i grupy „Najważniejsze” = streszczenie huba (`podsumowanie` z /graph). Graf (shared/web/graf.js)
// pokazuje tylko bieżący poziom: na wejściu skupiska części w kolorach kafli, w części skupiska grup, w grupie same
// notatki; klik w skupisko wchodzi głębiej, w kropkę otwiera notatkę. Szukaj działa na całym mózgu od razu (tytuły;
// skarbiec dokłada wyniki z treści, GET /search). Notatka obok: Markdown z [[linkami]] jako linkami Mózgu i „Powiązane”;
// notatka tożsamości z `edycja: pamiec` ma edytor wpisów (GET/PUT /pamiec), z `edycja: repo` prośbę do Jarva w rozmowie.
// Klawiatura: Tab po linkach, w polu szukania strzałki i Enter (combobox), Esc zamyka notatkę i czyści szukanie;
// nagłówek poziomu dostaje fokus po przejściu. Telefon: lista na cały ekran, graf pod „Mapa”, notatka na cały ekran.
// Części: MOZG_KATEGORIE (foldery skarbca, ta sama lista co wiedza.py FOLDERY_SKARBCA, pilnuje tego test) albo
// `kategorie` źródła z konfig/mozg.json; źródło z pliku bez nich dostaje części z folderów. Pakiet `mozg` (ten plik +
// graf.js) i style z bloku „@@pakiet mozg” ładują się po wejściu w widok. Budżet: scripts/hqbuild.py BUDZET_GZIP.

const MOZG_WIEDZA = { korzen: "/api/plugins/jarvo-wiedza" };
const MOZG_SKARBIEC = { klucz: "jarvo", nazwa: "Skarbiec Jarva", nazwa_en: "Jarvo's vault", rodzaj: "skarbiec" };

// `jedna`: folder bez podziału na podkatalogi (umiejętności floty to jedna grupa, ostatnia w Zespole); `nazwy`: nazwa
// grupy folderu tylko w tej części (`jarvo` to też agent: jego grupa w Zespole zostaje „Jarvo”)
const MOZG_KATEGORIE = [
  { k: "jarvo", ikona: "spark", foldery: ["jarvo", "orzeczenia"], nazwy: { jarvo: ["Tożsamość", "Identity"], "orzeczenia/marki": ["Poprawki dla marek", "Brand corrections"] },
    nazwa: "Jarvo", nazwa_en: "Jarvo",
    opis: "Kim jest, zasady pracy, pamięć i Twoje poprawki", opis_en: "Who he is, how he works, his memory and your corrections" },
  { k: "ty", ikona: "user", foldery: ["user"], nazwa: "Ty", nazwa_en: "You",
    opis: "Twój profil, decyzje i to, co Jarvo o Tobie pamięta", opis_en: "Your profile, decisions and what Jarvo remembers about you" },
  { k: "projekty", ikona: "folder", foldery: ["projekty", "brands", "inspiracje"], nazwa: "Projekty i marki", nazwa_en: "Projects and brands",
    opis: "Nad czym pracujemy: stan, decyzje, wyniki i wygląd marek", opis_en: "What we work on: status, decisions, results and brand looks" },
  { k: "zespol", ikona: "users", foldery: ["agenci", "fleet"], jedna: ["fleet"], nazwa: "Zespół", nazwa_en: "Team",
    opis: "Agenci, to, czego się nauczyli, i ich umiejętności", opis_en: "Agents, what they have learned and their skills" },
  { k: "swiat", ikona: "globe", foldery: ["podmioty"], nazwa: "Firmy i narzędzia", nazwa_en: "Companies and tools",
    opis: "Firmy, ludzie, narzędzia, konkurenci i dostawcy", opis_en: "Companies, people, tools, competitors and suppliers" },
  { k: "lekcje", ikona: "alert", foldery: ["pojecia", "bledy"], nazwa: "Lekcje i błędy", nazwa_en: "Lessons and mistakes",
    opis: "Pojęcia, sprawdzone metody i błędy, których nie powtarzamy", opis_en: "Concepts, proven methods and mistakes we don't repeat" },
  { k: "rozmowy", ikona: "msg", foldery: ["rozmowy", "briefy"], nazwa: "Rozmowy i briefy", nazwa_en: "Talks and briefs",
    opis: "Ustalenia z rozmów, poranne briefy i przeglądy tygodnia", opis_en: "What we agreed in talks, morning briefs, weekly reviews" },
  { k: "zrodla", ikona: "book", foldery: ["zrodla", "skrzynka", ""], drugorzedna: true, nazwa: "Dokumentacja i źródła", nazwa_en: "Docs and sources",
    opis: "Kopia dokumentacji Jarva i surowe materiały", opis_en: "A copy of Jarvo's docs and raw material" },
  { k: "archiwum", ikona: "clip", foldery: ["archiwum"], drugorzedna: true, nazwa: "Archiwum", nazwa_en: "Archive",
    opis: "Wycofane i zastąpione", opis_en: "Retired and replaced" },
];
// nazwy grup (folder albo ostatni człon ścieżki) i rodzajów notatek
const MOZG_NAZWY = { user: ["Ty", "You"], projekty: ["Projekty", "Projects"], brands: ["Marki", "Brands"],
  marki: ["Marki", "Brands"], inspiracje: ["Inspiracje", "Inspiration"], agenci: ["Agenci", "Agents"], fleet: ["Umiejętności", "Skills"],
  skille: ["Umiejętności", "Skills"], podmioty: ["Firmy i narzędzia", "Companies and tools"], pojecia: ["Pojęcia", "Concepts"],
  orzeczenia: ["Twoje poprawki", "Your corrections"], bledy: ["Błędy", "Mistakes"], rozmowy: ["Rozmowy", "Talks"], briefy: ["Briefy", "Briefs"],
  "jarvo-repo": ["Dokumentacja Jarva", "Jarvo docs"], archiwum: ["Archiwum", "Archive"] };
const MOZG_TYPY = { projekt: ["Projekty", "Projects"], lekcja: ["Lekcje", "Lessons"], fakt: ["Fakty", "Facts"], decyzja: ["Decyzje", "Decisions"],
  skill: ["Umiejętności", "Skills"], pojecie: ["Pojęcia", "Concepts"], blad: ["Błędy", "Mistakes"], podmiot: ["Firmy i narzędzia", "Companies and tools"],
  rozmowa: ["Rozmowy", "Talks"], brief: ["Briefy", "Briefs"], orzeczenia: ["Poprawki", "Corrections"], agent: ["Agenci", "Agents"],
  tozsamosc: ["Tożsamość i pamięć", "Identity and memory"] };
const MOZG_RODZAJE = Object.keys(MOZG_TYPY);
const mozgN = (p) => (p ? L(p[0], p[1]) : "");

// agent → nazwa dla właściciela w całym Mózgu (grupa, okruszki, „Przegląd”, graf, notatka): koordynator floty to
// „Jarvo”, choć hub w skarbcu ma tytuł roli („Main Judge”); notatek w skarbcu nie zmieniamy
const MOZG_AGENCI = { jarvo: "Jarvo" };
const mozgTytul = (n) => {
  const m = /^agenci\/([^/]+)\/_hub-/.exec(n.id);
  return m && MOZG_AGENCI[m[1]] ? MOZG_AGENCI[m[1]] : String(n.tytul || n.id);
};

// paleta z motywu: barwy kafli i skupisk (--j-barwa-*), reszta grafu z kolorów motywu
function mozgMotyw(el) {
  const cs = getComputedStyle(el), v = (n) => cs.getPropertyValue(n).trim();
  return { szary: v("--j-tekst-3") || "#888", barwy: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((i) => v(`--j-barwa-${i}`) || "#888"), motyw: { hub: v("--j-tekst"), tekst: v("--j-tekst"),
    sierota: "", sprzeczna: v("--j-uwaga"), zaznaczony: v("--j-fokus"), link: v("--j-linia-mocna"), linkAuto: v("--j-linia"),
    font: v("--j-font-ui"), tlo: v("--j-tlo") } };
}

const mozgProste = (s) => String(s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/ł/g, "l");
const mozgUrl = (z, id) => (z && z.notatka_url ? z.notatka_url.split("{id}").join(String(id).split("/").map(encodeURIComponent).join("/")) : "");
const mozgNowsze = (a, b) => String(b.zmieniono || "").localeCompare(String(a.zmieniono || "")) || a._t.localeCompare(b._t);
const mozgDuza = (s) => s.charAt(0).toUpperCase() + s.slice(1).replace(/[-_]+/g, " ");

// stan widoku w hashu: #/mozg?z=&k=&g=&o= (trasa aplikacji widzi #/mozg, reszta jest tylko Mózgu)
const MOZG_POLA = ["z", "k", "g", "o"];
function mozgStan(hash) {
  const h = String(hash || ""), i = h.indexOf("?"), q = new URLSearchParams(i < 0 ? "" : h.slice(i + 1)), s = {};
  for (const p of MOZG_POLA) s[p] = q.get(p) || "";
  return s;
}
const mozgHash = (s) => {
  const q = MOZG_POLA.filter((p) => s[p] && !(p === "z" && s[p] === "jarvo")).map((p) => `${p}=${encodeURIComponent(s[p]).replace(/\(/g, "%28").replace(/\)/g, "%29")}`);
  return "#/mozg" + (q.length ? "?" + q.join("&") : "");
};

// węzły → części → grupy. Grupa = katalog do dwóch członów (agenci/jarvo-ads), folder z `jedna` części w całości;
// podkatalog bez huba i z mniej niż 3 notatkami wraca do folderu. Grupa z samym hubem nie jest grupą: hub zostaje
// „Przeglądem” części. `korzen`: hub całego skarbca (jego streszczenie stoi na wejściu Mózgu).
function mozgMapa(wezly, defs) {
  const kat = [], zFolderu = new Map(), gdzie = new Map(), huby = new Map();
  const nowa = (d) => { const x = { ...d, wezly: [], grupy: [], hub: null, ile: 0 }; kat.push(x); for (const f of d.foldery || []) zFolderu.set(f, x); return x; };
  (defs || []).forEach(nowa);
  for (const n of wezly) {
    const cz = n.id.split("/"), f = cz.length > 1 ? cz[0] : "";
    if (n.hub && !huby.has(cz.slice(0, -1).join("/"))) huby.set(cz.slice(0, -1).join("/"), n);
    (zFolderu.get(f) || nowa({ k: "f-" + (f || "_"), foldery: [f], auto: 1 })).wezly.push(n);
  }
  // źródło z pliku: najwyżej 7 części z folderów, reszta w „Pozostałych”
  const auto = kat.filter((d) => d.auto).sort((a, b) => b.wezly.length - a.wezly.length);
  if (auto.length > 8) {
    const inne = nowa({ k: "inne", foldery: [], nazwa: "Pozostałe", nazwa_en: "Other" });
    for (const d of auto.slice(7)) { inne.wezly.push(...d.wezly); inne.foldery.push(...d.foldery); kat.splice(kat.indexOf(d), 1); }
  }
  for (const d of kat) {
    if (d.auto) { const f = d.foldery[0], h = huby.get(f); d.nazwa = f ? (MOZG_NAZWY[f] ? MOZG_NAZWY[f][0] : h ? h._t : mozgDuza(f)) : "Ogólne"; d.nazwa_en = f ? (MOZG_NAZWY[f] ? MOZG_NAZWY[f][1] : d.nazwa) : "General"; }
    const gr = new Map(), wloz = (dir, n) => { if (!gr.has(dir)) gr.set(dir, []); gr.get(dir).push(n); };
    for (const n of d.wezly) { const cz = n.id.split("/"); wloz(cz.length > 2 && !(d.jedna || []).includes(cz[0]) ? cz[0] + "/" + cz[1] : cz.length > 1 ? cz[0] : "", n); }
    for (const [dir, l] of [...gr]) if (dir.includes("/") && l.length < 3 && !l.some((n) => n.hub)) { gr.delete(dir); for (const n of l) wloz(dir.split("/")[0], n); }
    const fi = (dir) => { const i = d.foldery.indexOf(dir.split("/")[0]); return i < 0 ? 99 : i; };
    let przeglad = null;   // „Przegląd” części: hub pierwszego folderu części (sam folder przed podkatalogiem)
    for (const [dir, l] of gr) {
      const hub = l.filter((n) => n.hub).sort((a, b) => a.id.length - b.id.length)[0] || null, ile = l.filter((n) => !n.hub).length;
      if (hub && (!przeglad || fi(dir) < przeglad[0] || (fi(dir) === przeglad[0] && dir.length < przeglad[1]))) przeglad = [fi(dir), dir.length, hub];
      if (!ile) { for (const n of l) gdzie.set(n.id, { kat: d.k, grupa: "" }); continue; }
      const ost = dir.split("/").pop(), nz = (d.nazwy || {})[dir] || MOZG_NAZWY[dir.includes("/") ? ost : dir];
      const nazwa = nz ? nz : hub ? [hub._t.replace(/\s*\([^)]*\)\s*$/, "")] : [dir ? mozgDuza(ost) : "Ogólne", dir ? mozgDuza(ost) : "General"];
      d.grupy.push({ k: dir, wezly: l, hub, ile, nazwa: L(nazwa[0], nazwa[1] || nazwa[0]) });
      d.ile += ile;
    }
    d.grupy.sort((a, b) => fi(a.k) - fi(b.k) || b.ile - a.ile);
    d.hub = przeglad && przeglad[2];
    for (const g of d.grupy) for (const n of g.wezly) gdzie.set(n.id, { kat: d.k, grupa: g.k });
  }
  const pelne = kat.filter((d) => d.ile || d.hub);
  return { kat: pelne, glowne: pelne.filter((d) => !d.drugorzedna), gdzie, korzen: huby.get("") || null };
}

// notatki grupy według rodzaju (tożsamość pierwsza, potem najliczniejszy), w rodzaju od najnowszej, wycofane na końcu;
// tożsamość w stałej kolejności: Jarvo od A do Z (mapa), kim jest, zasady pracy, zasady krytyczne, pamięć
const MOZG_TOZSAMOSC = ["jak działa jarvo", "kim jest jarvo", "zasady pracy", "zasady krytyczne", "pamięć jarva", "pamięć jarva o tobie"];
const mozgMiejsceT = (n) => { const i = MOZG_TOZSAMOSC.indexOf(n.id.split("/").pop()); return i < 0 ? 99 : i; };
// notatka wycofana poza archiwum (w archiwum wycofane jest wszystko, więc tam bez wyszarzenia)
const mozgWycofana = (n) => n.status === "wycofana" && !n.id.startsWith("archiwum/");
function mozgSekcje(lista) {
  const m = new Map();
  for (const n of lista) if (!n.hub) { const t = MOZG_TYPY[n.typ] ? n.typ : ""; if (!m.has(t)) m.set(t, []); m.get(t).push(n); }
  const ul = (t) => (a, b) => (t === "tozsamosc" && mozgMiejsceT(a) - mozgMiejsceT(b)) || mozgWycofana(a) - mozgWycofana(b) || mozgNowsze(a, b);
  return [...m].map(([t, l]) => ({ t, nazwa: t ? mozgN(MOZG_TYPY[t]) : L("Notatki", "Notes"), wezly: l.sort(ul(t)) }))
    .sort((a, b) => (b.t === "tozsamosc") - (a.t === "tozsamosc") || b.wezly.length - a.wezly.length);
}

// szukanie po tytule i ścieżce bez ogonków; każde słowo musi pasować; tytuł od zapytania > tytuł z nim > ścieżka;
// archiwum i wycofane za aktualnymi
function mozgSzukaj(wezly, q, ile = 40) {
  const f = mozgProste(q).trim().replace(/\s+/g, " ");
  if (!f) return [[], 0];
  const slowa = f.split(" "), w = [];
  for (const n of wezly) if (slowa.every((s) => n._s.includes(s))) w.push([n._p.startsWith(f) ? 0 : n._p.includes(f) ? 1 : slowa.every((s) => n._p.includes(s)) ? 2 : 3, n]);
  const stare = (n) => (n.id.startsWith("archiwum/") ? 2 : n.status === "wycofana" ? 1 : 0);
  w.sort((a, b) => stare(a[1]) - stare(b[1]) || a[0] - b[0] || b[1].hub - a[1].hub || a[1]._t.length - b[1]._t.length);
  return [w.slice(0, ile).map((x) => x[1]), w.length];
}

// [[cel|napis]] z notatki skarbca → link Mózgu z napisem albo tytułem celu (cel nieznany: sam napis). Komentarze
// generatora i sekcja „## Powiązane” znikają: tę samą listę (z obu stron linku) Mózg pokazuje pod notatką.
function mozgWiki(tekst, cel) {
  return String(tekst || "").replace(/<!--[\s\S]*?-->/g, "").replace(/^##\s+Powiązane\s*\n[\s\S]*?(?=^##\s|(?![\s\S]))/m, "")
    .replace(/\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]/g, (_, t, e) => {
      const c = cel(t.trim()), napis = String(e || (c && c[1]) || t.split("/").pop()).replace(/[[\]]/g, "").trim();
      return c ? `[${napis}](${c[0]})` : napis;
    });
}

// wynik GET /search: `sciezka` notatki albo jej sekcji (`notatka#Sekcja`) → [notatka, sekcja]
const mozgSciezkaSekcji = (s) => { const t = String(s || ""), i = t.indexOf("#"); return i < 0 ? [t, ""] : [t.slice(0, i), t.slice(i + 1)]; };

// spis sekcji długiej notatki: nagłówki „## ” poza blokami kodu (w widoku h4.j-md-h2, ta sama kolejność), bez znaczników
function mozgSpis(tekst) {
  const wynik = [];
  let kod = false;
  for (const l of String(tekst || "").split("\n")) {
    if (/^ {0,3}(```|~~~)/.test(l)) kod = !kod;
    else if (!kod) { const m = /^ {0,3}##[ \t]+(.*?)[ \t#]*$/.exec(l); if (m && m[1]) wynik.push(m[1].replace(/[*_`]/g, "").trim()); }
  }
  return wynik;
}

// „Wstecz”: poprzedni widok Mózgu z historii przeglądarki (wpis oznaczony przy wejściu, history.back), a bez niego
// poziom wyżej (notatka → jej poziom, grupa → część, część → wejście)
function mozgWyzej(s, wieleGrup) {
  if (s.o) return { ...s, o: "" };
  if (s.g && wieleGrup) return { ...s, g: "" };
  return s.k ? { ...s, k: "", g: "" } : null;
}
function mozgWstecz(poprz, s, wieleGrup) {
  if (/^#\/mozg(\?|$)/.test(poprz || "")) return { stan: mozgStan(poprz), historia: true };
  const w = mozgWyzej(s, wieleGrup);
  return w && { stan: w, historia: false };
}

// pamięć Jarva (GET/PUT /pamiec wtyczki jarvo-wiedza): wpisy jak w narzędziu memory Hermesa, złączone „\n§\n”,
// limit liczony w znakach Unicode całego pliku; puste wpisy odpadają przed zapisem
const MOZG_SEP = "\n§\n";
function mozgPamiec(wpisy, limit) {
  const w = wpisy.map((x) => String(x || "").trim()).filter(Boolean), uzyte = [...w.join(MOZG_SEP)].length;
  return { wpisy: w, uzyte, ponad: Math.max(0, uzyte - limit), zly: w.findIndex((x) => /(^|\n)§(\n|$)/.test(x)) };
}
const MOZG_BLEDY_PAMIECI = {
  zmieniona: ["W międzyczasie ktoś zmienił tę pamięć (na przykład Jarvo w rozmowie). Wczytaj ponownie i nanieś zmianę jeszcze raz.",
    "Someone changed this memory in the meantime (for example Jarvo in a chat). Reload it and make your change again."],
  limit: ["Za dużo tekstu jak na limit pamięci. Skróć albo usuń któryś wpis.", "Too much text for the memory limit. Shorten or remove an entry."],
  pusty_wpis: ["Ten wpis jest pusty. Wpisz treść albo go usuń.", "This entry is empty. Type something or remove it."],
  zly_wpis: ["Jarvo nie przyjmie tego wpisu: jest powtórzony, wygląda na hasło albo klucz, ma linię z samym znakiem § albo nie przeszedł kontroli bezpieczeństwa. Popraw go albo usuń.",
    "Jarvo will not accept this entry: it is a duplicate, looks like a password or key, has a line with just § or failed the safety check. Fix or remove it."],
  paragraf: ["Wpis nie może mieć linii z samym znakiem §: nim pamięć oddziela wpisy.", "An entry cannot have a line with just §: it separates entries."],
  zajeta: ["Jarvo właśnie zapisuje pamięć. Spróbuj za chwilę.", "Jarvo is writing to his memory right now. Try again in a moment."],
  wczytaj: ["Nie udało się wczytać pamięci.", "Could not load the memory."],
  inny: ["Nie udało się zapisać. Spróbuj jeszcze raz.", "Could not save. Try again."],
};
const mozgBladPamieci = (e) => (e && (e.status === 409 || e.kod === "zmieniona") ? "zmieniona"
  : e && ["limit", "pusty_wpis", "zly_wpis", "zajeta"].includes(e.kod) ? e.kod : "inny");

// „Poproś o zmianę” (notatka z `edycja: repo`): początek wiadomości do Jarva w szkicu nowej rozmowy (bez dubla przy
// drugim kliknięciu, jak „Odpowiedz” w Aktualizacjach), adresat domyślny (Jarvo), ekran startu z kursorem na końcu
const mozgProsba = (plik, byl) => { const p = L(`Zmiana w ${plik}: `, `Change in ${plik}: `), t = String(byl || ""); return t.startsWith(p) ? t : p + t; };
function mozgPopros(plik) {
  sklep.ustaw((s) => {
    const byl = s.szkice.nowa || {};
    return { ...s, adresaci: { ...s.adresaci, "0:nowa": null },
      szkice: { ...s.szkice, nowa: { tekst: mozgProsba(plik, byl.tekst), pliki: byl.pliki || [], ts: Date.now() / 1000 } } };
  });
  Fokus.odloz("kompozytor");
  Trasa.idz({ widok: "start" });
}

// dane grafu dla poziomu: wejście = skupiska głównych części, część = skupiska grup, grupa = jej notatki
function mozgGraf(mapa, linki, kat, grupa) {
  const wezly = [], pin = (k, nazwa, ile, ci) => wezly.push({ id: "@" + k, grupa: k, stale: true, r: 15, etykieta: `${nazwa} · ${ile}`, _ci: ci });
  if (grupa) {
    for (const n of grupa.wezly) wezly.push({ ...n, _ci: MOZG_RODZAJE.indexOf(n.typ) + 1 });
    [...wezly].filter((n) => !n.hub).sort((a, b) => (b.we || 0) - (a.we || 0)).slice(0, 6).forEach((n) => { n.napis = 1; });
  } else if (kat) {
    kat.grupy.forEach((g, i) => { for (const n of g.wezly) wezly.push({ ...n, grupa: g.k, _ci: i }); pin(g.k, g.nazwa, g.ile, i); });
  } else {
    mapa.glowne.forEach((d, i) => { for (const g of d.grupy) for (const n of g.wezly) wezly.push({ ...n, grupa: d.k, _ci: i }); pin(d.k, L(d.nazwa, d.nazwa_en || d.nazwa), d.ile, i); });
  }
  for (const n of wezly) if (!n.stale) n.etykieta = n._t;   // napis = tytuł, nie nazwa pliku („_hub-web”)
  const ids = new Set(wezly.map((n) => n.id));
  return { wezly, linki: linki.filter((l) => ids.has(l.z) && ids.has(l.do)) };
}

function mozgData(s) {
  const d = new Date(String(s || "").slice(0, 10));
  if (isNaN(d)) return "";
  return d.toLocaleDateString(isPL() ? "pl-PL" : "en-GB", { day: "numeric", month: "short", ...(d.getFullYear() !== new Date().getFullYear() && { year: "numeric" }) });
}

function MozgWiersz({ n, href, gdzie, otwarta, opis }) {
  const stara = mozgWycofana(n);
  return html`<li><a class=${cx("j-mozg-wiersz", stara && "is-wycofana")} href=${href(n.id)} aria-current=${n.id === otwarta ? "true" : undefined}>
    <span class="j-mozg-wt">${stara && html`<span class="j-mozg-tag">${L("wycofana", "retired")}</span>`}${n.hub ? L("Przegląd: ", "Overview: ") : ""}${n._t}</span>
    ${gdzie && html`<span class="j-mozg-wg">${gdzie}</span>`}
    ${opis && html`<span class="j-mozg-wo">${opis}</span>`}${!gdzie && n.zmieniono && html`<span class="j-mozg-wd">${mozgData(n.zmieniono)}</span>`}</a></li>`;
}

// notatki grupy w sekcjach rodzajów, każda zwinięta do kilku; „Pokaż wszystkie” rozwija jedną sekcję
function MozgSekcje({ wezly, href, otwarta }) {
  const sekcje = useMemo(() => mozgSekcje(wezly), [wezly]), [wiecej, setWiecej] = useState(""), ile = sekcje.length > 1 ? 6 : 15;
  return sekcje.map((s) => html`<section key=${s.t} class="j-mozg-sekcja">
    ${sekcje.length > 1 && html`<h3>${s.nazwa} <span>${s.wezly.length}</span></h3>`}
    <ul>${(wiecej === s.t ? s.wezly : s.wezly.slice(0, ile)).map((n) => html`<${MozgWiersz} key=${n.id} n=${n} href=${href} otwarta=${otwarta}/>`)}</ul>
    ${s.wezly.length > ile && wiecej !== s.t && html`<button type="button" class="j-mozg-wiecej" onClick=${() => setWiecej(s.t)}>${L(`Pokaż wszystkie (${s.wezly.length})`, `Show all (${s.wezly.length})`)}</button>`}
  </section>`);
}

// „Najważniejsze”: streszczenie huba (blok STRESZCZENIE, `podsumowanie` z /graph) ze „stan na …”; długie zwinięte
function MozgNajwazniejsze({ hub, wiki }) {
  const [caly, setCaly] = useState(false), t = hub ? String(hub.podsumowanie || "").trim() : "";
  if (!t) return null;
  const dlugi = t.length > 700;
  return html`<section class=${cx("j-mozg-naj", dlugi && !caly && "is-zwiniety")} aria-label=${L("Najważniejsze", "Key points")}>
    <h3>${L("Najważniejsze", "Key points")}${hub.streszczono && html` <span>${L("stan na ", "as of ")}${mozgData(hub.streszczono)}</span>`}</h3>
    <${TrescMd} tekst=${wiki(t)}/>
    ${dlugi && html`<button type="button" class="j-mozg-wiecej" aria-expanded=${String(caly)} onClick=${() => setCaly(!caly)}>${caly ? L("Zwiń", "Show less") : L("Pokaż całość", "Show all")}</button>`}
  </section>`;
}

// ← z podpisem miejsca, do którego wraca (z historii: history.back, inaczej zwykły link poziom wyżej)
const MozgWstecz = ({ w }) => w && html`<a class="j-mozg-wstecz" href=${w.href} onClick=${w.klik} aria-label=${L(`Wstecz do: ${w.napis}`, `Back to: ${w.napis}`)}>
  <${Ikona} n="back" r=${16}/><span>${w.napis}</span></a>`;

// edytor wpisów pamięci (`klucz`: memory|user): lista pól, dodaj/usuń, licznik z limitem, Zapisz/Anuluj, 409 = wczytaj
// ponownie. Esc bez zmian zamyka edytor (ze zmianami nic nie robi, żeby nie zgubić tekstu), Ctrl+Enter zapisuje.
function MozgPamiec({ klucz, onZapis, onKoniec }) {
  const [st, setSt] = useState(null), [wpisy, setWpisy] = useState([]), [blad, setBlad] = useState(""), [trwa, setTrwa] = useState(false);
  const [wiersz, setWiersz] = useState(-1);   // pole wskazane przez serwer (400 z `indeks`)
  const lista = useRef(null), nr = useRef(0), dodano = useRef(false);
  const wczytaj = () => {
    setSt(null); setBlad(""); setTrwa(false); setWiersz(-1);
    zadanie("GET", "/pamiec", undefined, MOZG_WIEDZA).then((d) => {
      const p = d && d[klucz];
      if (!p || !Array.isArray(p.wpisy)) throw new Error(klucz);
      setSt(p); setWpisy((p.wpisy.length ? p.wpisy : [""]).map((t) => [++nr.current, t]));
    }).catch(() => setBlad("wczytaj"));
  };
  useEffect(wczytaj, []);
  useEffect(() => {
    if (!dodano.current) return;
    dodano.current = false;
    const pola = lista.current ? lista.current.querySelectorAll("textarea") : [];
    if (pola.length) pola[pola.length - 1].focus();
  }, [wpisy.length]);
  const sp = mozgPamiec(wpisy.map((x) => x[1]), st ? st.limit : Infinity);
  // numer wpisu z serwera (`indeks`) i ze sprawdzenia „§” liczy tylko niepuste; pole na liście ma swój numer
  const niepuste = wpisy.map((x, i) => (x[1].trim() ? i : -1)).filter((i) => i >= 0), zlyWiersz = sp.zly >= 0 ? niepuste[sp.zly] : wiersz;
  const zmiana = !!st && JSON.stringify(sp.wpisy) !== JSON.stringify(st.wpisy);
  const mozna = zmiana && !sp.ponad && sp.zly < 0 && !trwa;
  const zapisz = () => {
    if (!mozna) return;
    setTrwa(true); setBlad(""); setWiersz(-1);
    zadanie("PUT", `/pamiec/${klucz}`, { wpisy: sp.wpisy, wersja: st.wersja }, MOZG_WIEDZA).then(() => onZapis(), (e) => {
      const ix = e && e.dane && e.dane.indeks;
      setTrwa(false); setBlad(mozgBladPamieci(e)); setWiersz(Number.isInteger(ix) && niepuste[ix] !== undefined ? niepuste[ix] : -1);
    });
  };
  const klawisz = (e) => {
    if (e.key === "Escape") { e.stopPropagation(); if (!zmiana) onKoniec(); }
    else if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); zapisz(); }
  };
  const komunikat = (k) => html`<p role="alert" class="j-mozg-pam-blad">${zlyWiersz >= 0 && k !== "zmieniona" && L(`Wpis ${zlyWiersz + 1}: `, `Entry ${zlyWiersz + 1}: `)}${mozgN(MOZG_BLEDY_PAMIECI[k])}
    ${(k === "zmieniona" || k === "wczytaj") && html` <button type="button" class="j-mozg-wiecej" onClick=${wczytaj}>${L("Wczytaj ponownie", "Reload")}</button>`}</p>`;
  if (!st) return html`<div class="j-mozg-pam">${blad ? komunikat(blad) : html`<${Spinner}/>`}</div>`;
  return html`<div class="j-mozg-pam" role="group" aria-label=${L("Zmiana pamięci", "Edit memory")} onKeyDown=${klawisz}>
    <p class="j-mozg-opis">${L("Jeden wpis to jedna rzecz, którą Jarvo ma pamiętać. Zmiana działa od następnej rozmowy z Jarvem.",
      "One entry is one thing for Jarvo to remember. The change works from Jarvo's next chat.")}</p>
    <ol ref=${lista}>${wpisy.map(([k, t], i) => html`<li key=${k}>
      <textarea rows="2" value=${t} aria-label=${L(`Wpis ${i + 1}`, `Entry ${i + 1}`)} aria-invalid=${i === zlyWiersz ? "true" : undefined}
        onInput=${(e) => { const v = e.target.value; setWpisy((l) => l.map((x) => (x[0] === k ? [k, v] : x))); }}></textarea>
      <${Przycisk} rodzaj="cichy" maly ikona="trash" etykieta=${L(`Usuń wpis ${i + 1}`, `Remove entry ${i + 1}`)} onClick=${() => { setWiersz(-1); setWpisy((l) => l.filter((x) => x[0] !== k)); }}/>
    </li>`)}</ol>
    <button type="button" class="j-mozg-wiecej" onClick=${() => { dodano.current = true; setWpisy((l) => [...l, [++nr.current, ""]]); }}>+ ${L("Dodaj wpis", "Add entry")}</button>
    <p class=${cx("j-mozg-pam-licz", sp.ponad > 0 && "is-ponad")} aria-live="polite">${L(`${sp.uzyte} z ${st.limit} znaków`, `${sp.uzyte} of ${st.limit} characters`)}${sp.ponad > 0 && L(`: o ${sp.ponad} za dużo`, `: ${sp.ponad} too many`)}</p>
    ${(blad || sp.zly >= 0) && komunikat(sp.zly >= 0 ? "paragraf" : blad)}
    <div class="j-mozg-akcje">
      <${Przycisk} rodzaj="glowny" maly disabled=${!mozna} onClick=${zapisz}>${trwa ? L("Zapisuję…", "Saving…") : L("Zapisz", "Save")}</${Przycisk}>
      <${Przycisk} maly onClick=${onKoniec}>${L("Anuluj", "Cancel")}</${Przycisk}>
    </div>
  </div>`;
}

function MozgNotatka({ z, id, dane, mapa, href, cel, nazwaMiejsca, wstecz, sekcja, odsw, onZapis, onClose }) {
  const [n, setN] = useState(null), [wszystkie, setWszystkie] = useState(false), [edytor, setEdytor] = useState(false), [zapisano, setZapisano] = useState(false);
  const ref = useRef(null), info = useRef(null);
  const skarbiec = z.rodzaj === "skarbiec", w = dane.byId.get(id) || {}, url = mozgUrl(z, id);
  useEffect(() => { ref.current.focus(); }, [id]);   // Esc i czytnik ekranu: fokus w notatce
  useEffect(() => {
    let zywy = true;
    if (skarbiec) zadanie("GET", `/note?path=${encodeURIComponent(id)}`, undefined, MOZG_WIEDZA)
      .then((d) => zywy && setN(d), () => zywy && setN({ blad: 1 }));
    return () => { zywy = false; };
  }, [id, odsw]);
  useEffect(() => { if (zapisano && info.current) info.current.focus(); }, [zapisano]);
  const tresc = useMemo(() => n && !n.blad && mozgWiki(String(n.tresc || "").replace(/^\s*#\s[^\n]*\n/, ""), cel), [n]);
  // długa notatka (od 4 sekcji „## ”, np. „Jarvo od A do Z”): spis sekcji; klik przewija do nagłówka i daje mu fokus
  // (adres zostaje adresem Mózgu, bo hash niesie widok)
  const spis = useMemo(() => (tresc ? mozgSpis(tresc) : []), [tresc]);
  const skocz = (i) => {
    const h = ref.current.querySelectorAll(".j-md .j-md-h2")[i];
    if (!h) return;
    h.setAttribute("tabindex", "-1");
    h.scrollIntoView({ block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    h.focus({ preventScroll: true });
  };
  // wynik szukania z sekcją (`sciezka#Sekcja` z GET /search): po wczytaniu notatki przewinięcie do tej sekcji
  useEffect(() => {
    const i = sekcja && tresc ? spis.indexOf(sekcja.replace(/[*_`]/g, "").trim()) : -1;
    if (i < 0) return undefined;
    const t = setTimeout(() => skocz(i), 0);
    return () => clearTimeout(t);
  }, [tresc, sekcja]);
  const obok = [...(dane.sasiedzi.get(id) || [])].map((c) => dane.byId.get(c)).filter(Boolean).sort((a, b) => b.hub - a.hub || (b.we || 0) - (a.we || 0));
  const gd = mapa.gdzie.get(id), fm = (n && n.frontmatter) || {};
  const edycja = w.edycja || fm.edycja, pamiec = w.pamiec || fm.pamiec, plik = String(fm.plik || "");
  const zast = fm.zastapiona_przez && String(fm.zastapiona_przez).replace(/^\[\[|\]\]$/g, "").replace(/\.md$/, ""), zc = zast && cel(zast);
  return html`<aside ref=${ref} tabIndex="-1" class="j-mozg-karta" aria-labelledby="j-mozg-tytul">
    <div class="j-mozg-karta-gora">
      <${MozgWstecz} w=${wstecz}/>
      <button type="button" class="j-mozg-x" aria-label=${L("Zamknij notatkę", "Close the note")} onClick=${onClose}>×</button>
    </div>
    <h2 id="j-mozg-tytul">${w._t || id}</h2>
    <p class="j-mozg-wd">${[...new Set([gd && nazwaMiejsca(gd), mozgN(MOZG_TYPY[w.typ]), mozgData(w.zmieniono)].filter(Boolean))].join(" · ")}</p>
    ${(w.status || fm.status) === "wycofana" && html`<p class="j-mozg-info is-wycofana">${L("Wycofana", "Retired")}${fm.wycofano ? ` ${mozgData(fm.wycofano)}` : ""}${fm.powod ? `: ${String(fm.powod).replace(/[.\s]+$/, "")}` : ""}.
      ${zast && html` ${L("Zastąpiona przez: ", "Replaced by: ")}${zc ? html`<a href=${zc[0]}>${zc[1]}</a>` : zast}.`} ${L("Jarvo już z niej nie korzysta.", "Jarvo no longer uses it.")}</p>`}
    ${skarbiec && n && !n.blad && !edytor && (edycja === "pamiec" && (pamiec === "memory" || pamiec === "user")
      ? html`<div class="j-mozg-akcje"><${Przycisk} maly ikona="pen" onClick=${() => { setZapisano(false); setEdytor(true); }}>${L("Zmień", "Edit")}</${Przycisk}>
          <span class="j-mozg-wd">${L("Działa od następnej rozmowy z Jarvem", "Works from Jarvo's next chat")}</span></div>`
      : edycja === "repo" && html`<div class="j-mozg-akcje"><${Przycisk} maly ikona="msg" onClick=${() => mozgPopros(plik || id)}>${L("Poproś o zmianę", "Ask for a change")}</${Przycisk}>
          <span class="j-mozg-wd">${L("Plik Jarva, zmienia go Jarvo na Twoją prośbę", "Jarvo's file, he changes it when you ask")}</span></div>`)}
    ${zapisano && html`<p ref=${info} tabIndex="-1" class="j-mozg-info" role="status">${L("Zapisano. Jarvo zobaczy zmianę od następnej rozmowy.", "Saved. Jarvo will see the change from his next chat.")}</p>`}
    ${!edytor && spis.length >= 4 && html`<nav class="j-mozg-spis" aria-label=${L("Sekcje notatki", "Note sections")}>
      <h3>${L("W tej notatce", "In this note")}</h3>
      <ol>${spis.map((t, i) => html`<li key=${i}><button type="button" onClick=${() => skocz(i)}>${t}</button></li>`)}</ol></nav>`}
    ${edytor ? html`<${MozgPamiec} klucz=${pamiec} onKoniec=${() => setEdytor(false)} onZapis=${() => { setEdytor(false); setZapisano(true); onZapis(); }}/>`
      : skarbiec && (!n ? html`<${Spinner}/>` : n.blad ? html`<p>${L("Nie udało się otworzyć notatki.", "Could not open the note.")}</p>` : html`<${TrescMd} tekst=${tresc}/>`)}
    ${!skarbiec && w.opis && html`<p>${w.opis}</p>`}
    ${url && html`<p><a href=${url} target="_blank" rel="noopener noreferrer">${L("Otwórz notatkę ↗", "Open the note ↗")}</a></p>`}
    ${obok.length > 0 && !edytor && html`<section class="j-mozg-sekcja"><h3>${L("Powiązane", "Linked")} <span>${obok.length}</span></h3>
      <ul>${(wszystkie ? obok : obok.slice(0, 10)).map((c) => html`<${MozgWiersz} key=${c.id} n=${c} href=${href} gdzie=${nazwaMiejsca(mapa.gdzie.get(c.id))}/>`)}</ul>
      ${obok.length > 10 && !wszystkie && html`<button type="button" class="j-mozg-wiecej" onClick=${() => setWszystkie(true)}>${L(`Pokaż wszystkie (${obok.length})`, `Show all (${obok.length})`)}</button>`}</section>`}
  </aside>`;
}

function MozgWidok() {
  const korzen = useRef(null), plotno = useRef(null), g = useRef(null), naglowek = useRef(null), pierwszy = useRef(true), klik = useRef(null);
  const hash = React.useSyncExternalStore(Trasa.sluchaj, () => location.hash);
  const s = useMemo(() => mozgStan(hash), [hash]);
  const [zrodla, setZrodla] = useState([MOZG_SKARBIEC]);
  const [dane, setDane] = useState(null);
  const [blad, setBlad] = useState(false);
  const [q, setQ] = useState("");
  const [i, setI] = useState(0);
  const [tresc, setTresc] = useState([]);
  const [naMapie, setNaMapie] = useState(false);
  const [sekcja, setSekcja] = useState(["", ""]);   // [notatka, sekcja] z wybranego wyniku szukania
  const [odsw, setOdsw] = useState(0);        // po zapisie pamięci: graf, notatka i wyniki szukania od nowa
  const [poprz, setPoprz] = useState("");     // hash poprzedniego widoku Mózgu w historii przeglądarki („Wstecz”)
  const ostatni = useRef(""), wczytany = useRef(""), wGoreZ = useRef(null);
  const z = zrodla.find((x) => x.klucz === (s.z || "jarvo")) || zrodla[0];
  const href = (zm) => mozgHash({ ...s, ...zm });
  const idz = (zm) => { location.hash = href(zm); };

  useEffect(() => {
    zadanie("GET", "/mozg/zrodla").then((d) => d.zrodla && setZrodla(d.zrodla), () => {});
    // sterownik grafu raz na widok; motyw czytany co 120 klatek (zmiana motywu bez przeładowania)
    let p = mozgMotyw(korzen.current), co = 0;
    g.current = utworzGraf(plotno.current, {
      motyw: () => { if (++co % 120 === 0) p = mozgMotyw(korzen.current); return p.motyw; },
      kolor: (n) => (mozgWycofana(n) ? p.szary : p.barwy[(n._ci || 0) % 10]),
      otworz: (id) => klik.current(id),
    });
    return () => g.current.zniszcz();
  }, []);

  // każdy wpis historii w Mózgu dostaje przy pierwszym wejściu hash widoku, z którego przyszedł (history.state.mozgPoprz;
  // "" = spoza Mózgu); powrót przeglądarką trafia na wpis już oznaczony, więc „Wstecz” zawsze zgadza się z history.back.
  // Przejście w górę (×, Esc, „Wstecz” bez historii) zastępuje bieżący wpis i przejmuje jego oznaczenie: poziom po
  // zamknięciu notatki nie cofa do niej, a wraca tam, skąd przyszła notatka
  useEffect(() => {
    const st = history.state && typeof history.state === "object" ? history.state : {}, skad = wGoreZ.current === null ? ostatni.current : wGoreZ.current;
    wGoreZ.current = null;
    if (typeof st.mozgPoprz === "string") setPoprz(st.mozgPoprz);
    else { try { history.replaceState({ ...st, mozgPoprz: skad }, ""); } catch (_) { /* bez historii */ } setPoprz(skad); }
    ostatni.current = hash;
  }, [hash]);
  const wGore = (stan) => {
    const h = mozgHash(stan);
    if (h === poprz) history.back();
    else { wGoreZ.current = poprz; location.replace(h); }
  };

  useEffect(() => {
    let zywy = true;
    if (wczytany.current !== z.klucz) { setDane(null); setBlad(false); }   // odświeżenie tego samego źródła bez migania
    (z.rodzaj === "skarbiec" ? zadanie("GET", "/graph", undefined, MOZG_WIEDZA) : zadanie("GET", `/mozg/${encodeURIComponent(z.klucz)}`)).then((d) => {
      if (!zywy) return;
      // _t: nazwa do pokazania (mozgTytul), szukanie zna też tytuł ze skarbca
      const wezly = (d.wezly || []).map((n) => { const t = mozgTytul(n); return { ...n, _t: t, _p: mozgProste(t), _s: mozgProste(`${t} ${n.tytul || ""} ${n.id}`) }; });
      const byId = new Map(wezly.map((n) => [n.id, n])), sasiedzi = new Map(), ogon = new Map();
      for (const n of wezly) { const o = mozgProste(n.id.split("/").pop()); if (!ogon.has(o)) ogon.set(o, n.id); }
      for (const l of d.linki || []) for (const [a, b] of [[l.z, l.do], [l.do, l.z]]) if (a !== b && byId.has(b)) { if (!sasiedzi.has(a)) sasiedzi.set(a, new Set()); sasiedzi.get(a).add(b); }
      setDane({ wezly, linki: d.linki || [], byId, sasiedzi, ogon });
      wczytany.current = z.klucz;
    }, () => zywy && setBlad(true));
    return () => { zywy = false; };
  }, [z.klucz, odsw]);

  // bez `z` w zależnościach: odpowiedź /mozg/zrodla daje nowy obiekt źródła, a graf nie powinien od tego ruszać od nowa
  const mapa = useMemo(() => dane && mozgMapa(dane.wezly, z.kategorie || (z.rodzaj === "skarbiec" ? MOZG_KATEGORIE : null)), [dane, z.kategorie, z.rodzaj]);
  const kat = (mapa && mapa.kat.find((d) => d.k === s.k)) || null;
  const grupa = (kat && (kat.grupy.find((x) => x.k === s.g) || (kat.grupy.length === 1 ? kat.grupy[0] : null))) || null;
  const graf = useMemo(() => mapa && mozgGraf(mapa, dane.linki, kat, grupa), [mapa, kat, grupa]);
  const doNotatki = (id) => { const gd = mapa.gdzie.get(id) || {}; return { k: gd.kat || "", g: gd.grupa || "", o: id }; };
  const hrefNotatki = (id) => href(doNotatki(id));
  const nazwaKat = (d) => L(d.nazwa, d.nazwa_en || d.nazwa);
  const nazwaMiejsca = (gd) => {
    const d = gd && mapa.kat.find((x) => x.k === gd.kat), gr = d && d.grupy.length > 1 && d.grupy.find((x) => x.k === gd.grupa);
    return d ? nazwaKat(d) + (gr ? ` › ${gr.nazwa}` : "") : "";
  };
  // [[cel]] z treści skarbca → [adres w Mózgu, tytuł] (ścieżka albo sama nazwa pliku bez ogonków)
  const celLinku = (t) => {
    const c = dane.byId.has(t) ? t : dane.ogon.get(mozgProste(t.split("/").pop()));
    return c ? [hrefNotatki(c), dane.byId.get(c)._t] : null;
  };
  const wiki = (t) => mozgWiki(t, celLinku);
  const nazwaStanu = (st) => {
    if (st.o) return (dane.byId.get(st.o) || {})._t || st.o.split("/").pop();
    const d = mapa.kat.find((x) => x.k === st.k), gr = d && d.grupy.length > 1 && d.grupy.find((x) => x.k === st.g);
    return gr ? gr.nazwa : d ? nazwaKat(d) : L("Mózg", "Brain");
  };
  const cofnij = mapa && mozgWstecz(poprz, s, !!(kat && kat.grupy.length > 1));
  const wstecz = cofnij && { napis: nazwaStanu(cofnij.stan), href: cofnij.historia ? poprz : mozgHash(cofnij.stan),
    klik: (e) => { e.preventDefault(); if (cofnij.historia) history.back(); else wGore(cofnij.stan); } };
  klik.current = (id) => {
    if (id[0] !== "@") return idz(doNotatki(id));
    if (!kat) idz({ k: id.slice(1), g: "", o: "" });
    else idz({ g: id.slice(1), o: "" });
  };

  useEffect(() => { g.current.dane(graf); }, [graf]);
  useEffect(() => { g.current.zaznacz(s.o || null); if (s.o) g.current.wysrodkuj(s.o); else g.current.calosc(); }, [s.o, graf]);
  // po przejściu na inny poziom fokus na jego nagłówku (czytnik ekranu czyta, gdzie jesteśmy); szukanie się czyści
  useEffect(() => {
    if (pierwszy.current) { pierwszy.current = false; return; }
    if (s.o) return;   // otwarta notatka sama bierze fokus
    setQ("");
    if (naglowek.current) naglowek.current.focus({ preventScroll: true });
  }, [s.k, s.g, s.z]);

  const [tytuly, ileTytulow] = useMemo(() => (dane ? mozgSzukaj(dane.wezly, q) : [[], 0]), [dane, q]);
  useEffect(() => {
    setTresc([]);
    if (z.rodzaj !== "skarbiec" || mozgProste(q).trim().length < 3) return undefined;
    let zywy = true;
    const t = setTimeout(() => zadanie("GET", `/search?q=${encodeURIComponent(q.trim())}&limit=12`, undefined, MOZG_WIEDZA)
      .then((d) => zywy && setTresc((d && d.wyniki) || []), () => {}), 250);
    return () => { zywy = false; clearTimeout(t); };
  }, [q, z.klucz, odsw]);
  // wyniki z treści: notatka albo jej sekcja (`sciezka#Sekcja`, najwyżej jedna na notatkę); sekcja zostaje także przy
  // notatce, która już jest wśród tytułów (wskazuje konkretne miejsce)
  const opcje = useMemo(() => {
    const zt = dane ? tresc.map((r) => { const [p, sek] = mozgSciezkaSekcji(r.sciezka); return { n: dane.byId.get(p), sek, op: r.streszczenie, wTresci: 1 }; })
      .filter((o) => o.n && (o.sek || !tytuly.includes(o.n))) : [];
    return [...tytuly.map((n) => ({ n, sek: "" })), ...zt];
  }, [tytuly, tresc]);
  const ileTresci = opcje.length - tytuly.length;
  const otworz = (o) => { setSekcja([o.n.id, o.sek]); idz(doNotatki(o.n.id)); };
  useEffect(() => setI(0), [opcje]);

  const szukajKlawisz = (e) => {
    const d = { ArrowDown: 1, ArrowUp: -1 }[e.key];
    if (d) { e.preventDefault(); setI((x) => Math.max(0, Math.min(opcje.length - 1, x + d))); }
    else if (e.key === "Enter" && opcje[i]) { e.preventDefault(); otworz(opcje[i]); }
    else if (e.key === "Escape" && q) { e.stopPropagation(); setQ(""); }
  };
  useEffect(() => { const el = document.getElementById(`j-mozg-${i}`); if (el && el.scrollIntoView) el.scrollIntoView({ block: "nearest" }); }, [i]);
  const esc = (e) => { if (e.key === "Escape" && s.o) { e.stopPropagation(); wGore({ ...s, o: "" }); } };

  const okruszki = [[L("Mózg", "Brain"), href({ k: "", g: "", o: "" })]];
  if (kat) okruszki.push([nazwaKat(kat), href({ g: "", o: "" })]);
  if (kat && grupa && kat.grupy.length > 1) okruszki.push([grupa.nazwa, href({ o: "" })]);
  const szukam = q.trim() !== "";
  const tytulPoziomu = grupa && kat.grupy.length > 1 ? grupa.nazwa : kat ? nazwaKat(kat) : L("Co wie Jarvo", "What Jarvo knows");
  const ilePoziomu = grupa ? grupa.ile : kat ? kat.ile : mapa ? mapa.glowne.reduce((a, d) => a + d.ile, 0) : 0;
  const ostatnie = (lista) => lista.filter((n) => !n.hub).sort(mozgNowsze).slice(0, 5);

  let poziom = null;
  if (mapa && !szukam) {
    if (!kat) {
      poziom = html`
        ${!mapa.kat.length && html`<p class="j-mozg-opis">${L("Mózg jeszcze nic nie zapisał.", "The brain has not saved anything yet.")}</p>`}
        <ul class="j-mozg-kafle">${mapa.glowne.map((d, ci) => html`<li key=${d.k}><a class="j-mozg-kafel" href=${href({ k: d.k, g: "", o: "" })} style=${{ "--c": `var(--j-barwa-${ci % 10})` }}>
          <span class="j-mozg-ki"><${Ikona} n=${d.ikona || "folder"} r=${18}/></span>
          <span class="j-mozg-kn">${nazwaKat(d)}</span><span class="j-mozg-kl">${d.ile}</span>
          ${(d.opis || d.grupy.length > 1) && html`<span class="j-mozg-ko">${d.opis ? L(d.opis, d.opis_en || d.opis) : d.grupy.map((x) => x.nazwa).join(" · ")}</span>`}
        </a></li>`)}</ul>
        ${mapa.glowne.length > 0 && html`<section class="j-mozg-sekcja"><h3>${L("Ostatnio zmienione", "Recently changed")}</h3>
          <ul>${ostatnie(mapa.glowne.flatMap((d) => d.wezly)).map((n) => html`<${MozgWiersz} key=${n.id} n=${n} href=${hrefNotatki} gdzie=${nazwaMiejsca(mapa.gdzie.get(n.id))}/>`)}</ul></section>`}
        ${mapa.kat.filter((d) => d.drugorzedna).map((d) => html`<a key=${d.k} class="j-mozg-boczna" href=${href({ k: d.k, g: "", o: "" })}>
          <${Ikona} n=${d.ikona || "book"} r=${16}/><span><b>${nazwaKat(d)}</b> · ${d.ile}${d.opis && html`<br/><small>${L(d.opis, d.opis_en || d.opis)}</small>`}</span></a>`)}`;
    } else if (!grupa) {
      // grupa samej tożsamości (Jarvo: kim jest, zasady, pamięć) od razu jako lista, przed kaflami pozostałych grup
      const wprost = kat.grupy.filter((x) => x.wezly.every((n) => n.hub || n.typ === "tozsamosc")), kafle = kat.grupy.filter((x) => !wprost.includes(x));
      poziom = html`
        ${wprost.map((x) => html`<section key=${x.k} class="j-mozg-sekcja"><h3>${x.nazwa} <span>${x.ile}</span></h3>
          <ul>${mozgSekcje(x.wezly).flatMap((sk) => sk.wezly).map((n) => html`<${MozgWiersz} key=${n.id} n=${n} href=${hrefNotatki} otwarta=${s.o}/>`)}</ul></section>`)}
        ${kafle.length > 0 && html`<ul class="j-mozg-grupy">${kafle.map((x) => html`<li key=${x.k}><a class="j-mozg-grupa" href=${href({ g: x.k, o: "" })}
          style=${{ "--c": `var(--j-barwa-${kat.grupy.indexOf(x) % 10})` }}><span class="j-mozg-kn">${x.nazwa}</span><span class="j-mozg-kl">${x.ile}</span></a></li>`)}</ul>`}
        <section class="j-mozg-sekcja"><h3>${L("Ostatnio zmienione tutaj", "Recently changed here")}</h3>
          <ul>${ostatnie(kat.wezly.filter((n) => !wprost.some((x) => x.wezly.includes(n)))).map((n) => html`<${MozgWiersz} key=${n.id} n=${n} href=${hrefNotatki} gdzie=${nazwaMiejsca(mapa.gdzie.get(n.id))}/>`)}</ul></section>`;
    } else {
      poziom = html`<${MozgSekcje} key=${kat.k + grupa.k} wezly=${grupa.wezly} href=${hrefNotatki} otwarta=${s.o}/>`;
    }
  }
  const hub = grupa && kat.grupy.length > 1 ? grupa.hub : kat && kat.hub, hubNaj = kat ? hub : mapa && mapa.korzen;

  return html`<div ref=${korzen} class=${cx("j-mozg", s.o && dane && "is-notatka", naMapie && "is-mapa")} onKeyDown=${esc} data-mozg>
    <${NaglowekWidoku} klasa="j-mozg-gora" ikona=${IKONY_WIDOKOW.mozg}
      tytul=${html`<span class="j-mozg-okruszki">${okruszki.map(([t, h], k) => html`<span key=${k} class="j-mozg-ok">${k > 0 && html`<span class="j-mozg-ok-sep" aria-hidden="true">›</span>`}${k === okruszki.length - 1 && !s.o
        ? html`<span aria-current="page">${t}</span>` : html`<a href=${h}>${t}</a>`}</span>`)}</span>`}
      opis=${dane && `${dane.wezly.length} ${L("notatek", "notes")} · ${dane.linki.length} ${L("połączeń", "links")}`}>
      ${zrodla.length > 1 && html`<div class="j-mozg-zrodla">${zrodla.map((x) => html`<button key=${x.klucz} type="button"
        aria-pressed=${x === z} onClick=${() => { location.hash = mozgHash({ z: x.klucz }); }}>${L(x.nazwa, x.nazwa_en)}</button>`)}</div>`}
      ${z.widok_3d && html`<a class="j-mozg-3d" href=${z.widok_3d} target="_blank" rel="noopener noreferrer">${L("Widok 3D ↗", "3D view ↗")}</a>`}
      <button type="button" class="j-mozg-mapa-btn" onClick=${() => setNaMapie(!naMapie)}>${naMapie ? L("Lista", "List") : L("Mapa", "Map")}</button>
    </${NaglowekWidoku}>
    <div class="j-mozg-nav">
      <input type="search" value=${q} placeholder=${L("Szukaj w całym mózgu…", "Search the whole brain…")} aria-label=${L("Szukaj notatki", "Search notes")} role="combobox"
        aria-expanded=${szukam} aria-controls="j-mozg-wyniki" aria-autocomplete="list" aria-activedescendant=${szukam && opcje[i] ? `j-mozg-${i}` : undefined}
        onInput=${(e) => setQ(e.target.value)} onKeyDown=${szukajKlawisz}/>
      <div class="j-mozg-przewin">
        ${szukam ? html`<p class="j-mozg-opis" role="status">${ileTytulow + ileTresci ? L(`Znalezione: ${ileTytulow + ileTresci}`, `Found: ${ileTytulow + ileTresci}`) : L("Nic nie pasuje.", "Nothing matches.")}</p>
          <ul id="j-mozg-wyniki" role="listbox" aria-label=${L("Wyniki", "Results")} class="j-mozg-wyniki">${opcje.map((o, k) => html`<li key=${o.n.id + "#" + o.sek + (o.wTresci ? "+" : "")} id=${`j-mozg-${k}`} role="option"
            aria-selected=${k === i} onClick=${() => otworz(o)}>
            ${k === tytuly.length && html`<span class="j-mozg-wr">${L("W treści notatek", "Inside notes")}</span>`}
            <span class="j-mozg-wt">${o.n._t}${o.sek && `: ${o.sek}`}</span><span class="j-mozg-wg">${nazwaMiejsca(mapa.gdzie.get(o.n.id))}</span>
            ${o.op && html`<span class="j-mozg-wo">${o.op}</span>`}</li>`)}</ul>
          ${ileTytulow > tytuly.length && html`<p class="j-mozg-opis">${L(`i ${ileTytulow - tytuly.length} więcej: dopisz słowo, żeby zawęzić`, `and ${ileTytulow - tytuly.length} more: add a word to narrow down`)}</p>`}`
        : html`<header class="j-mozg-poziom">
            ${kat && !s.o && html`<${MozgWstecz} w=${wstecz}/>`}
            <h2 ref=${naglowek} tabIndex="-1">${tytulPoziomu} ${mapa && html`<span>${ilePoziomu}</span>`}</h2>
            ${kat && kat.opis && !(grupa && kat.grupy.length > 1) && html`<p class="j-mozg-opis">${L(kat.opis, kat.opis_en || kat.opis)}</p>`}
            ${!kat && mapa && html`<p class="j-mozg-opis">${L("Wybierz część, żeby zajrzeć do środka.", "Pick a part to look inside.")}</p>`}
            ${hub && html`<a class="j-mozg-przeglad" href=${hrefNotatki(hub.id)}>${L("Przegląd tej części", "Overview of this part")} →</a>`}
          </header>${hubNaj && html`<${MozgNajwazniejsze} key=${hubNaj.id} hub=${hubNaj} wiki=${wiki}/>`}${poziom}`}
        ${!dane && html`<div class="j-mozg-stan" role="status">${blad ? L("Nie udało się wczytać mózgu.", "Could not load the brain.") : html`<${Spinner}/>`}</div>`}
      </div>
    </div>
    <div class="j-mozg-plotno">
      <canvas ref=${plotno} role="img" aria-label=${L("Mapa wiedzy tego poziomu; to samo jest na liście obok", "Knowledge map of this level; the list shows the same")}></canvas>
      ${graf && html`<p class="j-mozg-podpowiedz" aria-hidden="true">${grupa ? L("Kropka = notatka. Kółko myszy przybliża.", "Dot = note. Scroll to zoom.")
        : L("Kliknij skupisko, żeby wejść.", "Click a cluster to go in.")}</p>`}
    </div>
    ${s.o && dane && mapa && html`<${MozgNotatka} key=${z.klucz + s.o} z=${z} id=${s.o} dane=${dane} mapa=${mapa} href=${hrefNotatki} cel=${celLinku}
      nazwaMiejsca=${nazwaMiejsca} wstecz=${wstecz} sekcja=${sekcja[0] === s.o ? sekcja[1] : ""} odsw=${odsw} onZapis=${() => setOdsw((x) => x + 1)} onClose=${() => wGore({ ...s, o: "" })}/>`}
  </div>`;
}

// rdzeń montuje widok przez Zasoby.wez("MozgWidok") po wczytaniu pakietu (docs/HQ.md „Pakiety”)
if (typeof Zasoby !== "undefined" && Zasoby.daj) Zasoby.daj({ MozgWidok });
