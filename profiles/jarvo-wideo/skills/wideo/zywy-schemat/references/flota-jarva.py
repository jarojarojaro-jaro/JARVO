#!/usr/bin/env python3
"""Przykład żywego schematu „Jak działa flota Jarva” (Instagram 4:5, motyw jarvo-jasny): config liczony skryptem.

    python3 flota-jarva.py [wyjscie.json]      # domyślnie flota-jarva.json obok

Wzór do własnych schematów: współrzędne z kilku stałych (szerokość ramki, odstęp, szyny), pętla po ramkach,
jedna maszyna `cycle` (`seq`, 8 kroków po 3,5 s) steruje obwódkami (`when`/`then`), strzałkami i listą kroków,
kropki (`flow`) jadą tylko po aktywnej drodze. Tekst w bezpiecznych marginesach: x 65–1015, y 108–1242.
"""
import json
import sys
from pathlib import Path

W, H = 1080, 1350
CX = W // 2


def seq(*k: int) -> dict:
    """Warunek: krok misji (indeks maszyny `seq`) jest jednym z k."""
    return {"var": "seq.i", "in": list(k)}


E = []
# tytuł
E.append({"type": "text", "x": 65, "y": 148, "w": 950, "align": "center", "size": 44, "b": 1, "c": "ink", "t": "Jak działa flota Jarva"})
E.append({"type": "text", "x": 65, "y": 192, "w": 950, "align": "center", "size": 18, "c": "dim",
          "t": "9 agentów: Jarvo prowadzi, 8 specjalistów robi"})

def box(x, y, w, h, color, fill, lines, when=None, glow=None, pad=(8, 8, 8), align="center", **kw):
    b = {"type": "box", "x": x, "y": y, "w": w, "h": h, "color": color, "fill": fill, "pad": list(pad), "align": align,
         "lines": lines, "radius": 10, "border": 1.5, **kw}
    if when is not None:
        b["when"] = when
        b["then"] = {"glow": glow or color, "border": 2.6, "color": glow or color}
    return b

def path(points, when=None, color="line", width=2.0, arrow=True, head=10):
    p = {"type": "path", "points": points, "color": color, "width": width, "r": 8, "head": head}
    if not arrow:
        p["arrow"] = False
    if when is not None:
        p["when"] = when
        p["then"] = {"color": "ak", "width": 3.2}
    return p

def flow(points, when=None, color="pk", period=1.4, offsets=(0, 0.5)):
    f = {"type": "flow", "path": points, "period": period, "offsets": list(offsets), "color": color}
    if when is not None:
        f["when"] = when
    return f

FLOWS = []
# Ty
E.append(box(300, 218, 480, 68, "gy", "gyf", [{"t": "👤 Ty: zlecenie", "size": 20, "b": 1, "c": "ink"},
          {"t": "na Telegramie albo w HQ, zwykłym językiem", "size": 14, "c": "dim"}], when=seq(0, 7), glow="ak", pad=(9, 8, 8)))
E.append(path([[CX, 286], [CX, 326]], when=seq(0)))
FLOWS.append(flow([[CX, 286], [CX, 326]], when=seq(0), period=1.0))
# Jarvo
E.append(box(300, 326, 480, 100, "ak", "akf", [{"t": "🛰️ Jarvo", "size": 23, "b": 1, "c": "rdt"},
          {"t": "przyjmuje zlecenie, zakłada misję", "size": 15, "c": "fg"},
          {"t": "i rozbija ją na karty kanbana", "size": 15, "c": "fg"}], when=seq(0, 6), glow="ak", pad=(9, 8, 8)))
# Skarbiec (lewo)
E.append(box(65, 326, 190, 100, "bl", "blf", [{"t": "📚 Skarbiec wiedzy", "size": 16, "b": 1, "c": "blt"},
          {"t": "skille, decyzje, lekcje", "size": 13, "c": "fg"}, {"t": "czytany przed pracą", "size": 13, "c": "dim"}],
          when=seq(0, 7), glow="bl", pad=(12, 6, 6)))
E.append(path([[255, 360], [300, 360]], when=seq(0), head=9))
E.append(path([[300, 392], [255, 392]], when=seq(7), head=9))
FLOWS.append(flow([[255, 360], [300, 360]], when=seq(0), period=0.9, offsets=(0,)))
FLOWS.append(flow([[300, 392], [255, 392]], when=seq(7), period=0.9, offsets=(0,)))
# Kanban (prawo)
E.append(box(825, 326, 190, 100, "yl", "ylf", [{"t": "📋 Kanban", "size": 16, "b": 1, "c": "ink"},
          {"t": "karta: cel, DoD, agent", "size": 13, "c": "fg"}, {"t": "1 karta = 1 zadanie", "size": 13, "c": "dim"}],
          when=seq(0), glow="yl", pad=(12, 6, 6)))
E.append(path([[780, 376], [825, 376]], when=seq(0), head=9))
FLOWS.append(flow([[780, 376], [825, 376]], when=seq(0), period=0.9, offsets=(0.3,)))

# specjaliści: 8 w rzędzie
AG = [("🔎", "Sherlock", "research", "bl", "blf"), ("🌐", "Web", "strony", "tl", "tlf"), ("🎬", "Studio", "posty, copy", "or", "orf"),
      ("🎥", "Wideograf", "filmy", "pu", "puf"), ("📈", "Ads", "reklamy", "yl", "ylf"), ("🎯", "Łowca", "leady", "gn", "gnf"),
      ("📱", "Aplikacje", "mobilne", "mc", "mcf"), ("🦾", "Prawa ręka", "zadania", "gy", "gyf")]
KROK_AGENT = {1: 0, 2: 2, 3: 3, 4: 1, 5: 4}          # krok misji → agent
AGENT_KROK = {a: k for k, a in KROK_AGENT.items()}
BW, GAP, X0, Y_TOP, Y_BOT = 110, 10, 65, 498, 598
BUS1, BUS2, REC_Y = 462, 628, 664
cx = [X0 + i * (BW + GAP) + BW // 2 for i in range(8)]
E.append(path([[CX, 426], [CX, BUS1]], arrow=False))
E.append(path([[cx[0], BUS1], [cx[-1], BUS1]], arrow=False))
E.append(path([[cx[0], BUS2], [cx[-1], BUS2]], arrow=False))
E.append(path([[CX, BUS2], [CX, REC_Y]], when=seq(1, 2, 3, 4, 5, 6)))
for i, (emo, name, role, col, fill) in enumerate(AG):
    k = AGENT_KROK.get(i)
    w = seq(k) if k is not None else None
    E.append(box(X0 + i * (BW + GAP), Y_TOP, BW, Y_BOT - Y_TOP, col, fill,
                 [{"t": emo, "size": 28, "h": 1.55}, {"t": name, "size": 15, "b": 1, "c": "ink"}, {"t": role, "size": 12.5, "c": "dim"}],
                 when=w, glow="ak", pad=(8, 3, 3)))
    E.append(path([[cx[i], BUS1], [cx[i], Y_TOP]], when=w, head=8))
    E.append(path([[cx[i], Y_BOT], [cx[i], BUS2]], when=w, arrow=False))
    if k is not None:
        FLOWS.append(flow([[CX, 426], [CX, BUS1], [cx[i], BUS1], [cx[i], Y_TOP]], when=seq(k), period=1.6, offsets=(0, 0.8)))
        FLOWS.append(flow([[cx[i], Y_BOT], [cx[i], BUS2], [CX, BUS2], [CX, REC_Y]], when=seq(k), period=1.6, offsets=(0.4, 1.2)))
# spokojne kropki na szynie, gdy nikt nie pracuje (struktura żyje)
FLOWS.append(flow([[CX, 426], [CX, BUS1], [cx[-1], BUS1]], when=seq(0, 6, 7), color="gy", period=3.0, offsets=(0,)))
FLOWS.append(flow([[CX, 426], [CX, BUS1], [cx[0], BUS1]], when=seq(0, 6, 7), color="gy", period=3.0, offsets=(1.5,)))
FLOWS.append(flow([[CX, BUS2], [CX, REC_Y]], when=seq(6), period=1.0, offsets=(0, 0.5)))
# Recenzja i wynik
E.append(box(300, REC_Y, 480, 84, "gn", "gnf", [{"t": "✅ Recenzja Jarva", "size": 18, "b": 1, "c": "ink"},
          {"t": "Definition of Done, jakość, źródła;", "size": 14, "c": "fg"},
          {"t": "poprawki wracają do agenta", "size": 14, "c": "dim"}], when=seq(6), glow="gn", pad=(7, 8, 8)))
E.append(path([[CX, REC_Y + 84], [CX, 784]], when=seq(7)))
FLOWS.append(flow([[CX, REC_Y + 84], [CX, 784]], when=seq(7), period=1.0))
E.append(box(300, 784, 480, 66, "gy", "gyf", [{"t": "📦 Wynik u Ciebie", "size": 18, "b": 1, "c": "ink"},
          {"t": "pliki i raport; wydatki tylko za Twoją zgodą", "size": 14, "c": "dim"}], when=seq(7), glow="ak", pad=(9, 8, 8)))
# Misja: lista kroków
KROKI = [("🛰️ Jarvo", "misja i 5 kart; najpierw skarbiec: co już wiemy"),
         ("🔎 Sherlock", "research rynku i konkurencji, ze źródłami"),
         ("🎬 Studio", "posty i copy na premierę"),
         ("🎥 Wideograf", "film 30 s na Reels"),
         ("🌐 Web", "landing produktu"),
         ("📈 Ads", "kampania Meta; budżet czeka na Twoją zgodę"),
         ("✅ Jarvo", "recenzja; poprawki wracają do kart"),
         ("📦 Ty", "wynik u Ciebie, lekcje trafiają do skarbca")]
rows = [{"t": "Misja (przykład): premiera nowego produktu", "size": 17, "b": 1, "c": "ink", "align": "left", "indent": 10, "h": 1.4}]
for k, (kto, co) in enumerate(KROKI):
    hl = {"var": "seq.i", "eq": k}
    rows.append({"align": "left", "indent": 10, "when": hl, "then": {"bg": "akf"}, "h": 1.12,
                 "items": [{"w": 56, "runs": [{"t": f"{k + 1}.", "size": 15, "c": "dim", "when": hl, "then": {"c": "rdt", "b": 1}}]},
                           {"w": 170, "runs": [{"t": kto, "size": 15, "c": "fg", "when": hl, "then": {"b": 1, "c": "ink"}}]},
                           {"grow": 1, "runs": [{"t": co, "size": 15, "c": "fg", "when": hl, "then": {"b": 1, "c": "ink"}}]}]})
E.append(box(65, 874, 950, 262, "gy", "wh", rows, pad=(8, 6, 6), align="left"))
E.append({"type": "text", "x": 65, "y": 1166, "w": 950, "align": "center", "size": 14, "c": "dim",
          "t": "● kropka = karta albo wynik w drodze · obwódka = kto teraz pracuje · jeden krok co 3,5 s"})
cfg = {"meta": {"title": "Jak działa flota Jarva", "lang": "pl"},
       "canvas": {"preset": "ig", "duration": 28, "fps": 30},
       "theme": {"preset": "jarvo-jasny"},
       "credit": {"text": "Misja i kolejność poglądowe · flota JARVO: 9 agentów (fleet.yaml) · ruch: live-panel (MIT)", "y": 1204, "size": 13},
       "machines": {"seq": {"type": "cycle", "period": 3.5, "t0": 0,
                            "values": ["plan", "sherlock", "studio", "wideograf", "web", "ads", "recenzja", "wynik"]}},
       "elements": E + FLOWS}
out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_suffix(".json")
out.write_text(json.dumps(cfg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"✓ {out}: {len(E)} elementów, {len(FLOWS)} przepływów")
