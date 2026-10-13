# build123d: ściąga do warsztatu 3D

Wersja w obrazie: build123d 0.13.0 (dokumentacja: <https://build123d.readthedocs.io/en/stable/>). Jednostki: mm.
Oś Z w górę, podłoga = płaszczyzna XY. Każdy fragment niżej jest sprawdzony w tej wersji.

## Szkielet skryptu
```python
"""Co to jest, do czego pasuje (jedno zdanie)."""
from build123d import *

# --- parametry (mm): nazwane, z komentarzem; zmiana = jedna liczba
szer, gl, wys = 60, 40, 6
scianka = 2.0          # ≥ 1,2 mm przy druku z dyszą 0,4

with BuildPart() as czesc:
    Box(szer, gl, wys, align=(Align.CENTER, Align.CENTER, Align.MIN))   # stoi na podłodze
    ...
wynik = czesc.part                 # obowiązkowo na końcu: to bierze cad.py
```

## Dwa style (można mieszać)
```python
# budowniczy: kolejne kroki w bloku with, Mode.SUBTRACT odejmuje
with BuildPart() as p:
    Box(40, 20, 10)
    Cylinder(4, 10, mode=Mode.SUBTRACT)

# algebra: działania na kształtach, Pos/Rot przesuwa i obraca
a = Box(40, 20, 10) - Pos(10, 0, 0) * Cylinder(4, 10)
a = Rot(0, 0, 45) * a              # obrót wokół Z o 45°
suma, czesc_wspolna = a + b, a & b
```

## Bryły i szkice
- Bryły: `Box(x, y, z)`, `Cylinder(r, h)`, `Sphere(r)`, `Cone(r_dol, r_gora, h)`, `Torus(R, r)`, `Wedge(...)`.
  `align=(Align.CENTER, Align.CENTER, Align.MIN)` = środek w XY, spód na Z = 0 (domyślnie środek bryły w 0).
- Szkic 2D w `BuildSketch(płaszczyzna)`: `Rectangle(x, y)`, `RectangleRounded(x, y, r)`, `Circle(r)`,
  `Ellipse(rx, ry)`, `RegularPolygon(r, n)`, `Polygon(*punkty)`, `SlotCenterToCenter(odl, szer)`,
  `Text("Łódź", font_size=6)`. Potem bryła: `extrude(amount=5)` (`both=True` w obie strony, ujemne = w dół;
  z `mode=Mode.SUBTRACT` = wycięcie), `revolve(axis=Axis.Z)`, `loft()` (między szkicami na kilku wysokościach),
  `sweep()` (szkic po ścieżce z `BuildLine`).
- Linie w `BuildLine()`: `Line`, `Polyline(*punkty, close=True)`, `Spline(*punkty)`, `CenterArc`, `RadiusArc`;
  zamknięty obrys → `make_face()` w szkicu. Niezamknięty → błąd „Face can only be created with closed wires”.

## Gdzie: płaszczyzny i rozmieszczenie
- `Plane.XY` (podłoga), `Plane.XZ` (przód), `Plane.YZ` (bok), `Plane.XY.offset(30)` (30 mm wyżej).
- Na ścianie bryły: `BuildSketch(p.faces().sort_by(Axis.Z)[-1])` (górna ściana), `[0]` = dolna.
- `with Locations((x, y, z), ...)`, `GridLocations(dx, dy, nx, ny)`, `PolarLocations(promien, ile)`:
  wszystko w bloku stawia się w każdym miejscu (otwory, żeberka, nóżki).

## Wybór krawędzi i ścian
```python
p.edges().filter_by(Axis.Z)              # krawędzie pionowe
p.edges().group_by(Axis.Z)[-1]           # krawędzie na samej górze
p.edges().filter_by(Axis.Z).group_by(Axis.Y)[0]   # pionowe z przodu (najmniejsze Y)
p.faces().sort_by(Axis.Z)[-1]            # górna ściana
p.faces().filter_by(GeomType.CYLINDER)   # ściany walcowe (otwory, zaokrąglenia)
```

## Operacje
- `fillet(krawedzie, radius=2)`, `chamfer(krawedzie, length=1)`: promień mniejszy niż połowa najcieńszej ścianki,
  inaczej błąd OpenCascade.
- Skorupa: `offset(amount=-scianka, openings=p.faces().sort_by(Axis.Z)[-1])` (pudełko otwarte od góry).
- Otwory od ściany w głąb (domyślnie przez całość): `Hole(radius)`, `CounterBoreHole(radius, counter_bore_radius,
  counter_bore_depth)` (łeb walcowy), `CounterSinkHole(radius, counter_sink_radius)` (łeb stożkowy).
  Stawiasz je `Locations` na wysokości ściany, z której wchodzą (np. `(x, y, grubosc)` dla podstawy).
- `mirror(about=Plane.YZ)` (lustro; sama kopia dokleja się tylko, gdy styka się z oryginałem),
  `split(bisect_by=Plane.XY, keep=Keep.BOTTOM)` (przecięcie), `Mode.INTERSECT` (część wspólna).
- Gwintów nie modelujemy: otwór pod wkręt z luzem albo pod wkładkę wtapianą (`references/druk-3d.md`).

## Kilka części, nazwy, kolory
```python
dno.part.label, dno.part.color = "dno", Color("#3A5A8C")
pokrywa.part.label = "pokrywa"
wynik = Compound(children=[dno.part, Pos(0, 0, 30) * pokrywa.part])   # albo: wynik = [dno.part, pokrywa.part]
```
Części obok siebie albo rozsunięte (widok złożenia): `Pos(...) *`. Raport: `czesci` z wymiarami każdej.

## Pliki od właściciela (tylko lokalne)
`import_step("/opt/data/jarvo/inbox/…/czesc.step")` (bryła z CAD), `import_svg("logo.svg")` (obrys do szkicu;
potem `extrude`). Z internetu nic nie pobierasz.

## Sprawdzenie w skrypcie (gdy trzeba)
`czesc.part.volume`, `czesc.part.bounding_box().size`, `czesc.part.is_valid`, `len(czesc.part.solids())`;
`print()` trafia do logu budowy, ale wynik i tak sprawdza raport `cad.py zbuduj`.

## Częste błędy
- `wynik` nie ustawiony → raport mówi, czego brakuje. Ustaw `wynik = czesc.part` na końcu.
- „2 osobne bryły” przy jednej części: element nie styka się z resztą (żebro, ucho, napis nad ścianą).
  Przesuń go tak, żeby nachodził na bryłę o ułamek milimetra.
- `StdFail_NotDone` przy fillet/chamfer: promień za duży albo krawędź z kilku kawałków; zmniejsz albo wybierz inne.
- Wymiary 1000× za małe/duże: wszystko w mm, nie w metrach ani calach.
