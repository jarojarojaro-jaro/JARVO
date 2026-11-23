// Motyw aplikacji (docs/HQ.md „Aplikacja”): wybór jasny / ciemny / system; na korzeniu `data-motyw` ma zawsze wynik
// (jasny albo ciemny), a tokeny kolorów (--j-*, oba motywy, kontrast sprawdza tests/test_hq_front.py) są w style.css.
// Do tego widok na telefonie: iOS Safari nie zmniejsza strony pod klawiaturą, więc wysokość (--j-vh) i górę (--j-vtop)
// aplikacji liczymy z visualViewport (kompozytor zostaje nad klawiaturą, góra przy górze ekranu).

const Motyw = {
  WYBORY: ["ciemny", "jasny", "system"],   // TARS: ciemny pierwszy (domyślny), jasny = ten sam monolit w świetle dnia
  rozwiaz: (wybor, systemCiemny) => (wybor === "jasny" || wybor === "ciemny" ? wybor : systemCiemny ? "ciemny" : "jasny"),
};

function useMotyw(wybor) {
  const mq = useMemo(() => (window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null), []);
  const ciemny = React.useSyncExternalStore((f) => {
    if (!mq) return () => {};
    mq.addEventListener("change", f);
    return () => mq.removeEventListener("change", f);
  }, () => !!(mq && mq.matches));
  return Motyw.rozwiaz(wybor, ciemny);
}

// zmienne na <html>, nie na korzeniu: korzeń aplikacji montuje się na nowo (ekran poznania, rozmowy), a wartości dziedziczy
function useWidokTelefonu() {
  useEffect(() => {
    const vv = window.visualViewport, el = document.documentElement;
    if (!vv) return undefined;
    let ramka = 0;
    // iPhone z klawiaturą przesuwa widoczny obszar (offsetTop > 0) nad przypiętą aplikacją: bez `--j-vtop` jej góra
    // zostawała nad ekranem, a widać było dół i pustkę (23.11 właściciel: „klikam pole i pokazuje blank ekran”)
    const licz = () => {
      cancelAnimationFrame(ramka);
      ramka = requestAnimationFrame(() => {
        el.style.setProperty("--j-vh", `${Math.round(vv.height)}px`);
        el.style.setProperty("--j-vtop", `${Math.max(0, Math.round(vv.offsetTop))}px`);
      });
    };
    licz();
    vv.addEventListener("resize", licz);
    vv.addEventListener("scroll", licz);
    return () => { cancelAnimationFrame(ramka); vv.removeEventListener("resize", licz); vv.removeEventListener("scroll", licz); };
  }, []);
}

function useMedia(q) {
  const get = () => typeof window !== "undefined" && window.matchMedia && window.matchMedia(q).matches;
  const [m, setM] = useState(get);
  useEffect(() => {
    if (!window.matchMedia) return undefined;
    const mq = window.matchMedia(q);
    const on = () => setM(mq.matches);
    mq.addEventListener ? mq.addEventListener("change", on) : mq.addListener(on);
    return () => (mq.removeEventListener ? mq.removeEventListener("change", on) : mq.removeListener(on));
  }, [q]);
  return m;
}

// pasek boczny wysuwany (poniżej 1024 px, jak w style.css)
const useWaskiEkran = () => useMedia("(max-width: 1023.98px)");
// telefon (< 640 px, centrum §2.2): lista rozmówców jako pierwszy ekran, rozmowa z „←” i paskiem rozmówców na dole
const useTelefon = () => useMedia("(max-width: 639.98px)");

// ruch: „gładko” tylko, gdy system nie prosi o ograniczenie animacji
const Ruch = { zachowanie: () => (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth") };
