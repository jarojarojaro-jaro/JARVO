"""Kątownik montażowy 60 × 40 mm z dwoma otworami pod wkręty 4 mm z łbem walcowym (pogłębienie) i żebrem."""
from build123d import *

# --- parametry (mm)
szer, gl, grub = 60, 40, 6      # podstawa
wys = 36                        # ścianka od podłogi
otwor, leb, leb_gl = 4.4, 8, 2.5   # wkręt 4 mm: otwór z luzem 0,4, łeb walcowy 8 mm
r_naroza = 5

with BuildPart() as katownik:
    Box(szer, gl, grub, align=(Align.CENTER, Align.CENTER, Align.MIN))
    with Locations((0, gl / 2 - grub / 2, grub)):
        Box(szer, grub, wys - grub, align=(Align.CENTER, Align.CENTER, Align.MIN))
    # zaokrąglone tylko przednie narożniki podstawy (tylne łączą się ze ścianką)
    fillet(katownik.edges().filter_by(Axis.Z).group_by(Axis.Y)[0], radius=r_naroza)
    # żebro w środku: trójkąt w płaszczyźnie YZ, 4 mm grubości
    with BuildSketch(Plane.YZ):
        with BuildLine():
            Polyline((gl / 2 - grub, grub), (gl / 2 - grub - 20, grub), (gl / 2 - grub, wys - 4), close=True)
        make_face()
    extrude(amount=2, both=True)
    with Locations((-18, -6, grub), (18, -6, grub)):
        CounterBoreHole(radius=otwor / 2, counter_bore_radius=leb / 2, counter_bore_depth=leb_gl)

wynik = katownik.part
