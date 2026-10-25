---
name: warsztat-3d
description: "Model 3D z kodu (build123d): STEP, STL, GLB, 3MF, podgląd PNG, film obrotu."
version: 1.1.1
author: "Jarvo (silnik: build123d, Apache-2.0, na OpenCascade, LGPL-2.1; podgląd: Three.js, MIT)"
license: MIT
metadata:
  hermes:
    tags: [3d, cad, build123d, opencascade, step, stl, gltf, glb, 3mf, 3d-printing, threejs, turntable]
  jarvo:
    autonomy: A0
    reviewed: "2026-10-25"
---

# Warsztat 3D: model z kodu

Bryła 3D opisana kodem Pythona (build123d na jądrze OpenCascade, tym samym co FreeCAD): wymiary w milimetrach,
parametry na górze skryptu, zmiana wymiaru = jedna liczba i ponowna budowa. Z jednego skryptu powstaje komplet:
**STEP** (CAD, CNC, wycena u wykonawcy), **STL** i **3MF** (druk 3D), **GLB** (strona, aplikacja, scena Three.js),
raport (wymiary, objętość, masa, poprawność) oraz podgląd **PNG** i **film obrotu MP4**. Wszystko na tym komputerze
i bez tokenów na render; sieć tylko raz, gdy na komputerze właściciela pierwsze użycie instaluje silnik (niżej).

## Kiedy użyć
- **Druk 3D:** uchwyt, obudowa, zaślepka, podkładka, organizer, część zamienna z wymiarami od właściciela.
- **Web:** model produktu albo części na stronę klienta (GLB do sceny Three.js), packshot PNG bez studia.
- **Wideograf:** film obrotu części (rolka, intro, explainer „jak to jest zbudowane”), GLB do sceny Three.js
  w filmie HTML (skille `threejs-*`, kontrakt `jarvo`).
- **Mobile:** model do aplikacji (GLB, np. expo-gl i Three.js), obraz produktu do karty sklepu.
- **Zapytanie do wykonawcy:** STEP + raport wymiarów do wyceny frezowania, cięcia albo druku.

## Kiedy NIE używać
- kształty organiczne: postać, twarz, zwierzę, rzeźba, ubranie (to modelowanie siatką, nie CAD; Blendera jeszcze
  nie mamy, decyzja właściciela),
- realistyczny render ze zdjęć, skan 3D, fotogrametria; gra (silnik gry to osobna praca),
- logo i znaki towarowe cudzych marek na modelu (napis klienta tak, cudzy znak nigdy),
- części, od których zależy bezpieczeństwo (nośne, ciśnieniowe, medyczne, do pojazdu): model tak, ale w raporcie
  wprost „wymaga sprawdzenia przez konstruktora”; nie obiecujesz wytrzymałości.

## Kroki
```bash
C="$HERMES_HOME/skills/design/warsztat-3d/scripts/cad.py"
@@PY@@ "$C" stan                                            # silnik, podgląd, ffmpeg (albo co pobierze 1. użycie)
@@PY@@ "$C" zainstaluj                                      # 1. użycie u właściciela: silnik CAD teraz
@@PY@@ "$C" zbuduj model.py -o out/3d/uchwyt --podglad      # STEP, STL, GLB, 3MF, raport JSON i PNG
@@PY@@ "$C" zbuduj model.py -o out/3d/uchwyt --formaty stl,3mf --material petg
@@PY@@ "$C" podglad out/3d/uchwyt/model.glb -o out/3d/uchwyt/spod.png --wysokosc -40 --siatka
@@PY@@ "$C" obrot out/3d/uchwyt/model.glb -o out/3d/uchwyt/obrot.mp4 --sekundy 6 --rozmiar 1080x1080
```
**Pierwsze użycie na komputerze właściciela.** W instalacji Jarva na komputerze (bez kontenera) silnika CAD na
początku nie ma: `stan` mówi wtedy „pobierze się przy pierwszym…” (z `--json`: `silnik_przy_uzyciu`, ok. 215 MB).
Pierwsze `zbuduj` pobiera go z sumami z manifestu (1–3 min), więc najpierw `cad.py zainstaluj` z limitem czasu
terminala ok. 900 s i jedno zdanie do właściciela („instaluję raz silnik 3D, ok. 2 min”). Przerwane pobieranie
wznowi się przy następnym poleceniu. Three.js do podglądu przychodzi już z instalacją Jarva (narzędzia npm floty);
gdy `stan` pokazuje „brak Three.js”, właściciel uruchamia instalację jeszcze raz. Błąd instalacji (brak sieci, inna
suma) zgłaszasz właścicielowi, nie obchodzisz go.

1. **Wymagania w liczbach.** Zanim napiszesz kod: wymiary (mm), do czego pasuje (śruba M4? płytka 50 × 30?),
   materiał i sposób wykonania (druk FDM, frez, tylko wizualizacja). Brakuje kluczowego wymiaru → jedno pytanie
   do właściciela, z propozycją („przyjmuję ściankę 2 mm, dobrze?”). Nie zgadujesz wymiarów pod coś istniejącego.
2. **Skrypt modelu** (`model.py` w katalogu zlecenia): parametry na górze jako nazwane zmienne z komentarzem,
   potem budowa, na końcu `wynik = ...`. Wzory: `assets/przyklady/katownik.py` (jedna część),
   `assets/przyklady/obudowa.py` (dwie części z nazwami i kolorami). Ściąga API: `references/build123d.md`.
3. **Budowa:** `cad.py zbuduj … --podglad`. Błąd skryptu wraca z numerem linii; popraw i powtórz.
4. **Sprawdź sam, zanim pokażesz:** raport (`wymiary_mm` zgodne z zamówieniem, `poprawny: true`, `bryly` = liczba
   części, brak `!` o osobnych bryłach) i obejrzyj PNG (otwory tam, gdzie mają być, nic nie wisi w powietrzu).
   Wątpliwy fragment → drugi widok (`podglad --kat 215`, `--wysokosc -40` od spodu, `--siatka` dla skali).
5. **Druk 3D:** reguły z `references/druk-3d.md` (ścianki, luzy, nawisy, ułożenie na stole); w raporcie dla
   właściciela: wymiary, masa w wybranym materiale (przy 100% wypełnienia; realny wydruk 15–20% wypełnienia waży
   mniej), które pliki do slicera (3MF albo STL; zestaw: osobny STL każdej części).
6. **Oddaj:** PNG i (na prośbę albo do filmu) MP4 liniami `MEDIA:<ścieżka>`; pliki CAD (STEP, STL, 3MF, GLB) też
   `MEDIA:`, a przy wielu plikach link do katalogu `@@PY@@ "@@REPO_DIR@@/scripts/jarvo_link.py" <katalog>`.
   W odpowiedzi: co to jest, wymiary, masa, co przyjąłeś bez danych od właściciela, jak zmienić (parametr w skrypcie).

## Opcje
- `zbuduj`: `--nazwa` (pliki `<nazwa>.*`, domyślnie nazwa skryptu), `--formaty step,stl,glb,3mf`, `--dokladnosc`
  (odchyłka siatki w mm, domyślnie 0,05; 0,02 = gładsze łuki i większy plik), `--material pla|petg|abs|asa|tpu|
  nylon|aluminium|stal|drewno` albo `--gestosc` (g/cm³), `--mimo-bledow` (eksport niepoprawnego kształtu tylko
  do obejrzenia, nigdy do druku), `--limit` (sekundy, domyślnie 300), `--json`.
- `podglad` i `obrot`: `--kat` (obrót modelu, domyślnie 35°), `--wysokosc` (kamera nad podłogą, domyślnie 25°,
  ujemna = od spodu), `--kolor "#RRGGBB"` (cały model; bez niego kolory z `.color` części albo szary), `--tlo`,
  `--przezroczyste` (tylko PNG), `--siatka` (podłoga co 10 mm), `--bez-krawedzi` (miękki render bez linii),
  `--skala 2` (ostrzej), `--rozmiar SZERxWYS`. Film: `--sekundy` (1–60), `--fps` (10–60).
- Zestaw części: `wynik = [czesc_a, czesc_b]` albo `Compound(children=[…])`; nazwa części z `.label`
  (litery łacińskie, cyfry, `-`), kolor z `.color = Color("#RRGGBB")`. Raport ma wtedy `czesci` z wymiarami
  i masą każdej, a STL powstaje też osobno dla każdej części.

## Czas i rozmiar
Budowa z eksportem i podglądem PNG ~10–20 s. Film obrotu liczy WebGL na procesorze (SwiftShader, sam bierze wszystkie
rdzenie, więc kilka renderów naraz nie przyspiesza): na serwerze z 4 rdzeniami ~0,65 s na klatkę 1080 × 1080,
~0,45 s na 720 × 720, czyli film 6 s × 30 kl./s (180 klatek) w 1080 × 1080 ~2 min, a wersja robocza
`--rozmiar 720x720 --fps 24` ~1 min; na komputerze właściciela z 12 wątkami ~0,16 s na klatkę 1080 × 1080
(ten sam film ~30 s). Najpierw sprawdź kadr na PNG (`podglad`), film dopiero z dobrym ujęciem. Film dłuższy niż kilka
minut renderu (np. 20 s w 1080 × 1080 na serwerze ≈ 6–7 min) → najpierw powiedz właścicielowi, ile potrwa.

## Nigdy
- **Bez sieci w skrypcie modelu:** żadnych pobrań, `requests`, `urllib`; `cad_model.py` blokuje gniazda.
  `export_to_pcbway` (wysyła plik do PCBWay) i `download_*` z bibliotek materiałów są zakazane: plik klienta nie
  wychodzi z serwera bez zgody właściciela.
- Pliki wejściowe tylko lokalne i od właściciela (`import_step`, `import_svg` z ścieżki w zleceniu): z internetu
  nie ściągasz modeli ani rysunków.
- Nie oddajesz modelu z `poprawny: false` ani z błędem w raporcie jako gotowego; nie podajesz wymiarów, których
  nie ma w raporcie.
- Nie obiecujesz wytrzymałości, pasowania „na pewno” ani dopuszczeń (CE, do żywności, do dzieci).
