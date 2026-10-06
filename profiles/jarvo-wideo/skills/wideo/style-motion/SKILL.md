---
name: style-motion
description: "15 stylów motion design: karta, wzór, moduły JS."
version: 1.2.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [video, motion-design, style, animation, canvas, webgl]
    related_skills: [rodzaje-filmu, film-z-kodu, typografia-edit, lektor-i-dzwiek, kontrola-wideo]
  jarvo:
    agent: jarvo-wideo
    autonomy: A1
    reviewed: "2026-10-05"
---

# Style motion design

Piętnaście stylów, które ekspert rozpoznaje w sekundę: rysunek z wrzącą linią, izometria, płaski wektor, morph, HUD,
Bauhaus, synthwave, pixel art i inne. Każdy ma kartę: po czym go poznać (z liczbami), jak go zbudować naszymi
modułami, rytm 10 s rozpisany na dłuższy film, dźwięk, pułapki i kontrolę. Do każdego jest film-wzór 10 s
z kodem (mg-styles-15, MIT, Vincentwei1021): oglądamy go i bierzemy techniki, nie sam film.

## Kiedy
- Rodzaj filmu już wybrany (`rodzaje-filmu`: motion graphics, logo i intro, promo, typografia), a brief nazywa jeden
  z tych stylów albo marka do niego pasuje (tabela niżej).
- Krótki film 10–30 s albo wstawka do dłuższego, budowany od zera jako nasza strona HTML (kontrakt jarvo).

## Nie do
- Cały film 30–75 s w jednym z 43 stylów kina (akwarela, anime, miedzioryt, hologram, plakat…) z gotowym
  silnikiem → `lemo-opuscar` (`film-z-kodu`). Tu budujemy sami, krócej i lżej.
- Kinowy film produktu ze zrzutów strony albo aplikacji → `video-shotcraft` (`film-z-kodu`).
- Explainer z lektorem, dane, historia z bohaterem → plik rodzaju w `rodzaje-filmu` (styl z tej listy może być
  jego wyglądem, ale strukturę daje rodzaj).

## Style
| Styl | Do czego (przykłady) | Karta | Moduły `/_lib/jarvo/` |
|---|---|---|---|
| Rysunek z wrzącą linią (cel, line boil) | ciepła marka, rzemiosło, piekarnia, dzieci, „zrobione ręcznie” | `references/kreska.md` | `kreska.js`, `plotno.js` |
| Rysunek jedną linią | elegancka usługa, gabinet, architekt, logo rysujące się samo | `references/rysunek-linia.md` | `kreska.js` |
| Płaski wektor | usługa w 3 krokach, aplikacja, gmina, szybki explainer | `references/plaski-wektor.md` | `ruch.js`, `morph.js` |
| Izometria | proces, logistyka, fabryka, SaaS „jak to działa”, mapa firmy | `references/izometria.md` | `ruch.js` |
| 3D (render) | produkt w świetle studia, opakowanie, sprzęt, premium | `references/3d.md` | Three.js `/_lib/three/` |
| Morph kształtów | logo, rebranding, „z A w B”, przemiana problemu w rozwiązanie | `references/morph.md` | `morph.js` |
| Naklejki i notes | sklep, kawiarnia, event, social z humorem, młoda marka | `references/naklejki.md` | `plotno.js`, `ruch.js` |
| Kolaż | moda, kultura, festiwal, historia firmy ze zdjęć klienta | `references/kolaz.md` | `plotno.js` |
| HUD (interfejs sci-fi) | technologia, cyberbezpieczeństwo, dane na żywo, gaming | `references/hud.md` | `crt.js` (`hud`) |
| Zorza i szkło | fintech, AI, aplikacja premium, uroda, spokój | `references/zorza-szklo.md` | WebGL, `plotno.js` |
| Płyn | kosmetyki, napoje, sztuka, płynne przejścia marki | `references/plyn.md` | WebGL, `ruch.js` |
| Bauhaus (plakat) | kultura, architektura, design, szkoła, wystawa | `references/bauhaus.md` | `plotno.js` (`druk`, `polton`) |
| Synthwave (neon, VHS) | muzyka, gaming, nocne wydarzenie, retro promocja | `references/synthwave.md` | `crt.js` (`vhs`, `crt`) |
| Pixel art | gra, aplikacja dla młodych, retro, nostalgia, „level up” | `references/pixel.md` | `piksel.js`, `crt.js` |
| Napisy show (telewizyjne) | nagranie klienta na social: reakcje, humor, kulisy, 9:16 | `references/napisy-show.md` | kroje, `ruch.js` |

Jeden styl na film. Dwa style tylko jako zamierzone przejście (np. szkic z wrzącą linią → płaski wektor) z jednym
zdaniem uzasadnienia w RAPORT.md.

## Przebieg (wszystko samo, bez zatwierdzania po drodze)
1. **Styl.** Z briefu albo z marki: tabela wyżej. Niejasne → styl, który najlepiej niesie cel z karty filmu.
2. **Karta.** Czytasz tylko kartę swojego stylu (inne to półka, nie lektura).
3. **Wzór.** Okładka `$MGSTYLES/videos/<slug>.jpg`, klatki wzoru `html_wideo.py klatki … --preset mg` (polecenie
   w karcie) i kod z miejsc, które karta wskazuje. Instalacja: `python3 $HERMES_HOME/scripts/narzedzia.py instaluj mg`,
   potem `eval "$(python3 $HERMES_HOME/scripts/narzedzia.py env mg)"`. Z wzoru bierzesz techniki, liczby i proporcje,
   nigdy fabułę, teksty, postacie ani zdjęcia.
4. **Brief** (`out/wideo/src/BRIEF.md`): styl i jego cechy z karty, paleta z marki (role kolorów jak we wzorze),
   oś zdarzeń w `out/wideo/src/cues.json` (jedno źródło czasu dla obrazu i dźwięku).
5. **Kadry kluczowe przed ruchem.** Strona `out/wideo/src/index.html` w kontrakcie jarvo
   (`rodzaje-filmu/references/kontrakt-html.md`): moduły z `/_lib/jarvo/`, kroje z `/_lib/kroje/kroje.css`
   (polskie znaki), losowość z ziarna. 6–8 stopklatek `html_wideo.py klatki … --preset jarvo --czasy … --arkusz`: każda ma wyglądać
   jak plakat (kompozycja, hierarchia, oddech, 5% marginesu). Poprawiasz, aż nic nie wygląda jak szablon.
6. **Ruch.** Charakter ruchu z marki (`ruch.js`, `rodzaje-filmu/references/ruch-i-kompozycja.md`), hak od klatki 0,
   kulminacja w 60–65% z krótką ciszą tuż przed nią, logo i hasło po 80%, końcowy kadr stoi 0,8–1,2 s z drobnym ruchem.
7. **Dźwięk** z tej samej osi (`cues.json`): skill `lektor-i-dzwiek`, gatunek i uderzenia z karty, −14 LUFS.
   Najpierw muzyka pisana pod ten film: `muzyka.py zrob out/wideo/film.mp4 -o out/wideo/final.mp4 --cues
   out/wideo/src/cues.json --styl <styl>` (przepis mgaudio dla stylu, kulminacja i logo z osi, efekty w tych samych
   chwilach; `muzyka.py przepisy` pokazuje alternatywę bliższą karcie, np. kreska → `--przepis variety`; brak
   dodatku → `narzedzia.py instaluj mgaudio`). Muzyka klienta albo podkład z biblioteki: synteza efektów
   `sound.mjs` z `--bed` (efekty osobnym plikiem, nie wmiksowane w muzykę). Oddajesz projekt edytora:
   `projekt.py z-kodu <film> --obraz out/wideo/film.mp4 --z-muzyki out/wideo/final.muzyka.json --render` (albo
   `--efekty`/`--muzyka` z plików, `film-z-kodu/references/projekt-edytora.md`), potem `qa_wideo.py --z-kodu`.
   Efekty z biblioteki CC0 dokładasz już do tego projektu: `projekt.py dodaj-dzwiek <film> <id> --start S` (raz na
   efekt) i `projekt.py render <film> --out <film>`.
8. **Kontrola:** punkty „Kontrola” z karty, `html_wideo.py pomiar … --preset jarvo` pełny i aktualny bez błędów, potem `kontrola-wideo`.
9. **Render szybki:** `html_wideo.py wideo out/wideo/src/index.html --preset jarvo --dlugosc N -o out/wideo/film.mp4` bez `--subklatki` (motion blur
   tylko na prośbę właściciela), przeglądarki równolegle same (`--rownolegle`). Czas: `klatki` na 2–3 najcięższych
   chwilach × liczba klatek ÷ przeglądarki (płótno 2D ok. 0,2–0,5 s na klatkę, WebGL na procesorze 2–15 s). Gdy
   wyjdzie dłużej niż kilka minut, najpierw mówisz właścicielowi, ile.

## Zasady
- **Wzór to nauka, nie film klienta.** Kod wzoru jest na MIT: przeniesiona funkcja dostaje komentarz
  `// za mg-styles-15 (MIT), demos/<slug>/<plik>`. Moduły Jarva już mają przeniesione silniki stylów: najpierw one.
- **Tylko pewne źródła obrazu.** Zdjęcia, naklejki i tekstury z wzorów 06, 18, 19 oraz ziarno, kurz i washi
  z `$MGSTYLES/assets/textures` nie mają podanego źródła: nigdy w filmie. Papier, ziarno, kurz, winieta, druk płyt
  i raster: `plotno.js`. Zdjęcia: tylko klienta albo stock z darmową licencją (`material-stock`).
- **Marka przed wzorem.** Paleta, krój i ton z marki; wzór daje proporcje kolorów, rytm i technikę.
- **9:16 to nowy układ**, nie zmiana rozmiaru: wzory mają kadr 1920×1080 na sztywno.
- **Polskie znaki:** każdy krój sprawdzasz na „Zażółć gęślą jaźń”; kroje wzorów (chińskie) zastępujesz krojem
  z `/_lib/kroje/`. Krój tekstu na kanwie wczytujesz przed `__ready` z próbką polskich liter
  (`document.fonts.load('64px "Anton"', 'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ')`), inaczej pierwsze klatki wyjdą innym krojem.
- **Ocena:** gotowy film ocenia właściciel. Nie ma recenzenta AI w pętli; twoja kontrola to karta, `pomiar`
  i `kontrola-wideo`, a w RAPORT.md piszesz uczciwie, co wyszło najlepiej, co najsłabiej.

## Pułapki
- Styl „na oko”: brak cech z karty (np. wrzenie linii bez rysunku co 2 klatki, izometria bez kąta 30°).
- Pięć efektów zamiast jednego języka; tekstury i blur, które na telefonie robią breję.
- Kopia wzoru z podmienionym tekstem: to test techniczny, nigdy film klienta.
- Losowość bez ziarna albo animacja z zegara: każdy render inny, klatki gubione.
