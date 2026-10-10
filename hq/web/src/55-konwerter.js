// Konwerter plików w Centrali: wrzucasz plik, wybierasz format, pobierasz wynik. Ten sam konwertuj.py
// co wspólny skill floty `konwersja-plikow`; plik nie wychodzi z serwera (wynik w inbox/<data>/konwerter/).

const KONW_GRUPY = bilingual({
  obraz: ["Zdjęcie", "Image"], wideo: ["Wideo", "Video"], audio: ["Dźwięk", "Audio"], pdf: ["PDF", "PDF"],
  dokument: ["Dokument", "Document"], tekst: ["Tekst", "Text"], arkusz: ["Arkusz", "Spreadsheet"],
  prezentacja: ["Prezentacja", "Slides"],
});
const KONW_ROZMIARY = [["", "Oryginał", "Original"], ["1920", "1920 px", "1920 px"], ["1080", "1080 px", "1080 px"],
  ["720p", "720p", "720p"], ["50%", "50%", "50%"]];
const KONW_JAKOSC = [["", "Zwykła", "Normal"], ["95", "Najlepsza", "Best"], ["50", "Mniejszy plik", "Smaller file"]];
// metadane o człowieku w zdjęciu, filmie, dźwięku, PDF i dokumencie (klucze z konwertuj.py: WRAZLIWE)
const KONW_META = bilingual({
  miejsce: ["Miejsce (GPS)", "Location (GPS)"], urzadzenie: ["Telefon albo aparat", "Phone or camera"],
  czas: ["Data i godzina", "Date and time"], firma: ["Firma, program albo szablon", "Company, app or template"],
  historia: ["Historia zmian", "Edit history"], osoba: ["Autor albo właściciel", "Author or owner"],
  opis: ["Opis albo komentarz", "Description or comment"], identyfikator: ["Identyfikatory zdjęcia", "Photo IDs"],
  miniatura: ["Miniatura w pliku", "Embedded thumbnail"], wlasne: ["Własne pola dokumentu", "Custom document fields"],
});
// komentarze i śledzone zmiany w treści dokumentu: skrypt ich nie usuwa, tylko mówi (pole „uwagi”)
const konwUwagi = (u) => (u || []).length > 0 && html`<span class="thq-muted">${L(
  `W treści zostają: ${u.map((x) => x.replace(/^zostało w treści: /, "").replace(/ \(.*\)$/, "")).join(", ")}. Usuń je w edytorze, jeśli plik idzie do kogoś.`,
  "Comments or tracked changes with author names stay in the content. Remove them in the editor before sending.")}</span>`;
// każda informacja w osobnej linii; przy kilku plikach nad nimi nazwa pliku
const konwMeta = (m, nazwa) => html`${nazwa && html`<em>${nazwa}</em>`}${Object.entries(m || {}).map(([k, v]) =>
  html`<span key=${k}>${KONW_META[k] || v.opis}${v.wartosc ? `: ${v.wartosc}` : ""}</span>`)}`;
// „Zmniejsz” bez wybranych opcji: jakość, przy której plik zwykle wyraźnie maleje
const KONW_ZMNIEJSZ = { obraz: 75, wideo: 60, pdf: 50, audio: 40 };

// „1 plik”, „3 pliki”, „5 plików”, „22 pliki”
function konwPlikow(n) {
  if (!isPL()) return `${n} ${n === 1 ? "file" : "files"}`;
  const d = n % 10, s = n % 100;
  return `${n} ${n === 1 ? "plik" : d >= 2 && d <= 4 && (s < 12 || s > 14) ? "pliki" : "plików"}`;
}

function konwWspolneCele(lista) {
  if (!lista.length) return [];
  const reszta = lista.slice(1).map((f) => new Set((f.cele || []).map((c) => c.format)));
  return (lista[0].cele || []).filter((c) => reszta.every((s) => s.has(c.format)));
}

function Konwerter({ onOpenFile }) {
  const [pliki, setPliki] = useState([]);       // [{name, size, path, format, nazwa, grupa, cele}]
  const [etap, setEtap] = useState("start");    // start | wysylanie | wybor | praca | gotowe
  const [postep, setPostep] = useState(null);   // {nr, z, ulamek}
  const [opcje, setOpcje] = useState({ rozmiar: "", jakosc: "", strony: "" });
  const [zadanie, setZadanie] = useState(null);
  const [blad, setBlad] = useState(null);
  const [drag, setDrag] = useState(false);
  const fileRef = useRef(null);
  const zyje = useRef(true);
  useEffect(() => () => { zyje.current = false; }, []);

  const reset = () => { setPliki([]); setEtap("start"); setZadanie(null); setBlad(null); setPostep(null); };

  async function dodaj(lista) {
    const files = Array.from(lista || []);
    if (!files.length) return;
    setBlad(null); setZadanie(null); setEtap("wysylanie");
    const gotowe = [];
    try {
      for (let i = 0; i < files.length; i++) {
        setPostep({ nr: i + 1, z: files.length, ulamek: 0, nazwa: files[i].name });
        const wpis = await api.konwUpload(files[i], (u) => zyje.current && setPostep({ nr: i + 1, z: files.length, ulamek: u, nazwa: files[i].name }));
        const info = await api.konwCele(wpis.path);
        gotowe.push({ ...wpis, ...info });
      }
      if (!zyje.current) return;
      setPliki(gotowe); setEtap("wybor");
    } catch (e) {
      if (!zyje.current) return;
      setBlad(e.message || String(e));
      setPliki(gotowe); setEtap(gotowe.length ? "wybor" : "start");
    } finally {
      if (zyje.current) setPostep(null);
    }
  }

  async function zamien(na, extra) {
    setBlad(null);
    const body = { paths: pliki.map((f) => f.path), na, ...extra };
    if (opcje.rozmiar) body.rozmiar = opcje.rozmiar;
    if (opcje.jakosc && body.jakosc == null) body.jakosc = Number(opcje.jakosc);
    if (opcje.strony.trim()) body.strony = opcje.strony.trim();
    try {
      let job = await api.konwStart(body);
      setZadanie(job); setEtap("praca");
      while (zyje.current && (job.state === "queued" || job.state === "running")) {
        await new Promise((r) => setTimeout(r, 1000));
        job = await api.konwJob(job.id);
        if (zyje.current) setZadanie(job);
      }
      if (!zyje.current) return;
      if (job.state === "error") { setBlad(job.error); setEtap("wybor"); } else setEtap("gotowe");
    } catch (e) {
      if (zyje.current) { setBlad(e.message || String(e)); setEtap("wybor"); }
    }
  }

  const onDrop = (e) => {
    e.preventDefault(); setDrag(false);
    if (etap === "wysylanie" || etap === "praca") return;
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) dodaj(e.dataTransfer.files);
  };
  const onDragOver = (e) => {
    if (e.dataTransfer && Array.from(e.dataTransfer.types || []).includes("Files")) { e.preventDefault(); setDrag(true); }
  };

  const cele = konwWspolneCele(pliki);
  const grupy = [];
  for (const c of cele) {
    const g = grupy.find((x) => x.grupa === c.grupa);
    if (g) g.cele.push(c); else grupy.push({ grupa: c.grupa, cele: [c] });
  }
  const jedenFormat = pliki.length && pliki.every((f) => f.format === pliki[0].format) ? pliki[0] : null;
  const moznaZmniejszyc = jedenFormat && KONW_ZMNIEJSZ[jedenFormat.grupa] != null;
  const moznaPolaczyc = pliki.length > 1 && pliki.every((f) => f.format === "pdf" || (f.cele || []).some((c) => c.format === "pdf"));
  const zPdf = pliki.some((f) => f.format === "pdf");
  const moznaCzyscic = pliki.length > 0 && pliki.every((f) => f.czysc);
  const zMetadanymi = pliki.filter((f) => f.metadane && Object.keys(f.metadane).length);
  const zUwagami = pliki.filter((f) => (f.uwagi || []).length);
  const dokumenty = zMetadanymi.some((f) => ["pdf", "dokument", "arkusz", "prezentacja"].includes(f.grupa));
  const czyszczenie = zadanie && zadanie.mode === "metadane";
  const wybierz = (e) => { e.target.files && dodaj(e.target.files); e.target.value = ""; };
  const sekundy = zadanie && zadanie.started ? Math.max(0, Math.round(Date.now() / 1000 - zadanie.started)) : 0;

  return html`<section class=${cx("thq-konw", drag && "is-drop")} aria-label=${L("Konwerter plików", "File converter")}
      onDragOver=${onDragOver} onDragLeave=${(e) => e.currentTarget === e.target && setDrag(false)} onDrop=${onDrop}>
    <h2 class="thq-h2">${L("Konwerter", "Converter")}</h2>
    <input ref=${fileRef} type="file" multiple hidden onChange=${wybierz}/>
    ${etap === "start" && html`<button type="button" class="thq-konw-drop" onClick=${() => fileRef.current && fileRef.current.click()}>
      <strong>${L("Upuść plik albo kliknij", "Drop a file or click")}</strong>
      <span class="thq-muted">${L("Zdjęcie (też HEIC z iPhone'a), film, dźwięk, PDF, Word. Zamiana na serwerze, plik nigdzie nie wychodzi. Usuwa też metadane (GPS, telefon, autor, firma).",
        "Photo (iPhone HEIC too), video, audio, PDF, Word. Converted on the server, the file goes nowhere else. Also strips metadata (GPS, phone, author, company).")}</span>
    </button>`}
    ${etap === "wysylanie" && postep && html`<div class="thq-konw-stan">
      <p>${L("Wysyłam", "Uploading")} ${postep.z > 1 ? `${postep.nr}/${postep.z} ` : ""}<strong>${postep.nazwa}</strong>…</p>
      <div class="thq-progress" role="progressbar" aria-valuenow=${Math.round(100 * postep.ulamek)} aria-valuemin="0" aria-valuemax="100">
        <span style=${{ width: `${Math.round(100 * postep.ulamek)}%` }}></span></div>
    </div>`}
    ${pliki.length > 0 && etap !== "wysylanie" && html`<div class="thq-chips thq-konw-pliki">
      ${pliki.map((f) => html`<span key=${f.path} class="thq-chip" title=${f.path}><em>${f.name}</em> ${f.nazwa} · ${bytes(f.size)}</span>`)}
      ${etap !== "praca" && html`<button type="button" class="thq-chips-toggle" onClick=${reset}>${L("Inny plik", "Other file")}</button>`}
    </div>`}
    ${etap === "wybor" && zMetadanymi.length > 0 && html`<div class="thq-konw-meta" role="note">
      <strong>${L("W pliku są dane o Tobie", "The file carries data about you")}</strong>
      ${zMetadanymi.slice(0, 5).map((f) => html`<p key=${f.path}>${konwMeta(f.metadane, pliki.length > 1 && f.name)}</p>`)}
      ${zMetadanymi.length > 5 && html`<p class="thq-muted">${L(`…i ${zMetadanymi.length - 5} więcej.`, `…and ${zMetadanymi.length - 5} more.`)}</p>`}
      <span class="thq-muted">${dokumenty
        ? L("Znikną po „Usuń metadane”.", "They go away with “Remove metadata”.")
        : L("Znikną po „Usuń metadane” albo zamianie na inny format.", "They go away with “Remove metadata” or a conversion to another format.")}</span>
    </div>`}
    ${etap === "wybor" && zUwagami.length > 0 && html`<div class="thq-konw-meta" role="note">
      ${zUwagami.slice(0, 5).map((f) => html`<p key=${f.path}>${pliki.length > 1 && html`<em>${f.name}</em>`}${konwUwagi(f.uwagi)}</p>`)}
    </div>`}
    ${etap === "wybor" && html`<div class="thq-konw-wybor">
      <div class="thq-konw-opcje">
        <label>${L("Rozmiar", "Size")} <select value=${opcje.rozmiar} onChange=${(e) => setOpcje({ ...opcje, rozmiar: e.target.value })}>
          ${KONW_ROZMIARY.map(([v, pl, en]) => html`<option key=${v} value=${v}>${L(pl, en)}</option>`)}</select></label>
        <label>${L("Jakość", "Quality")} <select value=${opcje.jakosc} onChange=${(e) => setOpcje({ ...opcje, jakosc: e.target.value })}>
          ${KONW_JAKOSC.map(([v, pl, en]) => html`<option key=${v} value=${v}>${L(pl, en)}</option>`)}</select></label>
        ${zPdf && html`<label>${L("Strony", "Pages")} <input type="text" size="7" placeholder="1-3,5" value=${opcje.strony}
          onInput=${(e) => setOpcje({ ...opcje, strony: e.target.value })}/></label>`}
      </div>
      ${grupy.length === 0 && !moznaPolaczyc && html`<p class="thq-muted">${L("Tego pliku nie umiem zamienić na nic innego.", "This file cannot be converted to anything else.")}</p>`}
      ${grupy.map((g) => html`<div key=${g.grupa} class="thq-konw-grupa">
        <span class="thq-muted">${KONW_GRUPY[g.grupa] || g.grupa}</span>
        ${g.cele.map((c) => html`<button key=${c.format} type="button" class="thq-act-btn" onClick=${() => zamien(c.format)}
          title=${`${c.opis} · ${c.trasa.join(" → ")}`}>${c.nazwa}</button>`)}
      </div>`)}
      ${(moznaZmniejszyc || moznaPolaczyc || moznaCzyscic) && html`<div class="thq-konw-grupa">
        <span class="thq-muted">${L("Inne", "Other")}</span>
        ${moznaZmniejszyc && html`<button type="button" class="thq-act-btn"
          title=${L("Ten sam format, mniejszy plik (rozmiar i jakość z opcji)", "Same format, smaller file (size and quality from options)")}
          onClick=${() => zamien(jedenFormat.format, opcje.rozmiar || opcje.jakosc ? {} : { jakosc: KONW_ZMNIEJSZ[jedenFormat.grupa] })}>
          ${L("Zmniejsz", "Shrink")} ${jedenFormat.nazwa}</button>`}
        ${moznaPolaczyc && html`<button type="button" class="thq-act-btn" onClick=${() => zamien("pdf", { polacz: true })}>
          ${L("Połącz w jeden PDF", "Merge into one PDF")}</button>`}
        ${moznaCzyscic && html`<button type="button" class="thq-act-btn" onClick=${() => zamien("", { usun_metadane: true })}
          title=${L("Ten sam plik bez miejsca GPS, telefonu, dat i opisów; obraz i dźwięk bez zmian", "Same file without GPS location, phone, dates and descriptions; picture and sound unchanged")}>
          ${L("Usuń metadane", "Remove metadata")}</button>`}
      </div>`}
    </div>`}
    ${etap === "praca" && html`<p class="thq-konw-stan" role="status">
      ${zadanie && zadanie.state === "queued" ? L("Czekam na poprzednią zamianę…", "Waiting for the previous conversion…")
        : czyszczenie ? L(`Usuwam metadane… ${sekundy} s`, `Removing metadata… ${sekundy} s`)
        : L(`Zamieniam na ${(zadanie && zadanie.na || "").toUpperCase()}… ${sekundy} s`, `Converting to ${(zadanie && zadanie.na || "").toUpperCase()}… ${sekundy} s`)}
    </p>`}
    ${etap === "gotowe" && zadanie && html`<div class="thq-konw-wynik">
      <p class="thq-ok">✓ ${L("Gotowe", "Done")}: ${bytes(zadanie.before)} → ${bytes(zadanie.after)}</p>
      ${zadanie.removed && html`<div class="thq-konw-meta is-ok">
        ${zadanie.removed.some((r) => Object.keys(r.metadane || {}).length) && html`<strong>${L("Usunięte", "Removed")}</strong>`}
        ${zadanie.removed.slice(0, 5).map((r) => html`<p key=${r.name}>${Object.keys(r.metadane || {}).length
          ? konwMeta(r.metadane, zadanie.removed.length > 1 && r.name)
          : html`${zadanie.removed.length > 1 && html`<em>${r.name}</em>`}<span>${r.count
            ? L(`Tylko wpisy techniczne: ${r.count}`, `Technical entries only: ${r.count}`)
            : L("W pliku nie było metadanych.", "The file had no metadata.")}</span>`}${konwUwagi(r.uwagi)}</p>`)}
        ${zadanie.removed.length > 5 && html`<p class="thq-muted">${L(`…i ${zadanie.removed.length - 5} więcej.`, `…and ${zadanie.removed.length - 5} more.`)}</p>`}
        <span class="thq-muted">${L("Sprawdzone po czyszczeniu: w metadanych nic o Tobie nie zostało.", "Checked after cleaning: nothing about you is left in the metadata.")}</span></div>`}
      ${zadanie.note && html`<p class="thq-muted">${L("Wynik nie jest mniejszy od oryginału: zostaw oryginał.", "The result is not smaller than the original: keep the original.")}</p>`}
      ${zadanie.zip && html`<p><button type="button" class="thq-act-btn is-run" onClick=${() => downloadFile(zadanie.zip).catch((e) => setBlad(e.message))}>
        ${L("Pobierz wszystko", "Download all")} (ZIP, ${konwPlikow(zadanie.files.length)})</button></p>`}
      <ul class="thq-list thq-konw-lista">${(zadanie.files || []).slice(0, 30).map((f) => html`<li key=${f.path}>
        <button type="button" class="thq-link" onClick=${() => onOpenFile && onOpenFile(f)} title=${L("Podgląd", "Preview")}>${f.name}</button>
        <span class="thq-muted"> ${bytes(f.size)}</span>
        <button type="button" class=${cx("thq-act-btn", !zadanie.zip && "is-run")} onClick=${() => downloadFile(f).catch((e) => setBlad(e.message))}>${L("Pobierz", "Download")}</button>
      </li>`)}</ul>
      ${(zadanie.files || []).length > 30 && html`<p class="thq-muted">${L(`…i ${zadanie.files.length - 30} więcej w ZIP-ie.`, `…and ${zadanie.files.length - 30} more in the ZIP.`)}</p>`}
      ${(zadanie.errors || []).map((x) => html`<p key=${x.name} class="thq-error">${x.name}: ${x.error}</p>`)}
      <p><button type="button" class="thq-chips-toggle" onClick=${() => { setEtap("wybor"); setZadanie(null); }}>${L("Ten sam plik na inny format", "Same file, another format")}</button>
        ${" "}<button type="button" class="thq-chips-toggle" onClick=${reset}>${L("Nowy plik", "New file")}</button></p>
    </div>`}
    ${blad && html`<p class="thq-error" role="alert">${blad}</p>`}
  </section>`;
}
