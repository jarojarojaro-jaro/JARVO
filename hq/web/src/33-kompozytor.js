// Kompozytor (docs/HQ.md „Aplikacja”, §13.11): pole wiadomości z wyborem adresata na jedną wiadomość (ChipAdresata:
// „Do: Jarvo” albo „Do: Web · tylko ta wiadomość”, × i Esc anulują, po wysłaniu wraca „Do: Jarvo”), podpowiedziami
// @wzmianek (listbox, strzałki, Enter/Tab, Esc), załącznikami (przycisk, wklejenie, przeciągnięcie; obrazy jako data URL,
// reszta przez /upload), szkicem na wątek, Enter = wyślij, Shift+Enter = nowa linia, ↑ w pustym polu = ostatnia własna
// wiadomość, paskiem trwającej pracy z „Zatrzymaj” i Esc Esc (stop wszystkich prac wątku).

const ZAL_OBRAZ = /^image\/(png|jpeg|webp|gif)$/;
const ZAL_PLIKI_MAKS = 8, ZAL_OBRAZY_MAKS = 4, ZAL_OBRAZY_BAJTY = 7000000, ZAL_PLIK_BAJTY = 50 * 1024 * 1024;

const uchwytAgenta = (a) => a.handle || Wzmianki.aliasyAgenta(a)[0] || a.name;


// agenci floty w kolejności z /app (koordynator pierwszy), bez archiwalnych
function useAgenciFloty(koordynator) {
  const agenci = useSklep((s) => s.agenci);
  const kolejnosc = useSklep((s) => s.kolejnosc);
  return useMemo(() => {
    const l = kolejnosc.map((n) => agenci[n]).filter((a) => a && a.stan !== "archiwum");
    l.sort((a, b) => (b.name === koordynator) - (a.name === koordynator));
    return l;
  }, [agenci, kolejnosc, koordynator]);
}

function zapiszSzkic(k, tekst, pliki) {
  sklep.ustaw((s) => {
    const sz = { ...s.szkice };
    if (String(tekst || "").trim() || (pliki && pliki.length)) sz[k] = { tekst, pliki, ts: Date.now() / 1000 };
    else if (sz[k]) delete sz[k];
    else return s;
    return { ...s, szkice: sz };
  });
}

// ------------------------------------------------------------------------------------------------- wybór adresata
function ChipAdresata({ wybor, koordynator, agenci, onWybierz }) {
  const [otwarte, setOtwarte] = useState(false);
  const [i, setI] = useState(0);
  const btn = useRef(null), lista = useRef(null);
  const id = useIdJarvo();
  const zamknij = () => setOtwarte(false);
  useWarstwa(otwarte, zamknij, lista, { pulapka: false });
  useEffect(() => {
    if (!otwarte) return undefined;
    const obok = (e) => { if (lista.current && !lista.current.contains(e.target) && !btn.current.contains(e.target)) zamknij(); };
    const t = setTimeout(() => document.addEventListener("pointerdown", obok), 0);
    return () => { clearTimeout(t); document.removeEventListener("pointerdown", obok); };
  }, [otwarte]);
  const otworz = () => { setI(Math.max(0, agenci.findIndex((a) => a.name === (wybor.agenci[0] || koordynator)))); setOtwarte(true); };
  const wybierz = (a) => { zamknij(); onWybierz(a.name === koordynator ? null : a.name); };
  const klawisz = (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setI((i + 1) % agenci.length); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setI((i - 1 + agenci.length) % agenci.length); }
    else if (e.key === "Home") { e.preventDefault(); setI(0); }
    else if (e.key === "End") { e.preventDefault(); setI(agenci.length - 1); }
    else if ((e.key === "Enter" || e.key === " ") && agenci[i]) { e.preventDefault(); wybierz(agenci[i]); }
    else if (e.key === "Tab") { e.preventDefault(); zamknij(); }   // jak menu: Tab zamyka listę, fokus wraca na chip
  };
  // fokus wyszedł z listy (czytnik ekranu, kliknięcie poza nią): lista się zamyka
  const wyszedl = (e) => { if (e.relatedTarget && !e.currentTarget.contains(e.relatedTarget) && e.relatedTarget !== btn.current) zamknij(); };
  useEffect(() => {
    const ul = otwarte && lista.current, el = ul && ul.querySelector(`[data-i="${i}"]`);
    if (!el) return;
    // tylko w liście (scrollIntoView przewinąłby też oś i korzeń aplikacji)
    if (el.offsetTop < ul.scrollTop) ul.scrollTop = el.offsetTop;
    else if (el.offsetTop + el.offsetHeight > ul.scrollTop + ul.clientHeight) ul.scrollTop = el.offsetTop + el.offsetHeight - ul.clientHeight;
  }, [i, otwarte]);
  const jeden = wybor.zrodlo != null;
  const nazwy = (jeden ? wybor.agenci : [koordynator]).map(nazwaAgenta).join(", ");
  const glowny = sklep.stan().agenci[jeden ? wybor.agenci[0] : koordynator] || { name: koordynator };
  return html`<span class=${cx("j-do", jeden && "is-jeden")}>
    <button type="button" class="j-do-b" ref=${btn} data-agent=${jeden ? wybor.agenci[0] : koordynator} aria-haspopup="listbox" aria-expanded=${String(otwarte)}
      aria-controls=${otwarte ? id : undefined} title=${T("kompozytor.do_opis")} onClick=${() => (otwarte ? zamknij() : otworz())}>
      <span class="j-do-l">${T("kompozytor.do")}</span><${Awatar} agent=${glowny} r=${20}/><b>${nazwy}</b>
      ${jeden ? html`<span class="j-do-jeden">· ${T("kompozytor.tylko_ta")}</span>` : html`<${Ikona} n="down" r=${14}/>`}
    </button>
    ${wybor.zrodlo === "wybor" && html`<button type="button" class="j-do-x" aria-label=${T("kompozytor.anuluj_wybor")}
      title=${T("kompozytor.anuluj_wybor")} onClick=${() => onWybierz(null)}><${Ikona} n="x" r=${14}/></button>`}
    ${otwarte && html`<ul class="j-lista-ag" role="listbox" id=${id} ref=${lista} tabIndex="-1" aria-label=${T("kompozytor.do_opis")} onBlur=${wyszedl}
        aria-activedescendant=${`${id}-${i}`} onKeyDown=${klawisz} data-fokus="">
      ${agenci.map((a, n) => html`<li key=${a.name} id=${`${id}-${n}`} data-i=${n} data-agent=${a.name} role="option" aria-selected=${String(n === i)}
          class=${cx("j-opcja-ag", n === i && "is-aktywna")} onMouseMove=${() => n !== i && setI(n)} onClick=${() => wybierz(a)}>
        <${Awatar} agent=${a} r=${26}/><span class="j-opcja-t"><b>${nazwaAgenta(a.name)}</b>
          <small>${a.name === koordynator ? T("kompozytor.koordynuje") : rolaAgenta(a)}</small></span>
        <span class="j-opcja-u">@${uchwytAgenta(a)}</span></li>`)}
    </ul>`}
  </span>`;
}

// ------------------------------------------------------------------------------------------------- załączniki
function ZalacznikiKompozytora({ obrazy, pliki, wgrywa, onUsunObraz, onUsunPlik }) {
  if (!obrazy.length && !pliki.length && !wgrywa) return null;
  return html`<ul class="j-zal" aria-label=${T("zal.etykieta")}>
    ${obrazy.map((o) => html`<li key=${o.id} class="j-zal-p is-obraz"><img src=${o.dane} alt=""/><span class="j-zal-n">${o.nazwa}</span>
      <button type="button" class="j-zal-x" aria-label=${T("zal.usun", { nazwa: o.nazwa })} onClick=${() => onUsunObraz(o.id)}><${Ikona} n="x" r=${12}/></button></li>`)}
    ${pliki.map((p) => html`<li key=${p.path} class="j-zal-p"><${Ikona} n="clip" r=${14}/><span class="j-zal-n" title=${p.path}>${p.name}</span>
      <span class="j-zal-r">${bytes(p.size)}</span>
      <button type="button" class="j-zal-x" aria-label=${T("zal.usun", { nazwa: p.name })} onClick=${() => onUsunPlik(p.path)}><${Ikona} n="x" r=${12}/></button></li>`)}
    ${wgrywa > 0 && html`<li class="j-zal-p is-wgrywa"><${Spinner}/><span class="j-zal-n">${T("zal.wgrywam", { n: wgrywa })}</span></li>`}
  </ul>`;
}

// ------------------------------------------------------------------------------------------------- pasek pracy
function PasekNaZywo({ przebiegi, watek }) {
  const teraz = useTeraz(1000, przebiegi.length > 0);
  const [stop, setStop] = useState(false);
  // sama prośba o zgodę: karta w wątku mówi wszystko, pasek by ją powtarzał (Esc Esc dalej zatrzymuje)
  if (!przebiegi.length || przebiegi.every((x) => x.stan === "czeka_na_zgode")) return null;
  const p = przebiegi.find((x) => x.stan !== "czeka_na_zgode") || przebiegi[0], od = p.przyjety_at || p.utworzony_at;
  const zatrzymuje = stop || przebiegi.every((x) => x.stan === "zatrzymywanie");
  const zatrzymaj = async () => { setStop(true); try { await akcje.zatrzymaj(watek); } finally { setStop(false); } };
  return html`<div class="j-zywo" role="group" aria-label=${T("zywo.etykieta")}>
    <${Awatar} agent=${sklep.stan().agenci[p.agent] || { name: p.agent }} r=${20}/>
    <span class="j-zywo-t"><b>${nazwaAgenta(p.agent)}</b> ${T(`przebieg.${p.stan}`)}${przebiegi.length > 1 ? ` · ${T("zywo.i_inni", { n: przebiegi.length - 1 })}` : ""}</span>
    ${od ? html`<span class="j-zywo-c" aria-hidden="true">${Czas.trwanie(teraz - od)}</span>` : null}
    <span class="j-rozpych"></span>
    <${Przycisk} maly rodzaj="cichy" ikona="stop" disabled=${zatrzymuje} onClick=${zatrzymaj} podpowiedz=${T("zywo.esc")}>
      ${T(zatrzymuje ? "zywo.zatrzymuje" : "zywo.zatrzymaj")}</${Przycisk}>
  </div>`;
}

// ------------------------------------------------------------------------------------------------- kompozytor
function Kompozytor({ watek = null, panel = 0, koordynator = "jarvo", start = false }) {
  const k = watek || "nowa";
  const kluczA = `${panel}:${k}`;
  const wybrany = useSklep((s) => s.adresaci[kluczA] || null);
  const brama = useSklep((s) => (s.gotowosc && s.gotowosc.brama) || null);
  const aktywne = useSklep((s) => (watek ? Os.doZatrzymania(Object.values(s.przebiegi).filter((p) => p.watek_id === watek)) : []), plytko);
  const agenci = useAgenciFloty(koordynator);
  const aliasy = useMemo(() => Wzmianki.mapaAliasow(agenci), [agenci]);
  const nazwy = useMemo(() => Wzmianki.nazwyAgentow(agenci), [agenci]);
  const szkic = useMemo(() => sklep.stan().szkice[k] || {}, [k]);
  const [tekst, setTekst] = useState(szkic.tekst || "");
  const [pliki, setPliki] = useState(szkic.pliki || []);
  const [obrazy, setObrazy] = useState([]);
  const [wgrywa, setWgrywa] = useState(0);
  const [wzm, setWzm] = useState(null);
  const [uwaga, setUwaga] = useState(null);
  const [nad, setNad] = useState(false);
  const pole = useRef(null), wybierak = useRef(null), esc = useRef(0), czasUwagi = useRef(0);
  const stan = useRef({});
  stan.current = { tekst, pliki, obrazy };
  const id = useIdJarvo();

  const a = useMemo(() => Pisanie.adresat(tekst, wybrany, aliasy, koordynator, nazwy), [tekst, wybrany, aliasy, koordynator, nazwy]);
  const ustawWybor = (agent) => sklep.zmien("adresaci", { [kluczA]: agent || undefined });
  const pokazUwage = (t, zle = false, ms = 4000) => {
    clearTimeout(czasUwagi.current);
    setUwaga({ t, zle });
    czasUwagi.current = setTimeout(() => setUwaga(null), ms);
  };

  // szkic tego wątku: zapis po chwili bez pisania i przy wyjściu z wątku; wybór adresata nie przechodzi na inny wątek
  useEffect(() => {
    const t = setTimeout(() => zapiszSzkic(k, tekst, pliki), 400);
    return () => clearTimeout(t);
  }, [tekst, pliki, k]);
  useEffect(() => () => {
    clearTimeout(czasUwagi.current);
    zapiszSzkic(k, stan.current.tekst, stan.current.pliki);
    if (sklep.stan().adresaci[kluczA]) sklep.zmien("adresaci", { [kluczA]: undefined });
  }, [k]);

  // wysokość pola rośnie z treścią (do max-height w CSS)
  React.useLayoutEffect(() => {
    const el = pole.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [tekst]);

  // ------------------------------------------------------------------- załączniki
  const dodajPliki = async (lista) => {
    for (const f of [...(lista || [])]) {
      if (ZAL_OBRAZ.test(f.type || "")) {
        if (stan.current.obrazy.length >= ZAL_OBRAZY_MAKS) { pokazUwage(T("zal.za_duzo_obrazow", { n: ZAL_OBRAZY_MAKS }), true); continue; }
        try {
          const dane = await imageDataUrl(f);
          const suma = stan.current.obrazy.reduce((s, o) => s + o.dane.length, 0) + dane.length;
          if (suma > ZAL_OBRAZY_BAJTY) { pokazUwage(T("zal.obrazy_za_duze"), true); continue; }
          const o = { id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, nazwa: f.name || "obraz", dane };
          stan.current.obrazy = stan.current.obrazy.concat([o]);
          setObrazy((x) => x.concat([o]));
        } catch (_) { pokazUwage(T("zal.zly_obraz", { nazwa: f.name || "obraz" }), true); }
        continue;
      }
      if (f.size > ZAL_PLIK_BAJTY) { pokazUwage(T("zal.za_duzy", { nazwa: f.name, mb: 50 }), true); continue; }
      if (!f.size) { pokazUwage(T("zal.pusty", { nazwa: f.name }), true); continue; }
      if (stan.current.pliki.length >= ZAL_PLIKI_MAKS) { pokazUwage(T("zal.za_duzo", { n: ZAL_PLIKI_MAKS }), true); continue; }
      setWgrywa((n) => n + 1);
      try {
        const e = await api.upload(f);
        const p = { path: e.path, name: e.name || f.name, size: e.size != null ? e.size : f.size, kind: e.kind || kindOf(e.path) };
        stan.current.pliki = stan.current.pliki.concat([p]);
        setPliki((x) => x.concat([p]));
      } catch (err) {
        pokazUwage(T("zal.nie_wgrano", { nazwa: f.name, blad: err.message || "" }), true, 7000);
      } finally { setWgrywa((n) => n - 1); }
    }
  };

  // Odpowiedz, przywrócony tekst nieudanej wiadomości, pliki upuszczone na wątek (akcje.doKompozytora)
  useEffect(() => {
    const f = (e) => {
      const d = e.detail || {};
      if (d.k !== k) return;
      if (d.tekst != null && (!d.tylkoPusty || !stan.current.tekst.trim())) setTekst(d.tekst);
      if (d.pliki) dodajPliki(d.pliki);
      if (d.fokus || d.tekst != null) requestAnimationFrame(() => pole.current && pole.current.focus());
    };
    window.addEventListener("jarvo-kompozytor", f);
    return () => window.removeEventListener("jarvo-kompozytor", f);
  }, [k]);

  // ------------------------------------------------------------------- wzmianki
  const podp = useMemo(() => (wzm ? Pisanie.podpowiedzi(agenci, wzm.q, koordynator) : []), [wzm && wzm.q, agenci, koordynator]);
  const sprawdzWzmianke = (el) => {
    const m = Pisanie.wzmiankaPrzyKursorze(el.value, el.selectionStart);
    setWzm(m ? { ...m, i: wzm && wzm.q === m.q ? wzm.i : 0 } : null);
  };
  const wybierzWzmianke = (ag) => {
    const r = Pisanie.wstawWzmianke(tekst, wzm, uchwytAgenta(ag));
    setTekst(r.tekst);
    setWzm(null);
    requestAnimationFrame(() => { const el = pole.current; if (el) { el.focus(); el.setSelectionRange(r.kursor, r.kursor); } });
  };

  // ------------------------------------------------------------------- wysyłka
  const pusta = !tekst.trim() && !pliki.length && !obrazy.length;
  const mozna = !pusta && !wgrywa;
  const wyslij = async () => {
    if (!mozna) return;
    // powyżej progu WIELU (wzmianki.py i 12-wzmianki.js) pytamy, zanim praca pójdzie do kilku agentów naraz
    if (a.wielu && !(await akcje.zapytaj({ rodzaj: "wielu", dane: { n: a.agenci.length } }))) return;
    akcje.wyslij({ watek, tekst: tekst.trim(), pliki, obrazy, adresaci: a.zrodlo === "wybor" ? a.adresaci : null, koordynator });
    setTekst(""); setPliki([]); setObrazy([]); setWzm(null);
    stan.current = { tekst: "", pliki: [], obrazy: [] };
    zapiszSzkic(k, "", []);
    if (wybrany) ustawWybor(null);
  };
  // ↑ w pustym polu: ostatnia własna wiadomość jako szkic (historia Hermesa jest tylko do dopisywania)
  const przywolaj = () => {
    const os = watek && sklep.stan().os[watek];
    const ost = os && [...os.pozycje].reverse().find((x) => x.rodzaj === "wlasciciel" && x.tekst);
    if (ost) { setTekst(ost.tekst); return true; }
    return false;
  };

  const klawisz = (e) => {
    if (e.isComposing || e.keyCode === 229) return;
    if (wzm && podp.length) {
      const i = wzm.i || 0;
      if (e.key === "ArrowDown") { e.preventDefault(); setWzm({ ...wzm, i: (i + 1) % podp.length }); return; }
      if (e.key === "ArrowUp") { e.preventDefault(); setWzm({ ...wzm, i: (i - 1 + podp.length) % podp.length }); return; }
      if (e.key === "Enter" || e.key === "Tab") { e.preventDefault(); wybierzWzmianke(podp[i]); return; }
      if (e.key === "Escape") { e.preventDefault(); setWzm(null); return; }
    }
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); wyslij(); return; }
    if ((e.key === "PageUp" || e.key === "PageDown") && !e.shiftKey && !e.altKey && !e.ctrlKey && !e.metaKey) {
      const s = document.querySelector(".j-watek-s");   // z kompozytora przewija się rozmowa, jak w czatach
      if (s) { e.preventDefault(); s.scrollBy({ top: (e.key === "PageUp" ? -1 : 1) * s.clientHeight * 0.85, behavior: Ruch.zachowanie() }); }
      return;
    }
    if (e.key === "ArrowUp" && !tekst && !pliki.length && przywolaj()) { e.preventDefault(); return; }
    if (e.key === "Escape" && !e.defaultPrevented) {
      if (wybrany) { e.preventDefault(); ustawWybor(null); return; }
      if (aktywne.length) {
        e.preventDefault();
        const t = Date.now();
        if (t - esc.current < 2000) {
          esc.current = 0;
          akcje.zatrzymaj(watek);
          pokazUwage(T("zywo.zatrzymuje"), false, 2000);
        } else {
          esc.current = t;
          pokazUwage(T("kompozytor.esc_ponownie"), false, 2000);
        }
      }
    }
  };
  const wklej = (e) => {
    const fs = e.clipboardData && e.clipboardData.files;
    if (fs && fs.length) { e.preventDefault(); dodajPliki(fs); }
  };
  const zPlikami = (e) => e.dataTransfer && [...(e.dataTransfer.types || [])].includes("Files");

  // ------------------------------------------------------------------- podpowiedź pod polem (jedna naraz)
  // podczas pisania wzmianki (lista podpowiedzi przy kursorze) nie podpowiadamy jeszcze, kto dostanie wiadomość
  const koord = nazwaAgenta(koordynator);
  let pod = null;
  if (uwaga) pod = uwaga;
  else if (wzm) pod = null;
  else if (a.nieznany) pod = { t: T("kompozytor.nieznany", { nazwa: a.nieznany, koord }) };
  else if (a.srodek.length && a.zrodlo !== "tekst") pod = { t: T("kompozytor.srodek", { koord }) };
  else if (a.zrodlo === "wybor") pod = { t: T("kompozytor.wybor_opis") };
  // na starcie stan bramy pokazuje karta gotowości (jedno miejsce, nie dwa)
  else if (!start && (brama === "startuje" || brama === "niedostepna")) pod = { t: T(`kompozytor.brama_${brama}`) };
  const placeholder = T(start ? "kompozytor.ph_start" : "kompozytor.ph");
  const aktywnaWzm = wzm && podp.length ? `${id}-w-${wzm.i || 0}` : undefined;

  return html`<div class=${cx("j-komp-w", start && "is-start")}
      onDragOver=${(e) => { if (zPlikami(e)) { e.preventDefault(); e.stopPropagation(); setNad(true); } }}
      onDragLeave=${(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setNad(false); }}
      onDrop=${(e) => { if (zPlikami(e)) { e.preventDefault(); e.stopPropagation(); setNad(false); dodajPliki(e.dataTransfer.files); } }}>
   <div class=${cx("j-komp", nad && "is-nad")}>
    <${PasekNaZywo} przebiegi=${aktywne} watek=${watek}/>
    <${ZalacznikiKompozytora} obrazy=${obrazy} pliki=${pliki} wgrywa=${wgrywa}
      onUsunObraz=${(x) => { stan.current.obrazy = stan.current.obrazy.filter((o) => o.id !== x); setObrazy((o) => o.filter((y) => y.id !== x)); }}
      onUsunPlik=${(x) => { stan.current.pliki = stan.current.pliki.filter((p) => p.path !== x); setPliki((p) => p.filter((y) => y.path !== x)); }}/>
    <label class="j-sr" for=${`${id}-pole`}>${T("kompozytor.etykieta")}</label>
    <textarea id=${`${id}-pole`} ref=${pole} class="j-komp-pole" data-kompozytor="" rows="1" spellcheck="true"
      placeholder=${placeholder} value=${tekst} aria-describedby=${`${id}-pod`}
      aria-autocomplete="list" aria-controls=${wzm && podp.length ? `${id}-w` : undefined} aria-activedescendant=${aktywnaWzm}
      onInput=${(e) => { setTekst(e.target.value); sprawdzWzmianke(e.target); }}
      onKeyDown=${klawisz} onKeyUp=${(e) => { if (e.key === "ArrowLeft" || e.key === "ArrowRight" || e.key === "Home" || e.key === "End") sprawdzWzmianke(e.target); }}
      onClick=${(e) => sprawdzWzmianke(e.target)} onBlur=${() => setTimeout(() => setWzm(null), 150)} onPaste=${wklej}></textarea>
    ${wzm && podp.length > 0 && html`<ul class="j-wzm" role="listbox" id=${`${id}-w`} aria-label=${T("kompozytor.wzmianki")}>
      ${podp.map((ag, n) => html`<li key=${ag.name} id=${`${id}-w-${n}`} data-agent=${ag.name} role="option" aria-selected=${String(n === (wzm.i || 0))}
          class=${cx("j-opcja-ag", n === (wzm.i || 0) && "is-aktywna")} onMouseDown=${(e) => { e.preventDefault(); wybierzWzmianke(ag); }}>
        <${Awatar} agent=${ag} r=${24}/><span class="j-opcja-t"><b>${nazwaAgenta(ag.name)}</b>
          <small>${ag.name === koordynator ? T("kompozytor.koordynuje") : rolaAgenta(ag)}</small></span>
        <span class="j-opcja-u">@${uchwytAgenta(ag)}</span></li>`)}
    </ul>`}
    <div class="j-komp-pasek">
      <${ChipAdresata} wybor=${a} koordynator=${koordynator} agenci=${agenci} onWybierz=${(x) => { ustawWybor(x); requestAnimationFrame(() => pole.current && pole.current.focus()); }}/>
      <span class="j-rozpych"></span>
      <${Przycisk} rodzaj="cichy" ikona="clip" etykieta=${T("zal.dodaj")} podpowiedz=${T("zal.dodaj")} onClick=${() => wybierak.current && wybierak.current.click()}/>
      <input type="file" multiple hidden ref=${wybierak} onChange=${(e) => { dodajPliki(e.target.files); e.target.value = ""; }}/>
      <button type="button" class=${cx("j-wyslij", mozna && "is-gotowy")} disabled=${!mozna} onClick=${wyslij}
        aria-label=${T("kompozytor.wyslij")} title=${T("kompozytor.wyslij_opis")}><${Ikona} n="up" r=${18}/></button>
    </div>
   </div>
    <p class=${cx("j-komp-pod", pod && pod.zle && "is-zle")} id=${`${id}-pod`} aria-live="polite">${pod ? pod.t : ""}</p>
  </div>`;
}
