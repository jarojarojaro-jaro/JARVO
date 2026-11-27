---
name: edytor-hq
description: "Edytor filmów HQ w przeglądarce: otwarcie projektu, podgląd, teksty i kolory planszy (Edytuj ujęcie), eksport."
version: 1.0.0
author: "Jarvo"
license: MIT
metadata:
  hermes:
    tags: [video, editor, hq, preview, captions, brand, desktop, browser]
  jarvo:
    autonomy: A1
    reviewed: "2026-11-27"
---

# Edytor filmów HQ

Edytor HQ to strona panelu Jarva; film i jego projekt `<film>.edycja.json` leżą obok siebie, a każda zmiana w edytorze to zmiana projektu.

## Kiedy edytor, kiedy polecenie
- Wideograf zmienia projekt poleceniami `projekt.py` (cięcie, napisy, audio, `popraw-ujecie` dla plansz z kodu), a edytor otwiera do podglądu i oceny wyniku.
- Teksty i kolory planszy filmu z kodu zmienia okno **Edytuj ujęcie** w edytorze albo `projekt.py popraw-ujecie`; oba zapisują `parametry.json` ujęcia.
- Edytor jest drogą dla zadań, które wprost każą coś zrobić w edytorze, i dla agenta bez `projekt.py` (Jarvo).

## Otwarcie
- Adres: `http://127.0.0.1:9119/jarvo#/?n=edytor&p=<pełna ścieżka filmu albo projektu, zakodowana jak w URL>`; na tym komputerze bez logowania.
- Jarvo otwiera go w Komputerze (`komputer` akcja `idz` z tym adresem), a agent z pulpitem w przeglądarce na pulpicie (`pulpit` akcja `uruchom`, `program: firefox`, `argumenty: [adres]`).
- Ścieżkę kodujesz `python3 -c 'import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=""))' "<ścieżka>"`.

## Praca
- Oś czasu i podgląd to płótno: klikasz `xy` z obrazu, `obszar` powiększa oś, a przyciski, pola i suwaki mają numery.
- Plansza z kodu: zaznacz klip na osi, **Edytuj ujęcie**, popraw pola tekstu i koloru (kolory marki z brand kitu, zapis `#RRGGBB`), zapisz; edytor sam przelicza ujęcie, a postęp widać na klipie.
- Skróty edytora: spacja odtwarza, S tnie pod głowicą, ctrl+z cofa, ctrl+shift+z ponawia.
- Przed oddaniem obejrzyj podgląd w kilku miejscach osi (`zobacz` po przesunięciu głowicy) i porównaj z zadaniem.
- **Eksportuj** zapisuje nową wersję obok oryginału (`film-edycja.mp4`), oryginał zostaje.
- Okno przeglądarki, które otworzyłeś na pulpicie, zamykasz na koniec (`zamknij`).
