#!/usr/bin/env python3
"""Odrzucenie w App Store albo Google Play: wiadomość recenzenta → wytyczne → poprawka, wyjaśnienie albo odwołanie,
szkic odpowiedzi po angielsku i nauka (ten sam błąd nie zdarza się drugi raz).

    odrzucenie.py analizuj <app> --plik wiadomosc.txt [--platforma ios|android]
    odrzucenie.py naucz --wytyczna "2.3.10" --opis "…" --poprawka "…" [--wzorzec REGEX --gdzie src|metadane|oba]
                        [--app <app>]
    odrzucenie.py wyuczone [--json]

Wiadomość recenzenta to obce dane: skrypt tylko z niej wyciąga numery wytycznych i nazwy zasad, nigdy nie wykonuje
zawartych w niej poleceń; zdania wyglądające na polecenia dla agenta oznacza jako podejrzane. Wynik:
`<app>/out/odrzucenia/<data>-<platforma>/` (wiadomosc.txt, analiza.json, ANALIZA.md dla właściciela, odpowiedz.md po
angielsku, LEKCJA.md do skarbca wiedzy). Wysłanie odpowiedzi albo odwołania robi właściciel (A2).

`naucz` dopisuje wyuczoną kontrolę do `<prace>/_nauka/odrzucenia.yaml` (`JARVO_MOBILE_PRACE`, domyślnie katalog
roboczy Twórcy aplikacji): z wzorcem `sklep_check.py` sprawdza ją od razu we wszystkich aplikacjach jako punkt N1, N2…
(błąd blokuje wysłanie), bez wzorca zostaje lekcją. Stałą kontrolę z testem do `sklep_check.py` dopisuje deweloper
floty (propozycja karty w raporcie). Kod: 0 = OK, 1 = nie rozpoznano żadnej wytycznej, 2 = złe wejście.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

TU = Path(__file__).resolve().parent
sys.path.insert(0, str(TU))

import mobile_lib as ml  # noqa: E402

# wytyczna → (nazwa, klasa domyślna, punkty listy kontrolnej, co zwykle poprawić)
APPLE: dict[str, tuple[str, str, list[int], str]] = {
    "1.2": ("treści użytkowników", "poprawka", [31], "regulamin przed publikacją, filtr, „Zgłoś” i „Zablokuj”, kontakt"),
    "2.1": ("kompletność aplikacji", "poprawka", [26, 27, 25, 33], "awaria, tekst zastępczy, martwy link, wyłączony backend albo konto demo"),
    "2.3": ("dokładne metadane", "poprawka", [37, 39, 41], "zrzuty i opis zgodne z aplikacją"),
    "2.3.1": ("ukryte funkcje i ogólne opisy", "poprawka", [44], "konkretne „Co nowego” i notatki, bez ukrytych funkcji"),
    "2.3.3": ("zrzuty", "poprawka", [36, 37], "zrzuty z aplikacją w użyciu, nie sam ekran startowy ani logowanie"),
    "2.3.7": ("nazwa i słowa kluczowe", "poprawka", [39, 40], "bez upychania słów, nazw konkurencji i cen"),
    "2.3.10": ("obce platformy", "poprawka", [37, 41], "bez „Android”, „Google Play” i innych platform w karcie i na zrzutach iOS"),
    "2.5.2": ("pobierany kod", "poprawka", [32], "aktualizacje bez recenzji tylko z poprawkami; nowe funkcje w nowej wersji"),
    "2.5.4": ("praca w tle", "poprawka", [15], "UIBackgroundModes tylko używane"),
    "2.5.5": ("sieć IPv6", "poprawka", [33], "backend osiągalny w sieci tylko z IPv6 (rekord AAAA albo NAT64)"),
    "3.1.1": ("zakupy w aplikacji", "poprawka", [30], "treści cyfrowe przez zakupy w aplikacji"),
    "3.1.3": ("inne metody płatności", "wyjaśnienie", [30], "towary fizyczne i usługi poza zakupami w aplikacji: wyjaśnić w notatkach"),
    "4.0": ("design", "poprawka", [28], "wygląd i nawigacja według platformy"),
    "4.1": ("podróbki", "poprawka", [26], "własna ikona, nazwa i marka"),
    "4.2": ("minimalna funkcjonalność", "poprawka", [28], "funkcje natywne zamiast okna na stronę (natywna-czy-pwa)"),
    "4.2.2": ("strona w aplikacji", "poprawka", [28], "mniej WebView, więcej funkcji natywnych"),
    "4.2.6": ("aplikacje z szablonu", "wyjaśnienie", [1, 29], "wysyła właściciel ze swojego konta; własny wygląd i treści"),
    "4.3": ("spam", "poprawka", [29], "jedna aplikacja zamiast kopii; własne treści i wygląd"),
    "4.8": ("logowanie", "poprawka", [23], "Zaloguj się przez Apple obok Google i Facebooka"),
    "5.1.1": ("zbieranie danych", "poprawka", [11, 12, 13, 20, 22, 24], "opisy uprawnień, polityka, usuwanie konta, katalog bez logowania"),
    "5.1.2": ("użycie danych", "poprawka", [17, 18, 19], "zgoda przed AI, ATT przy śledzeniu, aplikacja działa bez zgód"),
    "5.6.2": ("tożsamość wydawcy", "wyjaśnienie", [3], "dokumenty podmiotu w branży regulowanej"),
}
GOOGLE: dict[str, tuple[str, str, list[int], str]] = {
    r"broken functionality|niedziałając": ("niedziałająca aplikacja", "poprawka", [26, 27, 33], "awarie, ładowanie, raport przedpremierowy"),
    r"minimum functionality|ograniczon\w* funkcjonaln": ("ograniczona funkcjonalność", "poprawka", [28], "funkcje natywne"),
    r"\bspam\b|repetitive content|powtarzaln": ("spam", "poprawka", [29], "jedna aplikacja, własne treści"),
    r"metadata|metadan|store listing|karta sklepu": ("metadane", "poprawka", [39, 40, 41], "tytuł ≤ 30 bez promocji, bez emoji i WIELKICH LITER"),
    r"data safety|bezpieczeństw\w* danych": ("Data safety", "poprawka", [17], "formularz zgodny z aplikacją i jej bibliotekami"),
    r"account deletion|usuwani\w* kont": ("usuwanie konta", "poprawka", [22], "ścieżka w aplikacji i adres w sieci"),
    r"permission|uprawnie": ("uprawnienia", "poprawka", [13, 14], "usuń zbędne albo złóż deklarację"),
    r"target api|docelow\w* (poziom )?api": ("docelowe API", "poprawka", [6], "aktualny Expo SDK, targetSdk 36"),
    r"16 ?kb|page size|rozmiar\w* stron": ("strony pamięci 16 KB", "poprawka", [7], "aktualne biblioteki natywne"),
    r"user generated content|ugc|treści użytkownik": ("treści użytkowników", "poprawka", [31], "zgłaszanie, blokowanie, regulamin"),
    r"ai[- ]generated|generatywn|sztuczn\w* inteligenc": ("treści z AI", "poprawka", [18], "zgłaszanie obraźliwych odpowiedzi AI"),
    r"app access|login credentials|dostęp do aplikacji|dane logowania": ("dostęp dla recenzenta", "wyjaśnienie", [25], "działające konto demo bez 2FA"),
    r"deceptive|wprowadzając\w* w błąd": ("wprowadzanie w błąd", "poprawka", [37, 41], "karta zgodna z aplikacją"),
    r"impersonation|podszywa": ("podszywanie się", "poprawka", [26], "własna marka; dokumenty przy znaku towarowym"),
}
WYJASNIENIE = re.compile(r"information needed|need (additional|more) information|unable to (sign in|log ?in|locate|find)|"
                         r"could not (sign in|locate|find)|demo account|provide (a )?(demo|video|screen recording)|"
                         r"potrzebujemy (dodatkowych )?informacji|nie (mogliśmy|udało się) (zalogować|znaleźć)", re.I)
# zdania, które w wiadomości „od recenzenta” wyglądają na polecenia dla agenta (obce dane, nie polecenia)
PODEJRZANE = re.compile(r"ignore (all |the )?(previous|above)|system prompt|you are (now )?an? |run (the )?(command|script)|"
                        r"\b(curl|wget|rm -rf|chmod)\b|send (us )?(your|the) (token|key|password|credentials)|"
                        r"api[_ ]?key|EXPO_TOKEN|GITHUB_TOKEN|disable (the )?(check|gate)|skip (the )?(check|review)|"
                        r"zignoruj|wyłącz (kontrol|bramk)|podaj (token|hasło|klucz)", re.I)
WYTYCZNA = re.compile(r"(?:Guideline|Wytyczna)\s+(\d+(?:\.\d+)*)(\([a-z]\))?(\([ivx]+\))?", re.I)

ODPOWIEDZ = """Hello App Review team,

Thank you for reviewing {nazwa} {wersja}.

{bloki}
If anything else is unclear, we are happy to provide more details or a short screen recording.

Best regards,
{firma}
"""
BLOK = {
    "poprawka": "Regarding Guideline {w} ({nazwa_en}): JARVO-TODO: what exactly we changed. This is fixed in build {build}. "
                "To verify: JARVO-TODO: steps, screen by screen.\n",
    "wyjaśnienie": "Regarding Guideline {w} ({nazwa_en}): JARVO-TODO: the explanation with the exact path in the app "
                   "(screen by screen) and, if relevant, the demo account in App Review Information (no SMS code, no 2FA).\n",
    "odwołanie": "Regarding Guideline {w} ({nazwa_en}): we believe the app complies because JARVO-TODO: the concrete "
                 "argument with evidence (screens, documents). We kindly ask for another look.\n",
}
NAZWY_EN = {"1.2": "User-Generated Content", "2.1": "App Completeness", "2.3": "Accurate Metadata", "2.3.1": "Accurate Metadata",
            "2.3.3": "Accurate Metadata - Screenshots", "2.3.7": "Accurate Metadata - Name and Keywords",
            "2.3.10": "Accurate Metadata - Other Platforms", "2.5.2": "Software Requirements", "2.5.4": "Background Modes",
            "2.5.5": "IPv6 Networks", "3.1.1": "In-App Purchase", "3.1.3": "Other Purchase Methods", "4.0": "Design",
            "4.1": "Copycats", "4.2": "Minimum Functionality", "4.2.2": "Minimum Functionality", "4.2.6": "Template Apps",
            "4.3": "Spam", "4.8": "Login Services", "5.1.1": "Data Collection and Storage", "5.1.2": "Data Use and Sharing",
            "5.6.2": "Developer Identity"}


def _prace() -> Path:
    return Path(os.environ.get("JARVO_MOBILE_PRACE", "/opt/data/jarvo/workspaces/jarvo-mobile"))


def plik_nauki() -> Path:
    return _prace() / "_nauka" / "odrzucenia.yaml"


def wyuczone() -> list[dict]:
    p = plik_nauki()
    if not p.exists():
        return []
    import yaml
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("kontrole") or []


def _apple(numer: str) -> tuple[str, tuple] | None:
    """Najdłuższy znany prefiks numeru (2.3.10 → 2.3.10, 5.1.1(v) → 5.1.1, 2.1.0 → 2.1)."""
    czesci = numer.split(".")
    for n in range(len(czesci), 0, -1):
        k = ".".join(czesci[:n])
        if k in APPLE:
            return k, APPLE[k]
    return None


def analizuj(tekst: str, platforma: str = "") -> dict:
    platforma = platforma or ("ios" if re.search(r"Guideline\s+\d|App Review|App Store", tekst) else "android")
    znalezione, widziane = [], set()
    if platforma == "ios":
        for m in WYTYCZNA.finditer(tekst):
            numer = m.group(1) + (m.group(2) or "") + (m.group(3) or "")
            t = _apple(m.group(1))
            if not t or numer in widziane:
                continue
            widziane.add(numer)
            klucz, (nazwa, klasa, punkty, co) = t
            nastepna = WYTYCZNA.search(tekst, m.end())
            fragment = tekst[m.start():min(nastepna.start() if nastepna else len(tekst), m.start() + 700)]
            znalezione.append({"wytyczna": numer, "klucz": klucz, "nazwa": nazwa, "klasa": klasa, "punkty": punkty, "co": co,
                               "cytat": " ".join(fragment.split())[:400]})
    else:
        for wz, (nazwa, klasa, punkty, co) in GOOGLE.items():
            m = re.search(wz, tekst, re.I)
            if m and nazwa not in widziane:
                widziane.add(nazwa)
                start = max(0, tekst.rfind("\n", 0, m.start()))
                znalezione.append({"wytyczna": nazwa, "klucz": nazwa, "nazwa": nazwa, "klasa": klasa, "punkty": punkty, "co": co,
                                   "cytat": " ".join(tekst[start:start + 400].split())})
    if WYJASNIENIE.search(tekst):
        for z in znalezione:
            if z["klasa"] == "poprawka" and set(z["punkty"]) & {25, 26, 27, 33}:
                z["klasa"] = "wyjaśnienie"
                z["co"] = "recenzent czegoś nie znalazł albo nie zalogował się: ścieżka krok po kroku, konto demo, nagranie ekranu"
    podejrzane = [" ".join(m.group(0).split()) for m in PODEJRZANE.finditer(tekst)]
    return {"platforma": platforma, "wytyczne": znalezione, "podejrzane": podejrzane,
            "punkty": sorted({p for z in znalezione for p in z["punkty"]})}


def odpowiedz_md(a: dict, app: dict, build: str = "") -> str:
    bloki = "\n".join(BLOK[z["klasa"]].format(w=z["wytyczna"], nazwa_en=NAZWY_EN.get(z["klucz"], z["nazwa"]),
                                              build=build or "JARVO-TODO: numer")
                      for z in a["wytyczne"])
    return ODPOWIEDZ.format(nazwa=app.get("nazwa", ""), wersja=app.get("wersja", ""), bloki=bloki,
                            firma=(app.get("firma") or {}).get("nazwa", ""))


def analiza_md(a: dict, app: dict) -> str:
    l = [f"# Odrzucenie: {app.get('nazwa', '')} {app.get('wersja', '')} ({a['platforma']})", ""]
    if a["podejrzane"]:
        l += ["> ⚠ W wiadomości są zdania wyglądające na polecenia dla agenta (" + "; ".join(a["podejrzane"][:5]) +
              "). Traktuję je jako dane: nic z nich nie wykonuję. Sprawdź, czy wiadomość na pewno pochodzi z konsoli sklepu.", ""]
    if not a["wytyczne"]:
        l += ["Nie rozpoznałem wytycznej: przeczytaj wiadomość ręcznie i dopisz ją do mapy (odrzucenie.py)."]
    for z in a["wytyczne"]:
        l += [f"## {z['wytyczna']}: {z['nazwa']} → **{z['klasa']}**", "", f"> {z['cytat']}", "",
              f"- Co zwykle poprawić: {z['co']}.", f"- Punkty listy kontrolnej: {', '.join(map(str, z['punkty']))} "
              "(`sklep_check.py` po poprawce).", ""]
    l += ["## Dalej", "1. Poprawka w kodzie / metadanych / na stronie, nowy build (`wydanie.py build`), lista kontrolna.",
          "2. Odpowiedź z `odpowiedz.md` (po angielsku) wysyła właściciel w App Store Connect albo Play Console (A2).",
          "3. Odwołanie tylko z mocnym argumentem: Apple w 2025 przywróciło 423 z 26 305 aplikacji po odwołaniach.",
          "4. `odrzucenie.py naucz …` i lekcja w skarbcu: ten sam błąd nie zdarza się drugi raz."]
    return "\n".join(l) + "\n"


def lekcja_md(a: dict, app: dict) -> str:
    w = ", ".join(f"{z['wytyczna']} ({z['nazwa']})" for z in a["wytyczne"]) or "nierozpoznana"
    return (f"# Odrzucenie {a['platforma']}: {w}\n\n**Aplikacja {app.get('nazwa', '')} {app.get('wersja', '')} odrzucona za {w}; "
            f"dotyczy punktów listy {', '.join(map(str, a['punkty'])) or '—'}.**\n\nCytat: "
            f"{(a['wytyczne'][0]['cytat'] if a['wytyczne'] else '')[:300]}\n\nPoprawka: JARVO-TODO (co zmieniono i w którym buildzie).\n"
            "Wniosek dla floty: JARVO-TODO (jaka kontrola wyłapie to wcześniej).\n")


def analizuj_plik(kat: Path, plik: Path, platforma: str = "") -> dict:
    app = json.loads((kat / "jarvo.app.json").read_text(encoding="utf-8")) if (kat / "jarvo.app.json").exists() else {}
    tekst = plik.read_text(encoding="utf-8", errors="replace")
    if len(tekst) > 200_000:
        raise SystemExit("wiadomość dłuższa niż 200 tys. znaków: to nie jest wiadomość recenzenta")
    a = analizuj(tekst, platforma)
    out = kat / "out" / "odrzucenia" / f"{ml.DZIS.isoformat()}-{a['platforma']}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "wiadomosc.txt").write_text(tekst, encoding="utf-8")
    build = ""
    buildy = kat / "out" / "wydanie" / "buildy.json"
    if buildy.exists():
        b = next((x for x in json.loads(buildy.read_text(encoding="utf-8")).get("buildy", [])
                  if str(x.get("platforma")).lower() == a["platforma"] and x.get("numer")), None)
        build = str(b["numer"]) if b else ""
    ml.zapisz(out / "analiza.json", json.dumps(a, ensure_ascii=False, indent=2))
    ml.zapisz(out / "ANALIZA.md", analiza_md(a, app))
    ml.zapisz(out / "odpowiedz.md", odpowiedz_md(a, app, build))
    ml.zapisz(out / "LEKCJA.md", lekcja_md(a, app))
    return {**a, "katalog": str(out.relative_to(kat))}


def naucz(wytyczna: str, opis: str, poprawka: str, wzorzec: str = "", gdzie: str = "oba", app: str = "") -> dict:
    if len(opis.strip()) < 10 or len(poprawka.strip()) < 10:
        raise SystemExit("opis i poprawka: konkretnie, co najmniej 10 znaków")
    if wzorzec:
        try:
            re.compile(wzorzec)
        except re.error as e:
            raise SystemExit(f"wzorzec nie jest poprawnym wyrażeniem: {e}") from e
        if re.search(wzorzec, ""):
            raise SystemExit("wzorzec pasuje do pustego tekstu (zablokowałby każdą aplikację)")
    import yaml
    p = plik_nauki()
    p.parent.mkdir(parents=True, exist_ok=True)
    dane = (yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else None) or {"kontrole": []}
    nr = f"N{len(dane['kontrole']) + 1}"
    wpis = {"id": nr, "data": ml.DZIS.isoformat(), "wytyczna": wytyczna, "opis": opis.strip(), "poprawka": poprawka.strip(),
            "wzorzec": wzorzec, "gdzie": gdzie, "zrodlo": app}
    dane["kontrole"].append(wpis)
    naglowek = ("# Kontrole wyuczone z odrzuceń (odrzucenie.py naucz). sklep_check.py stosuje je jako punkty N1, N2…;\n"
                "# stała kontrola z testem trafia do sklep_check.py przez dewelopera floty.\n")
    p.write_text(naglowek + yaml.safe_dump(dane, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return wpis


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a_ = sub.add_parser("analizuj")
    a_.add_argument("app")
    a_.add_argument("--plik", required=True)
    a_.add_argument("--platforma", choices=["ios", "android"], default="")
    n = sub.add_parser("naucz")
    n.add_argument("--wytyczna", required=True)
    n.add_argument("--opis", required=True)
    n.add_argument("--poprawka", required=True)
    n.add_argument("--wzorzec", default="")
    n.add_argument("--gdzie", choices=["src", "metadane", "oba"], default="oba")
    n.add_argument("--app", default="")
    w = sub.add_parser("wyuczone")
    w.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "analizuj":
        kat = Path(a.app).resolve()
        if not Path(a.plik).exists():
            print(f"✗ brak pliku {a.plik}", file=sys.stderr)
            return 2
        r = analizuj_plik(kat, Path(a.plik), a.platforma)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r["wytyczne"] else 1
    if a.cmd == "naucz":
        print(json.dumps(naucz(a.wytyczna, a.opis, a.poprawka, a.wzorzec, a.gdzie, a.app), ensure_ascii=False, indent=2))
        return 0
    k = wyuczone()
    print(json.dumps(k, ensure_ascii=False, indent=2) if a.json else
          "\n".join(f"{x['id']} {x['wytyczna']}: {x['opis']}" + (f"  [/{x['wzorzec']}/ w {x['gdzie']}]" if x.get("wzorzec") else "")
                    for x in k) or "brak wyuczonych kontroli")
    return 0


if __name__ == "__main__":
    sys.exit(main())
