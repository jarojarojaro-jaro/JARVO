// Pasek boczny (docs/HQ.md „Aplikacja”, makieta V2 · Spokojny): marka, Nowa rozmowa, Szukaj, lista wątków
// w grupach (Przypięte, Dziś, Wczoraj, Ten tydzień, Wcześniej), Archiwum i Kosz pod „⋯” obok Szukaj, stopka
// (właściciel, kropka połączenia otwierająca System, ustawienia). Wiersz: ikona źródła, tytuł w jednej linii, znak stanu (● czeka na Ciebie, ◌ pracuje, ⚠ błąd) z tekstem
// dla czytnika i menu ⋯ (Zmień nazwę, Przypnij, Archiwizuj, Usuń; w koszu Przywróć i Usuń na zawsze), widoczne po
// najechaniu, na dotyku zawsze, też długim przytrzymaniem (500 ms) i prawym przyciskiem. Długa lista (> 120 wierszy)
// rysuje tylko widoczne wiersze. Wiersz idzie przez WierszListy (typ elementu), gotowy na jednolitą listę z sesjami.
// Poniżej 1024 px pasek wysuwa się z lewej (przycisk menu w nagłówku) jako warstwa: treść obok nieaktywna, Esc zamyka.

// pozycje menu wątku (wiersz listy i nagłówek wątku); zależą od miejsca wątku: lista, archiwum, kosz
function pozycjeMenuWatku(w, { onZmienNazwe } = {}) {
  if (w.usuniety_at) {
    return [
      { id: "przywroc", ikona: "back", tekst: T("watek.przywroc"), akcja: () => akcje.przywroc(w.id) },
      { oddzielnik: true },
      { id: "usun_trwale", ikona: "trash", tekst: T("watek.usun_trwale"), niebezpieczna: true, akcja: () => akcje.usunNaZawsze(w.id) },
    ];
  }
  const p = [];
  if (onZmienNazwe) p.push({ id: "nazwa", ikona: "pen", tekst: T("watek.zmien_nazwe"), akcja: onZmienNazwe });
  if (!w.archiwum) {
    p.push({ id: "przypnij", ikona: "pin", tekst: T(w.przypiety ? "watek.odepnij" : "watek.przypnij"),
      akcja: () => akcje.zmienWatek(w.id, { przypiety: !w.przypiety }) });
  }
  p.push({ id: "archiwum", ikona: "folder", tekst: T(w.archiwum ? "watek.z_archiwum" : "watek.archiwizuj"),
    akcja: () => akcje.archiwizuj(w.id, !w.archiwum) });
  p.push({ oddzielnik: true }, { id: "kosz", ikona: "trash", tekst: T("watek.usun"), niebezpieczna: true, akcja: () => akcje.doKosza(w.id) });
  return p;
}

function WierszWatku({ w, aktywny, edycja, onMenu, onKoniecEdycji }) {
  const przytrzymanie = useRef({ czas: 0, bylo: false });
  if (edycja) {
    return html`<div class="j-wiersz-w is-edycja"><span class="j-wiersz-zr"><${Ikona} n="pen" r=${16}/></span>
      <${EdycjaTytulu} watek=${w} onKoniec=${onKoniecEdycji} klasa="j-wiersz-pole" fokusPo=${`[data-watek="${w.id}"]`}/></div>`;
  }
  const menu = (el) => onMenu(w, el);
  const dotyk = {
    onPointerDown: (e) => {
      if (e.pointerType !== "touch") return;
      const el = e.currentTarget;
      przytrzymanie.current.bylo = false;
      przytrzymanie.current.czas = setTimeout(() => { przytrzymanie.current.bylo = true; menu(el); }, 500);
    },
    onPointerUp: () => clearTimeout(przytrzymanie.current.czas),
    onPointerCancel: () => clearTimeout(przytrzymanie.current.czas),
    onPointerMove: (e) => { if (Math.abs(e.movementX) + Math.abs(e.movementY) > 6) clearTimeout(przytrzymanie.current.czas); },
    onClick: (e) => { if (przytrzymanie.current.bylo) { e.preventDefault(); przytrzymanie.current.bylo = false; } },
    onContextMenu: (e) => { e.preventDefault(); menu(e.currentTarget); },
  };
  return html`<div class=${cx("j-wiersz-l", aktywny && "is-aktywny")}>
    <a class=${cx("j-wiersz-w", w.nieprzeczytane > 0 && "is-nowe")} href=${Trasa.zbuduj({ widok: "watek", watek: w.id })}
        aria-current=${aktywny ? "page" : undefined} data-watek=${w.id} ...${dotyk}>
      <span class="j-wiersz-zr"><${Ikona} n=${w.przypiety ? "pin" : w.kanal === "telegram" ? "tg" : "msg"} r=${16}/></span>
      <span class="j-wiersz-tyt">${w.tytul || T("watek.bez_tytulu")}</span>
      <span class="j-wiersz-st"><${ZnakStanu} stan=${w.status}/>${w.nieprzeczytane > 0
        && html`<span class="j-sr">${T("watek.nieprzeczytane", { n: w.nieprzeczytane })}</span>`}</span>
    </a>
    <button type="button" class="j-wiersz-m j-ma-tip" aria-label=${T("watek.menu_wiersza", { tytul: w.tytul || T("watek.bez_tytulu") })}
      aria-haspopup="menu" onClick=${(e) => menu(e.currentTarget)}><${Ikona} n="more" r=${16}/><${Podpowiedz} tekst=${T("watek.menu")}/></button>
  </div>`;
}

// element listy po typie: dziś tylko wątek aplikacji; etap 6 doda sesję z innych kanałów
function WierszListy({ el, ...reszta }) {
  if (el.typ === "watek") return html`<${WierszWatku} w=${el.watek} ...${reszta}/>`;
  return null;
}

// grupy listy: przypięte na górze (filtr „rozmowy”), reszta po dniu ostatniej aktywności
function grupyListy(lista, teraz) {
  const grupy = [];
  for (const k of lista.porzadek) {
    const el = lista.wg_klucza[k], w = el.watek;
    const g = lista.filtr === "rozmowy" && w.przypiety ? "przypiete" : Czas.grupa(w.aktywnosc_at || 0, teraz);
    if (!grupy.length || grupy[grupy.length - 1].id !== g) grupy.push({ id: g, elementy: [] });
    grupy[grupy.length - 1].elementy.push({ klucz: k, ...el });
  }
  return grupy;
}

// okno widocznych wierszy długiej listy (stałe wysokości: nagłówek grupy i wiersz mierzony z pierwszego wiersza)
const OKNO_OD = 120, WYS_GRUPY = 37;
function oknoListy(plaskie, wysWiersza, gora, wysokosc, zapas = 12) {
  let y = 0, od = -1, doI = plaskie.length;
  const pozycje = plaskie.map((e) => { const p = y; y += e.grupa ? WYS_GRUPY : wysWiersza; return p; });
  for (let i = 0; i < plaskie.length; i++) {
    if (od < 0 && pozycje[i] + (plaskie[i].grupa ? WYS_GRUPY : wysWiersza) >= gora) od = i;
    if (pozycje[i] > gora + wysokosc) { doI = i; break; }
  }
  od = Math.max(0, (od < 0 ? plaskie.length : od) - zapas);
  doI = Math.min(plaskie.length, doI + zapas);
  return { od, do: doI, przed: pozycje[od] || 0, po: y - (doI < plaskie.length ? pozycje[doI] : y) };
}

// odznaka aktualizacji „⬆ N” (spec §15.1): nowa wersja, czekanie na koniec pracy, aktualizacja w toku albo kłopot
function OdznakaAktualizacji({ otworz }) {
  const a = useSklep((s) => s.aktualizacja);
  if (!a) return null;
  const trwa = a.state === "updating" || (a.pending && !["done", "stalled", "failed"].includes(a.state));
  const zle = a.state === "stalled" || a.state === "failed";
  const nowa = a.online && (a.behind || 0) > 0;
  if (!trwa && !zle && !a.po_pracy && !nowa) return null;
  const opis = trwa ? T("akt.trwa") : a.po_pracy ? T("akt.czeka", { n: (a.praca || {}).aktywne || 0 })
    : zle ? T(a.state === "stalled" ? "akt.odznaka" : "akt.nieudana") : T("akt.dostepna", { n: a.behind });
  return html`<button type="button" class=${cx("j-odznaka", "j-ma-tip", zle && "is-zle", a.po_pracy && "is-czeka")} data-odznaka="aktualizacja"
      aria-label=${`${T("akt.odznaka")}: ${opis}`} onClick=${() => otworz("system")}>
    ${trwa ? html`<${Spinner} r=${10}/>` : html`<span aria-hidden="true">⬆</span>`}${nowa && !trwa ? html`<span>${a.behind}</span>` : ""}
    <${Podpowiedz} tekst=${opis}/></button>`;
}

function StopkaPaska() {
  const wlasciciel = useSklep((s) => s.wlasciciel);
  const stan = useSklep((s) => s.strumien.stan);
  const imie = wlasciciel && wlasciciel.imie;
  const otworz = (u) => Trasa.idz({ u, pod: undefined }, { scal: true });
  // bez imienia z USER.md: ikona osoby zamiast litery „T” od „Ty”
  return html`<div class="j-stopka">
    <button type="button" class="j-ja" onClick=${() => otworz("konto")}>
      <span class="j-ja-av" aria-hidden="true">${imie ? imie.slice(0, 1).toUpperCase() : html`<${Ikona} n="user" r=${14}/>`}</span>
      <span class="j-ja-n">${imie || T("pasek.ty")}</span></button>
    <${OdznakaAktualizacji} otworz=${otworz}/>
    <button type="button" class=${cx("j-zdrowie", "j-ma-tip", `is-${stan}`)} data-stan=${stan} aria-label=${T(`polaczenie.${stan}`)}
      onClick=${() => otworz("system")}><i></i><${Podpowiedz} tekst=${T(`polaczenie.${stan}`)}/></button>
    <${Przycisk} rodzaj="cichy" ikona="gear" etykieta=${T("pasek.ustawienia")} onClick=${() => otworz("ustawienia")}/>
  </div>`;
}

function Pasek({ trasa, warstwa = false }) {
  const lista = useSklep((s) => s.lista);
  const nav = useRef(null);
  const [wiecej, setWiecej] = useState(null);       // kotwica menu „⋯” obok Szukaj (Archiwum, Kosz)
  useWarstwa(warstwa, () => sklep.zmien("pasek", { otwarty: false }), nav);
  const grupy = useMemo(() => grupyListy(lista, Date.now() / 1000), [lista.porzadek, lista.wg_klucza]);
  const [menu, setMenu] = useState(null);           // {w, kotwica}
  const [edycja, setEdycja] = useState(null);       // id wątku ze zmienianą nazwą
  const przewijana = useRef(null);
  const [okno, setOkno] = useState({ gora: 0, wys: 800, wiersz: 34 });
  const zwin = () => sklep.zmien("pasek", (p) => ({ ...p, zwiniety: !p.zwiniety, otwarty: false }));
  const ile = lista.porzadek.length;
  const dlugaLista = ile > OKNO_OD;
  const plaskie = useMemo(() => (dlugaLista ? grupy.flatMap((g) => [{ grupa: g.id }].concat(g.elementy)) : null), [grupy, dlugaLista]);
  useEffect(() => {
    const el = przewijana.current;
    if (!el || !dlugaLista) return undefined;
    let ramka = 0;
    const mierz = () => {
      cancelAnimationFrame(ramka);
      ramka = requestAnimationFrame(() => {
        const w = el.querySelector(".j-wiersz-l");
        setOkno({ gora: el.scrollTop, wys: el.clientHeight, wiersz: (w && w.offsetHeight) || 34 });
      });
    };
    mierz();
    el.addEventListener("scroll", mierz, { passive: true });
    window.addEventListener("resize", mierz);
    return () => { cancelAnimationFrame(ramka); el.removeEventListener("scroll", mierz); window.removeEventListener("resize", mierz); };
  }, [dlugaLista]);
  const filtr = lista.filtr;
  const wiersz = (el) => html`<${WierszListy} key=${el.klucz} el=${el} aktywny=${trasa.watek === el.watek.id}
    edycja=${edycja === el.watek.id} onKoniecEdycji=${() => setEdycja(null)} onMenu=${(w, kotwica) => setMenu({ w, kotwica })}/>`;
  let tresc;
  if (dlugaLista) {
    const o = oknoListy(plaskie, okno.wiersz, okno.gora, okno.wys);
    tresc = html`<div style=${{ height: `${o.przed}px` }} aria-hidden="true"></div>
      ${plaskie.slice(o.od, o.do).map((e) => (e.grupa ? html`<h3 key=${`g:${e.grupa}`} class="j-grupa-t">${T(`grupa.${e.grupa}`)}</h3>` : wiersz(e)))}
      <div style=${{ height: `${o.po}px` }} aria-hidden="true"></div>`;
  } else {
    tresc = grupy.map((g) => html`<div key=${g.id} class="j-grupa" role="group" aria-labelledby=${`j-grupa-${g.id}`}>
      <h3 class="j-grupa-t" id=${`j-grupa-${g.id}`}>${T(`grupa.${g.id}`)}</h3>${g.elementy.map(wiersz)}</div>`);
  }
  return html`<nav class="j-pasek" id="jarvo-pasek" aria-label=${T("pasek.rozmowy")} data-region="pasek" tabIndex="-1" ref=${nav}>
    <div class="j-pasek-g">
      <span class="j-marka"><${LogoJarvo}/><span>Jarvo</span></span>
      <${Przycisk} rodzaj="cichy" ikona="panel" etykieta=${T("pasek.zwin")} klasa="j-zwin" onClick=${zwin}/>
      <${Przycisk} rodzaj="cichy" ikona="x" etykieta=${T("ui.zamknij")} klasa="j-zamknij-pasek"
        onClick=${() => sklep.zmien("pasek", { otwarty: false })}/>
    </div>
    <a class="j-nowa" href="#/" data-fokus="" onClick=${() => Fokus.odloz("kompozytor")}><${Ikona} n="compose"/><span>${T("pasek.nowa")}</span></a>
    <div class="j-szukaj-w">
      <label class="j-szukaj"><${Ikona} n="search" r=${16}/>
        <input type="search" data-szukaj placeholder=${T("pasek.szukaj")} aria-label=${T("pasek.szukaj")} value=${lista.q}
          onInput=${(e) => akcje.szukaj(e.target.value)}/></label>
      <${Przycisk} rodzaj="cichy" ikona="more" etykieta=${T("pasek.wiecej_list")} klasa="j-szukaj-m" aria-haspopup="menu"
        aria-expanded=${wiecej ? "true" : "false"} onClick=${(e) => setWiecej(e.currentTarget)}/></div>
    ${wiecej && html`<${Menu} kotwica=${wiecej} etykieta=${T("pasek.wiecej_list")} onZamknij=${() => setWiecej(null)} pozycje=${[
      { id: "archiwum", ikona: "folder", tekst: T("pasek.filtr_archiwum"), akcja: () => akcje.filtrListy("archiwum") },
      { id: "kosz", ikona: "trash", tekst: T("pasek.filtr_kosz"), akcja: () => akcje.filtrListy("kosz") }]}/>`}
    ${filtr !== "rozmowy" && html`<div class="j-filtr">
      <button type="button" class="j-link" onClick=${() => akcje.filtrListy("rozmowy")}><${Ikona} n="back" r=${14}/>${T("pasek.rozmowy")}</button>
      <b>${T(`pasek.filtr_${filtr}`)}</b></div>`}
    <div class="j-lista" ref=${przewijana}>
      ${tresc}
      ${lista.blad && html`<p class="j-pasek-pusto" role="alert">${lista.blad}
        <button type="button" class="j-link" onClick=${() => akcje.wczytajListe()}>${T("ui.ponow")}</button></p>`}
      ${!lista.blad && lista.wczytana && !grupy.length
        && html`<p class="j-pasek-pusto">${T(lista.q ? "pasek.brak_wynikow" : filtr === "rozmowy" ? "pasek.pusto" : `pasek.pusto_${filtr}`)}</p>`}
      ${!lista.wczytana && !lista.blad && html`<p class="j-pasek-pusto"><${Spinner}/></p>`}
      ${lista.dalej && html`<button type="button" class="j-link j-wiecej" disabled=${lista.laduje}
        onClick=${() => akcje.wczytajListe({ dopisz: true })}>${T("pasek.wiecej")}</button>`}
    </div>
    <${StopkaPaska}/>
    ${menu && html`<${Menu} kotwica=${menu.kotwica} etykieta=${menu.w.tytul || T("watek.bez_tytulu")} onZamknij=${() => setMenu(null)}
      pozycje=${pozycjeMenuWatku(menu.w, { onZmienNazwe: () => setEdycja(menu.w.id) })}/>`}
  </nav>`;
}
