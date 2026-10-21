// Motyw aplikacji (docs/HQ.md „Aplikacja”): wybór jasny / ciemny / system; na korzeniu `data-motyw` ma zawsze wynik
// (jasny albo ciemny), a tokeny kolorów (--j-*, oba motywy, kontrast sprawdza tests/test_hq_front.py) są w style.css.
// Do tego wysokość widoku na telefonie: iOS Safari nie zmniejsza strony pod klawiaturą, więc --j-vh i --j-klawiatura
// liczymy z visualViewport (kompozytor zostaje nad klawiaturą).

const Motyw = {
  WYBORY: ["system", "jasny", "ciemny"],
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

function useWidokTelefonu(ref) {
  useEffect(() => {
    const vv = window.visualViewport, el = ref.current;
    if (!vv || !el) return undefined;
    let ramka = 0;
    const licz = () => {
      cancelAnimationFrame(ramka);
      ramka = requestAnimationFrame(() => {
        el.style.setProperty("--j-vh", `${Math.round(vv.height)}px`);
        el.style.setProperty("--j-klawiatura", `${Math.max(0, Math.round(window.innerHeight - vv.height - vv.offsetTop))}px`);
      });
    };
    licz();
    vv.addEventListener("resize", licz);
    vv.addEventListener("scroll", licz);
    return () => { cancelAnimationFrame(ramka); vv.removeEventListener("resize", licz); vv.removeEventListener("scroll", licz); };
  }, []);
}

// pasek boczny wysuwany (poniżej 1024 px, jak w style.css)
const useWaskiEkran = () => useMedia("(max-width: 1023.98px)");

// ruch: „gładko” tylko, gdy system nie prosi o ograniczenie animacji
const Ruch = { zachowanie: () => (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth") };
