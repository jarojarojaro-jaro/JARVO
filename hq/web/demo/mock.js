// TARS HQ, tryb demo: symulacja floty w przeglądarce (misja „Ziarno”: otwarcie kawiarni).
// Implementuje ten sam interfejs co prawdziwe API pluginu (window.TARS_HQ_MOCK), bez serwera.
(function () {
  "use strict";
  const FLEET = (window.TARS_HQ_FLEET && window.TARS_HQ_FLEET.agents) || [];
  const now = () => Date.now() / 1000;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  const LABELS = {
    web_search: ["search", "szuka"], web_extract: ["page", "czyta stronę"], terminal: ["terminal", "terminal"],
    read_file: ["file", "czyta"], write_file: ["write", "pisze"], patch: ["write", "poprawia"],
    browser_navigate: ["browser", "otwiera"], browser_vision: ["eye", "patrzy na stronę"], vision_analyze: ["eye", "ogląda obraz"],
    image_generate: ["image", "generuje obraz"], skill_view: ["book", "czyta skill"], memory: ["memory", "zapisuje w pamięci"],
    kanban_create: ["card", "zakłada kartę"], kanban_comment: ["card", "komentuje kartę"], kanban_complete: ["done", "zamyka kartę"],
    kanban_request_review: ["review", "oddaje do oceny"], kanban_unblock: ["card", "odblokowuje kartę"], todo: ["check", "planuje kroki"],
  };
  const label = (tool, detail) => {
    const [icon, verb] = LABELS[tool] || ["tool", tool];
    return { tool, icon, verb, detail: detail || "" };
  };

  // Skrypty pracy: kolejne kroki narzędzi dla kart (detail = argument, który widzi użytkownik).
  const SCRIPTS = {
    research: [
      ["skill_view", "metoda-sherlocka"], ["todo", "4 wątki: lokale, ceny, opinie, trendy"],
      ["web_search", "kawiarnie specialty Kraków Kazimierz 2026"], ["web_search", "ceny flat white Kraków specialty"],
      ["web_extract", "https://www.google.com/maps/search/kawiarnia+specialty+krakow"], ["web_search", "opinie kawiarnia specialty Kraków Stare Miasto"],
      ["web_extract", "https://kawa.example/ranking-krakow-2026"], ["terminal", "python3 sources.py add … --tier B --type dane"],
      ["web_search", "trendy kawiarnie 2026 cold brew tonic"], ["write_file", "out/zrodla.jsonl (14 źródeł)"],
      ["write_file", "out/RAPORT.md"], ["kanban_request_review", "Raport: 11 konkurentów, mediana flat white 17 zł"],
    ],
    landing: [
      ["skill_view", "nowa-strona"], ["read_file", "knowledge/brands/ziarno/BRAND.md"],
      ["terminal", "npm create astro@latest ziarno -- --template minimal"], ["write_file", "src/pages/index.astro"],
      ["write_file", "src/components/Menu.astro"], ["terminal", "node images.cjs assets/ out/img --formats avif,webp"],
      ["terminal", "npm run build"], ["browser_navigate", "http://localhost:4321/"], ["browser_vision", "sprawdza hero na 375 px"],
      ["patch", "src/styles/global.css: kontrast przycisku 4.8:1"], ["terminal", "bash audit.sh http://localhost:4321 out/audyt"],
      ["write_file", "out/RAPORT.md (Lighthouse 98/100/100/100)"], ["kanban_request_review", "Landing gotowy, LCP 1,2 s, CLS 0"],
    ],
    judge_hosting: [
      ["read_file", "references/rubric-tars-reka.md"], ["read_file", "out/porownanie-hostingu.md"],
      ["terminal", "python3 -c 'sprawdza ceny w 3 źródłach'"], ["kanban_complete", "Zatwierdzone: Netlify Free wystarcza"],
    ],
    judge_research: [
      ["read_file", "references/rubric-tars-sherlock.md"], ["read_file", "out/RAPORT.md"], ["web_extract", "losowa próba 3 źródeł"],
      ["kanban_complete", "Zatwierdzone: źródła A/B, pewność wysoka"],
    ],
    judge_landing: [
      ["read_file", "references/rubric-tars-web.md"], ["browser_navigate", "http://localhost:4321/"], ["read_file", "out/audyt/summary.json"],
      ["kanban_complete", "Zatwierdzone: budżety jakości spełnione"],
    ],
    graphics: [
      ["read_file", "knowledge/brands/ziarno/BRAND.md"], ["skill_view", "grafika-social"],
      ["write_file", "grafiki/otwarcie.html"], ["terminal", "node render_html.cjs otwarcie.html out/ig --size 1080x1350 --size 1080x1920"],
      ["image_generate", "zdjęcie: filiżanka flat white na jasnym drewnie, bez tekstu"], ["terminal", "python3 check_media.py out/ --auto"],
      ["vision_analyze", "out/ig-1080x1350.png"], ["kanban_request_review", "3 grafiki IG + 2 stories"],
    ],
    film: [
      ["skill_view", "krotki-film"], ["write_file", "out/wideo/SCENARIUSZ.md (5 scen, hook 1,4 s)"],
      ["terminal", "python3 stock.py szukaj \"barista latte art\" --format 9:16 --arkusz out/wideo/kandydaci-s2.jpg"],
      ["vision_analyze", "out/wideo/kandydaci-s2.jpg"], ["write_file", "out/wideo/src/plan.json"],
      ["terminal", "python3 film.py render out/wideo/src/plan.json --szkic"], ["terminal", "python3 film.py render out/wideo/src/plan.json"],
      ["terminal", "python3 qa_wideo.py out/wideo/otwarcie/otwarcie-9x16.mp4 --platforma ig-reel --lektor --arkusz qa.jpg"],
      ["vision_analyze", "out/wideo/otwarcie/qa.jpg"], ["kanban_request_review", "Reel 20 s: lektor, napisy karaoke, −14 LUFS, ocena 91"],
    ],
    pack: [
      ["terminal", "python3 pack.py missions/M-260926-ziarno --out zlozenie/out"], ["write_file", "zlozenie/out/INDEX.md"],
      ["kanban_request_review", "Pakiet misji: 18 plików"],
    ],
  };

  let S = null;

  function fresh() {
    const t = now();
    const card = (id, title, assignee, status, extra) => ({ id, title, assignee, status, created_at: t - 3600, events: [], ...extra });
    S = {
      t0: t,
      cards: {
        t_c01: card("t_c01", "Brand kit z ziarno-kawa.pl", "tars-web", "done", { completed_at: t - 2400, started_at: t - 3300 }),
        t_c02: card("t_c02", "Research: kawiarnie specialty w Krakowie", "tars-sherlock", "running", { started_at: t - 400, script: "research", step: 3 }),
        t_c03: card("t_c03", "Landing page Ziarno (Astro, PL)", "tars-web", "running", { started_at: t - 200, script: "landing", step: 2 }),
        t_c04: card("t_c04", "Grafiki IG na otwarcie (post 4:5 i story 9:16)", "tars-studio", "blocked",
          { block_kind: "needs_input", reason: "Która data otwarcia na grafikach: 12 czy 19 października?", blocked_at: t - 900 }),
        t_c05: card("t_c05", "Film 20 s na Reels z napisami PL", "tars-wideo", "running", { started_at: t - 150, script: "film", step: 4 }),
        t_c06: card("t_c06", "Złożenie pakietu misji", "tars-reka", "todo", {}),
        t_c07: card("t_c07", "Porównanie hostingu dla strony Ziarno", "tars-reka", "review", { worker: "tars", script: "judge_hosting", step: 1, started_at: t - 60 }),
        t_c08: card("t_c08", "Cennik PDF dla kawiarni", "tars-reka", "done", { completed_at: t - 5000 }),
      },
      activity: {},
      feed: [],
      chats: {},
      tick: 0,
    };
    for (const c of Object.values(S.cards)) c.events.push({ kind: "created", created_at: c.created_at });
    S.cards.t_c04.events.push({ kind: "blocked", created_at: t - 900, payload: { kind: "needs_input", reason: S.cards.t_c04.reason } });
    // historia kroków, żeby panel „Teraz” nie startował pusty
    for (const c of Object.values(S.cards)) {
      if (c.script) {
        S.activity[c.id] = SCRIPTS[c.script].slice(0, c.step).map(([tool, d], i) => ({ ts: t - (c.step - i) * 25, kind: "tool", status: "done", ...label(tool, d) }));
        S.activity[c.id].unshift({ ts: c.started_at, kind: "brief", text: `Karta ${c.id}: ${c.title}. DoD w karcie, wyniki do out/.` });
      }
    }
    pushFeed("t_c01", "completed", "zakończył kartę", "good", t - 2400);
    pushFeed("t_c04", "blocked", "zablokowana", "bad", t - 900);
    pushFeed("t_c07", "review_requested", "oddaje do oceny", "info", t - 80);
  }

  function pushFeed(id, kind, text, tone, ts) {
    const c = S.cards[id];
    S.feed.unshift({ ts: ts || now(), kind, text, tone, task_id: id, title: c.title, agent: kind === "spawned" && c.worker ? c.worker : c.assignee });
    S.feed = S.feed.slice(0, 40);
  }

  function start(id, script, worker) {
    const c = S.cards[id];
    Object.assign(c, { status: worker ? "review" : "running", script, step: 0, started_at: now(), worker: worker || null });
    S.activity[id] = [{ ts: now(), kind: "brief", text: `Karta ${id}: ${c.title}.` }];
    c.events.push({ kind: "spawned", created_at: now() });
    pushFeed(id, "spawned", worker ? "TARS ocenia" : "zaczyna pracę", "neutral");
  }

  function finishStep(c) {
    const steps = SCRIPTS[c.script];
    const [tool, detail] = steps[c.step];
    const list = S.activity[c.id] || (S.activity[c.id] = []);
    const last = list[list.length - 1];
    if (last && last.status === "running") last.status = "done";
    list.push({ ts: now(), kind: "tool", status: "running", ...label(tool, detail) });
    c.step += 1;
    if (c.step < steps.length) return;
    // koniec skryptu
    last && (last.status = "done");
    if (tool === "kanban_request_review") {
      Object.assign(c, { status: "review", worker: null, script: null });
      c.events.push({ kind: "review_requested", created_at: now(), payload: { summary: detail } });
      pushFeed(c.id, "review_requested", "oddaje do oceny", "info");
      const judge = { t_c02: "judge_research", t_c03: "judge_landing" }[c.id];
      if (judge) setTimeout(() => S.cards[c.id].status === "review" && start(c.id, judge, "tars"), 6000);
      if (c.id === "t_c04" || c.id === "t_c05") setTimeout(() => S.cards[c.id].status === "review" && complete(c.id), 7000);
      if (c.id === "t_c06") setTimeout(() => S.cards[c.id].status === "review" && complete(c.id), 7000);
    } else if (tool === "kanban_complete") {
      complete(c.id);
    }
  }

  function complete(id) {
    const c = S.cards[id];
    Object.assign(c, { status: "done", worker: null, script: null, completed_at: now() });
    c.events.push({ kind: "completed", created_at: now() });
    pushFeed(id, "completed", "zakończył kartę", "good");
    if (id === "t_c04" && S.cards.t_c05.status === "ready") setTimeout(() => start("t_c05", "film"), 3000);
    const mission = ["t_c02", "t_c03", "t_c04", "t_c05"];
    if (mission.every((m) => S.cards[m].status === "done") && S.cards.t_c06.status === "todo") {
      S.cards.t_c06.status = "ready";
      setTimeout(() => start("t_c06", "pack"), 2500);
    }
    if (Object.values(S.cards).every((x) => x.status === "done")) setTimeout(fresh, 20000);
  }

  function unblock(id) {
    const c = S.cards[id];
    if (c.status !== "blocked") return;
    c.events.push({ kind: "unblocked", created_at: now() });
    pushFeed(id, "unblocked", "odblokowana", "good");
    start(id, "graphics");
  }

  function tick() {
    S.tick += 1;
    for (const c of Object.values(S.cards)) {
      if (c.script && (c.status === "running" || c.status === "review") && S.tick % (c.worker ? 2 : 3) === 0) finishStep(c);
    }
  }

  fresh();
  setInterval(tick, 1600);

  // ------------------------------------------------------------------ widoki
  const orchestrator = (FLEET.find((a) => a.kind === "orchestrator") || { name: "tars" }).name;

  function cardsOf(name) {
    const out = { running: [], ready: [], review: [], blocked: [], triage: [], done: [], judging: [] };
    for (const c of Object.values(S.cards)) {
      const mine = c.assignee === name;
      if ((c.status === "running" || c.status === "review") && c.worker === name && !mine) out.running.push(c);
      else if (c.status === "running" && mine) out.running.push(c);
      else if (mine && (c.status === "ready" || c.status === "todo")) out.ready.push(c);
      else if (mine && out[c.status]) out[c.status].push(c);
      if (name === orchestrator && c.status === "review") out.judging.push(c);
    }
    return out;
  }

  function statusOf(a, cards) {
    if (cards.running.length) {
      const c = cards.running[0];
      const act = (S.activity[c.id] || []).filter((x) => x.kind === "tool");
      return { status: "working", headline: c.title, task_id: c.id, since: c.started_at, tool: act[act.length - 1] || null };
    }
    if (cards.blocked.length) return { status: "blocked", headline: cards.blocked[0].title, task_id: cards.blocked[0].id, reason: cards.blocked[0].reason };
    if (cards.judging.length) return { status: "judging", headline: `Do oceny: ${cards.judging.length}`, task_id: cards.judging[0].id };
    if (cards.review.length) return { status: "review", headline: cards.review[0].title, task_id: cards.review[0].id };
    if (cards.ready.length) return { status: "queued", headline: `W kolejce: ${cards.ready.length}`, task_id: cards.ready[0].id };
    return { status: "idle", headline: "", task_id: null };
  }

  const brief = (c) => ({ id: c.id, title: c.title, status: c.status, assignee: c.assignee, worker: c.worker || null,
    created_at: c.created_at, started_at: c.started_at, completed_at: c.completed_at, block_kind: c.block_kind || null });

  function state() {
    const t = now();
    const agents = FLEET.map((a) => {
      const cards = cardsOf(a.name);
      return { ...a, ...statusOf(a, cards), counts: { running: cards.running.length, ready: cards.ready.length, review: cards.review.length,
        blocked: cards.blocked.length, judging: cards.judging.length,
        done_today: cards.done.filter((c) => (c.completed_at || 0) > t - 86400).length } };
    });
    const all = Object.values(S.cards);
    const count = (st) => all.filter((c) => st.includes(c.status)).length;
    const mission = ["t_c01", "t_c02", "t_c03", "t_c04", "t_c05", "t_c06"].map((id) => brief(S.cards[id]));
    const extra = all.filter((c) => c.id.startsWith("t_n"));
    return {
      ts: t, board_ok: true, agents,
      board: { triage: 0, ready: count(["ready", "todo"]), running: count(["running"]), review: count(["review"]), blocked: count(["blocked"]),
        done_today: count(["done"]) },
      decisions: all.filter((c) => c.status === "blocked").map((c) => ({ task_id: c.id, title: c.title, assignee: c.assignee, reason: c.reason, since: c.blocked_at })),
      missions: [
        { id: "M-260926-ziarno", title: "Otwarcie kawiarni Ziarno", status: "w toku", cards: mission, missing: [],
          done: mission.filter((c) => c.status === "done").length, total: mission.length },
        ...(extra.length ? [{ id: "M-260926-nowa", title: "Nowe zlecenie z czatu", status: "w toku", cards: extra.map(brief), missing: [],
          done: extra.filter((c) => c.status === "done").length, total: extra.length }] : []),
      ],
      feed: S.feed.slice(0, 30),
    };
  }

  const OUTPUTS = {
    "tars-web": [["ziarno-hero-375.png", "image", "#6B3E26"], ["ziarno-hero-1440.png", "image", "#8C5B35"], ["RAPORT.md", "text"], ["summary.json", "text"]],
    "tars-studio": [["ig-1080x1350.png", "image", "#D96B3C"], ["story-1080x1920.png", "image", "#2F6552"], ["kalendarz.csv", "text"]],
    "tars-sherlock": [["RAPORT.md", "text"], ["zrodla.jsonl", "text"]],
    "tars-reka": [["porownanie-hostingu.md", "text"], ["cennik.pdf", "pdf"]],
    "tars-wideo": [["otwarcie-9x16-miniatura.jpg", "image", "#3B2416"], ["SCENARIUSZ.md", "text"], ["film.json", "text"]],
  };

  function outputs(name) {
    return (OUTPUTS[name] || []).map(([n, kind, color], i) => ({ path: `/opt/data/tars/workspaces/${name}/out/${n}`, name: n, rel: `out/${n}`,
      kind, size: 18000 + i * 7311, mtime: now() - 600 * (i + 1), in_out: true, color }));
  }

  function agent(name) {
    const a = FLEET.find((x) => x.name === name);
    const cards = cardsOf(name);
    const st = statusOf(a, cards);
    const live = cards.running[0];
    return { agent: { ...a, ...st }, cards: Object.fromEntries(Object.entries(cards).map(([k, v]) => [k, v.map(brief)])),
      activity: live ? (S.activity[live.id] || []).slice(-40) : [], outputs: outputs(name),
      stats: { done_7d: cards.done.length + 6, first_pass_7d: cards.done.length + 5, changes_7d: 1 }, ts: now() };
  }

  const SAMPLE_SITE = `<!doctype html><html lang="pl"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Ziarno</title><style>body{margin:0;font:18px/1.6 Georgia,serif;background:#F3E6D3;color:#3B2416}header{padding:72px 24px;background:#6B3E26;color:#F3E6D3;text-align:center}
h1{font-size:64px;margin:0}section{max-width:640px;margin:0 auto;padding:32px 24px}.map{height:180px;background:#ccc;display:grid;place-items:center}
a.btn{display:inline-block;padding:12px 22px;background:#6B3E26;color:#F3E6D3;text-decoration:none;border-radius:6px}</style>
<header><h1>Ziarno</h1><p>Kawa, która ma korzenie.</p></header><section><h2>O nas</h2><p>Specialty coffee na Kazimierzu. Otwarcie 19.10.2026.</p>
<h2>Godziny otwarcia</h2><p>pn–pt 7:30–19:00 · sb–nd 9:00–18:00</p><div class="map">mapa — do osadzenia</div><p><a class="btn" href="#">Zarezerwuj stolik</a></p></section></html>`;

  function parseBrief(body) {
    const keys = { cel: "cel", kontekst: "kontekst", "wejścia": "wejscia", dod: "dod", "wyjścia": "wyjscia", granice: "granice" };
    const out = {};
    let key = "intro";
    for (const line of body.split("\n")) {
      const m = /^\s*\**\s*(cel|kontekst|wejścia|dod|wyjścia|granice)\s*\**\s*:\**\s*(.*)$/i.exec(line);
      if (m) { key = keys[m[1].toLowerCase()]; out[key] = m[2] ? [m[2]] : []; continue; }
      (out[key] = out[key] || []).push(line);
    }
    return Object.fromEntries(Object.entries(out).map(([k, v]) => [k, v.join("\n").trim()]).filter(([, v]) => v));
  }

  function task(id) {
    const c = S.cards[id];
    if (!c) throw new Error("Nie ma takiej karty");
    const web = c.assignee === "tars-web";
    const outName = web ? "index.html" : { "tars-studio": "post-otwarcie-4x5.png", "tars-wideo": "otwarcie-9x16-miniatura.jpg" }[c.assignee] || "raport.md";
    const body = `CEL: ${c.title}.
KONTEKST: „Ziarno” — specialty coffee w Krakowie, otwarcie 19.10.2026. Ton ciepły, rzemieślniczy, bez korpomowy.
WEJŚCIA: brand kit /opt/data/tars/knowledge/brands/ziarno/brand.md; wyniki Sherlocka w ../sherlock/out/.
DoD:
- wynik w out/ zgodny z brand kitem Ziarno (paleta, ton, hasło),
- responsywny, bez błędów w konsoli,
- krótki raport z decyzjami i ryzykami.
WYJŚCIA: out/${outName}
GRANICE: autonomia A1 (bez publikacji i wdrożeń); budżet ~45 min; nie ruszać innych plików.`;
    const done = c.status === "done";
    const kind = web ? "html" : /\.(png|jpg)$/.test(outName) ? "image" : "text";
    const outputs = done ? [{ path: `/opt/data/tars/missions/M-demo/${c.assignee}/out/${outName}`, name: outName, rel: `out/${outName}`,
      kind, size: 14200, mtime: (c.completed_at || now()) - 30, in_out: true, main: true, color: "#6B3E26" }] : [];
    return { ...brief(c), body, brief: parseBrief(body), expected: [`out/${outName}`], outputs,
      events: c.events.slice(), comments: c.comments || [],
      result: done ? `Gotowe: ${outName} w out/. Sprawdzone na 375/768/1440 px, bez poziomego przewijania, konsola czysta.` : null };
  }

  function svgFor(name, color) {
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1350" viewBox="0 0 1080 1350"><rect width="1080" height="1350" fill="${color || "#6B3E26"}"/>
      <circle cx="540" cy="560" r="260" fill="#F3E6D3"/><circle cx="540" cy="560" r="190" fill="#8C5B35"/><circle cx="540" cy="560" r="120" fill="#C89B63"/>
      <text x="540" y="1040" font-family="Georgia,serif" font-size="110" fill="#F3E6D3" text-anchor="middle">Ziarno</text>
      <text x="540" y="1150" font-family="Arial,sans-serif" font-size="48" fill="#F3E6D3" text-anchor="middle">Otwarcie 12.10 · Kazimierz</text></svg>`;
    return new Blob([svg], { type: "image/svg+xml" });
  }

  async function fileBlob(path) {
    const name = path.split("/").pop();
    const all = Object.values(OUTPUTS).flat();
    const hit = all.find(([n]) => n === name);
    if (hit && hit[1] === "image") return svgFor(name, hit[2]);
    if (name.endsWith(".html")) return new Blob([SAMPLE_SITE], { type: "text/plain" });
    if (/\.(png|jpg)$/.test(name)) return svgFor(name, "#6B3E26");
    return new Blob([`# ${name}\n\nPrzykładowa zawartość w trybie demo.\n\n- Konkurencja: 11 kawiarni specialty w promieniu 1,5 km\n- Mediana ceny flat white: 17 zł\n- Luka: brak śniadań wegańskich przed 8:00\n`], { type: "text/plain" });
  }

  // ----------------------------------------------------------------------- czat
  function chatOf(name) { return S.chats[name] || (S.chats[name] = []); }

  function reply(name, msg) {
    const dec = /^Decyzja do karty (t_\w+)/.exec(msg);
    if (name === orchestrator && dec) {
      const answer = msg.split("): ").slice(1).join("): ") || "ok";
      return { tools: [["kanban_comment", `${dec[1]}: ${answer}`], ["memory", "decyzja: data otwarcia"], ["kanban_unblock", dec[1]]],
        text: `Przyjąłem: **${answer}**. Zapisałem decyzję w dzienniku misji i odblokowałem kartę. Studio rusza z grafikami, dam znać po ocenie.`,
        after: () => unblock(dec[1]) };
    }
    if (name === orchestrator) {
      const topic = msg.replace(/\s+/g, " ").slice(0, 60);
      return { tools: [["todo", "rozbicie celu na karty"], ["kanban_create", `Research: ${topic}`], ["kanban_create", `Grafika: ${topic}`]],
        text: `Zrozumiałem cel. Założyłem dwie karty: **Sherlock** robi research, **Studio** przygotuje grafikę po jego wynikach. Kryteria gotowości są w kartach. Odezwę się, gdy będzie wynik albo decyzja dla Ciebie.`,
        after: () => {
          const t = now(), n = Object.keys(S.cards).length;
          S.cards[`t_n${n}`] = { id: `t_n${n}`, title: `Research: ${topic}`, assignee: "tars-sherlock", status: "ready", created_at: t, events: [{ kind: "created", created_at: t }] };
          S.cards[`t_n${n + 1}`] = { id: `t_n${n + 1}`, title: `Grafika: ${topic}`, assignee: "tars-studio", status: "todo", created_at: t, events: [{ kind: "created", created_at: t }] };
          pushFeed(`t_n${n}`, "created", "nowa karta", "neutral");
        } };
    }
    const byAgent = {
      "tars-sherlock": [[["web_search", msg.slice(0, 50)]], "Sprawdziłem wstępnie. Mam 3 źródła pierwotne, ale zanim dam liczby, potwierdzę je krzyżowo. Jeśli to ma być pełne śledztwo, zleć je przez TARS-a, wtedy dostaniesz raport z cytatami."],
      "tars-web": [[["read_file", "knowledge/brands/ziarno/BRAND.md"]], "Mogę to zrobić w ramach landingu Ziarno. Budżety jakości zostają: LCP poniżej 2,5 s, CLS poniżej 0,1, Lighthouse 90+. Wdrożenie na produkcję tylko po Twojej zgodzie."],
      "tars-studio": [[["skill_view", "formaty-platform"]], "Zrobię to w formatach 4:5 i 9:16, w kolorach z brand kitu Ziarno. Publikacja dopiero po Twojej akceptacji. Pierwsza wersja:\n\nMEDIA:/opt/data/tars/workspaces/tars-studio/out/ig-1080x1350.png\nMEDIA:/opt/data/tars/workspaces/tars-studio/out/kalendarz.csv\n\nPodgląd na żywo: http://localhost:9120/demo/index.html, pliki w `/opt/data/tars/workspaces/tars-studio/out/ig-1080x1350.png`."],
      "tars-reka": [[["terminal", "python3 -c '…'"]], "Zrobione, wynik w out/. Jeśli to część misji, TARS dopnie to do pakietu końcowego."],
      "tars-wideo": [[["skill_view", "krotki-film"]], "Zrobię to jako reels 9:16: hook do 2 s, polski lektor, napisy karaoke i muzyka pod głosem. Najpierw szkic do oceny rytmu, potem finał i kontrola jakości. Nic nie publikuję bez Twojej zgody."],
    };
    const [tools, text] = byAgent[name] || [[], "Jasne."];
    return { tools, text };
  }

  async function* send(name, msg, extra) {
    if (extra && extra.attachments) msg = [msg, ...extra.attachments.map((a) => `📎 ${a}`)].filter(Boolean).join("\n");
    const chat = chatOf(name);
    chat.push({ role: "user", text: msg, ts: now() });
    const r = reply(name, msg);
    yield { event: "run.started", data: {} };
    await sleep(500);
    const used = [];
    for (const [tool, detail] of r.tools) {
      yield { event: "tool.started", data: { tool_name: tool, preview: detail } };
      await sleep(700);
      yield { event: "tool.completed", data: { tool_name: tool } };
      used.push(label(tool, detail));
    }
    let acc = "";
    for (const word of r.text.split(/(\s+)/)) {
      acc += word;
      yield { event: "assistant.delta", data: { delta: word } };
      await sleep(28);
    }
    chat.push({ role: "assistant", text: acc, tools: used, ts: now() });
    if (r.after) r.after();
    yield { event: "assistant.completed", data: { content: acc } };
    yield { event: "run.completed", data: {} };
  }

  window.TARS_HQ_MOCK = {
    state: async () => state(),
    fleet: async () => ({ agents: FLEET }),
    agent: async (name) => agent(name),
    task: async (id) => task(id),
    history: async (name) => ({ session_id: "demo", messages: chatOf(name).slice() }),
    reset: async (name) => { S.chats[name] = []; return { ok: true }; },
    retry: async () => ({ ok: true }),
    upload: async (file) => ({ path: `/opt/data/tars/inbox/demo/${file.name}`, name: file.name, rel: file.name, size: file.size, kind: /^image\//.test(file.type) ? "image" : "other" }),
    site: async () => ({ url: URL.createObjectURL(new Blob([SAMPLE_SITE], { type: "text/html" })) }),
    reveal: async () => { throw new Error("W trybie demo nie ma hosta: folder otwiera się w lokalnej instalacji."); },
    host: async () => ({ explorer: false, preview: true, data_win: "\\\\wsl.localhost\\Ubuntu\\home\\ty\\tars-local\\data\\hermes" }),
    fileBlob,
    send,
  };
})();
