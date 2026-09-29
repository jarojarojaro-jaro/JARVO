// JARVO landing: skala planszy, żywy robot (oczy za kursorem, mruganie, pisanie), terminal i instalacja.
(() => {
  // Kontakt: adres e-mail (mailto:) albo strona; pusto = zgłoszenia na GitHubie.
  const CONTACT = "";
  // Skąd instalatory. Po podpięciu domeny wystarczy zmienić tę jedną linię (np. https://jarvo.dev).
  const BASE = "https://raw.githubusercontent.com/jarojarojaro-jaro/JARVO/main";
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $ = (s, el = document) => el.querySelector(s);
  const root = document.documentElement;

  // ---------------------------------------------------------------- skala (desktop 1:1 z makietą)
  if (CONTACT) document.getElementById("contact").href = CONTACT.includes("@") && !CONTACT.startsWith("mailto:") ? `mailto:${CONTACT}` : CONTACT;
  const mobile = matchMedia("(max-width: 820px)");
  const scene = $(".scene");
  function fit() {
    const w = document.documentElement.clientWidth;
    // cała plansza zawsze na jednym ekranie (szerokość i wysokość), z odrobiną oddechu
    const s = Math.min(Math.min(w, 1760) / 1536 * 0.9, innerHeight / 1024 * 0.96);
    root.style.setProperty("--s", s);
    if (mobile.matches) root.style.setProperty("--ss", scene.clientWidth / 735);
    const st = $(".stage");
    st.style.marginLeft = mobile.matches ? "" : `${(w - 1536 * s) / 2}px`;
    // wysoki ekran: plansza na środku w pionie
    st.style.marginTop = mobile.matches ? "" : `${Math.max(0, (innerHeight - 1024 * s) / 2)}px`;

  }
  addEventListener("resize", fit); mobile.addEventListener("change", fit); fit();

  // ---------------------------------------------------------------- pyłki nad sceną
  const motes = $("#particles");
  const cols = ["#D4213D", "#D4213D", "#B8FF3D", "#5E6577", "#F2F1E8"];
  const spots = [[40, 60], [10, 170], [150, 300], [200, 250], [262, 30], [480, 20], [520, 200], [600, 250], [690, 110],
    [700, 300], [470, 110], [60, 370], [720, 460], [230, 520], [110, 420]];
  for (const [i, [x, y]] of spots.entries()) {
    const m = document.createElement("i");
    m.style.cssText = `left:${x}px;top:${y}px;--z:${4 + (i % 3) * 2}px;--c:${cols[i % cols.length]};--d:${5 + (i % 4) * 1.5}s;--t:${-i * 0.9}s`;
    motes.appendChild(m);
  }

  // ---------------------------------------------------------------- robot: oczy i paralaksa za kursorem
  const eyes = $("#eyes");
  const layers = [...document.querySelectorAll(".par")];
  let raf = 0, mx = 0, my = 0;
  function look() {
    raf = 0;
    const r = scene.getBoundingClientRect();
    const cx = r.left + r.width * 0.46, cy = r.top + r.height * 0.33;     // środek ekranu-twarzy
    const dx = Math.max(-1, Math.min(1, (mx - cx) / (innerWidth * 0.45)));
    const dy = Math.max(-1, Math.min(1, (my - cy) / (innerHeight * 0.5)));
    eyes.style.transform = `translate(${(dx * 5).toFixed(2)}px, ${(dy * 3).toFixed(2)}px)`;
    for (const l of layers) {
      const k = +l.dataset.depth;
      l.style.transform = `translate(${(-dx * k).toFixed(2)}px, ${(-dy * k * 0.6).toFixed(2)}px)`;
    }
  }
  if (!reduced) addEventListener("pointermove", (e) => { mx = e.clientX; my = e.clientY; if (!raf) raf = requestAnimationFrame(look); }, { passive: true });

  function blink() {
    if (!reduced) for (const e of [eyes, $("#bot-eyes")].filter(Boolean)) { e.classList.remove("blink"); void e.offsetWidth; e.classList.add("blink"); }
    setTimeout(blink, 2200 + Math.random() * 3800 + (Math.random() < 0.2 ? -1800 : 0));
  }
  setTimeout(blink, 1600);

  // ---------------------------------------------------------------- terminal: ktoś pisze, Jarvo odpowiada
  // ta sama rozmowa w terminalu (desktop) i w dymku robota (telefon)
  const each = (sel, t) => { for (const el of document.querySelectorAll(sel)) el.textContent = t; };
  const ask = { set textContent(t) { each("[data-ask]", t); } }, reply = { set textContent(t) { each("[data-reply]", t); } };
  const askEl = $("#ask"), replyEl = $("#reply"), cursor = $("#cursor"), sceneInner = $(".scene-inner");
  const talks = [
    ["yo, let's take over the world", "Already on it, boss. Phase one starts Monday."],
    ["build me a landing page by lunch", "Lunch? It's live. Go eat."],
    ["find the best CRM for a team of 5", "Read 40 reviews so you don't have to. Top 3 on your desk."],
    ["make a 30s promo from these photos", "Say less. Rendering the hype."],
    ["remind me what I promised the client", "Friday demo. I remembered, you're welcome."],
  ];
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  let busy = false;
  async function type(el, text, min, spread, host) {
    busy = true; host.parentNode.appendChild(cursor); cursor.classList.add("is-typing");
    for (let i = 1; i <= text.length; i++) { el.textContent = text.slice(0, i); await sleep(min + Math.random() * spread); }
    cursor.classList.remove("is-typing"); busy = false;
  }
  // ---------------------------------------------------------------- robot na telefonie: stoi, mruga, wita się w dymku
  const bot = $("#bot"), bubble = $(".bubble"), hello = $("#hello");
  const lines = [
    "Hi, I'm <b>JARVO</b>.\nYour digital right hand.",
    "Tap <b>Start building</b>\nand let's get to work.",
    "Research, sites, videos, docs.\nOne team, zero drama.",
    "Still here. Still ready, boss.",
  ];
  let li = 0, talking = 0;
  async function speak(html) {
    const id = ++talking;
    bubble.classList.add("show");
    const plain = html.replace(/<[^>]+>/g, ""), tags = [...html.matchAll(/<b>(.*?)<\/b>/g)].map((m) => m[1]);
    for (let i = 1; i <= plain.length; i++) {
      if (id !== talking) return;
      let s = plain.slice(0, i);
      for (const t of tags) s = s.replace(t, `<b>${t}</b>`);
      hello.innerHTML = s + '<span class="caret"></span>';
      await sleep(plain[i - 1] === "\n" ? 220 : 32 + Math.random() * 30);
    }
  }
  setTimeout(() => speak(lines[0]), reduced ? 0 : 700);
  bot.addEventListener("click", () => {
    bot.classList.remove("hop"); void bot.offsetWidth; bot.classList.add("hop");
    li = (li + 1) % lines.length; speak(lines[li]);
  });
  bot.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); bot.click(); } });

  async function loop() {
    const whos = document.querySelectorAll(".t-who");
    for (;;) for (const [q, a] of talks) {
      ask.textContent = ""; reply.textContent = ""; for (const w of whos) w.style.visibility = "hidden";
      await sleep(500);
      await type(ask, q, 45, 70, askEl);          // człowiek pisze wolniej, z wahaniem
      await sleep(650);
      for (const w of whos) w.style.visibility = "";
      await type(reply, a, 16, 22, replyEl);      // Jarvo odpowiada szybko
      await sleep(3200);
    }
  }
  if (!reduced) loop();
  // robot stuka prawie bez przerwy: serie po 1–3 s, krótkie pauzy; zawsze, gdy terminal pisze
  async function hands() {
    for (;;) {
      sceneInner.classList.add("typing");
      await sleep(1000 + Math.random() * 2200);
      if (!busy) { sceneInner.classList.remove("typing"); await sleep(250 + Math.random() * 650); }
    }
  }
  if (!reduced) hands();
  if (!reduced) loop();

  // ---------------------------------------------------------------- instalacja: system → polecenie
  const dlg = $("#install");
  const OS = {
    macos: { label: "MACOS", tabs: {
      CURL: `curl -fsSL ${BASE}/install.sh | bash`,
      WGET: `wget -qO- ${BASE}/install.sh | bash`,
    }, steps: [
      `Install and start <a href="https://www.docker.com/products/docker-desktop/" target="_blank" rel="noopener">Docker Desktop</a>.`,
      `Open <b>Terminal</b>, paste the command and press Enter.`,
      `Pick your model provider and paste its key when asked.`,
      `Open <a href="http://localhost:9119/base">localhost:9119</a>. Your team is ready.`,
    ] },
    linux: { label: "LINUX", tabs: {
      CURL: `curl -fsSL ${BASE}/install.sh | bash`,
      WGET: `wget -qO- ${BASE}/install.sh | bash`,
    }, steps: [
      `Install <a href="https://docs.docker.com/engine/install/" target="_blank" rel="noopener">Docker Engine</a> with the compose plugin, plus <code>git</code>.`,
      `Paste the command into your terminal and press Enter.`,
      `Pick your model provider and paste its key when asked.`,
      `Open <a href="http://localhost:9119/base">localhost:9119</a>. Your team is ready.`,
    ] },
    windows: { label: "WINDOWS", tabs: {
      PS1: `irm ${BASE}/install.ps1 | iex`,
      WSL: `curl -fsSL ${BASE}/install.sh | bash`,
    }, steps: [
      `Install <a href="https://www.docker.com/products/docker-desktop/" target="_blank" rel="noopener">Docker Desktop</a> and turn on <b>Settings → Resources → WSL integration</b>.`,
      `PS1: open <b>PowerShell</b> and paste the command. It sets up WSL if needed. WSL: paste it in your Ubuntu terminal.`,
      `Pick your model provider and paste its key when asked.`,
      `Open <a href="http://localhost:9119/base">localhost:9119</a>. Your team is ready.`,
    ] },
  };
  function detect() {
    const p = (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || navigator.userAgent;
    if (/win/i.test(p)) return "windows";
    if (/mac|iphone|ipad/i.test(p)) return "macos";
    if (/linux|x11|android|cros/i.test(p)) return "linux";
    return null;
  }
  const detected = detect();
  let os = null, tab = null;
  function pick(name) {
    os = name; tab = Object.keys(OS[name].tabs)[0];
    for (const b of dlg.querySelectorAll("[data-os]")) b.setAttribute("aria-checked", String(b.dataset.os === name));
    render();
  }
  function render() {
    const o = OS[os], box = $("#inst-cmd"), tabs = $(".tabs", box);
    box.hidden = false;
    tabs.replaceChildren(...Object.keys(o.tabs).map((t) => {
      const b = document.createElement("button");
      b.type = "button"; b.role = "tab"; b.textContent = t; b.setAttribute("aria-selected", String(t === tab));
      b.onclick = () => { tab = t; render(); };
      return b;
    }));
    $(".inst-for", box).textContent = os === "windows" ? (tab === "WSL" ? "WSL · UBUNTU" : "WINDOWS 10 · 11") : "MACOS · LINUX";
    $("#cmd").textContent = o.tabs[tab];
    $("#steps").innerHTML = o.steps.map((s) => `<li>${s}</li>`).join("");
    const c = $("#copy"); c.textContent = "COPY"; c.classList.remove("ok");
  }
  for (const b of dlg.querySelectorAll("[data-os]")) {
    if (b.dataset.os === detected) b.dataset.detected = "";
    b.addEventListener("click", () => pick(b.dataset.os));
  }
  $("#copy").addEventListener("click", async () => {
    const c = $("#copy"), text = $("#cmd").textContent;
    try { await navigator.clipboard.writeText(text); }
    catch { const r = document.createRange(); r.selectNodeContents($("#cmd")); getSelection().removeAllRanges(); getSelection().addRange(r); document.execCommand("copy"); }
    c.textContent = "COPIED"; c.classList.add("ok");
    setTimeout(() => { c.textContent = "COPY"; c.classList.remove("ok"); }, 1800);
  });
  for (const b of document.querySelectorAll("[data-install]")) b.addEventListener("click", () => {
    dlg.showModal();
    if (detected && !os) pick(detected);
  });
  dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });   // klik w tło zamyka
})();
