// Stopka bloczka wpisywania (pakiet „stopka”, ładowany przy pierwszej otwartej rozmowie; docs/HQ.md „Kompozytor”): dolny rząd
// białego bloczka jak w czatach z agentami. Lewo, obok „Do:”: pigułki model (skrót nazwy), wysiłek myślenia (mała
// skala i poziom) i ⚡ tryb szybki (wyciszony, gdy wyłączony). Prawo, przy spinaczu: pierścień kontekstu z procentem okna
// (kolor uwagi od 80%). Klik w pigułkę otwiera wysuwkę nad nią (23.11 właściciel: „modele podzielone na subskrypcje,
// effort jakieś fajne grafiki, to ma być zajebiste”):
// - model: szukajka i dostawcy jako subskrypcje albo klucze API (zwijane, bieżący rozwinięty), w nich rodziny
//   (Opus, Sonnet, DeepSeek…) od najnowszych, przy modelu okno kontekstu i znak myślenia;
// - wysiłek: skala słupków od „off” do „max” z opisem poziomu pod kursorem, strzałki ← → i Enter;
// - kontekst: duży pierścień, tokeny, koszt, ostatnia kompresja i „Skompresuj teraz” z polem „na czym się skupić”.
// Wybór idzie komendą (/model, /effort, /fast, /compact), więc zostaje w rozmowie jak w terminalu. Dane:
// GET /rozmowy/{id}/licznik od razu po każdej zmianie pliku sesji (zdarzenie `watek.os`: krok, kompresja, zmiana modelu
// albo myślenia w terminalu), co 2 s w trakcie pracy panelu, inaczej co 30 s; w ukrytej karcie przeglądarki nie pyta.

const krotko = (n) => (n >= 1e6 ? `${(n / 1e6).toFixed(1).replace(/\.0$/, "")}M` : n >= 1e3 ? `${(n / 1e3).toFixed(n >= 1e4 ? 0 : 1)}k` : String(n || 0));
// „anthropic/claude-opus-5-5” → „opus-5-5” (dostawca i rodzina w wysuwce i w dymku)
const krotkiModel = (m) => String(m || "?").split("/").pop().replace(/^claude-/, "");
const dolary = (x) => `$${Number(x || 0).toFixed(2)}`;
const godzina = (s) => new Date(s * 1000).toLocaleTimeString(isPL() ? "pl-PL" : "en-GB", { hour: "2-digit", minute: "2-digit" });

const OPIS_WYSILKU = {
  off: ["Bez myślenia", "Najszybciej. Proste pytania i krótkie polecenia.", "No thinking", "Fastest. Simple questions and short commands."],
  minimal: ["Ślad myślenia", "Prawie od razu, z krótkim namysłem.", "A trace of thinking", "Almost instant, with a brief pause."],
  low: ["Krótko", "Szybko i tanio. Codzienna robota.", "Brief", "Quick and cheap. Everyday work."],
  medium: ["Rozsądnie", "Środek między szybkością a dokładnością.", "Balanced", "Between speed and care."],
  high: ["Dokładnie", "Wolniej, ale pewniej przy trudnych rzeczach.", "Thorough", "Slower, surer on hard problems."],
  xhigh: ["Głęboko", "Długie zadania, duży kod, wiele kroków.", "Deep", "Long tasks, big code, many steps."],
  max: ["Pełna moc", "Najwolniej i najdokładniej. Gdy liczy się każdy szczegół.", "Full power", "Slowest and most careful. When every detail matters."],
};
const opisWysilku = (p) => { const o = OPIS_WYSILKU[p] || [p, "", p, ""]; return isPL() ? [o[0], o[1]] : [o[2], o[3]]; };

function Pierscien({ p, r = 7, w = 16, grubosc = 2 }) {
  const o = 2 * Math.PI * r, c = r + grubosc;
  return html`<svg class="j-pier" viewBox=${`0 0 ${2 * c} ${2 * c}`} width=${w} height=${w} aria-hidden="true">
    <circle cx=${c} cy=${c} r=${r} class="j-pier-t" stroke-width=${grubosc}/>
    <circle cx=${c} cy=${c} r=${r} class="j-pier-w" stroke-width=${grubosc} transform=${`rotate(-90 ${c} ${c})`}
      stroke-dasharray=${`${(o * Math.min(100, Math.max(0, p || 0))) / 100} ${o}`}/></svg>`;
}

// mała skala w pigułce wysiłku: 5 słupków, pełnych tyle, ile poziom (off 0, max 5; domyślne = puste)
function Slupki({ poziom }) {
  const n = ["off", "minimal", "low", "medium", "high", "xhigh", "max"].indexOf(poziom);
  const pelne = n < 0 ? 0 : Math.round((n * 5) / 6);
  return html`<svg class="j-slupki" viewBox="0 0 17 12" width="17" height="12" aria-hidden="true">
    ${[0, 1, 2, 3, 4].map((i) => html`<rect key=${i} x=${i * 3.5} y=${10 - i * 2.4} width="2.2" height=${2 + i * 2.4}
      class=${i < pelne ? "is-pelny" : ""}/>`)}</svg>`;
}

// wysuwka nad pigułką: Esc i klik obok zamykają, fokus wraca do pigułki
function Wysuwka({ kotwica, onZamknij, etykieta, klasa, children }) {
  const ref = useRef(null);
  useWarstwa(true, onZamknij, ref, { pulapka: false });
  const [miejsce, setMiejsce] = useState({ visibility: "hidden" });
  React.useLayoutEffect(() => {
    const el = ref.current, r = kotwica.getBoundingClientRect();
    const w = el.offsetWidth, h = el.offsetHeight;
    const left = Math.max(8, Math.min(r.left, window.innerWidth - w - 8));
    const top = r.top - 8 - h >= 8 ? r.top - 8 - h : Math.min(r.bottom + 8, window.innerHeight - h - 8);
    setMiejsce({ left, top });
  }, []);
  useEffect(() => {
    const obok = (e) => { if (ref.current && !ref.current.contains(e.target) && !kotwica.contains(e.target)) onZamknij(); };
    const t = setTimeout(() => document.addEventListener("pointerdown", obok), 0);
    return () => { clearTimeout(t); document.removeEventListener("pointerdown", obok); };
  }, []);
  return html`<div class=${cx("j-wys", klasa)} role="dialog" aria-label=${etykieta} ref=${ref} tabIndex="-1" style=${miejsce}>${children}</div>`;
}

// strzałki ↑ ↓ między przyciskami listy (i z pola szukania do pierwszego)
function strzalki(e, kontener, selektor) {
  if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
  const p = [...kontener.querySelectorAll(selektor)];
  if (!p.length) return;
  e.preventDefault();
  const i = p.indexOf(document.activeElement);
  (e.key === "ArrowDown" ? p[Math.min(p.length - 1, i + 1)] : i <= 0 ? kontener.querySelector("input") || p[0] : p[i - 1]).focus();
}

const KOLEJNOSC_RODZIN = ["Opus", "Sonnet", "Fable", "Mythos", "Haiku"];
// rodzina z nazwy modelu: „Claude Opus 5.5” → Opus, „DeepSeek V4 Flash” → DeepSeek, „GPT-5.4” → GPT
const rodzina = (n) => { const s = String(n || "").split(/\s+/); return (s[0] === "Claude" && s[1] ? s[1] : s[0].split(/[-/]/)[0]) || "?"; };
const bezRodziny = (n) => String(n || "").replace(/^Claude\s+/, "");

function ModelWybor({ o, onWybierz }) {
  const [q, setQ] = useState("");
  const biezacy = o.modele.find((m) => m.biezacy);
  const [otwarte, setOtwarte] = useState(() => new Set(biezacy ? [biezacy.grupa] : []));
  const ref = useRef(null);
  const fraza = q.trim().toLowerCase();
  const grupy = [...o.grupy].sort((a, b) => (biezacy && b.slug === biezacy.grupa) - (biezacy && a.slug === biezacy.grupa)
    || (a.rodzaj === "klucz") - (b.rodzaj === "klucz"));
  const sekcje = grupy.map((g) => {
    const lista = o.modele.filter((m) => m.grupa === g.slug && (!fraza || `${m.nazwa} ${m.model}`.toLowerCase().includes(fraza)));
    const rodziny = new Map();
    for (const m of lista) { const r = rodzina(m.nazwa); if (!rodziny.has(r)) rodziny.set(r, []); rodziny.get(r).push(m); }
    const pozycja = (r) => { const i = KOLEJNOSC_RODZIN.indexOf(r); return i < 0 ? 99 : i; };
    const posortowane = [...rodziny.entries()].sort((a, b) => pozycja(a[0]) - pozycja(b[0]) || a[0].localeCompare(b[0]))
      .map(([r, ms]) => [r, ms.sort((a, b) => b.nazwa.localeCompare(a.nazwa, undefined, { numeric: true }))]);
    return { g, lista, rodziny: posortowane };
  }).filter((s) => s.lista.length);
  const przelacz = (slug) => setOtwarte((s) => { const n = new Set(s); n.has(slug) ? n.delete(slug) : n.add(slug); return n; });
  return html`<div class="j-wm" ref=${ref} onKeyDown=${(e) => strzalki(e, ref.current, ".j-wm-m, .j-wm-g")}>
    <div class="j-wys-g"><span class="j-wys-t">${L("Model", "Model")}</span>
      ${biezacy && html`<span class="j-wys-teraz">${bezRodziny(biezacy.nazwa)}</span>`}</div>
    <label class="j-wm-szukaj"><${Ikona} n="search" r=${14}/>
      <input type="search" data-fokus value=${q} placeholder=${L("Szukaj modelu…", "Search models…")}
        aria-label=${L("Szukaj modelu", "Search models")} onInput=${(e) => setQ(e.currentTarget.value)}
        onKeyDown=${(e) => { if (e.key === "Enter") { const m = sekcje[0] && sekcje[0].lista[0]; if (m) onWybierz(m); } }}/></label>
    <div class="j-wm-lista">
      ${sekcje.map(({ g, lista, rodziny }) => {
        const rozw = !!fraza || otwarte.has(g.slug) || sekcje.length === 1;
        return html`<section key=${g.slug} class=${cx("j-wm-sek", rozw && "is-rozw")}>
          <button type="button" class="j-wm-g" aria-expanded=${String(rozw)} onClick=${() => przelacz(g.slug)}>
            <${Ikona} n="right" r=${12}/><span class="j-wm-gn">${g.nazwa}</span>
            <span class=${cx("j-wm-rodzaj", g.rodzaj === "klucz" && "is-klucz")}>${g.rodzaj === "klucz"
              ? L("klucz API · za tokeny", "API key · per token") : L("subskrypcja", "subscription")}</span>
            <span class="j-rozpych"></span><span class="j-wm-ile">${lista.length}</span></button>
          ${rozw && rodziny.map(([r, ms]) => html`<div key=${r} class="j-wm-rod">
            <div class="j-wm-rn">${r}</div>
            ${ms.map((m) => html`<button key=${m.model} type="button" class=${cx("j-wm-m", m.biezacy && "is-biez")}
              aria-current=${m.biezacy ? "true" : undefined} title=${m.model} onClick=${() => onWybierz(m)}>
              <span class="j-wm-mn">${bezRodziny(m.nazwa)}</span><span class="j-rozpych"></span>
              ${m.okno > 0 && html`<span class="j-wm-okno">${krotko(m.okno)}</span>`}
              <span class="j-wm-ok">${m.biezacy ? html`<${Ikona} n="check" r=${14}/>` : null}</span></button>`)}
          </div>`)}
        </section>`;
      })}
      ${!sekcje.length && html`<p class="j-wm-pusto">${L("Nie ma takiego modelu.", "No such model.")}</p>`}
    </div></div>`;
}

function WysilekWybor({ poziomy, biezacy, onWybierz }) {
  const [pod, setPod] = useState(null);
  const ref = useRef(null);
  const i0 = poziomy.indexOf(biezacy);
  const pokaz = pod != null ? poziomy[pod] : biezacy || null;
  const [tytul, opis] = pokaz ? opisWysilku(pokaz) : [L("Jak ustawienie agenta", "Agent default"), L("Poziom z konfiguracji agenta albo sesji.", "The level from the agent or session settings.")];
  useEffect(() => { const b = ref.current && ref.current.querySelectorAll(".j-ww-s")[Math.max(0, i0)]; if (b) b.focus({ preventScroll: true }); }, []);
  const klawisz = (e, i) => {
    const d = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1 }[e.key];
    if (!d) return;
    e.preventDefault();
    const n = Math.max(0, Math.min(poziomy.length - 1, i + d));
    ref.current.querySelectorAll(".j-ww-s")[n].focus();
    setPod(n);
  };
  return html`<div class="j-ww" ref=${ref}>
    <div class="j-wys-g"><span class="j-wys-t">${L("Wysiłek myślenia", "Thinking effort")}</span>
      <span class="j-wys-teraz">${biezacy || L("domyślne", "default")}</span></div>
    <div class="j-ww-skala" role="radiogroup" aria-label=${L("Wysiłek myślenia", "Thinking effort")} onPointerLeave=${() => setPod(null)}>
      ${poziomy.map((p, i) => {
        const h = 14 + (i / Math.max(1, poziomy.length - 1)) * 58;
        const zaznacz = pod != null ? i <= pod : i0 >= 0 && i <= i0;
        return html`<button key=${p} type="button" role="radio" aria-checked=${String(p === biezacy)} class=${cx("j-ww-s", zaznacz && "is-pelny", p === biezacy && "is-biez", pod != null && "is-podglad")}
          onPointerEnter=${() => setPod(i)} onFocus=${() => setPod(i)} onKeyDown=${(e) => klawisz(e, i)} onClick=${() => onWybierz(p)}>
          <span class="j-ww-sl" style=${{ height: `${h}px` }}></span><span class="j-ww-p">${p}</span></button>`;
      })}
    </div>
    <div class="j-ww-opis" aria-live="polite"><strong>${tytul}</strong><span>${opis}</span></div>
    <button type="button" class=${cx("j-ww-dom", !biezacy && "is-biez")} onClick=${() => onWybierz("domyslny")}>
      ${!biezacy && html`<${Ikona} n="check" r=${14}/>`}<span>${L("Jak ustawienie agenta", "Agent default")}</span></button>
  </div>`;
}

function KontekstWybor({ d, onKomenda }) {
  const [skup, setSkup] = useState("");
  const zaj = d.okno ? Math.round(d.procent) : null;
  const k = d.kompresja;
  return html`<div class="j-wk">
    <div class="j-wys-g"><span class="j-wys-t">${L("Kontekst", "Context")}</span>
      <span class="j-wys-teraz">${krotkiModel(d.model)}</span></div>
    <div class="j-wk-gora">
      <div class=${cx("j-wk-pier", zaj >= 80 && "is-duzo")}><${Pierscien} p=${d.procent} r=${30} w=${76} grubosc=${5}/>
        <span class="j-wk-proc">${zaj != null ? `${zaj}%` : "?"}</span></div>
      <div class="j-wk-liczby">
        <div class="j-wk-duza">${d.szacunek ? "≈" : ""}${krotko(d.kontekst)}<small>${d.okno ? ` / ${krotko(d.okno)}` : ""}</small></div>
        <div class="j-wk-pod">${L("tokenów w oknie modelu", "tokens in the model window")}</div>
        ${k && k.po > 0 && html`<div class="j-wk-komp"><${Ikona} n="repeat" r=${12}/>
          ${L(`kompresja ${godzina(k.czas)}: ${krotko(k.przed)} → ${krotko(k.po)}`, `compacted ${godzina(k.czas)}: ${krotko(k.przed)} → ${krotko(k.po)}`)}</div>`}
      </div>
    </div>
    <dl class="j-wk-tab">
      <dt>${L("Wejście", "Input")}</dt><dd>${krotko(d.wejscie)}</dd>
      <dt>${L("Wyjście", "Output")}</dt><dd>${krotko(d.wyjscie)}</dd>
      ${(d.cache_odczyt || d.cache_zapis) ? html`<dt>Cache</dt><dd>${krotko(d.cache_odczyt)} / ${krotko(d.cache_zapis)}</dd>` : null}
      ${d.koszt > 0 && html`<dt>${L("Koszt", "Cost")}</dt><dd>${d.koszt_dzis > 0 ? L(`dziś ${dolary(d.koszt_dzis)} · sesja ${dolary(d.koszt)}`, `today ${dolary(d.koszt_dzis)} · session ${dolary(d.koszt)}`) : dolary(d.koszt)}</dd>`}
    </dl>
    ${d.koszt > 0 && html`<p class="j-wk-uw">${L("Ceny API jako równoważnik; przy subskrypcji to nie jest rachunek.", "API prices as an equivalent; not a bill on a subscription.")}</p>`}
    ${d.zaplecze === "omp" ? html`<form class="j-wk-komp-f" onSubmit=${(e) => { e.preventDefault(); onKomenda(`/compact${skup.trim() ? ` ${skup.trim()}` : ""}`); }}>
        <input type="text" data-fokus value=${skup} onInput=${(e) => setSkup(e.currentTarget.value)}
          placeholder=${L("Na czym się skupić (opcjonalnie)", "What to focus on (optional)")} aria-label=${L("Na czym się skupić", "What to focus on")}/>
        <button type="submit" class="j-wk-btn"><${Ikona} n="repeat" r=${14}/><span>${L("Skompresuj teraz", "Compact now")}</span></button></form>`
      : html`<button type="button" class="j-wk-btn is-cichy" onClick=${() => onKomenda("/context")}>${L("Szczegóły (/context)", "Details (/context)")}</button>`}
  </div>`;
}

function Stopka({ watek }) {
  const praca = useSklep((s) => Os.doZatrzymania(Object.values(s.przebiegi).filter((p) => p.watek_id === watek)).length > 0);
  const [d, setD] = useState(null);
  const [nr, setNr] = useState(0);
  const [menu, setMenu] = useState(null);           // {co: model|wysilek|kontekst, kotwica, o}
  useEffect(() => {
    let zywy = true, t = 0, w = 0, ostatnio = 0;
    const tik = async () => {
      clearTimeout(t);
      if (!document.hidden) {
        ostatnio = Date.now();
        // ta sama odpowiedź nie rysuje stopki na nowo
        try { const r = await api.rozmowy.licznik(watek); if (zywy) setD((s) => (JSON.stringify(s) === JSON.stringify(r.licznik) ? s : r.licznik)); } catch (_) { /* bez stopki */ }
      }
      if (zywy) t = setTimeout(tik, praca ? 2000 : 30000);
    };
    // plik sesji się zmienił (terminal: krok, /compact, model, myślenie): licznik od razu, najwyżej raz na sekundę
    const zmiana = (x) => {
      if (x.watek_id !== watek || w) return;
      w = setTimeout(() => { w = 0; tik(); }, Math.max(150, 1000 - (Date.now() - ostatnio)));
    };
    const haki = [Strumien.naZdarzenie("watek.os", zmiana), Strumien.naZdarzenie("przebieg.koniec", zmiana)];
    const widok = () => { if (!document.hidden) tik(); };
    document.addEventListener("visibilitychange", widok);
    tik();
    return () => { zywy = false; clearTimeout(t); clearTimeout(w); haki.forEach((f) => f()); document.removeEventListener("visibilitychange", widok); };
  }, [watek, praca, nr]);
  if (!d || !(d.model || d.kontekst || d.wejscie)) return html`<span class="j-rozpych"></span>`;
  const kom = async (t) => {
    setMenu(null);
    try { await Komendy.wykonaj({ watek, tekst: t }); } catch (e) { akcje._blad(e); }
    setNr((n) => n + 1);
  };
  const otworz = async (co, e) => {
    const kotwica = e.currentTarget;
    if (menu && menu.kotwica === kotwica) { setMenu(null); return; }
    if (co === "fast") { kom(`/fast ${d.fast ? "off" : "on"}`); return; }
    if (co === "kontekst") { setMenu({ co, kotwica }); return; }
    try { setMenu({ co, kotwica, o: (await api.rozmowy.opcje(watek)).opcje }); } catch (er) { akcje._blad(er); }
  };
  const zaj = d.okno ? Math.round(d.procent) : null;
  const dymek = `${L("Kontekst", "Context")}: ${d.szacunek ? "≈" : ""}${krotko(d.kontekst)}${d.okno ? ` / ${krotko(d.okno)} (${zaj}%)` : ""}`;
  const pig = (co, tresc, tip, klasa) => html`<button type="button" class=${cx("j-pig", klasa, menu && menu.co === co && "is-otw")} title=${tip}
    aria-haspopup=${co === "fast" ? undefined : "dialog"} aria-expanded=${co === "fast" ? undefined : String(!!(menu && menu.co === co))}
    onClick=${(e) => otworz(co, e)}>${tresc}</button>`;
  const zamknij = () => setMenu(null);
  return html`<span class="j-pig-w">
      ${pig("model", krotkiModel(d.model), `${d.model}: ${L("kliknij, żeby zmienić model", "click to change the model")}`)}
      ${pig("wysilek", html`<${Slupki} poziom=${d.wysilek}/><span>${d.wysilek || L("domyślne", "default")}</span>`,
        L("Wysiłek myślenia: kliknij, żeby zmienić", "Thinking effort: click to change"), "is-zb")}
      ${d.fast_dostepny && pig("fast", html`<${Ikona} n="bolt" r=${14}/><span class="j-sr">${L("Tryb szybki", "Fast mode")}</span>`,
        L(`Tryb szybki ${d.fast ? "włączony" : "wyłączony"}: kliknij, żeby przełączyć`, `Fast mode ${d.fast ? "on" : "off"}: click to toggle`),
        cx("is-zb", "is-fast", !d.fast && "is-wyc"))}
    </span><span class="j-rozpych"></span>
    ${pig("kontekst", html`<${Pierscien} p=${d.procent}/><span>${zaj != null ? `${zaj}%` : krotko(d.kontekst)}</span>`,
      dymek, cx("j-pig-k", zaj >= 80 && "is-duzo"))}
    ${menu && menu.co === "model" && html`<${Wysuwka} kotwica=${menu.kotwica} onZamknij=${zamknij} etykieta=${L("Wybór modelu", "Model picker")} klasa="is-model">
      <${ModelWybor} o=${menu.o} onWybierz=${(m) => (m.biezacy ? zamknij() : kom(Komendy.komendaModelu(m)))}/></${Wysuwka}>`}
    ${menu && menu.co === "wysilek" && html`<${Wysuwka} kotwica=${menu.kotwica} onZamknij=${zamknij} etykieta=${L("Wysiłek myślenia", "Thinking effort")} klasa="is-wysilek">
      <${WysilekWybor} poziomy=${menu.o.poziomy} biezacy=${menu.o.wysilek} onWybierz=${(p) => kom(`/effort ${p}`)}/></${Wysuwka}>`}
    ${menu && menu.co === "kontekst" && html`<${Wysuwka} kotwica=${menu.kotwica} onZamknij=${zamknij} etykieta=${L("Kontekst rozmowy", "Conversation context")} klasa="is-kontekst">
      <${KontekstWybor} d=${d} onKomenda=${kom}/></${Wysuwka}>`}`;
}

Zasoby.daj({ Stopka });
