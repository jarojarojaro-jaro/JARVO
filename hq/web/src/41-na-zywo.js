// Podgląd na żywo (docs/HQ.md „Podgląd na żywo”), część rdzenia: urządzenie z kroku agenta (narzędzia telefonów
// PhoneUse z argumentem `phone`, computer_use i komputer, pulpit), przycisk „Telefon second · Podgląd na żywo” w pasku
// pracy i w kroku rozmowy, stan okna i jego miejsce w korzeniu aplikacji. Samo okno (WebSocket, dekoder H.264, stany,
// dziennik działań, „Przejmij”) jest w pakiecie na żądanie „podglad” (42-podglad.js), wczytywanym przy pierwszym otwarciu.
const NaZywo = (() => {
  const TELEFON = /^mcp__phone__?(act|batch|screen|shot|ping|wait)$/;
  const KOMPUTER = new Set(["computer_use", "komputer"]);
  const liczba = (v) => typeof v === "number" && isFinite(v);
  // krok → { rodzaj: "telefon"|"komputer"|"pulpit", u: nazwa telefonu, "komputer" albo "pulpit" (null: telefon bez
  // argumentu phone), punkt: {x, y} (stuknięcie albo kliknięcie, gdy jest), cmd } albo null dla innych narzędzi
  function urzadzenie(k) {
    if (!k || k.komentarz != null) return null;
    const n = k.narzedzie || "", a = k.args || {};
    const punkt = liczba(a.x) && liczba(a.y) ? { x: a.x, y: a.y } : null;
    const cmd = typeof a.cmd === "string" ? a.cmd : null;
    if (TELEFON.test(n)) return { rodzaj: "telefon", u: typeof a.phone === "string" && a.phone ? a.phone : null, punkt, cmd };
    if (KOMPUTER.has(n)) return { rodzaj: "komputer", u: "komputer", punkt, cmd };
    if (n === "pulpit") return { rodzaj: "pulpit", u: "pulpit", punkt, cmd };
    return null;
  }
  // bieżące urządzenie agentów otwartej rozmowy `wid`: ostatni krok narzędzia każdego jej pracującego przebiegu,
  // najnowszy wygrywa
  function teraz(przebiegi, wid) {
    let wynik = null;
    for (const p of przebiegi || []) {
      if (p.stan !== "pracuje" || p.watek_id !== wid) continue;
      const kroki = p.kroki || [];
      let i = kroki.length - 1;
      while (i >= 0 && kroki[i].komentarz != null) i--;
      const u = i >= 0 ? urzadzenie(kroki[i]) : null;
      if (u && (!wynik || (kroki[i].ts || 0) > (wynik.krok.ts || 0))) wynik = { ...u, krok: kroki[i], agent: p.agent, pid: p.id };
    }
    return wynik;
  }
  const rowne = (a, b) => a === b || !!(a && b && a.pid === b.pid && a.u === b.u && a.krok.ts === b.krok.ts && a.krok.narzedzie === b.krok.narzedzie);
  let stan = { otwarte: false, u: null };
  const sluchacze = new Set();
  const ustaw = (z) => { stan = { ...stan, ...z }; sluchacze.forEach((f) => f(stan)); };
  return {
    urzadzenie, teraz, rowne, stan: () => stan, ustaw,
    // wątek rozmowy na ekranie: z trasy rozmowy albo rozmówcy (lewa kolumna), null poza rozmową
    watekTrasy: (s, t) => t.watek || (t.rozmowca && ((s.rozmowcy || []).find((r) => r.klucz === t.rozmowca) || {}).watek_id) || null,
    // ostatnie urządzenie w krokach przebiegu: przycisk stoi w pasku od pierwszego kroku na urządzeniu, nie skacze
    ostatnie: (kroki) => { for (let i = (kroki || []).length - 1; i >= 0; i--) { const u = urzadzenie(kroki[i]); if (u) return u; } return null; },
    sluchaj: (f) => { sluchacze.add(f); return () => sluchacze.delete(f); },
    otworz: (u) => ustaw({ otwarte: true, u: u || null, od: Date.now() }),
    zamknij: () => ustaw({ otwarte: false }),
  };
})();

function useNaZywo() {
  const [s, setS] = useState(NaZywo.stan);
  useEffect(() => NaZywo.sluchaj(setS), []);
  return s;
}

const nazwaUrzadzenia = (u) => (u === "komputer" ? T("podglad.komputer") : u === "pulpit" ? T("podglad.pulpit")
  : u ? T("podglad.telefon_n", { n: u }) : T("podglad.telefon"));
const ikonaUrzadzenia = (u) => (u === "komputer" ? "globe" : u === "pulpit" ? "monitor" : "phone");

// jeden stały przycisk (pasek pracy, pasek podagentów): ikona urządzenia, „Na żywo” i nazwa; drugi klik zamyka okno
function PrzyciskNaZywo({ urz }) {
  const s = useNaZywo();
  if (!urz) return null;
  const opis = `${nazwaUrzadzenia(urz.u)} · ${T("podglad.na_zywo")}`;
  return html`<button type="button" class="j-na-zywo" aria-pressed=${String(s.otwarte)} title=${opis} aria-label=${opis}
    onClick=${(e) => { e.stopPropagation(); if (s.otwarte) NaZywo.zamknij(); else NaZywo.otworz(urz.u); }}>
    <${Ikona} n=${ikonaUrzadzenia(urz.u)} r=${15}/><span class="j-na-zywo-t">${L("Na żywo", "Live")}</span>
    ${urz.rodzaj === "telefon" && urz.u && html`<span class="j-na-zywo-u">${urz.u}</span>`}<span class="j-na-zywo-k" aria-hidden="true"></span></button>`;
}

// okno w korzeniu aplikacji, zawsze dla otwartej rozmowy: zmiana rozmowy zamyka je (24.11 właściciel: podgląd
// telefonu z rozmowy Jarva został w rozmowie Kernela); „Otwieraj podgląd sam” (Ustawienia › Powiadomienia) otwiera
// je przy nowym przebiegu tej rozmowy, który pracuje na urządzeniu (zamknięte ręcznie nie wraca w tym samym przebiegu)
function NaZywoOkno() {
  const s = useNaZywo();
  const trasa = useTrasa();
  const wid = useSklep((x) => NaZywo.watekTrasy(x, trasa));
  const biezacy = useSklep((x) => NaZywo.teraz(Object.values(x.przebiegi || {}), wid), NaZywo.rowne);
  const sam = useSklep((x) => !!(x.ustawienia && x.ustawienia.podglad_sam));
  const otwartyDla = useRef(null);
  const bylWid = useRef(wid);
  useEffect(() => {
    if (bylWid.current !== wid) { bylWid.current = wid; NaZywo.zamknij(); }
  }, [wid]);
  useEffect(() => {
    if (!sam || !biezacy || s.otwarte || otwartyDla.current === biezacy.pid) return;
    otwartyDla.current = biezacy.pid;
    NaZywo.otworz(biezacy.u);
  }, [sam, biezacy, s.otwarte]);
  if (!s.otwarte) return null;
  return html`<${Leniwy} pakiet="podglad" nazwa="PodgladOkno" stan=${s} biezacy=${biezacy} wid=${wid}/>`;
}
