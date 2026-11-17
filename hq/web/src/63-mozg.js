// Mózg Jarva (#/mozg, docs/HQ.md „Mózg”): graf wiedzy z shared/web/graf.js, lista „Notatki” obok (szukaj, strzałki,
// Enter otwiera; działa bez myszy i z czytnikiem ekranu) i karta notatki. Pakiet `mozg` (ten plik + graf.js) i dane
// ładują się dopiero po wejściu w widok. Źródła z GET /mozg/zrodla: skarbiec Jarva (trasy jarvo-wiedza) i grafy
// z konfiguracji instalacji (GET /mozg/<klucz>, notatka jako link `notatka_url`, „Widok 3D ↗” z `widok_3d`).
// Telefon: graf na cały ekran, lista pod przyciskiem „Notatki”, karta arkuszem od dołu, dwa palce przybliżają.
// Kolory z motywu: foldery dostają odcienie ramki, akcentu i przygaszonego tekstu, huby jasne, sieroty w akcencie.
// Style: hq/web/style.css w bloku „@@pakiet mozg” (build wydziela je do mozg-<skrót>.css). Budżet: 6 KB gzip.

const MOZG_WIEDZA = { korzen: "/api/plugins/jarvo-wiedza" };
const MOZG_SKARBIEC = { klucz: "jarvo", nazwa: "Skarbiec Jarva", nazwa_en: "Jarvo's vault", rodzaj: "skarbiec" };

// paleta z motywu; canvas sprowadza każdy kolor (też zmienną) do #rrggbb, więc odcień = ten kolor z przezroczystością
function mozgMotyw(el) {
  const cs = getComputedStyle(el), v = (n) => cs.getPropertyValue(n).trim();
  const ctx = document.createElement("canvas").getContext("2d");
  const hex = (k) => { ctx.fillStyle = "#888"; ctx.fillStyle = k || "#888"; return String(ctx.fillStyle).slice(0, 7); };
  const odcienie = [];
  for (const a of ["", "b0", "70"]) for (const k of ["--j-krawedz", "--j-akcent", "--j-tekst-3"]) odcienie.push(hex(v(k)) + a);
  return { odcienie, motyw: { hub: v("--j-tekst"), tekst: v("--j-tekst"), sierota: v("--j-akcent"), sprzeczna: v("--j-uwaga"), zaznaczony: v("--j-fokus"),
    link: v("--j-linia-mocna"), linkAuto: v("--j-linia"), font: v("--j-font-ui") } };
}

const mozgProste = (s) => String(s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/ł/g, "l");
// filtr listy bez ogonków i wielkości liter, po tytule i ścieżce; huby na górze, potem alfabetycznie
function mozgFiltruj(wezly, q) {
  const f = mozgProste(q).trim();
  return (f ? wezly.filter((n) => n._s.includes(f)) : wezly.slice()).sort((a, b) => (b.hub - a.hub) || a._t.localeCompare(b._t));
}
const mozgUrl = (z, id) => (z && z.notatka_url ? z.notatka_url.split("{id}").join(String(id).split("/").map(encodeURIComponent).join("/")) : "");

function MozgKarta({ z, id, dane, onOpen, onClose }) {
  const [n, setN] = useState(null), ref = useRef(null);
  const skarbiec = z.rodzaj === "skarbiec", w = dane.byId.get(id) || {}, url = mozgUrl(z, id);
  useEffect(() => {
    let zywy = true;
    ref.current.focus();   // Esc i czytnik ekranu: fokus w karcie (na telefonie lista z polem szukania znika)
    if (skarbiec) zadanie("GET", `/note?path=${encodeURIComponent(id)}`, undefined, MOZG_WIEDZA)
      .then((d) => zywy && setN(d), () => zywy && setN({ blad: 1 }));
    return () => { zywy = false; };
  }, [id]);
  const obok = [...new Set(dane.linki.filter((l) => l.z === id || l.do === id).map((l) => (l.z === id ? l.do : l.z)))].slice(0, 60);
  return html`<aside ref=${ref} tabIndex="-1" class="j-mozg-karta" aria-label=${w.tytul || id}>
    <button type="button" class="j-mozg-x" aria-label=${L("Zamknij notatkę", "Close the note")} onClick=${onClose}>×</button>
    <h2>${w.tytul || id}</h2>
    ${skarbiec && (!n ? html`<${Spinner}/>` : n.blad ? "—" : html`<${TrescMd} tekst=${n.tresc || ""}/>`)}
    ${!skarbiec && w.opis && html`<p>${w.opis}</p>`}
    ${url && html`<p><a href=${url} target="_blank" rel="noopener noreferrer">${L("Otwórz notatkę ↗", "Open the note ↗")}</a></p>`}
    ${obok.length > 0 && html`<h3>${L("Powiązane", "Linked")}</h3><ul>${obok.map((c) => html`<li key=${c}><button type="button" class="j-link" onClick=${() => onOpen(c)}>${(dane.byId.get(c) || {}).tytul || c}</button></li>`)}</ul>`}
  </aside>`;
}

function MozgWidok() {
  const korzen = useRef(null), plotno = useRef(null), g = useRef(null), ul = useRef(null);
  const [zrodla, setZrodla] = useState([MOZG_SKARBIEC]);
  const [klucz, setKlucz] = useState("jarvo");
  const [dane, setDane] = useState(null);
  const [blad, setBlad] = useState(false);
  const [q, setQ] = useState("");
  const [i, setI] = useState(0);
  const [otwarta, setOtwarta] = useState(null);
  const [lista, setLista] = useState(false);
  const [ile, setIle] = useState({ wezly: 0, linki: 0 });
  const z = zrodla.find((x) => x.klucz === klucz) || zrodla[0];

  useEffect(() => {
    zadanie("GET", "/mozg/zrodla").then((d) => d.zrodla && setZrodla(d.zrodla), () => {});
    // sterownik grafu raz na widok; motyw czytany co 120 klatek (zmiana motywu bez przeładowania)
    let p = mozgMotyw(korzen.current), co = 0;
    const foldery = new Map();
    g.current = utworzGraf(plotno.current, {
      motyw: () => { if (++co % 120 === 0) p = mozgMotyw(korzen.current); return p.motyw; },
      kolor: (n) => { if (!foldery.has(n.folder)) foldery.set(n.folder, foldery.size); return p.odcienie[foldery.get(n.folder) % 9]; },
      otworz: setOtwarta,
    });
    return () => g.current.zniszcz();
  }, []);

  useEffect(() => {
    let zywy = true;
    setDane(null); setBlad(false); setOtwarta(null);
    (z.rodzaj === "skarbiec" ? zadanie("GET", "/graph", undefined, MOZG_WIEDZA) : zadanie("GET", `/mozg/${encodeURIComponent(z.klucz)}`)).then((d) => {
      if (!zywy) return;
      const wezly = (d.wezly || []).map((n) => ({ ...n, _t: String(n.tytul || n.id), _s: mozgProste(`${n.tytul} ${n.id}`) }));
      setDane({ wezly, linki: d.linki || [], byId: new Map(wezly.map((n) => [n.id, n])) });
    }, () => zywy && setBlad(true));
    return () => { zywy = false; };
  }, [z.klucz]);

  useEffect(() => setIle(g.current.dane(dane)), [dane]);
  useEffect(() => { g.current.zaznacz(otwarta); if (otwarta) g.current.wysrodkuj(otwarta); }, [otwarta]);

  const widac = useMemo(() => (dane ? mozgFiltruj(dane.wezly, q) : []), [dane, q]);
  useEffect(() => setI(0), [widac]);
  useEffect(() => { const li = ul.current.children[i]; if (li && li.scrollIntoView) li.scrollIntoView({ block: "nearest" }); }, [i]);

  const otworz = (id) => { setOtwarta(id); setLista(false); };
  const klawisz = (e) => {
    const d = { ArrowDown: 1, ArrowUp: -1 }[e.key];
    if (d) { e.preventDefault(); setI((x) => Math.max(0, Math.min(widac.length - 1, x + d))); }
    else if (e.key === "Enter" && widac[i]) { e.preventDefault(); otworz(widac[i].id); }
  };
  const esc = (e) => { if (e.key === "Escape" && (otwarta || lista)) { e.stopPropagation(); setOtwarta(null); setLista(false); } };

  return html`<div ref=${korzen} class=${cx("j-mozg", lista && "is-lista")} onKeyDown=${esc} data-mozg>
    <div class="j-mozg-gora">
      <h1>${L("Mózg", "Brain")}</h1>
      ${zrodla.length > 1 && html`<div class="j-mozg-zrodla">${zrodla.map((x) => html`<button key=${x.klucz}
        type="button" aria-pressed=${x === z} onClick=${() => setKlucz(x.klucz)}>${L(x.nazwa, x.nazwa_en)}</button>`)}</div>`}
      ${z.widok_3d && html`<a class="j-mozg-3d" href=${z.widok_3d} target="_blank" rel="noopener noreferrer">${L("Widok 3D ↗", "3D view ↗")}</a>`}
      <span class="j-mozg-meta">${dane && `${ile.wezly} ${L("notatek", "notes")} · ${ile.linki} ${L("linków", "links")}`}</span>
      <button type="button" class="j-mozg-lista-btn" aria-expanded=${lista} onClick=${() => setLista(!lista)}>${L("Notatki", "Notes")}</button>
    </div>
    <div class="j-mozg-lista">
      <input type="search" value=${q} placeholder=${L("Szukaj notatki…", "Search notes…")} aria-label=${L("Szukaj notatki", "Search notes")} role="combobox"
        aria-expanded="true" aria-controls="j-mozg-n" aria-activedescendant=${widac[i] ? `j-mozg-${i}` : undefined} onInput=${(e) => setQ(e.target.value)} onKeyDown=${klawisz}/>
      <ul id="j-mozg-n" role="listbox" aria-label=${L("Notatki", "Notes")} ref=${ul}>${widac.map((n, k) => html`<li key=${n.id} id=${`j-mozg-${k}`} role="option"
        aria-selected=${k === i} class=${n.hub ? "is-hub" : ""} onClick=${() => { setI(k); otworz(n.id); }}>${n._t}</li>`)}</ul>
    </div>
    <div class="j-mozg-plotno">
      <canvas ref=${plotno} role="img" aria-label=${L("Graf wiedzy; notatki są też na liście", "Knowledge graph; notes are also in the list")}></canvas>
      ${!dane && html`<div class="j-mozg-stan" role="status">${blad ? L("Nie udało się wczytać grafu.", "Could not load the graph.") : html`<${Spinner}/>`}</div>`}
    </div>
    ${otwarta && dane && html`<${MozgKarta} key=${z.klucz + otwarta} z=${z} id=${otwarta} dane=${dane} onOpen=${otworz} onClose=${() => setOtwarta(null)}/>`}
  </div>`;
}

// rdzeń montuje widok przez Zasoby.wez("MozgWidok") po wczytaniu pakietu (docs/HQ.md „Pakiety”)
if (typeof Zasoby !== "undefined" && Zasoby.daj) Zasoby.daj({ MozgWidok });
