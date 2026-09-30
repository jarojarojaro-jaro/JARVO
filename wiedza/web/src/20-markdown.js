// Renderer Markdown notatek: tekst → elementy (bez innerHTML). Linki [[ścieżka|etykieta]] otwierają notatkę w zakładce,
// linki http(s) otwierają się w nowej karcie, bloki generowane (<!-- Jarvo:GEN … -->) dostają dyskretną etykietę.

const INLINE_RE = /(\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\])|(\[([^\]]+)\]\((https?:\/\/[^)\s]+)\))|(`([^`]+)`)|(\*\*(.+?)\*\*)|(\*([^*\n]+?)\*)/g;

function inline(text, onOpen, keyBase) {
  const out = [];
  let last = 0, m, i = 0;
  const re = new RegExp(INLINE_RE.source, "g");   // własna instancja: rekurencja (pogrubienie w kursywie) nie zeruje lastIndex
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const k = `${keyBase}-${i++}`;
    if (m[1]) {
      const target = m[2].trim().replace(/\.md$/, ""), label = (m[3] || m[2]).trim();
      out.push(html`<button key=${k} type="button" class="twz-wikilink" title=${target} onClick=${() => onOpen && onOpen(target)}>${label}</button>`);
    } else if (m[4]) {
      out.push(html`<a key=${k} href=${m[6]} target="_blank" rel="noopener noreferrer">${m[5]}</a>`);
    } else if (m[7]) {
      out.push(html`<code key=${k}>${m[8]}</code>`);
    } else if (m[9]) {
      out.push(html`<strong key=${k}>${inline(m[10], onOpen, k)}</strong>`);
    } else if (m[11]) {
      out.push(html`<em key=${k}>${inline(m[12], onOpen, k)}</em>`);
    }
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function Markdown({ text, onOpen }) {
  const lines = String(text || "").replace(/\r/g, "").split("\n");
  const blocks = [];
  let i = 0, key = 0;
  const push = (node) => blocks.push(node);
  while (i < lines.length) {
    const line = lines[i];
    const k = `b${key++}`;
    if (!line.trim()) { i++; continue; }
    let m;
    if ((m = line.match(/^<!-- Jarvo:GEN (\w+) -->$/))) {
      push(html`<div key=${k} class="twz-gen-mark">${L("blok generowany", "generated block")}: ${m[1]}</div>`); i++; continue;
    }
    if (/^<!-- \/Jarvo:GEN \w+ -->$/.test(line) || /^<!--.*-->$/.test(line)) { i++; continue; }
    if (line.startsWith("```")) {
      const code = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) code.push(lines[i++]);
      i++;
      push(html`<pre key=${k}><code>${code.join("\n")}</code></pre>`); continue;
    }
    if ((m = line.match(/^(#{1,6})\s+(.*)$/))) {
      const Tag = `h${Math.min(6, m[1].length + 1)}`;   // h1 notatki → h2 (tytuł jest w nagłówku panelu)
      push(html`<${Tag} key=${k}>${inline(m[2], onOpen, k)}</${Tag}>`); i++; continue;
    }
    if (/^(-{3,}|\*{3,})$/.test(line.trim())) { push(html`<hr key=${k}/>`); i++; continue; }
    if (line.startsWith(">")) {
      const q = [];
      while (i < lines.length && lines[i].startsWith(">")) q.push(lines[i++].replace(/^>\s?/, ""));
      push(html`<blockquote key=${k}>${q.map((l, j) => html`<p key=${j}>${inline(l, onOpen, `${k}-${j}`)}</p>`)}</blockquote>`); continue;
    }
    if (/^\s*([-*+]|\d+\.)\s+/.test(line)) {
      const items = [];
      const ordered = /^\s*\d+\./.test(line);
      while (i < lines.length && /^\s*([-*+]|\d+\.)\s+/.test(lines[i])) {
        let item = lines[i++].replace(/^\s*([-*+]|\d+\.)\s+/, "");
        while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*([-*+]|\d+\.)\s+/.test(lines[i])) item += " " + lines[i++].trim();
        items.push(item);
      }
      const Tag = ordered ? "ol" : "ul";
      push(html`<${Tag} key=${k}>${items.map((it, j) => html`<li key=${j}>${inline(it, onOpen, `${k}-${j}`)}</li>`)}</${Tag}>`); continue;
    }
    if (line.startsWith("|")) {
      const rows = [];
      while (i < lines.length && lines[i].startsWith("|")) rows.push(lines[i++]);
      const cells = (r) => r.replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      const head = cells(rows[0]);
      const body = rows.slice(1).filter((r) => !/^\|?\s*:?-{2,}/.test(r)).map(cells);
      push(html`<table key=${k}><thead><tr>${head.map((c, j) => html`<th key=${j}>${inline(c, onOpen, `${k}h${j}`)}</th>`)}</tr></thead>
        <tbody>${body.map((r, ri) => html`<tr key=${ri}>${r.map((c, j) => html`<td key=${j}>${inline(c, onOpen, `${k}-${ri}-${j}`)}</td>`)}</tr>`)}</tbody></table>`);
      continue;
    }
    const para = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,6}\s|```|>|\||\s*([-*+]|\d+\.)\s+|<!--)/.test(lines[i]) && !/^(-{3,}|\*{3,})$/.test(lines[i].trim())) para.push(lines[i++]);
    if (!para.length) { i++; continue; }
    push(html`<p key=${k}>${inline(para.join(" "), onOpen, k)}</p>`);
  }
  return html`<div class="twz-md">${blocks}</div>`;
}
