# Pulpit serwera dla agentów

Narzędzie `pulpit` daje agentom z `pulpit: true` we [`fleet.yaml`](../fleet.yaml) (Jarvo, Studio, Wideograf) ekran X11
serwera (`:0`, Xfce): uruchamiają program z oknem, widzą ekran, klikają, piszą, przeciągają i sprawdzają wynik.
Właściciel ogląda ten sam ekran na żywo w HQ (okno „Na żywo”, ikona monitora: zrzut 3 razy na sekundę tylko po zmianie
obrazu i tylko, gdy ktoś patrzy, [HQ.md](HQ.md#podgląd-na-żywo-telefony-komputer-i-pulpit)) albo przez VNC. Strony robi
dalej Komputer Jarva ([KOMPUTER.md](KOMPUTER.md)), polecenia narzędzie `terminal`; pulpit jest do programów z oknami
i do oceny, jak wynik wygląda.

## Kto ma pulpit i dlaczego

| Agent | Po co |
|---|---|
| `jarvo` | edytor HQ (zadania z planszami i kolorami marki), LibreOffice (tabele, eksport XLSX i PDF), GIMP; sam robi pracę na ekranie |
| `jarvo-wideo` | Kdenlive i edytor HQ: podgląd i poprawki montażu, formaty, których `projekt.py` nie ma |
| `jarvo-studio` | GIMP i Inkscape: miniatury, grafiki, poprawki obrazu, którego nie da się zrobić skryptem |

Pozostali agenci pracują kodem, przeglądarką albo API (Sherlock, Web, Ads, Łowca, Twórca aplikacji, Bigshort,
Hacker); gdy potrzebują programu z oknem, zlecają to Jarvowi. Jeden ekran ma naraz jedno zadanie agenta, więc mniej
agentów z pulpitem to mniej odmów „pulpit zajęty”.

## Jak działa

```
 Hermes (profil z pulpit: true)
   └─ wtyczka jarvo-pulpit (pulpit/plugin/__init__.py): narzędzie `pulpit`, zamek pulpitu, zrzut jako obraz
        └─ silnik (pulpit/plugin/silnik.py, /usr/bin/python3: PyGObject z AT-SPI, Wnck, Gdk + Pillow)
             ├─ zrzut: Gdk (okno główne X11) → 1280×720 JPEG z numerami elementów
             ├─ elementy: AT-SPI aktywnego okna i jego otwartych menu (do 60, najwyżej 200; ok. 2,5 s na przejście)
             ├─ wejście: XTEST (libX11, libXtst przez ctypes), polskie znaki przez chwilowo przypisany wolny klawisz
             └─ okna: Wnck (lista, aktywacja, zamknięcie, nowe okno uruchomionego programu)
```

- Silnik to proces potomny procesu Hermesa (jeden na proces, kończy się po 15 min bez wywołań), rozmowa JSON
  w wierszach. Pamięta numery elementów z ostatniego `zobacz`.
- Wynik `zobacz` (i `kroki` z `zobacz_po`) to koperta `_multimodal` z obrazem, ta sama co `capture` computer_use
  Hermesa; gdy Hermes kieruje obrazy do `auxiliary.vision` (model bez obrazu), wynik jest tekstem ze ścieżką
  zrzutu w `cache/images` (ostatnie 20 plików `pulpit_*.jpg`).
- Współrzędne: jedna przestrzeń obrazu całego ekranu (1920×1080 → 1280×720); lista elementów, `xy`, `obszar`
  i położenie okien są w niej, silnik przelicza na piksele ekranu.
- Paragon po każdym działaniu: zmiana ekranu (miniatura 320×180 przed i po, ekran musi stanąć), nowe i zamknięte
  okna, aktywne okno, element z fokusem i jego treść (pole hasła bez treści).
- Przy starcie silnik ustawia `org.a11y.Status IsEnabled` (jak czytnik ekranu), a programy uruchamia
  z `QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1`, `GNOME_ACCESSIBILITY=1` i `SAL_USE_VCLPLUGIN=gtk3`, żeby Qt (Kdenlive),
  Firefox i LibreOffice dawały drzewo AT-SPI.

## Akcje

| Akcja | Parametry | Wynik |
|---|---|---|
| `zobacz` | `maks`, `obszar` [x, y, szer, wys], `elementy: false`, `numery: false` | obraz z numerami + lista `[n] rola „napis” = „wartość” (stany) @x,y` |
| `klik` | `numer` albo `xy`, `przycisk` (lewy, prawy, srodkowy), `podwojny` | paragon |
| `pisz` | `tekst`, opcjonalnie `numer`/`xy` (najpierw klik), `zamien` (ctrl+a) | paragon z treścią pola |
| `klawisz` | `klawisz` (Return, ctrl+s, alt+F4…), `razy` | paragon |
| `przewin` | `kierunek`, `ile`, opcjonalnie `numer`/`xy` | paragon |
| `przeciagnij` | `numer`/`xy` → `do_numer`/`do_xy` | paragon |
| `okna`, `aktywuj`, `zamknij` | `okno` (fragment tytułu albo id) | lista albo paragon |
| `uruchom` | `program`, `argumenty` (pliki, adres), `sekundy` | paragon z nowym oknem |
| `czekaj` | `tekst` albo `okno` (z `zniknie`) albo nic (ekran stoi), `sekundy` do 60 | spełnione albo czas minął |
| `kroki` | `kroki` (do 20 akcji), `zobacz_po` | paragon na krok, staje na pierwszym błędzie |

Programy `uruchom`: gimp, calc, writer, impress, draw, libreoffice, mousepad, thunar, ristretto, parole, firefox
(też jako `przegladarka`, np. edytor HQ), kdenlive i inkscape. Kdenlive 26.08.3 i Inkscape 1.4.4 to AppImage
z [`vendor/natywne.yaml`](../vendor/natywne.yaml) (`kiedy: przy-uzyciu`, sha256): pierwsze `uruchom` pobiera plik
przez `jarvo/przy_uzyciu.py`, potem są też w PATH procesów floty. Opcji programów w `argumenty` nie ma (tylko pliki
i adresy).

## Twarde zasady

Silnik sprawdza je przed działaniem; odmowa nic nie robi.
- Płatność: kliknięcie przycisku albo linku płatności (cel i przodkowie, wzorce z
  [`infra/komputer/zasady.py`](../infra/komputer/zasady.py), `KATEGORIE = ("platnosc",)`), Enter w takim polu,
  pisanie w pole karty, CVV, BLIK albo numeru karty (Luhn) tylko z linią `ZGODA WŁAŚCICIELA: platnosc` w zadaniu
  agenta (`komputer/zgoda_karty.py`). Klucz albo token w tekście: zawsze odmowa.
- Bez terminali, okna uruchamiania poleceń (xfrun4, appfinder) i menedżera zadań: polecenia idą przez `terminal`
  z jego zgodami.
- Bez okna Komputera Jarva (Chrome z profilem Komputera): tam działa `komputer` ze swoimi zasadami.
- Bez skrótów, które wylogowują, blokują ekran, zabijają okno (xkill) albo otwierają terminal i uruchamianie
  poleceń (ctrl+alt+t, super+t, alt+F2, alt+F3, super+r, ctrl+alt+l, super+l, ctrl+alt+delete,
  ctrl+alt+backspace, ctrl+alt+escape, ctrl+shift+escape, super+p, alt+super+s).
- Zamek pulpitu (`<korzeń>/stan/pulpit/zamek.json`): działać może jedno zadanie agenta; inne dostaje „pulpit
  zajęty” z tym, kto pracuje, i czasem do zwolnienia (120 s od jego ostatniego działania). Patrzeć (`zobacz`,
  `okna`, `czekaj`) wolno zawsze.
- Pod YOLO wtyczka `jarvo-zgody` blokuje `pulpit` jak inne narzędzia ekranu, a prywatne numery właściciela
  blokuje w `tekst` i `kroki`.

## Instalacja

- Build ([`scripts/build.py`](../scripts/build.py), tylko układ natywny na Linuksie) kopiuje `pulpit/plugin` do
  `plugins/jarvo-pulpit` razem z `zasady.py` i `zgoda_karty.py`, włącza wtyczkę i dokłada toolset `pulpit` na
  platformach rozmowy i zadań (bez cron) w profilach z `pulpit: true`; `validate.py` nie pozwala wpisać toolsetu
  ręcznie. `install_fleet.py` dowiązuje wtyczkę w tych profilach.
- Wymagania pulpitu: Linux z X11 i rozszerzeniem XTEST, `/usr/bin/python3` z `python3-gi`, `gir1.2-atspi-2.0`,
  `gir1.2-wnck-3.0`, `gir1.2-gtk-3.0` i `python3-pil` (pakiety pulpitu Ubuntu z Xfce), FUSE 2 dla AppImage (bez
  niego AppImage rozpakowuje się przy starcie). Bez nich narzędzie mówi, czego brak.
- Inny ekran: `JARVO_PULPIT_DISPLAY`, inny Python systemu: `JARVO_PULPIT_PYTHON`.

## Skille

Wspólne skille ([`shared/skills`](../shared/skills), ładowane na żądanie): `pulpit` (pętla i zasady), `gimp`,
`libreoffice`, `kdenlive` (z `scripts/melt.py`: melt z AppImage Kdenlive), `edytor-hq` (edytor filmów HQ
w przeglądarce na pulpicie).

## Porządek na `:0`

Okno zgłoszenia awarii apport („Ubuntu”) zabiera fokus programom agenta, więc silnik zamyka je przy starcie i przed
każdym `uruchom` (samo zgłoszenie zostaje w `/var/crash`). Nowe okna przestają się pokazywać po
`gsettings set com.ubuntu.update-notifier show-apport-crashes false` (ustawienie właściciela, bez sudo), a całe
zbieranie awarii wyłącza właściciel poleceniem `sudo systemctl disable --now apport.service`. Jarvo tych ustawień nie
zmienia sam, bo to pulpit właściciela poza katalogiem Jarva.
