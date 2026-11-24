// Podgląd na żywo (docs/HQ.md „Podgląd na żywo”), część rdzenia: urządzenie z kroku agenta (narzędzia telefonów
// PhoneUse z argumentem `phone`, computer_use i komputer), przycisk „Telefon second · Podgląd na żywo” w pasku pracy
// i w kroku rozmowy, stan okna i jego miejsce w korzeniu aplikacji. Samo okno (WebSocket, dekoder H.264, stany) jest
// w pakiecie na żądanie „podglad” (42-podglad.js), wczytywanym przy pierwszym otwarciu.
const NaZywo = (() => {
  const TELEFON = /^mcp__phone__?(act|batch|screen|shot|ping|wait)$/;
  const KOMPUTER = new Set(["computer_use", "komputer"]);
  const liczba = (v) => typeof v === "number" && isFinite(v);
  // krok → { rodzaj: "telefon"|"komputer", u: nazwa telefonu albo "komputer" (null: telefon bez argumentu phone),
  // punkt: {x, y} (stuknięcie albo kliknięcie, gdy jest), cmd } albo null dla innych narzędzi i komentarzy
  function urzadzenie(k) {
    if (!k || k.komentarz != null) return null;
    const n = k.narzedzie || "", a = k.args || {};
    const punkt = liczba(a.x) && liczba(a.y) ? { x: a.x, y: a.y } : null;
    const cmd = typeof a.cmd === "string" ? a.cmd : null;
    if (TELEFON.test(n)) return { rodzaj: "telefon", u: typeof a.phone === "string" && a.phone ? a.phone : null, punkt, cmd };
    if (KOMPUTER.has(n)) return { rodzaj: "komputer", u: "komputer", punkt, cmd };
    return null;
  }
  // bieżące urządzenie agentów: ostatni krok narzędzia każdego pracującego przebiegu, najnowszy wygrywa
  function teraz(przebiegi) {
    let wynik = null;
    for (const p of przebiegi || []) {
      if (p.stan !== "pracuje") continue;
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

const nazwaUrzadzenia = (u) => (u === "komputer" ? T("podglad.komputer") : u ? T("podglad.telefon_n", { n: u }) : T("podglad.telefon"));

function PrzyciskNaZywo({ urz }) {
  if (!urz) return null;
  return html`<button type="button" class="j-na-zywo" data-urzadzenie=${urz.u || "telefon"}
    onClick=${(e) => { e.stopPropagation(); NaZywo.otworz(urz.u); }}><span class="j-na-zywo-k" aria-hidden="true"></span>
    ${nazwaUrzadzenia(urz.u)} · ${T("podglad.na_zywo")}</button>`;
}

// okno w korzeniu aplikacji; „Otwieraj podgląd sam” (Ustawienia › Powiadomienia) otwiera je przy nowym przebiegu,
// który pracuje na urządzeniu (zamknięte ręcznie nie wraca w tym samym przebiegu)
function NaZywoOkno() {
  const s = useNaZywo();
  const biezacy = useSklep((x) => NaZywo.teraz(Object.values(x.przebiegi || {})), NaZywo.rowne);
  const sam = useSklep((x) => !!(x.ustawienia && x.ustawienia.podglad_sam));
  const otwartyDla = useRef(null);
  useEffect(() => {
    if (!sam || !biezacy || s.otwarte || otwartyDla.current === biezacy.pid) return;
    otwartyDla.current = biezacy.pid;
    NaZywo.otworz(biezacy.u);
  }, [sam, biezacy, s.otwarte]);
  if (!s.otwarte) return null;
  return html`<${Leniwy} pakiet="podglad" nazwa="PodgladOkno" stan=${s} biezacy=${biezacy}/>`;
}
