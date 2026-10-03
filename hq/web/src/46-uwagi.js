// ------------------------------------------------------------------ edytor: kadr i uwagi reżyserskie
// Bez Reacta i bez DOM: matematyka kadru i treść prośby do Wideografa (testy w node: tests/test_edytor.py).

// Prostokąt, w którym przeglądarka rysuje klatkę o wymiarach vw×vh w kadrze W×H: object-fit (contain albo cover),
// object-position = punkt skupienia (fx, fy) i scale(zoom) wokół niego, tak jak applyFit w podglądzie i cover_filter
// w eksporcie (edytor.py). Zrzut kadru rysuje klatkę dokładnie tam, gdzie widzi ją użytkownik.
function fitBox(vw, vh, W, H, c) {
  const cover = !!c && c.fit === "cover";
  const lim = (x, a, b, d) => Math.min(b, Math.max(a, Number.isFinite(+x) ? +x : d));
  const fx = cover ? lim(c.fx, 0, 1, 0.5) : 0.5, fy = cover ? lim(c.fy, 0, 1, 0.5) : 0.5;
  const z = cover ? lim(c.zoom, 1, 3, 1) : 1;
  const s = cover ? Math.max(W / vw, H / vh) : Math.min(W / vw, H / vh);
  const dw = vw * s, dh = vh * s;
  const ox = W * fx, oy = H * fy;
  return { x: ox + ((W - dw) * fx - ox) * z, y: oy + ((H - dh) * fy - oy) * z, w: dw * z, h: dh * z };
}

// Rozmyte tło (fit "blur"): ujęcie pokrywające kadr, zmniejszone do ~128 px na kanwie `s` (podgląd rozmywa ją
// w CSS, kadr dla agenta filtrem kanwy). Eksport: edytor.blur_filter, ten sam wygląd co `film.py --tryb rozmyte`.
function blurBg(s, el, vw, vh, W, H) {
  const k = 128 / Math.max(W, H), w = Math.max(2, Math.round(W * k)), h = Math.max(2, Math.round(H * k));
  if (s.width !== w || s.height !== h) { s.width = w; s.height = h; }
  const r = fitBox(vw, vh, w, h, { fit: "cover" });
  try { s.getContext("2d").drawImage(el, r.x, r.y, r.w, r.h); } catch (_) { /* klatka jeszcze niegotowa */ }
  return s;
}

// Zaznaczenie na podglądzie (dwa punkty w ułamkach 0–1) → prostokąt w pikselach kadru W×H.
// Kliknięcie albo zaznaczenie mniejsze niż `min` kadru = cały kadr.
function shotRect(a, b, W, H, min = 0.03) {
  const c01 = (v) => Math.min(1, Math.max(0, v));
  const x0 = c01(Math.min(a.x, b.x)), x1 = c01(Math.max(a.x, b.x));
  const y0 = c01(Math.min(a.y, b.y)), y1 = c01(Math.max(a.y, b.y));
  if (x1 - x0 < min || y1 - y0 < min) return { x: 0, y: 0, w: W, h: H, full: true };
  const x = Math.round(x0 * W), y = Math.round(y0 * H);
  return { x, y, w: Math.max(2, Math.round(x1 * W) - x), h: Math.max(2, Math.round(y1 * H) - y), full: false };
}

// Rozmiar obrazu wysyłanego modelowi: dłuższy bok najwyżej `max` px (mniej tokenów, a tekst na kadrze dalej czytelny).
function shotSize(w, h, max = 1280) {
  const k = Math.min(1, max / Math.max(w, h));
  return [Math.max(1, Math.round(w * k)), Math.max(1, Math.round(h * k))];
}

// Czas osi do uwag: 0:04.2, 1:05.0
function edClock(s) {
  const t = Math.max(0, Math.round((+s || 0) * 10) / 10);
  const m = Math.floor(t / 60);
  return `${m}:${(t - m * 60).toFixed(1).padStart(4, "0")}`;
}

// Uwagi jeszcze niezamknięte przez Wideografa, w kolejności osi.
function openNotes(notes) { return (notes || []).filter((n) => n && !n.done).sort((a, b) => a.t - b.t); }

// Prośba do Wideografa: film, projekt, miejsce na osi, prośba ogólna, kadr do niej i otwarte uwagi z czasem i kadrami.
// `urls(path)` zwraca obraz (data URL) zrobiony w tej sesji edytora; pierwsze 4 obrazy idą też jako obrazy wiadomości
// (model je widzi), wszystkie kadry jako ścieżki (vision_analyze, także po ponownym otwarciu edytora).
function askMessage({ path, cursor, where, text, shot, notes, urls }) {
  const projFile = path.replace(/\.[^./]+$/, ".edycja.json");
  const open = openNotes(notes);
  const attachments = [], images = [];
  const pic = (p) => {
    if (!p) return "";
    if (!attachments.includes(p)) attachments.push(p);
    const u = urls ? urls(p) : null;
    if (u && images.length < 4 && !images.includes(u)) { images.push(u); return ` (obraz ${images.length})`; }
    return "";
  };
  const lines = [`Edycja filmu w edytorze HQ: \`${path}\``,
    `Projekt montażu: \`${projFile}\` · kursor ${edClock(cursor)} · zaznaczone: ${where || "nic"}.`,
    `Prośba: ${(text || "").trim() || "zajmij się uwagami z osi poniżej"}`];
  if (shot && shot.path) lines.push(`Kadr do prośby: \`${shot.path}\`${pic(shot.path)}`);
  if (open.length) {
    lines.push(`Uwagi na osi (${open.length}; czas osi po cięciach, uwaga dotyczy tego miejsca):`);
    open.forEach((n, i) => lines.push(`${i + 1}. [${n.id}] ${edClock(n.t)}: „${String(n.text || "").trim() || "zobacz kadr"}”`
      + (n.img ? ` · kadr \`${n.img}\`${pic(n.img)}` : "")));
  }
  lines.push("Pracuj na tym projekcie: `python3 $HERMES_HOME/scripts/projekt.py pokaz <film>` (uwagi też tam są), zmiany przez "
    + "`projekt.py dodaj-audio / dodaj-tekst / dodaj-klip / kadr / napisy / usun`"
    + (open.length ? ", każdą uwagę zamknij: `projekt.py uwaga <film> <id> --zrobione \"co zmieniłeś\"` albo `--odrzuc \"dlaczego\"`" : "")
    + ", na końcu `projekt.py render <film>` i linia MEDIA:. Kadry oglądasz przez vision_analyze. Nie cofaj moich cięć; edytor sam wczyta Twoje zmiany.");
  lines.push("Typografia słowo po słowie (skill `typografia-edit`): `typografia.py pokaz / popraw / paleta / style / sylwetki <film>`, "
    + "`typografia.py plan` tylko gdy projekt nie ma jeszcze planu; moje poprawki bloków zostają.");
  return { message: lines.join("\n"), attachments, images };
}
