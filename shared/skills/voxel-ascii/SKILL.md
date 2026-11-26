---
name: voxel-ascii
description: "Diorama z klocków 3D w znakach ASCII: rolka i kadry."
version: 1.0.0
author: "Jarvo (pipeline: silnikjava voxel-ascii, MIT)"
license: MIT
metadata:
  hermes:
    tags: [voxel, ascii, isometric, diorama, 3d, reel, vertical, procedural, python]
    related_skills: [film-rysowany, pracownia-malarza, film-z-kodu, kontrola-wideo]
  jarvo:
    autonomy: A1
    reviewed: "2026-11-26"
---

# Voxel ASCII (silnikjava)

**Co to jest:** izometryczna diorama zbudowana z klocków 3D (jak świat z gry z klocków) z prawdziwym światłem
(cienie słońca, okluzja w rogach, ciepłe lampy), animacją (woda z falami i odbłyskami, migające światła, snop
latarni, śnieg, liście, ptaki, najazd kamery) i filtrem, który zamienia każdą klatkę w znaki ASCII z tilt-shiftem.
**Kiedy użyć:** klimatyczna rolka 9:16 albo kadr „ASCII art z gry”: miejsce, nastrój, pora dnia, tło pod cytat
albo muzykę; film bez lektora i bez objaśniania.
**Przykład zlecenia:** „Zrób 20-sekundową rolkę ASCII: latarnia na klifie nocą” albo „kadr ASCII zimowej świątyni
na tapetę”.

Pipeline w Pythonie (numpy, scipy, Pillow, ffmpeg) z silnikjava właściciela (MIT, `narzedzia.py instaluj
silnikjava`: scipy przypięte w venvie narzędzi); nie używa silnika rysowanego ani jego zasad rysownika. Wynik: MP4
1080×1920, 30 kl./s, bez dźwięku, i podglądy PNG. Gotowe sceny: `lighthouse` (latarnia na klifie o zachodzie,
wariant `noc`), `shrine` (zimowa świątynia z torii, wariant `zmierzch`).

## Czym różni się od podobnych
| Chcę… | Skill |
|---|---|
| diorama z klocków 3D w znakach ASCII, nastrój bez lektora | **ten skill** |
| ręka rysuje schemat i pisze pod lektora (styl `ascii` też tam jest, ale to rysunek, nie świat 3D) | `film-rysowany` |
| obraz malowany pędzlem albo kredką i film, jak powstaje | `pracownia-malarza` |
| animowana scena w stylu malarza (w tym piksel 8-bit) | `style-malarskie` (Wideograf) |
| scena 3D z kamerą i shaderami (Three.js) | `film-z-kodu` (rodzaj „Scena 3D”) |

## Kto robi
- **Jarvo sam:** kadr albo arkusz (`podglad`, `arkusz`) na tym komputerze.
- **Wideograf:** pełny film (rolka), zawsze z renderem na InstaBox albo krótką próbą tutaj, potem projekt edytora.

## Dwie drogi renderu
Render jest ciężki: świat i render 3D (cienie, okluzja) za pierwszym razem ok. 3 min na serwerze (jeden rdzeń,
potem z cache), klatka ok. 1 s na rdzeń, czyli film 20 s ok. 10 min na 4 rdzeniach. Serwer ma limit CPU 80%.
- **Na tym komputerze:** `voxel.py` zawsze z `nice -n 15`, najwyżej 2 procesy klatek (`--watki`, domyślnie 2),
  BLAS po jednym wątku. Tutaj: `podglad`, `arkusz` i krótkie próby filmu (`--sekundy 2`).
- **Na InstaBox (pełne filmy):** maszyna 4 vCPU z `zapas-mocy` (arsenał floty): wysyłasz katalog pipeline'u
  i swoją scenę, render idzie w tle, wracasz po MP4, a projekt edytora składasz tutaj (`voxel.py film … --surowy`).
  Zmierzone 26.11 na flota-01: render 3D 95 s, 60 klatek (2 s filmu) ok. 30 s przy `--jobs 4`.

## Przebieg (polecenia)
```bash
N="@@REPO_DIR@@/profiles/jarvo-wideo/scripts"; V="@@TOOLS_DIR@@/silnikjava/.claude/skills/voxel-ascii"
@@PY@@ "$N/narzedzia.py" instaluj silnikjava                    # raz (pipeline, scipy, krój DejaVu Sans Mono)
@@PY@@ "$N/voxel.py" sceny                                      # gotowe sceny i warianty
@@PY@@ "$N/voxel.py" podglad lighthouse --wariant noc --t 8     # raw_008.0.png (3D) + ascii_008.0.png
@@PY@@ "$N/voxel.py" arkusz lighthouse --wariant noc            # 6 klatek z całego filmu (czy wszystko się rusza)
@@PY@@ "$N/voxel.py" film lighthouse --wariant noc --sekundy 2 -o out/wideo/proba.mp4   # krótka próba tutaj
```
Wyniki w `out/wideo/src/voxel/<scena>[-wariant]/` (`--out` zmienia), cache świata i renderu 3D obok
(`<scena>-cache/`): zmiana samego wyglądu (`look`: ASCII, efekty, kamera, kolory) nie liczy cieni od nowa.

**Pełny film na InstaBox** (z katalogu roboczego; `--tlo`, bo render trwa dłużej niż 600 s jednego polecenia):
```bash
zapas-mocy uruchom --tlo --wyslij "$V:/data/home/voxel-ascii" [--wyslij moja_scena.py:/data/home/voxel-ascii/scenes/moja.py] \
  -- 'set -e; command -v ffmpeg >/dev/null || sudo apt-get install -y -qq ffmpeg;
      test -f /usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf || sudo apt-get install -y -qq fonts-dejavu-core;
      test -x /data/home/vx/bin/python || python3 -m venv /data/home/vx;
      /data/home/vx/bin/pip install -q numpy scipy==1.16.3 pillow;
      cd /data/home/voxel-ascii && /data/home/vx/bin/python run.py lighthouse --variant noc --video --jobs 4 --out /data/home/wynik/latarnia'
zapas-mocy zadanie <numer> --odbierz /data/home/wynik/latarnia/lighthouse-noc.mp4:out/wideo/src/voxel/latarnia.mp4
@@PY@@ "$N/voxel.py" film lighthouse --wariant noc --surowy out/wideo/src/voxel/latarnia.mp4 -o out/wideo/latarnia.mp4
```
`zadanie` czeka do 10 min na raz: gdy render jeszcze trwa, wołasz je ponownie z tym samym numerem. Kilka filmów
naraz: każdy na innej maszynie (`ZAPAS_MOCY_MASZYNA=flota-02`). Plik MP4 nazywa się `<scena>[-wariant].mp4`.

## Nowa scena
Kopiujesz `$V/scenes/shrine.py` albo `lighthouse.py` do `out/wideo/src/voxel/<nazwa>.py` i zmieniasz `build()`
(świat 256×256×96: teren `w.H`, materiały, woda, obiekty `w.lamp_post`, `w.torii`, `w.forest`, `w.tree_pine`,
`w.boat`, `w.fox`, `w.path`, światła i nazwane punkty `w.marks`) oraz `CONFIG` (kamera, światło, `look`: efekty
`beam`, `birds`, `leaves`, `snow`, długość, najazd, ekspozycja, ASCII, tilt-shift). Potem `voxel.py podglad
out/wideo/src/voxel/<nazwa>.py`. Pełny opis układu świata, wszystkich opcji `look` i pułapek:
`@@TOOLS_DIR@@/silnikjava/.claude/skills/voxel-ascii/SKILL.md`.

## Procedura jakości (zawsze w tej kolejności)
1. `podglad` i **najpierw `raw_*.png`** (3D bez ASCII): jeśli surowy render jest płaski, ASCII go nie uratuje.
2. Poprawiasz świat i światło, aż raw wygląda jak ładna gra z klocków; potem `ascii_*.png`.
3. `arkusz`: czy snop, woda i kamera się ruszają, czy nic nie ucieka z kadru, czy rogi nie są czarne.
4. Film (InstaBox albo krótka próba), `voxel.py film` składa projekt edytora (muzyka po `--`: `-- --muzyka m.wav`),
   potem `kontrola-wideo` z `qa_wideo.py --z-kodu`.

## Pułapki
- Płaskie kolory bez światła wyglądają tanio: jakość robią cienie, okluzja, tekstury i ciepłe światło z chłodnym cieniem.
- Ściana po skosie siatki to płot z kolców: zbocze tarasami albo ściany wzdłuż osi x i y.
- Widać tylko ściany +x, +y i górę: drzwi, okna i detale stawiasz od frontu.
- Ważne obiekty nie mogą być ucięte krawędzią ani zasłonięte; puste rogi wypełniasz (skały, łódka, drzewa).
- Procesy renderu zatrzymujesz po numerze procesu, nie `pkill -f` (zabija też własną powłokę).
- Film jest bez dźwięku: muzyka albo efekty dochodzą w projekcie edytora.

## Wynik
`out/wideo/<film>.mp4` z projektem `<film>.edycja.json` (Wideograf) albo kadr `ascii_*.png` (Jarvo); w RAPORT.md:
scena i wariant, gdzie liczony render (InstaBox albo tutaj) i jak długo.
