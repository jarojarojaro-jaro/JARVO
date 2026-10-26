// Karty pracy w wątku (docs/HQ.md „Karty pracy”): przekazanie Jarva (pozycja `przekazanie` z `karta.task_id`) to
// żywa karta agenta: awatar, zadanie, etap (czeka → pracuje → ocena → gotowe), co robi teraz, czas, a po rozwinięciu
// przebieg pracy wykonawcy i sędziego (GET /karty/{id}). Koniec karty (budzenie „completed”) to wiadomość
// „<agent> · skończone” z tym, co zrobił, plikami i werdyktem Jarva. Stan z GET /karty?id=… co 4 s, dopóki któraś karta
// w wątku pracuje i karta przeglądarki jest widoczna, oraz od razu po każdej zmianie osi (budzenie z tablicy).

const KARTY_CO_MS = 4000;
const KARTY_KONCOWE = new Set(["gotowe", "porzucona"]);
const ETAPY_PASKA = ["czeka", "pracuje", "ocena", "gotowe"];
const MISJA_W_TYTULE = /^\s*\[[^\]]{1,60}\]\s*/;

// ścieżka w opisie kroku skrócona do dwóch ostatnich członów („…/audyt/out.md”), bez korzenia danych na całą linię;
// adres (https://…) zostaje: ukośnik po „:”, drugim ukośniku albo literze nie zaczyna ścieżki
const SCIEZKA_W_KROKU = /(?<![:\w/\\])(?:[A-Za-z]:)?[\\/](?:[^\s\\/"']+[\\/])+([^\s\\/"']+[\\/][^\s\\/"']+)/g;
const sciezkiKroku = (t) => String(t || "").replace(SCIEZKA_W_KROKU, "…/$1");
const tytulKarty = (t) => String(t || "").replace(MISJA_W_TYTULE, "") || T("karta.bez_tytulu");
// etap na pasku: do_oceny i ocena to „ocena”, poprawki to „praca”, zablokowana i porzucona zostają na swoim miejscu
const krokPaska = (etap) => ({ czeka: 0, pracuje: 1, poprawki: 1, zablokowana: 1, porzucona: 1, do_oceny: 2, ocena: 2, gotowe: 3 }[etap] ?? 0);

// stan kart wątku w sklepie (`karty`: id → karta); odpytywanie tylko widocznych i niezakończonych
function useKartyWatku(watek, ids) {
  const klucz = ids.join(",");
  const karty = useSklep((s) => s.karty, plytko);
  useEffect(() => {
    if (!klucz) return undefined;
    let zywy = true, czas = 0;
    const wczytaj = async () => {
      clearTimeout(czas);
      if (document.visibilityState === "visible") {
        try {
          const odp = await api.karty.stan(klucz.split(","));
          if (zywy && odp && odp.karty) sklep.ustaw((s) => ({ ...s, karty: { ...s.karty, ...odp.karty } }));
        } catch (_) { /* serwer się restartuje: zostaje ostatni stan, następna próba za chwilę */ }
      }
      if (!zywy) return;
      const k = sklep.stan().karty || {};
      if (klucz.split(",").some((id) => !k[id] || !KARTY_KONCOWE.has(k[id].etap))) czas = setTimeout(wczytaj, KARTY_CO_MS);
    };
    wczytaj();
    const haki = [Strumien.naZdarzenie("watek.os", (d) => d.watek_id === watek && wczytaj())];
    const widocznosc = () => { if (document.visibilityState === "visible") wczytaj(); };
    document.addEventListener("visibilitychange", widocznosc);
    return () => { zywy = false; clearTimeout(czas); haki.forEach((f) => f()); document.removeEventListener("visibilitychange", widocznosc); };
  }, [watek, klucz]);
  return karty;
}

// czas pracy na żywo („2:14”) albo całkowity po końcu
function CzasKarty({ k }) {
  const trwa = !!k.od && !KARTY_KONCOWE.has(k.etap) && k.etap !== "czeka";
  const teraz = useTeraz(1000, trwa);
  if (!k.od) return null;
  const koniec = k.koniec || (trwa ? teraz : null);
  return koniec ? html`<span class="j-karta-czas">${Czas.trwanie(Math.max(0, koniec - k.od))}</span>` : null;
}

const opisEtapu = (k) => T(`karta.e_${k.etap}`, { agent: nazwaAgenta(k.agent), sedzia: nazwaAgenta(k.przypisany || "jarvo") });

function PasekEtapow({ etap }) {
  const n = krokPaska(etap), zle = etap === "zablokowana" || etap === "porzucona";
  return html`<ol class="j-karta-pasek" aria-label=${T("karta.etapy")}>
    ${ETAPY_PASKA.map((e, i) => html`<li key=${e} class=${cx(i < n && "is-za", i === n && "is-teraz", i === n && zle && "is-zle")}
      aria-current=${i === n ? "step" : undefined}><span>${T(`karta.p_${e}`)}</span></li>`)}</ol>`;
}

// jedna linia „co teraz”: ostatni krok sesji pracownika (czasownik + szczegół) albo jego ostatnie zdanie / notatka
function TerazKarty({ k }) {
  const t = k.teraz;
  if (k.etap === "zablokowana" || k.etap === "porzucona") {
    return k.powod ? html`<p class="j-karta-teraz is-zle"><${Ikona} n="alert" r=${14}/><span>${k.powod}</span></p>` : null;
  }
  if (KARTY_KONCOWE.has(k.etap) || k.etap === "czeka") return null;
  const tekst = t ? (t.verb ? `${(isPL() ? t.verb : t.verb_en || t.verb)}${t.detail ? ` ${sciezkiKroku(t.detail)}` : ""}` : t.tekst) : k.notatka;
  return tekst ? html`<p class="j-karta-teraz" aria-live="off"><span class="j-karta-puls" aria-hidden="true"></span><span>${tekst}</span></p>` : null;
}

// przebieg pracy po rozwinięciu: kroki i wypowiedzi wykonawcy, potem sędziego (GET /karty/{id}, odświeżany przy pracy)
function PrzebiegKarty({ id, trwa }) {
  const [dane, setDane] = useState(null);
  const [blad, setBlad] = useState(false);
  useEffect(() => {
    let zywy = true, czas = 0;
    const wczytaj = async () => {
      try {
        const odp = await api.karty.wez(id);
        if (zywy) { setDane(odp.karta); setBlad(false); }
      } catch (_) { if (zywy) setBlad(true); }
      if (zywy && trwa) czas = setTimeout(wczytaj, KARTY_CO_MS);
    };
    wczytaj();
    return () => { zywy = false; clearTimeout(czas); };
  }, [id, trwa]);
  if (blad && !dane) return html`<p class="j-karta-pusto">${T("karta.nie_wczytano")}</p>`;
  if (!dane) return html`<p class="j-karta-pusto"><${Spinner}/></p>`;
  const przebiegi = (dane.przebieg || []).filter((p) => p.kroki && p.kroki.length);
  if (!przebiegi.length) return html`<p class="j-karta-pusto">${T("karta.bez_krokow")}</p>`;
  return html`<div class="j-karta-przebieg">${przebiegi.map((p, i) => html`<section key=${i} class="j-karta-run">
    <h4><${Awatar} agent=${{ name: p.profil }} r=${18}/><span>${nazwaAgenta(p.profil)}</span>
      <small>${T(p.rola === "ocena" ? "karta.rola_ocena" : "karta.rola_praca")}${p.od ? ` · ${Czas.godzina(p.od)}` : ""}</small></h4>
    <ol>${p.kroki.map((s, j) => s.kind === "say"
      ? html`<li key=${j} class="j-karta-mowi"><${TrescMd} tekst=${s.text || ""} klasa="j-karta-mowi-t"/></li>`
      : html`<li key=${j} class=${cx("j-karta-krok", s.status === "error" && "is-blad", s.status === "running" && "is-teraz")}>
          <span class="j-karta-krok-z" aria-hidden="true">${s.status === "running" ? html`<${Spinner} r=${10}/>`
            : html`<${Ikona} n=${s.status === "error" ? "x" : "check"} r=${12}/>`}</span>
          <span><b>${isPL() ? s.verb : s.verb_en || s.verb}</b>${s.detail ? ` ${sciezkiKroku(s.detail)}` : ""}</span>
          <time>${Czas.godzina(s.ts)}</time></li>`)}</ol></section>`)}</div>`;
}

function KartaPracy({ x, ctx }) {
  const p = x.karta || {};
  const id = p.task_id;
  const k = useSklep((s) => (id && s.karty[id]) || null);
  const [otwarta, setOtwarta] = useState(false);
  const domId = useIdJarvo();
  const karta = k || { etap: "czeka", agent: p.agent, tytul: p.tytul || x.tekst };
  const a = useAgent(karta.agent);
  const trwa = !KARTY_KONCOWE.has(karta.etap);
  return html`<article class=${cx("j-karta", `is-${karta.etap}`)} data-karta=${id || undefined} data-etap=${karta.etap}
      aria-label=${`${nazwaAgenta(karta.agent)}: ${tytulKarty(karta.tytul)}`}>
    <header class="j-karta-g">
      <${Awatar} agent=${a} r=${36} stan=${karta.etap === "pracuje" || karta.etap === "poprawki" || karta.etap === "ocena" ? "pracuje" : null}/>
      <div class="j-karta-kto">
        <b>${nazwaAgenta(karta.agent)}</b>
        <span class="j-karta-tytul">${tytulKarty(karta.tytul)}</span>
      </div>
      <span class="j-karta-etap"><span>${opisEtapu(karta)}</span><${CzasKarty} k=${karta}/></span>
    </header>
    <${PasekEtapow} etap=${karta.etap}/>
    <${TerazKarty} k=${karta}/>
    ${karta.etap === "gotowe" && (x.koniec_nizej
      ? karta.podsumowanie && html`<p class="j-karta-skrot">${karta.podsumowanie.split(/(?<=[.!?])\s/)[0]}</p>`
      : html`<${WynikPracy} k=${karta}/>`)}
    ${id && html`<button type="button" class="j-karta-wiecej" aria-expanded=${String(otwarta)} aria-controls=${domId}
        onClick=${() => setOtwarta(!otwarta)}>
      <${Ikona} n=${otwarta ? "down" : "right"} r=${14}/><span>${T(otwarta ? "karta.zwin" : "karta.jak_pracuje", { agent: nazwaAgenta(karta.agent) })}</span>
      ${karta.proby > 1 && html`<span class="j-karta-proby">${T("karta.proby", { n: karta.proby })}</span>`}</button>`}
    <div id=${domId} hidden=${!otwarta}>${otwarta && id && html`<${PrzebiegKarty} id=${id} trwa=${trwa}/>`}</div>
  </article>`;
}

// co zrobił: wynik (zwinięty, gdy długi), pliki jako zwarta siatka (najwyżej PLIKI_NAJPIERW, reszta pod „+N”), ocena
const PLIKI_NAJPIERW = 6;
function WynikPracy({ k, tekst }) {
  const [calosc, setCalosc] = useState(false);
  const [wszystkie, setWszystkie] = useState(false);
  const t = tekst != null ? tekst : k.podsumowanie || "";
  const dlugi = t.length > 420;
  const pliki = (k.pliki || []).map(fileFromPath);
  const widoczne = wszystkie ? pliki : pliki.slice(0, PLIKI_NAJPIERW);
  return html`<div class="j-wynik">
    ${t && html`<div class=${cx("j-koniec-wynik", dlugi && !calosc && "is-zwiniety")}><${TrescMd} tekst=${t} klasa="j-msg-t"/></div>`}
    ${dlugi && html`<button type="button" class="j-link" onClick=${() => setCalosc(!calosc)}>${T(calosc ? "karta.mniej" : "karta.calosc")}</button>`}
    ${pliki.length > 0 && html`<div class="j-wynik-pliki">${widoczne.map((p) => html`<${KartaPliku} key=${p.path} plik=${p} kompakt=${true}/>`)}
      ${pliki.length > widoczne.length && html`<button type="button" class="j-wynik-wiecej" onClick=${() => setWszystkie(true)}>
        ${T("karta.pliki_wiecej", { n: pliki.length - widoczne.length })}</button>`}</div>`}
    ${k.ocena && html`<p class="j-koniec-ocena"><${Awatar} agent=${{ name: k.przypisany || "jarvo" }} r=${18}/>
      <span><b>${T("karta.ocena", { sedzia: nazwaAgenta(k.przypisany || "jarvo") })}</b> ${k.ocena}</span></p>`}
  </div>`;
}

// „Web · skończone”: koniec karty z tablicy (budzenie completed) z tym, co zrobił, plikami i werdyktem sędziego
function KoniecPracy({ x, ctx }) {
  const b = x.budzenie || {};
  const k = useSklep((s) => s.karty[b.task_id] || null) || {};
  const agent = k.agent || b.wykonawca;
  const a = useAgent(agent);
  const tekst = k.podsumowanie || b.wynik || "";
  return html`<article class="j-msg j-msg-ag j-koniec" data-koniec=${b.task_id} data-agent=${agent}>
    <h3 class="j-sr">${T("karta.skonczyl", { agent: nazwaAgenta(agent) })}, ${Czas.godzina(x.ts)}</h3>
    <header class="j-msg-g"><${Awatar} agent=${a} r=${28}/><b class="j-msg-n">${nazwaAgenta(agent)}</b>
      <span class="j-koniec-tag"><${Ikona} n="check" r=${12}/>${T("karta.skonczyl_krotko")}</span>
      <time title=${czasPelny(x.ts)}>${Czas.godzina(x.ts)}</time></header>
    <p class="j-koniec-t">${tytulKarty(k.tytul || b.tytul)}${k.od && k.koniec ? html` <span class="j-karta-czas">· ${Czas.trwanie(k.koniec - k.od)}</span>` : null}</p>
    <${WynikPracy} k=${k} tekst=${tekst}/>
    <${AkcjeWiadomosci} tekst=${tekst} agent=${agent} watek=${ctx.watek} koordynator=${ctx.koordynator}/>
  </article>`;
}
