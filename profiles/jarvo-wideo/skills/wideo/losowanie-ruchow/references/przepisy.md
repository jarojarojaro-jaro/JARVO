# Przepis z biblioteki → nasz kontrakt HTML

Przepisy w bibliotece (`assets/cinetic/techniques.json`, cinetic, MIT) są pisane dla Remotion przy 60 kl./s.
U nas animacja to strona z `window.__seek(t)` i czystymi funkcjami czasu `t` w **sekundach**
(`rodzaje-filmu/references/kontrakt-html.md`). Ten plik mówi, co czym zastąpić. Przepisu nie kopiujesz
słowo w słowo: bierzesz ruch, liczby i kolejność, a przedmioty, kolory i tekst są z filmu.

## Czas
- **Klatki → sekundy:** `f(n) = n / 60` z `tokeny.js`. „over 18 f” = `f(18)` = 0,3 s, „f24–66” = od `f(24)` do `f(66)`.
  Liczby zostają jak w przepisie, niezależnie od fps renderu (`html_wideo.py --fps`).
- `fd(frame)` (stan dyskretny: liczba znaków, licznik) → `fd(t * 60) / 60` albo `Math.round(t * fps)` w klatkach renderu.
- `b(bar, beat)` (siatka taktów) → czasy taktów z `rytm.py muzyka.mp3` (BPM, takty, drop); bez muzyki: 120 BPM,
  takt = 2 s, bit = 0,5 s.
- `<Sequence from={a}>` i `<Loop durationInFrames={P}>` → `t - a` i `t % P` w funkcji sceny.

## Tokeny (z `/_lib/jarvo/tokeny.js`, te same nazwy co w przepisie)
```js
import { E, SPR, f, prog, tw, mix, lmix, spr, hitPulse, squash, arrive, depart, blurIn, blurOut, breath,
         stagger, inertia, rand, mixColor, fd } from '/_lib/jarvo/tokeny.js';
```
| W przepisie | U nas | Uwagi |
|---|---|---|
| `E.out`, `E.cam`, `E.smooth`, … | `E.out`, `E.cam`, `E.smooth`, … | te same krzywe (cubic-bezier); w GSAP podajesz funkcję: `ease: E.out` |
| `prog(f, a, b, E.x)` | `prog(t, f(a), f(b), E.x)` | postęp 0–1, przycięty |
| `tw(f, a, b, v0, v1, E.x)` | `tw(t, f(a), f(b), v0, v1, E.x)` | wartość od v0 do v1 |
| `interpolate(…, {easing})` | `tw` / `prog` (kilka odcinków: kilka wywołań) | zawsze przycięte |
| `spr(f, start, SPR.snap)`, `spring()` | `spr(t, f(start), SPR.snap)` | wzór zamknięty, sekundy; `SPR` jak w przepisie |
| `lmix(a, b, u)` | `lmix(a, b, u)` | skala i zoom w log |
| `mixColor(C.a, C.b, u)` | `mixColor(a, b, u)` | OKLab; kolory z `marka.css` / tokenów marki |
| `hitPulse(t, 2, 5)` (klatki) | `hitPulse(t - t0, f(2), f(5))` | sekundy |
| `squash(t)` | `squash(t - tKontaktu)` | `{along, across}` |
| `inertia(f, start, v0, d)` (px/kl.) | `inertia(t, f(start), v0 * 60, d)` | v0 w px/s |
| `arrive`, `depart`, `blurIn`, `blurOut`, `breath`, `stagger`, `rand` | te same | `stagger(i, n, f(24))` w sekundach |
| `C.ink`, `C.accent`, `C.paper` | zmienne CSS marki (`marka.css`) | paleta z marki, nie z przepisu |
| `AbsoluteFill` | `<div style="position:absolute; inset:0">` | |
| `Img`, `staticFile()` | `<img src="assets/…">` (pliki obok strony) | |
| motion blur, `<CameraMotionBlur>` | **bez**: `smuga` / `duchy` z `ruch.js` | nasza zasada szybkiego renderu |

## Komponenty z przepisów → nasze moduły
| W przepisie | U nas |
|---|---|
| `camera(lc(A, B, t))`, `Shot`, `toScreen` (kamera nad światem) | jedna transformacja świata: `strona.js` `kamera`/`najazd` albo `ujecia.js` `paralaksa`, `dollyZoom`; zoom przez `lmix` |
| `Words`, `Chain`, `MaskRise` (słowa i fragmenty) | `typografia.py` (bloki z rytmem czytania) albo własne słowa na `E.outSoft` + `arrive`; zasady w `typografia-edit` |
| `TypeOn`, `typeOn` (pisanie) | `ujecia.js` `pisanie` |
| `Roll`, `countSteps` (licznik) | `ujecia.js` `licznikBebnowy` |
| `Cursor`, `cursorArc`, `pressAt` (kursor i klik) | `ujecia.js` `klik`, `strona.js` `wycieczka` |
| `Morph` (kształt w kształt) | `morph.js` `przemiana` |
| `Iris`, maski i wycięcia | `clip-path` / maska SVG po `prog` |
| `RackFocus` (ostrość) | `filter: blur()` po `blurIn` / `blurOut` (gotowe przed 60% ruchu) |
| zrzut UI, `safeBox` | `assety.py` (zrzut 2×, wycinki, `layout.json`) |

## Dźwięk z przepisu
Przepis często mówi, gdzie dźwięk („tick on each step”, „whoosh at the apex”). Szczyt prędkości ruchu = miejsce
na „whoosh”, osiadnięcie 97% = miejsce na „klik”. Efekty z naszej biblioteki (`lektor-i-dzwiek`, zdania dźwiękowe),
nie z przepisu.

## Czego nie bierzemy
- Motion bluru i podklatek (`--subklatki` zostaje na 1): smugi zamiast.
- Zakazów stylu biblioteki (szeryfy, kursywa, pomarańcz, fiolet, gradienty, poświata): decyduje marka.
- Lintów i kontroli z Remotion: u nas pomiar `html_wideo.py`, `qa_wideo.py`, `krytyka.py`.
