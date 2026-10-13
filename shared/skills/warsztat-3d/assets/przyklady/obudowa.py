"""Obudowa z pokrywą na płytkę 50 × 30 mm: dwie części, kolory, napis, otwory wentylacyjne."""
from build123d import *

# --- parametry (mm)
plytka_x, plytka_y, plytka_z = 50, 30, 15
scianka = 2.0        # ≥ 1,2 mm przy druku z dyszą 0,4
luz = 0.3            # pasowanie pokrywy
promien = 3

zew_x, zew_y = plytka_x + 2 * scianka + 2 * luz, plytka_y + 2 * scianka + 2 * luz

with BuildPart() as dno:
    with BuildSketch():
        RectangleRounded(zew_x, zew_y, promien)
    extrude(amount=plytka_z + scianka)
    offset(amount=-scianka, openings=dno.faces().sort_by(Axis.Z)[-1])     # skorupa otwarta od góry
    with BuildSketch(dno.faces().sort_by(Axis.Y)[0]) :                      # otwór na złącze w przedniej ściance
        Rectangle(12, 6)
    extrude(amount=-scianka, mode=Mode.SUBTRACT)
    with Locations((0, 0, scianka)):          # od dna w środku, w dół przez dno
        with PolarLocations(radius=8, count=6):
            Hole(radius=1.5, depth=scianka)
dno.part.label, dno.part.color = "dno", Color("#3A5A8C")

with BuildPart() as pokrywa:
    with BuildSketch():
        RectangleRounded(zew_x, zew_y, promien)
    extrude(amount=scianka)
    with BuildSketch(Plane.XY.offset(-4)):
        RectangleRounded(plytka_x + 2 * luz - 0.2, plytka_y + 2 * luz - 0.2, max(0.5, promien - scianka))
        RectangleRounded(plytka_x + 2 * luz - 0.2 - 2 * 1.6, plytka_y + 2 * luz - 0.2 - 2 * 1.6, 0.5, mode=Mode.SUBTRACT)
    extrude(amount=4)
    with BuildSketch(pokrywa.faces().sort_by(Axis.Z)[-1]):
        Text("JARVO", font_size=7)
    extrude(amount=-0.6, mode=Mode.SUBTRACT)                                 # napis wklęsły 0,6 mm
pokrywa.part.label, pokrywa.part.color = "pokrywa", Color("#E4572E")

wynik = Compound(children=[dno.part, Pos(0, 0, plytka_z + scianka + 10) * pokrywa.part])
