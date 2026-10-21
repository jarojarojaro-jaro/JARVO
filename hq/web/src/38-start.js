// Ekran startu (docs/HQ.md „Ekran startu”, makieta V2 · Spokojny): figurka Jarva, powitanie z USER.md, kompozytor
// nowej rozmowy i pod nim najwyżej 4 rzeczy: „Czeka na Ciebie” (zgody, nieudana praca, pytania zespołu) i startery
// „Na początek” (warstwa nauki N0, hq/plugin/podpowiedzi.py). Pod powitaniem jedna linia gotowości tylko wtedy, gdy
// czegoś brakuje (brama, model, poznajmy się); młoda brama to „Jarvo się uruchamia…”, bez czerwonego paska.

// figurka Jarva 24×32 (te same piksele co w makiecie V2): warstwy [klasa, [[kolor, ścieżka], …]]; „lid” = mrugnięcie
const FIGURA_JARVA = [
  ["", [["rgba(0,0,0,.35)", "M5 31h14v1h-14z"], ["#1D2129", "M7 23h10v2h-10zM7 25h4v5h-4zM13 25h4v5h-4z"], ["#16191f", "M15 25h1v5h-1z"],
    ["#08090B", "M7 30h4v1h-4zM13 30h4v1h-4z"], ["#1D2129", "M7 14h10v9h-10z"], ["#111419", "M16 14h1v9h-1z"],
    ["#F1F3F5", "M10 14h4v2h-4zM11 16h2v2h-2z"], ["#951e1e", "M11 14h2v1h-2z"], ["#C62828", "M11 15h2v6h-2z"],
    ["#111419", "M9 15h1v1h-1zM14 15h1v1h-1z"], ["#F1F3F5", "M15 17h1v1h-1z"], ["#111419", "M9 20h1v1h-1zM9 18h1v1h-1z"],
    ["#D9B21E", "M11 13h2v1h-2z"]]],
  ["", [["#F2CD37", "M8 5h8v8h-8z"], ["#D9B21E", "M15 5h1v8h-1zM10 4h4v1h-4z"],
    ["#15171C", "M10 8h1v1h-1zM13 8h1v1h-1zM10 10h1v1h-1zM11 11h2v1h-2zM13 10h1v1h-1z"],
    ["#17120E", "M8 4h8v2h-8zM8 6h1v2h-1zM15 6h1v1h-1z"], ["#5d5956", "M11 4h1v1h-1z"], ["#17120E", "M9 3h6v1h-6z"]]],
  ["lid", [["#F2CD37", "M10 8h1v1h-1zM13 8h1v1h-1z"]]],
  ["", [["#1D2129", "M5 14h2v7h-2z"], ["#F2CD37", "M5 21h2v2h-2z"]]],
  ["", [["#1D2129", "M17 14h2v7h-2z"], ["#111419", "M18 14h1v7h-1z"], ["#F2CD37", "M17 21h2v2h-2z"]]],
];

function FiguraJarva({ skala = 2.5 }) {
  return html`<span class="j-fig" aria-hidden="true"><svg viewBox="0 0 24 32" width=${24 * skala} height=${32 * skala} focusable="false">
    ${FIGURA_JARVA.map(([kl, warstwy], i) => html`<g key=${i} class=${kl ? `j-fig-${kl}` : undefined}>
      ${warstwy.map(([kolor, d], j) => html`<path key=${j} fill=${kolor} d=${d}/>`)}</g>`)}</svg></span>`;
}

// pora dnia z godziny: rano 5–11, dzień 12–17, wieczór 18–4 (PL: „Dzień dobry” do 18, potem „Dobry wieczór”)
const poraDnia = (h) => (h >= 5 && h < 12 ? "rano" : h >= 12 && h < 18 ? "dzien" : "wieczor");

// koordynator nowej rozmowy: Jarvo; tylko w instalacji testu E2E (funkcje.e2e) profil testowy z localStorage
const PROFIL_WZOR = /^[a-z0-9][a-z0-9-]{0,63}$/;
function useKoordynatorStartu() {
  const e2e = useSklep((s) => !!(s.funkcje && s.funkcje.e2e));
  if (!e2e) return "jarvo";
  let k = null;
  try { k = localStorage.getItem("jarvo.e2e.koordynator"); } catch (_) { /* zablokowane */ }
  return k && PROFIL_WZOR.test(k) ? k : "jarvo";
}

const agentWg = (agenci, nazwa) => agenci[nazwa] || { name: nazwa };

// ---- linia gotowości (§13.10): jedno zdanie pod powitaniem i najwyżej jeden przycisk, tylko gdy czegoś brakuje.
// Kolejność: brama (uruchamia się / nie odpowiada), potem model, a gdy model działa: „Poznajmy się” (profil właściciela).
// „Jak działa zespół” jest w Ustawieniach › Zespół, nie na starcie.
function stanGotowosci(got) {
  if (!got) return null;
  if (got.brama === "startuje" || got.brama === "niedostepna") return got.brama;
  if (!(got.model || {}).polaczony) return "model";
  if (!got.profil_wlasciciela) return "poznajmy";
  return null;
}

function LiniaGotowosci({ got, koordynator }) {
  const klucz = stanGotowosci(got);
  if (!klucz) return null;
  const model = got.model || {};
  const akcja = {
    model: [T("gotowosc.polacz"), () => Trasa.idz({ u: "polaczenia", pod: model.sposob === "oauth" ? "modele" : "klucze" }, { scal: true })],
    poznajmy: [T("gotowosc.zacznij"), () => akcje.wyslij({ tekst: T("gotowosc.poznajmy_tekst"), koordynator })],
  }[klucz];
  const ikona = klucz === "startuje" ? html`<${Spinner}/>` : html`<${Ikona} n=${klucz === "model" ? "plug" : klucz === "poznajmy" ? "msg" : "alert"} r=${16}/>`;
  return html`<p class="j-gotowosc" data-gotowosc=${klucz} data-brama=${got.brama || ""}
      role=${klucz === "startuje" || klucz === "niedostepna" ? "status" : undefined}>
    ${ikona}<span>${T(`gotowosc.${klucz}`)}</span>
    ${akcja && html`<button type="button" class="j-link j-got-b" onClick=${akcja[1]}>${akcja[0]}</button>`}</p>`;
}

// ---- „Czeka na Ciebie”: zgody, pytania zespołu i nieudana praca (najwyżej 4). Zgoda i błąd otwierają wątek,
// pytania zespołu (zablokowane karty) decyzje w Starej Bazie, do czasu aż przejdą do rozmów (etap 4)
function tytulCzeka(w) {
  if (w.rodzaj === "zgoda") return T("czeka.zgoda", { agent: nazwaAgenta(w.agent) });
  if (w.rodzaj === "decyzja") return (w.liczba || 1) > 1 ? T("czeka.decyzje", { n: w.liczba }) : T("czeka.decyzja", { agent: nazwaAgenta(w.agent || "jarvo") });
  return T("czeka.blad", { agent: nazwaAgenta(w.agent) });
}
function otworzCzeka(w) {
  if (w.rodzaj === "decyzja") sklep.ustaw({ stara_baza: "decyzje" });
  else Trasa.idz({ widok: "watek", watek: w.watek });
}

function CzekaNaCiebie({ wiersze }) {
  const agenci = useSklep((s) => s.agenci);
  const id = useIdJarvo();
  if (!wiersze || !wiersze.length) return null;
  return html`<section class="j-czeka" aria-labelledby=${`${id}-c`}>
    <h2 class="j-lbl" id=${`${id}-c`}>${T("czeka.tytul")}</h2>
    <div class="j-czeka-l">${wiersze.map((w) => html`<button type="button" class="j-czeka-w" key=${`${w.rodzaj}:${w.przebieg}`}
        data-rodzaj=${w.rodzaj} onClick=${() => otworzCzeka(w)}>
      <${Awatar} agent=${agentWg(agenci, w.agent || "jarvo")} r=${30}/>
      <b>${tytulCzeka(w)}</b>
      <small>${w.rodzaj === "decyzja" ? w.tytul || T("czeka.decyzje_opis") : w.tytul || T("watek.bez_tytulu")}</small>
      <span class="j-czeka-go">${T(w.akcja === "zobacz" ? "czeka.zobacz" : "czeka.napraw")}<${Ikona} n="right" r=${16}/></span></button>`)}</div>
  </section>`;
}

// „pokazana” raz dziennie na starter (localStorage tej przeglądarki; serwer i tak liczy raz po kluczu)
function oznaczPokazane(lista) {
  const d = new Date();
  const dzien = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const byly = Pamiec.wez("jarvo.pokazane.v1", null);
  const ids = new Set(byly && byly.dzien === dzien ? byly.ids : []);
  for (const p of lista) {
    if (ids.has(p.id)) continue;
    ids.add(p.id);
    akcje.reakcja(p.id, "pokazana", `pokazana:${p.id}:${dzien}`);
  }
  Pamiec.daj("jarvo.pokazane.v1", { dzien, ids: [...ids].slice(-40) });
}

// ---- „Na początek”: startery N0 (tytuł, agent · powód), klik wkłada prośbę do kompozytora; × ukrywa, potem „nigdy”
function NaPoczatek({ lista }) {
  const agenci = useSklep((s) => s.agenci);
  const [ukryte, setUkryte] = useState({});           // id → "odrzucona" | "nigdy"
  const id = useIdJarvo();
  const klucz = lista.map((p) => p.id).join(",");
  useEffect(() => {
    if (!lista.length) return undefined;
    const t = setTimeout(() => { if (document.visibilityState !== "hidden") oznaczPokazane(lista); }, 1000);
    return () => clearTimeout(t);
  }, [klucz]);
  if (!lista.length) return null;
  const pl = isPL();
  const pole = (p, k) => (!pl && p[`${k}_en`]) || p[k] || "";
  const kliknij = (p) => {
    akcje.reakcja(p.id, "kliknieta");
    akcje.doKompozytora("nowa", { tekst: pole(p, "prompt"), fokus: true });
  };
  const odrzuc = (p, rodzaj) => {
    setUkryte((u) => ({ ...u, [p.id]: rodzaj }));
    akcje.reakcja(p.id, rodzaj);
  };
  return html`<section class="j-podp" aria-labelledby=${`${id}-p`}>
    <h2 class="j-lbl" id=${`${id}-p`}>${T("podp.na_poczatek")}</h2>
    <div>${lista.map((p) => (ukryte[p.id]
      ? html`<div key=${p.id} class="j-podp-w is-ukryta" role="status" data-podpowiedz=${p.klucz || p.id}><${Ikona} n="check" r=${14}/>
          ${ukryte[p.id] === "nigdy" ? html`<span>${T("podp.nigdy_ok")}</span>`
            : html`<span>${T("podp.ukryte")}</span><button type="button" class="j-link" onClick=${() => odrzuc(p, "nigdy")}>${T("podp.nigdy")}</button>`}</div>`
      : html`<div key=${p.id} class="j-podp-w" data-podpowiedz=${p.klucz || p.id}>
          <button type="button" class="j-podp-b" onClick=${() => kliknij(p)}>
            <${Awatar} agent=${agentWg(agenci, p.agent)} r=${30}/>
            <span class="j-podp-a">${pole(p, "tytul")}</span>
            <span class="j-podp-o">${nazwaAgenta(p.agent)} · ${pole(p, "powod")}</span></button>
          <button type="button" class="j-podp-x j-ma-tip" aria-label=${T("podp.ukryj")} onClick=${() => odrzuc(p, "odrzucona")}>
            <${Ikona} n="x" r=${14}/><${Podpowiedz} tekst=${T("podp.ukryj")}/></button></div>`))}</div>
  </section>`;
}

// ---- start: #/ i #/nowa/<agent> (wybrany adresat na pierwszą wiadomość)
function EkranStartu({ agent }) {
  const wlasciciel = useSklep((s) => s.wlasciciel);
  const got = useSklep((s) => s.gotowosc);
  const ileAgentow = useSklep((s) => s.kolejnosc.filter((n) => n !== "jarvo").length);
  const podp = useSklep((s) => s.podpowiedzi);
  const oczekujace = useSklep((s) => s.wysylane.nowa);
  const koordynator = useKoordynatorStartu();
  const [godzina] = useState(() => new Date().getHours());
  // #/nowa/<agent>: ten agent dostaje pierwszą wiadomość (wybór na jedną wiadomość, jak „Napisz do Web”)
  useEffect(() => {
    if (agent) sklep.zmien("adresaci", { "0:nowa": agent });
  }, [agent]);
  // „Czeka na Ciebie” i startery: przy wejściu i po zmianach wątków (zgoda, błąd), zebrane po 1,5 s
  useEffect(() => {
    akcje.wczytajPodpowiedzi();
    let t = 0;
    const odswiez = () => { clearTimeout(t); t = setTimeout(() => akcje.wczytajPodpowiedzi(), 1500); };
    const usun = [Strumien.naZdarzenie("watek.zmiana", odswiez), Strumien.naZdarzenie("watek.usuniety", odswiez),
      Strumien.naZdarzenie("reset", odswiez)];
    return () => { clearTimeout(t); usun.forEach((f) => f()); };
  }, []);
  const imie = wlasciciel && wlasciciel.imie, firma = wlasciciel && wlasciciel.firma;
  const pora = poraDnia(godzina);
  const nowy = !imie && !!got && !got.profil_wlasciciela;
  const tytul = imie ? T(`start.${pora}_imie`, { imie }) : nowy ? T("start.nowy") : T(`start.${pora}`);
  const podtytul = firma ? T("start.firma", { firma }) : nowy ? T("start.zespol", { n: ileAgentow }) : null;
  const pozycje = (oczekujace || []).map((o) => ({ rodzaj: "wlasciciel", id: `o:${o.klucz}`, ts: o.ts, tekst: o.tekst, oczekuje: o }));
  const czeka = (podp && podp.czeka) || [];
  // bez modelu startery tylko by obiecywały pracę, której nikt nie zrobi: najpierw „Połącz”
  const startery = got && !(got.model || {}).polaczony ? [] : (podp && podp.podpowiedzi) || [];
  return html`<div class="j-start">
    <div class="j-start-in">
      <div class="j-start-hero">
        <${FiguraJarva}/>
        <h1 class="j-witaj">${tytul}</h1>
        ${podtytul && html`<p class="j-start-p">${podtytul}</p>`}
        ${got && html`<${LiniaGotowosci} got=${got} koordynator=${koordynator}/>`}
      </div>
      ${pozycje.length > 0 && html`<div class="j-start-os">${pozycje.map((x) => html`<${WiadomoscWlasciciela} key=${x.id} x=${x} k="nowa"/>`)}</div>`}
      <${Kompozytor} key=${agent || "nowa"} start=${true} koordynator=${koordynator}/>
      ${(czeka.length > 0 || startery.length > 0) && html`<div class="j-start-pod">
        <${CzekaNaCiebie} wiersze=${czeka}/>
        <${NaPoczatek} lista=${startery}/>
      </div>`}
    </div>
  </div>`;
}
