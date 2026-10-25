# Długi zwój: postać idzie od lewej do prawej przez kolejne obrazy

Inna forma niż przegląd stylów (jeden pokój, zmienia się styl). Tu jest **jeden poziomy zwój**: każdy świat to
poziomo rozciągnięty obraz, światy stykają się końcami, bohater cały czas idzie w prawo, a w chwili przekroczenia
granicy jego styl zmienia się razem ze światem. Film źródłowy: 123,7 s, 24 światy. Metoda stylów: `metoda.md`,
klatki postaci: `postacie.md`, dowody: `zasady-huashu.md` (zasady 41–43).

## Do czego
- Historia marki albo miejsca jako spacer przez epoki (np. 100 lat zakładu, kamienicy, rzemiosła), 16:9, 60–120 s.
- Intro wydarzenia kulturalnego, muzeum, festiwalu: przejście przez kilka obrazów z kolekcji, 30–60 s.
- Ścieżka klienta jako podróż przez „światy” (etapy usługi, każdy innym stylem), 30–45 s.

## Nie do
- Pion 9:16 bez miejsca na boczny ruch: ten szkielet jest poziomy (1920×1080, bohater w 720 px).
- Film bez postaci i bez klatek postaci: wtedy przegląd stylów w jednym kadrze (`metoda.md`).

## Demo i jego klatki

Demo: `$HUASHU/scripts/engine/demos/long_scroll/`, 3 odcinki (egipskie malowidło ścienne → „Japoński mostek”
Moneta → 8-bit piksel), ok. 15,6 s. **Klatki postaci z demo nie są zainstalowane w Jarvie** (przedstawiają postać
autora biblioteki). Bez nich demo nie wystartuje: silnik zgłosi brak biblioteki klatek. Szkielet (`lib/world.js`,
`lib/crossing.js`, `lib/acts.js`) i kod odcinków są do czytania i do użycia; klatki robisz własne (droga B albo C
z `postacie.md`) pod te same klucze albo pod swoje: `egypt_walk8`, `egypt_dodge`, `monet_walk`, `monet_throw`,
`8bit_walk`, `8bit_act`.

Podgląd w przeglądarce: strona silnika `$HUASHU/scripts/engine/index.html?film=demos/long_scroll`;
`&only=28_monet,14_8bit` układa tylko te odcinki (świat zaczyna się od 0), `&v=330` próbuje innej prędkości
marszu. Silnik wystawia `renderFrame(t)` i ustawia `window.__ready`; stopklatki i film robi nasz `html_wideo.py`
(nie ich `render.py`):
```sh
@@PY@@ "$HERMES_HOME/scripts/html_wideo.py" klatki "@@TOOLS_DIR@@/huashu-art-motion/scripts/engine/index.html" --serwer \
  --query "film=demos/long_scroll" --seek "t => renderFrame(t)" --gotowe "window.__ready === true" \
  --selektor "#c" --czasy 1,5,9 --arkusz out/wideo/zwoj-klatki.jpg
```
Własny film: kopia szkieletu w projekcie (`out/wideo/src/`), własne `segments/` i `frames/`; plików w `$HUASHU`
nie zmieniasz. Ścieżki `demos/long_scroll/…` w `eras.js` i w `XING.sprites` są względne wobec strony: po skopiowaniu
popraw je i sprawdź na pierwszej stopklatce, że klatki się wczytały.

## Pliki

| Plik | Za co odpowiada |
|---|---|
| `eras.js` | wejście filmu: ładuje biblioteki, `FILM_ORDER` (kolejność odcinków), rejestruje biblioteki klatek, tworzy jeden odcinek o `dur = WORLD.total`; ustawia `window.PUNCH = 0` (bez uderzenia kamery) |
| `lib/world.js` | szkielet `WORLD`: oś czasu (idzie → staje i robi interakcję → idzie), marsz bohatera, kamera, bohater przycięty na granicy, granice, znacznik roku. **Najpierw przeczytaj jego komentarz na górze** |
| `lib/crossing.js` | `XING`: wczytuje biblioteki klatek, rysuje klatkę postaci (`XING.actor`), materiał pociągnięć, światy (Monet, ukiyo-e, Van Gogh) |
| `lib/acts.js` | `ACT`: narzędzia małych scenek (np. tor kamyka puszczanego po wodzie) |
| `lib/xing2_*.js` | drobne narzędzia wspólne dla kilku odcinków, ładowane na początku pliku odcinka, gdy potrzebne |
| `segments/<id>.js` | jeden świat = jeden plik, woła `WORLD.add({...})` |
| `frames/<key>/` | biblioteka klatek: 8 przezroczystych PNG i `meta.json` (dla każdej klatki kotwica stóp `ax/ay`, rozmiar `w/h`, czy jest w powietrzu `air`; `ref_h` = wysokość stojącej postaci w pikselach) |

## Interfejs odcinka

Współrzędne są w „świecie odcinka”: x od 0 do `w`; linia gruntu `WORLD.GROUND = 760` wspólna dla całego filmu.
```js
WORLD.add({
  id: '28_monet', year: 1899, name: 'Monet, Japoński mostek',      // znacznik: rok i nazwa
  w: 2150,                                                          // szerokość świata (px), ≥ 1900, z miejscem na marsz i interakcję
  hero: { walk: 'monet_walk', mat: 'monet', h: 300 },               // biblioteka klatek marszu, materiał (XING.actor), wysokość stojącej postaci
  acts: [ { at: 760, dur: 1.6, key: 'monet_throw', frame: u => numerKlatki, y: lx => yStop, lead: 160 } ],
                                                                    // w x = at bohater staje na dur s; frame(u) zwraca klatkę ruchu (u = s od początku interakcji)
  ground: lx => y,                                                  // opcjonalnie: wysokość gruntu (mostek, schody); na obu końcach wraca do GROUND
  back(c, s) {}, front(c, s) {},                                    // tło i pierwszy plan; c już przycięty do pasa tego odcinka
  seam(c, y, sx, t) {},                                             // opcjonalnie: jak wygląda granica wejścia w ten świat; sx = x granicy na ekranie
});
```
`s` w `back`/`front`: `camX` (w świecie odcinka; ekran = `lx - s.camX`), `t` (czas filmu), `lt` (s od wejścia
w odcinek), `hx` (x bohatera w odcinku), `act` (bieżąca interakcja i jej czas `u` albo `null`), `W`, `H`, `G`
(grunt). Interakcja może mieć też `move(u)` (ruch w czasie interakcji), `dx` (przesunięcie bohatera) i własną
prędkość `v`. Bohater startuje w x = 320 pierwszego świata (cały widoczny od klatki 0).

## Dodanie odcinka

1. W `segments/` utwórz `<id>.js` z `WORLD.add({ id, year, name, w, hero, acts, back, front, seam })`. Świat
   rysuje kod. Najlepiej przerób gotową scenę stylu `scenes/<id>.js` na wersję rozciągniętą w poziomie (szerokość
   odcinka 2000–2800).
2. Klatki postaci: dla każdego świata „marsz, 8 klatek”, a gdy jest interakcja, jeszcze „interakcja, 8 klatek”.
   Model maluje je w stylu tego świata, na zielonym tle, potem wycięcie i cięcie na klatki (`malarz.py potnij`,
   `postacie.md`). Wrzuć je do `frames/<key>/` i napisz `meta.json`.
3. Dopisz `<id>` do `FILM_ORDER` w `eras.js`.
4. Zrób stopklatki po obu stronach każdej granicy; potem `@@PY@@ "$HERMES_HOME/scripts/krytyka.py" determinizm`
   na stronie filmu: deterministyczność musi przejść. Po renderze `qa_wideo.py` (duchy, skoki, zamrożone klatki).

## Ustalenia stałe (wspólne dla filmu, wpisane w szkielet)

- **Linia gruntu `WORLD.GROUND = 760`, wysokość stojącej postaci 300, bohater w 720 px kadru.** Oba końce odcinka
  (x = 0 i x = w, ±150 px) muszą mieć grunt z powrotem na 760, a horyzont najlepiej w 480–560; wtedy obie strony
  granicy się łączą. W środku mogą być mostki i schody (`ground: lx => y`).
- **Wszystkie zdarzenia licz od początku interakcji.** `WORLD.actT(odcinek)` daje chwilę startu interakcji w czasie
  filmu; `r = S.t - WORLD.actT(ME)`. Nie pisz „sekunda X od wejścia w odcinek”. Prędkość marszu całego filmu
  podniesiono potem z 330 do 560 (`WORLD.V`, `?v=`) i odcinki pisane w ten sposób nie wymagały żadnej zmiany.
- **Kamera tylko do przodu.** Cel kamery = x bohatera − 720 + `lead` (miejsce zostawione przed nim w czasie
  interakcji, domyślnie 160); z tego maksimum dotychczasowych wartości i wygładzenie Gaussem, więc ruch jest
  monotoniczny, a zatrzymanie i ruszenie bez szarpnięcia. Interakcja bez ruchu kamery: `lead: 0`.
- **Granica odcinka w języku-podpisie tego odcinka** (`seam`: brzeg papieru, szachownica pikseli, linia podziału
  barwnych pól…). To wersja zasady „przejście = język-podpis następnego stylu” dla długiego zwoju.
- **Klatkaż marszu proporcjonalny do prędkości** (`hero.fps`, domyślnie 8,5 kl./s przy prędkości 330, skalowany
  z `WORLD.V`); 8 klatek na cykl kroku. Gdy postać ma dostać jeszcze materiał stylu, napisz w odcinku
  `hero.draw(c, key, i, o, S)` i składaj sam, bez zmian we wspólnej bibliotece.
- **Nie dodawaj bohaterowi gagów, o które nikt nie prosił.** Szkielet ma funkcję pamiątek zbieranych z każdego
  świata i niesionych dalej (pole `item`, przełącznik `FILM_HAT_ITEMS`); konkuruje o uwagę ze sceną, więc jest
  domyślnie wyłączona. Włączasz tylko na prośbę właściciela.

## Muzyka do zwoju

Obraz najpierw, muzyka potem. Każdy odcinek dostaje całą liczbę bitów, a tempo stroisz odcinek po odcinku w zakresie
86–104 BPM, tak by każda granica wypadła na pierwszą miarę taktu (w źródle 24 granice, największy błąd 11,7 ms).
Ucho nie słyszy różnicy tempa ±8% między odcinkami, a słyszy zmianę instrumentu poza mocną miarą. Szczegóły
i narzędzia (`rytm.py`, `muzyka.py`): `rytm.md`.

## Kontrola
- Czy na każdej granicy stopy bohatera są na tej samej wysokości po obu stronach (grunt 760 na końcach odcinków)?
- Czy kamera nigdy się nie cofa (ani o kilka pikseli po interakcji)?
- Czy zdarzenia w odcinku są liczone od `WORLD.actT`, a nie od wejścia w odcinek?
- Czy granica wygląda jak język nowego świata, a nie jak zwykłe wycieranie?
- Czy zmiany instrumentu w muzyce wypadają na pierwszą miarę taktu na każdej granicy?
