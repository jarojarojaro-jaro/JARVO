// Pliki w rozmowie (docs/HQ.md „Aplikacja”): karta pliku z miniaturą i akcjami (Podgląd, Pobierz, Kopiuj ścieżkę,
// Odpal dla HTML, Otwórz w nowej karcie, Kopiuj obraz, Pokaż w folderze), ścieżka floty w tekście (klik = podgląd),
// obraz z dysku floty w Markdownie i okno podglądu. Bezpieczeństwo (§16.4): blob tylko jako src obrazu, wideo i dźwięku
// albo <a download>; SVG nigdy jako blob (<img> z adresem /file, który ma CSP sandbox); „Otwórz w nowej karcie” zawsze
// na /file; PDF w <iframe sandbox> z /file, z linkiem zapasowym, gdy przeglądarka nie pokaże PDF w ramce.

const jestSvg = (path) => /\.svg$/i.test(String(path || ""));
const krotkaSciezka = (path) => Sciezki.krotka(path);

// obraz z dysku floty: SVG z /file (bez bloba), reszta przez blob z autoryzacją (działa też bez logowania)
function useObrazPliku(path) {
  const svg = jestSvg(path);
  const blob = useBlobUrl(path && !svg ? path : null);
  return svg ? urlPliku(path) : blob;
}

function SciezkaPliku({ sciezka, kod, children }) {
  const plik = useMemo(() => fileFromPath(sciezka), [sciezka]);
  return html`<button type="button" class=${cx("j-sciezka", kod && "is-kod")} title=${sciezka}
    onClick=${() => akcje.podglad(plik)}>${children && children.length ? children : krotkaSciezka(sciezka)}</button>`;
}

function ObrazPliku({ sciezka, alt }) {
  const src = useObrazPliku(sciezka);
  return html`<button type="button" class="j-md-obraz" title=${sciezka} onClick=${() => akcje.podglad(fileFromPath(sciezka))}>
    ${src ? html`<img src=${src} alt=${alt || fileFromPath(sciezka).name} loading="lazy"/>` : html`<span>${fileFromPath(sciezka).name}</span>`}</button>`;
}

const IKONA_RODZAJU = { image: "palette", video: "play", audio: "mic", pdf: "book", text: "book", html: "globe", archive: "folder", doc: "book", other: "clip" };

function MiniaturaPliku({ plik }) {
  const obraz = plik.kind === "image";
  const src = useObrazPliku(obraz ? plik.path : null);
  if (obraz && src) return html`<span class="j-plik-mini is-obraz"><img src=${src} alt="" loading="lazy"/></span>`;
  return html`<span class=${cx("j-plik-mini", `is-${plik.kind}`)}><${Ikona} n=${IKONA_RODZAJU[plik.kind] || "clip"} r=${20}/></span>`;
}

// akcje pliku jako lista (menu karty i stopka podglądu); `uwaga` pokazuje wynik (skopiowano, błąd)
function akcjePliku(plik, host, uwaga) {
  const wykonaj = (fn, ok) => async () => {
    try { await fn(); if (ok) uwaga(ok); } catch (e) { uwaga(e.message || String(e), true); }
  };
  const p = [
    { id: "podglad", ikona: "ext", tekst: T("plik.podglad"), akcja: () => akcje.podglad(plik) },
    { id: "pobierz", ikona: "dl", tekst: T("plik.pobierz"), akcja: wykonaj(() => downloadFile(plik)) },
    { id: "kopiuj", ikona: "copy", tekst: host.explorer ? T("plik.kopiuj_sciezke") : T("plik.kopiuj_sciezke"),
      akcja: wykonaj(() => copyText(hostPathOf(plik.path, host)), T("plik.skopiowano")) },
  ];
  if (plik.kind === "html") p.unshift({ id: "odpal", ikona: "play", tekst: T("plik.odpal"), akcja: wykonaj(() => openSite(plik.path)) });
  if (plik.kind === "image" && !jestSvg(plik.path)) {
    p.push({ id: "obraz", ikona: "copy", tekst: T("plik.kopiuj_obraz"), akcja: wykonaj(() => copyImage(plik), T("plik.obraz_w_schowku")) });
  }
  p.push({ id: "karta", ikona: "ext", tekst: T("plik.nowa_karta"), akcja: () => window.open(urlPliku(plik.path), "_blank", "noopener,noreferrer") });
  if (host.explorer) p.push({ id: "folder", ikona: "folder", tekst: T("plik.w_folderze"), akcja: wykonaj(() => api.reveal(plik.path), T("plik.otwieram_folder")) });
  return p;
}

function useUwaga() {
  const [uwaga, setUwaga] = useState(null);
  const czas = useRef(0);
  useEffect(() => () => clearTimeout(czas.current), []);
  const pokaz = (tekst, zle) => {
    clearTimeout(czas.current);
    setUwaga({ tekst, zle });
    czas.current = setTimeout(() => setUwaga(null), zle ? 6000 : 2500);
  };
  return [uwaga, pokaz];
}

// karta pliku: miniatura i nazwa otwierają podgląd; obok Pobierz (albo Odpal dla HTML) i menu z resztą akcji
function KartaPliku({ plik, kompakt = false }) {
  const host = useHost();
  const [menu, setMenu] = useState(null);
  const [uwaga, pokazUwage] = useUwaga();
  if (!plik || !plik.path) return null;
  const pozycje = akcjePliku(plik, host, pokazUwage);
  const glowna = pozycje.find((x) => x.id === (plik.kind === "html" ? "odpal" : "pobierz"));
  const opis = [T(`plik.r_${plik.kind || "other"}`), plik.size != null ? bytes(plik.size) : null].filter(Boolean).join(" · ");
  return html`<div class=${cx("j-plik", kompakt && "is-kompakt", plik.kind === "image" && !kompakt && "is-obraz")} data-plik=${plik.path}>
    <button type="button" class="j-plik-otworz" onClick=${() => akcje.podglad(plik)} title=${plik.path}
      aria-label=${T("plik.otworz", { nazwa: plik.name })}>
      <${MiniaturaPliku} plik=${plik}/>
      <span class="j-plik-t"><span class="j-plik-n">${plik.name}</span><span class="j-plik-o">${opis}</span></span>
    </button>
    <span class="j-plik-akcje">
      <${Przycisk} rodzaj="cichy" maly ikona=${glowna.ikona} etykieta=${glowna.tekst} podpowiedz=${glowna.tekst} onClick=${glowna.akcja}/>
      <${Przycisk} rodzaj="cichy" maly ikona="more" etykieta=${T("plik.wiecej", { nazwa: plik.name })}
        aria-haspopup="menu" aria-expanded=${menu ? "true" : "false"} onClick=${(e) => setMenu(e.currentTarget)}/>
    </span>
    ${uwaga && html`<span class=${cx("j-plik-uwaga", uwaga.zle && "is-zle")} role="status">${uwaga.tekst}</span>`}
    ${menu && html`<${Menu} kotwica=${menu} etykieta=${plik.name} onZamknij=${() => setMenu(null)}
      pozycje=${pozycje.filter((x) => x.id !== glowna.id)}/>`}
  </div>`;
}

// okno podglądu (sklep.podglad): obraz, wideo, dźwięk, PDF, tekst i kod HTML (jako tekst, bez wykonywania)
function PodgladPliku() {
  const plik = useSklep((s) => s.podglad);
  return plik ? html`<${OknoPodgladu} key=${plik.path} plik=${plik}/>` : null;
}

function OknoPodgladu({ plik }) {
  const host = useHost();
  const [uwaga, pokazUwage] = useUwaga();
  const media = ["image", "video", "audio"].includes(plik.kind);
  const src = useObrazPliku(plik.kind === "image" ? plik.path : null);
  const blob = useBlobUrl(media && plik.kind !== "image" ? plik.path : null);
  const [tekst, setTekst] = useState(null);
  const [blad, setBlad] = useState(false);
  useEffect(() => {
    if (plik.kind !== "text" && plik.kind !== "html") return undefined;
    let zywy = true;
    api.fileBlob(plik.path).then((b) => b.text()).then((t) => zywy && setTekst(t.slice(0, 60000)), () => zywy && setBlad(true));
    return () => { zywy = false; };
  }, [plik.path]);
  const zamknij = () => akcje.podglad(null);
  const pozycje = akcjePliku(plik, host, pokazUwage).filter((x) => x.id !== "podglad");
  const stopka = html`<div class="j-podglad-akcje">
    ${pozycje.map((x, i) => html`<${Przycisk} key=${x.id} rodzaj=${i === 0 ? "mocny" : "zwykly"} maly ikona=${x.ikona} onClick=${x.akcja}>${x.tekst}</${Przycisk}>`)}
    ${uwaga && html`<span class=${cx("j-plik-uwaga", uwaga.zle && "is-zle")} role="status">${uwaga.tekst}</span>`}</div>`;
  let tresc;
  if (plik.kind === "image") tresc = src ? html`<img class="j-podglad-obraz" src=${src} alt=${plik.name}/>` : html`<${Spinner}/>`;
  else if (plik.kind === "video") tresc = blob ? html`<video class="j-podglad-obraz" src=${blob} controls playsinline></video>` : html`<${Spinner}/>`;
  else if (plik.kind === "audio") tresc = blob ? html`<audio class="j-podglad-audio" src=${blob} controls></audio>` : html`<${Spinner}/>`;
  else if (plik.kind === "pdf") {
    tresc = html`<iframe class="j-podglad-pdf" sandbox="" src=${urlPliku(plik.path)} title=${plik.name} referrerpolicy="no-referrer"></iframe>
      <p class="j-podglad-uwaga">${T("plik.pdf_zapas")} <a class="j-link" href=${urlPliku(plik.path)} target="_blank" rel="noopener noreferrer">${T("plik.nowa_karta")}</a></p>`;
  } else if (plik.kind === "text" || plik.kind === "html") {
    tresc = blad ? html`<p class="j-podglad-uwaga">${T("plik.nie_wczytano")}</p>`
      : html`<pre class="j-podglad-tekst" tabIndex="0">${tekst == null ? T("plik.wczytuje") : tekst}</pre>`;
  } else tresc = html`<p class="j-podglad-uwaga">${T("plik.bez_podgladu")}</p>`;
  return html`<${Okno} tytul=${plik.name} onZamknij=${zamknij} klasa="j-podglad" stopka=${stopka}>
    <p class="j-podglad-sciezka" title=${plik.path}>${hostPathOf(plik.path, host)}${plik.size != null ? ` · ${bytes(plik.size)}` : ""}</p>
    <div class=${cx("j-podglad-t", `is-${plik.kind}`)}>${tresc}</div>
  </${Okno}>`;
}
