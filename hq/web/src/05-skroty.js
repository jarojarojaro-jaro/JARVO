// Skróty klawiszowe aplikacji (docs/HQ.md „Aplikacja”; ⌘ zamiast Ctrl na macOS). Jeden nasłuch keydown dla całej
// aplikacji. Skrót bez modyfikatora („/”, F6) nie działa w polu tekstowym. Ctrl/⌘+1…8 i Alt+1…8 nie są używane:
// przeglądarki zostawiają je sobie. Pauza (narzędzie na pełny ekran, Stara Baza): skróty milkną, Esc obsługują warstwy.

const Skroty = (() => {
  const nav = typeof navigator === "undefined" ? {} : navigator;
  const MAC = /Mac|iPhone|iPad/.test(nav.platform || nav.userAgent || "");
  const KODY = { ",": "Comma", "/": "Slash", "\\": "Backslash", ".": "Period" };
  const NAZWY = { ArrowUp: "↑", ArrowDown: "↓", ArrowLeft: "←", ArrowRight: "→", Escape: "Esc" };
  const wpisy = [];
  let pauza = false, slucha = false;

  // „Mod+Shift+O” → {mod, shift, alt, klawisz}
  function parsuj(komb) {
    const cz = String(komb).split("+"), k = { mod: false, shift: false, alt: false, klawisz: cz.pop() };
    for (const x of cz) k[x.toLowerCase()] = true;
    return k;
  }

  function pasuje(e, k, mac = MAC) {
    if (!!k.mod !== !!(mac ? e.metaKey : e.ctrlKey) || (mac ? e.ctrlKey : e.metaKey)) return false;
    if (!!k.alt !== !!e.altKey) return false;
    const kl = k.klawisz;
    if (kl.length === 1 && !/[a-z0-9]/i.test(kl)) {        // znak („/”, „,”): Shift zależy od układu klawiatury
      if (k.shift && !e.shiftKey) return false;
      return e.key === kl || (!e.shiftKey && e.code === KODY[kl]);
    }
    if (!!k.shift !== !!e.shiftKey) return false;
    if (kl.length === 1) return String(e.key || "").toLowerCase() === kl.toLowerCase() || e.code === `Key${kl.toUpperCase()}`;
    return e.key === kl;
  }

  const wPolu = (el) => !!el && (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.isContentEditable);

  function naKlawisz(e) {
    if (pauza || e.defaultPrevented || e.isComposing) return;
    for (const w of wpisy) {
      if (!pasuje(e, w.k)) continue;
      if (!w.k.mod && !w.k.alt && !w.wPolu && wPolu(e.target)) continue;
      e.preventDefault();
      w.akcja(e);
      return;
    }
  }

  // {komb, opis (klucz T), akcja, wPolu?} → funkcja usuwająca
  function dodaj(w) {
    const wpis = { ...w, k: parsuj(w.komb) };
    wpisy.push(wpis);
    if (!slucha && typeof window !== "undefined") { window.addEventListener("keydown", naKlawisz); slucha = true; }
    return () => {
      const i = wpisy.indexOf(wpis);
      if (i >= 0) wpisy.splice(i, 1);
      if (!wpisy.length && slucha) { window.removeEventListener("keydown", naKlawisz); slucha = false; }
    };
  }

  // „Mod+Shift+O” → „Ctrl+Shift+O” albo „⌘⇧O” (pomoc skrótów, podpowiedzi)
  function opis(komb, mac = MAC) {
    const k = parsuj(komb);
    const cz = [k.mod && (mac ? "⌘" : "Ctrl"), k.alt && (mac ? "⌥" : "Alt"), k.shift && (mac ? "⇧" : "Shift"), NAZWY[k.klawisz] || k.klawisz];
    return cz.filter(Boolean).join(mac ? "" : "+");
  }

  return {
    MAC, parsuj, pasuje, dodaj, opis,
    lista: () => wpisy.map(({ komb, opis: o }) => ({ komb, opis: o })),
    wstrzymaj: (tak) => { pauza = !!tak; },
  };
})();
