// ------------------------------------------------------------------ edytor: menu Audio (jak w CapCut)
// Efekty i Muzyka z biblioteki CC0 (scripts/dzwieki.py, odsłuch przed dodaniem), muzyka ze skarbca i z katalogu filmu,
// Wyodrębnij (dźwięk innego filmu), Lektor (Edge TTS, ten sam co film.py Wideografa), Nagraj (mikrofon przez HTTPS;
// bez HTTPS wgranie notatki głosowej). Każda droga kończy się plikiem obok filmu (dzwieki/, lektor/) i wywołaniem
// onAdd(opis pliku, głośność, start): element audio na osi. Wideograf ma to samo w projekt.py (dzwieki, dodaj-dzwiek,
// wyodrebnij, lektor), a prośba z edytora („Poproś agenta”) wymienia te polecenia.
const AUDIO_ZAKLADKI = [["efekty", "Efekty", "Sounds"], ["muzyka", "Muzyka", "Music"], ["wyodrebnij", "Wyodrębnij", "Extract"],
  ["lektor", "Lektor", "Voice"], ["nagraj", "Nagraj", "Record"]];
// te same głosy co edytor.GLOSY (serwer odrzuca inne)
const AUDIO_GLOSY = [["pl-PL-MarekNeural", "Marek (PL)", "Marek (PL)"], ["pl-PL-ZofiaNeural", "Zofia (PL)", "Zofia (PL)"],
  ["en-US-AndrewMultilingualNeural", "Andrew (wielojęzyczny)", "Andrew (multilingual)"],
  ["en-US-AvaMultilingualNeural", "Ava (wielojęzyczna)", "Ava (multilingual)"],
  ["de-DE-SeraphinaMultilingualNeural", "Seraphina (wielojęzyczna)", "Seraphina (multilingual)"]];
const AUDIO_GLOSNOSC_PODKLADU = 0.3;   // podkład pod mową (jak projekt.py dodaj-dzwiek)
const audioKatalog = { v: null, p: null };
const audioUrls = new Map();           // id z biblioteki albo ścieżka → object URL (odsłuch bez ponownego pobierania)

function wczytajKatalog() {
  if (audioKatalog.v) return Promise.resolve(audioKatalog.v);
  if (!api.editDzwieki) return Promise.resolve({ kategorie: [], dzwieki: [] });
  audioKatalog.p = audioKatalog.p || api.editDzwieki().then((k) => (audioKatalog.v = k)).finally(() => { audioKatalog.p = null; });
  return audioKatalog.p;
}

// Odsłuch jednego dźwięku naraz: drugi klik zatrzymuje, inny dźwięk przerywa poprzedni.
function useOdsluch() {
  const [gra, setGra] = useState(null);
  const ref = useRef(null);
  const stop = () => { if (ref.current) ref.current.pause(); ref.current = null; setGra(null); };
  useEffect(() => () => { if (ref.current) ref.current.pause(); }, []);
  const graj = async (klucz, pobierz) => {
    if (gra === klucz) { stop(); return; }
    stop();
    setGra(klucz);
    try {
      let url = audioUrls.get(klucz);
      if (!url) { url = URL.createObjectURL(await pobierz()); audioUrls.set(klucz, url); }
      const a = new Audio(url);
      ref.current = a;
      a.onended = () => { if (ref.current === a) { ref.current = null; setGra(null); } };
      await a.play();
    } catch (_) { setGra((g) => (g === klucz ? null : g)); }
  };
  return { gra, graj, stop };
}

const fmtDl = (s) => (s >= 60 ? `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}` : `${(+s).toFixed(s < 10 ? 1 : 0)} s`);

function AudioMenu({ path, media, start, onAdd, onUploadAdd, wgrajFilm, top }) {
  const [tab, setTab] = useState("efekty");
  const [kat, setKat] = useState(audioKatalog.v);
  const [grupa, setGrupa] = useState(null);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(null);
  const [err, setErr] = useState("");
  const [skarbiec, setSkarbiec] = useState(null);
  const [tekst, setTekst] = useState("");
  const [glos, setGlos] = useState(AUDIO_GLOSY[0][0]);
  const [tempo, setTempo] = useState(0);
  const [rec, setRec] = useState(null);          // {sek} w trakcie nagrania, {wysyla: true} po zatrzymaniu
  const recRef = useRef(null);
  const ods = useOdsluch();

  useEffect(() => { if (!kat) wczytajKatalog().then(setKat).catch((e) => setErr(e.message || String(e))); }, []);
  useEffect(() => {
    if (tab === "muzyka" && skarbiec === null && api.editMuzyka) api.editMuzyka().then((d) => setSkarbiec(d.muzyka || [])).catch(() => setSkarbiec([]));
    ods.stop();
  }, [tab]);
  useEffect(() => () => { const r = recRef.current; if (r) { r.anuluj = true; if (r.mr.state !== "inactive") r.mr.stop(); } }, []);

  const zrob = async (klucz, fn) => {
    setBusy(klucz); setErr("");
    try { await fn(); } catch (e) { setErr(e.message || String(e)); } finally { setBusy(null); }
  };
  const dodajBib = (d) => zrob(d.id, async () => { ods.stop(); onAdd(await api.editDzwiek(path, d.id), d.kat === "muzyka" ? AUDIO_GLOSNOSC_PODKLADU : 1); });
  const dodajPlik = (m, vol) => { ods.stop(); onAdd(m, vol); };

  const wiersz = (klucz, nazwa, dl, pobierz, dodaj, opis) => html`<li key=${klucz} class="thq-ed-snd">
    <button type="button" class=${cx(ods.gra === klucz && "is-on")} onClick=${() => ods.graj(klucz, pobierz)} title=${L("Odsłuchaj", "Preview")}>
      <span class="thq-ed-mk is-audio">${ods.gra === klucz ? ED_ICON.pause : ED_ICON.play}</span>
      <span class="thq-ed-mn">${nazwa}${opis ? html`<small> · ${opis}</small>` : ""}</span><span class="thq-ed-md">${dl ? fmtDl(dl) : ""}</span></button>
    <button type="button" class="thq-ed-snd-add" disabled=${!!busy} onClick=${dodaj} title=${L("Dodaj na oś od wskaźnika", "Add at the playhead")}
      aria-label=${L(`Dodaj: ${nazwa}`, `Add: ${nazwa}`)}>${busy === klucz ? "…" : ED_ICON.plus}</button></li>`;
  const bib = (d) => wiersz(d.id, isPL() ? d.nazwa : d.en, d.dl, () => api.dzwiekBlob(d.id), () => dodajBib(d));
  const plik = (m, vol, opis) => wiersz(m.path, m.name, m.duration, () => api.fileBlob(m.path), () => dodajPlik(m, vol), opis);
  const lista = (items) => html`<ul class="thq-ed-list thq-ed-snds">${items}</ul>`;

  const efekty = () => {
    const grupy = (kat ? kat.kategorie : []).filter((k) => !k.muzyka);
    const fraza = q.trim().toLowerCase();
    const rows = (kat ? kat.dzwieki : []).filter((d) => d.kat !== "muzyka" && (fraza
      ? `${d.id} ${d.nazwa} ${d.en}`.toLowerCase().includes(fraza) : d.kat === (grupa || (grupy[0] || {}).id)));
    return html`<input class="thq-ed-search" type="search" value=${q} placeholder=${L("Szukaj dźwięku (np. kasa, whoosh, oklaski)", "Search sounds (e.g. cash, whoosh, applause)")}
        onInput=${(e) => setQ(e.target.value)}/>
      ${!fraza && html`<div class="thq-ed-chips">${grupy.map((k) => html`<button type="button" key=${k.id} class=${cx((grupa || (grupy[0] || {}).id) === k.id && "is-on")}
        onClick=${() => setGrupa(k.id)}>${isPL() ? k.nazwa : k.en}</button>`)}</div>`}
      ${!kat ? html`<p class="thq-ed-note">${L("Wczytuję bibliotekę…", "Loading the library…")}</p>`
        : rows.length ? lista(rows.map(bib)) : html`<p class="thq-ed-note">${L("Nic nie pasuje.", "Nothing matches.")}</p>`}
      <p class="thq-ed-note">${L("Dźwięki CC0 (Kenney, Freesound): wolno ich używać także komercyjnie. Dodany efekt gra od wskaźnika.",
        "CC0 sounds (Kenney, Freesound): free for commercial use too. An added sound plays from the playhead.")}</p>`;
  };
  const muzyka = () => {
    const pod = (kat ? kat.dzwieki : []).filter((d) => d.kat === "muzyka");
    const wlasne = media.filter((m) => m.kind === "audio");
    return html`<p class="thq-ed-sub">${L("Podkłady (bez praw autorskich, CC0)", "Backing tracks (royalty-free, CC0)")}</p>
      ${pod.length ? lista(pod.map(bib)) : html`<p class="thq-ed-note">${L("Wczytuję…", "Loading…")}</p>`}
      ${skarbiec && skarbiec.length > 0 && html`<p class="thq-ed-sub">${L("Twoja muzyka i muzyka marek (skarbiec)", "Your music and brand music (vault)")}</p>
        ${lista(skarbiec.map((m) => plik(m, AUDIO_GLOSNOSC_PODKLADU, m.marka)))}`}
      ${wlasne.length > 0 && html`<p class="thq-ed-sub">${L("Z katalogu filmu", "From the film's folder")}</p>${lista(wlasne.map((m) => plik(m, 0.6)))}`}
      <label class="thq-ed-btn is-wide thq-ed-upload">${ED_ICON.upload} ${L("Wgraj plik audio", "Upload an audio file")}
        <input type="file" accept="audio/*" onChange=${(e) => { const f = Array.from(e.target.files || []); e.target.value = ""; zrob("wgraj", () => onUploadAdd(f)); }}/></label>
      <p class="thq-ed-note">${L("Popularnych piosenek nie dodajemy: platformy wyciszają takie filmy. Muzykę marki wrzuć do skarbca (wideo/muzyka albo brands/<marka>/muzyka).",
        "No chart songs: platforms mute such videos. Put brand music in the vault (wideo/muzyka or brands/<brand>/muzyka).")}</p>`;
  };
  const wyodrebnij = () => {
    const filmy = media.filter((m) => m.kind === "video" && m.audio !== false);
    return html`<p class="thq-ed-note">${L("Dźwięk z innego filmu jako osobne audio od wskaźnika. Dźwięk klipu z osi: zaznacz klip i wybierz „Wyodrębnij dźwięk”.",
        "A video's sound as a separate audio from the playhead. For a clip on the timeline: select it and choose “Extract audio”.")}</p>
      ${filmy.length ? html`<ul class="thq-ed-list">${filmy.map((m) => html`<li key=${m.path}><button type="button" disabled=${!!busy}
          onClick=${() => zrob(m.path, async () => onAdd(await api.editWyodrebnij(path, m.path), 1))}>
          <span class="thq-ed-mk">${ED_ICON.film}</span><span class="thq-ed-mn">${m.name}</span><span class="thq-ed-md">${m.duration ? fmtDl(m.duration) : ""}</span>
          <span class="thq-ed-plus">${busy === m.path ? "…" : ED_ICON.plus}</span></button></li>`)}</ul>`
        : html`<p class="thq-ed-note">${L("Brak filmów z dźwiękiem w katalogu.", "No videos with sound in the folder.")}</p>`}
      ${wgrajFilm}`;
  };
  const lektor = () => html`<label>${L("Tekst lektora", "Voice-over text")}
      <textarea rows="4" maxlength="3000" value=${tekst} onInput=${(e) => setTekst(e.target.value)}
        placeholder=${L("Np. Nowa kolekcja już w sklepie. Sprawdź link w opisie!", "E.g. The new collection is in store. Check the link below!")}></textarea></label>
    <label>${L("Głos", "Voice")}<select value=${glos} onChange=${(e) => setGlos(e.target.value)}>
      ${AUDIO_GLOSY.map(([k, pl, en]) => html`<option value=${k}>${isPL() ? pl : en}</option>`)}</select></label>
    <label>${L("Tempo", "Speed")} · ${tempo > 0 ? "+" : ""}${tempo}%<input type="range" min="-30" max="30" step="5" value=${tempo} onInput=${(e) => setTempo(+e.target.value)}/></label>
    <button type="button" class="thq-ed-btn is-main is-wide" disabled=${!!busy || !tekst.trim()}
      onClick=${() => zrob("lektor", async () => onAdd(await api.editLektor(path, tekst, glos, tempo), 1))}>
      ${ED_ICON.speech} ${busy === "lektor" ? L("Tworzę lektora…", "Creating the voice-over…") : L("Utwórz i dodaj od wskaźnika", "Create and add at the playhead")}</button>
    <p class="thq-ed-note">${L("Ten sam lektor co u Wideografa (Edge TTS, bez klucza). Do napisów: zakładka Napisy rozpozna mowę z nagrania.",
      "The same voice as the Video agent (Edge TTS, no key). For captions, the Captions tab recognises the speech.")}</p>`;

  const moznaNagrac = typeof window !== "undefined" && window.isSecureContext && navigator.mediaDevices
    && navigator.mediaDevices.getUserMedia && typeof window.MediaRecorder !== "undefined";
  const nagrywaj = async () => {
    setErr("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      const mr = new MediaRecorder(stream), kawalki = [], od = start, t0 = Date.now();
      const r = { mr, anuluj: false };
      recRef.current = r;
      mr.ondataavailable = (e) => { if (e.data && e.data.size) kawalki.push(e.data); };
      mr.onstop = () => {
        clearInterval(r.timer);
        stream.getTracks().forEach((tr) => tr.stop());
        recRef.current = null;
        if (r.anuluj) return;
        setRec({ wysyla: true });
        zrob("nagranie", async () => onAdd(await api.editNagranie(path, new Blob(kawalki, { type: mr.mimeType || "audio/webm" })), 1, od))
          .finally(() => setRec(null));
      };
      r.timer = setInterval(() => setRec({ sek: (Date.now() - t0) / 1000 }), 250);
      mr.start(250);
      setRec({ sek: 0 });
    } catch (e) { setErr(L("Brak dostępu do mikrofonu: ", "No microphone access: ") + (e.message || String(e))); }
  };
  const nagraj = () => (moznaNagrac ? html`
    ${rec && rec.sek !== undefined
      ? html`<button type="button" class="thq-ed-btn is-wide thq-ed-rec is-on" onClick=${() => recRef.current && recRef.current.mr.stop()}>
          <i class="thq-ed-recdot"></i> ${L("Zatrzymaj", "Stop")} · ${fmtDl(rec.sek)}</button>`
      : html`<button type="button" class="thq-ed-btn is-main is-wide thq-ed-rec" disabled=${!!busy || !!rec} onClick=${nagrywaj}>
          <i class="thq-ed-recdot"></i> ${rec && rec.wysyla ? L("Zapisuję nagranie…", "Saving the recording…") : L("Nagraj lektora", "Record a voice-over")}</button>`}
    <p class="thq-ed-note">${L("Nagranie trafi na oś od miejsca wskaźnika z chwili startu. Słuchawki zmniejszają echo z głośników.",
      "The recording lands on the timeline at the playhead position from when you started. Headphones reduce echo.")}</p>`
    : html`<p class="thq-ed-note is-warn">${L("Mikrofon w przeglądarce działa tylko przez HTTPS (np. Tailscale). Nagraj notatkę głosową w telefonie i wgraj ją tutaj:",
        "The browser microphone needs HTTPS (e.g. Tailscale). Record a voice memo on your phone and upload it here:")}</p>
      <label class="thq-ed-btn is-main is-wide thq-ed-upload">${ED_ICON.upload} ${L("Wgraj nagranie", "Upload a recording")}
        <input type="file" accept="audio/*" capture onChange=${(e) => { const f = Array.from(e.target.files || []); e.target.value = ""; zrob("wgraj", () => onUploadAdd(f)); }}/></label>`);

  const tresc = { efekty, muzyka, wyodrebnij, lektor, nagraj }[tab];
  return html`<div class="thq-ed-form thq-ed-audio">
    ${top}
    <div class="thq-ed-seg">${AUDIO_ZAKLADKI.map(([k, pl, en]) => html`<button type="button" key=${k} class=${cx(tab === k && "is-on")} onClick=${() => setTab(k)}>${isPL() ? pl : en}</button>`)}</div>
    ${err && html`<p class="thq-ed-note is-warn" role="alert">${err}</p>`}
    ${tresc()}
  </div>`;
}
