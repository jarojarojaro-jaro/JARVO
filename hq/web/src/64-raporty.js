// Aktualizacje (#/aktualizacje[/<dzień>][/<rodzaj>], docs/HQ.md „Aktualizacje”): raporty rutyn floty (brief, patrol,
// przegląd tygodnia, świeżość wiedzy, nowe wersje, rutyny agentów) dzień po dniu. Szeroko: raporty wybranego dnia,
// obok mały kalendarz miesiąca (kropki w kolorach rodzajów, pogrubione dni z nowymi raportami) i lista rodzajów
// jako filtr; telefon: data z ‹ › u góry, kalendarz pod przyciskiem, rodzaje w jednym przewijanym rzędzie. Bez dnia
// w adresie widok otwiera ostatni dzień z raportami; ‹ › i strzałki ←/→ skaczą po dniach z raportami (serwer podaje
// sąsiednie). „Odpowiedz” otwiera rozmowę z rozmówcą profilu rutyny (Jarvo: temat JARVO) z cytatem raportu w polu
// wiadomości. Dzień obejrzany bez filtra oznacza raporty jako przeczytane (licznik przy „Aktualizacje” w pasku).
// Nowy raport (zdarzenie `raporty.nowe`) odświeża kalendarz i dzień. Dane: GET /raporty, GET /raporty/kalendarz.
// Pakiet `raporty` (ten plik) ładuje się dopiero po wejściu w widok; style w bloku „@@pakiet raporty” style.css.

const RAPORT_ZWINIETY = 1600;           // dłuższy raport pokazuje się zwinięty (fragment i „Pokaż całość”)
const DZIEN_MAKS = 100;                 // raportów jednego dnia na jedną odpowiedź (rutyny dają kilka dziennie)

// ------------------------------------------------------------------------------------------------- daty (czyste)
const dwa = (n) => String(n).padStart(2, "0");
// dzień kalendarzowy w strefie przeglądarki: "RRRR-MM-DD"
function kluczDnia(ts) {
  const d = new Date(ts * 1000);
  return `${d.getFullYear()}-${dwa(d.getMonth() + 1)}-${dwa(d.getDate())}`;
}
// granice dnia w sekundach: {od: północ, przed: następna północ} (zmiana czasu: Date liczy sam)
function granicyDnia(klucz) {
  const [r, m, d] = klucz.split("-").map(Number);
  return { od: new Date(r, m - 1, d).getTime() / 1000, przed: new Date(r, m - 1, d + 1).getTime() / 1000 };
}
// siatka miesiąca od poniedziałku: pełne tygodnie, dni sąsiednich miesięcy z wMiesiacu = false
function siatkaMiesiaca(rok, miesiac) {
  const pierwszy = new Date(rok, miesiac, 1);
  const przesuniecie = (pierwszy.getDay() + 6) % 7;
  const dniWMiesiacu = new Date(rok, miesiac + 1, 0).getDate();
  const tygodnie = Math.ceil((przesuniecie + dniWMiesiacu) / 7);
  const komorki = [];
  for (let i = 0; i < tygodnie * 7; i++) {
    const d = new Date(rok, miesiac, 1 - przesuniecie + i);
    komorki.push({ klucz: `${d.getFullYear()}-${dwa(d.getMonth() + 1)}-${dwa(d.getDate())}`, dzien: d.getDate(), wMiesiacu: d.getMonth() === miesiac });
  }
  return komorki;
}
// wpisy kalendarza [{ts, rodzaj, nowy, blad}] → {klucz dnia: {liczba, nowe, blad, rodzaje: [rodzaj…] bez powtórzeń}}
function dniKalendarza(wpisy) {
  const dni = {};
  for (const w of wpisy || []) {
    const k = kluczDnia(w.ts);
    const d = dni[k] || (dni[k] = { liczba: 0, nowe: 0, blad: false, rodzaje: [] });
    d.liczba += 1;
    if (w.nowy) d.nowe += 1;
    if (w.blad) d.blad = true;
    if (!d.rodzaje.includes(w.rodzaj)) d.rodzaje.push(w.rodzaj);
  }
  return dni;
}
// kolory rodzajów (--j-barwa-N) w stałej kolejności wyraźnie różnych barw: rodzaje po id alfabetycznie, więc ten sam
// rodzaj ma ten sam kolor w kalendarzu, filtrze i raporcie, a kilka rodzajów nigdy nie dostaje dwóch zieleni
const BARWY_RODZAJOW = [5, 1, 3, 7, 2, 4, 6, 8, 9];
function koloryRodzajow(rodzaje) {
  const mapa = {};
  [...new Set(rodzaje || [])].sort().forEach((r, i) => { mapa[r] = `var(--j-barwa-${BARWY_RODZAJOW[i % BARWY_RODZAJOW.length]})`; });
  return mapa;
}
const DNI_TYGODNIA = { pl: ["pn", "wt", "śr", "cz", "pt", "so", "nd"], en: ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"] };
// tekst do pola wiadomości po „Odpowiedz”: cytat z rodzajem, czasem i pierwszą treściwą linią raportu
function cytatRaportu(r, teraz = Date.now() / 1000) {
  const linia = String(r.tekst || "").split("\n").map((x) => x.replace(/[#>*_`~|]/g, "").replace(/\s+/g, " ").trim()).find(Boolean) || "";
  const krotka = linia.length > 140 ? `${linia.slice(0, 139).trimEnd()}…` : linia;
  const kiedy = kluczDnia(r.ts) === kluczDnia(teraz) ? Czas.godzina(r.ts) : `${Czas.data(r.ts)}, ${Czas.godzina(r.ts)}`;
  return `> ${T("rap.cytat")} „${r.nazwa}” (${kiedy}): ${krotka}\n\n`;
}

// nagłówek dnia: Dziś / Wczoraj, dalej dzień tygodnia z datą (rok tylko poza bieżącym)
function nazwaDnia(klucz, teraz = Date.now() / 1000) {
  const { od } = granicyDnia(klucz);
  const g = Czas.grupa(od + 3600, teraz);
  const d = new Date(od * 1000);
  const pelna = d.toLocaleDateString(isPL() ? "pl-PL" : "en-GB", {
    weekday: "long", day: "numeric", month: "long", ...(d.getFullYear() !== new Date(teraz * 1000).getFullYear() ? { year: "numeric" } : {}) });
  const duza = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  return g === "dzis" || g === "wczoraj" ? { glowna: T(`grupa.${g}`), pod: pelna } : { glowna: duza(pelna), pod: null };
}

// ------------------------------------------------------------------------------------------------- odpowiedź
// „Odpowiedz”: cytat raportu na początek szkicu rozmowy (bez dubla przy drugim kliknięciu), potem rozmowa z kursorem
function odpowiedzNaRaport(r, rozmowca) {
  const k = rozmowca.watek_id || "nowa";
  const cytat = cytatRaportu(r);
  sklep.ustaw((s) => {
    const byl = s.szkice[k] || {};
    const tekst = String(byl.tekst || "");
    if (tekst.startsWith(cytat)) return s;
    return { ...s, szkice: { ...s.szkice, [k]: { tekst: cytat + tekst, pliki: byl.pliki || [], ts: Date.now() / 1000 } } };
  });
  Fokus.odloz("kompozytor");
  Trasa.idz({ widok: "rozmowca", rozmowca: rozmowca.klucz });
}

// ------------------------------------------------------------------------------------------------- raport
function Raport({ r, rozmowca, kolor }) {
  const dlugi = (r.tekst || "").length > RAPORT_ZWINIETY;
  const [caly, setCaly] = useState(!dlugi);
  const [ok, setOk] = useState(false);
  const kopiuj = async () => {
    try { await copyText(r.tekst); setOk(true); setTimeout(() => setOk(false), 1500); } catch (e) { Komunikaty.pokaz(e.message || String(e), { rodzaj: "blad" }); }
  };
  const kto = rozmowca ? nazwaRozmowcy(rozmowca) : "";
  return html`<article class=${cx("j-rap-r", r.nowy && "is-nowy", r.blad && "is-blad", !caly && "is-zwiniety")} data-raport=${r.id}
      style=${{ "--j-rap-kolor": kolor }} aria-labelledby=${`j-rap-r-${r.id}`}>
    <header class="j-rap-r-g">
      <i class="j-rap-kropka" aria-hidden="true"></i>
      <h3 id=${`j-rap-r-${r.id}`}>${r.nazwa}</h3>
      <time datetime=${new Date(r.ts * 1000).toISOString()} title=${`${Czas.data(r.ts)}, ${Czas.godzina(r.ts)}`}>${Czas.godzina(r.ts)}</time>
      ${r.nowy && html`<span class="j-rap-nowy">${T("rap.nowy")}</span>`}
      ${r.blad && html`<span class="j-tag is-blad"><${Ikona} n="alert" r=${12}/>${T("rap.blad")}</span>`}
    </header>
    <div class="j-rap-r-t"><${TrescMd} tekst=${r.tekst} klasa="j-msg-t"/></div>
    <footer class="j-rap-r-s">
      ${rozmowca && html`<${Przycisk} rodzaj="glowny" maly ikona="turn" data-odpowiedz=""
        etykieta=${T("rap.odpowiedz_tip", { kto })} onClick=${() => odpowiedzNaRaport(r, rozmowca)}>${T("rap.odpowiedz")}</${Przycisk}>`}
      ${dlugi && html`<button type="button" class="j-link" aria-expanded=${String(caly)} onClick=${() => setCaly(!caly)}>
        ${T(caly ? "rap.zwin" : "rap.calosc")}</button>`}
      <${Przycisk} rodzaj="cichy" maly ikona=${ok ? "check" : "copy"} etykieta=${T(ok ? "md.skopiowano" : "msg.kopiuj")} klasa="j-rap-kopiuj" onClick=${kopiuj}/>
    </footer>
  </article>`;
}

// ------------------------------------------------------------------------------------------------- kalendarz
// Bez własnych strzałek miesiąca (19.11 właściciel: „dwa sety strzałek, po co miesiące”): miesiąc kalendarza idzie
// za wybranym dniem, a dni zmieniają ‹ › w nagłówku i ←/→; jedyne strzałki w widoku to te dzienne.
function Kalendarz({ miesiac, wybrany, dni, rodzaj, idzDo, dzis, kolory }) {
  const komorki = useMemo(() => siatkaMiesiaca(miesiac.r, miesiac.m), [miesiac.r, miesiac.m]);
  const pl = isPL() ? "pl-PL" : "en-GB";
  const tytul = new Date(miesiac.r, miesiac.m, 1).toLocaleDateString(pl, { month: "long", year: "numeric" }).replace(/^./, (z) => z.toUpperCase());
  const naglowki = DNI_TYGODNIA[isPL() ? "pl" : "en"];
  return html`<div class="j-kal" role="group" aria-label=${T("rap.kalendarz")}>
    <div class="j-kal-g"><b class="j-kal-t" aria-live="polite">${tytul}</b></div>
    <div class="j-kal-siatka">
      ${naglowki.map((n) => html`<span key=${n} class="j-kal-dt" aria-hidden="true">${n}</span>`)}
      ${komorki.map((c) => {
        const d = dni[c.klucz];
        const widoczne = d ? (rodzaj ? d.rodzaje.filter((x) => x === rodzaj) : d.rodzaje) : [];
        const przyszly = c.klucz > dzis;
        const opis = `${nazwaDnia(c.klucz).pod || nazwaDnia(c.klucz).glowna}${d ? `: ${T("rap.w_dniu", { n: d.liczba })}${d.nowe ? `, ${T("rap.nowe", { n: d.nowe })}` : ""}` : ""}`;
        return html`<button type="button" key=${c.klucz} data-dzien=${c.klucz} disabled=${przyszly}
          class=${cx("j-kal-d", !c.wMiesiacu && "is-obok", c.klucz === wybrany && "is-wybrany", c.klucz === dzis && "is-dzis",
            widoczne.length > 0 && "is-ma", d && d.nowe > 0 && "is-nowe", d && d.blad && "is-blad")}
          aria-pressed=${String(c.klucz === wybrany)} aria-current=${c.klucz === dzis ? "date" : undefined} aria-label=${opis}
          onClick=${() => idzDo(c.klucz)}>
          <span>${c.dzien}</span>
          <i class="j-kal-kropki" aria-hidden="true">${widoczne.slice(0, 3).map((x) => html`<b key=${x} style=${{ background: kolory[x] }}></b>`)}</i>
        </button>`;
      })}
    </div>
  </div>`;
}

// filtr rodzaju: zostaje na wybranym dniu, gdy ten dzień ma raport tego rodzaju; inaczej idzie na ostatni dzień rodzaju
function Rodzaje({ rodzaje, rodzaj, dzien, rodzajeDnia, kolory }) {
  const razem = rodzaje.reduce((n, x) => n + x.liczba, 0);
  const pozycja = (wartosc, nazwa, liczba) => {
    const tu = (rodzaj || null) === wartosc;
    return html`<li key=${wartosc || "*"}><a href=${Trasa.zbuduj({ widok: "aktualizacje", dzien: !wartosc || rodzajeDnia.includes(wartosc) ? dzien : undefined, rodzaj: wartosc })} aria-current=${tu ? "true" : undefined}
      class=${cx("j-rap-f", tu && "is-aktywny")} style=${wartosc ? { "--j-rap-kolor": kolory[wartosc] } : undefined}>
      <i class=${cx("j-rap-kropka", !wartosc && "is-wszystkie")} aria-hidden="true"></i><span>${nazwa}</span><small>${liczba}</small></a></li>`;
  };
  return html`<nav class="j-rap-rodzaje" aria-label=${T("rap.filtr")}><ul>
    ${pozycja(null, T("rap.wszystkie"), razem)}${rodzaje.map((x) => pozycja(x.rodzaj, x.nazwa, x.liczba))}</ul></nav>`;
}

// ------------------------------------------------------------------------------------------------- widok
function Aktualizacje({ trasa }) {
  const rodzaj = trasa.rodzaj || null;
  const wersja = useSklep((s) => s.raporty.wersja);
  const rozmowcy = useSklep((s) => s.rozmowcy);
  const dzis = kluczDnia(Date.now() / 1000);
  const start = trasa.dzien || dzis;
  const [miesiac, setMiesiac] = useState(() => { const [r, m] = start.split("-").map(Number); return { r, m: m - 1 }; });
  const [kal, setKal] = useState({ wpisy: [], rodzaje: [], najnowszy: null, wczytany: false });
  const [st, setSt] = useState({ raporty: [], poprzedni: null, nastepny: null, laduje: true, blad: null, dzien: null });
  const [kalOtwarty, setKalOtwarty] = useState(false);       // telefon: kalendarz pod przyciskiem z datą
  const zywy = useRef(true);
  const lista = useRef(null);
  useEffect(() => () => { zywy.current = false; }, []);

  // ostatni dzień z raportami (tego rodzaju przy filtrze), gdy adres nie ma dnia
  const ostatni = useMemo(() => {
    const zrodlo = rodzaj ? kal.rodzaje.filter((x) => x.rodzaj === rodzaj) : kal.rodzaje;
    const ts = zrodlo.reduce((m, x) => Math.max(m, x.ostatni || 0), 0);
    return ts ? kluczDnia(ts) : null;
  }, [kal.rodzaje, rodzaj]);
  const dzien = trasa.dzien || (kal.wczytany ? ostatni || dzis : null);

  // kalendarz miesiąca widoku (z dniami sąsiednich miesięcy w siatce)
  useEffect(() => {
    const kom = siatkaMiesiaca(miesiac.r, miesiac.m);
    const od = granicyDnia(kom[0].klucz).od, przed = granicyDnia(kom[kom.length - 1].klucz).przed;
    api.raporty.kalendarz({ od, do: przed }).then((d) => {
      if (zywy.current) setKal({ wpisy: d.wpisy || [], rodzaje: d.rodzaje || [], najnowszy: d.najnowszy || null, wczytany: true });
    }, (e) => { if (zywy.current) setKal((k) => ({ ...k, wczytany: true })); setSt((s) => ({ ...s, blad: e.message || String(e) })); });
  }, [miesiac.r, miesiac.m, wersja]);

  // wybrany dzień spoza miesiąca kalendarza (‹ ›, strzałki, adres): kalendarz idzie za nim
  useEffect(() => {
    if (!dzien) return;
    const [r, m] = dzien.split("-").map(Number);
    if (r !== miesiac.r || m - 1 !== miesiac.m) setMiesiac({ r, m: m - 1 });
  }, [dzien]);

  // raporty dnia
  const wczytajDzien = async () => {
    if (!dzien) return;
    setSt((s) => ({ ...s, laduje: true, blad: null }));
    try {
      const { od, przed } = granicyDnia(dzien);
      const d = await api.raporty.lista({ od, przed, rodzaj: rodzaj || undefined, limit: DZIEN_MAKS });
      if (!zywy.current) return;
      setSt({ raporty: d.raporty || [], poprzedni: d.poprzedni || null, nastepny: d.nastepny || null, laduje: false, blad: null, dzien });
      sklep.zmien("raporty", { nieprzeczytane: d.nieprzeczytane || 0 });
      // dzień bez filtra pokazuje wszystko z tego dnia: jego najnowszy raport = przeczytane do tej chwili
      const naj = (d.raporty || [])[0];
      if (!rodzaj && naj && naj.ts > (d.przeczytane_do || 0)) akcje.raportyPrzeczytane(naj.ts);
    } catch (e) {
      if (zywy.current) setSt((s) => ({ ...s, laduje: false, blad: e.message || String(e) }));
    }
  };
  useEffect(() => { wczytajDzien(); }, [dzien, rodzaj, wersja]);
  useEffect(() => { if (lista.current) lista.current.scrollTop = 0; }, [dzien, rodzaj]);

  const idzDo = (k, zastap = false) => { setKalOtwarty(false); Trasa.idz({ widok: "aktualizacje", dzien: k, rodzaj: rodzaj || undefined }, { zastap }); };
  const poprzedni = st.dzien === dzien && st.poprzedni ? kluczDnia(st.poprzedni) : null;
  const nastepny = st.dzien === dzien && st.nastepny ? kluczDnia(st.nastepny) : null;
  // ←/→ poprzedni / następny dzień z raportami, gdy widok jest otwarty (na całym dokumencie: po wejściu fokus nie
  // stoi w widoku, a strzałki działają od razu), ale nie w polach tekstowych, menu i oknach
  const sasiedzi = useRef({});
  sasiedzi.current = { poprzedni, nastepny, idzDo };
  useEffect(() => {
    const klawisz = (e) => {
      if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
      if (e.target.closest && e.target.closest("input, textarea, select, [contenteditable], [role=menu], [role=listbox], [role=dialog]")) return;
      const s = sasiedzi.current, cel = e.key === "ArrowLeft" ? s.poprzedni : e.key === "ArrowRight" ? s.nastepny : null;
      if (cel) { e.preventDefault(); s.idzDo(cel); }
    };
    document.addEventListener("keydown", klawisz);
    return () => document.removeEventListener("keydown", klawisz);
  }, []);

  const dni = useMemo(() => dniKalendarza(kal.wpisy), [kal.wpisy]);
  const kolory = useMemo(() => koloryRodzajow(kal.rodzaje.map((x) => x.rodzaj).concat(st.raporty.map((r) => r.rodzaj))), [kal.rodzaje, st.raporty]);
  const rodzaje = useMemo(() => kal.rodzaje.slice().sort((a, b) => b.liczba - a.liczba || a.nazwa.localeCompare(b.nazwa)), [kal.rodzaje]);
  const rozmowcaRaportu = (r) => rozmowcy.find((x) => x.zaplecze === "hermes" && x.cel === r.profil) || null;
  const nd = dzien ? nazwaDnia(dzien) : null;
  const nowe = st.raporty.filter((r) => r.nowy).length;
  const pusto = !kal.rodzaje.length && kal.wczytany;

  const podsumowanie = st.dzien === dzien && st.raporty.length
    ? `${T("rap.w_dniu", { n: st.raporty.length })}${nowe > 0 ? ` · ${T("rap.nowe", { n: nowe })}` : ""}` : null;
  return html`<section class="j-rap" aria-label=${T("rap.tytul")}>
    <${NaglowekWidoku} ikona=${IKONY_WIDOKOW.aktualizacje} tytul=${T("rap.tytul")} opis=${podsumowanie}>
      ${nd && html`<div class="j-rap-nawig">
        ${trasa.dzien && trasa.dzien !== ostatni && html`<${Przycisk} rodzaj="cichy" maly podpowiedz=${T("rap.najnowsze_tip")}
          onClick=${() => Trasa.idz({ widok: "aktualizacje", rodzaj: rodzaj || undefined })}>${T("rap.najnowsze")}</${Przycisk}>`}
        <${Przycisk} rodzaj="cichy" ikona="back" etykieta=${T("rap.poprzedni")} disabled=${!poprzedni} onClick=${() => idzDo(poprzedni)}/>
        <button type="button" class="j-rap-data" aria-expanded=${String(kalOtwarty)} aria-controls="j-rap-bok" onClick=${() => setKalOtwarty(!kalOtwarty)}>
          <b>${nd.glowna}</b>${nd.pod && html`<small>${nd.pod}</small>`}<${Ikona} n="down" r=${14} klasa="j-rap-data-i"/></button>
        <${Przycisk} rodzaj="cichy" ikona="right" etykieta=${T("rap.nastepny")} disabled=${!nastepny} onClick=${() => idzDo(nastepny)}/>
      </div>`}
    </${NaglowekWidoku}>
    <div class="j-rap-tresc" ref=${lista}><div class="j-rap-uklad">
      <div class="j-rap-lista">
        ${st.raporty.map((r) => html`<${Raport} key=${r.id} r=${r} rozmowca=${rozmowcaRaportu(r)} kolor=${kolory[r.rodzaj]}/>`)}
        ${st.blad && html`<p class="j-pasek-pusto" role="alert">${st.blad}
          <button type="button" class="j-link" onClick=${() => wczytajDzien()}>${T("ui.ponow")}</button></p>`}
        ${!st.blad && !st.laduje && !st.raporty.length && (pusto
          ? html`<${Pusto} ikona="repeat" tytul=${T("rap.pusto")}/>`
          : html`<${Pusto} ikona="repeat" tytul=${T(rodzaj ? "rap.dzien_pusto_rodzaj" : "rap.dzien_pusto")}>
              ${ostatni && ostatni !== dzien && html`<button type="button" class="j-link" onClick=${() => Trasa.idz({ widok: "aktualizacje", rodzaj: rodzaj || undefined })}>${T("rap.najnowsze_tip")} →</button>`}
            </${Pusto}>`)}
        ${st.laduje && !st.raporty.length && html`<p class="j-pasek-pusto"><${Spinner}/></p>`}
      </div>
      <aside class=${cx("j-rap-bok", kalOtwarty && "is-otwarty")} id="j-rap-bok">
        <${Kalendarz} miesiac=${miesiac} wybrany=${dzien} dni=${dni} rodzaj=${rodzaj} idzDo=${idzDo} dzis=${dzis} kolory=${kolory}/>
        ${rodzaje.length > 0 && html`<${Rodzaje} rodzaje=${rodzaje} rodzaj=${rodzaj} dzien=${trasa.dzien} rodzajeDnia=${(dni[dzien] || {}).rodzaje || []} kolory=${kolory}/>`}
      </aside>
    </div></div>
  </section>`;
}

// rdzeń montuje widok przez Zasoby.wez("Aktualizacje") po wczytaniu pakietu (docs/HQ.md „Pakiety”)
if (typeof Zasoby !== "undefined" && Zasoby.daj) Zasoby.daj({ Aktualizacje, kluczDnia, granicyDnia, siatkaMiesiaca, dniKalendarza, cytatRaportu });
