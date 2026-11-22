// Stopka bloczka wpisywania (pakiet „stopka”, ładowany przy pierwszej otwartej rozmowie; docs/HQ.md „Kompozytor”): dolny rząd
// białego bloczka jak w czatach z agentami. Lewo, obok „Do:”: pigułki model (skrót nazwy), myślenie (poziom) i ⚡ tryb
// szybki (wyciszony, gdy wyłączony); klik w model albo myślenie otwiera menu z GET /rozmowy/{id}/opcje, wybór idzie
// komendą (/model, /effort, /fast), więc zostaje w rozmowie jak w terminalu. Prawo, przy spinaczu: pierścień kontekstu
// z procentem okna (kolor uwagi od 80%); najechanie pokazuje szczegóły w dymku, klik otwiera je w menu ze
// „Skompresuj teraz” (omp: /compact) albo „Szczegóły” (/context). Dane: GET /rozmowy/{id}/licznik co 2 s, gdy trwa
// praca (i zaraz po jej końcu albo po komendzie), inaczej co 30 s; w ukrytej karcie przeglądarki nie pyta.

const krotko = (n) => (n >= 1e6 ? `${(n / 1e6).toFixed(n % 1e6 ? 1 : 0)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(n >= 1e4 ? 0 : 1)}k` : String(n || 0));
// „anthropic/claude-opus-5-5” → „opus-5-5” (dostawca i rodzina w menu i w dymku)
const krotkiModel = (m) => String(m || "?").split("/").pop().replace(/^claude-/, "");
const dolary = (x) => `$${Number(x || 0).toFixed(2)}`;

function Pierscien({ p }) {
  const o = 2 * Math.PI * 7;
  return html`<svg class="j-pier" viewBox="0 0 18 18" width="16" height="16" aria-hidden="true">
    <circle cx="9" cy="9" r="7" class="j-pier-t"/>
    <circle cx="9" cy="9" r="7" class="j-pier-w" transform="rotate(-90 9 9)"
      stroke-dasharray=${`${(o * Math.min(100, Math.max(0, p || 0))) / 100} ${o}`}/></svg>`;
}

function Stopka({ watek }) {
  const praca = useSklep((s) => Os.doZatrzymania(Object.values(s.przebiegi).filter((p) => p.watek_id === watek)).length > 0);
  const [d, setD] = useState(null);
  const [nr, setNr] = useState(0);
  const [menu, setMenu] = useState(null);           // {co: model|wysilek|kontekst, kotwica, o}
  useEffect(() => {
    let zywy = true, t = 0;
    const tik = async () => {
      if (!document.hidden) {
        // ta sama odpowiedź co 2 s nie rysuje stopki na nowo
        try { const r = await api.rozmowy.licznik(watek); if (zywy) setD((s) => (JSON.stringify(s) === JSON.stringify(r.licznik) ? s : r.licznik)); } catch (_) { /* bez stopki */ }
      }
      if (zywy) t = setTimeout(tik, praca ? 2000 : 30000);
    };
    tik();
    return () => { zywy = false; clearTimeout(t); };
  }, [watek, praca, nr]);
  if (!d || !(d.model || d.kontekst || d.wejscie)) return html`<span class="j-rozpych"></span>`;
  const kom = async (t) => {
    try { await Komendy.wykonaj({ watek, tekst: t }); } catch (e) { akcje._blad(e); }
    setNr((n) => n + 1);
  };
  const otworz = async (co, e) => {
    const kotwica = e.currentTarget;
    if (co === "fast") { kom(`/fast ${d.fast ? "off" : "on"}`); return; }
    if (co === "kontekst") { setMenu({ co, kotwica }); return; }
    try { setMenu({ co, kotwica, o: (await api.rozmowy.opcje(watek)).opcje }); } catch (er) { akcje._blad(er); }
  };
  const zaj = d.okno ? Math.round(d.procent) : null;
  const dzis = d.koszt_dzis > 0;
  const szczegoly = [
    `${L("Kontekst", "Context")}: ${d.szacunek ? "≈" : ""}${krotko(d.kontekst)}${d.okno ? ` / ${krotko(d.okno)} (${zaj}%)` : ""}`,
    `${L("Tokeny", "Tokens")}: ↑${krotko(d.wejscie)} ↓${krotko(d.wyjscie)}${d.cache_odczyt || d.cache_zapis ? ` · cache ${krotko(d.cache_odczyt)}/${krotko(d.cache_zapis)}` : ""}`,
    d.koszt > 0 && (dzis ? L(`Dziś ${dolary(d.koszt_dzis)}, cała sesja ${dolary(d.koszt)}`, `Today ${dolary(d.koszt_dzis)}, whole session ${dolary(d.koszt)}`)
      : L(`Cała sesja ${dolary(d.koszt)}`, `Whole session ${dolary(d.koszt)}`)),
    d.koszt > 0 && L("Ceny API (równoważnik; przy subskrypcji to nie jest rachunek)", "API prices (an equivalent; not a bill on a subscription)"),
  ].filter(Boolean);
  const ok = (b) => (b ? "✓ " : "");
  const pozycje = !menu ? [] : menu.co === "kontekst"
    ? szczegoly.map((t, i) => ({ id: `s${i}`, tekst: t, wylaczona: true })).concat([{ oddzielnik: true },
      d.zaplecze === "omp" ? { id: "c", ikona: "repeat", tekst: L("Skompresuj teraz (/compact)", "Compact now (/compact)"), akcja: () => kom("/compact") }
        : { id: "x", tekst: L("Szczegóły (/context)", "Details (/context)"), akcja: () => kom("/context") }])
    : menu.co === "model" ? menu.o.modele.map((m) => ({ id: m.model + m.provider, tekst: `${ok(m.biezacy)}${m.model} · ${m.nazwa}`,
      akcja: () => kom(Komendy.komendaModelu(m)) }))
      : menu.o.poziomy.map((p) => ({ id: p, tekst: ok(p === menu.o.wysilek) + p, akcja: () => kom(`/effort ${p}`) }))
        .concat([{ id: "d", tekst: ok(!menu.o.wysilek) + L("domyślne agenta", "agent default"), akcja: () => kom("/effort domyslny") }]);
  const pig = (co, tresc, tip, klasa) => html`<button type="button" class=${cx("j-pig", klasa)} title=${tip}
    aria-haspopup=${co === "fast" ? undefined : "menu"} onClick=${(e) => otworz(co, e)}>${tresc}</button>`;
  return html`<span class="j-pig-w">
      ${pig("model", krotkiModel(d.model), `${d.model}: ${L("kliknij, żeby zmienić model", "click to change the model")}`)}
      ${pig("wysilek", d.wysilek || L("domyślne", "default"), L("Wysiłek myślenia: kliknij, żeby zmienić", "Thinking effort: click to change"), "is-zb")}
      ${d.fast_dostepny && pig("fast", html`<${Ikona} n="bolt" r=${14}/><span class="j-sr">${L("Tryb szybki", "Fast mode")}</span>`,
        L(`Tryb szybki ${d.fast ? "włączony" : "wyłączony"}: kliknij, żeby przełączyć`, `Fast mode ${d.fast ? "on" : "off"}: click to toggle`),
        cx("is-zb", "is-fast", !d.fast && "is-wyc"))}
    </span><span class="j-rozpych"></span>
    ${pig("kontekst", html`<${Pierscien} p=${d.procent}/><span>${zaj != null ? `${zaj}%` : krotko(d.kontekst)}</span>`,
      szczegoly.join("\n"), cx("j-pig-k", zaj >= 80 && "is-duzo"))}
    ${menu && html`<${Menu} kotwica=${menu.kotwica} etykieta=${L("Stopka rozmowy", "Conversation footer")}
      onZamknij=${() => setMenu(null)} pozycje=${pozycje}/>`}`;
}

Zasoby.daj({ Stopka });
