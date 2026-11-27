---
name: gimp
description: "Obraz w GIMP: miniatura, napis, skalowanie, eksport PNG/JPG; najpierw Python-Fu bez okna, okno na pulpicie do poprawek."
version: 1.0.0
author: "Jarvo (program: GIMP 3, GPL-3.0)"
license: MIT
metadata:
  hermes:
    tags: [image, gimp, thumbnail, python-fu, script-fu, export, desktop]
  jarvo:
    autonomy: A1
    reviewed: "2026-11-27"
---

# GIMP

GIMP 3 jest w systemie (`gimp`, bez okna `gimp-console`); skrypt Python-Fu robi to samo co okno, szybciej i powtarzalnie.

## Najpierw skrypt (bez okna)
```bash
cat > miniatura.py <<'EOF'
from gi.repository import Gimp, Gio, Gegl
img = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path("/pełna/ścieżka/klatka.png"))
img.scale(1280, 720)
napis = Gimp.TextLayer.new(img, "Tytuł filmu", Gimp.Font.get_by_name("Sans-serif Bold"), 96, Gimp.Unit.pixel())
img.insert_layer(napis, None, 0)
napis.set_offsets(60, 560)
napis.set_color(Gegl.Color.new("white"))
img.flatten()
Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, img, Gio.File.new_for_path("/pełna/ścieżka/miniatura.png"), None)
img.delete()
EOF
gimp-console -i -n --batch-interpreter=python-fu-eval -b "exec(open('miniatura.py').read())" --quit
```
- Klatkę z filmu daje `ffmpeg -ss <sekunda> -i film.mp4 -frames:v 1 klatka.png`.
- Format pliku wynika z rozszerzenia w `Gimp.file_save` (png, jpg, webp, xcf).
- Kolor marki podajesz jako `Gegl.Color.new("#RRGGBB")`, krój nazwą z `fc-list`.
- Skrypt trwa ok. 12 s (start GIMP-a); wynik oglądasz w odpowiedzi narzędzia albo `pulpit` akcją `uruchom` z `program: ristretto`.

## Okno GIMP (pulpit)
- `pulpit` akcja `uruchom` z `program: gimp` i `argumenty: [pełna ścieżka obrazu]`; pierwsze okno pojawia się po ok. 10 s.
- Menu, okna dialogowe i pola mają numery w `zobacz`; płótno ich nie ma, więc tam klikasz `xy` z obrazu.
- Skróty: T tekst, M przesuwanie, ctrl+shift+e eksport jako, ctrl+z cofnij, ctrl+q wyjście.
- Eksport (ctrl+shift+e): nazwa z pełną ścieżką w polu nazwy, Enter, potem Eksportuj w oknie opcji formatu.
- Przy wyjściu bez zapisu wybierasz „Odrzuć zmiany” (Discard Changes).
