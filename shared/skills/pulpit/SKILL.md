---
name: pulpit
description: "Program z oknem na pulpicie serwera (GIMP, LibreOffice, Kdenlive, Inkscape, edytor HQ): narzędzie pulpit."
version: 1.0.0
author: "Jarvo"
license: MIT
metadata:
  hermes:
    tags: [desktop, gui, screen, computer-use, gimp, libreoffice, kdenlive, inkscape, click, screenshot]
  jarvo:
    autonomy: A1
    reviewed: "2026-11-27"
---

# Pulpit serwera

Narzędzie `pulpit` steruje ekranem `:0` serwera myszą i klawiaturą jak człowiek; właściciel ogląda go na żywo przez VNC.

## Kiedy pulpit
- Program ma API, skrypt albo wiersz poleceń (LibreOffice `soffice --headless`, GIMP batch, `melt`, `inkscape --export-type`, `projekt.py`): robisz to skryptem, a pulpit służy do obejrzenia i poprawek.
- Strona w internecie: narzędzie `komputer` (Jarvo) albo `browser_*`; pulpit odmawia działań w oknie Komputera Jarva.
- Polecenie powłoki: narzędzie `terminal`; pulpit nie działa w terminalach ani w oknie uruchamiania poleceń.
- Program z oknem, którego nie da się obsłużyć skryptem, i ocena, jak wynik wygląda: pulpit.

## Pętla
1. `uruchom` (program, pliki w `argumenty`) albo `aktywuj` (fragment tytułu okna).
2. `zobacz`: obraz 1280×720 z czerwonymi numerami elementów aktywnego okna i ich lista `[n] rola „napis” @x,y`.
3. Działanie na numer (`klik`, `pisz`, `przewin`, `przeciagnij`), a gdzie numeru nie ma (płótno, oś czasu, podgląd) na `xy` odczytane z obrazu.
4. Paragon po działaniu mówi, co się zmieniło (procent ekranu, nowe i zamknięte okna, aktywne okno, pole z fokusem i jego treść); „bez widocznej zmiany” znaczy: najpierw `zobacz`, potem decyzja.
5. Kilka pewnych kroków naraz (menu, pole, Enter, czekanie na okno) idzie jedną akcją `kroki`, z `zobacz_po: true` na końcu.

## Zasady
- Współrzędne zawsze z ostatniego obrazu `zobacz` (1280×720), także w `obszar`, który pokazuje fragment w pełnej rozdzielczości.
- Numery elementów są ważne do następnego `zobacz`; element, który zniknął, daje odmowę z prośbą o nowe `zobacz`.
- Na wolne okno czekasz akcją `czekaj` (tekst, okno, `zniknie`, spokojny ekran), a nie powtarzaniem kliknięć.
- Skróty klawiszowe programu (ctrl+s, ctrl+shift+e, alt+F4) są szybsze i pewniejsze niż szukanie w menu.
- Tekst po `pisz` sprawdzasz w paragonie (fokus pokazuje treść pola), zanim zatwierdzisz Enterem.
- Pliki zapisujesz w katalogu roboczym zadania agenta pełną ścieżką wpisaną w okno zapisu.
- Pulpit ma naraz jedno zadanie agenta; przy odmowie „pulpit zajęty” robisz inną część zadania i próbujesz po podanym czasie.
- Płatność i dane karty przechodzą tylko z linią ZGODA WŁAŚCICIELA: platnosc w zadaniu agenta.
- Na koniec zamykasz okna, które otworzyłeś (`zamknij` albo ctrl+q), i odpowiadasz na pytanie o zapis.
- Programy: gimp, calc, writer, impress, draw, libreoffice, mousepad, thunar, ristretto, parole, firefox, kdenlive, inkscape; Kdenlive i Inkscape pobierają się przy pierwszym `uruchom` (minuta albo dwie).
- Skille programów: `gimp`, `libreoffice`, `kdenlive`, `edytor-hq`.
