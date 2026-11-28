// Komendy po „/” w kompozytorze (docs/HQ.md „Komendy”, serwer: hq/plugin/komendy.py). Brama Hermesa nie wykonuje
// komend, więc tekst `/nazwa …` nigdy nie idzie do agenta: wykonuje go `POST /komendy`, a wynik staje w rozmowie jako
// wpis systemowy typu „komenda” (WynikKomendy). Menu komend (MenuKomend) bierze katalog rozmowy z `GET /komendy`:
// komendy, które panel wykonuje, najpierw, reszta rejestru Hermesa jako niedostępna z powodem (widać ją po wpisaniu
// początku nazwy). Enter wykonuje podświetloną komendę, Tab ją dopisuje (do argumentów), Esc zamyka menu.
// „//tekst” to zwykła wiadomość (serwer też tak to czyta).

const Komendy = (() => {
  const RE = /^\/([A-Za-z][A-Za-z0-9_-]{0,31})(?:@[\w.-]+)?(?:\s+([\s\S]*))?$/;
  const MENU_MAKS = 12;
  // bliźniak komendy.parsuj: {nazwa, args} albo null („/etc/hosts …” i „//…” to zwykły tekst)
  function parsuj(tekst) {
    const m = RE.exec(String(tekst || "").trim());
    return m ? { nazwa: m[1].toLowerCase(), args: (m[2] || "").trim() } : null;
  }
  // nazwa w trakcie pisania (całe pole to „/” albo „/mo”, bez spacji): fragment do menu, inaczej null
  function pisana(tekst) {
    const m = /^\/([A-Za-z0-9_-]{0,32})$/.exec(String(tekst || ""));
    return m ? m[1].toLowerCase() : null;
  }
  const pamiec = new Map();
  // katalog rozmowy (raz na rozmowę i adresata; błąd nie zostaje w pamięci, następna próba pyta znowu)
  function katalog(watek, agent) {
    const k = `${watek || ""}|${agent || ""}`;
    if (!pamiec.has(k)) {
      pamiec.set(k, api.komendy.lista({ watek: watek || "", agent: agent || "" }).catch((e) => { pamiec.delete(k); throw e; }));
    }
    return pamiec.get(k);
  }
  // podpowiedzi menu: nazwa albo alias zaczyna się od fragmentu; przy samym „/” tylko komendy panelu (rejestr Hermesa
  // ma ich kilkadziesiąt: pokazujemy je, gdy właściciel zacznie pisać nazwę)
  function podpowiedzi(lista, q) {
    const out = [];
    for (const c of lista || []) {
      if (!q && !c.panel) continue;
      const traf = [c.nazwa, ...(c.aliasy || [])].find((n) => n.startsWith(q || ""));
      if (traf != null) out.push(c);
    }
    return out.slice(0, MENU_MAKS);
  }
  // POST /komendy; wpis wyniku od razu na osi (strumień przyniesie ten sam wpis, Os.osWpis podmienia po id); `cicho`
  // (stopka: model, wysiłek, tryb szybki) = bez wpisu w rozmowie
  async function wykonaj({ watek = null, agent = null, tekst, cicho = false }) {
    const klucz = Pisanie.klucz(crypto.getRandomValues(new Uint8Array(16)));
    const odp = await api.komendy.wykonaj({ tekst, klucz, watek, agent, ...(cicho ? { cicho } : {}) });
    if (watek && odp && odp.wpis) {
      sklep.ustaw((s) => (s.os[watek] ? { ...s, os: { ...s.os, [watek]: Os.osWpis(s.os[watek], odp.wpis) } } : s));
    }
    return odp;
  }
  const zWpisu = (x) => !!(x && x.wpis && x.wpis.dane && x.wpis.dane.typ === "komenda");
  // przycisk modelu z wyniku `/model`: Hermes „/model <id> --provider <slug>”, omp „/model <dostawca/id>”
  const komendaModelu = (w) => `/model ${w.model}${w.provider ? ` --provider ${w.provider}` : ""}`;
  return { parsuj, pisana, katalog, podpowiedzi, wykonaj, zWpisu, komendaModelu };
})();

// menu komend nad polem kompozytora (listbox jak podpowiedzi @wzmianek; fokus zostaje w polu)
function MenuKomend({ id, lista, aktywna, onWybierz, onNajedz }) {
  if (!lista.length) return null;
  return html`<ul class="j-wzm j-kom-menu" role="listbox" id=${id} aria-label=${T("komendy.menu")}>
    ${lista.map((c, n) => html`<li key=${c.nazwa} id=${`${id}-${n}`} role="option" aria-selected=${String(n === aktywna)}
        aria-disabled=${c.dziala ? undefined : "true"} data-komenda=${c.nazwa}
        class=${cx("j-opcja-kom", n === aktywna && "is-aktywna", !c.dziala && "is-niedostepna")}
        onMouseMove=${() => n !== aktywna && onNajedz(n)} onMouseDown=${(e) => { e.preventDefault(); onWybierz(c); }}>
      <span class="j-opcja-kom-n">/${c.nazwa}${c.argumenty ? html` <small>${c.argumenty}</small>` : null}</span>
      <span class="j-opcja-kom-o">${c.dziala ? (isPL() ? c.opis : c.opis_en)
        : html`<em>${T("komendy.niedostepna")}</em> · ${isPL() ? c.powod : c.powod_en}`}</span>
    </li>`)}
  </ul>`;
}

// `/compact` sesji omp w rozmowie: jedna linia jak inne zdarzenia osi, z kółkiem i licznikiem czasu, póki trwa (jak
// „Compacting context…” w terminalu omp), potem liczby tokenów; ten sam wpis przechodzi z `trwa` w wynik
function KomendaWToku({ x, d }) {
  const trwa = !!d.trwa;
  const [teraz, setTeraz] = useState(() => Date.now() / 1000);
  useEffect(() => {
    if (!trwa) return undefined;
    const t = setInterval(() => setTeraz(Date.now() / 1000), 1000);
    return () => clearInterval(t);
  }, [trwa]);
  const k = d.kompresja || {};
  let tekst;
  if (trwa) tekst = d.komenda === "compact" ? T("komendy.kompresja_trwa") : T("komendy.trwa", { komenda: d.polecenie || "" });
  else if (k.przed && k.po) {
    tekst = T("os.kompresjaTokeny", { przed: krotkoTokeny(k.przed), po: krotkoTokeny(k.po) });
    if (typeof k.procent === "number") tekst += ` · ${T("komendy.procent_okna", { procent: k.procent.toFixed(1).replace(".", isPL() ? "," : ".") })}`;
  } else tekst = ((isPL() ? d.wynik : d.wynik_en || d.wynik) || "").replace(/`/g, "");
  const s = Math.max(0, Math.round(teraz - (x.ts || teraz)));
  return html`<p class=${cx("j-msg-sys is-komenda", trwa && "is-trwa")} data-pozycja=${x.id} role="status" aria-live="polite">
    ${trwa ? html`<span class="j-spin" aria-hidden="true"></span>` : html`<${Ikona} n="repeat" r=${14}/>`}<span>${tekst}</span>
    ${d.agent && html`<span class="j-kom-sys-ag">· ${nazwaAgenta(d.agent)}</span>`}
    <time class="j-kom-sys-czas">${trwa ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}` : Czas.godzina(x.ts)}</time></p>`;
}

// wynik komendy: w rozmowie z wpisu osi (`x`), na ekranie startu z odpowiedzi trasy (`dane`, `onZamknij`)
function WynikKomendy(props) {
  const { x = null, dane = null } = props;
  const d = dane || (x && x.wpis && x.wpis.dane) || {};
  return x && d.ok !== false && (d.trwa || d.komenda === "compact") ? html`<${KomendaWToku} x=${x} d=${d}/>`
    : html`<${KartaKomendy} ...${props}/>`;
}

function KartaKomendy({ x = null, dane = null, watek = null, onZamknij = null }) {
  const d = dane || (x && x.wpis && x.wpis.dane) || {};
  const [trwa, setTrwa] = useState(null);
  const wybor = Array.isArray(d.wybor) ? d.wybor : [];
  const tekst = (isPL() ? d.wynik : d.wynik_en || d.wynik) || "";
  // w rozmowie przycisk modelu od razu go wybiera (jak wybór w Telegramie), poza nią wstawia komendę do kompozytora
  const wybierz = async (w) => {
    const komenda = Komendy.komendaModelu(w);
    if (!watek) { akcje.doKompozytora("nowa", { tekst: `${komenda} --global`, fokus: true }); return; }
    setTrwa(komenda);
    try { await Komendy.wykonaj({ watek, agent: d.agent || null, tekst: komenda }); }
    catch (e) { Komunikaty.pokaz(T("komendy.blad", { blad: e && e.tekst ? e.tekst() : String(e) }), { rodzaj: "blad" }); }
    finally { setTrwa(null); }
  };
  return html`<article class=${cx("j-kom", d.ok === false && "is-zle")} data-pozycja=${x ? x.id : undefined} aria-label=${T("komendy.wynik")}>
    <p class="j-kom-pol"><${Ikona} n="wrench" r=${14}/><code>${d.polecenie || ""}</code>
      ${d.agent && html`<span class="j-kom-ag">· ${nazwaAgenta(d.agent)}</span>`}
      ${x && html`<time class="j-kom-czas">${Czas.godzina(x.ts)}</time>`}
      ${onZamknij && html`<${Przycisk} maly rodzaj="cichy" ikona="x" etykieta=${T("ui.zamknij")} onClick=${onZamknij}/>`}</p>
    <${TrescMd} tekst=${tekst} klasa="j-kom-t"/>
    ${wybor.length > 0 && html`<div class="j-kom-wybor" role="group" aria-label=${T("komendy.wybierz_model")}>
      ${wybor.map((w) => html`<button type="button" key=${`${w.provider}/${w.model}`} class=${cx("j-kom-model", w.biezacy && "is-biezacy")}
          aria-pressed=${w.biezacy ? "true" : undefined} disabled=${!!trwa} title=${Komendy.komendaModelu(w)} onClick=${() => wybierz(w)}>
        <span>${w.model}</span>${w.biezacy ? html`<small>${T("komendy.biezacy")}</small>` : w.nazwa && w.provider ? html`<small>${w.nazwa}</small>` : null}
      </button>`)}
    </div>`}
  </article>`;
}
