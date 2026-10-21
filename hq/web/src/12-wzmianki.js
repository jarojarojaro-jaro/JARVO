// Wzmianki: parser @uchwytów w rozmowie (bliźniak hq/plugin/wzmianki.py; serwer decyduje, tu tylko podgląd adresata).
// Te same wektory testów: tests/data/wzmianki.json (test_wzmianki.py uruchamia je w Pythonie i w node).
// Jedna nazwa na poziomie pakietu (`Wzmianki`): wszystkie pliki src/*.js dzielą jedno IIFE.

const Wzmianki = (() => {
  const ZAREZERWOWANE = new Set(["all", "everyone", "wszyscy", "here", "diff", "staged", "file", "folder", "git", "url"]);
  const KOORDYNATOR = "jarvo";
  const WIELU = 3;
  const SLOWO = /[\p{L}\p{N}_-]+/uy;
  const CALE_SLOWO = /^[\p{L}\p{N}_-]+$/u;
  const bialy = (c) => /\s/.test(c);

  // NFKD bez znaków łączących, ł→l, małe litery („Ręka” → „reka”)
  const zloz = (s) => String(s || "").normalize("NFKD").replace(/\p{M}/gu, "").replace(/ł/g, "l").replace(/Ł/g, "L").toLowerCase();

  const slowoOd = (tekst, i) => {
    SLOWO.lastIndex = i;
    const m = SLOWO.exec(tekst);
    return m ? m[0] : null;
  };
  const granicaPrzed = (t, i) => i === 0 || bialy(t[i - 1]) || t[i - 1] === ",";
  const granicaPo = (t, j) => j >= t.length || bialy(t[j]) || t[j] === "," || t[j] === ":";

  function aliasyAgenta(a) {
    const surowe = (a.aliasy && a.aliasy.length) ? a.aliasy : [a.handle || "", a.name || ""];
    return [...new Set(surowe.map(zloz).filter((x) => x && CALE_SLOWO.test(x)))];
  }

  function mapaAliasow(agenci) {
    const mapa = {};
    for (const a of agenci || []) {
      for (const alias of aliasyAgenta(a)) {
        if (!ZAREZERWOWANE.has(alias) && !(alias in mapa)) mapa[alias] = a.name;
      }
    }
    return mapa;
  }

  function nazwyAgentow(agenci) {
    return Object.fromEntries((agenci || []).map((a) => [a.name, a.nazwa || a.short || a.name]));
  }

  const nazwa = (agent, nazwy) => (nazwy && nazwy[agent]) ||
    (agent.startsWith("jarvo-") ? agent.slice(6) : agent).replace(/^./, (c) => c.toUpperCase());

  function wTresci(tresc, aliasy, pomin) {
    const wyjscie = [], srodek = [];
    let i = 0;
    for (;;) {
      const k = tresc.indexOf("@", i);
      if (k < 0) { wyjscie.push(tresc.slice(i)); break; }
      const w = slowoOd(tresc, k + 1);
      if (!w || !granicaPrzed(tresc, k) || !granicaPo(tresc, k + 1 + w.length)) {
        wyjscie.push(tresc.slice(i, k + 1));
        i = k + 1;
        continue;
      }
      const agent = Object.prototype.hasOwnProperty.call(aliasy, zloz(w)) ? aliasy[zloz(w)] : null;
      let j = k + 1 + w.length;
      wyjscie.push(tresc.slice(i, j));
      if (agent) {
        if (!pomin.has(agent) && !srodek.includes(agent)) srodek.push(agent);
        if (tresc[j] === ":" && j + 1 < tresc.length && !bialy(tresc[j + 1])) { wyjscie.push(": "); j += 1; }
      }
      i = j;
    }
    return [wyjscie.join(""), srodek];
  }

  // {adresaci, bezposrednio, tresc, wiodace, ostrzezenia}; bezstanowe: bez wiodących wzmianek = koordynator wątku
  function parsuj(tekst, aliasy, opcje) {
    const koordynator = (opcje && opcje.koordynator) || KOORDYNATOR;
    const nazwy = opcje && opcje.nazwy;
    tekst = String(tekst || "");
    const n = tekst.length;
    let i = 0;
    while (i < n && bialy(tekst[i])) i++;
    const agenci = [], ostrzezenia = [];
    let resztaOd = 0;
    while (i < n && tekst[i] === "@" && granicaPrzed(tekst, i)) {
      const w = slowoOd(tekst, i + 1);
      if (!w || !granicaPo(tekst, i + 1 + w.length)) break;
      let j = i + 1 + w.length;
      const klucz = zloz(w);
      if (ZAREZERWOWANE.has(klucz)) { ostrzezenia.push("zarezerwowane:" + w); break; }
      const agent = Object.prototype.hasOwnProperty.call(aliasy, klucz) ? aliasy[klucz] : null;
      if (!agent) { ostrzezenia.push("nieznany:" + w); break; }
      if (!agenci.includes(agent)) agenci.push(agent);
      if (j < n && tekst[j] === ":") j++;
      while (j < n && (tekst[j] === "," || bialy(tekst[j]))) j++;
      i = resztaOd = j;
    }
    const wiodace = agenci.length > 0;
    let adresaci = wiodace ? agenci : [koordynator];
    let [tresc, srodek] = wTresci((wiodace ? tekst.slice(resztaOd) : tekst).trim(), aliasy, new Set(adresaci));
    tresc = tresc.trim();
    if (!tresc) ostrzezenia.push("pusta_tresc");
    if (adresaci.includes(koordynator) && adresaci.length > 1) {
      const inni = adresaci.filter((a) => a !== koordynator);
      adresaci = [koordynator];
      if (tresc) tresc += "\n\n(Właściciel chce w tym udziału: " + inni.map((a) => nazwa(a, nazwy)).join(", ") + ".)";
      ostrzezenia.push("koordynuje:" + inni.join(","));
    }
    for (const a of srodek) if (!adresaci.includes(a)) ostrzezenia.push("srodek:" + a);
    if (adresaci.length > WIELU) ostrzezenia.push("wielu:" + adresaci.length);
    return { adresaci, bezposrednio: adresaci.filter((a) => a !== koordynator), tresc, wiodace, ostrzezenia };
  }

  return { zloz, parsuj, mapaAliasow, nazwyAgentow, aliasyAgenta, ZAREZERWOWANE, KOORDYNATOR };
})();
