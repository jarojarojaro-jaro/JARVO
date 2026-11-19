// Mózg Jarva (#/mozg, docs/HQ.md „Mózg”): wiedza poukładana w kilka głównych części (Ty, Projekty i marki, Zespół, …),
// w części grupy (agent, folder), w grupie notatki według rodzaju. Wejście = kafle części z liczbą i jednym zdaniem,
// dalej krok po kroku z okruszkami; stan w adresie (#/mozg?k=<część>&g=<grupa>&o=<notatka>&z=<źródło>), więc
// „Wstecz” przeglądarki cofa o poziom. Graf (shared/web/graf.js) pokazuje tylko bieżący poziom: na wejściu skupiska
// części w kolorach kafli, w części skupiska grup, w grupie same notatki; klik w skupisko wchodzi głębiej, w kropkę
// otwiera notatkę. Szukaj działa na całym mózgu od razu (tytuły; skarbiec dokłada wyniki z treści, GET /search).
// Notatka obok: Markdown z [[linkami]] jako linkami Mózgu i „Powiązane”. Klawiatura: Tab po linkach, w polu szukania
// strzałki i Enter (combobox), Esc zamyka notatkę i czyści szukanie; nagłówek poziomu dostaje fokus po przejściu.
// Telefon: lista na cały ekran, graf pod przyciskiem „Mapa”, notatka na cały ekran.
// Części: MOZG_KATEGORIE (foldery skarbca z wiedza.py) albo `kategorie` źródła z konfig/mozg.json; źródło z pliku bez
// nich dostaje części z folderów. Pakiet `mozg` (ten plik + graf.js) i style z bloku „@@pakiet mozg” ładują się po
// wejściu w widok. Budżet: 10 KB gzip (scripts/hqbuild.py).

const MOZG_WIEDZA = { korzen: "/api/plugins/jarvo-wiedza" };
const MOZG_SKARBIEC = { klucz: "jarvo", nazwa: "Skarbiec Jarva", nazwa_en: "Jarvo's vault", rodzaj: "skarbiec" };

const MOZG_KATEGORIE = [
  { k: "ty", ikona: "user", foldery: ["user"], nazwa: "Ty", nazwa_en: "You",
    opis: "Kim jesteś, Twoja firma, oferta i klienci", opis_en: "Who you are, your business, offer and clients" },
  { k: "projekty", ikona: "folder", foldery: ["projekty", "brands", "inspiracje"], nazwa: "Projekty i marki", nazwa_en: "Projects and brands",
    opis: "Nad czym pracujemy: stan, decyzje, wyniki i wygląd marek", opis_en: "What we work on: status, decisions, results and brand looks" },
  { k: "zespol", ikona: "users", foldery: ["agenci", "fleet"], nazwa: "Zespół", nazwa_en: "Team",
    opis: "Agenci, ich umiejętności i to, czego się nauczyli", opis_en: "Agents, their skills and what they have learned" },
  { k: "swiat", ikona: "globe", foldery: ["podmioty"], nazwa: "Firmy i narzędzia", nazwa_en: "Companies and tools",
    opis: "Firmy, ludzie, narzędzia, konkurenci i dostawcy", opis_en: "Companies, people, tools, competitors and suppliers" },
  { k: "lekcje", ikona: "spark", foldery: ["pojecia", "orzeczenia", "bledy"], nazwa: "Lekcje i zasady", nazwa_en: "Lessons and rules",
    opis: "Pojęcia, Twoje poprawki i błędy, których nie powtarzamy", opis_en: "Concepts, your corrections and mistakes we don't repeat" },
  { k: "rozmowy", ikona: "msg", foldery: ["rozmowy", "briefy"], nazwa: "Rozmowy i briefy", nazwa_en: "Talks and briefs",
    opis: "Ustalenia z rozmów, poranne briefy i przeglądy tygodnia", opis_en: "What we agreed in talks, morning briefs, weekly reviews" },
  { k: "zrodla", ikona: "book", foldery: ["zrodla", "skrzynka", ""], drugorzedna: true, nazwa: "Dokumentacja i źródła", nazwa_en: "Docs and sources",
    opis: "Kopia dokumentacji Jarva i surowe materiały", opis_en: "A copy of Jarvo's docs and raw material" },
];
// nazwy grup (folder albo ostatni człon ścieżki) i rodzajów notatek
const MOZG_NAZWY = { user: ["Ty", "You"], projekty: ["Projekty", "Projects"], brands: ["Marki", "Brands"], marki: ["Marki", "Brands"],
  inspiracje: ["Inspiracje", "Inspiration"], agenci: ["Agenci", "Agents"], fleet: ["Flota", "Fleet"], skille: ["Umiejętności", "Skills"],
  podmioty: ["Firmy i narzędzia", "Companies and tools"], pojecia: ["Pojęcia", "Concepts"], orzeczenia: ["Twoje poprawki", "Your corrections"],
  bledy: ["Błędy", "Mistakes"], rozmowy: ["Rozmowy", "Talks"], briefy: ["Briefy", "Briefs"], "jarvo-repo": ["Dokumentacja Jarva", "Jarvo docs"] };
const MOZG_TYPY = { projekt: ["Projekty", "Projects"], lekcja: ["Lekcje", "Lessons"], fakt: ["Fakty", "Facts"], decyzja: ["Decyzje", "Decisions"],
  skill: ["Umiejętności", "Skills"], pojecie: ["Pojęcia", "Concepts"], blad: ["Błędy", "Mistakes"], podmiot: ["Firmy i narzędzia", "Companies and tools"],
  rozmowa: ["Rozmowy", "Talks"], brief: ["Briefy", "Briefs"], orzeczenia: ["Poprawki", "Corrections"], agent: ["Agenci", "Agents"] };
const MOZG_RODZAJE = Object.keys(MOZG_TYPY);
const mozgN = (p) => (p ? L(p[0], p[1]) : "");

// paleta z motywu: barwy kafli i skupisk (--j-barwa-*), reszta grafu z kolorów motywu
function mozgMotyw(el) {
  const cs = getComputedStyle(el), v = (n) => cs.getPropertyValue(n).trim();
  return { barwy: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((i) => v(`--j-barwa-${i}`) || "#888"), motyw: { hub: v("--j-tekst"), tekst: v("--j-tekst"),
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

// węzły → części → grupy. Grupa = katalog do dwóch członów (agenci/jarvo-ads); podkatalog bez huba i z mniej niż
// 3 notatkami wraca do folderu. Grupa z samym hubem nie jest grupą: hub zostaje „Przeglądem” części.
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
    if (d.auto) { const f = d.foldery[0], h = huby.get(f); d.nazwa = f ? (MOZG_NAZWY[f] ? MOZG_NAZWY[f][0] : h ? h.tytul : mozgDuza(f)) : "Ogólne"; d.nazwa_en = f ? (MOZG_NAZWY[f] ? MOZG_NAZWY[f][1] : d.nazwa) : "General"; }
    const gr = new Map(), wloz = (dir, n) => { if (!gr.has(dir)) gr.set(dir, []); gr.get(dir).push(n); };
    for (const n of d.wezly) { const cz = n.id.split("/"); wloz(cz.length > 2 ? cz[0] + "/" + cz[1] : cz.length > 1 ? cz[0] : "", n); }
    for (const [dir, l] of [...gr]) if (dir.includes("/") && l.length < 3 && !l.some((n) => n.hub)) { gr.delete(dir); for (const n of l) wloz(dir.split("/")[0], n); }
    const fi = (dir) => { const i = d.foldery.indexOf(dir.split("/")[0]); return i < 0 ? 99 : i; };
    let przeglad = null;   // „Przegląd” części: hub pierwszego folderu części (sam folder przed podkatalogiem)
    for (const [dir, l] of gr) {
      const hub = l.filter((n) => n.hub).sort((a, b) => a.id.length - b.id.length)[0] || null, ile = l.filter((n) => !n.hub).length;
      if (hub && (!przeglad || fi(dir) < przeglad[0] || (fi(dir) === przeglad[0] && dir.length < przeglad[1]))) przeglad = [fi(dir), dir.length, hub];
      if (!ile) { for (const n of l) gdzie.set(n.id, { kat: d.k, grupa: "" }); continue; }
      const ost = dir.split("/").pop(), nz = MOZG_NAZWY[dir.includes("/") ? ost : dir];
      const nazwa = nz ? nz : hub ? [hub.tytul.replace(/\s*\([^)]*\)\s*$/, "")] : [dir ? mozgDuza(ost) : "Ogólne", dir ? mozgDuza(ost) : "General"];
      d.grupy.push({ k: dir, wezly: l, hub, ile, nazwa: L(nazwa[0], nazwa[1] || nazwa[0]) });
      d.ile += ile;
    }
    d.grupy.sort((a, b) => fi(a.k) - fi(b.k) || b.ile - a.ile);
    d.hub = przeglad && przeglad[2];
    for (const g of d.grupy) for (const n of g.wezly) gdzie.set(n.id, { kat: d.k, grupa: g.k });
  }
  const pelne = kat.filter((d) => d.ile || d.hub);
  return { kat: pelne, glowne: pelne.filter((d) => !d.drugorzedna), gdzie };
}

// notatki grupy według rodzaju (najliczniejszy pierwszy), w rodzaju od najnowszej
function mozgSekcje(lista) {
  const m = new Map();
  for (const n of lista) if (!n.hub) { const t = MOZG_TYPY[n.typ] ? n.typ : ""; if (!m.has(t)) m.set(t, []); m.get(t).push(n); }
  return [...m].map(([t, l]) => ({ t, nazwa: t ? mozgN(MOZG_TYPY[t]) : L("Notatki", "Notes"), wezly: l.sort(mozgNowsze) })).sort((a, b) => b.wezly.length - a.wezly.length);
}

// szukanie po tytule i ścieżce bez ogonków; każde słowo musi pasować; tytuł od zapytania > tytuł z nim > ścieżka
function mozgSzukaj(wezly, q, ile = 40) {
  const f = mozgProste(q).trim().replace(/\s+/g, " ");
  if (!f) return [[], 0];
  const slowa = f.split(" "), w = [];
  for (const n of wezly) if (slowa.every((s) => n._s.includes(s))) w.push([n._p.startsWith(f) ? 0 : n._p.includes(f) ? 1 : slowa.every((s) => n._p.includes(s)) ? 2 : 3, n]);
  w.sort((a, b) => a[0] - b[0] || b[1].hub - a[1].hub || a[1]._t.length - b[1]._t.length);
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
  return html`<li><a class="j-mozg-wiersz" href=${href(n.id)} aria-current=${n.id === otwarta ? "true" : undefined}>
    <span class="j-mozg-wt">${n.hub ? L("Przegląd: ", "Overview: ") : ""}${n._t}</span>${gdzie && html`<span class="j-mozg-wg">${gdzie}</span>`}
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

function MozgNotatka({ z, id, dane, mapa, href, nazwaMiejsca, onClose }) {
  const [n, setN] = useState(null), [wszystkie, setWszystkie] = useState(false), ref = useRef(null);
  const skarbiec = z.rodzaj === "skarbiec", w = dane.byId.get(id) || {}, url = mozgUrl(z, id);
  useEffect(() => {
    let zywy = true;
    ref.current.focus();   // Esc i czytnik ekranu: fokus w notatce
    if (skarbiec) zadanie("GET", `/note?path=${encodeURIComponent(id)}`, undefined, MOZG_WIEDZA)
      .then((d) => zywy && setN(d), () => zywy && setN({ blad: 1 }));
    return () => { zywy = false; };
  }, [id]);
  const tresc = useMemo(() => n && !n.blad && mozgWiki(String(n.tresc || "").replace(/^\s*#\s[^\n]*\n/, ""), (t) => {
    const c = dane.byId.has(t) ? t : dane.ogon.get(mozgProste(t.split("/").pop()));
    return c ? [href(c), dane.byId.get(c)._t] : null;
  }), [n]);
  const obok = [...(dane.sasiedzi.get(id) || [])].map((c) => dane.byId.get(c)).filter(Boolean).sort((a, b) => b.hub - a.hub || (b.we || 0) - (a.we || 0));
  const gd = mapa.gdzie.get(id);
  return html`<aside ref=${ref} tabIndex="-1" class="j-mozg-karta" aria-labelledby="j-mozg-tytul">
    <div class="j-mozg-karta-gora">
      <span class="j-mozg-wg">${gd && nazwaMiejsca(gd)}</span>
      <button type="button" class="j-mozg-x" aria-label=${L("Zamknij notatkę", "Close the note")} onClick=${onClose}>×</button>
    </div>
    <h2 id="j-mozg-tytul">${w.tytul || id}</h2>
    <p class="j-mozg-wd">${[mozgN(MOZG_TYPY[w.typ]), mozgData(w.zmieniono)].filter(Boolean).join(" · ")}</p>
    ${skarbiec && (!n ? html`<${Spinner}/>` : n.blad ? html`<p>${L("Nie udało się otworzyć notatki.", "Could not open the note.")}</p>` : html`<${TrescMd} tekst=${tresc}/>`)}
    ${!skarbiec && w.opis && html`<p>${w.opis}</p>`}
    ${url && html`<p><a href=${url} target="_blank" rel="noopener noreferrer">${L("Otwórz notatkę ↗", "Open the note ↗")}</a></p>`}
    ${obok.length > 0 && html`<section class="j-mozg-sekcja"><h3>${L("Powiązane", "Linked")} <span>${obok.length}</span></h3>
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
  const z = zrodla.find((x) => x.klucz === (s.z || "jarvo")) || zrodla[0];
  const href = (zm) => mozgHash({ ...s, ...zm });
  const idz = (zm) => { location.hash = href(zm); };

  useEffect(() => {
    zadanie("GET", "/mozg/zrodla").then((d) => d.zrodla && setZrodla(d.zrodla), () => {});
    // sterownik grafu raz na widok; motyw czytany co 120 klatek (zmiana motywu bez przeładowania)
    let p = mozgMotyw(korzen.current), co = 0;
    g.current = utworzGraf(plotno.current, {
      motyw: () => { if (++co % 120 === 0) p = mozgMotyw(korzen.current); return p.motyw; },
      kolor: (n) => p.barwy[(n._ci || 0) % 10],
      otworz: (id) => klik.current(id),
    });
    return () => g.current.zniszcz();
  }, []);

  useEffect(() => {
    let zywy = true;
    setDane(null); setBlad(false);
    (z.rodzaj === "skarbiec" ? zadanie("GET", "/graph", undefined, MOZG_WIEDZA) : zadanie("GET", `/mozg/${encodeURIComponent(z.klucz)}`)).then((d) => {
      if (!zywy) return;
      const wezly = (d.wezly || []).map((n) => { const t = String(n.tytul || n.id); return { ...n, _t: t, _p: mozgProste(t), _s: mozgProste(`${t} ${n.id}`) }; });
      const byId = new Map(wezly.map((n) => [n.id, n])), sasiedzi = new Map(), ogon = new Map();
      for (const n of wezly) { const o = mozgProste(n.id.split("/").pop()); if (!ogon.has(o)) ogon.set(o, n.id); }
      for (const l of d.linki || []) for (const [a, b] of [[l.z, l.do], [l.do, l.z]]) if (a !== b && byId.has(b)) { if (!sasiedzi.has(a)) sasiedzi.set(a, new Set()); sasiedzi.get(a).add(b); }
      setDane({ wezly, linki: d.linki || [], byId, sasiedzi, ogon });
    }, () => zywy && setBlad(true));
    return () => { zywy = false; };
  }, [z.klucz]);

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
  }, [q, z.klucz]);
  const zTresci = useMemo(() => (dane ? tresc.map((r) => [dane.byId.get(r.sciezka), r.streszczenie]).filter(([n]) => n && !tytuly.includes(n)) : []), [tresc, tytuly]);
  const opcje = useMemo(() => [...tytuly, ...zTresci.map((x) => x[0])], [tytuly, zTresci]);
  useEffect(() => setI(0), [opcje]);

  const szukajKlawisz = (e) => {
    const d = { ArrowDown: 1, ArrowUp: -1 }[e.key];
    if (d) { e.preventDefault(); setI((x) => Math.max(0, Math.min(opcje.length - 1, x + d))); }
    else if (e.key === "Enter" && opcje[i]) { e.preventDefault(); idz(doNotatki(opcje[i].id)); }
    else if (e.key === "Escape" && q) { e.stopPropagation(); setQ(""); }
  };
  useEffect(() => { const el = document.getElementById(`j-mozg-${i}`); if (el && el.scrollIntoView) el.scrollIntoView({ block: "nearest" }); }, [i]);
  const esc = (e) => { if (e.key === "Escape" && s.o) { e.stopPropagation(); idz({ o: "" }); } };

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
      poziom = html`
        <ul class="j-mozg-grupy">${kat.grupy.map((x, ci) => html`<li key=${x.k}><a class="j-mozg-grupa" href=${href({ g: x.k, o: "" })} style=${{ "--c": `var(--j-barwa-${ci % 10})` }}>
          <span class="j-mozg-kn">${x.nazwa}</span><span class="j-mozg-kl">${x.ile}</span></a></li>`)}</ul>
        <section class="j-mozg-sekcja"><h3>${L("Ostatnio zmienione tutaj", "Recently changed here")}</h3>
          <ul>${ostatnie(kat.wezly).map((n) => html`<${MozgWiersz} key=${n.id} n=${n} href=${hrefNotatki} gdzie=${nazwaMiejsca(mapa.gdzie.get(n.id))}/>`)}</ul></section>`;
    } else {
      poziom = html`<${MozgSekcje} key=${kat.k + grupa.k} wezly=${grupa.wezly} href=${hrefNotatki} otwarta=${s.o}/>`;
    }
  }
  const hub = grupa && kat.grupy.length > 1 ? grupa.hub : kat && kat.hub;

  return html`<div ref=${korzen} class=${cx("j-mozg", s.o && dane && "is-notatka", naMapie && "is-mapa")} onKeyDown=${esc} data-mozg>
    <div class="j-mozg-gora">
      <nav aria-label=${L("Gdzie jesteś", "Where you are")} class="j-mozg-okruszki"><ol>${okruszki.map(([t, h], k) => html`<li key=${k}>${k === okruszki.length - 1
        ? html`<h1 aria-current=${s.o ? undefined : "page"}>${s.o ? html`<a href=${h}>${t}</a>` : t}</h1>` : html`<a href=${h}>${t}</a>`}</li>`)}</ol></nav>
      ${zrodla.length > 1 && html`<div class="j-mozg-zrodla">${zrodla.map((x) => html`<button key=${x.klucz} type="button"
        aria-pressed=${x === z} onClick=${() => { location.hash = mozgHash({ z: x.klucz }); }}>${L(x.nazwa, x.nazwa_en)}</button>`)}</div>`}
      ${z.widok_3d && html`<a class="j-mozg-3d" href=${z.widok_3d} target="_blank" rel="noopener noreferrer">${L("Widok 3D ↗", "3D view ↗")}</a>`}
      <span class="j-mozg-meta">${dane && `${dane.wezly.length} ${L("notatek", "notes")} · ${dane.linki.length} ${L("połączeń", "links")}`}</span>
      <button type="button" class="j-mozg-mapa-btn" onClick=${() => setNaMapie(!naMapie)}>${naMapie ? L("Lista", "List") : L("Mapa", "Map")}</button>
    </div>
    <div class="j-mozg-nav">
      <input type="search" value=${q} placeholder=${L("Szukaj w całym mózgu…", "Search the whole brain…")} aria-label=${L("Szukaj notatki", "Search notes")} role="combobox"
        aria-expanded=${szukam} aria-controls="j-mozg-wyniki" aria-autocomplete="list" aria-activedescendant=${szukam && opcje[i] ? `j-mozg-${i}` : undefined}
        onInput=${(e) => setQ(e.target.value)} onKeyDown=${szukajKlawisz}/>
      <div class="j-mozg-przewin">
        ${szukam ? html`<p class="j-mozg-opis" role="status">${ileTytulow + zTresci.length ? L(`Znalezione: ${ileTytulow + zTresci.length}`, `Found: ${ileTytulow + zTresci.length}`) : L("Nic nie pasuje.", "Nothing matches.")}</p>
          <ul id="j-mozg-wyniki" role="listbox" aria-label=${L("Wyniki", "Results")} class="j-mozg-wyniki">${opcje.map((n, k) => html`<li key=${n.id} id=${`j-mozg-${k}`} role="option"
            aria-selected=${k === i} onClick=${() => idz(doNotatki(n.id))}>
            ${k === tytuly.length && html`<span class="j-mozg-wr">${L("W treści notatek", "Inside notes")}</span>`}
            <span class="j-mozg-wt">${n._t}</span><span class="j-mozg-wg">${nazwaMiejsca(mapa.gdzie.get(n.id))}</span>
            ${k >= tytuly.length && zTresci[k - tytuly.length][1] && html`<span class="j-mozg-wo">${zTresci[k - tytuly.length][1]}</span>`}</li>`)}</ul>
          ${ileTytulow > tytuly.length && html`<p class="j-mozg-opis">${L(`i ${ileTytulow - tytuly.length} więcej: dopisz słowo, żeby zawęzić`, `and ${ileTytulow - tytuly.length} more: add a word to narrow down`)}</p>`}`
        : html`<header class="j-mozg-poziom">
            <h2 ref=${naglowek} tabIndex="-1">${tytulPoziomu} ${mapa && html`<span>${ilePoziomu}</span>`}</h2>
            ${kat && kat.opis && !(grupa && kat.grupy.length > 1) && html`<p class="j-mozg-opis">${L(kat.opis, kat.opis_en || kat.opis)}</p>`}
            ${!kat && mapa && html`<p class="j-mozg-opis">${L("Wybierz część, żeby zajrzeć do środka.", "Pick a part to look inside.")}</p>`}
            ${hub && html`<a class="j-mozg-przeglad" href=${hrefNotatki(hub.id)}>${L("Przegląd tej części", "Overview of this part")} →</a>`}
          </header>${poziom}`}
        ${!dane && html`<div class="j-mozg-stan" role="status">${blad ? L("Nie udało się wczytać mózgu.", "Could not load the brain.") : html`<${Spinner}/>`}</div>`}
      </div>
    </div>
    <div class="j-mozg-plotno">
      <canvas ref=${plotno} role="img" aria-label=${L("Mapa wiedzy tego poziomu; to samo jest na liście obok", "Knowledge map of this level; the list shows the same")}></canvas>
      ${graf && html`<p class="j-mozg-podpowiedz" aria-hidden="true">${grupa ? L("Kropka = notatka. Kółko myszy przybliża.", "Dot = note. Scroll to zoom.")
        : L("Kliknij skupisko, żeby wejść.", "Click a cluster to go in.")}</p>`}
    </div>
    ${s.o && dane && mapa && html`<${MozgNotatka} key=${z.klucz + s.o} z=${z} id=${s.o} dane=${dane} mapa=${mapa} href=${hrefNotatki}
      nazwaMiejsca=${nazwaMiejsca} onClose=${() => idz({ o: "" })}/>`}
  </div>`;
}

// rdzeń montuje widok przez Zasoby.wez("MozgWidok") po wczytaniu pakietu (docs/HQ.md „Pakiety”)
if (typeof Zasoby !== "undefined" && Zasoby.daj) Zasoby.daj({ MozgWidok });
