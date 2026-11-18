// Aktualizacje (#/aktualizacje[/<rodzaj>], docs/HQ.md „Aktualizacje”): archiwum raportów rutyn floty (brief, patrol,
// przegląd tygodnia, świeżość wiedzy, nowe wersje, rutyny agentów) do przeglądania. Tylko odczyt: na raport odpowiada
// się w rozmowie z Jarvem (rutyna wpisuje go też do sesji tematu JARVO), link „Odpowiedz w rozmowie” prowadzi tam.
// Od najnowszego, pogrupowane po dniu (Dziś, Wczoraj, data), w dniu po rodzaju raportu; filtr rodzaju w adresie;
// znacznik „nowy” przy nieprzeczytanych, a otwarcie widoku bez filtra oznacza wszystkie jako przeczytane (licznik
// w lewej kolumnie). Nowy raport (zdarzenie `raporty.nowe`) odświeża otwarty widok. Dane: GET /raporty (raporty.py).
// Pakiet `raporty` (ten plik) ładuje się dopiero po wejściu w widok; style w bloku „@@pakiet raporty” style.css.

const RAPORT_ZWINIETY = 900;            // dłuższy raport pokazuje się zwinięty (fragment i „Pokaż całość”)

// raporty od najnowszego → dni [{dzien: "RRRR-MM-DD", ts: północ, sekcje: [{rodzaj, nazwa, raporty}]}]; sekcje dnia
// w kolejności najnowszego raportu rodzaju (czyste, testy node)
function grupujRaporty(raporty) {
  const dni = [];
  for (const r of raporty || []) {
    const d = new Date(r.ts * 1000);
    d.setHours(0, 0, 0, 0);
    const klucz = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    let dzien = dni[dni.length - 1];
    if (!dzien || dzien.dzien !== klucz) {
      dzien = { dzien: klucz, ts: d.getTime() / 1000, sekcje: [] };
      dni.push(dzien);
    }
    let s = dzien.sekcje.find((x) => x.rodzaj === r.rodzaj);
    if (!s) {
      s = { rodzaj: r.rodzaj, nazwa: r.nazwa, raporty: [] };
      dzien.sekcje.push(s);
    }
    s.raporty.push(r);
  }
  return dni;
}

// nagłówek dnia: Dziś, Wczoraj, dalej dzień tygodnia z datą
function dzienRaportow(ts, teraz) {
  const g = Czas.grupa(ts, teraz);
  if (g === "dzis" || g === "wczoraj") return T(`grupa.${g}`);
  return new Date(ts * 1000).toLocaleDateString(isPL() ? "pl-PL" : "en-GB", { weekday: "long", day: "numeric", month: "long" });
}

function Raport({ r, rozmowca }) {
  const dlugi = (r.tekst || "").length > RAPORT_ZWINIETY;
  const [caly, setCaly] = useState(!dlugi);
  const [ok, setOk] = useState(false);
  const kopiuj = async () => {
    try { await copyText(r.tekst); setOk(true); setTimeout(() => setOk(false), 1500); } catch (e) { Komunikaty.pokaz(e.message || String(e), { rodzaj: "blad" }); }
  };
  return html`<article class=${cx("j-rap-r", r.nowy && "is-nowy", r.blad && "is-blad", !caly && "is-zwiniety")} data-raport=${r.id}>
    <header class="j-rap-r-g"><time title=${`${Czas.data(r.ts)}, ${Czas.godzina(r.ts)}`}>${Czas.godzina(r.ts)}</time>
      ${r.nowy && html`<span class="j-rap-nowy">${T("rap.nowy")}</span>`}
      ${r.blad && html`<span class="j-tag is-blad"><${Ikona} n="alert" r=${12}/>${T("rap.blad")}</span>`}</header>
    <div class="j-rap-r-t"><${TrescMd} tekst=${r.tekst} klasa="j-msg-t"/></div>
    <footer class="j-rap-r-s">
      ${dlugi && html`<button type="button" class="j-link" aria-expanded=${String(caly)} onClick=${() => setCaly(!caly)}>
        ${T(caly ? "rap.zwin" : "rap.calosc")}</button>`}
      <${Przycisk} rodzaj="cichy" maly ikona=${ok ? "check" : "copy"} etykieta=${T(ok ? "md.skopiowano" : "msg.kopiuj")} onClick=${kopiuj}/>
      ${rozmowca && html`<a class="j-link j-rap-odp" href=${Trasa.zbuduj({ widok: "rozmowca", rozmowca: rozmowca.klucz })}
        onClick=${() => Fokus.odloz("kompozytor")}><${Ikona} n="turn" r=${14}/>${T("rap.odpowiedz")} · ${nazwaRozmowcy(rozmowca)}</a>`}
    </footer>
  </article>`;
}

function Aktualizacje({ trasa }) {
  const rodzaj = trasa.rodzaj || null;
  const wersja = useSklep((s) => s.raporty.wersja);
  const rozmowcy = useSklep((s) => s.rozmowcy);
  const [st, setSt] = useState({ raporty: [], rodzaje: [], dalej: null, laduje: true, blad: null, przeczytane_do: 0 });
  const zywy = useRef(true);
  useEffect(() => () => { zywy.current = false; }, []);
  const wczytaj = async (dopisz = false) => {
    setSt((s) => ({ ...s, laduje: true, blad: null }));
    try {
      const d = await api.raporty.lista({ rodzaj: rodzaj || undefined, przed: dopisz ? st.dalej : undefined });
      if (!zywy.current) return;
      setSt((s) => ({ ...d, raporty: dopisz ? s.raporty.concat(d.raporty) : d.raporty, laduje: false, blad: null }));
      sklep.zmien("raporty", { nieprzeczytane: d.nieprzeczytane || 0 });
      // widok bez filtra pokazuje wszystko: najnowszy raport = przeczytane (z filtrem inne rodzaje mogą czekać)
      const naj = d.raporty[0];
      if (!dopisz && !rodzaj && naj && naj.ts > (d.przeczytane_do || 0)) akcje.raportyPrzeczytane(naj.ts);
    } catch (e) {
      if (zywy.current) setSt((s) => ({ ...s, laduje: false, blad: e.message || String(e) }));
    }
  };
  useEffect(() => { wczytaj(false); }, [rodzaj, wersja]);
  const dni = useMemo(() => grupujRaporty(st.raporty), [st.raporty]);
  const teraz = Date.now() / 1000;
  const razem = st.rodzaje.reduce((n, x) => n + x.liczba, 0);
  // rozmowa, w której odpowiada się na raport: rozmówca profilu rutyny (Jarvo: temat JARVO)
  const rozmowcaRaportu = (r) => rozmowcy.find((x) => x.zaplecze === "hermes" && x.cel === r.profil) || null;
  const filtr = (wartosc, tekst, liczba) => html`<a key=${wartosc || "*"} href=${Trasa.zbuduj({ widok: "aktualizacje", rodzaj: wartosc })}
    aria-current=${(rodzaj || null) === wartosc ? "page" : undefined} class=${cx("j-rap-f", (rodzaj || null) === wartosc && "is-aktywny")}>
    <span>${tekst}</span>${liczba > 0 && html`<small>${liczba}</small>`}</a>`;
  return html`<section class="j-rap" aria-labelledby="j-rap-t">
    <header class="j-rap-g">
      <h1 id="j-rap-t" tabIndex="-1"><span aria-hidden="true">↻ </span>${T("rap.tytul")}</h1>
      <p class="j-rap-opis">${T("rap.opis")}</p>
      ${st.rodzaje.length > 0 && html`<nav class="j-rap-filtr" aria-label=${T("rap.filtr")}>
        ${filtr(null, T("rap.wszystkie"), razem)}${st.rodzaje.map((x) => filtr(x.rodzaj, x.nazwa, x.liczba))}</nav>`}
    </header>
    <div class="j-rap-lista">
      ${dni.map((d) => html`<section key=${d.dzien} class="j-rap-dzien" aria-labelledby=${`j-rap-d-${d.dzien}`}>
        <h2 class="j-rap-dzien-t" id=${`j-rap-d-${d.dzien}`}>${dzienRaportow(d.ts, teraz)}</h2>
        ${d.sekcje.map((s) => html`<section key=${s.rodzaj} class="j-rap-sekcja" data-rodzaj=${s.rodzaj}>
          <h3 class="j-rap-sekcja-t">${s.nazwa}${s.raporty.length > 1 && html`<small> · ${s.raporty.length}</small>`}</h3>
          ${s.raporty.map((r) => html`<${Raport} key=${r.id} r=${r} rozmowca=${rozmowcaRaportu(r)}/>`)}
        </section>`)}
      </section>`)}
      ${st.blad && html`<p class="j-pasek-pusto" role="alert">${st.blad}
        <button type="button" class="j-link" onClick=${() => wczytaj(false)}>${T("ui.ponow")}</button></p>`}
      ${!st.blad && !st.laduje && !st.raporty.length && html`<${Pusto} ikona="repeat" tytul=${T(rodzaj ? "rap.pusto_rodzaj" : "rap.pusto")}/>`}
      ${st.laduje && html`<p class="j-pasek-pusto"><${Spinner}/></p>`}
      ${st.dalej && !st.laduje && html`<button type="button" class="j-link j-wiecej" onClick=${() => wczytaj(true)}>${T("rap.starsze")}</button>`}
    </div>
  </section>`;
}

// rdzeń montuje widok przez Zasoby.wez("Aktualizacje") po wczytaniu pakietu (docs/HQ.md „Pakiety”)
if (typeof Zasoby !== "undefined" && Zasoby.daj) Zasoby.daj({ Aktualizacje, grupujRaporty });
