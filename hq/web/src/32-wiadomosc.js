// Wiadomości w osi wątku (docs/HQ.md „Aplikacja”, makieta V2 · Spokojny): dymek właściciela (od razu, zanim serwer
// odpowie; nieudana wysyłka z „Spróbuj ponownie” i „Usuń”), wiadomość agenta (Markdown, karty plików, Kopiuj,
// „Odpowiedz: <agent>”, znacznik „bezpośrednio”), kroki pracy (Prosty: jedna linia do rozwinięcia; Szczegóły: lista
// z podglądem wyników), żywy dymek trwającej pracy (tekst z delt, stan, czas, kolejka), prośba o zgodę (dokładnie
// wybory zdarzenia, odliczanie, „Czas minął” i „Poproś ponownie”), błąd z „Ponów” i pozycje systemowe.

const useIdJarvo = React.useId || (() => {
  const r = useRef(null);
  if (r.current === null) r.current = `j${Math.random().toString(36).slice(2, 9)}`;
  return r.current;
});

// zegar odświeżany co `ms`, tylko gdy włączony (odliczanie zgody, czas pracy)
function useTeraz(ms, wlaczony = true) {
  const [t, setT] = useState(() => Date.now() / 1000);
  useEffect(() => {
    if (!wlaczony) return undefined;
    setT(Date.now() / 1000);
    const i = setInterval(() => setT(Date.now() / 1000), ms);
    return () => clearInterval(i);
  }, [ms, wlaczony]);
  return t;
}

function useAgent(nazwa) {
  const a = useSklep((s) => s.agenci[nazwa]);
  return a || { name: nazwa || "" };
}

const czasPelny = (ts) => (ts ? `${Czas.data(ts)}, ${Czas.godzina(ts)}` : "");

function NaglowekAgenta({ agent, ts, bezposrednio }) {
  const a = useAgent(agent);
  return html`<header class="j-msg-g"><${Awatar} agent=${a} r=${28}/><b class="j-msg-n">${nazwaAgenta(agent)}</b>
    ${bezposrednio && html`<span class="j-tag">${T("msg.bezposrednio")}</span>`}
    ${ts ? html`<time title=${czasPelny(ts)}>${Czas.godzina(ts)}</time>` : null}</header>`;
}

// akcje pod wiadomością (widoczne po najechaniu i przy fokusie; na dotyku zawsze): Kopiuj, Odpowiedz: <agent>
function AkcjeWiadomosci({ tekst, agent, watek, koordynator }) {
  const [ok, setOk] = useState(false);
  const kopiuj = async () => {
    try { await copyText(tekst); setOk(true); setTimeout(() => setOk(false), 1500); } catch (e) { Komunikaty.pokaz(e.message || String(e), { rodzaj: "blad" }); }
  };
  const etykieta = T(ok ? "md.skopiowano" : "msg.kopiuj");
  return html`<div class="j-msg-akcje">
    ${tekst && html`<${Przycisk} rodzaj="cichy" maly ikona=${ok ? "check" : "copy"} etykieta=${etykieta} podpowiedz=${etykieta} onClick=${kopiuj}/>`}
    ${agent && agent !== koordynator && html`<${Przycisk} rodzaj="cichy" maly ikona="turn" klasa="j-msg-odp"
      onClick=${() => akcje.odpowiedz(watek, agent)}>${T("msg.odpowiedz", { agent: nazwaAgenta(agent) })}</${Przycisk}>`}
  </div>`;
}

const OBRAZ_DATA = /^data:image\/(png|jpeg|gif|webp);base64,/;

// ------------------------------------------------------------------------------------------------- właściciel
function WiadomoscWlasciciela({ x, k }) {
  const o = x.oczekuje, w = x.wpis || {};
  const adresaci = (o ? o.adresaci : w.adresaci) || [];
  const bezposrednio = o ? adresaci.length > 0 : x.tryb === "bezposrednio";
  // zapisany wpis: załączniki z /upload (path, name, size, kind) i obrazy z wiadomości (path); bez powtórek ścieżek
  const pliki = o ? o.pliki || [] : [...new Map((x.pliki || [])
    .concat((w.zalaczniki || []).filter((z) => z && z.path).map((z) => ({ ...fileFromPath(z.path), ...z })))
    .concat((w.obrazy || []).filter((b) => b && b.path).map((b) => ({ ...fileFromPath(b.path), size: b.size })))
    .map((p) => [p.path, p])).values()];
  const obrazy = o ? (o.obrazy || []).filter((b) => OBRAZ_DATA.test(b.dane || "")) : [];
  return html`<article class="j-msg j-msg-ja" data-wpis=${o ? undefined : x.id}>
    <h3 class="j-sr">${T("os.ty")}, ${Czas.godzina(x.ts)}</h3>
    ${bezposrednio && adresaci.length > 0 && html`<p class="j-msg-tag"><${Ikona} n="turn" r=${14}/>
      <span>${T("msg.bezposrednio")} · ${adresaci.map(nazwaAgenta).join(", ")}</span></p>`}
    ${x.tekst && html`<div class=${cx("j-babel", o && o.stan === "blad" && "is-blad")} title=${czasPelny(x.ts)}>${x.tekst}</div>`}
    ${(obrazy.length > 0 || pliki.length > 0) && html`<div class="j-msg-pliki">
      ${obrazy.map((b, i) => html`<img key=${i} class="j-zal-obraz" src=${b.dane} alt=${b.nazwa || ""}/>`)}
      ${pliki.map((p) => html`<${KartaPliku} key=${p.path} plik=${p} kompakt=${true}/>`)}</div>`}
    ${o && html`<${StanWysylki} o=${o} k=${k}/>`}
  </article>`;
}

// wiadomość w drodze: „Wysyłam…” dopiero po chwili (bez migania), nieudana z „Spróbuj ponownie” i „Usuń”
function StanWysylki({ o, k }) {
  const [dlugo, setDlugo] = useState(false);
  useEffect(() => {
    if (o.stan !== "wysylanie") return undefined;
    const t = setTimeout(() => setDlugo(true), 1200);
    return () => clearTimeout(t);
  }, [o.stan]);
  if (o.stan === "blad") {
    return html`<p class="j-msg-stan is-blad" role="alert"><${Ikona} n="alert" r=${14}/>
      <span>${T("wysylka.nie_wyslano")}${o.blad ? ` ${o.blad}` : ""}</span>
      <button type="button" class="j-link" onClick=${() => akcje.ponowWysylke(k, o.klucz)}>${T("ui.ponow")}</button>
      <button type="button" class="j-link" onClick=${() => akcje.porzucWysylke(k, o.klucz)}>${T("wysylka.usun")}</button></p>`;
  }
  return dlugo ? html`<p class="j-msg-stan">${T("wysylka.wysylam")}</p>` : null;
}

// ------------------------------------------------------------------------------------------------- agent
function WiadomoscAgenta({ x, ctx, ostatniaPrzebiegu }) {
  const pomin = useMemo(() => new Set((x.pliki || []).map((p) => p.path)), [x.pliki]);
  const bezposrednio = x.tryb === "bezposrednio" && x.agent !== ctx.koordynator;
  return html`<article class="j-msg j-msg-ag" data-pozycja=${x.id} data-agent=${x.agent}>
    <h3 class="j-sr">${nazwaAgenta(x.agent)}, ${Czas.godzina(x.ts)}</h3>
    <${NaglowekAgenta} agent=${x.agent} ts=${x.ts} bezposrednio=${bezposrednio}/>
    ${x.kroki && x.kroki.length > 0 && html`<${Kroki} kroki=${x.kroki} szczegoly=${ctx.szczegoly}/>`}
    <${TrescMd} tekst=${x.tekst} pomin=${pomin} klasa="j-msg-t"/>
    ${x.pliki && x.pliki.length > 0 && html`<div class="j-pliki">${x.pliki.map((p) => html`<${KartaPliku} key=${p.path} plik=${p}/>`)}</div>`}
    ${ostatniaPrzebiegu && x.przebieg_id && html`<${ZgodaPoKoncu} pid=${x.przebieg_id} ctx=${ctx}/>`}
    ${x.zatrzymany && html`<${MetaPrzebiegu} p=${x.zatrzymany}/>`}
    <${AkcjeWiadomosci} tekst=${x.tekst} agent=${x.agent} watek=${ctx.watek} koordynator=${ctx.koordynator}/>
  </article>`;
}

// wygasła zgoda zostaje pod ostatnią wiadomością przebiegu także po jego końcu, tak samo linia z odpowiedzią właściciela
function ZgodaPoKoncu({ pid, ctx }) {
  const p = useSklep((s) => s.przebiegi[pid]);
  const z = p && (p.zgoda_wygasla || (p.zgoda && p.zgoda.wygasla ? p.zgoda : null));
  if (z) return html`<${ZgodaWygasla} p=${p} z=${z} ctx=${ctx}/>`;
  return p && p.zgoda_odp ? html`<${ZgodaOdpowiedz} odp=${p.zgoda_odp} pid=${pid}/>` : null;
}

// po „Zezwól” albo „Odmów” karta znika, a zostaje jedna spokojna linia z tym, co się stało
// (tabIndex -1: po kliknięciu w karcie fokus przechodzi tutaj, a nie na <body>)
function ZgodaOdpowiedz({ odp, pid }) {
  const nie = odp.wybor === "deny";
  return html`<p class=${cx("j-zgoda-po", nie && "is-nie")} data-wybor=${odp.wybor} data-zgoda-po=${pid} tabIndex="-1"><${Ikona} n=${nie ? "x" : "check"} r=${14}/>
    <span>${nie ? T("zgoda.odp_nie") : T("zgoda.odp_tak", { wybor: T(`zgoda.w_${odp.wybor}`) })}</span></p>`;
}

// ------------------------------------------------------------------------------------------------- kroki pracy
const czasownik = (k) => (isPL() ? k.verb || k.narzedzie : k.verb_en || k.verb || k.narzedzie) || "";
const KROKI_NAJPIERW = 80;

function KrokiLista({ kroki, szczegoly }) {
  const [wszystkie, setWszystkie] = useState(false);
  const widoczne = wszystkie ? kroki : kroki.slice(-KROKI_NAJPIERW);
  return html`<div class="j-kroki-l">
    ${widoczne.length < kroki.length && html`<button type="button" class="j-link" onClick=${() => setWszystkie(true)}>
      ${T("kroki.wczesniejsze", { n: kroki.length - widoczne.length })}</button>`}
    <ol>${widoczne.map((k, i) => html`<li key=${i} class=${cx(k.blad && "is-blad")}>
      <time>${Czas.godzina(k.ts)}</time>
      <span class="j-kroki-o"><b>${czasownik(k)}</b>${k.detail ? ` ${k.detail}` : ""}${k.blad ? html` <span class="j-kroki-blad">· ${T("kroki.blad")}</span>` : null}
        ${szczegoly && k.czas_ms > 0 && html` <span class="j-kroki-czas">${Czas.trwanie(k.czas_ms / 1000)}</span>`}</span>
      ${szczegoly && k.podglad && html`<pre class="j-kroki-podglad">${k.podglad}</pre>`}</li>`)}</ol></div>`;
}

// Prosty: zwinięta linia „12 kroków · 2:05” (przy trwającej pracy też ostatni krok); Szczegóły: rozwinięte
function Kroki({ kroki, szczegoly, zywe }) {
  const [otwarte, setOtwarte] = useState(!!szczegoly);
  useEffect(() => setOtwarte(!!szczegoly), [szczegoly]);
  const id = useIdJarvo();
  const s = Os.krokiPodsumowanie(kroki);
  if (!s.n) return null;
  return html`<div class=${cx("j-kroki", zywe && "is-zywe")}>
    <button type="button" class="j-kroki-b" aria-expanded=${String(otwarte)} aria-controls=${id} onClick=${() => setOtwarte(!otwarte)}>
      <${Ikona} n="right" r=${14}/><span>${T("os.kroki", { n: s.n })}${s.sekundy ? ` · ${Czas.trwanie(s.sekundy)}` : ""}</span>
      ${s.bledy > 0 && html`<span class="j-kroki-blad">· ${T("kroki.bledy", { n: s.bledy })}</span>`}
      ${zywe && s.ostatni && html`<span class="j-kroki-teraz">· ${czasownik(s.ostatni)}</span>`}
    </button>
    <div id=${id} hidden=${!otwarte}>${otwarte && html`<${KrokiLista} kroki=${kroki} szczegoly=${szczegoly}/>`}</div>
  </div>`;
}

// ------------------------------------------------------------------------------------------------- zgoda
function Zgoda({ p }) {
  const z = p.zgoda;
  const teraz = useTeraz(1000);
  const [wysylam, setWysylam] = useState(null);
  const [polecenie, setPolecenie] = useState(false);
  const [wiecej, setWiecej] = useState(null);
  const id = useIdJarvo();
  const { widoczne, wiecej: ukryte } = Os.wyboryZgody(z.wybory);
  const odliczanie = Czas.odliczanie(z.wygasa_at, teraz);
  const odpowiedz = async (w) => {
    setWysylam(w);
    try { await akcje.zgoda(p, w); } finally { setWysylam(null); }
  };
  const ryzyko = isPL() && z.ryzyko ? z.ryzyko : T(`zgoda.r_${Os.ryzyko(z)}`);
  // opis z Hermesa jest po angielsku: po polsku tylko pod „Pokaż polecenie”, obok samego polecenia
  const opisWSzczegolach = !!z.opis && isPL();
  const szczegoly = !!z.polecenie || opisWSzczegolach;
  return html`<div class="j-zgoda" role="group" aria-labelledby=${`${id}-q`}>
    <p class="j-zgoda-h"><${Ikona} n="hand" r=${14}/><span>${T("zgoda.naglowek", { agent: nazwaAgenta(p.agent) })}</span>
      <span class="j-rozpych"></span>
      <span class=${cx("j-zgoda-czas", odliczanie.zostalo <= 10 && "is-malo")} role="timer" aria-live="off"
        title=${T("zgoda.czas_opis")}>${odliczanie.minelo ? T("zgoda.mija") : odliczanie.tekst}</span></p>
    <p class="j-zgoda-q" id=${`${id}-q`}>${ryzyko}</p>
    ${z.opis && !isPL() && html`<p class="j-zgoda-p">${z.opis}</p>`}
    <div class="j-zgoda-b">
      ${widoczne.map((w, i) => html`<${Przycisk} key=${w} maly rodzaj=${w === "deny" ? "cichy" : i === 0 ? "mocny" : "zwykly"}
        disabled=${!!wysylam} onClick=${() => odpowiedz(w)}>${wysylam === w ? html`<${Spinner}/>` : null}${T(`zgoda.w_${w}`)}</${Przycisk}>`)}
      ${ukryte.length > 0 && html`<${Przycisk} maly rodzaj="cichy" ikona="more" aria-haspopup="menu" disabled=${!!wysylam}
        onClick=${(e) => setWiecej(e.currentTarget)}>${T("zgoda.wiecej")}</${Przycisk}>`}
      <span class="j-rozpych"></span>
      ${szczegoly && html`<button type="button" class="j-link" aria-expanded=${String(polecenie)} aria-controls=${`${id}-p`}
        onClick=${() => setPolecenie(!polecenie)}>${T(polecenie ? "zgoda.ukryj_polecenie" : "zgoda.pokaz_polecenie")}<${Ikona} n="down" r=${14}/></button>`}
    </div>
    ${szczegoly && html`<div class="j-zgoda-szcz" id=${`${id}-p`} hidden=${!polecenie}>
      ${opisWSzczegolach && html`<p class="j-zgoda-p">${z.opis}</p>`}
      ${z.polecenie && html`<pre class="j-zgoda-pol"><code>${z.polecenie}</code></pre>`}</div>`}
    ${wiecej && html`<${Menu} kotwica=${wiecej} etykieta=${T("zgoda.wiecej")} onZamknij=${() => setWiecej(null)}
      pozycje=${ukryte.map((w) => ({ id: w, tekst: T(`zgoda.w_${w}`), ikona: "check", akcja: () => odpowiedz(w) }))}/>`}
  </div>`;
}

// czas minął: polecenie się nie wykonało; „Poproś ponownie” wysyła prośbę do tego samego agenta (jedna wiadomość)
function ZgodaWygasla({ p, z, ctx }) {
  const [wyslano, setWyslano] = useState(false);
  const prosba = () => {
    setWyslano(true);
    akcje.wyslij({ watek: ctx.watek, tekst: T("zgoda.ponow_tekst"), koordynator: ctx.koordynator,
      adresaci: p.agent !== ctx.koordynator ? [p.agent] : null });
  };
  return html`<div class="j-zgoda is-wygasla" role="group" aria-label=${T("zgoda.minelo")}>
    <p class="j-zgoda-h"><${Ikona} n="alert" r=${14}/><span>${T("zgoda.minelo")}</span></p>
    ${z.opis && !isPL() && html`<p class="j-zgoda-p">${z.opis}</p>`}
    <div class="j-zgoda-b">${wyslano
      ? html`<span class="j-zgoda-odp"><${Ikona} n="check" r=${14}/>${T("zgoda.poproszono")}</span>`
      : html`<${Przycisk} maly rodzaj="mocny" ikona="repeat" onClick=${prosba}>${T("zgoda.ponow")}</${Przycisk}>`}</div>
  </div>`;
}

// ------------------------------------------------------------------------------------------------- błąd i stan
// szczegóły techniczne błędu (surowy komunikat Hermesa) zwinięte: właściciel widzi najpierw zdanie po polsku
const SzczegolyBledu = ({ tekst }) => (tekst ? html`<details class="j-blad-sz"><summary>${T("blad.szczegoly")}</summary>
  <p>${String(tekst).slice(0, 600)}</p></details>` : null);

function BladPrzebiegu({ p }) {
  const b = p.blad || {};
  const kl = Os.klasaBledu(b);
  const tekst = (isPL() ? b.komunikat : b.komunikat_en || b.komunikat) || T(`przebieg.${p.stan}`);
  return html`<div class="j-blad-p" role="group" aria-label=${T("przebieg.blad")}>
    <p class="j-blad-t"><${Ikona} n="alert" r=${16}/><span>${tekst}</span></p>
    <${SzczegolyBledu} tekst=${b.szczegoly}/>
    <div class="j-blad-b">
      ${kl.sekcja && html`<${Przycisk} maly onClick=${() => Trasa.idz({ u: kl.sekcja, pod: kl.pod }, { scal: true })}>
        ${T(kl.pod === "klucze" ? "blad.otworz_klucze" : "blad.otworz_modele")}</${Przycisk}>`}
      <${Przycisk} maly rodzaj="mocny" ikona="repeat" onClick=${() => akcje.ponow(p.id)}>${T("przebieg.ponow")}</${Przycisk}>
    </div></div>`;
}

const POWODY_KOLEJKI = new Set(["zajety_agent", "tura", "limit", "wstrzymane", "misja", "start", "brama"]);

// linia stanu pod dymkiem. Trwającą pracę (stan, czas, Zatrzymaj) pokazuje raz pasek nad kompozytorem, a w dymku
// widać kropki pisania i tekst; tu zostaje tylko to, czego pasek nie mówi: powód kolejki z jej przyciskami, „trwa
// dłużej niż zwykle” i „Zatrzymane · Ponów” po Stopie.
function MetaPrzebiegu({ p }) {
  const trwa = !Os.KONCOWE.has(p.stan);
  const kolejka = p.stan === "kolejka";
  if (p.stan !== "zatrzymane" && !kolejka && !(trwa && p.dlugo)) return null;
  const tekst = kolejka ? T(`kolejka.${POWODY_KOLEJKI.has(p.powod) ? p.powod : "inne"}`)
    : p.stan === "zatrzymane" ? T("przebieg.zatrzymane") : T("przebieg.dlugo");
  return html`<p class="j-msg-meta" data-stan=${p.stan}>${kolejka ? html`<span class="j-kropka"></span>` : null}<span>${tekst}</span>
    ${kolejka && (p.powod === "wstrzymane" || p.powod === "misja") && html`<button type="button" class="j-link"
      onClick=${() => akcje.wyslijTeraz(p.id)}>${T("kolejka.wyslij_teraz")}</button>`}
    ${kolejka && html`<button type="button" class="j-link" onClick=${() => akcje.anuluj(p.id)}>${T("kolejka.anuluj")}</button>`}
    ${p.stan === "zatrzymane" && html`<button type="button" class="j-link" onClick=${() => akcje.ponow(p.id)}>${T("przebieg.ponow")}</button>`}
  </p>`;
}

const Pisze = () => html`<p class="j-pisze" aria-hidden="true"><i></i><i></i><i></i></p>`;

// żywy dymek przebiegu: tekst z delt (po przeładowaniu z tekst_dotad migawki), kroki, zgoda, błąd, stan
function ZywyDymek({ p, ctx }) {
  const trwa = !Os.KONCOWE.has(p.stan);
  const z = p.zgoda;
  const zgoda = p.stan === "czeka_na_zgode" && z && !z.wygasla;
  const wygasla = !zgoda && (p.zgoda_wygasla || (z && z.wygasla ? z : null));
  const blad = p.stan === "blad" || p.stan === "przerwane" || p.stan === "zgubione";
  const od = p.przyjety_at || p.utworzony_at;
  const bezposrednio = p.agent !== ctx.koordynator && (p.zrodlo || "wlasciciel") === "wlasciciel";
  return html`<article class="j-msg j-msg-ag is-zywy" data-przebieg=${p.id} data-agent=${p.agent} aria-busy=${String(trwa)}>
    <h3 class="j-sr">${nazwaAgenta(p.agent)}, ${Czas.godzina(od)}</h3>
    <${NaglowekAgenta} agent=${p.agent} ts=${od} bezposrednio=${bezposrednio}/>
    ${p.kroki && p.kroki.length > 0 && html`<${Kroki} kroki=${p.kroki} szczegoly=${ctx.szczegoly} zywe=${trwa}/>`}
    ${p.tekst ? html`<${TrescMd} tekst=${p.tekst} zywy=${trwa} klasa="j-msg-t"/>`
      : trwa && !zgoda && p.stan !== "kolejka" ? html`<${Pisze}/>` : null}
    ${zgoda && html`<${Zgoda} key=${z.request_id} p=${p}/>`}
    ${wygasla && html`<${ZgodaWygasla} p=${p} z=${wygasla} ctx=${ctx}/>`}
    ${!zgoda && !wygasla && p.zgoda_odp && html`<${ZgodaOdpowiedz} odp=${p.zgoda_odp} pid=${p.id}/>`}
    ${blad && html`<${BladPrzebiegu} p=${p}/>`}
    <${MetaPrzebiegu} p=${p}/>
    ${!trwa && p.tekst && html`<${AkcjeWiadomosci} tekst=${p.tekst} agent=${p.agent} watek=${ctx.watek} koordynator=${ctx.koordynator}/>`}
  </article>`;
}

// ------------------------------------------------------------------------------------------------- systemowe
function PozycjaSystemowa({ x }) {
  let tekst = x.tekst || T("os.zdarzenie"), ikona = null;
  if (x.rodzaj === "luka") { tekst = T("os.luka"); ikona = "alert"; }
  else if (x.rodzaj === "kompresja") tekst = T("os.kompresja");
  else if (x.rodzaj === "dopisano") { tekst = T("os.dopisano", { tekst: x.tekst || "" }); ikona = "plus"; }
  else if (x.rodzaj === "dostawa") { tekst = T("os.dostawa", { agent: nazwaAgenta(x.agent) }); ikona = "dl"; }
  else if (x.rodzaj === "przekazanie") {
    const k = x.karta || {};
    tekst = T("os.przekazanie", { tytul: k.tytul || x.tekst || "", agent: nazwaAgenta(k.agent || "") });
    ikona = "arrow";
  } else if (x.rodzaj === "budzenie") {
    const b = x.budzenie || {};
    tekst = T("os.budzenie", { tytul: b.tytul || "", stan: (isPL() ? b.status_pl : b.status_en) || b.status || "" });
    ikona = "repeat";
  }
  return html`<p class=${cx("j-msg-sys", `is-${x.rodzaj}`)}>${ikona && html`<${Ikona} n=${ikona} r=${14}/>`}<span>${tekst}</span></p>`;
}

// wiadomość z innego kanału albo spoza aplikacji (wiersz sesji agenta, którego nie wysłała aplikacja)
function WiadomoscObca({ x }) {
  return html`<article class="j-msg j-msg-ja is-obca">
    <h3 class="j-sr">${T("os.obca")}, ${Czas.godzina(x.ts)}</h3>
    <p class="j-msg-tag"><${Ikona} n="msg" r=${14}/><span>${T("os.obca")}</span></p>
    <div class="j-babel is-obca">${x.tekst}</div></article>`;
}

function BladTury({ x }) {
  return html`<div class="j-msg j-blad-tury" role="note"><p class="j-blad-t"><${Ikona} n="alert" r=${14}/>
    <span>${T("os.blad_tury", { agent: nazwaAgenta(x.agent) })}</span></p>
    <${SzczegolyBledu} tekst=${x.tekst}/></div>`;
}

// jedna pozycja osi (widok z Os.widok): rodzaj → komponent. React.memo: długa rozmowa nie renderuje się cała przy
// każdym zdarzeniu strumienia, tylko pozycje, których dane się zmieniły (Os.widok zachowuje obiekty bez zmian)
const ElementOsi = React.memo(function ElementOsiW({ x, ctx, ostatniaPrzebiegu }) {
  switch (x.rodzaj) {
    case "wlasciciel": return html`<${WiadomoscWlasciciela} x=${x} k=${ctx.k}/>`;
    case "agent": return html`<${WiadomoscAgenta} x=${x} ctx=${ctx} ostatniaPrzebiegu=${ostatniaPrzebiegu}/>`;
    case "zywy": return html`<${ZywyDymek} p=${x.przebieg} ctx=${ctx}/>`;
    case "kroki": return html`<div class="j-msg-kroki"><${Kroki} kroki=${x.kroki || []} szczegoly=${ctx.szczegoly}/></div>`;
    case "obca": return html`<${WiadomoscObca} x=${x}/>`;
    case "blad_tury": return html`<${BladTury} x=${x}/>`;
    default: return html`<${PozycjaSystemowa} x=${x}/>`;
  }
});
