// Grafika pokoi (SVG): skorupa pokoju z cegiełek, rekwizyty tematyczne, minifigurki i TARS-monolit.
// Każdy pokój: viewBox 400×300 (mostek 800×300). Kotwica figurki w % służy do pozycjonowania dymka HTML.

const ROOMS = {
  bridge:   { w: 800, wall: "#5A6574", seam: "#48525F", side: "#434C58", floor: "#2E3540", floor2: "#373F4B", base: "#7C8896", fig: [31, 50], bubble: "left" },
  study:    { w: 400, wall: "#2F6552", seam: "#244E3F", side: "#285544", floor: "#8C5B35", floor2: "#7C4F2D", base: "#6F8F3A", fig: [66, 44] },
  devlab:   { w: 400, wall: "#2370D2", seam: "#1B5BAD", side: "#1C5EB2", floor: "#DADFE5", floor2: "#CBD1D8", base: "#4F93E3", fig: [30, 44] },
  atelier:  { w: 400, wall: "#DE6A8B", seam: "#C25676", side: "#BE5372", floor: "#E7D0A7", floor2: "#DAC095", base: "#F3A4BC", fig: [36, 40] },
  workshop: { w: 400, wall: "#E48A2F", seam: "#C57320", side: "#C06F1F", floor: "#8F979F", floor2: "#848C94", base: "#F2B64C", fig: [44, 40] },
  office:   { w: 400, wall: "#9CA9B9", seam: "#8595A7", side: "#8494A5", floor: "#5B6C80", floor2: "#53637A", base: "#BAC6D2", fig: [40, 44] },
};

const FIGS = {
  study:    { torso: "#2E4A3B", legs: "#5B4636", hat: "deerstalker", detail: "scarf" },
  devlab:   { torso: "#233A5E", legs: "#2B2F36", hat: "messy", detail: "hoodie", phones: true },
  atelier:  { torso: "#F2C230", legs: "#3B3F8C", hat: "beret", detail: "stripes" },
  workshop: { torso: "#D9661F", legs: "#2F5D9E", hat: "cap", detail: "overalls" },
  office:   { torso: "#5A6472", legs: "#2E3440", hat: "hair", detail: "tie" },
};

// ------------------------------------------------------------------ skorupa pokoju

function RoomShell({ id, r, lit }) {
  const W = r.w, floorY = 218, baseY = 262;
  const bid = `thq-bricks-${id}`, sid = `thq-side-${id}`, fid = `thq-floor-${id}`, lid = `thq-light-${id}`;
  const studs = [];
  for (let x = 18; x < W - 6; x += 26) studs.push(x);
  return html`<g>
    <defs>
      <pattern id=${bid} width="40" height="20" patternUnits="userSpaceOnUse">
        <rect width="40" height="20" fill=${r.wall}/>
        <path d="M0 0.5H40M0 10.5H40M10 0V10M30 10V20" stroke=${r.seam} stroke-width="1.2"/>
        <path d="M1 2H9M11 12H29M31 2H39" stroke="#fff" stroke-opacity=".12" stroke-width="1"/>
      </pattern>
      <pattern id=${sid} width="40" height="20" patternUnits="userSpaceOnUse">
        <rect width="40" height="20" fill=${r.side}/>
        <path d="M0 0.5H40M0 10.5H40M10 0V10M30 10V20" stroke=${r.seam} stroke-width="1.2"/>
      </pattern>
      <pattern id=${fid} width="44" height="22" patternUnits="userSpaceOnUse">
        <rect width="44" height="22" fill=${r.floor}/>
        <rect x="22" width="22" height="11" fill=${r.floor2}/><rect y="11" width="22" height="11" fill=${r.floor2}/>
      </pattern>
      <radialGradient id=${lid} cx="50%" cy="0%" r="75%">
        <stop offset="0%" stop-color="#FFE7A8" stop-opacity=".55"/>
        <stop offset="100%" stop-color="#FFE7A8" stop-opacity="0"/>
      </radialGradient>
    </defs>
    <rect x="46" y="22" width=${W - 56} height=${floorY - 22} fill=${`url(#${bid})`}/>
    <polygon points=${`6,8 46,22 46,${floorY} 6,${baseY}`} fill=${`url(#${sid})`}/>
    <polygon points=${`6,8 46,22 46,${floorY} 6,${baseY}`} fill="#000" fill-opacity=".14"/>
    <rect x="40" y="14" width=${W - 44} height="9" rx="2" fill=${r.seam}/>
    <polygon points=${`46,${floorY} ${W - 10},${floorY} ${W - 4},${baseY} 6,${baseY}`} fill=${`url(#${fid})`}/>
    <polygon points=${`46,${floorY} ${W - 10},${floorY} ${W - 4},${baseY} 6,${baseY}`} fill="#000" fill-opacity=".06"/>
    <rect x="46" y=${floorY - 4} width=${W - 56} height="4" fill="#000" fill-opacity=".18"/>
    <rect x="2" y=${baseY} width=${W - 4} height="30" rx="3" fill=${r.base}/>
    <rect x="2" y=${baseY + 22} width=${W - 4} height="8" rx="3" fill="#000" fill-opacity=".18"/>
    ${studs.map((x) => html`<g key=${x}>
      <rect x=${x - 8} y=${baseY - 5} width="16" height="7" rx="2" fill=${r.base}/>
      <rect x=${x - 8} y=${baseY - 5} width="16" height="7" rx="2" fill="#000" fill-opacity=".1"/>
      <rect x=${x - 6} y=${baseY - 5} width="6" height="2" rx="1" fill="#fff" fill-opacity=".45"/>
    </g>`)}
    <rect class=${cx("thq-light", lit && "is-on")} x="46" y="22" width=${W - 56} height=${baseY - 22} fill=${`url(#${lid})`}/>
    <rect class=${cx("thq-dim", !lit && "is-on")} x="2" y="8" width=${W - 4} height=${baseY - 8} fill="#0B1220"/>
  </g>`;
}

// ----------------------------------------------------------------------- minifigurka

function Hat({ kind }) {
  switch (kind) {
    case "deerstalker":
      return html`<g>
        <path d="M-13 -89 Q-12 -104 0 -105 Q12 -104 13 -89 Z" fill="#B58B57"/>
        <path d="M-9 -103 L9 -92 M-12 -95 L6 -104 M-3 -105 L13 -95" stroke="#7E5E38" stroke-width="1.2"/>
        <path d="M-15 -90 L-19 -80 L-11 -86 Z M15 -90 L19 -80 L11 -86 Z" fill="#A27A4A"/>
        <rect x="-15" y="-91" width="30" height="4" rx="2" fill="#8E6A3F"/>
      </g>`;
    case "messy":
      return html`<path d="M-12 -86 Q-13 -101 -4 -103 L-2 -99 L2 -104 L5 -99 L10 -102 Q14 -96 12 -86 L9 -93 L4 -90 L0 -94 L-5 -90 L-9 -94 Z" fill="#2B1D16"/>`;
    case "beret":
      return html`<g><ellipse cx="2" cy="-97" rx="15" ry="6" fill="#B0306A" transform="rotate(-8 2 -97)"/>
        <rect x="1" y="-106" width="3" height="5" rx="1.5" fill="#8C2455"/></g>`;
    case "cap":
      return html`<g><path d="M-12 -90 Q-11 -104 0 -104 Q11 -104 12 -90 Z" fill="#F08A24"/>
        <path d="M8 -91 L24 -89 Q24 -86 20 -86 L8 -87 Z" fill="#D06F14"/>
        <rect x="-3" y="-101" width="6" height="4" rx="1" fill="#fff" fill-opacity=".85"/></g>`;
    default:
      return html`<path d="M-12 -87 Q-12 -102 0 -102 Q12 -102 12 -89 Q5 -97 -3 -94 Q-8 -92 -12 -87 Z" fill="#6B4226"/>`;
  }
}

function Minifig({ room, status, x, y, scale = 1 }) {
  const f = FIGS[room] || FIGS.office;
  const working = status === "working" || status === "judging";
  const seated = room === "study" || room === "devlab" || room === "office";
  const legH = seated ? 16 : 32;
  const lift = seated ? 16 : 0;
  const holdPaper = status === "review";
  return html`<g transform=${`translate(${x} ${y}) scale(${scale})`}>
    <g class=${cx("thq-fig", working && "is-working", status === "idle" && "is-idle", status === "blocked" && "is-alert")}>
      <ellipse cx="0" cy="1" rx="22" ry="4" fill="#000" fill-opacity=".22"/>
      <rect x="-15" y=${-legH} width="14" height=${legH} rx="2" fill=${f.legs}/>
      <rect x="1" y=${-legH} width="14" height=${legH} rx="2" fill=${f.legs}/>
      <rect x="-16" y=${-legH - 8} width="32" height="9" rx="2" fill=${f.legs}/>
      <rect x="-15" y=${-legH - 8} width="30" height="2" fill="#fff" fill-opacity=".15"/>
      <g transform=${`translate(0 ${lift})`}>
        <path d="M-13 -72 L13 -72 L16 -40 L-16 -40 Z" fill=${f.torso}/>
        ${f.detail === "scarf" && html`<path d="M-8 -72 L8 -72 L4 -64 L6 -52 L1 -52 L0 -64 Z" fill="#C9A26B"/>`}
        ${f.detail === "hoodie" && html`<g><path d="M-9 -72 Q0 -64 9 -72" stroke="#16263F" stroke-width="3" fill="none"/>
          <path d="M-3 -67 V-56 M3 -67 V-56" stroke="#E8EEF6" stroke-width="1.4"/>
          <text x="0" y="-45" text-anchor="middle" font-size="7" font-family="monospace" fill="#7FB4FF">${"</>"}</text></g>`}
        ${f.detail === "stripes" && html`<path d="M-14 -64 H14 M-15 -56 H15 M-15.5 -48 H15.5" stroke="#1E1E24" stroke-width="2.4"/>`}
        ${f.detail === "overalls" && html`<g><rect x="-10" y="-60" width="20" height="20" fill="#2F5D9E"/>
          <path d="M-9 -60 L-6 -72 M9 -60 L6 -72" stroke="#2F5D9E" stroke-width="3"/>
          <rect x="-5" y="-56" width="10" height="6" rx="1" fill="#244C83"/></g>`}
        ${f.detail === "tie" && html`<path d="M-2 -72 H2 L3 -52 L0 -48 L-3 -52 Z" fill="#C0392B"/>`}
        <g class="thq-arm-l"><rect x="-21" y="-71" width="8" height="24" rx="4" fill=${f.torso} transform="rotate(12 -17 -71)"/>
          <circle cx="-21" cy="-46" r="5" fill="#F2CD37"/><circle cx="-21" cy="-46" r="2" fill="#D9B21E"/></g>
        <g class=${holdPaper ? "thq-arm-up" : "thq-arm-r"}>
          <rect x="13" y="-71" width="8" height="24" rx="4" fill=${f.torso} transform="rotate(-12 17 -71)"/>
          <circle cx="21" cy="-46" r="5" fill="#F2CD37"/><circle cx="21" cy="-46" r="2" fill="#D9B21E"/>
          ${holdPaper && html`<g><rect x="16" y="-66" width="16" height="20" rx="1" fill="#FFFFFF" transform="rotate(8 24 -56)"/>
            <path d="M19 -61 H29 M19 -57 H28 M19 -53 H26" stroke="#8A94A3" stroke-width="1.2" transform="rotate(8 24 -56)"/></g>`}
        </g>
        <rect x="-5" y="-76" width="10" height="5" fill="#E5BE2A"/>
        <g class="thq-head">
          <rect x="-12" y="-96" width="24" height="22" rx="7" fill="#F2CD37"/>
          <rect x="-12" y="-96" width="24" height="5" rx="3" fill="#fff" fill-opacity=".25"/>
          <rect x="-6" y="-100" width="12" height="5" rx="1.5" fill="#E5BE2A"/>
          <g class="thq-eyes"><ellipse cx="-4.5" cy="-87" rx="1.8" ry="2.2" fill="#1B1B1B"/><ellipse cx="4.5" cy="-87" rx="1.8" ry="2.2" fill="#1B1B1B"/></g>
          ${status === "blocked"
            ? html`<path d="M-4 -80 Q0 -83 4 -80" stroke="#1B1B1B" stroke-width="1.4" fill="none"/>`
            : html`<path d="M-5 -82 Q0 -77 5 -82" stroke="#1B1B1B" stroke-width="1.4" fill="none"/>`}
          <${Hat} kind=${f.hat}/>
          ${f.phones && html`<g><path d="M-14 -86 Q-14 -106 0 -106 Q14 -106 14 -86" stroke="#1FB6A6" stroke-width="3" fill="none"/>
            <rect x="-17" y="-91" width="6" height="11" rx="2" fill="#1FB6A6"/><rect x="11" y="-91" width="6" height="11" rx="2" fill="#1FB6A6"/></g>`}
        </g>
      </g>
      ${status === "idle" && html`<g class="thq-zzz" fill="#FFFFFF" font-weight="700" font-family="sans-serif">
        <text x="16" y="-86" font-size="9">z</text><text x="22" y="-96" font-size="11">z</text><text x="30" y="-108" font-size="13">z</text></g>`}
    </g>
  </g>`;
}

// TARS: robot-monolit z „Interstellar” (cztery płyty i pasek wyświetlacza)
function TarsBot({ x, y, status }) {
  const working = status === "working" || status === "judging";
  const screen = status === "blocked" ? "#FF5A4E" : working ? "#7CF0B4" : "#6E7C8C";
  return html`<g transform=${`translate(${x} ${y})`} class=${cx("thq-tars", working && "is-working", status === "idle" && "is-idle")}>
    <ellipse cx="0" cy="2" rx="40" ry="5" fill="#000" fill-opacity=".3"/>
    ${[-27, -9, 9, 27].map((dx, i) => html`<g key=${i} class=${`thq-slab thq-slab-${i}`}>
      <rect x=${dx - 8} y="-118" width="16" height="118" rx="1.5" fill="#8E98A4"/>
      <rect x=${dx - 8} y="-118" width="4" height="118" fill="#fff" fill-opacity=".18"/>
      <rect x=${dx + 5} y="-118" width="3" height="118" fill="#000" fill-opacity=".22"/>
      <path d=${`M${dx - 8} -60 H${dx + 8} M${dx - 8} -30 H${dx + 8}`} stroke="#6B7582" stroke-width="1"/>
    </g>`)}
    <rect x="-35" y="-104" width="70" height="15" rx="2" fill="#0D1117"/>
    <g class="thq-tars-screen" fill=${screen}>
      ${status === "blocked"
        ? html`<text x="0" y="-92.5" text-anchor="middle" font-size="11" font-weight="700" font-family="monospace">!</text>`
        : [0, 1, 2, 3, 4, 5, 6].map((i) => html`<rect key=${i} class="thq-bar" x=${-30 + i * 9} y="-100" width="6" height="7" rx="1" style=${{ animationDelay: `${i * 0.12}s` }}/>`)}
    </g>
  </g>`;
}

// ------------------------------------------------------------------------ rekwizyty

function BridgeProps({ board }) {
  const cols = [
    ["Gotowe", board.ready || 0, "#9CC3FF"],
    ["W toku", board.running || 0, "#7CF0B4"],
    ["Ocena", board.review || 0, "#FFD36E"],
    ["Blokady", board.blocked || 0, "#FF8A7A"],
  ];
  const stars = [[82, 44], [118, 70], [150, 40], [96, 104], [176, 92], [130, 124], [70, 136], [188, 60]];
  return html`<g>
    <rect x="62" y="34" width="150" height="120" rx="10" fill="#0B1426"/>
    <circle cx="170" cy="118" r="30" fill="#E9A55C"/><path d="M142 110 Q170 100 199 114" stroke="#C67C38" stroke-width="3" fill="none"/>
    ${stars.map(([sx, sy], i) => html`<circle key=${i} class="thq-star" cx=${sx} cy=${sy} r="1.6" fill="#fff" style=${{ animationDelay: `${i * 0.4}s` }}/>`)}
    <rect x="62" y="34" width="150" height="120" rx="10" fill="none" stroke="#343E4C" stroke-width="7"/>
    <path d="M137 34 V154 M62 94 H212" stroke="#343E4C" stroke-width="4"/>
    <rect x="300" y="30" width="360" height="132" rx="6" fill="#10151D"/>
    <rect x="300" y="30" width="360" height="132" rx="6" fill="none" stroke="#2A323D" stroke-width="6"/>
    <text x="316" y="50" font-size="11" font-family="monospace" fill="#8FA3B8" letter-spacing="1">TABLICA FLOTY</text>
    ${cols.map(([label, n, color], i) => {
      const x0 = 316 + i * 84;
      return html`<g key=${label}>
        <text x=${x0} y="70" font-size="9.5" font-family="monospace" fill="#8FA3B8">${label}</text>
        <text x=${x0 + 64} y="70" font-size="11" font-weight="700" font-family="monospace" fill=${color} text-anchor="end">${n}</text>
        ${Array.from({ length: Math.min(n, 5) }).map((_, j) => html`<rect key=${j} x=${x0} y=${78 + j * 15} width="64" height="11" rx="2" fill=${color} fill-opacity=".85"/>`)}
        ${n > 5 && html`<text x=${x0 + 32} y="160" font-size="8" fill="#8FA3B8" text-anchor="middle" font-family="monospace">+${n - 5}</text>`}
      </g>`;
    })}
    <rect x="280" y="176" width="400" height="30" rx="4" fill="#3A4350"/>
    <rect x="280" y="176" width="400" height="6" rx="3" fill="#4C5663"/>
    ${[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((i) => html`<rect key=${i} class="thq-blink" x=${298 + i * 36} y="188" width="14" height="7" rx="1.5"
      fill=${["#FF6B5E", "#FFD36E", "#7CF0B4", "#9CC3FF"][i % 4]} style=${{ animationDelay: `${(i * 0.37) % 2}s` }}/>`)}
    <rect x="286" y="206" width="12" height="12" fill="#2C333D"/><rect x="662" y="206" width="12" height="12" fill="#2C333D"/>
    <g transform="translate(720 218)">
      <rect x="-20" y="-48" width="40" height="30" rx="8" fill="#B8323A"/>
      <rect x="-24" y="-22" width="48" height="10" rx="4" fill="#9C2A31"/>
      <rect x="-3" y="-12" width="6" height="10" fill="#444C57"/><rect x="-16" y="-3" width="32" height="4" rx="2" fill="#444C57"/>
    </g>
  </g>`;
}

function StudyProps({ status, queue }) {
  const books = ["#C0392B", "#2C3E50", "#E0B84C", "#6C8EBF", "#8E5B3C", "#3E7B5A", "#B85C8A", "#D98E32"];
  return html`<g>
    <rect x="58" y="52" width="78" height="166" fill="#5E3B22"/>
    ${[0, 1, 2, 3].map((s) => html`<g key=${s}>
      <rect x="62" y=${60 + s * 38} width="70" height="32" fill="#3E2615"/>
      ${books.map((c, i) => html`<rect key=${i} x=${64 + i * 8.4} y=${66 + s * 38 + ((i * 7 + s * 3) % 9)} width="7" height=${26 - ((i * 7 + s * 3) % 9)} rx="1" fill=${books[(i + s * 3) % books.length]}/>`)}
      <rect x="60" y=${92 + s * 38} width="74" height="4" fill="#6E4628"/>
    </g>`)}
    <rect x="160" y="44" width="112" height="76" rx="2" fill="#6E4628"/>
    <rect x="165" y="49" width="102" height="66" fill="#C89B63"/>
    <rect x="172" y="56" width="26" height="20" fill="#FFF8E8" transform="rotate(-4 185 66)"/>
    <rect x="232" y="54" width="24" height="18" fill="#FFF3C4" transform="rotate(5 244 63)"/>
    <rect x="190" y="84" width="30" height="22" fill="#FFFFFF" transform="rotate(3 205 95)"/>
    <rect x="236" y="88" width="22" height="18" fill="#E6F0FF" transform="rotate(-6 247 97)"/>
    <polyline points="184,60 246,58 206,90 246,92 184,60" fill="none" stroke="#C0392B" stroke-width="1.4"/>
    ${[[184, 60], [246, 58], [206, 90], [246, 92]].map(([px, py], i) => html`<circle key=${i} cx=${px} cy=${py} r="2.6" fill="#D62D20"/>`)}
    <rect x="262" y="128" width="46" height="60" rx="10" fill="#7A2E2E"/>
    <rect x="236" y="182" width="150" height="10" rx="2" fill="#6E4628"/>
    <rect x="244" y="192" width="10" height="26" fill="#553418"/><rect x="368" y="192" width="10" height="26" fill="#553418"/>
    ${Array.from({ length: Math.min(queue, 5) }).map((_, i) => html`<rect key=${i} x="248" y=${176 - i * 3} width="30" height="4" fill=${i % 2 ? "#F4EEDC" : "#FFFFFF"} stroke="#CFC6AE" stroke-width=".6"/>`)}
    <g transform="translate(352 182)">
      <rect x="-3" y="-30" width="4" height="30" fill="#8C6B2F"/>
      <path d="M-16 -30 Q-1 -44 14 -30 Z" fill="#2E7D4F"/>
      <ellipse class=${cx("thq-glow", status === "working" && "is-on")} cx="-1" cy="-24" rx="24" ry="14" fill="#FFE39A"/>
      <rect x="-12" y="-2" width="24" height="3" rx="1.5" fill="#8C6B2F"/>
    </g>
    <g transform="translate(318 180) rotate(-20)"><circle r="7" fill="#DDEBF7" stroke="#6E4628" stroke-width="2.4"/><rect x="5" y="-1.5" width="12" height="3" fill="#6E4628"/></g>
  </g>`;
}

function DevlabProps({ status }) {
  const working = status === "working";
  const lines = [[0, 60, "#7FB4FF"], [8, 44, "#FFD36E"], [8, 52, "#9BE3A7"], [16, 30, "#FF9BB0"], [8, 48, "#7FB4FF"], [0, 22, "#C9D3DE"]];
  const monitor = (mx, key) => html`<g key=${key} transform=${`translate(${mx} 116)`}>
    <rect x="0" y="0" width="84" height="56" rx="3" fill="#1D232C"/>
    <rect x="4" y="4" width="76" height="46" fill="#0F141B"/>
    <g class=${cx("thq-code", working && "is-on")}>
      ${lines.map(([ix, w, c], i) => html`<rect key=${i} x=${8 + ix} y=${9 + i * 6.5} width=${w * 0.9} height="3" rx="1" fill=${c}/>`)}
    </g>
    <rect x="38" y="56" width="8" height="10" fill="#2A313B"/><rect x="28" y="64" width="28" height="4" rx="2" fill="#2A313B"/>
  </g>`;
  return html`<g>
    <rect x="66" y="46" width="84" height="64" rx="2" fill="#FFFFFF"/>
    <rect x="72" y="52" width="72" height="12" fill="#DCE8F7"/>
    <rect x="72" y="68" width="34" height="36" fill="#EEF3FA"/><rect x="110" y="68" width="34" height="16" fill="#EEF3FA"/><rect x="110" y="88" width="34" height="16" fill="#EEF3FA"/>
    <text class=${cx("thq-neon", working && "is-on")} x="226" y="80" font-size="30" font-weight="800" font-family="monospace" fill="#7FF3FF">${"</>"}</text>
    ${monitor(190, "a")}${monitor(284, "b")}
    <rect x="176" y="184" width="206" height="9" rx="2" fill="#E9EDF2"/>
    <rect x="184" y="193" width="8" height="25" fill="#AEB7C2"/><rect x="366" y="193" width="8" height="25" fill="#AEB7C2"/>
    <rect x="232" y="178" width="60" height="5" rx="1.5" fill="#3A424D"/>
    <g transform="translate(350 170)"><rect x="0" y="0" width="14" height="14" rx="2" fill="#FFFFFF"/><path d="M14 4 Q20 6 14 10" stroke="#FFFFFF" stroke-width="2" fill="none"/>
      <g class=${cx("thq-steam", working && "is-on")}><path d="M4 -3 Q2 -8 5 -12 M9 -3 Q7 -9 10 -14" stroke="#FFFFFF" stroke-opacity=".8" stroke-width="1.4" fill="none"/></g></g>
    <g transform="translate(118 216)"><rect x="-18" y="-40" width="36" height="30" rx="6" fill="#2D3440"/><rect x="-3" y="-12" width="6" height="8" fill="#555E6B"/><rect x="-16" y="-4" width="32" height="4" rx="2" fill="#555E6B"/></g>
    <g transform="translate(364 218)"><rect x="-10" y="-18" width="20" height="18" rx="2" fill="#C8693C"/>
      <path d="M0 -18 Q-14 -40 -4 -52 M0 -18 Q4 -46 14 -50 M0 -18 Q10 -32 20 -34" stroke="#2F8F4E" stroke-width="5" fill="none" stroke-linecap="round"/></g>
  </g>`;
}

function AtelierProps({ status }) {
  const working = status === "working";
  const swatches = ["#1D3557", "#E63946", "#F1FAEE", "#F4A261"];
  return html`<g>
    <path d="M232 34 H372 V190 Q302 216 232 190 Z" fill="#F7F3EC"/>
    <rect x="228" y="28" width="148" height="10" rx="5" fill="#8A8F99"/>
    <g transform="translate(300 188)"><rect x="-9" y="-34" width="18" height="34" rx="4" fill="#E9C46A"/><rect x="-5" y="-42" width="10" height="9" rx="2" fill="#2A2A2A"/>
      <rect x="-7" y="-24" width="14" height="10" fill="#FFFFFF" fill-opacity=".7"/></g>
    <g transform="translate(206 218)">
      <path d="M0 0 L-12 -60 M0 0 L12 -60 M0 0 L0 -62" stroke="#3A3F48" stroke-width="3"/>
      <rect x="-20" y="-86" width="40" height="26" rx="4" fill="#23272E"/>
      <circle cx="18" cy="-73" r="10" fill="#3A404A"/><circle cx="18" cy="-73" r="6" fill="#0E1116"/><circle cx="16" cy="-75" r="2" fill="#6D8BB0"/>
      <rect class=${cx("thq-rec", working && "is-on")} x="-15" y="-82" width="5" height="5" rx="2.5" fill="#FF3B30"/>
    </g>
    <g transform="translate(96 218)">
      <path d="M0 0 L0 -96" stroke="#3A3F48" stroke-width="3"/><path d="M-14 0 L0 -24 L14 0" stroke="#3A3F48" stroke-width="3" fill="none"/>
      <path d="M-26 -140 L26 -140 L20 -100 L-20 -100 Z" fill="#E7ECF2"/>
      <path class=${cx("thq-glow", working && "is-on")} d="M-24 -100 L24 -100 L60 -40 L-60 -40 Z" fill="#FFF3C4"/>
    </g>
    <g transform="translate(160 218)">
      <path d="M-18 0 L0 -110 L18 0 M-10 -40 H10" stroke="#8A5A33" stroke-width="3" fill="none"/>
      <rect x="-26" y="-104" width="52" height="40" fill="#FFFFFF" stroke="#8A5A33" stroke-width="2"/>
      ${swatches.map((c, i) => html`<rect key=${i} x=${-22 + i * 12} y="-98" width="10" height="28" fill=${c}/>`)}
    </g>
    <g transform="translate(58 206) rotate(-10)"><rect width="30" height="16" fill="#23272E"/><rect y="-6" width="30" height="6" fill="#FFFFFF"/>
      <path d="M4 -6 L8 0 M12 -6 L16 0 M20 -6 L24 0" stroke="#23272E" stroke-width="2"/></g>
  </g>`;
}

function WorkshopProps({ status, queue }) {
  const working = status === "working";
  const n = Math.max(1, Math.min(queue + 1, 6));
  const boxes = [[312, 218], [352, 218], [332, 194], [312, 170], [352, 194], [332, 170]].slice(0, n);
  return html`<g>
    <rect x="62" y="40" width="130" height="84" rx="2" fill="#CFA56A"/>
    ${Array.from({ length: 6 }).map((_, i) => Array.from({ length: 4 }).map((__, j) => html`<circle key=${`${i}-${j}`} cx=${74 + i * 21} cy=${52 + j * 20} r="1.6" fill="#8A6A3C"/>`))}
    <path d="M84 52 L84 92 M78 52 H90" stroke="#5B6470" stroke-width="5" stroke-linecap="round"/>
    <g transform="translate(118 50)"><rect x="-3" y="0" width="6" height="42" rx="2" fill="#8A5A33"/><rect x="-12" y="-4" width="24" height="10" rx="2" fill="#4A515C"/></g>
    <path d="M150 52 L150 94" stroke="#C0392B" stroke-width="6" stroke-linecap="round"/><path d="M150 94 L150 108" stroke="#9AA3AE" stroke-width="2"/>
    <path d="M168 56 Q180 70 172 104" stroke="#2F5D9E" stroke-width="4" fill="none" stroke-linecap="round"/>
    <rect x="70" y="170" width="190" height="12" rx="2" fill="#6B4A2D"/>
    <rect x="78" y="182" width="10" height="36" fill="#553A22"/><rect x="242" y="182" width="10" height="36" fill="#553A22"/>
    <g transform="translate(208 170)" class=${cx("thq-robot", working && "is-on")}>
      <rect x="-12" y="-6" width="24" height="6" rx="2" fill="#3C434D"/>
      <g class="thq-robot-arm"><rect x="-4" y="-40" width="8" height="36" rx="3" fill="#F2B64C"/>
        <g transform="translate(0 -40)" class="thq-robot-fore"><rect x="-3" y="-4" width="30" height="8" rx="3" fill="#F2B64C"/>
          <path d="M27 -6 L34 -8 M27 6 L34 8" stroke="#3C434D" stroke-width="3" stroke-linecap="round"/></g></g>
    </g>
    ${boxes.map(([bx, by], i) => html`<g key=${i} transform=${`translate(${bx} ${by})`}>
      <rect x="-18" y="-24" width="36" height="24" fill="#C8955A"/><rect x="-18" y="-24" width="36" height="5" fill="#B07E45"/>
      <rect x="-3" y="-24" width="6" height="24" fill="#E3C28C"/></g>`)}
    <g class=${cx("thq-hazard")}>${Array.from({ length: 16 }).map((_, i) => html`<path key=${i} d=${`M${46 + i * 22} 218 L${58 + i * 22} 218 L${52 + i * 22} 226 L${40 + i * 22} 226 Z`} fill=${i % 2 ? "#1E1E1E" : "#F5C400"}/>`)}</g>
  </g>`;
}

function OfficeProps({ status }) {
  return html`<g>
    <circle cx="300" cy="66" r="18" fill="#FFFFFF" stroke="#5B6C80" stroke-width="3"/>
    <path d="M300 66 V54 M300 66 L308 70" stroke="#2E3440" stroke-width="2"/>
    <rect x="200" y="176" width="150" height="9" rx="2" fill="#E9EDF2"/>
    <rect x="208" y="185" width="8" height="33" fill="#AEB7C2"/><rect x="334" y="185" width="8" height="33" fill="#AEB7C2"/>
    <g transform="translate(250 176)"><rect x="0" y="-26" width="44" height="26" rx="2" fill="#2D3440"/>
      <rect x="3" y="-23" width="38" height="20" fill=${status === "working" ? "#7FB4FF" : "#3E4856"}/></g>
  </g>`;
}

const PROPS = { bridge: BridgeProps, study: StudyProps, devlab: DevlabProps, atelier: AtelierProps, workshop: WorkshopProps, office: OfficeProps };

function RoomArt({ agent, board }) {
  const room = ROOMS[agent.room] ? agent.room : "office";
  const r = ROOMS[room];
  const lit = agent.status !== "idle" && agent.status !== "offline";
  const Props = PROPS[room];
  const queue = (agent.counts && agent.counts.ready) || 0;
  const [fx, fy] = r.fig;
  const figX = (fx / 100) * r.w, figY = 218 + (room === "study" || room === "devlab" || room === "office" ? 0 : 0);
  return html`<svg class="thq-art" viewBox=${`0 0 ${r.w} 300`} role="img" aria-label=${`${agent.label || agent.title}: ${STATUS[agent.status] ? STATUS[agent.status].label : ""}`}>
    <${RoomShell} id=${agent.name} r=${r} lit=${lit}/>
    <${Props} status=${agent.status} queue=${queue} board=${board || {}}/>
    ${room === "bridge"
      ? html`<${TarsBot} x=${figX} y=${figY} status=${agent.status}/>`
      : html`<${Minifig} room=${room} status=${agent.status} x=${figX} y=${figY} scale=${1.05}/>`}
    ${room === "study" && html`<rect x="236" y="182" width="150" height="10" rx="2" fill="#6E4628"/>`}
    ${agent.status === "blocked" && html`<g class="thq-alarm"><circle cx=${r.w - 30} cy="40" r="9" fill="#FF3B30"/><rect x=${r.w - 34} y="46" width="8" height="5" fill="#8C1F1A"/></g>`}
  </svg>`;
}
