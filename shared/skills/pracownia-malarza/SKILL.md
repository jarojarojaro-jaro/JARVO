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

**Co to jest:** obraz MALOWANY kodem tak, jak robi to ręka: tysiące pociągnięć pędzla (olej, impresja, szpachla,
puentylizm) albo kreski i plamy na papierze z ziarnem (kredki, pastele, węgiel, ołówek, tusz, akwarela), ze zdjęcia
albo z motywu opisanego w kodzie, plus film z pracowni, na którym obraz powstaje pociągnięcie po pociągnięciu.
**Kiedy użyć:** trzeba obrazu albo rysunku „jak spod ręki” (grafika, okładka, prezent, pejzaż, portret ze zdjęcia)
albo filmu, w którym widz patrzy, jak dzieło powstaje (rolka timelapse, intro, tło pod lektora).
**Przykład zlecenia:** „Namaluj to zdjęcie kota olejem i zrób z tego rolkę, jak powstaje” albo „rysunek Tatr
akwarelą na okładkę”.

Malarz to część silnikjava właściciela (MIT, `narzedzia.py instaluj silnikjava`), czysty JS bez zależności. Wynik
to lista pociągnięć (12 bajtów każde): obraz odtworzysz w dowolnej skali i zatrzymasz w dowolnej chwili.

## Czym różni się od podobnych
| Chcę… | Skill |
|---|---|
| obraz malowany albo rysowany kreska po kresce i film, jak powstaje | **ten skill** |
| animowana scena w stylu epoki albo malarza (Van Gogh, Klimt, Egipt), obraz się porusza, nikt go nie maluje | `style-malarskie` (Wideograf) |
| ręka rysuje schemat i pisze pod lektora, film objaśniający | `film-rysowany` |
| diorama z klocków 3D w znakach ASCII | `voxel-ascii` |
| grafika z modelu AI (zdjęciowa, fantazyjna) | generowanie obrazów (Studio) |

## Kto robi
- **Jarvo sam:** pojedynczy obraz albo rysunek (PNG) i krótki film z pracowni bez muzyki.
- **Wideograf:** film z pracowni do publikacji (muzyka, lektor, montaż z innymi ujęciami, seria), `kontrola-wideo`.

## Style
Pędzel olejny (`lib/malarz.js`): `olej` (domyślny, 15 tys. pociągnięć, alla prima), `impresja` (krótkie grube
dotknięcia, żywy kolor), `etiuda` (1,2 tys., sam układ plam, najszybszy), `szpachla` (farba kładziona nożem, gruba
faktura), `punkty` (puentylizm), `kopia` (62 tys., wierna kopia do najdrobniejszego detalu, najdłużej).
Papier (`lib/rysownik.js`): `kredki` (szraf warstwami, trzyma kolor), `pastele` (suche na tonowanym papierze, żywe,
pejzaże), `olejne` (pastele olejne, gęsty przesadzony kolor), `mieszane` (pastel, kredki, węgiel i biała kreda:
najczystszy kolor i rysunek), `akwarela` (lawowania, laserunki, biel to papier), `wegiel` (węgiel i biała kreda,
sam walor), `olowek` (szraf krzyżowy), `szkic` (szybki kontur i lekki szraf), `tusz` (piórko, szraf w trzech
kierunkach).
Dobór: portret i klasyka `olej` albo `kopia`; pejzaż i kwiaty `impresja`, `szpachla`, `akwarela`; plakatowo
`etiuda`; barwny motyw „jak z ręki” `mieszane`, `pastele`, `kredki`; rysunek `olowek`, `szkic`, `tusz`, `wegiel`.
Ciemne i jaskrawe motywy: `pastele` albo `mieszane` (kredki i akwarela nie przyciemnią do końca).

## Przebieg (polecenia)
```bash
N="@@REPO_DIR@@/profiles/jarvo-wideo/scripts"
@@PY@@ "$N/narzedzia.py" instaluj silnikjava                                     # raz
@@PY@@ "$N/narzedzia.py" uruchom silnikjava -- node {MALARZ}/maluj.mjs zdjecie.jpg --styl olej --out out/malarz/kot \
  [--skup 0.5,0.3,0.15,0.18,3] [--tytul "Kot"]
@@PY@@ "$N/narzedzia.py" uruchom silnikjava -- node {MALARZ}/maluj.mjs {MALARZ}/motywy/tatry.js --styl akwarela \
  --out out/malarz/tatry                                                            # motyw z kodu
@@PY@@ "$N/narzedzia.py" uruchom silnikjava -- node {MALARZ}/przeglad.mjs zdjecie.jpg --style olej,akwarela,tusz,kredki \
  --watki 2 --out out/malarz/przeglad                                               # arkusz stylów
@@PY@@ "$N/narzedzia.py" uruchom silnikjava -- node {MALARZ}/odtworz.mjs out/malarz/kot/obraz.json --skala 3 \
  --okno 0.3,0.25,0.3,0.3                                                           # detal z bliska
@@PY@@ "$N/pracownia.py" klatki out/malarz/kot/obraz.json --arkusz out/malarz/kot/pracownia.jpg   # 6 klatek filmu
@@PY@@ "$N/pracownia.py" film out/malarz/kot/obraz.json -o out/wideo/kot.mp4 --dzwiek [--czas 30] [-- --muzyka m.wav]
@@PY@@ "$N/narzedzia.py" uruchom silnikjava -- node {MALARZ}/strona.mjs out/malarz/kot/obraz.json   # maluje na żywo
```
1. **Wzór:** obejrzyj zdjęcie (gdzie jest punkt uwagi: twarz, oczy, słońce). Malarz sam szuka tematu i wypisuje
   elipsę; przy portrecie podaj twarz `--skup x,y,rx,ry,waga` (ułamki kadru). Cudze dzieła tylko z domeny publicznej.
2. **Motyw z kodu** (bez pliku graficznego): `motywy/jezioro.js` (pion 2:3), `lato.js` i `tatry.js` (panoramy 16:9)
   albo własny plik z `export const wzor = (W, H) => namaluj(W, H, kolor)` (`lib/szkic.js`: `pasmo`, `fbm`, `gladko`,
   `miesz`); buduj od tyłu do przodu, kontrast ciepłe i zimne, jeden jasny punkt uwagi. Wzorzec: `motywy/jezioro.js`.
3. **Maluj** i obejrzyj `porownanie.png` (wzór, czysty kolor, ze światłem) oraz detal z `odtworz.mjs`: z daleka
   obraz, z bliska pociągnięcia. Zły wynik zwykle naprawia `--skup`, nie więcej pociągnięć.
4. **Film z pracowni** (`pracownia.py`): kadr pion 1080×1920, praca szersza niż 1,2:1 sama w poziomie 1920×1080
   (`--uklad` wymusza); widać pędzel albo ołówek w ręce, lupę ×4, paletę albo piórnik, listę pędzli i licznik.
   Najpierw `klatki` (czy nic się nie nakłada, czy tytuł się mieści), potem `film`: render przez html_wideo.py
   i projekt edytora `<film>.edycja.json` (obraz, szelest narzędzia `--dzwiek` jako efekty, muzyka po `--`).
5. **Kontrola** filmu (Wideograf): `kontrola-wideo` z `qa_wideo.py --z-kodu`.

Pliki `maluj.mjs` w `--out`: `obraz.json` (pociągnięcia), `obraz.png` (skala 2, ze światłem na fakturze), `wzor.png`,
`porownanie.png`, `etapy.png` (stan po każdym pędzlu). Tytuł i autor na planszy filmu: `--tytul`, `--autor` przy
malowaniu. Czas na serwerze (`nice`): `etiuda` ok. 1 min, `olej` 2 do 3 min, `kopia` najdłużej; film z pracowni
34 s to kilka minut renderu (na InstaBox szybciej, `voxel-ascii` opisuje `zapas-mocy`).

## Ręka bez wzoru i szkicownik
- Z ręki (pociągnięcia albo kreski wprost w kodzie: `lib/reka.js`, `lib/rysunek.js`): akcenty i proste układy; opis
  i przykłady w `@@TOOLS_DIR@@/silnikjava/.claude/skills/malarz/SKILL.md` (rozdziały „Rysowanie z ręki”).
- **Szkicownik** (`strona.mjs --sam`): strona, na której człowiek maluje sam tymi samymi narzędziami (nacisk z rysika,
  kalka ze zdjęcia, cofanie, zapis w tym samym formacie, więc `pracownia.py film` zrobi z jego rysunku film). Panel
  dla właściciela to osobny krok: dziś tylko możliwość, nie wysyłaj mu go bez prośby.

## Pułapki
- Światło na fakturze łatwo przesadzić; ocena koloru zawsze bez światła (`porownanie.png`, środkowy panel).
- Zdjęcie z szumem i kurzem: style poza `kopia` same je wygładzają, `kopia` je skopiuje.
- RMSE to nie jakość: patrz na obraz, nie na liczbę.
- Kredki i akwarela na białym papierze: ciemne tło wychodzi jaśniej (pigment przezroczysty); wtedy `pastele`.
- Dźwięk filmu to syntetyczny szelest narzędzia w rytm ruchu ręki (bez muzyki i lektora); muzykę dokładasz w projekcie.
- Pełny opis silnika malarza, procedura autora i lista pułapek z prób: `@@TOOLS_DIR@@/silnikjava/.claude/skills/malarz/SKILL.md`
  (jego `film.mjs` u nas nie istnieje: film robi `pracownia.py`).

## Wynik
`out/malarz/<nazwa>/obraz.png` (obraz) albo `out/wideo/<film>.mp4` z projektem edytora i `pracownia.mp4` obok
obrazu; w RAPORT.md: wzór (źródło, licencja), styl i dlaczego, czas malowania, „Projekt do poprawek: HQ → Wideograf
→ Wyniki → <film> → Edytuj”.
