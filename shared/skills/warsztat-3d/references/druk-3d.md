# Druk 3D (FDM): reguły modelu

Domyślnie zakładamy zwykłą drukarkę FDM z dyszą 0,4 mm i warstwą 0,2 mm (Prusa, Bambu, Creality). Inna technologia
(żywica SLA, proszek SLS, frez CNC) → zapytaj, bo reguły są inne. Wartości to bezpieczny start, nie norma.

## Ścianki i szczegóły
| Element | Minimum | Dobrze |
|---|---|---|
| Ścianka pionowa | 0,8 mm (2 obrysy) | 1,2–2 mm; obciążona 2,5–3 mm |
| Dno i strop | 0,6 mm | 1–2 mm |
| Najmniejszy detal w XY (żebro, ząbek) | 0,8 mm | ≥ 1,2 mm |
| Napis wypukły / wklęsły | 0,4 mm wysokości, krój ≥ 6 mm | 0,6–1 mm, krój bezszeryfowy, kreska ≥ 0,8 mm |
| Otwór pionowy (wychodzi mniejszy) | + 0,2–0,4 mm do średnicy | sprawdź próbką |

## Luzy (pasowania)
- Wcisk (na stałe): 0–0,1 mm. Ślizg (pokrywa, szuflada): 0,2–0,3 mm na stronę. Luźno (zawias, oś): 0,4–0,5 mm.
- Wkręt przez otwór: średnica + 0,4 mm (M3 → 3,4; M4 → 4,4). Wkręt w tworzywo bezpośrednio: średnica − 0,5 mm
  (np. 2,5 pod wkręt 3 mm do plastiku). Gwint metryczny na stałe: wkładka wtapiana (M3: otwór 4,0–4,2 mm,
  głębokość = długość wkładki + 1 mm).
- Nakrętka w gnieździe sześciokątnym: wymiar pod klucz + 0,2–0,3 mm (M3: 5,5 → 5,8).
- Dwie części do złożenia drukuj osobno (raport daje osobne STL); w skrypcie rozsuń je, żeby nie przenikały.

## Kształt pod druk
- **Nawisy:** do 45° od pionu drukują się bez podpór. Poziome dno nad pustką > 5–10 mm (most) albo nawis > 45°
  → zmień kształt (faza 45° zamiast poziomej półki, łezka zamiast poziomego otworu) albo zaplanuj podpory.
- **Płaski spód:** model ma stać na stole największą płaską ścianą; spód na Z = 0. Zaokrąglenie na krawędzi przy
  stole zamień na fazę (zaokrąglenie dolne wymaga podpór), zaokrąglenia na górze zostają.
- **Wytrzymałość:** wydruk jest najsłabszy między warstwami (w osi Z). Część zginana (hak, zatrzask) układaj
  tak, żeby siła szła wzdłuż warstw, nie je rozrywała. Zaokrąglenie w narożu wewnętrznym (≥ 1 mm) zmniejsza pękanie.
- **Bez cienkich mostków** między dużymi bryłami, bez ostrych wewnętrznych narożników przy obciążeniu.
- Duża płaska część (> 150 mm) może się odkształcić (ABS, ASA najbardziej): zaokrąglone rogi, ewentualnie żebra.

## Materiał (dla raportu)
| Materiał | Gęstość g/cm³ | Kiedy |
|---|---|---|
| PLA | 1,24 | domyślnie: łatwy, sztywny, nie na słońce i ciepło (mięknie ~55 °C) |
| PETG | 1,27 | wytrzymalszy, lekko giętki, do ~70 °C, wilgoć ok |
| ABS / ASA | 1,04 / 1,07 | ciepło do ~90 °C; ASA na zewnątrz (UV); drukarka z obudową |
| TPU | 1,21 | elastyczny: uszczelki, nóżki, etui |
| Nylon (PA) | 1,14 | zawiasy, koła zębate, ścieranie; trudniejszy w druku |

Masa w raporcie to bryła pełna. Realny wydruk (2–3 obrysy, 15–20% wypełnienia) waży zwykle 30–60% tego; podaj
obie liczby jako szacunek, a dokładną masę i czas druku pokaże slicer.

## Pliki dla właściciela
- **3MF** do slicera (jednostki i kilka części w jednym pliku; PrusaSlicer, Bambu Studio, Cura czytają),
  **STL** gdy slicer albo drukarnia chce STL (zestaw: osobny STL każdej części), **STEP** do dalszej edycji w CAD
  albo do wyceny u wykonawcy.
- Nie wysyłamy plików do drukarni ani serwisu w sieci: robi to właściciel.
