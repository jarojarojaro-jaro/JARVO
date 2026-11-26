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

**Co to jest:** film objaśniający, w którym jedna ręka na oczach widza rysuje schematy, strzałki i obiekty, koloruje
je i pisze odręcznie litera po literze, a lektor mówi w tym samym tempie (rysunek trafia w słowa).
**Kiedy użyć:** trzeba coś wyjaśnić krok po kroku (jak działa usługa, proces, zjawisko, liczby), a film ma wyglądać
jak rysowany na tablicy, w zeszycie albo na kartce, nie jak motion design.
**Przykład zlecenia:** „Zrób 40-sekundowy film na tablicy kredowej: jak działa agent AI, z lektorem” albo „rolka 9:16
w zeszycie w kratkę: zasada 50/30/20”.

Silnik to silnikjava właściciela (MIT, `narzedzia.py instaluj silnikjava`): ręka z fizyką (ludzkie tempo, przeloty,
podnoszenie narzędzia), pismo prawdziwymi kreskami liter z polskimi znakami, 21 stylów zmienianych jedną linijką,
kamera (najazd, zjazd), ścieranie tablicy gąbką, rolki 9:16 ze strefą bezpieczną, bryły 3D w izometrii, styl ASCII.
Strona filmu, render (html_wideo.py), lektor (`lektor-i-dzwiek`) i projekt edytora są nasze.

## Czym różni się od podobnych
| Chcę… | Skill |
|---|---|
| ręka rysuje schemat i pisze pod lektora (whiteboard, zeszyt, tablica) | **ten skill** |
| obraz malowany pędzlem albo rysowany kredką, pastelem, węglem, tuszem, akwarelą, kreska po kresce, i film z pracowni | `pracownia-malarza` |
| animowana scena w stylu epoki albo malarza (Van Gogh, Egipt, Hopper), obraz żyje, nikt go nie maluje | `style-malarskie` (Wideograf) |
| diorama z klocków 3D pokazana znakami ASCII (rolka klimatyczna) | `voxel-ascii` |
| fragment explainera w gramatyce Kurzgesagt, Vox, 3Blue1Brown, wykresy | `gramatyki-explainera` (Wideograf) |

## Kto robi
- **Jarvo sam:** krótki filmik do ok. 30 s, jeden styl, zwykły lektor, bez poprawek właściciela po drodze.
- **Wideograf:** dłuższy film, rolka do publikacji, kilka stylów albo ujęć, muzyka, film marki, wszystko z oceną
  `kontrola-wideo`. Jarvo zleca to kartą z tematem, długością, stylem i formatem.

## Style (21 + papier)
`rysowany.py style` wypisuje wszystkie z opisem; obraz filmu-wzoru stylu: `rysowany.py wzor <id>` (arkusz stopklatek).
Pełna tabela z kreską, kolorowaniem, krojem i narzędziem w ręce: `references/style.md`. Skrót: `chalk` lekcje,
`blueprint` architektura systemów, `neon` technologia i AI, `notebook` finanse i nauka, `watercolor` przyroda,
`comic` ciekawostki i social, `flipchart` warsztaty i sprzedaż, `kraft` przepisy i rękodzieło, `sketch` fizyka
i technika, `parchment` historia i mapy, `woodcut` dawne rzemiosło, `cosmos` astronomia, `terminal` historia
komputerów, `poster` historia XX wieku, `corkboard` śledztwa i przyczyny, `sumi` przyroda i spokój, `patent`
wynalazki, `pixel` gry, `charcoal` dramatyczne tematy, `iso` sprzęt i sieci w 3D, `ascii` kultura cyfrowa, `paper`
(domyślny) pióro na kremowym papierze.

## Przebieg (polecenia)
```bash
N="@@REPO_DIR@@/profiles/jarvo-wideo/scripts"; F=out/wideo/src/<film>
@@PY@@ "$N/narzedzia.py" instaluj silnikjava                       # raz (silnik, kroje stylów)
@@PY@@ "$N/rysowany.py" nowy $F --styl chalk [--pion] --tytul "Jak działa agent?"   # index.html + scena.js
@@PY@@ "$N/film.py" narracja $F/narracja.txt -o $F/lektor.wav --os $F/os_czasu.json  # lektor (lektor-i-dzwiek)
@@PY@@ "$N/rysowany.py" glos $F $F/os_czasu.json                    # czasy słów → glos/voice.json silnika
#   piszesz scena.js: sb.say(glos.beat(N), () => { … cue: 'słowo' … }) według references/zasady-rysownika.md
@@PY@@ "$N/rysowany.py" sprawdz $F                                  # lint i audyt silnika: 0 błędów, 0 uwag
@@PY@@ "$N/html_wideo.py" klatki $F/index.html --preset jarvo --czasy 1,3,5,8 --arkusz $F/klatki.jpg   # obejrzyj
@@PY@@ "$N/rysowany.py" film $F -o out/wideo/<film>.mp4 --arkusz $F/arkusz.jpg [-- --muzyka podklad.wav]
```
1. **Tekst lektora najpierw** (`scenariusz`, `lektor-i-dzwiek`): jedno zdanie = jeden obraz, do ok. 15 słów, na
   tablicy tylko słowa-klucze; krótki tekst bez akapitów: `film.py lektor "…" -o $F/lektor.mp3`, potem
   `rysowany.py glos $F $F/lektor.slowa.json --lektor $F/lektor.mp3`.
2. **Scena** (`scena.js`, `export function zbuduj(glos)` zwraca Storyboard): obiekt w całości, potem następny
   (kontur, kolor, detale, podpis); kotwica `cue` na pierwszym kroku obiektu; kolory tylko z palety. API kroków,
   ścieżek i opcji: `references/api-sceny.md`; gotowe sceny 21 stylów do podpatrzenia:
   `@@TOOLS_DIR@@/silnikjava/examples/scenes/styles/<id>.js`, rolki `…/examples/scenes/reels/`.
3. **Sprawdzenie** `rysowany.py sprawdz`: błąd lintu, skok ręki albo klatka ponad budżet = poprawka w scenie.
   Uwagi (cisza po zdaniu, spóźniona kotwica, przestój, poza strefą rolki) też poprawiasz: dopisz lektorowi słowa,
   przesuń kotwicę, przenieś część rysunku do następnego zdania; nie przyspieszaj ręki (`dur`, `fast`).
4. **Film** `rysowany.py film`: render przez html_wideo.py (obraz bez napisów i dźwięku), lektor złożony pod oś
   silnika (silnik przesuwa zdanie najwyżej o 1,5 s, gdy ręka nie zdąży), cięcia ujęć na akapitach i ścieraniu
   tablicy, potem `projekt.py z-kodu … --karaoke --render`: film = render projektu edytora `<film>.edycja.json`
   (właściciel otworzy go w HQ i poprawi). Muzykę i inne opcje projektu podajesz po `--`.
5. **Kontrola** (Wideograf zawsze, Jarvo przy filmie dla klienta): `kontrola-wideo` z `qa_wideo.py --z-kodu --lektor`;
   pomiar HTML (`html_wideo.py pomiar`) dla tego silnika zastępuje `rysowany.py sprawdz`.

## Zasady, które łamią się najczęściej
- Nic nie pojawia się samo: każdy ślad robi ręka; wyjątek tylko nazwany (`ambient`, `magic`).
- Obiekt rysujesz do końca, zanim zaczniesz następny; zaznaczenie (kółko, zakreślenie) to nowy obiekt.
- Coś dzieje się cały czas: do 6 s ręka rysuje bez przerwy, później oddech najwyżej 3 s.
- Rolka 9:16: rysunek w strefie x 36 do 640, y 150 do 900 kadru 720×1280, tytuł ≥ 60, podpisy ≥ 36, najwyżej 3 do 4
  obiekty w kadrze, układ z góry na dół. Napisy lektora nie są wypalane: idą do projektu jako tekst.
- Na tablicy słowa-klucze, pełne zdania mówi lektor i pokazują napisy.

## Pliki
- `references/zasady-rysownika.md`: zasady rysownika autora silnika (fizyka ręki, kolejność, lektor, wygląd, rolka,
  izometria) i nasza procedura.
- `references/api-sceny.md`: kroki Storyboard, ścieżki, opcje czasu, paleta, lektor w scenie, kamera, ścieranie.
- `references/style.md`: 21 stylów: podłoże, kreska, kolorowanie, krój, narzędzie w ręce, do czego.
- Więcej u autora: `@@TOOLS_DIR@@/silnikjava/README.md` (API), `docs/STYLE.md` (własny styl), `docs/PRODUKCJA.md`
  (od skryptu do filmu), `docs/SKALOWANIE.md` (seria filmów).

## Wynik
`out/wideo/<film>.mp4` z projektem `<film>.edycja.json` i ścieżkami obok, źródła (`index.html`, `scena.js`,
`glos/`, `sprawdzenie.json`) w `out/wideo/src/<film>/`; w RAPORT.md: styl i dlaczego, wynik `sprawdz`, czas renderu,
zdanie „Projekt do poprawek: HQ → Wideograf → Wyniki → <film> → Edytuj” i oznaczenie głosu syntetycznego.
