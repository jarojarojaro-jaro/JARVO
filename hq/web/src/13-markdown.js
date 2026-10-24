// Bezpieczny Markdown aplikacji (docs/HQ.md „Aplikacja”, spec §13.7). Czysty tokenizer Md.parsuj(tekst) → bloki
// (akapit, nagłówek 1–4, lista do 3 poziomów z zadaniami [ ]/[x], cytat, blok kodu, tabela GFM, linia, pliki MEDIA:/📎)
// i Md.inline(tekst) → węzły (pogrubienie, kursywa, przekreślenie, `kod`, [link](url), gołe adresy, ścieżki floty,
// obrazy data:image). Renderer tylko przez React (html`` = React.createElement): bez wstawiania HTML-a, surowy HTML ze źródła
// zostaje tekstem. Linki tylko http(s), mailto i #/ (reszta jako zwykły tekst), obrazy tylko data:image (png, jpeg,
// gif, webp) i pliki floty. Bez wyrażeń z zagnieżdżonymi kwantyfikatorami: szukanie domknięć idzie z pamięcią
// ostatniego trafienia (pozycje rosną), więc czas jest liniowy także dla złośliwego wejścia (test: 100 KB < 50 ms).

const Md = (() => {
  const MAKS = 200 * 1024;                       // dłuższa wiadomość: zwykły tekst z „Pokaż całość”
  const GLEBOKOSC = 6;                           // zagnieżdżenie bloków (cytat, lista)
  const GLEBOKOSC_INLINE = 4;                    // zagnieżdżenie wyróżnień i etykiet linków
  const ESC = new Set("\\`*_{}[]()#+-.!|~<>\"'".split(""));
  // linie plików i ścieżki floty: /opt/data i korzeń instalacji natywnej (07-sciezki.js), składane raz na korzeń
  const plikLinia = () => Sciezki.linia();
  const wTekscie = () => Sciezki.wzor("md.tekst", ({ poczatek }) =>
    new RegExp(`https?:\\/\\/[^\\s<>()\`"'\\]\\[]+|${poczatek}[^\\s\`'"<>()\\]\\[]+`, "g"));
  const OBRAZ_DATA = /^data:image\/(?:png|jpe?g|gif|webp);base64,[A-Za-z0-9+/=]+$/;
  const KONCOWKA = /[.,;:!?…*_)\]]+$/;

  // ---------------------------------------------------------------------------------------------- adresy
  // http(s) z hostem, mailto i trasy aplikacji #/; znak sterujący albo biały w środku (java\nscript:) = odmowa.
  // Encje (&#106;avascript:) nie są dekodowane, więc nie pasują do schematu i też odpadają.
  function bezpiecznyUrl(u) {
    const s = String(u == null ? "" : u).trim();
    if (!s || /[\u0000-\u0020\u007f-\u009f\u00ad\u200b-\u200f\u2028-\u202e\u2060-\u2064\ufeff]/.test(s)) return null;
    if (s.startsWith("#/")) return s;
    const m = /^([A-Za-z][A-Za-z0-9+.-]{0,20}):/.exec(s);
    if (!m) return null;
    const schemat = m[1].toLowerCase();
    if (schemat === "http" || schemat === "https") return /^https?:\/\/[^/\\?#@\s]/i.test(s) ? s : null;
    if (schemat === "mailto") return /^mailto:[^\s@]+@[^\s@]+$/i.test(s) ? s : null;
    return null;
  }
  const sciezkaFloty = (s) => Sciezki.flota(s);
  const obrazData = (s) => OBRAZ_DATA.test(String(s || ""));

  // szukanie z pamięcią: pozycje zapytań rosną, więc każde indexOf przechodzi nowy fragment tekstu tylko raz
  function szukacz(s) {
    const pamiec = new Map();
    return (d, od) => {
      const p = pamiec.get(d);
      if (p && od >= p.od && (p.w < 0 || od <= p.w)) return p.w;
      const w = s.indexOf(d, od);
      pamiec.set(d, { od, w });
      return w;
    };
  }

  // ---------------------------------------------------------------------------------------------- inline
  const bialy = (c) => c === undefined || c === " " || c === "\t" || c === "\n" || c === "\u00a0";
  const slowny = (c) => c !== undefined && /[\p{L}\p{N}]/u.test(c);

  // gołe adresy i ścieżki floty w zwykłym tekście
  function tekstZLinkami(t, out, bezLinkow) {
    if (bezLinkow) { out.push({ t: "tekst", v: t }); return; }
    let ost = 0;
    const re = wTekscie();
    re.lastIndex = 0;
    for (let m = re.exec(t); m; m = re.exec(t)) {
      let v = m[0];
      const ogon = KONCOWKA.exec(v);
      if (ogon) v = v.slice(0, v.length - ogon[0].length);
      if (!v) continue;
      if (m.index > ost) out.push({ t: "tekst", v: t.slice(ost, m.index) });
      if (!/^https?:\/\//.test(v)) out.push({ t: "sciezka", v });          // druga gałąź wyrażenia: ścieżka floty
      else if (bezpiecznyUrl(v)) out.push({ t: "url", href: v });
      else out.push({ t: "tekst", v });
      ost = m.index + v.length;
      re.lastIndex = ost;
    }
    if (ost < t.length) out.push({ t: "tekst", v: t.slice(ost) });
  }

  // pozycje możliwych domknięć wyróżnienia `d` (jedno przejście tekstu): przed nim nie biały znak, dla _ i __ po nim
  // nie litera, pojedyncze * i _ nie są częścią podwójnego
  function domkniecia(s, d) {
    const out = [];
    for (let j = s.indexOf(d, 1); j >= 0; j = s.indexOf(d, j + 1)) {
      if (bialy(s[j - 1])) continue;
      if (d.length === 1 && (s[j + 1] === d || s[j - 1] === d)) continue;
      if (d[0] === "_" && slowny(s[j + d.length])) continue;
      out.push(j);
    }
    return out;
  }
  // pierwszy element tablicy rosnącej ≥ od (wyszukiwanie binarne), -1 gdy brak
  function pierwszyOd(tab, od) {
    let a = 0, b = tab.length;
    while (a < b) { const c = (a + b) >> 1; if (tab[c] < od) a = c + 1; else b = c; }
    return a < tab.length ? tab[a] : -1;
  }

  // szybkie sito: tekst bez tych znaków (i bez początku ścieżki floty) to sam tekst
  const znaczace = () => Sciezki.wzor("md.znaczace", ({ korzen: z }) =>
    new RegExp("[\\\\`*_~[!\\n]|https?:|\\/opt\\/data\\/" + (z ? `|${z}` : "")));
  function inline(s, gl = 0, bezLinkow = false) {
    s = String(s == null ? "" : s);
    if (!znaczace().test(s)) return s ? [{ t: "tekst", v: s }] : [];
    const out = [], n = s.length, szukaj = szukacz(s), zamkniecia = new Map();
    let tekst = "";
    const zrzuc = () => { if (tekst) { tekstZLinkami(tekst, out, bezLinkow); tekst = ""; } };
    const glebiej = gl + 1 < GLEBOKOSC_INLINE;
    const domkniecie = (d, od) => {
      if (!zamkniecia.has(d)) zamkniecia.set(d, domkniecia(s, d));
      return pierwszyOd(zamkniecia.get(d), od);
    };

    let i = 0;
    while (i < n) {
      const c = s[i];
      if (c === "\\" && i + 1 < n && ESC.has(s[i + 1])) { tekst += s[i + 1]; i += 2; continue; }
      if (c === "\n") { zrzuc(); out.push({ t: "br" }); i++; continue; }
      if (c === "`") {
        let r = 1;
        while (s[i + r] === "`") r++;
        const plot = "`".repeat(r);
        const j = szukaj(plot, i + r);
        if (j >= 0) {
          zrzuc();
          let v = s.slice(i + r, j).replace(/\n/g, " ");
          if (v.length > 2 && v[0] === " " && v[v.length - 1] === " ") v = v.slice(1, -1);
          out.push(sciezkaFloty(v.trim()) && !bezLinkow ? { t: "sciezka", v: v.trim(), kod: true } : { t: "kod", v });
          i = j + r;
          continue;
        }
        tekst += plot; i += r; continue;
      }
      if (c === "!" && s[i + 1] === "[" && !bezLinkow) {
        const z = obrazLubLink(i + 1, true);
        if (z) { zrzuc(); out.push(z.w); i = z.koniec; continue; }
        tekst += c; i++; continue;
      }
      if (c === "[" && !bezLinkow) {
        const z = obrazLubLink(i, false);
        if (z) { zrzuc(); if (z.w) out.push(z.w); else tekst += z.tekst; i = z.koniec; continue; }
        tekst += c; i++; continue;
      }
      if ((c === "*" || c === "_" || c === "~") && glebiej) {
        const podwojny = s[i + 1] === c;
        if (c === "~" && !podwojny) { tekst += c; i++; continue; }
        const d = podwojny ? c + c : c;
        const poOtw = s[i + d.length];
        const otwiera = !bialy(poOtw) && poOtw !== c && !(c === "_" && slowny(s[i - 1]));
        const j = otwiera ? domkniecie(d, i + d.length) : -1;
        if (j > i + d.length) {
          zrzuc();
          out.push({ t: c === "~" ? "s" : podwojny ? "b" : "i", d: inline(s.slice(i + d.length, j), gl + 1, bezLinkow) });
          i = j + d.length;
          continue;
        }
        tekst += d; i += d.length; continue;
      }
      tekst += c;
      i++;
    }
    zrzuc();
    return out;

    // [etykieta](adres) i ![alt](adres): etykieta do 1000 znaków, adres do 2000, bez nowej linii w adresie
    function obrazLubLink(i0, obraz) {
      const j = szukaj("]", i0 + 1);
      if (j < 0 || j - i0 > 1000 || s[j + 1] !== "(") return null;
      const k = szukaj(")", j + 2);
      if (k < 0 || k - j > 2000) return null;
      const surowy = s.slice(j + 2, k);
      if (surowy.includes("\n")) return null;
      const adres = surowy.trim().split(/[ \t]+/)[0].replace(/^<(.*)>$/, "$1");
      const etykieta = s.slice(i0 + 1, j);
      const zrodlo = s.slice(obraz ? i0 - 1 : i0, k + 1);
      if (obraz) {
        if (obrazData(adres)) return { w: { t: "obraz", src: adres, alt: etykieta }, koniec: k + 1 };
        if (sciezkaFloty(adres)) return { w: { t: "obraz_plik", v: adres, alt: etykieta }, koniec: k + 1 };
        return { w: { t: "tekst", v: zrodlo }, koniec: k + 1 };
      }
      const d = glebiej ? inline(etykieta, gl + 1, true) : [{ t: "tekst", v: etykieta }];
      if (sciezkaFloty(adres)) return { w: { t: "sciezka", v: adres, d }, koniec: k + 1 };
      const href = bezpiecznyUrl(adres);
      if (href) return { w: { t: "link", href, d }, koniec: k + 1 };
      return { tekst: zrodlo, koniec: k + 1 };          // niedozwolony adres: całe źródło jako tekst
    }
  }

  // ---------------------------------------------------------------------------------------------- bloki
  // płot bloku kodu i nagłówek bez wyrażeń z nakładającymi się kwantyfikatorami (długa linia nie zwalnia parsera)
  function plot(l) {
    const m = /^( {0,3})(`{3,}|~{3,})/.exec(l);
    if (!m) return null;
    const info = l.slice(m[0].length);
    if (m[2][0] === "`" && info.includes("`")) return null;
    return { wc: m[1].length, znak: m[2][0], dl: m[2].length, jezyk: (info.trim().split(/[ \t]/)[0] || "").slice(0, 30) };
  }
  function naglowek(l) {
    const m = /^ {0,3}(#{1,6})(?=[ \t]|$)/.exec(l);
    if (!m) return null;
    let t = l.slice(m[0].length).trim();
    let k = t.length;
    while (k > 0 && t[k - 1] === "#") k--;
    if (k === 0 || t[k - 1] === " " || t[k - 1] === "\t") t = t.slice(0, k).trim();
    return { n: m[1].length, tekst: t };
  }
  const LISTA = /^( *)([-*+]|\d{1,9}[.)])(?:[ \t]+(.*))?$/;
  const CYTAT = /^ {0,3}> ?(.*)$/;
  const SEP_TABELI = /^[ \t]*\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$/;
  const ZWYKLA = /^\p{L}/u;
  const wciecie = (l) => { let k = 0; while (l[k] === " ") k++; return k; };
  const pusta = (l) => !l || !l.trim();
  const linia = (l) => { const t = l.replace(/[ \t]/g, ""); return wciecie(l) < 4 && /^(?:-{3,}|\*{3,}|_{3,})$/.test(t); };
  // tabela: najwyżej TAB_KOLUMNY kolumn i TAB_KOMORKI komórek (dłuższa reszta zostaje tekstem), żeby wklejony
  // ogromny plik nie zawiesił karty
  const TAB_KOLUMNY = 50, TAB_KOMORKI = 10000;
  const tabelaOd = (linie, i) => linie[i].includes("|") && linie[i].length < 4000 && i + 1 < linie.length && linie[i + 1].includes("-")
    && SEP_TABELI.test(linie[i + 1]) && komorki(linie[i + 1]).length === komorki(linie[i]).length && komorki(linie[i]).length <= TAB_KOLUMNY;
  const zaczynaBlok = (linie, i) => {
    const l = linie[i];
    return !!plot(l) || !!naglowek(l) || CYTAT.test(l) || linia(l) || plikLinia().test(l) || tabelaOd(linie, i);
  };

  // komórki wiersza tabeli: | poza `kodem` i bez \|
  function komorki(l) {
    let t = l.trim();
    if (t.startsWith("|")) t = t.slice(1);
    if (t.endsWith("|") && !t.endsWith("\\|")) t = t.slice(0, -1);
    const out = [];
    let biez = "", kod = false;
    for (let i = 0; i < t.length; i++) {
      const c = t[i];
      if (c === "\\" && t[i + 1] === "|") { biez += "|"; i++; continue; }
      if (c === "`") kod = !kod;
      if (c === "|" && !kod) { out.push(biez.trim()); biez = ""; continue; }
      biez += c;
    }
    out.push(biez.trim());
    return out;
  }

  function bloki(linie, gl) {
    const out = [], n = linie.length;
    let i = 0, akapit = [];
    const zamknijAkapit = () => {
      if (akapit.length) out.push({ t: "p", d: inline(akapit.map((l) => l.trim()).join("\n")) });
      akapit = [];
    };
    while (i < n) {
      const l = linie[i];
      if (pusta(l)) { zamknijAkapit(); i++; continue; }
      // zwykła linia tekstu (litera na początku, bez | i znacznika pliku): od razu do akapitu
      if (ZWYKLA.test(l) && !l.includes("|") && !l.startsWith("MEDIA:") && !l.startsWith("Załączniki")) { akapit.push(l); i++; continue; }
      const f = plot(l);
      if (f) {
        zamknijAkapit();
        const { wc, znak, dl } = f;
        const tresc = [];
        let j = i + 1, zamkniety = false;
        for (; j < n; j++) {
          const z = /^ {0,3}(`{3,}|~{3,})[ \t]*$/.exec(linie[j]);
          if (z && z[1][0] === znak && z[1].length >= dl) { zamkniety = true; break; }
          tresc.push(linie[j].slice(Math.min(wc, wciecie(linie[j]))));
        }
        out.push({ t: "kod", jezyk: f.jezyk, v: tresc.join("\n"), otwarty: !zamkniety });
        i = zamkniety ? j + 1 : j;
        continue;
      }
      const h = naglowek(l);
      if (h && (h.tekst || !akapit.length)) {
        zamknijAkapit();
        out.push({ t: "h", n: Math.min(4, h.n), d: inline(h.tekst) });
        i++;
        continue;
      }
      if (linia(l)) { zamknijAkapit(); out.push({ t: "hr" }); i++; continue; }
      if (plikLinia().test(l)) {
        zamknijAkapit();
        const sciezki = [];
        while (i < n && plikLinia().test(linie[i])) { sciezki.push(plikLinia().exec(linie[i])[1]); i++; }
        out.push({ t: "pliki", sciezki });
        continue;
      }
      if (/^Załączniki \(pliki na dysku floty\):\s*$/.test(l.trim()) && i + 1 < n && plikLinia().test(linie[i + 1])) { i++; continue; }
      if (CYTAT.test(l) && gl < GLEBOKOSC) {
        zamknijAkapit();
        const wew = [];
        while (i < n && !pusta(linie[i])) {
          const c = CYTAT.exec(linie[i]);
          if (c) wew.push(c[1]);
          else if (!zaczynaBlok(linie, i) && !LISTA.test(linie[i])) wew.push(linie[i]);
          else break;
          i++;
        }
        out.push({ t: "cytat", d: bloki(wew, gl + 1) });
        continue;
      }
      if (tabelaOd(linie, i)) {
        zamknijAkapit();
        const nag = komorki(l), wyr = komorki(linie[i + 1]).map((k) => (/^:-+:$/.test(k) ? "center" : /-:$/.test(k) ? "right" : /^:-/.test(k) ? "left" : null));
        const wiersze = [];
        i += 2;
        const maxWierszy = Math.min(500, Math.floor(TAB_KOMORKI / nag.length) - 1);
        while (i < n && !pusta(linie[i]) && linie[i].includes("|") && wiersze.length < maxWierszy) {
          const k = komorki(linie[i]);
          wiersze.push(nag.map((_, x) => (k[x] ? inline(k[x]) : [])));   // brakująca komórka: pusta, bez parsowania
          i++;
        }
        out.push({ t: "tabela", wyr, nag: nag.map((k) => inline(k)), wiersze });
        continue;
      }
      const m = LISTA.exec(l);
      if (m && gl < GLEBOKOSC && !(akapit.length && (m[3] === undefined || (/\d/.test(m[2]) && !/^1[.)]$/.test(m[2]))))) {
        zamknijAkapit();
        const [blok, j] = lista(linie, i, gl);
        out.push(blok);
        i = j;
        continue;
      }
      akapit.push(l);
      i++;
    }
    zamknijAkapit();
    return out;
  }

  // lista od linii i: pozycje na wcięciu pierwszej; linie wcięte głębiej (i leniwe kontynuacje akapitu) należą do
  // pozycji i są parsowane rekurencyjnie (zagnieżdżona lista, kod w punkcie). Do 3 poziomów list.
  function lista(linie, i, gl) {
    const n = linie.length, m0 = LISTA.exec(linie[i]);
    const wc = m0[1].length, uporz = /\d/.test(m0[2]);
    const znacznik = uporz ? m0[2].slice(-1) : m0[2];
    const el = [];
    let luzna = false;
    while (i < n) {
      const m = LISTA.exec(linie[i]);
      if (!m || m[1].length !== wc || /\d/.test(m[2]) !== uporz || (uporz ? m[2].slice(-1) : m[2]) !== znacznik) break;
      const odstep = m[3] === undefined ? 1 : linie[i].length - m[3].length - m[1].length - m[2].length;
      const wcTresci = wc + m[2].length + Math.min(4, Math.max(1, odstep));
      let pierwsza = m[3] || "";
      let zadanie = null;
      const z = /^\[([ xX])\][ \t]+/.exec(pierwsza);
      if (z) { zadanie = z[1] !== " "; pierwsza = pierwsza.slice(z[0].length); }
      const tresc = [pierwsza];
      let j = i + 1, przerwa = false;
      for (; j < n; j++) {
        const lj = linie[j];
        if (pusta(lj)) { przerwa = true; tresc.push(""); continue; }
        const wj = wciecie(lj);
        if (wj >= wcTresci || (wj > wc && LISTA.test(lj))) { tresc.push(lj.slice(Math.min(wj, wcTresci))); przerwa = false; continue; }
        if (!przerwa && wj > wc - 1 && !LISTA.test(lj) && !zaczynaBlok(linie, j)) { tresc.push(lj.trim()); continue; }
        break;
      }
      while (tresc.length && pusta(tresc[tresc.length - 1])) tresc.pop();
      if (przerwa && j < n && LISTA.test(linie[j]) && wciecie(linie[j]) === wc) luzna = true;
      const prosta = tresc.length === 1 && ZWYKLA.test(tresc[0]) && !tresc[0].includes("|");
      el.push({ zadanie, d: !prosta && gl + 1 < GLEBOKOSC ? bloki(tresc, gl + 1) : [{ t: "p", d: inline(tresc.join("\n")) }] });
      i = j;
      if (przerwa && (i >= n || !LISTA.test(linie[i]) || wciecie(linie[i]) !== wc)) break;
    }
    return [{ t: "lista", uporzadkowana: uporz, start: uporz ? parseInt(m0[2], 10) : null, luzna, el }, i];
  }

  function parsuj(tekst) {
    const s = String(tekst == null ? "" : tekst).replace(/\r\n?/g, "\n");
    if (s.length > MAKS) return [{ t: "surowy", v: s }];
    return bloki(s.split("\n"), 0);
  }

  // stały początek strumieniowanego tekstu: do ostatniej pustej linii poza blokiem kodu (tylko ogon parsujemy znowu)
  function granica(tekst) {
    const s = String(tekst || "");
    let i = 0, kod = null, ost = 0;
    while (i < s.length) {
      let j = s.indexOf("\n", i);
      if (j < 0) j = s.length;
      const l = s.slice(i, j);
      const p = /^ {0,3}(`{3,}|~{3,})/.exec(l);
      if (p) {
        if (!kod) kod = p[1];
        else if (p[1][0] === kod[0] && p[1].length >= kod.length && !l.trim().slice(p[1].length).trim()) kod = null;
      } else if (!kod && !l.trim() && j < s.length) ost = j + 1;
      i = j + 1;
    }
    return ost;
  }

  // zwykły tekst bloków (podgląd, kopiowanie, testy)
  function tekstWezlow(w) {
    return (w || []).map((x) => (x.t === "br" ? "\n" : x.v != null && !x.d ? x.v : x.href && !x.d ? x.href : tekstWezlow(x.d))).join("");
  }

  return { MAKS, parsuj, inline, granica, bezpiecznyUrl, sciezkaFloty, obrazData, tekstWezlow, plikLinia };
})();

// ------------------------------------------------------------------------------------------------- render
// Wszystko z React.createElement (html``), teksty jako węzły tekstowe. `opcje.pomin`: ścieżki, które wiadomość już
// pokazuje kartami plików (z osi czasu), żeby linia MEDIA: ich nie dublowała.
function renderujInline(wezly, k = "i") {
  return (wezly || []).map((w, i) => {
    const key = `${k}${i}`;
    switch (w.t) {
      case "tekst": return w.v;
      case "br": return html`<br key=${key}/>`;
      case "b": return html`<strong key=${key}>${renderujInline(w.d, key)}</strong>`;
      case "i": return html`<em key=${key}>${renderujInline(w.d, key)}</em>`;
      case "s": return html`<del key=${key}>${renderujInline(w.d, key)}</del>`;
      case "kod": return html`<code key=${key} class="j-md-k">${w.v}</code>`;
      case "link": {
        const wew = w.href.startsWith("#/");
        return html`<a key=${key} class="j-md-a" href=${w.href} target=${wew ? undefined : "_blank"}
          rel=${wew ? undefined : "noopener noreferrer"}>${renderujInline(w.d, key)}</a>`;
      }
      case "url": return html`<a key=${key} class="j-md-a" href=${w.href} target="_blank" rel="noopener noreferrer">${w.href}</a>`;
      case "sciezka": return html`<${SciezkaPliku} key=${key} sciezka=${w.v} kod=${w.kod}>${w.d ? renderujInline(w.d, key) : null}</${SciezkaPliku}>`;
      case "obraz": return html`<img key=${key} class="j-md-img" src=${w.src} alt=${w.alt || ""}/>`;
      case "obraz_plik": return html`<${ObrazPliku} key=${key} sciezka=${w.v} alt=${w.alt || ""}/>`;
      default: return null;
    }
  });
}

function renderujBloki(bloki, opcje = {}, k = "b") {
  return (bloki || []).map((b, i) => {
    const key = `${k}${i}`;
    switch (b.t) {
      case "p": return html`<p key=${key}>${renderujInline(b.d, key)}</p>`;
      case "h": return React.createElement(`h${Math.min(6, b.n + 2)}`, { key, className: `j-md-h j-md-h${b.n}` }, renderujInline(b.d, key));
      case "hr": return html`<hr key=${key}/>`;
      case "kod": return html`<${BlokKodu} key=${key} jezyk=${b.jezyk} kod=${b.v}/>`;
      case "cytat": return html`<blockquote key=${key}>${renderujBloki(b.d, opcje, key)}</blockquote>`;
      case "lista": {
        const el = b.el.map((x, j) => html`<li key=${j} class=${x.zadanie != null ? "j-md-zad" : undefined}>
          ${x.zadanie != null && html`<input type="checkbox" checked=${x.zadanie} disabled aria-label=${T(x.zadanie ? "md.zrobione" : "md.do_zrobienia")}/>`}
          ${renderujBloki(x.d, opcje, `${key}-${j}-`)}</li>`);
        const klasa = cx(b.luzna ? "is-luzna" : "is-zwarta");
        return b.uporzadkowana
          ? html`<ol key=${key} class=${klasa} start=${b.start !== 1 ? b.start : undefined}>${el}</ol>`
          : html`<ul key=${key} class=${klasa}>${el}</ul>`;
      }
      case "tabela": return html`<div key=${key} class="j-md-tab" role="region" tabIndex="0" aria-label=${T("md.tabela")}><table>
        <thead><tr>${b.nag.map((c, j) => html`<th key=${j} style=${b.wyr[j] ? { textAlign: b.wyr[j] } : undefined}>${renderujInline(c, `${key}h${j}`)}</th>`)}</tr></thead>
        <tbody>${b.wiersze.map((w, r) => html`<tr key=${r}>${w.map((c, j) => html`<td key=${j} style=${b.wyr[j] ? { textAlign: b.wyr[j] } : undefined}>${renderujInline(c, `${key}r${r}c${j}`)}</td>`)}</tr>`)}</tbody>
      </table></div>`;
      case "pliki": {
        const sciezki = b.sciezki.filter((s) => !(opcje.pomin && opcje.pomin.has(s)));
        return sciezki.length ? html`<div key=${key} class="j-pliki">${sciezki.map((s) => html`<${KartaPliku} key=${s} plik=${fileFromPath(s)}/>`)}</div>` : null;
      }
      case "surowy": return html`<${DlugiTekst} key=${key} tekst=${b.v}/>`;
      default: return null;
    }
  });
}

function DlugiTekst({ tekst }) {
  const [calosc, setCalosc] = useState(false);
  return html`<div class="j-md-surowy">${calosc ? tekst : tekst.slice(0, 20000)}
    ${!calosc && html`<button type="button" class="j-link" onClick=${() => setCalosc(true)}>${T("md.pokaz_calosc")}</button>`}</div>`;
}

function BlokKodu({ jezyk, kod }) {
  const [zawijaj, setZawijaj] = useState(false);
  const [skopiowano, setSkopiowano] = useState(false);
  const kopiuj = async () => {
    try { await copyText(kod); setSkopiowano(true); setTimeout(() => setSkopiowano(false), 1600); } catch (e) { Komunikaty.pokaz(e.message || String(e)); }
  };
  return html`<figure class=${cx("j-md-kod", zawijaj && "is-zawijany")}>
    <figcaption><span>${jezyk || T("md.kod")}</span><span class="j-rozpych"></span>
      <button type="button" class="j-md-kod-b" aria-pressed=${String(zawijaj)} onClick=${() => setZawijaj(!zawijaj)}>${T("md.zawijaj")}</button>
      <button type="button" class="j-md-kod-b" onClick=${kopiuj}>${T(skopiowano ? "md.skopiowano" : "md.kopiuj")}</button></figcaption>
    <pre tabIndex="0"><code>${kod}</code></pre></figure>`;
}

// tekst wiadomości jako Markdown. Strumień: stały początek (do ostatniej pustej linii poza kodem) parsowany raz,
// ogon na nowo co klatkę animacji (delty przychodzą co ≤ 50 ms, rysujemy najwyżej raz na klatkę)
const BlokiMd = React.memo ? React.memo(({ tekst, pomin }) => renderujBloki(Md.parsuj(tekst), { pomin })) : null;

// Jedno rysowanie naraz, z najnowszym tekstem: kolejna delta nie anuluje czekającej klatki (inaczej przy deltach
// częstszych niż klatki, np. w karcie w tle, gdzie klatek nie ma, tekst stałby do końca odpowiedzi); gdy klatki
// nie przychodzą, rysuje zegar po 100 ms (w tle przeglądarka i tak tnie go do 1 na sekundę).
function useKlatka(wartosc, wlaczone) {
  const [w, setW] = useState(wartosc);
  const najnowsza = useRef(wartosc);
  const plan = useRef(null);
  najnowsza.current = wartosc;
  const odwolaj = () => {
    if (!plan.current) return;
    cancelAnimationFrame(plan.current.r);
    clearTimeout(plan.current.t);
    plan.current = null;
  };
  useEffect(() => {
    if (!wlaczone) { odwolaj(); setW(wartosc); return; }
    if (plan.current) return;
    const rysuj = () => { odwolaj(); setW(najnowsza.current); };
    plan.current = { r: requestAnimationFrame(rysuj), t: setTimeout(rysuj, 100) };
  }, [wartosc, wlaczone]);
  useEffect(() => odwolaj, []);
  return wlaczone ? w : wartosc;
}

function TrescMd({ tekst, zywy = false, pomin = null, klasa }) {
  const t = useKlatka(String(tekst || ""), zywy);
  if (!zywy) return html`<div class=${cx("j-md", klasa)}><${BlokiMd} tekst=${t} pomin=${pomin}/></div>`;
  const g = Md.granica(t);
  return html`<div class=${cx("j-md", klasa)}><${BlokiMd} tekst=${t.slice(0, g)} pomin=${pomin}/><${BlokiMd} tekst=${t.slice(g)} pomin=${pomin}/></div>`;
}
