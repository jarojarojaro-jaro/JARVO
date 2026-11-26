---
name: pracownia-malarza
description: "Obraz malowany pędzlem albo kredką, pastelem, tuszem i film."
version: 1.0.0
author: "Jarvo (malarz: silnikjava, MIT)"
license: MIT
metadata:
  hermes:
    tags: [painting, drawing, brush, pastel, charcoal, watercolor, ink, timelapse, video, image]
    related_skills: [film-rysowany, voxel-ascii, film-z-kodu, kontrola-wideo]
  jarvo:
    autonomy: A1
    reviewed: "2026-11-26"
---

# Pracownia malarza (silnikjava)

**Co to jest:** obraz malowany kodem pociągnięcie po pociągnięciu (olej, kredki, pastele, węgiel, tusz, akwarela) i film, jak powstaje.
**Kiedy użyć:** trzeba obrazu „spod ręki” ze zdjęcia albo motywu, albo rolki timelapse jego powstawania.
**Przykład zlecenia:** „Namaluj to zdjęcie kota olejem i zrób z tego rolkę, jak powstaje”.

## Czym różni się od podobnych
| Chcę… | Skill |
|---|---|
| obraz malowany kreska po kresce i film, jak powstaje | **ten skill** |
| animowana scena w stylu malarza, nikt jej nie maluje | `style-malarskie` (Wideograf) |
| ręka rysuje schemat pod lektora | `film-rysowany` |
| diorama z klocków 3D w znakach ASCII | `voxel-ascii` |
| grafika z modelu AI | generowanie obrazów (Studio) |

## Kto robi
- **Jarvo sam:** obraz PNG i krótki film z pracowni bez muzyki.
- **Wideograf:** film do publikacji (muzyka, lektor, montaż, seria) z `kontrola-wideo`.

## Style (`--styl`)
- Pędzel: `olej` (domyślny), `impresja`, `etiuda` (najszybszy), `szpachla`, `punkty`, `kopia` (najdłuższy, kopiuje też szum).
- Papier: `kredki`, `pastele`, `olejne`, `mieszane`, `akwarela`, `wegiel`, `olowek`, `szkic`, `tusz`.
- Portret `olej` albo `kopia`, pejzaż `impresja`, `szpachla`, `akwarela`, rysunek `olowek`, `tusz`, `wegiel`.
- Ciemne i jaskrawe motywy tylko `pastele` albo `mieszane`, bo kredki i akwarela nie przyciemnią.

## Przebieg
```bash
N="@@REPO_DIR@@/profiles/jarvo-wideo/scripts"
@@PY@@ "$N/narzedzia.py" instaluj silnikjava                                     # raz
@@PY@@ "$N/narzedzia.py" uruchom silnikjava -- node {MALARZ}/maluj.mjs zdjecie.jpg --styl olej --out out/malarz/kot \
  [--skup 0.5,0.3,0.15,0.18,3] [--tytul "Kot"] [--autor "…"]
@@PY@@ "$N/narzedzia.py" uruchom silnikjava -- node {MALARZ}/maluj.mjs {MALARZ}/motywy/tatry.js --styl akwarela --out out/malarz/tatry
@@PY@@ "$N/narzedzia.py" uruchom silnikjava -- node {MALARZ}/przeglad.mjs zdjecie.jpg --style olej,akwarela,tusz --watki 2 --out out/malarz/przeglad
@@PY@@ "$N/narzedzia.py" uruchom silnikjava -- node {MALARZ}/odtworz.mjs out/malarz/kot/obraz.json --skala 3 --okno 0.3,0.25,0.3,0.3
@@PY@@ "$N/pracownia.py" klatki out/malarz/kot/obraz.json [--czasy 2,8,20,33] --arkusz out/malarz/kot/pracownia.jpg
@@PY@@ "$N/pracownia.py" film out/malarz/kot/obraz.json -o out/wideo/kot.mp4 [--czas 30] [--koniec 3.5] \
  [--uklad pion|poziom] [--dzwiek] [--arkusz qa.jpg] [-- --muzyka m.wav]
@@PY@@ "$N/narzedzia.py" uruchom silnikjava -- node {MALARZ}/strona.mjs out/malarz/kot/obraz.json [--sam]   # na żywo; --sam = szkicownik
```
1. Przy portrecie podaj twarz `--skup x,y,rx,ry,waga` w ułamkach kadru, bo zły wynik zwykle naprawia `--skup`, nie więcej pociągnięć.
2. Cudze dzieła tylko z domeny publicznej.
3. Motyw z kodu: `motywy/jezioro.js` (2:3), `lato.js`, `tatry.js` (16:9) albo własny `export const wzor = (W, H) => …` wzorem `jezioro.js`.
4. `maluj.mjs` daje w `--out`: `obraz.json`, `obraz.png`, `wzor.png`, `porownanie.png`, `etapy.png`.
5. Kolor oceniasz na środkowym panelu `porownanie.png` (bez światła), detal przez `odtworz.mjs`.
6. Najpierw `klatki` (nakładanie, tytuł), potem `film`, który składa projekt `<film>.edycja.json` (szelest `--dzwiek` jako efekty).
7. Kadr pion 1080×1920, a praca szersza niż 1,2:1 sama idzie w poziomie; czas to `--czas` + `--koniec` + 0,9 s.
8. Kontrola filmu: `kontrola-wideo` z `qa_wideo.py --z-kodu`.
9. Szkicownik (`--sam`) wysyłasz właścicielowi tylko na prośbę.

## Pułapki
- `kopia` trwa najdłużej, `olej` 2 do 3 min, `etiuda` ok. 1 min, a film to kilka minut renderu.
- RMSE to nie jakość, patrz na obraz.
- `film.mjs` autora u nas nie istnieje, film robi `pracownia.py`.
- Pełny opis malarza: `@@TOOLS_DIR@@/silnikjava/.claude/skills/malarz/SKILL.md`.

## Wynik
`out/malarz/<nazwa>/obraz.png` albo `out/wideo/<film>.mp4` z projektem edytora.
RAPORT.md: wzór (źródło, licencja), styl i dlaczego, czas, „Projekt do poprawek: HQ → Wideograf → Wyniki → <film> → Edytuj”.
