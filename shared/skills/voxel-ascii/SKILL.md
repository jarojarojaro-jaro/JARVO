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

**Co to jest:** animowana diorama z klocków 3D ze światłem, pokazana znakami ASCII z tilt-shiftem (MP4 1080×1920, 30 kl./s, bez dźwięku).
**Kiedy użyć:** klimatyczna rolka 9:16 albo kadr bez lektora: miejsce, nastrój, pora dnia.
**Przykład zlecenia:** „Zrób 20-sekundową rolkę ASCII: latarnia na klifie nocą”.

## Czym różni się od podobnych
| Chcę… | Skill |
|---|---|
| diorama 3D w znakach ASCII, bez lektora | **ten skill** |
| ręka rysuje schemat pod lektora (też styl `ascii`) | `film-rysowany` |
| obraz malowany i film, jak powstaje | `pracownia-malarza` |
| animowana scena w stylu malarza | `style-malarskie` (Wideograf) |
| scena 3D Three.js | `film-z-kodu` |

## Kto robi
- **Jarvo sam:** `podglad` i `arkusz` na tym komputerze.
- **Wideograf:** pełny film na InstaBox, tutaj tylko krótka próba i projekt edytora.

## Przebieg
```bash
N="@@REPO_DIR@@/profiles/jarvo-wideo/scripts"; V="@@TOOLS_DIR@@/silnikjava/.claude/skills/voxel-ascii"
@@PY@@ "$N/narzedzia.py" instaluj silnikjava                    # raz
@@PY@@ "$N/voxel.py" sceny                                      # lighthouse (noc), shrine (zmierzch)
nice -n 15 @@PY@@ "$N/voxel.py" podglad lighthouse [--wariant noc] [--t 8] [--out out/wideo/src/voxel]   # raw_*.png + ascii_*.png
nice -n 15 @@PY@@ "$N/voxel.py" arkusz lighthouse [--wariant noc] [--out …]                             # 6 klatek
nice -n 15 @@PY@@ "$N/voxel.py" film lighthouse -o out/wideo/proba.mp4 [--wariant noc] --sekundy 2 [--watki 2]
```
- Tutaj zawsze `nice -n 15` i najwyżej `--watki 2`, bo film 20 s to ok. 10 min na 4 rdzeniach.
- Wyniki w `out/wideo/src/voxel/<scena>[-wariant]/`, cache obok, a zmiana samego `look` nie liczy cieni od nowa (pierwszy raz ok. 3 min).

**Pełny film na InstaBox** (`--tlo`, bo render trwa ponad 600 s):
```bash
zapas-mocy uruchom --tlo --wyslij "$V:/data/home/voxel-ascii" [--wyslij moja_scena.py:/data/home/voxel-ascii/scenes/moja.py] \
  -- 'set -e; command -v ffmpeg >/dev/null; test -f /usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf;
      test -x /data/home/vx/bin/python || python3 -m venv /data/home/vx;
      /data/home/vx/bin/pip install -q numpy scipy==1.16.3 pillow;
      cd /data/home/voxel-ascii && /data/home/vx/bin/python run.py lighthouse --variant noc --video --jobs 4 --out /data/home/wynik/latarnia'
zapas-mocy zadanie <numer> --odbierz /data/home/wynik/latarnia/lighthouse-noc.mp4:out/wideo/src/voxel/latarnia.mp4
@@PY@@ "$N/voxel.py" film lighthouse --wariant noc --surowy out/wideo/src/voxel/latarnia.mp4 -o out/wideo/latarnia.mp4 [-- --muzyka m.wav]
```
- Brak ffmpeg albo kroju DejaVu na maszynie (`set -e` przerwie zadanie) zgłaszasz operatorowi floty.
- `zadanie` czeka do 10 min, więc gdy render trwa, wołasz je ponownie z tym samym numerem.
- Kilka filmów naraz idzie na różne maszyny (`ZAPAS_MOCY_MASZYNA=flota-02`).
- MP4 nazywa się `<scena>[-wariant].mp4`.

## Nowa scena
Kopiujesz `$V/scenes/lighthouse.py` albo `shrine.py` do `out/wideo/src/voxel/<nazwa>.py`, zmieniasz `build()` i `CONFIG`, potem `voxel.py podglad out/wideo/src/voxel/<nazwa>.py`.
Opis świata, opcji `look` i pułapek: `$V/SKILL.md`.

## Kolejność jakości
1. Najpierw `raw_*.png`, bo płaskiego renderu 3D ASCII nie uratuje.
2. Potem `ascii_*.png`.
3. `arkusz`: ruch snopu, wody i kamery, nic nie ucieka z kadru, rogi nie są czarne.
4. Film, projekt edytora, `kontrola-wideo` z `qa_wideo.py --z-kodu`.

## Pułapki
- Jakość robią cienie, okluzja i ciepłe światło z chłodnym cieniem, nie płaskie kolory.
- Ściana po skosie siatki to płot z kolców, więc stawiaj ściany wzdłuż osi x i y.
- Widać tylko ściany +x, +y i górę, więc detale stawiasz od frontu.
- Ważne obiekty nie mogą być ucięte ani zasłonięte, a puste rogi wypełniasz.
- Procesy renderu zatrzymujesz po PID, nigdy `pkill -f`.

## Wynik
`out/wideo/<film>.mp4` z `<film>.edycja.json` albo kadr `ascii_*.png`; RAPORT.md: scena, wariant, gdzie liczony render i jak długo.
