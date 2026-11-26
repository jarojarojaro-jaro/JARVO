// Pasek boczny (docs/HQ.md „Aplikacja”, makieta V2 · Spokojny): marka, Nowa rozmowa, Szukaj, lista wątków
// w grupach (Przypięte, Dziś, Wczoraj, Ten tydzień, Wcześniej), Archiwum i Kosz pod „⋯” obok Szukaj, nawigacja
// (Aktualizacje, Mózg, Ustawienia), stopka (odznaka aktualizacji, stan połączenia słowem). Wiersz: ikona źródła, tytuł w jednej linii, znak stanu (● czeka na Ciebie, ◌ pracuje, ⚠ błąd) z tekstem
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

// ------------------------------------------------------------------------------------------------- rozmówcy
// Sekcja ROZMÓWCY (centrum §1, §2.1): stała kolejność z konfiguracji, wiersz = znak agenta z kwadratem stanu, nazwa,
// skrót ⌘1–⌘4 albo licznik nieprzeczytanych i linia „ETYKIETA STANU podgląd” (kwadrat i słowo: czytnik ekranu,
// daltonizm). Lista to role=listbox: strzałki, Home/End, Enter; jeden wiersz w kolejności Tab (aktywny albo pierwszy).
const STANY_ROZMOWCY = new Set(["pracuje", "czeka", "wolny", "terminal", "kolejka", "offline"]);
const nazwaRozmowcy = (r) => (r ? (!isPL() && r.nazwa_en) || r.nazwa || r.klucz : "");
const agentRozmowcy = (r) => (r.zaplecze === "omp" ? r.klucz : r.cel);
// wolny rozmówca z nieprzeczytaną odpowiedzią = „odpowiedź” (26.11 właściciel: ma być widać, że odpowiedź czeka)
const stanRozmowcy = (r) => {
  const st = STANY_ROZMOWCY.has(r && r.stan) ? r.stan : "offline";
  return st === "wolny" && (r.nieprzeczytane || 0) > 0 ? "odpowiedz" : st;
};
function slowoStanu(r) {
  const st = stanRozmowcy(r);
  return st === "kolejka" ? T("rozm.kolejka", { n: Math.max(1, r.czeka || 0) }) : T(`rozm.${st}`);
}
// stan jako etykieta TARS (mono, wersaliki, kolor = stan: czerwień pracuje, bursztyn czeka) i reszta linijki
// (podgląd ostatniej wiadomości, czekające w terminalu, powód niedostępności)
function LiniaStanu({ r, podglad = true }) {
  const st = stanRozmowcy(r);
  const cz = [];
  if (st === "terminal" && r.czeka > 0) cz.push(T("rozm.czeka_n", { n: r.czeka }));
  if (st === "offline" && r.powod) cz.push(r.powod);
  else if (podglad && r.podglad) cz.push(r.podglad);
  return html`<em class=${`j-st is-${st}`}>${slowoStanu(r)}</em>${cz.length > 0 && html`<span>${cz.join(" · ")}</span>`}`;
}

function AwatarRozmowcy({ r, rozmiar = 34 }) {
  const a = useSklep((s) => s.agenci[agentRozmowcy(r)]);
  return html`<span class="j-rozm-av"><${Awatar} agent=${{ nazwa: r.nazwa, ...(a || { name: agentRozmowcy(r) }) }} r=${rozmiar}/>
    <i class=${`j-rk is-${stanRozmowcy(r)}`} aria-hidden="true"></i></span>`;
}

const otworzRozmowce = (r, fokus = true) => {
  if (fokus) Fokus.odloz("kompozytor");
  Trasa.idz({ widok: "rozmowca", rozmowca: r.klucz });
};

function ListaRozmowcow({ trasa }) {
  const rozmowcy = useSklep((s) => s.rozmowcy);
  const ref = useRef(null);
  if (!rozmowcy.length) return null;
  const aktywny = rozmowcy.findIndex((r) => r.klucz === trasa.rozmowca);
  const wTabie = aktywny < 0 ? 0 : aktywny;
  const klawisz = (e) => {
    const el = [...ref.current.querySelectorAll('[role="option"]')];
    const i = el.indexOf(document.activeElement);
    let j = null;
    if (e.key === "ArrowDown") j = Math.min(el.length - 1, i + 1);
    else if (e.key === "ArrowUp") j = Math.max(0, i - 1);
    else if (e.key === "Home") j = 0;
    else if (e.key === "End") j = el.length - 1;
    else if ((e.key === "Enter" || e.key === " ") && i >= 0) { e.preventDefault(); otworzRozmowce(rozmowcy[i]); return; }
    if (j == null) return;
    e.preventDefault();
    el[j].focus();
  };
  return html`<ul class="j-rozmowcy" role="listbox" aria-label=${T("rozm.sekcja")} ref=${ref} onKeyDown=${klawisz}>
    ${rozmowcy.map((r, i) => {
      const st = stanRozmowcy(r), n = r.nieprzeczytane || 0;
      const opis = [nazwaRozmowcy(r), slowoStanu(r), n > 0 ? T("watek.nieprzeczytane", { n }) : ""].filter(Boolean).join(", ");
      return html`<li key=${r.klucz} role="option" class=${cx("j-rozm", i === aktywny && "is-aktywny", `is-${st}`)}
          aria-selected=${String(i === aktywny)} tabIndex=${i === wTabie ? "0" : "-1"} aria-label=${opis}
          data-rozmowca=${r.klucz} onClick=${() => otworzRozmowce(r)}>
        <${AwatarRozmowcy} r=${r} rozmiar=${34}/>
        <span class="j-rozm-n">${nazwaRozmowcy(r)}</span>
        ${n > 0 ? html`<span class="j-rozm-licz" aria-hidden="true">${n > 99 ? "99+" : n}</span>`
          : i < 4 ? html`<kbd class="j-rozm-skrot" aria-hidden="true">${Skroty.opis(`Mod+${i + 1}`)}</kbd>` : html`<span></span>`}
        <span class="j-rozm-st" aria-hidden="true"><${LiniaStanu} r=${r}/></span>
      </li>`;
    })}
  </ul>`;
}

// Aktualizacje (raporty rutyn z licznikiem nieprzeczytanych) na górze, pod „+ Nowa rozmowa” (19.11 właściciel:
// „Aktualizacje ma być na górze”); Mózg i Ustawienia pod rozmówcami (⌘M, ⌘,). Telefon (23.11 właściciel: „miały być
// wciśnięte w lewy dolny róg”): Aktualizacje razem z Mózgiem i Ustawieniami na dole paska, góra ich nie pokazuje
function PozycjaAktualizacji({ trasa, klasa }) {
  const n = useSklep((s) => s.raporty.nieprzeczytane);
  const tu = trasa.widok === "aktualizacje";
  return html`<li class=${klasa}><a href=${Trasa.zbuduj({ widok: "aktualizacje" })} aria-current=${tu ? "page" : undefined}
      class=${cx(tu && "is-aktywny")} data-nawig="aktualizacje"
      aria-label=${n > 0 ? `${T("rap.tytul")}, ${T("rap.nowe", { n })}` : undefined}>
    <${Ikona} n=${IKONY_WIDOKOW.aktualizacje} r=${16} klasa="j-nawig-i"/><span class="j-nawig-t">${T("rap.tytul")}</span>
    ${n > 0 && html`<span class="j-rozm-licz" aria-hidden="true">${n > 99 ? "99+" : n}</span>`}</a></li>`;
}

function NawigacjaCentrum({ trasa }) {
  const poz = [["mozg", T("rozm.mozg"), "Mod+M"], ["ustawienia", T("pasek.ustawienia"), "Mod+,"]];
  return html`<ul class="j-nawig is-dol"><${PozycjaAktualizacji} trasa=${trasa} klasa="j-tylko-telefon"/>
    ${poz.map(([w, tekst, komb]) => html`<li key=${w}>
    <a href=${Trasa.zbuduj({ widok: w })} aria-current=${trasa.widok === w ? "page" : undefined} class=${cx(trasa.widok === w && "is-aktywny")}>
      <${Ikona} n=${IKONY_WIDOKOW[w]} r=${16} klasa="j-nawig-i"/><span class="j-nawig-t">${tekst}</span>
      <kbd class="j-rozm-skrot" aria-hidden="true">${Skroty.opis(komb)}</kbd></a></li>`)}</ul>`;
}

// „+ Nowa rozmowa” na samej górze (nad rozmówcami, ⌘⇧O): otwiera start z kompozytorem i wyborem „Do:” (domyślnie Jarvo)
function NowaRozmowa({ fokus = false }) {
  return html`<a class="j-nowa" href="#/nowa" data-nowa data-fokus=${fokus ? "" : undefined}
      aria-keyshortcuts="Meta+Shift+O Control+Shift+O" onClick=${() => Fokus.odloz("kompozytor")}>
    <span class="j-nowa-plus" aria-hidden="true">+</span><span class="j-nowa-t">${T("pasek.nowa")}</span>
    <kbd class="j-nowa-skrot" aria-hidden="true">${Skroty.opis("Mod+Shift+O")}</kbd></a>`;
}

// pasek 4 rozmówców na dole rozmowy (telefon): figurka z kropką stanu i nazwa
function DokRozmowcow({ trasa }) {
  const rozmowcy = useSklep((s) => s.rozmowcy);
  if (!rozmowcy.length) return null;
  return html`<nav class="j-dok-rozm" aria-label=${T("rozm.sekcja")}>${rozmowcy.slice(0, 5).map((r) => html`<a key=${r.klucz}
      href=${Trasa.zbuduj({ widok: "rozmowca", rozmowca: r.klucz })} aria-current=${trasa.rozmowca === r.klucz ? "page" : undefined}
      aria-label=${`${nazwaRozmowcy(r)}, ${slowoStanu(r)}`} class=${cx(trasa.rozmowca === r.klucz && "is-aktywny")}>
    <${AwatarRozmowcy} r=${r} rozmiar=${28}/><span>${nazwaRozmowcy(r)}</span>
    ${r.nieprzeczytane > 0 && html`<b class="j-rozm-licz" aria-hidden="true">${r.nieprzeczytane}</b>`}</a>`)}</nav>`;
}

// Powiadomienia przeglądarki (centrum D9): „czeka na Ciebie” od razu, kolejka po 2 min (serwer: `powiadom`) i koniec
// pracy dłuższej niż 2 min. Tylko karta lidera strumienia (jedno powiadomienie na przeglądarkę), tylko gdy właściciel
// nie patrzy na tę rozmowę; klik otwiera rozmówcę.
function usePowiadomieniaRozmowcow() {
  useEffect(() => Strumien.naZdarzenie("rozmowca.stan", (d) => {
    const s = sklep.stan();
    // poprzedni stan z poprzedniego zdarzenia (sklep ma już nowy: reduktor działa przed hakami)
    const byl = STANY_POWIADOMIEN[d.klucz] || null;
    STANY_POWIADOMIEN[d.klucz] = { stan: d.stan, od: d.stan_od };
    const poprzedni = byl && byl.stan, od = byl && byl.od;
    const r = s.rozmowcy.find((x) => x.klucz === d.klucz);
    if (!r || !s.ustawienia.powiadomienia || !window.Notification || Notification.permission !== "granted" || !Strumien.jestLiderem()) return;
    const patrzy = document.visibilityState === "visible" && Trasa.biezaca().rozmowca === d.klucz;
    let tekst = null;
    if (d.stan === "czeka" && poprzedni !== "czeka") tekst = T("rozm.powiadom_czeka");
    else if (d.powiadom) tekst = T("rozm.powiadom_kolejka", { n: Math.max(1, d.czeka || 0) });
    else if (poprzedni === "pracuje" && d.stan === "wolny" && od && Date.now() / 1000 - od > 120) tekst = T("rozm.powiadom_koniec");
    if (!tekst || patrzy) return;
    try {
      const n = new Notification(`${nazwaRozmowcy(r)} · Jarvo`, { body: tekst, tag: `jarvo-${d.klucz}` });
      n.onclick = () => { window.focus(); otworzRozmowce(r, false); n.close(); };
    } catch (_) { /* przeglądarka bez powiadomień w tym kontekście */ }
  }), []);
}
const STANY_POWIADOMIEN = {};

// Stan połączenia słowem (stopka paska, ekran rozmówców na telefonie): cichy „● połączono”, a bez połączenia
// ostrzeżenie (⚠ Łączę ponownie…); tylko informacja, nie przycisk
function StanPolaczenia({ klasa }) {
  const stan = useSklep((s) => s.strumien.stan);
  const ok = stan === "ok";
  return html`<p class=${cx("j-zdrowie", `is-${stan}`, klasa)} data-stan=${stan} role="status">
    <i aria-hidden="true">${ok ? "" : "⚠"}</i><span>${ok ? T("polaczenie.krotko") : T(`polaczenie.${stan}`)}</span></p>`;
}

// Stopka paska: bez drugiego wejścia do Ustawień (jest pozycja „Ustawienia” w nawigacji, ⌘,), stan połączenia
// i odznaka aktualizacji (22.11 właściciel: bez mierników „szczerość, humor”, ma być profesjonalnie)
function StopkaPaska() {
  return html`<div class="j-stopka">
    <${StanPolaczenia}/>
    <${OdznakaAktualizacji} otworz=${(sekcja) => Trasa.idz({ widok: "ustawienia", sekcja })}/>
  </div>`;
}

function Pasek({ trasa, warstwa = false }) {
  const lista = useSklep((s) => s.lista);
  const saRozmowcy = useSklep((s) => s.rozmowcy.length > 0);
  const inneOtwarte = useSklep((s) => s.inne_otwarte);
  const inne = !saRozmowcy || inneOtwarte || lista.filtr !== "rozmowy" || !!lista.q;
  const nav = useRef(null);
  const [wiecej, setWiecej] = useState(null);       // kotwica menu „⋯” obok Szukaj (Archiwum, Kosz)
  useWarstwa(warstwa, () => sklep.zmien("pasek", { otwarty: false }), nav);
  const grupy = useMemo(() => grupyListy(lista, Date.now() / 1000), [lista.porzadek, lista.wg_klucza]);
  const [menu, setMenu] = useState(null);           // {w, kotwica}
  const [edycja, setEdycja] = useState(null);       // id wątku ze zmienianą nazwą
  const przewijana = useRef(null), listaEl = useRef(null);
  const [okno, setOkno] = useState({ gora: 0, wys: 800, wiersz: 34 });
  const zwin = () => sklep.zmien("pasek", (p) => ({ ...p, zwiniety: !p.zwiniety, otwarty: false }));
  const ile = lista.porzadek.length;
  const dlugaLista = ile > OKNO_OD;
  const plaskie = useMemo(() => (dlugaLista ? grupy.flatMap((g) => [{ grupa: g.id }].concat(g.elementy)) : null), [grupy, dlugaLista]);
  // przewija się środek paska (rozmówcy i Inne rozmowy razem); okno długiej listy liczone od jej początku w środku
  useEffect(() => {
    const el = przewijana.current;
    if (!el || !dlugaLista || !inne) return undefined;
    let ramka = 0;
    const mierz = () => {
      cancelAnimationFrame(ramka);
      ramka = requestAnimationFrame(() => {
        const w = el.querySelector(".j-wiersz-l"), l = listaEl.current;
        const od = l ? l.getBoundingClientRect().top - el.getBoundingClientRect().top + el.scrollTop : 0;
        setOkno({ gora: Math.max(0, el.scrollTop - od), wys: el.clientHeight, wiersz: (w && w.offsetHeight) || 34 });
      });
    };
    mierz();
    el.addEventListener("scroll", mierz, { passive: true });
    window.addEventListener("resize", mierz);
    return () => { cancelAnimationFrame(ramka); el.removeEventListener("scroll", mierz); window.removeEventListener("resize", mierz); };
  }, [dlugaLista, inne]);
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
  // układ: góra stała (marka, Nowa rozmowa, Aktualizacje), środek przewijany (Rozmówcy, pod nimi Inne rozmowy
  // z wyszukiwarką i listą), dół przypięty do rogu (Mózg, Ustawienia, stan połączenia). Telefon: nowa rozmowa to ikona
  // w belce paska, Aktualizacje na dole z Mózgiem i Ustawieniami
  return html`<nav class="j-pasek" id="jarvo-pasek" aria-label=${T("pasek.rozmowy")} data-region="pasek" tabIndex="-1" ref=${nav}>
    <div class="j-pasek-g">
      <span class="j-marka"><${LogoJarvo}/><span>Jarvo</span></span>
      <${Przycisk} rodzaj="cichy" ikona="compose" etykieta=${T("pasek.nowa")} klasa="j-pisz"
        onClick=${() => { Fokus.odloz("kompozytor"); Trasa.idz({ widok: "nowa" }); }}/>
      <${Przycisk} rodzaj="cichy" ikona="panel" etykieta=${T("pasek.zwin")} klasa="j-zwin" onClick=${zwin}/>
      <${Przycisk} rodzaj="cichy" ikona="x" etykieta=${T("ui.zamknij")} klasa="j-zamknij-pasek"
        onClick=${() => sklep.zmien("pasek", { otwarty: false })}/>
    </div>
    <${NowaRozmowa} fokus=${!saRozmowcy}/>
    <ul class="j-nawig is-gora"><${PozycjaAktualizacji} trasa=${trasa}/></ul>
    <div class="j-pasek-s" ref=${przewijana}>
    ${saRozmowcy && html`<div class="j-pasek-rozm">
      <h2 class="j-sekcja" id="j-sekcja-rozm">${T("rozm.sekcja_t")}</h2>
      <${ListaRozmowcow} trasa=${trasa}/>
      <button type="button" class="j-inne" aria-expanded=${String(inne)} aria-controls="j-inne-l"
        onClick=${() => sklep.ustaw((s) => ({ ...s, inne_otwarte: !inne }))}>
        <span>${T("rozm.inne")}</span><span aria-hidden="true">${inne ? "▾" : "▸"}</span>
        ${!inne && lista.porzadek.length > 0 && html`<small>${lista.porzadek.length}</small>`}</button></div>`}
    ${inne && html`<div class=${cx("j-inne-l", saRozmowcy && "is-pod-rozm")} id="j-inne-l">
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
    <div class="j-lista" ref=${listaEl}>
      ${tresc}
      ${lista.blad && html`<p class="j-pasek-pusto" role="alert">${lista.blad}
        <button type="button" class="j-link" onClick=${() => akcje.wczytajListe()}>${T("ui.ponow")}</button></p>`}
      ${!lista.blad && lista.wczytana && !grupy.length
        && html`<p class="j-pasek-pusto">${T(lista.q ? "pasek.brak_wynikow" : filtr === "rozmowy" ? "pasek.pusto" : `pasek.pusto_${filtr}`)}</p>`}
      ${!lista.wczytana && !lista.blad && html`<p class="j-pasek-pusto"><${Spinner}/></p>`}
      ${lista.dalej && html`<button type="button" class="j-link j-wiecej" disabled=${lista.laduje}
        onClick=${() => akcje.wczytajListe({ dopisz: true })}>${T("pasek.wiecej")}</button>`}
    </div>
    </div>`}
    </div>
    <${NawigacjaCentrum} trasa=${trasa}/>
    <${StopkaPaska}/>
    ${menu && html`<${Menu} kotwica=${menu.kotwica} etykieta=${menu.w.tytul || T("watek.bez_tytulu")} onZamknij=${() => setMenu(null)}
      pozycje=${pozycjeMenuWatku(menu.w, { onZmienNazwe: () => setEdycja(menu.w.id) })}/>`}
  </nav>`;
}
