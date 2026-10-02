#!/usr/bin/env python3
"""Przegląd tygodnia jako strona (pomysł Karpathy'ego: liczby łatwiej zrozumieć z obrazu niż ze ściany tekstu).

Bez modelu (0 tokenów): z danych `fleet_report.py --mode weekly` (jakość, liczby floty, prosty polski) składa jedną
stronę HTML z kaflami, paskami jakości i tokenów na agenta oraz listami kart. Zapis do
`<dane>/jarvo/workspaces/jarvo/raporty/tydzien-RRRR-MM-DD.html` (podgląd w Jarvo HQ) i link na 7 dni z `jarvo_link.py`
(telefon, Telegram). Strona statyczna: CSP bez skryptów i sieci, tytuły kart escapowane (to dane od agentów).

    python3 raport_strona.py --fixture dane.json [--out strona.html]   # podgląd z zapisanych danych
"""

from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import sys
import time
from pathlib import Path

CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:"


def _e(x) -> str:
    return html.escape(str(x if x is not None else ""))


def _tys(n: int | float | None) -> str:
    n = n or 0
    return f"{n / 1e6:.1f} mln".replace(".", ",") if n >= 1e6 else f"{n / 1e3:.0f} tys." if n >= 1e3 else str(int(n))


def _kolor(p: int | None) -> str:
    return "var(--szary)" if p is None else "var(--dobry)" if p >= 80 else "var(--uwaga)" if p >= 60 else "var(--zly)"


def _kafel(etykieta: str, wartosc: str, opis: str = "", kolor: str = "") -> str:
    styl = f' style="color:{kolor}"' if kolor else ""
    return f'<div class="kafel"><span>{_e(etykieta)}</span><b{styl}>{_e(wartosc)}</b><small>{_e(opis)}</small></div>'


def _pasek(etykieta: str, ulamek: float, tekst: str, kolor: str) -> str:
    szer = max(0.0, min(1.0, ulamek)) * 100
    return (f'<div class="pasek"><span class="et">{_e(etykieta)}</span><span class="tor">'
            f'<i style="width:{szer:.1f}%;background:{kolor}"></i></span><span class="wart">{_e(tekst)}</span></div>')


def _lista(karty: list[dict], pusto: str, z_powodem: bool = False, limit: int = 12) -> str:
    if not karty:
        return f'<p class="pusto">{_e(pusto)}</p>'
    li = "".join(f'<li><b>{_e(k.get("title") or k.get("id"))}</b> <span>{_e(k.get("assignee") or "")}'
                 + (f' · {_e(k.get("reason") or "bez powodu")}' if z_powodem else "") + "</span></li>" for k in karty[:limit])
    reszta = f'<p class="pusto">… i {len(karty) - limit} więcej</p>' if len(karty) > limit else ""
    return f"<ul>{li}</ul>{reszta}"


def strona(dane: dict, od: str, do: str) -> str:
    """HTML przeglądu tygodnia z danych fleet_report (klucze: finished, blocked, in_flight, quality, liczby, prosty_polski)."""
    lz = dane.get("liczby") or {}
    jak = lz.get("jakosc") or dane.get("quality") or {}
    z1 = lz.get("za_1_razem") or {}
    esk, aw, cis, tok = lz.get("eskalacje") or {}, lz.get("awarie") or {}, lz.get("cisza") or {}, lz.get("tokeny") or {}
    pp = dane.get("prosty_polski") or {}
    tok_suma = {a: sum(v for k, v in t.items() if k != "sesje" and isinstance(v, (int, float))) for a, t in tok.items()}
    cisza_n = len(cis.get("bez_sygnalu") or []) + len(cis.get("blokady_bez_powodu") or [])
    kafle = "".join([
        _kafel("Zrobione", str(len(dane.get("finished") or [])), "kart w 7 dni"),
        _kafel("Za 1. razem", f"{z1['procent']}%" if z1.get("procent") is not None else "–",
               f"{z1.get('przyjete', 0)}/{z1.get('zrobione', 0)} bez poprawek", _kolor(z1.get("procent"))),
        _kafel("Stoi", str(len(dane.get("blocked") or [])), "czeka na decyzję albo dane",
               "var(--zly)" if dane.get("blocked") else ""),
        _kafel("Eskalacje", str(sum(v for v in esk.values() if isinstance(v, int))), "pytania, poza zakresem, porzucone"),
        _kafel("Awarie i cisza", str(sum(aw.values()) + cisza_n), "praca, która mogła przepaść",
               "var(--zly)" if sum(aw.values()) + cisza_n else ""),
        _kafel("Tokeny", _tys(sum(tok_suma.values())), "wszyscy agenci"),
        _kafel("Prosty polski", f"{pp.get('w_normie', 0)}/{pp.get('wiadomosci', 0)}" if pp.get("wiadomosci") else "–",
               "wiadomości do Ciebie w normie"),
    ])
    jakosc = "".join(_pasek(a.removeprefix("jarvo-"), s["first_pass"] / s["done"] if s.get("done") else 0,
                            f"{s.get('first_pass', 0)}/{s.get('done', 0)}" + (f" · poprawek {s['changes_requested']}" if s.get("changes_requested") else ""),
                            _kolor(round(100 * s["first_pass"] / s["done"]) if s.get("done") else None))
                     for a, s in sorted(jak.items(), key=lambda x: -x[1].get("done", 0))) or '<p class="pusto">Brak zakończonych kart.</p>'
    top = max(tok_suma.values() or [0]) or 1
    tokeny = "".join(_pasek(a.removeprefix("jarvo-"), v / top, _tys(v), "var(--akcent)")
                     for a, v in sorted(tok_suma.items(), key=lambda x: -x[1])) or '<p class="pusto">Brak danych o tokenach.</p>'
    uwagi = []
    if aw:
        uwagi.append("Awarie pracownika: " + ", ".join(f"{k} {v}" for k, v in aw.items()))
    if cis.get("bez_sygnalu"):
        uwagi.append("Bez sygnału życia: " + ", ".join(map(str, cis["bez_sygnalu"])))
    if cis.get("blokady_bez_powodu"):
        uwagi.append("Blokady bez powodu: " + ", ".join(map(str, cis["blokady_bez_powodu"])))
    if pp.get("najczestsze"):
        uwagi.append("Styl, najczęściej: " + ", ".join(pp["najczestsze"]))
    uwagi_html = "".join(f"<li>{_e(u)}</li>" for u in uwagi)
    return f"""<!doctype html><html lang="pl"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Tydzień floty {_e(do)}</title>
<style>
:root{{--tlo:#F6F5F0;--karta:#fff;--tusz:#1B1D22;--szary:#6B7280;--linia:#E5E4DD;--akcent:#D4213D;--dobry:#1F8A4C;--uwaga:#B7791F;--zly:#C0271C}}
@media (prefers-color-scheme:dark){{:root{{--tlo:#15171C;--karta:#1E2128;--tusz:#F2F1E8;--szary:#9AA0AA;--linia:#2C3039;--dobry:#3DD68C;--uwaga:#F5B83D;--zly:#FF6B5E}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--tlo);color:var(--tusz);font:16px/1.5 Inter,"Segoe UI",system-ui,sans-serif}}
main{{max-width:960px;margin:0 auto;padding:24px 16px 48px}}h1{{margin:0;font-size:28px}}h2{{font-size:18px;margin:0 0 12px}}
.pod{{color:var(--szary);margin:4px 0 20px}}section{{background:var(--karta);border:1px solid var(--linia);border-radius:14px;padding:18px;margin-top:16px}}
.kafle{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}}
.kafel{{background:var(--karta);border:1px solid var(--linia);border-radius:14px;padding:14px;display:flex;flex-direction:column;gap:2px}}
.kafel span{{color:var(--szary);font-size:13px}}.kafel b{{font-size:30px;line-height:1.1}}.kafel small{{color:var(--szary);font-size:12px}}
.pasek{{display:grid;grid-template-columns:110px 1fr 150px;gap:10px;align-items:center;margin:8px 0}}
.tor{{height:12px;background:var(--linia);border-radius:6px;overflow:hidden}}.tor i{{display:block;height:100%;border-radius:6px}}
.et{{font-weight:600}}.wart{{color:var(--szary);font-size:14px;text-align:right}}
.dwie{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}}
ul{{margin:0;padding-left:18px}}li{{margin:4px 0}}li span{{color:var(--szary);font-size:14px}}.pusto{{color:var(--szary);margin:0}}
footer{{color:var(--szary);font-size:13px;margin-top:20px}}
@media (max-width:560px){{.pasek{{grid-template-columns:80px 1fr;}}.wart{{grid-column:2;text-align:left}}}}
</style></head><body><main>
<h1>Tydzień floty</h1><p class="pod">{_e(od)} – {_e(do)} · strona bez modelu, z tablicy i sesji</p>
<div class="kafle">{kafle}</div>
<section><h2>Jakość: przyjęte za 1. razem</h2>{jakosc}</section>
<section class="dwie"><div><h2>Zrobione</h2>{_lista(dane.get("finished") or [], "Nic w tym tygodniu.")}</div>
<div><h2>Stoi</h2>{_lista(dane.get("blocked") or [], "Nic nie stoi.", z_powodem=True)}</div></section>
<section><h2>W toku</h2>{_lista(dane.get("in_flight") or [], "Nic w toku.")}</section>
<section><h2>Tokeny na agenta</h2>{tokeny}</section>
{f'<section><h2>Do uwagi</h2><ul>{uwagi_html}</ul></section>' if uwagi_html else ''}
<footer>Wygenerowane {_e(time.strftime('%Y-%m-%d %H:%M'))} przez raport_strona.py (fleet_report.py, liczby.py, prosty.py). Wnioski i propozycje: wiadomość Jarva.</footer>
</main></body></html>"""


def katalog_raportow() -> Path:
    h = Path(os.environ.get("HERMES_HOME", "/opt/data"))
    korzen = h.parent.parent if h.parent.name == "profiles" else h
    return Path(os.environ.get("JARVO_RAPORTY_DIR") or korzen / "jarvo" / "workspaces" / "jarvo" / "raporty")


def _jarvo_link() -> Path | None:
    """`scripts/jarvo_link.py` z repo floty (kontener: /opt/jarvo/repo; repo: trzy katalogi wyżej)."""
    for kandydat in (os.environ.get("JARVO_REPO", "/opt/jarvo/repo"), str(Path(__file__).resolve().parents[3])):
        p = Path(kandydat) / "scripts" / "jarvo_link.py"
        if p.is_file():
            return p
    return None


def zapisz(dane: dict, now: float, katalog: Path | None = None) -> dict:
    """Zapisuje stronę tygodnia i zwraca {"plik", "link"} (link None, gdy podgląd HQ niedostępny)."""
    katalog = katalog or katalog_raportow()
    katalog.mkdir(parents=True, exist_ok=True)
    od, do = (time.strftime("%Y-%m-%d", time.localtime(t)) for t in (now - 7 * 86400, now))
    plik = katalog / f"tydzien-{do}.html"
    plik.write_text(strona(dane, od, do), encoding="utf-8")
    link = None
    skrypt = _jarvo_link()
    if skrypt:
        try:
            r = subprocess.run([sys.executable, str(skrypt), str(plik)], capture_output=True, text=True, timeout=30)
            link = (r.stdout.strip().splitlines() or [None])[-1] if r.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            link = None
    return {"plik": str(plik), "link": link}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fixture", required=True)
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    dane = json.loads(Path(a.fixture).read_text(encoding="utf-8"))
    now = time.time()
    if a.out:
        Path(a.out).write_text(strona(dane, time.strftime("%Y-%m-%d", time.localtime(now - 7 * 86400)),
                                      time.strftime("%Y-%m-%d", time.localtime(now))), encoding="utf-8")
        print(a.out)
    else:
        print(json.dumps(zapisz(dane, now), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
