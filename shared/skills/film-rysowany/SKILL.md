---
name: film-rysowany
description: "Film rysowany: ręka rysuje i pisze pod lektora, 21 stylów."
version: 1.0.0
author: "Jarvo (silnik: silnikjava, MIT)"
license: MIT
metadata:
  hermes:
    tags: [video, explainer, whiteboard, hand-drawn, handwriting, narration, canvas, reels]
    related_skills: [pracownia-malarza, voxel-ascii, film-z-kodu, rodzaje-filmu, lektor-i-dzwiek, kontrola-wideo]
  jarvo:
    autonomy: A1
    reviewed: "2026-11-26"
---

# Film rysowany (silnikjava)

**Co to jest:** film objaśniający, w którym ręka rysuje schematy i pisze odręcznie w tempie lektora.
**Kiedy użyć:** trzeba wyjaśnić coś krok po kroku w wyglądzie tablicy, zeszytu albo kartki.
**Przykład zlecenia:** „Zrób 40-sekundowy film na tablicy kredowej: jak działa agent AI, z lektorem”.

## Czym różni się od podobnych
| Chcę… | Skill |
|---|---|
| ręka rysuje schemat i pisze pod lektora | **ten skill** |
| obraz malowany albo rysowany kreska po kresce i film, jak powstaje | `pracownia-malarza` |
| animowana scena w stylu epoki albo malarza | `style-malarskie` (Wideograf) |
| diorama z klocków 3D w znakach ASCII | `voxel-ascii` |
| explainer w gramatyce Kurzgesagt, Vox, 3Blue1Brown | `gramatyki-explainera` (Wideograf) |

## Kto robi
- **Jarvo sam:** filmik do ok. 30 s, jeden styl, bez poprawek po drodze.
- **Wideograf:** dłuższy film, rolka do publikacji, muzyka, kilka stylów, zawsze z `kontrola-wideo`.

## Style
`rysowany.py style [--json]` wypisuje 21 stylów, `rysowany.py wzor <id> [--czasy 2,6,12] [--arkusz plik.jpg]` pokazuje stopklatki wzoru.
Tabela: `references/style.md`; domyślny `paper`, np. `chalk` lekcje, `blueprint` systemy, `neon` AI, `notebook` finanse.

## Przebieg
```bash
N="@@REPO_DIR@@/profiles/jarvo-wideo/scripts"; F=out/wideo/src/<film>
@@PY@@ "$N/narzedzia.py" instaluj silnikjava                       # raz
@@PY@@ "$N/rysowany.py" nowy $F --styl chalk [--pion] [--tytul "Jak działa agent?"]   # index.html + scena.js
@@PY@@ "$N/film.py" narracja $F/narracja.txt -o $F/lektor.wav --os $F/os_czasu.json
@@PY@@ "$N/rysowany.py" glos $F $F/os_czasu.json                    # → glos/voice.json
#   krótki lektor: film.py lektor "…" -o $F/lektor.mp3; rysowany.py glos $F $F/lektor.slowa.json --lektor $F/lektor.mp3
@@PY@@ "$N/rysowany.py" sprawdz $F [--json]                         # kod 1 = do poprawy
@@PY@@ "$N/html_wideo.py" klatki $F/index.html --preset jarvo --czasy 1,3,5,8 --arkusz $F/klatki.jpg
@@PY@@ "$N/rysowany.py" film $F -o out/wideo/<film>.mp4 [--fps 30] [--arkusz $F/arkusz.jpg] [-- --muzyka podklad.wav]
```
1. Tekst lektora najpierw: jedno zdanie to jeden obraz, do ok. 15 słów, na tablicy tylko słowa-klucze.
2. `scena.js` eksportuje `zbuduj(glos)` zwracające Storyboard; zdanie to `sb.say(glos.beat(N), () => {…})` z kotwicą `cue: 'słowo'`.
3. API: `references/api-sceny.md`; zasady: `references/zasady-rysownika.md`; wzory: `@@TOOLS_DIR@@/silnikjava/examples/scenes/styles/<id>.js` i `…/reels/`.
4. Każdy błąd i uwagę `sprawdz` poprawiasz w scenie (słowa lektora, kotwica, podział rysunku), nigdy przyspieszeniem ręki (`dur`, `fast`).
5. `film` renderuje obraz, układa lektora pod oś silnika, tnie ujęcia na akapitach i `sb.clear()`, składa projekt `<film>.edycja.json` z karaoke.
6. Kontrola: `kontrola-wideo` z `qa_wideo.py --z-kodu --lektor`, a `sprawdz` zastępuje tu `html_wideo.py pomiar`.

## Pułapki
- Każdy ślad robi ręka, wyjątki tylko nazwane (`ambient`, `magic`).
- Obiekt kończysz przed następnym, a zaznaczenie to nowy obiekt.
- Ręka rysuje bez przerwy do 6 s, potem oddech najwyżej 3 s.
- Rolka `--pion`: rysunek w x 36 do 640, y 150 do 900 kadru 720×1280, tytuł ≥ 60, podpisy ≥ 36, najwyżej 4 obiekty.
- Napisy nie są wypalane, idą do projektu jako tekst.
- Krój `flipchart` nie ma polskich liter, więc sprawdź ą, ę, ł na arkuszu.

## Wynik
`out/wideo/<film>.mp4` z `<film>.edycja.json`, źródła w `out/wideo/src/<film>/`.
RAPORT.md: styl i dlaczego, wynik `sprawdz`, czas renderu, „Projekt do poprawek: HQ → Wideograf → Wyniki → <film> → Edytuj”, oznaczenie głosu syntetycznego.
