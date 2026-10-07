---
name: iso-glow
description: Build interactive isometric line-art figures with glow lighting in a single HTML file — a dark hairline drawing where whatever is live glows in one accent colour (pressed keys, lit screens and windows, beams, wires with travelling light pulses), plus an accent-colour picker. One figure, or a gallery of several figures with sidebar navigation. Use for isometric objects, devices, buildings and cityscapes, "Fig N" plates, and glowing interactive isometric illustrations.
---

# Iso glow

Interactive isometric figures with glow lighting. Builds on **iso-figure** by Tolga Cohce (MIT, github.com/MrBongoC/ai-iso-skill): the projection kernel, the "Fig N" plate and the rule that every figure must do something real all come from there. This skill adds the lighting, colour palettes, a multi-figure gallery shell, and lessons from building twenty figures (desk objects and city buildings).

## The look in one sentence

A monochrome hairline drawing on a dark panel; **one accent colour, only on what is live** — and live things glow. Lit display content, the key you just pressed, a floor whose lights are on, a wire carrying signal, a sweeping beam. That contrast is the whole effect.

## Fast path (follow this; it is quick and can't hang)

You never need to open `assets/gallery.html` or the example files. Everything required is on this page.

1. **Write the figure to `fig.js`** in the working folder, starting from the starter below. Default to **one figure** unless the user asks for several (then put several `FIGS.push` calls in the file). Aim for roughly 150–300 lines.
2. **Assemble the page with this one command** (it copies the template, sets the name and palette, and inserts `fig.js`). Replace `<skill folder>` with the base directory shown when this skill loaded (usually `~/.claude/skills/iso-glow`), `NAME` with the piece's name and `PALETTE` with `ember` (default) or `city`:

```bash
python3 - "<skill folder>/assets/gallery.html" NAME.html fig.js "NAME" PALETTE <<'PY'
import sys
src, out, fig, name, pal = sys.argv[1:6]
s = open(src).read()
for a, b in [('<title>Iso Figures</title>', f'<title>{name}</title>'), ('Iso figures</span>', f'{name}</span>'),
             ("palette: 'ember'", f"palette: '{pal}'"), ('/* paste figure scripts here (see examples/) */', open(fig).read())]:
    assert a in s, a
    s = s.replace(a, b, 1)
open(out, 'w').write(s)
print('wrote', out)
PY
```

   No Python? Copy the template (`cp`) and make the same four text replacements with your edit tool, without reading the rest of the file.
3. **Finish without browser automation.** Do **not** install or launch Playwright, Puppeteer, headless Chrome or any other browser tool: they need downloads or can hang indefinitely. Instead re-read `fig.js` once for obvious mistakes (`node --check fig.js` if Node is available), open the page in the user's normal browser and return immediately (`open NAME.html` on macOS, `xdg-open` on Linux, `start` on Windows), and tell the user what to click or press. If they report a problem, fix that. Some preview panes show local `file://` pages as static snapshots without running scripts, which makes a working page look blank.

### Starter figure (complete and working: a lamp whose window lights up)

```js
FIGS.push({
  id: 'lamp', name: 'Lamp', hint: 'Click the lamp · space toggles', aria: 'Isometric lamp. Click it or press space to switch it on.',
  mount(stage, api) {
    const K = api.iso.frame([[0,0,0],[200,0,0],[0,160,0],[200,160,0],[70,50,98]]);   // extreme corners incl. tallest point
    const { TOP, FRONT, box } = K;
    let svg = box(0,0,0, 200,160,8, 12);                                                 // ground plate
    svg += `<g transform="${TOP(0,0,8)}"><rect class="detail" x="8" y="8" width="184" height="144" rx="8"/></g>`;
    svg += `<g class="press" id="lamp-body">${box(70,50,8, 60,60,90, 6)}</g>`;          // pressable body
    svg += `<g transform="${FRONT(70,110,98)}"><rect id="lamp-glass" class="face led" filter="url(#soft)" x="10" y="12" width="40" height="40" rx="4"/></g>`;
    stage.setAttribute('viewBox', K.viewBox); stage.innerHTML = svg;
    const st = { on: false };
    const glass = stage.querySelector('#lamp-glass'), body = stage.querySelector('#lamp-body');
    function render() { glass.classList.toggle('hot', st.on); api.power(st.on); api.readout(st.on ? 'on' : 'off'); }
    const toggle = () => { st.on = !st.on; render(); };
    body.addEventListener('click', toggle);
    render();
    return { key: e => (e.key === ' ' || e.key === 'Enter') ? (toggle(), true) : false, demo: () => api.after(200, toggle) };
  },
});
```

Grow this: more `box()` parts for the object, detail drawn on face planes (`FRONT`/`SIDE`/`TOP` groups), one state object, one `render()`, keyboard and click calling the same functions, and a `demo()` that leaves it lit. Only what is live gets the accent (`.hot`, `.lit`, `.latched`).

## Start from the template

`assets/gallery.html` is a complete, self-contained page: tokens for dark and light themes, glow filters, the shared CSS vocabulary below, the kernel, navigation, the palette picker, and an empty slot for figures. Copy it (never read it), set `<title>` and the brand text, choose a palette in `window.GALLERY`, and paste the figure code over the placeholder `/* paste figure scripts here (see examples/) */`. The placeholder is already inside a `<script>` tag, so paste plain JavaScript (one `FIGS.push({...})` per figure), not another `<script>` tag. With one figure the sidebar simply lists one item; delete the nav if you want a bare plate.

`assets/examples/desk-computer.js` (typing, power toggle, coiled cable with a light pulse) and `assets/examples/office-tower.js` (window grids, floor toggles, cascading lights) are complete figures. You don't need to read them; the starter figure above shows the structure.

## Figure contract

```js
FIGS.push({
  id: 'lamp', name: 'Desk lamp', hint: 'Click the switch · ↑↓ dim', aria: 'Isometric desk lamp. …',
  css: `[data-fig="lamp"] …`,            // optional, always scoped to the figure
  mount(stage, api) {                      // stage: a fresh <svg> per mount
    const K = api.iso.frame([/* extreme 3D corners, incl. the tallest point */]);
    const { P, D, TOP, FRONT, SIDE, rect, box, boxc, path } = K;
    stage.setAttribute('viewBox', K.viewBox); stage.innerHTML = svg;
    // listeners on stage; one state object; one render()
    return { key(e) { /* true if handled */ }, keyup(e) {}, unmount() {}, demo() {} };
  },
});
```

`api`: `iso.frame(points)` (kernel + 4:3 viewBox), `iso.slits(a0,a1,step,b0,b1,vertical=true,cls='detail')` (parallel hairlines at a0, a0+step … a1, each spanning b0→b1, in face-local units; vertical lines by default), `iso.esc`, `readout(str)`, `audio()` → `{ctx,out,analyser}` (call inside a user gesture), `after(ms,fn)` / `every(ms,fn)` / `loop(fn)` (all auto-cleared on unmount; `loop` calls `fn(timestampMs)` every animation frame and returns a stop function, so animate from the timestamp rather than counting frames), `flash(el)` (press + glow, then fade), `replay(el,'go')` (restart a one-shot animation such as a pulse), `power(bool)` (warm haze behind the figure while it is on). The figure's `name` becomes the "Fig N · Name" label, the sidebar entry and the browser-tab title; the template's brand text (`Iso figures`) is the only other name to change. Prefix every id with the figure id. `demo()` is a short scripted sequence using the same functions as real input; it runs with `?demo`, or on every arrival when `GALLERY.autoDemo` is true, so a figure can open already lit.

## Kernel (from iso-figure)

```js
const C = Math.cos(Math.PI/6), S = Math.sin(Math.PI/6);
const P = (x,y,z) => [(x-y)*C + OX, (x+y)*S - z + OY];
const D = (x,y,z) => [(x-y)*C, (x+y)*S - z];
const plane = (O,U,V) => { const o=P(...O), u=D(...U), v=D(...V); return `matrix(${u[0]} ${u[1]} ${v[0]} ${v[1]} ${o[0]} ${o[1]})`; };
const TOP   = (x,y,z) => plane([x,y,z],[1,0,0],[0,1,0]);
const FRONT = (x,y,z) => plane([x,y,z],[1,0,0],[0,0,-1]);   // y = max face, lower-left
const SIDE  = (x,y,z) => plane([x,y,z],[0,-1,0],[0,0,-1]);  // x = max face, lower-right
```

+x runs down-right, +y down-left, +z up. Draw ordinary rects, text and paths inside `<g transform="${FRONT(x, y+d, z+h)}">` (face top-left corner, local v grows downward) and they land on the plane. A box is its three visible faces. `box(x,y,z,w,d,h,r)` always draws a full, opaque top over its whole footprint, so don't use it for thin trim, ledges or bands that sit against a wall (the top would cover what is above or behind); draw those as flat strips on the wall's FRONT/SIDE plane instead. `rect(transform, w, h, r = 0, cls = 'face')` draws one rectangle on a plane, e.g. `rect(FRONT(x, y+d, z+h), w, 4, 0, 'face')` for a strip. Paint order is the only depth sort: back to front (smaller x+y first, lower z first). Faces need opaque fills. `vector-effect: non-scaling-stroke` on every stroke.

## Glow kit (classes in the template)

| Class | Use |
|---|---|
| `.face`, `.face.top`, `.face.recess`, `.detail`, `.label` | structure, decks, insets, hairline texture, printed text |
| `.press` + `.down` / `.lit` / `.latched` | pressable part; sinks 3px; transient orange glow (`api.flash`); persistent on-state |
| `.glass` + `.hot` | display glass, lit: warm fill + accent stroke |
| `.halo` + `.hot` with `filter="url(#bloom)"` | soft light spilling behind a lit glass, beam or bulb |
| `.scr`, `.scr-accent` | lit display content |
| `.led` + `.hot` | indicator on |
| `.wire` + `.hot`, `.wire-under` | wire, carrying signal; background-coloured stroke under it for crossings |
| `.pulse` + `.go` on a `path` with `pathLength="1000"` | a dash of light travelling along a wire (`api.replay`) |
| filters `#glow`, `#soft`, `#bloom` | strong glow, subtle glow, blur only |

Colour only through tokens: `--body --deck --line --detail --recess --ink --ink-hi --glass --glass-on --accent --accent-hi --accent-dim --panel`. Never a literal hue in a figure, or the palette picker and light theme break.

## Palettes

Set `window.GALLERY.palette` to `'ember'` (Ember, Cyan, Lime, Violet, Rose, Ice) or `'city'` (Sodium street-lamp amber, Tungsten, Neon, Signal, Dusk, Moon), or pass your own `[[name, darkAccent, darkHi, lightAccent, lightHi], …]`. Pick a set that matches the subject: city lights for buildings, warm ember for desk objects. Each colour needs a darker light-theme variant so it stays readable on a pale panel. The choice is remembered per viewer.

## Procedure

1. **Name the output** of each figure before drawing: typed text, a number, a sound, lights that switch, a vehicle that moves. A figure you can only watch is decoration.
2. **Decompose** into 3–8 boxes; write `(x,y,z,w,d,h)` down first. Give the long, detailed face to FRONT or SIDE.
3. **Draw back to front**, detail on faces, texture by repetition (slits, window grids, ribs). Start from a ground plate (rounded box, inset line, screws).
4. **Light it**: decide what glows in each state. At least one large lit element per figure (a display, a lit floor band, a beam, a sign) should read as solid accent with bloom.
5. **Wire state**: one state object, one `render()`, keyboard and pointer calling the same functions. Readout bottom-right, terse and lowercase: `on · 9 chars · key t`.
6. **Frame** with `api.iso.frame` including the tallest point. **Finish** as in Fast path step 3: open it in the user's browser and hand over; no browser automation.

## Lessons (from building twenty figures)

- **Make the lit state unmistakable.** A faint glow was the most common failure. Push opacity and bloom until it reads at thumbnail size.
- **Point the detail at the viewer.** Only the top, FRONT and SIDE faces show. A server rack with its front on the narrow face looked like a blank box.
- **Moving things**: animate with `api.loop`, timed from `performance.now()`; move along an axis by translating with `D(dx,dy,dz)`. Objects that pass in front of and behind others need their draw order recomputed per frame.
- **Filters on straight lines**: the template's filters use `filterUnits="userSpaceOnUse"` because a perfectly horizontal or vertical path has a zero-height box and vanishes under a default filter region.
- **Escape before writing text into SVG**; clip scrolling screen text to its glass with a `<clipPath>`.
- **Rounded boxes**: `box(..., r)` draws a rounded top plus one continuous side wall, so corners line up. Don't round the FRONT and SIDE faces separately; three separately rounded faces leave notched, misaligned corners.
- **Round things** (domes, lamp shades, beams) can be drawn as hulls of projected circles or as stacked boxes; keep the hairline style.
- **After a nav click, focus the stage** (the template does this) so Space and Enter go to the figure instead of re-clicking the button.
- Audio only after a user gesture; wrap it in try/catch.

## Footer credit

The template ends with a light footer, **Made with ISO-GLOW ↗**, linking to https://iso-glow.vercel.app. Keep it by default, including on single-figure pages you build without the template (a small, muted link under the figure). Remove it whenever the user asks or says they don't want it. Never turn it into an author credit such as "Made by …"; the finished work belongs to the user.

## Don'ts

- No real company logos, product silhouettes or trademarks on objects or screens; invent signage and glyphs.
- No hand-written skewed polygons for faces; use `plane()`.
- No external scripts; the page must run when opened from disk.
- No hue anywhere except through the accent tokens.
- Give the svg `role="img"` and an `aria-label` that says what it is and how to operate it (the template sets this from `aria`).
