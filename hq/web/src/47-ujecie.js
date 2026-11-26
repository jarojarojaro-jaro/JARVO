// „Edytuj ujęcie” w edytorze filmu: klip, którego obraz powstał ze strony animacji (projekt.py z-kodu --strona).
// Pola z parametry.json strony (z `czas` na odcinku ujęcia i wspólne bez `czas`; bez przypisań wszystkie), podgląd na
// żywo chwili ujęcia (przewijanie tylko w jego zakresie osi strony) i „Zastosuj w filmie”: serwer zapisuje parametry,
// renderuje tylko ten odcinek strony (projekt.py popraw-ujecie, postęp z /edit/job) i podmienia obraz klipu. Edytor
// wczytuje potem projekt jako zwykły krok, więc „Cofnij” wraca do poprzedniego pliku ujęcia.

// Odcinek osi strony [od, do] klipu (jak edytor.zakres_strony); null = projekt nie zna strony albo klip ma inne źródło.
function ujZakres(P, c) {
  const zk = (P && P.zKodu) || {};
  const uj = zk.ujecia || {};
  if (!(zk.strona && zk.strona.plik) || !c || c.kind !== "video" || !Object.prototype.hasOwnProperty.call(uj, c.src)) return null;
  const od = +uj[c.src] + +c.in;
  if (!Number.isFinite(od)) return null;
  return [Math.round(od * 1000) / 1000, Math.round((od + +c.out - +c.in) * 1000) / 1000];
}

// Pola strony dla ujęcia: `wlasne` (czas pola zachodzi na odcinek ujęcia), `wspolne` (bez czasu: kolory marki, tempo);
// strona bez żadnego `czas` → wszystkie pola jako wspólne.
function ujPola(pola, zakres) {
  const przypisane = pola.some((p) => p.czas);
  if (!przypisane) return { wlasne: [], wspolne: pola, przypisane };
  const [od, doS] = zakres;
  return { wlasne: pola.filter((p) => p.czas && p.czas[0] < doS && p.czas[1] > od), wspolne: pola.filter((p) => !p.czas), przypisane };
}

function UjecieStudio({ P, c, nr, onClose, onApply, onDone }) {
  const me = useRef({});
  const frameRef = useRef(null);
  const [od, doS] = ujZakres(P, c);
  const strona = P.zKodu.strona.plik;
  const fps = +(P.canvas || {}).fps || 30;
  const [info, setInfo] = useState(null);
  const [err, setErr] = useState(null);
  const [vals, setVals] = useState({});
  const [base, setBase] = useState({});            // wartości, z którymi powstał obecny obraz klipu
  const [playing, setPlaying] = useState(false);
  const [job, setJob] = useState(null);
  const valsRef = useRef({}), play = useRef({ raf: 0, t0: 0, s0: 0 });
  valsRef.current = vals;
  const { ready, pageErr, t, tRef, seekTo } = useAnimMost(frameRef, valsRef, od + (doS - od) / 2);
  const running = !!job && job.state === "running";

  useEffect(() => { MODAL_STACK.push(me.current); return () => { const i = MODAL_STACK.indexOf(me.current); if (i >= 0) MODAL_STACK.splice(i, 1); }; }, []);
  useEffect(() => {
    let alive = true;
    api.animInfo(strona).then((d) => {
      if (!alive) return;
      const teraz = anValuesOf(d.parametry && d.parametry.pola);
      const uzyte = (P.zKodu.parametry || {})[c.src] || {};
      const v = { ...teraz, ...Object.fromEntries(Object.entries(uzyte).filter(([k]) => k in teraz)) };
      valsRef.current = v;
      setInfo({ ...d, teraz }); setVals(v); setBase(v);
    }).catch((e) => alive && setErr(e.message || String(e)));
    return () => { alive = false; cancelAnimationFrame(play.current.raf); };
  }, [strona, c.src]);

  const stop = () => { cancelAnimationFrame(play.current.raf); setPlaying(false); };
  const start = () => {
    if (!ready) return;
    const P0 = play.current;
    P0.t0 = performance.now(); P0.s0 = tRef.current >= doS - 0.02 ? od : tRef.current;
    setPlaying(true);
    const step = (now) => {
      let x = P0.s0 + (now - P0.t0) / 1000;
      if (x >= doS) { x = od; P0.s0 = od; P0.t0 = now; }          // pętla w zakresie ujęcia
      seekTo(x);
      P0.raf = requestAnimationFrame(step);
    };
    P0.raf = requestAnimationFrame(step);
  };
  const toggle = () => (playing ? stop() : start());
  const change = (k, v) => { const n = { ...valsRef.current, [k]: v }; valsRef.current = n; setVals(n); seekTo(tRef.current, true); };
  const close = () => { if (!running) { stop(); onClose(); } };

  useEffect(() => {
    const onKey = (e) => {
      if (MODAL_STACK[MODAL_STACK.length - 1] !== me.current) return;
      const tag = (e.target && e.target.tagName) || "";
      if (e.key === "Escape") { e.preventDefault(); close(); return; }
      if (/INPUT|TEXTAREA|SELECT/.test(tag)) return;
      if (e.key === " ") { e.preventDefault(); toggle(); }
      else if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault(); stop();
        seekTo(Math.min(doS, Math.max(od, tRef.current + (e.key === "ArrowLeft" ? -1 : 1) * (e.shiftKey ? 1 : 1 / fps))));
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  const pola = (info && info.parametry && info.parametry.pola) || [];
  const { wlasne, wspolne, przypisane } = ujPola(pola, [od, doS]);
  const widoczne = [...wlasne, ...wspolne];
  const zmiany = widoczne.filter((p) => !anSame(vals[p.klucz], base[p.klucz]));
  async function apply() {
    if (!zmiany.length || running) return;
    stop();
    setJob({ state: "running", progress: 0 });
    try {
      // do parametry.json tylko to, czym strona różni się od obrazu tego ujęcia
      const wartosci = Object.fromEntries(widoczne.filter((p) => !anSame(vals[p.klucz], info.teraz[p.klucz])).map((p) => [p.klucz, vals[p.klucz]]));
      let j = await onApply(wartosci);
      setJob(j);
      while (j.state === "running") { await edSleep(500); j = await api.editJob(j.id); setJob(j); }
      await onDone(j);                                  // także błąd albo przerwanie: edytor znów śledzi zmiany projektu
    } catch (e) { onDone(null); setJob({ state: "error", error: e.message || String(e) }); }
  }

  const shell = (body) => html`<div class="thq-ed thq-an" role="dialog" aria-modal="true" aria-label=${L("Edytuj ujęcie", "Edit shot")}>${body}</div>`;
  if (err) return shell(html`<div class="thq-ed-msg"><p class="thq-ed-bad">${err}</p><button type="button" class="thq-ed-btn" onClick=${onClose}>${L("Zamknij", "Close")}</button></div>`);
  if (!info) return shell(html`<div class="thq-ed-msg"><span class="thq-ed-spin"></span></div>`);

  const src = `${location.protocol}//${location.hostname}:${info.podglad.port}${info.podglad.path}`;
  const pct = Math.round(((job && job.progress) || 0) * 100);
  const field = (p) => html`<${AnField} key=${p.klucz} p=${p} value=${vals[p.klucz]} saved=${base[p.klucz]} onChange=${change}/>`;
  return shell(html`
    <header class="thq-ed-top">
      <button type="button" class="thq-ed-ico" disabled=${running} onClick=${close} aria-label=${L("Wróć do edytora", "Back to the editor")} title=${L("Wróć do edytora", "Back to the editor")}>${ED_ICON.back}</button>
      <strong class="thq-ed-title" title=${strona}>${L(`Ujęcie ${nr}`, `Shot ${nr}`)} · ${strona.split("/").slice(-2).join("/")}</strong>
      <span class="thq-ed-saved">${zmiany.length ? L(`${zmiany.length} ${plForma(zmiany.length, ["zmiana", "zmiany", "zmian"])}`, `${zmiany.length} changed`) : ""}</span>
      <span class="thq-ed-grow"></span>
      ${widoczne.length > 0 && html`<button type="button" class="thq-ed-btn" disabled=${!zmiany.length || running} onClick=${() => { setVals(base); valsRef.current = base; seekTo(tRef.current, true); }}>${ED_ICON.reset}${L("Przywróć", "Revert")}</button>
        <button type="button" class="thq-ed-btn is-main" disabled=${!zmiany.length || running} onClick=${apply}
          title=${L("Renderuje tylko to ujęcie i podmienia je w filmie", "Renders only this shot and swaps it into the film")}>${running ? "…" : L("Zastosuj w filmie", "Apply to the film")}</button>`}
    </header>
    <div class="thq-an-body">
      <section class="thq-an-main">
        <${AnKadr} src=${src} ready=${ready} frameRef=${frameRef} title=${L("Podgląd ujęcia", "Shot preview")}/>
        ${pageErr && html`<p class="thq-ed-bad">${L("Błąd na stronie:", "Page error:")} ${pageErr}</p>`}
        <div class="thq-an-transport">
          <button type="button" class="thq-ed-play" onClick=${toggle} disabled=${!ready} aria-label=${playing ? L("Pauza", "Pause") : L("Odtwórz", "Play")}>${playing ? ED_ICON.pause : ED_ICON.play}</button>
          <span class="thq-ed-time">${edTC(Math.max(0, t - od))}<span class="thq-ed-dur"> / ${edTC(doS - od)}</span></span>
          <input type="range" class="thq-an-scrub" min=${od} max=${doS} step=${1 / fps} value=${t} disabled=${!ready}
            onInput=${(e) => { stop(); seekTo(+e.target.value); }} aria-label=${L("Czas ujęcia", "Shot time")}/>
          <span class="thq-an-dur">${L("strona", "page")} ${fmtSek(od)} – ${fmtSek(doS)}</span>
        </div>
      </section>
      <aside class="thq-an-side">
        ${!pola.length ? html`<p class="thq-ed-note">${L("Strona nie ma parametry.json: teksty i kolory są w jej kodzie. Poproś Wideografa: „wystaw teksty i kolory planszy jako parametry” (kontrakt HTML, reguła 7).",
          "The page has no parametry.json: texts and colors live in its code. Ask the video agent to expose the board's texts and colors as parameters.")}</p>`
          : html`
            ${wlasne.length > 0 && html`<h4>${L("W tym ujęciu", "In this shot")}</h4>${wlasne.map(field)}`}
            ${przypisane && !wlasne.length && html`<p class="thq-ed-note">${L("Żaden tekst strony nie jest przypisany do tego ujęcia.", "No page text is assigned to this shot.")}</p>`}
            ${wspolne.length > 0 && html`<h4>${przypisane ? L("Cały film", "Whole film") : L("Parametry strony", "Page parameters")}</h4>
              <p class="thq-ed-note">${przypisane ? L("Wspólne dla wszystkich ujęć: zmiana wejdzie tylko do tego ujęcia, inne dostaną ją przy swoim renderze.",
                "Shared by all shots: the change goes into this shot only; other shots get it when they are rendered.")
                : L("Strona nie przypisuje pól do ujęć, więc widać wszystkie; zmiana wejdzie tylko do tego ujęcia.",
                  "The page doesn't assign fields to shots, so all are shown; the change goes into this shot only.")}</p>
              ${wspolne.map(field)}`}`}
        ${pola.length > 0 && ready && !ready.parametry && html`<p class="thq-ed-bad">${L("Strona nie wystawia window.__params: zmiany nie będą widoczne na żywo.", "The page has no window.__params: changes won't show live.")}</p>`}
        ${info.parametry && info.parametry.blad && html`<p class="thq-ed-bad">${info.parametry.blad}</p>`}
        <p class="thq-ed-note">${L(`„Zastosuj w filmie” renderuje tylko to ujęcie (${fmtSek(doS - od)}) i podmienia je na osi; ↶ Cofnij w edytorze wraca do poprzedniej wersji.`,
          `“Apply to the film” renders only this shot (${fmtSek(doS - od)}) and swaps it on the timeline; ↶ Undo in the editor brings the previous version back.`)}</p>
      </aside>
    </div>
    ${job && job.state !== "done" && html`<div class="thq-ed-export" role="status">
      ${running ? html`<p><strong>${L(`Renderuję ujęcie ${pct}%`, `Rendering the shot ${pct}%`)}</strong></p>
          <div class="thq-ed-bar"><i style=${{ width: `${pct}%` }}></i></div>
          ${job.id && html`<button type="button" class="thq-ed-btn" onClick=${() => api.editCancel(job.id).catch(() => {})}>${L("Przerwij", "Cancel")}</button>`}`
        : html`<p class="thq-ed-bad">${job.state === "cancelled" ? L("Przerwano: ujęcie zostało jak było.", "Cancelled: the shot stays as it was.")
            : `${L("Render ujęcia nie wyszedł", "The shot render failed")}: ${job.error || ""}`}</p>
          <button type="button" class="thq-ed-btn" onClick=${() => setJob(null)}>OK</button>`}
    </div>`}`);
}
