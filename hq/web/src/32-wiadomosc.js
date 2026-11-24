// Wiadomości w osi wątku (docs/HQ.md „Aplikacja”, makieta V2 · Spokojny): dymek właściciela (od razu, zanim serwer
// odpowie; nieudana wysyłka z „Spróbuj ponownie” i „Usuń”), wiadomość agenta (Markdown, karty plików, Kopiuj,
// „Odpowiedz: <agent>”, znacznik „bezpośrednio”), kroki pracy (Prosty: jedna linia do rozwinięcia; Szczegóły: lista
// z podglądem wyników; każdy krok rozwija się osobno: polecenie, myśl i wynik), żywy dymek trwającej pracy (tekst
// z delt, stan, czas, kolejka), prośba o zgodę (dokładnie wybory zdarzenia, odliczanie, „Czas minął” i „Poproś
// ponownie”), błąd z „Ponów” i pozycje systemowe.

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

// `rutyna`: nazwa rutyny przy raporcie (Poranny brief, Patrol floty) zamiast znacznika „bezpośrednio”
function NaglowekAgenta({ agent, ts, bezposrednio, rutyna }) {
  const a = useAgent(agent);
  return html`<header class="j-msg-g"><${Awatar} agent=${a} r=${28}/><b class="j-msg-n">${nazwaAgenta(agent)}</b>
    ${bezposrednio && html`<span class="j-tag">${T("msg.bezposrednio")}</span>`}
    ${rutyna && html`<span class="j-tag is-rutyna" data-rutyna=${rutyna}><span aria-hidden="true">↻ </span>${rutyna}</span>`}
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
// odznaka źródła w rozmowie z rozmówcą (centrum §2.1): „z Telegrama”, „z terminala”, „z panelu” (etykieta mono nad treścią;
// godzina stoi na osi rozmowy)
const ZRODLA = new Set(["telegram", "terminal", "panel"]);
function Zrodlo({ zrodlo }) {
  const z = ZRODLA.has(zrodlo) ? zrodlo : "panel";
  return html`<span class="j-zrodlo" data-zrodlo=${z}>${T(`zrodlo.${z}`)}</span>`;
}

// stan przebiegu wiadomości właściciela (wpis_id → stan): jedna mapa na stan sklepu zamiast przeglądu wszystkich
// przebiegów przez każdy dymek przy każdym zdarzeniu strumienia (pierwszy przebieg wpisu wygrywa, jak wcześniej)
let stanyWpisow = { p: null, m: null };
function stanWpisu(przebiegi, id) {
  if (stanyWpisow.p !== przebiegi) {
    const m = new Map();
    for (const p of Object.values(przebiegi)) if (p.wpis_id && !m.has(p.wpis_id)) m.set(p.wpis_id, p.stan);
    stanyWpisow = { p: przebiegi, m };
  }
  return stanyWpisow.m.get(id) || null;
}

function WiadomoscWlasciciela({ x, k, rozmowca }) {
  const o = x.oczekuje, w = x.wpis || {};
  const adresaci = (o ? o.adresaci : w.adresaci) || [];
  const bezposrednio = !rozmowca && (o ? adresaci.length > 0 : x.tryb === "bezposrednio");
  // zapisany wpis: załączniki z /upload (path, name, size, kind) i obrazy z wiadomości (path); bez powtórek ścieżek
  const pliki = o ? o.pliki || [] : [...new Map((x.pliki || [])
    .concat((w.zalaczniki || []).filter((z) => z && z.path).map((z) => ({ ...fileFromPath(z.path), ...z })))
    .concat((w.obrazy || []).filter((b) => b && b.path).map((b) => ({ ...fileFromPath(b.path), size: b.size })))
    .map((p) => [p.path, p])).values()];
  const obrazy = o ? (o.obrazy || []).filter((b) => OBRAZ_DATA.test(b.dane || "")) : [];
  // dopisana do trwającej tury (Enter w trakcie pracy, „Wyślij teraz do trwającej pracy” albo sama z kolejki):
  // „Dopisuję…”, potem „Dopisana”; wróciła do kolejki albo poszła jako własna tura = pokazuje to jej żywy dymek
  const dop = !!(w.dane && w.dane.dopisane_do);
  const stanDop = useSklep((s) => (o ? null : stanWpisu(s.przebiegi, x.id)));
  return html`<article class="j-msg j-msg-ja" data-wpis=${o ? undefined : x.id} data-zrodlo=${rozmowca ? x.zrodlo || "panel" : undefined}>
    <h3 class="j-sr">${T("os.ty")}, ${Czas.godzina(x.ts)}</h3>${x.ts ? html`<time class="j-msg-ts" aria-hidden="true">${Czas.godzina(x.ts)}</time>` : null}
    ${bezposrednio && adresaci.length > 0 && html`<p class="j-msg-tag"><${Ikona} n="turn" r=${14}/>
      <span>${T("msg.bezposrednio")} · ${adresaci.map(nazwaAgenta).join(", ")}</span></p>`}
    ${x.tekst && html`<div class=${cx("j-babel", o && o.stan === "blad" && "is-blad")} title=${czasPelny(x.ts)}>
      ${rozmowca && html`<${Zrodlo} zrodlo=${x.zrodlo}/>`}${renderujInline(Md.linki(x.tekst))}</div>`}
    ${(obrazy.length > 0 || pliki.length > 0) && html`<div class="j-msg-pliki">
      ${obrazy.map((b, i) => html`<img key=${i} class="j-zal-obraz" src=${b.dane} alt=${b.nazwa || ""}/>`)}
      ${pliki.map((p) => html`<${KartaPliku} key=${p.path} plik=${p} kompakt=${true}/>`)}</div>`}
    ${o && html`<${StanWysylki} o=${o} k=${k}/>`}
    ${(stanDop === "dopisany" || stanDop === "wlaczony" || (dop && !stanDop)) && html`<p class="j-msg-stan is-dop">
      <${Ikona} n="plus" r=${12}/>${T(stanDop === "dopisany" ? "msg.dopisuje" : "msg.dopisana")}</p>`}
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
// „[[czeka-na-tak]]” (centrum §6): rozmówca z potwierdzeniami kończy plan tym znacznikiem. Znacznik nie trafia do
// widoku; pod ostatnią taką odpowiedzią bez odpowiedzi właściciela stoją „Tak, wykonaj” i „Nie” (zwykła wiadomość
// „tak”/„nie”, wykonanie przychodzi w następnej turze), a po odpowiedzi jedna spokojna linia z nią.
const ZNACZNIK_TAK = "[[czeka-na-tak]]";
const bezZnacznika = (t) => (t && t.includes(ZNACZNIK_TAK) ? t.split(ZNACZNIK_TAK).join("").trim() : t);
const czekaNaTak = (x) => !!(x && (x.czeka_na_tak || String(x.tekst || "").includes(ZNACZNIK_TAK)
  || (x.przebieg && String(x.przebieg.tekst || "").includes(ZNACZNIK_TAK))));

function TakNie({ tak, ctx }) {
  const [wysyla, setWysyla] = useState(false);
  if (tak !== "czeka") {
    return html`<p class="j-tak-po" data-tak-po=""><${Ikona} n="check" r=${14}/><span>${T("tak.odpowiedziano", { tekst: tak })}</span></p>`;
  }
  const odpowiedz = async (tekst) => {
    setWysyla(true);
    try { await akcje.wyslij({ watek: ctx.watek, tekst, koordynator: ctx.koordynator }); } finally { setWysyla(false); }
  };
  return html`<div class="j-tak" role="group" aria-label=${T("tak.etykieta")}>
    <p class="j-tak-t">${T("tak.tytul")}</p>
    <div class="j-tak-b">
      <${Przycisk} rodzaj="mocny" ikona="check" disabled=${wysyla} data-tak="tak" onClick=${() => odpowiedz("tak")}>${T("tak.tak")}</${Przycisk}>
      <${Przycisk} disabled=${wysyla} data-tak="nie" onClick=${() => odpowiedz("nie")}>${T("tak.nie")}</${Przycisk}>
    </div></div>`;
}

// lustro do Telegrama nie doszło (lustro.py: 3 próby): znacznik pod odpowiedzią
function LustroNie({ pid }) {
  const nie = useSklep((s) => !!(s.przebiegi[pid] && s.przebiegi[pid].lustro_nie));
  return nie ? html`<p class="j-msg-meta is-lustro" role="note"><span aria-hidden="true">📱</span><span>${T("lustro.nie_doszlo")}</span></p>` : null;
}

function WiadomoscAgenta({ x, ctx, ostatniaPrzebiegu, tak }) {
  const pomin = useMemo(() => new Set((x.pliki || []).map((p) => p.path)), [x.pliki]);
  const bezposrednio = x.tryb === "bezposrednio" && x.agent !== ctx.koordynator && !ctx.rozmowca;
  const tekst = bezZnacznika(x.tekst);
  const rutyna = x.rodzaj === "rutyna" ? (x.rutyna && x.rutyna.nazwa) || T("rap.rutyna") : null;
  return html`<article class=${cx("j-msg", "j-msg-ag", rutyna && "is-rutyna")} data-pozycja=${x.id} data-agent=${x.agent}>
    <h3 class="j-sr">${nazwaAgenta(x.agent)}${rutyna ? ` · ${rutyna}` : ""}, ${Czas.godzina(x.ts)}</h3>
    <${NaglowekAgenta} agent=${x.agent} ts=${x.ts} bezposrednio=${bezposrednio} rutyna=${rutyna}/>
    ${x.kroki && x.kroki.length > 0 && html`<${Kroki} kroki=${x.kroki} szczegoly=${ctx.szczegoly} watek=${ctx.watek}/>`}
    <${TrescMd} tekst=${tekst} pomin=${pomin} klasa="j-msg-t"/>
    ${x.pliki && x.pliki.length > 0 && html`<div class="j-pliki">${x.pliki.map((p) => html`<${KartaPliku} key=${p.path} plik=${p}/>`)}</div>`}
    ${x.przebieg_id && ctx.watek && (x.kroki || []).some((k) => k.narzedzie === "delegate_task") && html`<${Leniwy} pakiet="podglad"
      nazwa="PodagenciLinia" watek=${ctx.watek} pidy=${x.przebiegi || [x.przebieg_id]} agent=${x.agent}/>`}
    ${tak && html`<${TakNie} tak=${tak} ctx=${ctx}/>`}
    ${ostatniaPrzebiegu && x.przebieg_id && html`<${ZgodaPoKoncu} pid=${x.przebieg_id} ctx=${ctx}/>`}
    ${ostatniaPrzebiegu && x.przebieg_id && ctx.rozmowca && html`<${LustroNie} pid=${x.przebieg_id}/>`}
    ${x.zatrzymany && html`<${MetaPrzebiegu} p=${x.zatrzymany}/>`}
    <${AkcjeWiadomosci} tekst=${tekst} agent=${ctx.rozmowca ? null : x.agent} watek=${ctx.watek} koordynator=${ctx.koordynator}/>
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

// Rozwinięty krok (jak w terminalu): myśl tuż przed wywołaniem, argumenty (polecenie, plik, wzorzec…), diff edycji
// i wynik przycięty z „Pokaż więcej” (sufit serwera). Dane z GET /rozmowy/{id}/krok dopiero po kliknięciu (oś ich nie
// niesie); krok z wynikiem zostaje w pamięci karty, krok w toku pyta serwer przy każdym rozwinięciu.
const krokiPamiec = new Map();
const KROKI_PAMIEC_MAKS = 100;
const ARGUMENTY_KROKU = { command: "polecenie", cmd: "polecenie", path: "plik", file_path: "plik", paths: "pliki",
  pattern: "wzorzec", query: "zapytanie", url: "adres", content: "tresc", code: "kod", edits: "zmiany", input: "wejscie",
  title: "tytul", language: "jezyk" };
const etykietaArgumentu = (k) => (ARGUMENTY_KROKU[k] ? T(`krok.a_${ARGUMENTY_KROKU[k]}`) : k);

function KrokSzczegoly({ id, watek, krokRef }) {
  const [wiecej, setWiecej] = useState(false);
  const klucz = `${watek}|${krokRef}|${wiecej ? 1 : 0}`;
  const [k, setK] = useState(() => krokiPamiec.get(klucz) || null);
  const [blad, setBlad] = useState(false);
  useEffect(() => {
    const jest = krokiPamiec.get(klucz);
    if (jest) { setK(jest); return undefined; }
    let zywy = true;
    setBlad(false);
    api.rozmowy.krok(watek, krokRef, wiecej ? { wiecej: 1 } : null).then((d) => {
      if (!zywy) return;
      const krok = (d && d.krok) || null;
      if (krok && krok.gotowy) {
        if (krokiPamiec.size >= KROKI_PAMIEC_MAKS) krokiPamiec.delete(krokiPamiec.keys().next().value);
        krokiPamiec.set(klucz, krok);
      }
      setK(krok);
    }).catch(() => { if (zywy) setBlad(true); });
    return () => { zywy = false; };
  }, [klucz]);
  const meta = k && [k.gotowy && k.linie > 1 && T("krok.linie", { n: k.linie }), k.kod != null && T("krok.kod", { n: k.kod }),
    k.czas_ms > 0 && Czas.trwanie(k.czas_ms / 1000)].filter(Boolean);
  return html`<div class="j-krok-sz" id=${id}>
    ${blad && html`<p class="j-krok-sz-n">${T("krok.nie_wczytano")}</p>`}
    ${!k && !blad && html`<p class="j-krok-sz-n"><${Spinner}/> ${T("krok.wczytuje")}</p>`}
    ${k && html`
      ${k.mysl && html`<p class="j-krok-sz-h">${T("krok.mysl")}</p><p class="j-krok-sz-mysl">${k.mysl}</p>`}
      ${(k.argumenty || []).map((a, i) => html`<p key=${`h${i}`} class="j-krok-sz-h">${etykietaArgumentu(a.klucz)}</p>
        <pre key=${`a${i}`} class="j-kroki-podglad">${a.wartosc}</pre>`)}
      ${k.zmiana && html`<p class="j-krok-sz-h">${T("krok.zmiana")}</p><pre class="j-kroki-podglad">${k.zmiana}</pre>`}
      <p class="j-krok-sz-h">${T("krok.wynik")}${meta.length ? html` <span class="j-kroki-czas">· ${meta.join(" · ")}</span>` : null}
        ${k.blad && html` <span class="j-kroki-blad">· ${T("kroki.blad")}</span>`}</p>
      ${k.poufny ? html`<p class="j-krok-sz-n">${T("krok.poufny")}</p>`
        : !k.gotowy ? html`<p class="j-krok-sz-n">${T("krok.w_toku")}</p>`
          : html`<pre class="j-kroki-podglad">${k.wynik || T("krok.pusty")}</pre>`}
      ${k.przyciete && !k.wiecej && html`<button type="button" class="j-link" onClick=${() => setWiecej(true)}>${T("krok.wiecej")}</button>`}
      ${k.przyciete && k.wiecej && html`<p class="j-krok-sz-n">${T("krok.sufit")}</p>`}`}
  </div>`;
}

// Krok z adresem (`ref`) w wątku rozwija się sam (każdy osobno), reszta zostaje zwykłą linią. Na żywo (`zywe`) jak
// w terminalu: myśli między krokami i wyjście kroku, który właśnie trwa (23.11 właściciel: „nie widać, co agent robi”).
function KrokiLista({ kroki, szczegoly, watek, zywe }) {
  const [wszystkie, setWszystkie] = useState(false);
  const [rozwiniete, setRozwiniete] = useState(() => new Set());
  const id = useIdJarvo();
  const przelacz = (ref) => setRozwiniete((s) => {
    const n = new Set(s);
    if (n.has(ref)) n.delete(ref); else n.add(ref);
    return n;
  });
  const widoczne = wszystkie ? kroki : kroki.slice(-KROKI_NAJPIERW);
  let trwa = -1;
  if (zywe) for (let i = widoczne.length - 1; i >= 0; i--) if (widoczne[i].komentarz == null) { if (widoczne[i].czas_ms == null) trwa = i; break; }
  // podgląd na żywo: przycisk przy ostatnim kroku na telefonie albo w Komputerze, dopóki praca trwa
  let urzI = -1, urz = null;
  if (zywe) for (let i = widoczne.length - 1; i >= 0 && !urz; i--) if ((urz = NaZywo.urzadzenie(widoczne[i]))) urzI = i;
  return html`<div class="j-kroki-l">
    ${widoczne.length < kroki.length && html`<button type="button" class="j-link" onClick=${() => setWszystkie(true)}>
      ${T("kroki.wczesniejsze", { n: kroki.length - widoczne.length })}</button>`}
    <ol>${widoczne.map((k, i) => {
      if (k.komentarz != null) {
        return html`<li key=${i} class=${cx("is-komentarz", k.mysl && "is-mysl")}><time>${Czas.godzina(k.ts)}</time><div class="j-kroki-kom"><${TrescMd} tekst=${bezZnacznika(k.komentarz)}/></div></li>`;
      }
      const moze = !!(watek && k.ref);
      const otwarty = moze && rozwiniete.has(k.ref);
      const opis = html`<b>${czasownik(k)}</b>${k.detail ? ` ${k.detail}` : ""}${k.blad ? html` <span class="j-kroki-blad">· ${T("kroki.blad")}</span>` : null}
        ${szczegoly && k.czas_ms > 0 && html` <span class="j-kroki-czas">${Czas.trwanie(k.czas_ms / 1000)}</span>`}`;
      return html`<li key=${i} class=${cx(k.blad && "is-blad", i === trwa && "is-trwa")}>
      <time>${Czas.godzina(k.ts)}</time>
      ${moze ? html`<button type="button" class="j-kroki-o j-kroki-k" aria-expanded=${String(otwarty)} aria-controls=${`${id}-${i}`}
          onClick=${() => przelacz(k.ref)}><span>${opis}</span><${Ikona} n="right" r=${12}/></button>`
        : html`<span class="j-kroki-o">${opis}</span>`}
      ${i === urzI && html`<${PrzyciskNaZywo} urz=${urz}/>`}
      ${(szczegoly || i === trwa) && k.podglad && !otwarty && html`<${PodgladKroku} tekst=${k.podglad}/>`}
      ${otwarty && html`<${KrokSzczegoly} id=${`${id}-${i}`} watek=${watek} krokRef=${k.ref}/>`}</li>`;
    })}</ol></div>`;
}

// wyjście kroku przewinięte na koniec (jak terminal: widać ostatnie linie)
function PodgladKroku({ tekst }) {
  const ref = useRef(null);
  useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight; }, [tekst]);
  return html`<pre ref=${ref} class="j-kroki-podglad">${tekst}</pre>`;
}

// Prosty: zwinięta linia „12 kroków · 2:05” (przy trwającej pracy też ostatni krok), bez licznika błędów narzędzi
// (zwykle odzyskane potknięcia, a czerwone „2 błędy” pod odpowiedzią wyglądało jak awaria; błąd widać na liście kroków);
// Szczegóły: rozwinięte, z licznikiem błędów. Każdy krok z adresem rozwija się dalej sam (KrokSzczegoly).
function Kroki({ kroki, szczegoly, zywe, watek }) {
  const [otwarte, setOtwarte] = useState(!!(szczegoly || zywe));
  useEffect(() => setOtwarte(!!(szczegoly || zywe)), [szczegoly, zywe]);
  const id = useIdJarvo();
  const s = Os.krokiPodsumowanie(kroki);
  if (!s.n) return null;
  return html`<div class=${cx("j-kroki", zywe && "is-zywe")}>
    <button type="button" class="j-kroki-b" aria-expanded=${String(otwarte)} aria-controls=${id} onClick=${() => setOtwarte(!otwarte)}>
      <${Ikona} n="right" r=${14}/><span>${T("os.kroki", { n: s.n })}${s.sekundy ? ` · ${Czas.trwanie(s.sekundy)}` : ""}</span>
      ${szczegoly && s.bledy > 0 && html`<span class="j-kroki-blad">· ${T("kroki.bledy", { n: s.bledy })}</span>`}
      ${zywe && s.ostatni && html`<span class="j-kroki-teraz">· ${czasownik(s.ostatni)}</span>`}
    </button>
    <div id=${id} hidden=${!otwarte}>${otwarte && html`<${KrokiLista} kroki=${kroki} szczegoly=${szczegoly} watek=${watek} zywe=${zywe}/>`}</div>
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
      ${kl.sekcja && html`<${Przycisk} maly onClick=${() => Trasa.idz({ widok: "ustawienia", sekcja: kl.sekcja, pod: kl.pod })}>
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
    ${kolejka && (p.zrodlo || "wlasciciel") === "wlasciciel" && p.powod !== "misja" && html`<button type="button" class="j-link"
      onClick=${() => akcje.doPracy(p.id)}>${T("kolejka.do_pracy")}</button>`}
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
    ${p.kroki && p.kroki.length > 0 && html`<${Kroki} kroki=${p.kroki} szczegoly=${ctx.szczegoly} zywe=${trwa} watek=${ctx.watek}/>`}
    ${p.tekst ? html`<${TrescMd} tekst=${bezZnacznika(p.tekst)} zywy=${trwa} klasa="j-msg-t"/>`
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
  else if (x.rodzaj === "kompresja") {
    const t = x.tokeny || {}, k = (n) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : `${Math.round(n / 1e3)}k`);
    tekst = t.przed && t.po ? T("os.kompresjaTokeny", { przed: k(t.przed), po: k(t.po) }) : T("os.kompresja");
    ikona = "repeat";
  }
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
    <div class="j-babel is-obca">${renderujInline(Md.linki(x.tekst))}</div></article>`;
}

function BladTury({ x }) {
  return html`<div class="j-msg j-blad-tury" role="note"><p class="j-blad-t"><${Ikona} n="alert" r=${14}/>
    <span>${T("os.blad_tury", { agent: nazwaAgenta(x.agent) })}</span></p>
    <${SzczegolyBledu} tekst=${x.tekst}/></div>`;
}

// jedna pozycja osi (widok z Os.widok): rodzaj → komponent. React.memo: długa rozmowa nie renderuje się cała przy
// każdym zdarzeniu strumienia, tylko pozycje, których dane się zmieniły (Os.widok zachowuje obiekty bez zmian)
const ElementOsi = React.memo(function ElementOsiW({ x, ctx, ostatniaPrzebiegu, tak }) {
  switch (x.rodzaj) {
    case "wlasciciel": return html`<${WiadomoscWlasciciela} x=${x} k=${ctx.k} rozmowca=${ctx.rozmowca}/>`;
    case "agent": return html`<${WiadomoscAgenta} x=${x} ctx=${ctx} ostatniaPrzebiegu=${ostatniaPrzebiegu} tak=${tak}/>`;
    case "rutyna": return html`<${WiadomoscAgenta} x=${x} ctx=${ctx}/>`;
    case "zywy": return html`<${ZywyDymek} p=${x.przebieg} ctx=${ctx}/>`;
    case "kroki": return html`<div class="j-msg-kroki"><${Kroki} kroki=${x.kroki || []} szczegoly=${ctx.szczegoly} watek=${ctx.watek}/></div>`;
    case "obca": return html`<${WiadomoscObca} x=${x}/>`;
    case "blad_tury": return html`<${BladTury} x=${x}/>`;
    case "przekazanie": return x.karta && x.karta.task_id ? html`<${KartaPracy} x=${x} ctx=${ctx}/>` : html`<${PozycjaSystemowa} x=${x}/>`;
    case "koniec": return html`<${KoniecPracy} x=${x} ctx=${ctx}/>`;
    case "system": return Komendy.zWpisu(x) ? html`<${WynikKomendy} x=${x} watek=${ctx.watek}/>` : html`<${PozycjaSystemowa} x=${x}/>`;
    default: return html`<${PozycjaSystemowa} x=${x}/>`;
  }
});
