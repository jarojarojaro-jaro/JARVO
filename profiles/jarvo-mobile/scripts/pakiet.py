#!/usr/bin/env python3
"""Pakiet do sklepów: metadane, grafiki i zrzuty, które sprawdza potem `sklep_check.py`.

    pakiet.py szkic <app> [--nadpisz]               # store.config.json (EAS Metadata), karta Google, scenariusz zrzutów
    pakiet.py grafiki <app>                         # Google: ikona 512×512 i grafika promocyjna 1024×500
    pakiet.py zrzuty <app> [--zrodlo web|android|ios] [--scenariusz out/sklep/zrzuty.yaml]

Szkic wypełnia to, co wiadomo z `jarvo.app.json` (nazwa, opis, firma, adresy, konta), a pola na teksty sprzedażowe
(podtytuł, opis, słowa kluczowe, nagłówki kadrów) zostawia ze znacznikiem `JARVO-TODO`, który blokuje listę kontrolną,
dopóki ich nie napisze agent albo Studio. Istniejących plików nie nadpisuje bez `--nadpisz` (dopisuje brakujące pola).

Zrzuty: scenariusz 2–8 kadrów (trasa + nagłówek z korzyścią) → ekrany aplikacji ze źródła → kompozycja HTML
(kolor marki, nagłówek, ekran w ramce) w dokładnych wymiarach, PNG bez alfy:
- `out/sklep/apple/pl-PL/ios-6.9/NN.png` 1320×2868 (iPhone 6,9″), `ipad-13/NN.png` 2064×2752 przy tablecie;
- `out/sklep/google/pl-PL/images/phoneScreenshots/NN.png` 1080×1920.
Źródła ekranów: `web` (eksport z `aplikacja.py podglad`, przybliżenie do szkicu karty), `android` (telefon testowy
floty przez adb, tryb demo paska stanu, wymaga zainstalowanego builda), `ios` (artefakt `ios_ci.py`: symulator
z paskiem stanu 9:41). Do wysłania: android / ios. Opis kadrów i źródła: `out/sklep/zrzuty.json`.
Galeria do obejrzenia w podglądzie HQ: `out/sklep/index.html` (`jarvo_link.py <app>/out/sklep`; odświeża ją też
`sklep_check.py`).
Kod: 0 = OK, 1 = błąd, 2 = złe wejście.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TU = Path(__file__).resolve().parent
sys.path.insert(0, str(TU))

import aplikacja  # noqa: E402
import mobile_lib as ml  # noqa: E402

TODO = "JARVO-TODO"
CELE = {   # cel → (katalog względem out/sklep, szerokość, wysokość, źródło web, proporcje ekranu w ramce)
    "ios-6.9": ("apple/pl-PL/ios-6.9", 1320, 2868, "iphone"),
    "ipad-13": ("apple/pl-PL/ipad-13", 2064, 2752, "ipad"),
    "google": ("google/pl-PL/images/phoneScreenshots", 1080, 1920, "pixel"),
}
POMIN_TRASY = {"prywatnosc", "usun-konto", "+not-found", "kontakt", "_layout"}

SCENARIUSZ = """# Kadry do sklepów (pakiet.py zrzuty): 2–8, kolejność jak w karcie. Każdy kadr = jedna korzyść dla klienta,
# z ekranem, który ją pokazuje w użyciu (nie logowanie, nie ekran startowy: Apple 2.3.3). Nagłówek ≤ 40 znaków,
# po polsku, od Studia; podtytuł opcjonalny. Dane na ekranach: realistyczne, bez danych prawdziwych klientów.
motyw: jasny
kadry:
{kadry}"""

NOTATKI = """This app is published by {firma} ({strona}) for its own customers in Poland. The interface is in Polish.

Main features:
- {TODO}: feature 1 (what the customer does and on which screen)
- {TODO}: feature 2

How to test:
1. Open the app. The home screen shows {TODO}: what is visible without an account.
2. {TODO}: the path to the main feature, screen by screen.
{konto}
Updates: we use EAS Update only for bug fixes. New features ship in new App Store versions.
Contact for the review team: {email}, {telefon}."""
KONTO_TAK = """3. Sign in with the demo account from the App Review Information fields (no SMS code, no 2FA).
4. Account deletion: More (Więcej) → Delete account (Usuń konto); the account and its data are removed.
"""
KONTO_NIE = "The app has no user accounts; everything is available without signing in.\n"


class Blad(Exception):
    pass


def _app(kat: Path) -> dict:
    p = kat / "jarvo.app.json"
    if not p.exists():
        raise Blad(f"{kat}: brak jarvo.app.json (to nie aplikacja z szablonu JARVO)")
    return json.loads(p.read_text(encoding="utf-8"))


def _uzupelnij(stare, nowe):
    """Dopisuje brakujące klucze (rekurencyjnie), istniejących wartości nie rusza."""
    if isinstance(stare, dict) and isinstance(nowe, dict):
        out = dict(stare)
        for k, v in nowe.items():
            out[k] = _uzupelnij(stare[k], v) if k in stare else v
        return out
    return stare


def trasy_aplikacji(kat: Path) -> list[str]:
    app_dir = kat / "src" / "app"
    out = []
    for p in sorted(app_dir.rglob("*.tsx")) if app_dir.exists() else []:
        czesci = [c for c in p.relative_to(app_dir).with_suffix("").parts if not (c.startswith("(") and c.endswith(")"))]
        if not czesci or czesci[-1] in POMIN_TRASY or any(c.startswith(("_", "[")) for c in czesci):
            continue
        if czesci[-1] == "index":
            czesci = czesci[:-1]
        trasa = "/" + "/".join(czesci)
        if trasa not in out:
            out.append(trasa)
    return sorted(out, key=lambda t: (t != "/", t))


def szkic(kat: Path, nadpisz: bool = False) -> dict:
    app = _app(kat)
    firma, konta = app.get("firma") or {}, bool((app.get("funkcje") or {}).get("konta"))
    nazwa, opis = app.get("nazwa") or "", app.get("opis") or ""
    rok = ml.DZIS.year
    store = {
        "configVersion": 0,
        "apple": {
            "copyright": f"{rok} {firma.get('nazwa', '')}".strip(),
            "info": {"pl-PL": {
                "title": nazwa[:30],
                "subtitle": f"{TODO}: korzyść w ≤ 30 znakach",
                "description": f"{opis}\n\n{TODO}: 3–5 akapitów o tym, co klient załatwi w aplikacji (bez cen, rabatów i superlatyw).",
                "keywords": [TODO],
                "promoText": "",
                "releaseNotes": f"Pierwsza wersja aplikacji {nazwa}.",
                "marketingUrl": firma.get("strona", ""),
                "supportUrl": firma.get("strona", ""),
                "privacyPolicyUrl": firma.get("prywatnosc_url", ""),
            }},
            "review": {
                "firstName": "", "lastName": "", "email": firma.get("email", ""), "phone": firma.get("telefon", ""),
                "demoRequired": konta, **({"demoUsername": ""} if konta else {}),
                "notes": NOTATKI.format(firma=firma.get("nazwa", ""), strona=firma.get("strona", ""), TODO=TODO,
                                        konto=KONTO_TAK if konta else KONTO_NIE, email=firma.get("email", ""),
                                        telefon=firma.get("telefon", "")),
            },
        },
    }
    pliki = []
    p = kat / "store.config.json"
    stary = json.loads(p.read_text(encoding="utf-8")) if p.exists() and not nadpisz else None
    p.write_text(json.dumps(_uzupelnij(stary, store) if stary else store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pliki.append(p)
    g = kat / "out" / "sklep" / "google" / "pl-PL"
    for n, v in (("title.txt", nazwa[:30]),
                 ("short_description.txt", f"{TODO}: korzyść w ≤ 80 znakach" if len(opis) > 80 else opis),
                 ("full_description.txt", f"{opis}\n\n{TODO}: pełny opis do 4000 znaków (bez cen, rabatów i superlatyw).")):
        if nadpisz or not (g / n).exists():
            pliki.append(ml.zapisz(g / n, v + "\n"))
    sc = kat / "out" / "sklep" / "zrzuty.yaml"
    if nadpisz or not sc.exists():
        trasy = trasy_aplikacji(kat)[:8]
        kadry = "\n".join(f"  - trasa: {t}\n    naglowek: \"{TODO}: korzyść ekranu {t}\"" for t in trasy)
        pliki.append(ml.zapisz(sc, SCENARIUSZ.format(kadry=kadry) + "\n"))
    todo = sum(f.read_text(encoding="utf-8").count(TODO) for f in pliki)
    return {"pliki": [str(f.relative_to(kat)) for f in pliki], "do_uzupelnienia": todo,
            "dalej": "teksty sprzedażowe (Studio: opisy, słowa kluczowe, nagłówki kadrów), konto demo, potem `pakiet.py zrzuty`"}


# ------------------------------------------------------------------ kompozycja kadrów

STYL = """<!doctype html><html lang="pl"><meta charset="utf-8"><style>
html,body{{margin:0;width:{w}px;height:{h}px;overflow:hidden}}
body{{background:linear-gradient(170deg,{tlo} 0%,{tlo2} 100%);font-family:Inter,'Inter Display',system-ui,sans-serif;
  color:{tekst};display:flex;flex-direction:column;align-items:center}}
.nag{{margin-top:{gora}px;width:{szer_tekstu}px;text-align:center}}
h1{{font-size:{f1}px;line-height:1.12;font-weight:800;letter-spacing:-.01em;margin:0;text-wrap:balance}}
p{{font-size:{f2}px;line-height:1.3;font-weight:500;opacity:.88;margin:{odstep}px 0 0;text-wrap:balance}}
.ramka{{position:absolute;left:{rx}px;top:{ry}px;width:{rw}px;height:{rh}px;box-sizing:border-box;background:#0B0B0D;
  border-radius:{rr}px;padding:{bz}px;box-shadow:0 {cien}px {cien2}px rgba(0,0,0,.28)}}
.ekran{{width:100%;height:100%;border-radius:{er}px;overflow:hidden;background:#fff;display:flex;flex-direction:column}}
.pasek{{height:{ph}px;flex:none;display:{pasek};align-items:center;justify-content:space-between;padding:0 {pp}px;
  font:600 {pf}px Inter,system-ui,sans-serif;box-sizing:border-box}}
.ekran img{{width:100%;height:auto;display:block}}
</style>
<script>window.KADR_GOTOWY=false;</script>
<body><div class="nag"><h1>{naglowek}</h1>{podtytul}</div>
<div class="ramka"><div class="ekran"><div class="pasek" id="pasek"><span>9:41</span>
<svg width="{bw}" height="{bh}" viewBox="0 0 68 24" fill="currentColor" aria-hidden="true"><rect x="0" y="14" width="5" height="8" rx="1"/>
<rect x="8" y="10" width="5" height="12" rx="1"/><rect x="16" y="6" width="5" height="16" rx="1"/><rect x="24" y="2" width="5" height="20" rx="1"/>
<rect x="36" y="3" width="28" height="18" rx="4" fill="none" stroke="currentColor" stroke-width="2"/><rect x="39" y="6" width="22" height="12" rx="2"/>
<rect x="65" y="9" width="3" height="6" rx="1"/></svg></div><img id="zrzut" src="{obraz}"></div></div>
<script>
const img=document.getElementById('zrzut'), pasek=document.getElementById('pasek');
function gotowe(){{try{{const c=document.createElement('canvas');c.width=img.naturalWidth;c.height=4;const x=c.getContext('2d');
  x.drawImage(img,0,0);const d=x.getImageData(Math.floor(img.naturalWidth/2),1,1,1).data;
  pasek.style.background=`rgb(${{d[0]}},${{d[1]}},${{d[2]}})`;
  pasek.style.color=(0.299*d[0]+0.587*d[1]+0.114*d[2])>150?'#0B0B0D':'#FFFFFF';}}catch(e){{}}
  window.KADR_GOTOWY=true;}}
img.complete?gotowe():img.addEventListener('load',gotowe);
</script></body></html>"""


def _ciemniej(hex_: str, o: float = 0.22) -> str:
    r, g, b = (int(hex_[i:i + 2], 16) for i in (1, 3, 5))
    return "#{:02X}{:02X}{:02X}".format(*(max(0, int(c * (1 - o))) for c in (r, g, b)))


SIEROTKI = re.compile(r"(?<!\S)([aiouwzAIOUWZ]|[a-zA-Z]{1}\.)\s+")


def bez_sierotek(t: str) -> str:
    """Polska typografia: jednoliterowe spójniki i przyimki (w, z, i, a, o, u) nie zostają na końcu linii."""
    return SIEROTKI.sub(lambda m: m.group(1) + "\u00a0", t)


def html_kadru(cel: str, obraz: Path, naglowek: str, podtytul: str, kolory: dict, pasek: bool) -> str:
    _, w, h, _ = CELE[cel]
    zr = ml.obraz(obraz)
    proporcja = (zr["wys"] / zr["szer"]) if zr["szer"] else 2.17
    skala = w / 1320
    gora, f1, f2 = int(150 * skala), int(92 * skala), int(48 * skala)
    if cel == "ipad-13":
        gora, f1, f2 = 150, 104, 54
    if cel == "google":
        gora, f1, f2 = 110, 66, 36
    naglowek_h = gora + int(f1 * 1.12 * 2) + (int(f2 * 1.3) + int(20 * skala) if podtytul else 0) + int(70 * skala)
    rh_max = h - naglowek_h - int(70 * skala)
    # ekran w całości (bez kadrowania paska zakładek): ramka = pasek stanu (tylko źródło web) + cały zrzut
    pasek_wzgl = 0.105 if pasek else 0.0
    rw = int(w * (0.76 if cel != "ipad-13" else 0.74))
    for _ in range(40):
        bz = max(10, int(rw * 0.026))
        rw_ekran = rw - 2 * bz
        rh = int(rw_ekran * (proporcja + pasek_wzgl)) + 2 * bz
        if rh <= rh_max:
            break
        rw = int(rw * 0.97)
    rx, ry = (w - rw) // 2, naglowek_h + max(0, (rh_max - rh) // 2)
    ph = int(rw_ekran * pasek_wzgl)
    return STYL.format(
        w=w, h=h, tlo=kolory["glowny"], tlo2=_ciemniej(kolory["glowny"]), tekst=kolory["naGlownym"], gora=gora,
        szer_tekstu=int(w * 0.86), f1=f1, f2=f2, odstep=int(20 * skala), rx=rx, ry=ry, rw=rw, rh=rh,
        rr=int(rw * (0.12 if cel != "ipad-13" else 0.05)), bz=bz, er=int(rw * (0.10 if cel != "ipad-13" else 0.04)),
        cien=int(30 * skala), cien2=int(80 * skala), ph=ph, pasek="flex" if pasek else "none", pp=int(rw_ekran * 0.07),
        pf=int(rw_ekran * 0.042), bw=int(rw_ekran * 0.17), bh=int(rw_ekran * 0.06), obraz=obraz.as_uri(),
        naglowek=html.escape(bez_sierotek(naglowek)),
        podtytul=f"<p>{html.escape(bez_sierotek(podtytul))}</p>" if podtytul else "")


def html_promo(app: dict, ikona: Path, kolory: dict) -> str:
    return f"""<!doctype html><html lang="pl"><meta charset="utf-8"><style>
html,body{{margin:0;width:1024px;height:500px;overflow:hidden}}
body{{background:linear-gradient(160deg,{kolory['glowny']},{_ciemniej(kolory['glowny'])});color:{kolory['naGlownym']};
  font-family:Inter,system-ui,sans-serif;display:flex;align-items:center;gap:56px;padding:0 84px;box-sizing:border-box}}
img{{width:208px;height:208px;border-radius:46px;box-shadow:0 0 0 6px rgba(255,255,255,.28),0 18px 50px rgba(0,0,0,.3);flex:none}}
h1{{font-size:64px;line-height:1.05;margin:0 0 18px;font-weight:800;text-wrap:balance}} p{{font-size:30px;line-height:1.3;margin:0;opacity:.9}}
</style><body><img src="{ikona.as_uri()}"><div><h1>{html.escape(app.get('nazwa', ''))}</h1>
<p style="text-wrap:balance">{html.escape(bez_sierotek((app.get('opis') or '')[:110]))}</p></div></body></html>"""


def _kadry_cjs(zadania: list[dict], katalog: Path) -> list[dict]:
    plik = katalog / "zadania.json"
    plik.write_text(json.dumps(zadania, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run(["node", str(TU / "kadry.cjs"), str(plik)], capture_output=True, text=True, timeout=900)
    if r.returncode not in (0, 1):
        raise Blad(f"kadry.cjs: {(r.stdout + r.stderr).strip()[-1200:]}")
    wyniki = json.loads(r.stdout.strip().splitlines()[-1])
    zle = [w for w in wyniki if not w["ok"]]
    if zle:
        raise Blad(f"kadry.cjs: złe wymiary albo alfa: {zle}")
    return wyniki


def grafiki(kat: Path) -> dict:
    app = _app(kat)
    ikona = kat / "assets" / "icon.png"
    if not ikona.exists():
        raise Blad("brak assets/icon.png: najpierw `aplikacja.py ustaw`")
    obr = kat / "out" / "sklep" / "google" / "pl-PL" / "images"
    robocze = kat / "out" / "sklep" / ".robocze"
    robocze.mkdir(parents=True, exist_ok=True)
    kolory = aplikacja.paleta(app.get("kolory", {}).get("glowny", "#2F5BEA"))["jasny"]
    (robocze / "promo.html").write_text(html_promo(app, ikona, kolory), encoding="utf-8")
    wyniki = _kadry_cjs([{"ikona": str(ikona), "out": str(obr / "icon.png"), "rozmiar": 512},
                         {"html": str(robocze / "promo.html"), "out": str(obr / "featureGraphic.png"), "w": 1024, "h": 500}], robocze)
    return {"pliki": [str(Path(w["out"]).relative_to(kat)) for w in wyniki]}


# ------------------------------------------------------------------ ekrany ze źródeł

def _nazwa(trasa: str) -> str:
    return "start" if trasa == "/" else re.sub(r"[^\w-]+", "_", trasa.lstrip("/"))


def ekrany_web(kat: Path, trasy: list[str], urzadzenia: list[str], motyw: str) -> dict[str, Path]:
    dist = kat / "dist-web"
    if not (dist / "index.html").exists():
        raise Blad("brak dist-web: najpierw `aplikacja.py podglad <app>` (eksport webowy)")
    m = re.search(r'src="(/[^"/]+)/_expo/', (dist / "index.html").read_text(encoding="utf-8", errors="replace"))
    prefiks = m.group(1) if m else ""
    surowe = kat / "out" / "sklep" / ".robocze" / "surowe"
    srv, port = aplikacja.serwer_spa(dist, prefiks)
    try:
        r = subprocess.run(["node", str(TU / "zrzuty.cjs"), f"http://127.0.0.1:{port}{prefiks}", str(surowe), "--trasy",
                            ",".join(trasy), "--urzadzenia", ",".join(urzadzenia), "--motywy", motyw],
                           capture_output=True, text=True, timeout=900)
    finally:
        srv.shutdown()
    if r.returncode not in (0, 1):
        raise Blad(f"zrzuty.cjs: {(r.stdout + r.stderr).strip()[-1200:]}")
    raport = json.loads((surowe / "zrzuty.json").read_text(encoding="utf-8"))
    puste = [w["trasa"] for w in raport["wyniki"] if w.get("pusty") or (w.get("status") or 200) >= 400]
    if puste:
        raise Blad(f"puste albo niedziałające ekrany: {', '.join(sorted(set(puste)))}")
    return {f"{u}:{t}": surowe / f"{u}-{motyw}" / f"{_nazwa(t)}.png" for u in urzadzenia for t in trasy}


def ekrany_android(kat: Path, trasy: list[str]) -> dict[str, Path]:
    import urzadzenie as ur
    app = _app(kat)
    adb = ur.Adb()
    adb.polacz()
    surowe = kat / "out" / "sklep" / ".robocze" / "surowe" / "android"
    pakiet, schemat = app.get("pakiet_android"), app.get("scheme")
    if pakiet not in adb.sh(f"pm list packages {pakiet}"):
        raise Blad(f"na telefonie testowym nie ma {pakiet}: zainstaluj build (`urzadzenie.py zainstaluj plik.apk`)")
    demo = ["settings put global sysui_demo_allowed 1",
            "am broadcast -a com.android.systemui.demo -e command enter",
            "am broadcast -a com.android.systemui.demo -e command clock -e hhmm 0941",
            "am broadcast -a com.android.systemui.demo -e command battery -e level 100 -e plugged false",
            "am broadcast -a com.android.systemui.demo -e command network -e wifi show -e level 4 -e mobile show -e datatype none -e level 4",
            "am broadcast -a com.android.systemui.demo -e command notifications -e visible false"]
    out = {}
    try:
        for p in demo:
            adb.sh(p)
        for t in trasy:
            adb.sh(f"am start -a android.intent.action.VIEW -d '{schemat}://{t.lstrip('/')}' {pakiet}")
            time.sleep(float(ur.CZEKAJ_S))
            out[f"android:{t}"] = ur.zrzut(adb, surowe / f"{_nazwa(t)}.png")
    finally:
        adb.sh("am broadcast -a com.android.systemui.demo -e command exit")
    return out


def ekrany_ios(kat: Path, trasy: list[str]) -> dict[str, Path]:
    art = kat / "out" / "jakosc" / "ios"
    out, braki = {}, []
    for t in trasy:
        p = art / f"jasny-{_nazwa(t)}.png"
        if p.exists():
            out[f"ios:{t}"] = p
        else:
            braki.append(t)
    if braki:
        raise Blad(f"artefakt iOS bez tras {', '.join(braki)}: `ios_ci.py uruchom <app> --repo … --tryb build --trasy …`")
    return out


def zrzuty(kat: Path, zrodlo: str = "web", scenariusz: Path | None = None) -> dict:
    app = _app(kat)
    sc_plik = scenariusz or kat / "out" / "sklep" / "zrzuty.yaml"
    if not sc_plik.exists():
        raise Blad(f"brak scenariusza {sc_plik}: `pakiet.py szkic <app>`")
    sc = aplikacja.wczytaj_yaml(sc_plik)
    kadry = sc.get("kadry") or []
    if not 2 <= len(kadry) <= 8:
        raise Blad(f"scenariusz: {len(kadry)} kadrów (2–8: Google wymaga co najmniej 2, App Store do 10)")
    trasy = [str(k.get("trasa", "/")) for k in kadry]
    motyw = sc.get("motyw", "jasny")
    tablet = bool(app.get("tablet"))
    cele = ["ios-6.9", "google"] + (["ipad-13"] if tablet else [])
    if zrodlo == "web":
        ekrany = ekrany_web(kat, trasy, ["iphone", "pixel"] + (["ipad"] if tablet else []), motyw)
        zrodla = {"ios-6.9": "iphone", "google": "pixel", "ipad-13": "ipad"}
    elif zrodlo == "android":
        ekrany, zrodla, cele = ekrany_android(kat, trasy), {"google": "android"}, ["google"]
    elif zrodlo == "ios":
        ekrany, zrodla, cele = ekrany_ios(kat, trasy), {"ios-6.9": "ios"}, ["ios-6.9"]
    else:
        raise Blad(f"nieznane źródło {zrodlo!r}: web, android albo ios")
    kolory = aplikacja.paleta(app.get("kolory", {}).get("glowny", "#2F5BEA"))["jasny"]
    sklep = kat / "out" / "sklep"
    robocze = sklep / ".robocze"
    zadania = []
    for cel in cele:
        katalog = sklep / CELE[cel][0]
        if katalog.exists():
            shutil.rmtree(katalog)                    # dokładnie te kadry, bez starych plików w zestawie
        for i, (k, t) in enumerate(zip(kadry, trasy), 1):
            obraz = ekrany[f"{zrodla[cel]}:{t}"]
            h = robocze / f"{cel}-{i:02d}.html"
            h.write_text(html_kadru(cel, obraz, str(k.get("naglowek") or ""), str(k.get("podtytul") or ""), kolory,
                                    pasek=zrodlo == "web"), encoding="utf-8")
            zadania.append({"html": str(h), "out": str(katalog / f"{i:02d}.png"), "w": CELE[cel][1], "h": CELE[cel][2]})
    wyniki = _kadry_cjs(zadania, robocze)
    meta = {"zrodlo": zrodlo, "motyw": motyw, "kadry": [{"trasa": t, "naglowek": k.get("naglowek"), "podtytul": k.get("podtytul")}
                                                        for k, t in zip(kadry, trasy)],
            "cele": {c: CELE[c][0] for c in cele}, "pliki": [str(Path(w["out"]).relative_to(kat)) for w in wyniki],
            "uwaga": "źródło web to przybliżenie do szkicu karty; do wysłania przechwyć z buildu (android / ios)" if zrodlo == "web" else ""}
    ml.zapisz(sklep / "zrzuty.json", json.dumps(meta, ensure_ascii=False, indent=2))
    return meta


def galeria(kat: Path) -> Path:
    """`out/sklep/index.html`: kadry, grafiki i podsumowanie listy kontrolnej do obejrzenia w podglądzie HQ
    (`jarvo_link.py <app>/out/sklep`). Same ścieżki względne, bez skryptów."""
    app = _app(kat)
    sklep = kat / "out" / "sklep"
    kolory = aplikacja.paleta(app.get("kolory", {}).get("glowny", "#2F5BEA"))["jasny"]
    sekcje = []
    for tytul, rel in (("App Store: iPhone 6,9″", CELE["ios-6.9"][0]), ("App Store: iPad 13″", CELE["ipad-13"][0]),
                       ("Google Play: telefon", CELE["google"][0])):
        pliki = sorted((sklep / rel).glob("*.png")) if (sklep / rel).exists() else []
        if pliki:
            sekcje.append(f"<h2>{tytul} <small>{len(pliki)}</small></h2><div class=rzad>" + "".join(
                f'<a href="{html.escape(f.relative_to(sklep).as_posix())}"><img src="{html.escape(f.relative_to(sklep).as_posix())}" '
                f'alt="kadr {f.stem}" loading=lazy></a>' for f in pliki) + "</div>")
    obr = sklep / "google" / "pl-PL" / "images"
    graf = [f for f in (obr / "featureGraphic.png", obr / "icon.png") if f.exists()]
    if graf:
        sekcje.append("<h2>Google Play: grafiki</h2><div class=rzad>" + "".join(
            f'<img class=graf src="{html.escape(f.relative_to(sklep).as_posix())}" alt="{f.stem}">' for f in graf) + "</div>")
    meta = json.loads((sklep / "zrzuty.json").read_text(encoding="utf-8")) if (sklep / "zrzuty.json").exists() else {}
    if meta.get("uwaga"):
        sekcje.insert(0, f"<p class=uwaga>{html.escape(meta['uwaga'])}</p>")
    check = json.loads((sklep / "check.json").read_text(encoding="utf-8")) if (sklep / "check.json").exists() else None
    if check:
        zle = [w for w in check["wyniki"] if w["stan"] == "blad"]
        sekcje.append(f"<h2>Lista kontrolna ({html.escape(check['data'])})</h2><p>{html.escape(check['podsumowanie'])}</p>"
                      + ("<ul>" + "".join(f"<li><b>{w['nr']}.</b> {html.escape(w['tytul'])}: {html.escape(w['dowod'][:220])}"
                                          f" <i>({html.escape(w['podstawa'])})</i></li>" for w in zle) + "</ul>" if zle else "")
                      + '<p><a href="CHECK.md">CHECK.md: wszystkie 44 punkty</a></p>')
    strona = f"""<!doctype html><html lang="pl"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Pakiet do sklepów: {html.escape(app.get('nazwa', ''))}</title><style>
body{{margin:0;font:16px/1.5 Inter,system-ui,sans-serif;background:#F4F5F7;color:#111318}}
header{{background:{kolory['glowny']};color:{kolory['naGlownym']};padding:28px 24px}} header h1{{margin:0;font-size:26px}}
main{{padding:8px 24px 40px;max-width:1200px}} h2{{font-size:19px;margin:28px 0 12px}} small{{color:#5B616E;font-weight:500}}
.rzad{{display:flex;gap:14px;overflow-x:auto;padding-bottom:8px}} .rzad img{{height:420px;border-radius:12px;
box-shadow:0 2px 10px rgba(0,0,0,.12)}} .rzad img.graf{{height:180px}} .uwaga{{background:#FFF4E5;border-left:4px solid #F79009;
padding:10px 14px;border-radius:6px}} li{{margin:6px 0}} a{{color:{aplikacja.paleta(app.get('kolory', {}).get('glowny', '#2F5BEA'))['jasny']['glowny']}}}
</style><header><h1>{html.escape(app.get('nazwa', ''))}: pakiet do sklepów</h1><div>{html.escape(app.get('opis', ''))}</div></header>
<main>{''.join(sekcje) or '<p>Pakiet jest pusty: pakiet.py szkic, grafiki, zrzuty.</p>'}</main></html>"""
    return ml.zapisz(sklep / "index.html", strona)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("szkic")
    s.add_argument("app")
    s.add_argument("--nadpisz", action="store_true")
    sub.add_parser("grafiki").add_argument("app")
    z = sub.add_parser("zrzuty")
    z.add_argument("app")
    z.add_argument("--zrodlo", default="web", choices=["web", "android", "ios"])
    z.add_argument("--scenariusz")
    a = ap.parse_args(argv)
    kat = Path(a.app).resolve()
    try:
        if a.cmd == "szkic":
            r = szkic(kat, a.nadpisz)
        elif a.cmd == "grafiki":
            r = grafiki(kat)
        else:
            r = zrzuty(kat, a.zrodlo, Path(a.scenariusz) if a.scenariusz else None)
    except Blad as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2 if "brak jarvo.app.json" in str(e) else 1
    if a.cmd != "szkic":
        r["galeria"] = str(galeria(kat).relative_to(kat))
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
