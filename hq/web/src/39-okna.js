// Okna i pliki w rdzeniu: modal z Escape, akcje pliku i plik w wiadomości (MEDIA:). Pakiety „baza” i „edytor”
// biorą je stąd; konteksty edytora i animacji też leżą tu, bo akcje pliku pytają o nie przy każdym renderze.
const EditCtx = React.createContext(null);
const AnimCtx = React.createContext(null);
// Otwarte okna jedno na drugim (karta → podgląd pliku): Escape zamyka tylko to na wierzchu.
const MODAL_STACK = [];

function Modal({ title, onClose, children, wide }) {
  const me = useRef({});
  useEffect(() => {
    MODAL_STACK.push(me.current);
    return () => { const i = MODAL_STACK.indexOf(me.current); if (i >= 0) MODAL_STACK.splice(i, 1); };
  }, []);
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && MODAL_STACK[MODAL_STACK.length - 1] === me.current && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return html`<div class="thq-modal-back" onClick=${(e) => e.target === e.currentTarget && onClose()}>
    <div class=${cx("thq-modal", wide && "is-wide")} role="dialog" aria-modal="true" aria-label=${title}>
      <header class="thq-modal-head"><h3>${title}</h3>
        <button type="button" class="thq-icon-btn" onClick=${onClose} aria-label=${L("Zamknij", "Close")}>×</button></header>
      <div class="thq-modal-body">${children}</div>
    </div>
  </div>`;
}

// Akcje pliku wynikowego: podgląd, „Odpal” (HTML w nowej karcie), folder w Eksploratorze, pobranie.
function FileActions({ file, onPreview, compact }) {
  const host = useHost();
  const [note, setNote] = useState(null);
  const say = (text, bad) => { setNote({ text, bad }); setTimeout(() => setNote(null), bad ? 6000 : 3500); };
  const run = (fn, okText) => async (e) => {
    e.stopPropagation();
    try { await fn(); if (okText) say(okText); } catch (err) { say(err.message || String(err), true); }
  };
  const copy = run(() => copyText(hostPathOf(file.path, host)), L("Ścieżka skopiowana", "Path copied"));
  const edit = React.useContext(EditCtx);
  const animate = React.useContext(AnimCtx);
  const [isAnim, setIsAnim] = useState(file.anim);
  useEffect(() => {   // plik z linku w czacie nie ma flagi z listy wyników: pytamy serwer raz
    if (file.kind !== "html" || file.anim !== undefined || !api.animCheck) return undefined;
    let alive = true;
    api.animCheck(file.path).then((r) => alive && setIsAnim(!!(r && r.anim))).catch(() => {});
    return () => { alive = false; };
  }, [file.path]);
  return html`<span class=${cx("thq-file-acts", compact && "is-compact")}>
    ${file.kind === "html" && isAnim && animate && html`<button type="button" class="thq-act-btn is-run" onClick=${(e) => { e.stopPropagation(); animate(file); }}
      title=${L("Podgląd na żywo: przewijanie, parametry (kolory, teksty, tempo), pomiar", "Live preview: scrubbing, parameters (colors, texts, timing), measurement")}>◐ ${L("Animacja", "Animation")}</button>`}
    ${file.kind === "video" && edit && html`<button type="button" class="thq-act-btn is-run" onClick=${(e) => { e.stopPropagation(); edit(file); }}
      title=${L("Otwórz w edytorze: tnij, napisy, muzyka, tempo, eksport", "Open in the editor: cut, text, music, speed, export")}>✎ ${L("Edytuj", "Edit")}</button>`}
    ${file.kind === "html" && html`<button type="button" class="thq-act-btn is-run" onClick=${run(() => openSite(file.path))}
      title=${L("Otwórz stronę w nowej karcie przeglądarki", "Open the page in a new browser tab")}>▶ ${L("Odpal", "Run")}</button>`}
    ${onPreview && html`<button type="button" class="thq-act-btn" onClick=${(e) => { e.stopPropagation(); onPreview(file); }}
      title=${L("Podgląd w oknie", "Preview in a window")}>${file.kind === "html" ? L("Kod", "Code") : L("Podgląd", "Preview")}</button>`}
    ${host.explorer
      ? html`<button type="button" class="thq-act-btn" onClick=${run(() => api.reveal(file.path), L("Otwieram Eksplorator…", "Opening Explorer…"))}
          title=${hostPathOf(file.path, host)}>${L("Pokaż w folderze", "Show in folder")}</button>`
      : html`<button type="button" class="thq-act-btn" onClick=${copy} title=${hostPathOf(file.path, host)}>${L("Kopiuj ścieżkę", "Copy path")}</button>`}
    ${file.kind === "image" && html`<button type="button" class="thq-act-btn" onClick=${run(() => copyImage(file), L("Obraz w schowku: wklej go w czacie", "Image copied: paste it into a chat"))}
      title=${L("Skopiuj obraz do schowka (np. do Telegrama)", "Copy the image to the clipboard (e.g. for Telegram)")}>${L("Kopiuj obraz", "Copy image")}</button>`}
    ${!compact && html`<button type="button" class="thq-act-btn" onClick=${run(() => downloadFile(file))} title=${L("Zapisz plik na dysku", "Save the file to disk")}>${L("Pobierz", "Download")}</button>`}
    ${note && html`<span class=${cx("thq-act-note", note.bad && "is-bad")} role="status">${note.text}</span>`}
  </span>`;
}

// Plik w wiadomości (MEDIA: od agenta, 📎 od Ciebie): obraz jako miniatura, inny plik jako nazwa z akcjami.
function MediaFile({ path }) {
  const open = React.useContext(FileCtx);
  const f = fileFromPath(path);
  const [url, setUrl] = useState(null);
  const [bad, setBad] = useState(false);
  useEffect(() => {
    if (f.kind !== "image") return undefined;
    let alive = true, made = null;
    api.fileBlob(path).then((b) => { if (alive) { made = URL.createObjectURL(b); setUrl(made); } }).catch(() => alive && setBad(true));
    return () => { alive = false; if (made) URL.revokeObjectURL(made); };
  }, [path]);
  if (bad) return html`<span class="thq-media-file is-bad" title=${path}>${f.name} · ${L("poza katalogami floty albo nie istnieje", "outside fleet folders or missing")}</span>`;
  if (f.kind === "image") {
    return html`<button type="button" class="thq-media-img" onClick=${() => open && open(f)} title=${`${f.name} · ${L("kliknij: podgląd, kopiuj, pobierz", "click: preview, copy, download")}`}>
      ${url ? html`<img src=${url} alt=${f.name}/>` : html`<span class="thq-muted">${f.name}</span>`}</button>`;
  }
  return html`<span class="thq-media-file"><button type="button" class="thq-pathlink" onClick=${() => open && open(f)}>${f.name}</button>
    <${FileActions} file=${f} compact=${true}/></span>`;
}

