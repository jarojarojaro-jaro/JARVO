# Kontrakt figury izometrycznej (iso-glow, nakładka Jarva)

Streszczenie po polsku z `assets/iso-glow/ISO-GLOW.md` (iso-glow, April Zhu, na iso-figure, Tolga Cohce; MIT) plus
to, co dokłada Jarvo (`iso.py`, `iso_jarvo.js`). Oryginał po angielsku czytaj tylko, gdy tu czegoś brakuje.

## Wygląd w jednym zdaniu
Monochromatyczna cienka kreska na ciemnym panelu; **jeden kolor akcentu, tylko na tym, co żyje**, i to świeci:
zapalony ekran, wciśnięty klawisz, piętro z włączonym światłem, kabel z sygnałem, snop światła. Cały efekt to ten kontrast.

## Plik figury
Jeden plik `.js`, w nim jedno albo kilka `FIGS.push({...})` (kolejność = Rys. 1, 2, 3). Zwykle 150–300 linii.

```js
FIGS.push({
  id: 'lampa', name: 'Lampka', hint: 'Klik w lampkę · spacja wł./wył.',
  aria: 'Izometryczna lampka. Kliknij ją albo naciśnij spację, żeby ją włączyć.',
  css: `[data-fig="lampa"] …`,              // opcjonalnie, zawsze zawężone do figury
  mount(stage, api) {                         // stage: świeży <svg> przy każdym wejściu
    const K = api.iso.frame([[0,0,0],[200,0,0],[0,160,0],[200,160,0],[70,50,98]]);   // skrajne narożniki + najwyższy punkt
    const { TOP, FRONT, SIDE, box, path } = K;
    let svg = box(0,0,0, 200,160,8, 12);                                               // podstawa
    svg += `<g class="press" id="lampa-korpus">${box(70,50,8, 60,60,90, 6)}</g>`;     // część do kliknięcia
    svg += `<g transform="${FRONT(70,110,98)}"><rect id="lampa-szklo" class="face led" filter="url(#soft)" x="10" y="12" width="40" height="40" rx="4"/></g>`;
    stage.setAttribute('viewBox', K.viewBox); stage.innerHTML = svg;
    const st = { on: false };                                                          // jeden obiekt stanu
    const szklo = stage.querySelector('#lampa-szklo');
    function render() { szklo.classList.toggle('hot', st.on); api.power(st.on); api.readout(st.on ? 'wł.' : 'wył.'); }
    const przelacz = () => { st.on = !st.on; render(); };
    stage.querySelector('#lampa-korpus').addEventListener('click', przelacz);
    render();
    return { key: e => (e.key === ' ' || e.key === 'Enter') ? (przelacz(), true) : false,
             unmount() {}, demo: () => api.after(200, przelacz) };
  },
});
```
- `id` jest przedrostkiem każdego id w figurze (`lampa-szklo`), `name` = podpis „Rys. N · nazwa” i tytuł karty.
- `hint` (krótko, co kliknąć), odczyt `api.readout('wł. · 92°c')` (prawy dolny róg, krótko, małe litery), `aria`
  (co to jest i jak tego użyć): po polsku.
- Jeden obiekt stanu, jedna funkcja `render()`, klawiatura i klik wołają te same funkcje.
- `demo()`: krótki scenariusz tymi samymi funkcjami co prawdziwe wejście; zostawia figurę zapaloną. Z niego są
  PNG w chwili t i film, więc ma pokazać to, co figura robi najlepiej, w pierwszych 2–5 s.

## api
- `iso.frame(punkty)` → kernel + viewBox 4:3; `iso.slits(a0,a1,krok,b0,b1,pionowe=true,klasa='detail')` = równoległe
  kreski; `iso.esc(s)` = tekst bezpieczny do SVG (zawsze przed wpisaniem tekstu).
- `readout(s)`, `hint(s)`, `power(bool)` (ciepła poświata za figurą, gdy włączona), `flash(el)` (wciśnięcie
  + błysk), `replay(el,'go')` (powtórz jednorazową animację, np. impuls `.pulse`), `audio()` (tylko po geście; try/catch).
- **Czas (Jarvo):** `after(ms,fn)`, `every(ms,fn)`, `loop(fn)` (fn(ts) co klatkę, zwraca stop), `now()` (ms),
  `clear(uchwyt)`. Wszystko czyszczone przy zmianie figury. W renderze (`?render=1`: PNG, film) to zegar wirtualny:
  `window.__seek(t)` przesuwa czas strony, a animacje CSS stają w tej samej chwili. `setTimeout`, `setInterval`,
  `requestAnimationFrame`, `Date.now`, `performance.now`, `Math.random` wprost = uwaga kontroli (film się rozjedzie).
  Ruch licz z `ts` z `api.loop`, nie z licznika klatek.

## Kernel
`P(x,y,z)` → punkt na ekranie; `+x` w dół w prawo, `+y` w dół w lewo, `+z` w górę. Płaszczyzny ścian: `TOP(x,y,z)`,
`FRONT(x,y,z)` (ściana o największym y, lewa dolna), `SIDE(x,y,z)` (ściana o największym x, prawa dolna). Zwykłe
`rect`, `text`, `path` w `<g transform="${FRONT(x, y+d, z+h)}">` (lewy górny róg ściany, lokalne v w dół) lądują
na ścianie razem z tekstem i zaokrągleniami.
- `box(x,y,z,w,d,h,r)`: bryła = trzy widoczne ściany (r > 0: zaokrąglona góra i jedna ciągła ściana boczna).
  Zawsze rysuje pełną, nieprzezroczystą górę: cienkich listew i pasów przy ścianie nie rób boxem, tylko paskiem
  `rect(FRONT(…), w, 4, 0, 'face')` na ścianie.
- `boxc(…, klasa)`: bryła z dodatkową klasą (np. do podświetlania całej bryły), `path(punkty3d)` → `d` ścieżki.
- **Kolejność rysowania to jedyne sortowanie głębi:** od tyłu do przodu (mniejsze x+y najpierw, niżej najpierw).
  Ściany mają nieprzezroczyste wypełnienie, każda kreska `vector-effect: non-scaling-stroke` (klasy to mają).

## Klasy świecenia (w szablonie)
| Klasa | Do czego |
|---|---|
| `.face`, `.face.top`, `.face.recess`, `.detail`, `.label` | bryły, blaty, wnęki, faktura z kresek, nadruki |
| `.press` + `.down` / `.lit` / `.latched` | część do wciśnięcia; opada 3 px; chwilowy błysk (`api.flash`); stały stan włączony |
| `.glass` + `.hot` | szyba wyświetlacza, zapalona: ciepłe wypełnienie + obrys w akcencie |
| `.halo` + `.hot` z `filter="url(#bloom)"` | miękkie światło za zapaloną szybą, snopem, żarówką |
| `.scr`, `.scr-accent` | treść zapalonego wyświetlacza |
| `.led` + `.hot` | kontrolka włączona |
| `.wire` + `.hot`, `.wire-under` | kabel, z sygnałem; pod spodem kreska koloru tła na skrzyżowaniach |
| `.pulse` + `.go` na `path` z `pathLength="1000"` | kropla światła biegnąca po kablu (`api.replay`) |
| filtry `#glow`, `#soft`, `#bloom` | mocne świecenie, delikatne, samo rozmycie |

Kolory **tylko** przez tokeny: `--body --deck --line --detail --recess --ink --ink-hi --glass --glass-on --accent
--accent-hi --accent-dim --panel`. Wpisany kolor (`#ff7a1a`, `rgb(…)`) = błąd kontroli: psuje paletę marki i jasny motyw.

## Palety
`--paleta ember` (Ember, Cyan, Lime, Violet, Rose, Ice: przedmioty na biurku) albo `city` (Sodium, Tungsten, Neon,
Signal, Dusk, Moon: budynki, miasto); `--akcent` z kolorem marki klienta zastępuje paletę (wariant na jasny motyw
skrypt liczy sam). Widz wybiera kolor w przełączniku; PNG i film: `--akcent <nazwa>`.

## Procedura
1. **Wynik figury przed rysunkiem:** napis, liczba, dźwięk, światła, ruch pojazdu.
2. **Rozkład na 3–8 brył:** wypisz `(x,y,z,w,d,h)` w komentarzu. Długą, bogatą ścianę daj na FRONT albo SIDE.
3. **Od tyłu do przodu**, detal na ścianach, faktura przez powtórzenie (kreski, siatka okien, żebra). Zacznij od
   podstawy (zaokrąglona płyta, linia wewnętrzna, śruby).
4. **Światło:** co świeci w każdym stanie. Co najmniej jeden duży zapalony element (wyświetlacz, pas pięter, snop,
   szyld) czyta się jako pełny akcent z poświatą.
5. **Stan:** jeden obiekt, jedno `render()`, klawiatura i klik wołają to samo; odczyt krótki.
6. **Kadr:** `api.iso.frame` z najwyższym punktem i wystającymi częściami (inaczej tekst poza kadrem w kontroli).

## Lekcje (z dwudziestu figur iso-glow)
- **Stan zapalony ma być nie do przeoczenia.** Za słaba poświata to najczęstszy błąd: podkręć krycie i bloom,
  aż widać ją w miniaturze.
- **Detal w stronę widza:** widać tylko górę, FRONT i SIDE. Szafa serwerowa z frontem na wąskiej ścianie to pudło.
- **Ruch:** `api.loop(ts)`, przesunięcie wzdłuż osi przez `D(dx,dy,dz)`; rzeczy przechodzące przed i za innymi
  wymagają przeliczenia kolejności co klatkę.
- Filtry na prostych liniach działają (szablon ma `filterUnits="userSpaceOnUse"`).
- Tekst przesuwający się po ekranie przytnij do szyby `<clipPath>`; tekst zawsze przez `iso.esc`.
- Zaokrąglenia tylko przez `box(…, r)`; trzy osobno zaokrąglone ściany dają poszarpane rogi.
- Rzeczy okrągłe (kopuły, klosze, snopy): obrys rzutowanych okręgów albo stos brył, w stylu cienkiej kreski.
- Dźwięk tylko po geście człowieka, w try/catch (w filmie go nie ma: dźwięk dokłada Wideograf).

## Nakładka Jarva (iso.py)
- Polskie napisy strony (Rys., Wstecz/Dalej, Kolor poświaty), `lang="pl"`, krój JetBrains Mono (OFL, polskie znaki)
  w pliku zamiast Google Fonts (`--kroj systemowy` = bez kroju w pliku).
- Tryb kadru (`--kadr` / `?kadr`), podpis (`?podpis`), motyw, akcent, przezroczyste tło (`?tlo=0`), wybór figury
  (`?figura=id`) i demo (`?demo`) z parametrów adresu.
- Render (`?render=1`): kadr + zegar wirtualny (`iso_jarvo.js`), `window.__seek(t)`, `__ready`, `__W`/`__H`:
  kontrakt `html_wideo.py --preset jarvo`. Cofnięcie czasu = figura od nowa i znów do przodu.
- Stopka iso-glow zostaje na naszych materiałach; `--bez-stopki` na pracach dla klientów.
- Zakazy z oryginału: żadnych prawdziwych logo, sylwetek markowych produktów ani znaków towarowych; ściany tylko
  przez `plane()` (TOP/FRONT/SIDE), nie ręcznie skośne wielokąty; bez zewnętrznych skryptów; `svg role="img"`
  i `aria-label` ustawia szablon z `aria`.
