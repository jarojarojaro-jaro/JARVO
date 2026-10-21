// Czas w aplikacji (czyste funkcje, testy node w tests/test_hq_front.py): czas względny, godzina, data, grupy listy
// (Dziś / Wczoraj / Ten tydzień / Wcześniej), trwanie i odliczanie. Znaczniki czasu w sekundach (jak w API).

const Czas = (() => {
  const loc = () => (typeof isPL === "function" && !isPL() ? "en-GB" : "pl-PL");
  const polnoc = (ts) => { const d = new Date(ts * 1000); d.setHours(0, 0, 0, 0); return d; };
  const teraz = () => Date.now() / 1000;

  // grupa wiersza listy: dni kalendarzowe w strefie przeglądarki, tydzień od poniedziałku
  function grupa(ts, t = teraz()) {
    const dzis = polnoc(t), d = polnoc(ts);
    const roznica = Math.round((dzis - d) / 864e5);
    if (roznica <= 0) return "dzis";
    if (roznica === 1) return "wczoraj";
    const pon = new Date(dzis);
    pon.setDate(pon.getDate() - ((pon.getDay() + 6) % 7));
    return d >= pon ? "tydzien" : "wczesniej";
  }

  function godzina(ts) {
    return ts ? new Date(ts * 1000).toLocaleTimeString(loc(), { hour: "2-digit", minute: "2-digit" }) : "";
  }

  function data(ts, t = teraz()) {
    if (!ts) return "";
    const d = new Date(ts * 1000), o = { day: "numeric", month: "short" };
    if (d.getFullYear() !== new Date(t * 1000).getFullYear()) o.year = "numeric";
    return d.toLocaleDateString(loc(), o);
  }

  // „teraz”, „5 min temu”, „2 godz. temu”, „wczoraj”, potem data
  function wzgledny(ts, t = teraz()) {
    if (!ts) return "";
    const s = Math.max(0, t - ts);
    if (s < 45) return T("czas.teraz");
    if (s < 3600) return T("czas.min", { n: Math.max(1, Math.round(s / 60)) });
    const g = grupa(ts, t);
    if (g === "dzis") return T("czas.godz", { n: Math.round(s / 3600) });
    if (g === "wczoraj") return T("czas.wczoraj");
    return data(ts, t);
  }

  // 43 → „0:43”, 3725 → „1:02:05”
  function trwanie(sekundy) {
    const s = Math.max(0, Math.floor(sekundy || 0)), h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
    const ss = String(s % 60).padStart(2, "0");
    return h ? `${h}:${String(m).padStart(2, "0")}:${ss}` : `${m}:${ss}`;
  }

  // ile zostało do `do_ts` (zgoda wygasa): {zostalo: sekundy ≥ 0, tekst: „m:ss”, minelo}
  function odliczanie(doTs, t = teraz()) {
    const zostalo = Math.max(0, Math.ceil((doTs || 0) - t));
    return { zostalo, tekst: trwanie(zostalo), minelo: zostalo === 0 };
  }

  return { grupa, godzina, data, wzgledny, trwanie, odliczanie };
})();
