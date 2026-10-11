#!/usr/bin/env python3
"""Paczka kampanii do ręcznej publikacji: agent przygotowuje wszystko, człowiek wkleja i klika „Opublikuj”.

  paczka.py kampania.json -o out/paczka            # sprawdzenie + PUBLIKACJA.md, teksty.md, kreacje/, paczka.json
  paczka.py kampania.json --sprawdz                # samo sprawdzenie (bez plików)
  paczka.py kampania.json -o out/paczka --limit 1500   # budżet łączny nie może przekroczyć zgody właściciela

Wejście (`kampania.json`, format: skill `publikacja-reczna`, references/kampania.md): platforma `meta` albo `google`,
kampania (nazwa, cel, budżet łączny albo dzienny, daty od–do), zestawy/grupy (odbiorcy, słowa kluczowe), reklamy
(pliki, teksty, CTA, URL, UTM). Skrypt sprawdza to, co platforma odrzuci albo co przepali budżet: długości tekstów,
brak daty końca, budżet ponad `--limit`, URL bez https, brakujące pliki, proporcje i rozmiar kreacji (ffprobe),
nazwy poza konwencją. Błędy = kod 1 i bez paczki; uwagi nie blokują.

Wynik: `PUBLIKACJA.md` (krok po kroku w Menedżerze reklam / Google Ads, z wartościami do wklejenia i listą
kontrolną przed „Opublikuj”), `teksty.md` (każdy tekst w osobnym bloku do skopiowania), `kreacje/` (pliki
z nazwami reklam), `paczka.json` (podsumowanie). Agent nie ma dostępu do konta: niczego nie publikuje i nie wydaje.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlencode, urlsplit

# limity tekstów: twarde (platforma odrzuci) i zalecane (dłuższy tekst Meta ucina w podglądzie „Więcej”)
META_ZALECANE = {"tekst": 125, "naglowek": 40, "opis": 30}
GOOGLE_TWARDE = {"naglowek": 30, "opis": 90, "sciezka": 15}
GOOGLE_ILE = {"naglowki": (3, 15), "opisy": (2, 4)}
META_CELE = {  # objective API → (PL w Menedżerze reklam, EN)
    "OUTCOME_AWARENESS": ("Rozpoznawalność", "Awareness"), "OUTCOME_TRAFFIC": ("Ruch", "Traffic"),
    "OUTCOME_ENGAGEMENT": ("Aktywność", "Engagement"), "OUTCOME_LEADS": ("Kontakty", "Leads"),
    "OUTCOME_APP_PROMOTION": ("Promowanie aplikacji", "App promotion"), "OUTCOME_SALES": ("Sprzedaż", "Sales"),
}
META_CTA = {
    "LEARN_MORE": ("Dowiedz się więcej", "Learn more"), "SIGN_UP": ("Zarejestruj się", "Sign up"),
    "SHOP_NOW": ("Kup teraz", "Shop now"), "CONTACT_US": ("Skontaktuj się z nami", "Contact us"),
    "BOOK_NOW": ("Zarezerwuj", "Book now"), "DOWNLOAD": ("Pobierz", "Download"),
    "GET_QUOTE": ("Uzyskaj wycenę", "Get quote"), "SUBSCRIBE": ("Subskrybuj", "Subscribe"),
    "APPLY_NOW": ("Złóż wniosek", "Apply now"), "ORDER_NOW": ("Zamów teraz", "Order now"),
}
GOOGLE_TYPY = {"search": ("Sieć wyszukiwania", "Search")}
PROPORCJE = {"9:16": 9 / 16, "4:5": 4 / 5, "1:1": 1.0, "16:9": 16 / 9, "1.91:1": 1.91}
MAX_MB = {"obraz": 30, "wideo": 4096}
WIDEO = {".mp4", ".mov", ".m4v", ".webm"}
OBRAZ = {".jpg", ".jpeg", ".png", ".webp"}
NAZWA_KAMPANII = re.compile(r"^[A-Z0-9-]+_(meta|google)_[a-z0-9-]+_\d{6}$")


class Wynik:
    def __init__(self) -> None:
        self.bledy: list[str] = []
        self.uwagi: list[str] = []

    def blad(self, msg: str) -> None:
        self.bledy.append(msg)

    def uwaga(self, msg: str) -> None:
        self.uwagi.append(msg)


def data(s: str | None, pole: str, w: Wynik) -> dt.date | None:
    if not s:
        w.blad(f"brak daty `{pole}`: kampania bez daty końca może wydawać bez końca")
        return None
    try:
        return dt.date.fromisoformat(str(s))
    except ValueError:
        w.blad(f"`{pole}`: {s!r} to nie data RRRR-MM-DD")
        return None


def budzet(spec: dict, w: Wynik, limit: float | None, dzis: dt.date) -> dict:
    k = spec.get("kampania") or {}
    od, do = data(k.get("od"), "kampania.od", w), data(k.get("do"), "kampania.do", w)
    b = k.get("budzet") or {}
    typ, kwota = b.get("typ"), b.get("kwota")
    out: dict = {"typ": typ, "kwota": kwota, "waluta": b.get("waluta", "PLN")}
    if typ not in ("laczny", "dzienny"):
        w.blad("kampania.budzet.typ: `laczny` albo `dzienny`")
    if not isinstance(kwota, (int, float)) or kwota <= 0:
        w.blad("kampania.budzet.kwota: liczba > 0")
        return out
    if od and do:
        if do < od:
            w.blad(f"data końca {do} przed startem {od}")
            return out
        if od < dzis:
            w.uwaga(f"start {od} jest w przeszłości: w Menedżerze ustaw dzisiejszą datę")
        dni = (do - od).days + 1
        out["dni"] = dni
        out["laczny"] = round(kwota * dni, 2) if typ == "dzienny" else float(kwota)
        out["dzienny_sredni"] = round(out["laczny"] / dni, 2)
        if spec.get("platforma") == "meta" and dni < 7:
            w.uwaga(f"kampania trwa {dni} dni: Meta potrzebuje ~7 dni, żeby wyjść z fazy uczenia")
        if limit is not None and out["laczny"] > limit + 1e-9:
            w.blad(f"budżet łączny {out['laczny']:.2f} {out['waluta']} > zgoda właściciela {limit:.2f}: zmniejsz kwotę albo okres")
    return out


def probe(path: Path) -> dict | None:
    if not shutil.which("ffprobe"):
        return None
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
                        "-of", "json", str(path)], capture_output=True, text=True)
    try:
        d = json.loads(r.stdout or "{}")
        s = (d.get("streams") or [{}])[0]
        return {"w": int(s["width"]), "h": int(s["height"]), "sek": float((d.get("format") or {}).get("duration") or 0)}
    except (ValueError, KeyError, TypeError):
        return None


def proporcja(wym: dict) -> str | None:
    r = wym["w"] / wym["h"]
    for nazwa, v in PROPORCJE.items():
        if abs(r - v) / v < 0.02:
            return nazwa
    return None


def sprawdz_plik(rel: str, baza: Path, reklama: str, platforma: str, w: Wynik) -> dict | None:
    p = (baza / rel).resolve() if not Path(rel).is_absolute() else Path(rel)
    if not p.is_file():
        w.blad(f"{reklama}: brak pliku {rel}")
        return None
    ext = p.suffix.lower()
    rodzaj = "wideo" if ext in WIDEO else "obraz" if ext in OBRAZ else None
    if not rodzaj:
        w.blad(f"{reklama}: {p.name}: format {ext or '?'} nieobsługiwany (obraz: JPG/PNG/WebP, wideo: MP4/MOV)")
        return None
    mb = p.stat().st_size / 1e6
    if mb > MAX_MB[rodzaj]:
        w.blad(f"{reklama}: {p.name} ma {mb:.0f} MB > {MAX_MB[rodzaj]} MB ({rodzaj})")
    info = {"plik": str(p), "rodzaj": rodzaj, "mb": round(mb, 1)}
    wym = probe(p)
    if wym:
        info.update(wym)
        info["proporcja"] = proporcja(wym)
        if not info["proporcja"]:
            w.uwaga(f"{reklama}: {p.name} {wym['w']}×{wym['h']}: proporcja poza 9:16, 4:5, 1:1, 16:9; platforma przytnie kadr")
        if min(wym["w"], wym["h"]) < 600:
            w.uwaga(f"{reklama}: {p.name} ma krótszy bok {min(wym['w'], wym['h'])} px: rozmyje się (zalecane ≥ 1080)")
        if rodzaj == "wideo" and wym["sek"] and platforma == "meta" and wym["sek"] > 60:
            w.uwaga(f"{reklama}: film {wym['sek']:.0f} s: w Reels i Stories liczy się pierwsze 3 s, rozważ ≤ 30 s")
    elif shutil.which("ffprobe") is None:
        w.uwaga(f"{reklama}: brak ffprobe, proporcje {p.name} niesprawdzone")
    return info


def url_z_utm(url: str, utm: dict | None, reklama: str, w: Wynik) -> str:
    u = urlsplit(url or "")
    if u.scheme != "https" or not u.netloc:
        w.blad(f"{reklama}: URL {url!r} musi zaczynać się od https://")
        return url or ""
    if not utm:
        w.uwaga(f"{reklama}: bez UTM: w analityce ruch z reklamy zleje się z innym")
        return url
    return url + ("&" if u.query else "?") + urlencode(utm)


def sprawdz_meta(spec: dict, baza: Path, w: Wynik) -> list[dict]:
    k = spec.get("kampania") or {}
    if k.get("cel") not in META_CELE:
        w.blad(f"kampania.cel: jeden z {', '.join(META_CELE)}")
    if "kategorie_specjalne" not in k:
        w.blad("kampania.kategorie_specjalne: wpisz [] albo kategorię (kredyt, zatrudnienie, mieszkania, polityka)")
    zestawy = {z.get("nazwa") for z in spec.get("zestawy") or []}
    if not zestawy:
        w.blad("brak zestawów reklam")
    reklamy = []
    for r in spec.get("reklamy") or []:
        n = r.get("nazwa") or "?"
        if r.get("zestaw") not in zestawy:
            w.blad(f"{n}: zestaw {r.get('zestaw')!r} nie istnieje w `zestawy`")
        for pole, lim in META_ZALECANE.items():
            t = str(r.get(pole) or "")
            if pole != "opis" and not t.strip():
                w.blad(f"{n}: pusty `{pole}`")
            elif len(t) > lim:
                w.uwaga(f"{n}: `{pole}` ma {len(t)} znaków (zalecane ≤ {lim}): reszta schowa się pod „Więcej”")
        if (r.get("cta") or "LEARN_MORE") not in META_CTA:
            w.blad(f"{n}: CTA {r.get('cta')!r}: jedno z {', '.join(META_CTA)}")
        pliki = [sprawdz_plik(f, baza, n, "meta", w) for f in r.get("pliki") or []]
        if not r.get("pliki"):
            w.blad(f"{n}: brak plików kreacji")
        reklamy.append({**r, "_pliki": [p for p in pliki if p], "_url": url_z_utm(r.get("url", ""), r.get("utm"), n, w)})
    if not reklamy:
        w.blad("brak reklam")
    return reklamy


def sprawdz_google(spec: dict, w: Wynik) -> list[dict]:
    k = spec.get("kampania") or {}
    if (k.get("typ") or "search") not in GOOGLE_TYPY:
        w.blad("kampania.typ: na razie paczka obsługuje `search` (PMax i YouTube: plan + instrukcja ręczna)")
    grupy = []
    for g in spec.get("zestawy") or []:
        n = g.get("nazwa") or "?"
        if not g.get("slowa_kluczowe"):
            w.blad(f"{n}: brak słów kluczowych")
        if not g.get("wykluczenia"):
            w.uwaga(f"{n}: brak wykluczających słów: dopasowanie przybliżone przepala budżet na nietrafione hasła")
        rsa = g.get("reklama") or {}
        for pole, (lo, hi) in GOOGLE_ILE.items():
            lista = rsa.get(pole) or []
            lim = GOOGLE_TWARDE["naglowek" if pole == "naglowki" else "opis"]
            if not lo <= len(lista) <= hi:
                w.blad(f"{n}: `{pole}`: {len(lista)} (Google wymaga {lo}–{hi})")
            for t in lista:
                if len(t) > lim:
                    w.blad(f"{n}: „{t}” ma {len(t)} znaków > {lim} (Google odrzuci)")
            if len({t.strip().lower() for t in lista}) < len(lista):
                w.blad(f"{n}: `{pole}` się powtarzają")
        for s in rsa.get("sciezki") or []:
            if len(s) > GOOGLE_TWARDE["sciezka"]:
                w.blad(f"{n}: ścieżka „{s}” > {GOOGLE_TWARDE['sciezka']} znaków")
        grupy.append({**g, "_url": url_z_utm(rsa.get("url", ""), rsa.get("utm"), n, w)})
    if not grupy:
        w.blad("brak grup reklam")
    return grupy


def sprawdz(spec: dict, baza: Path, limit: float | None, dzis: dt.date | None = None) -> tuple[Wynik, dict, list[dict]]:
    w = Wynik()
    plat = spec.get("platforma")
    if plat not in ("meta", "google"):
        w.blad("platforma: `meta` albo `google`")
        return w, {}, []
    nazwa = (spec.get("kampania") or {}).get("nazwa") or ""
    if not nazwa:
        w.blad("kampania.nazwa: pusta")
    elif not NAZWA_KAMPANII.match(nazwa):
        w.uwaga(f"nazwa {nazwa!r} poza konwencją <MARKA>_<platforma>_<cel>_<RRMMDD> (plan-kampanii)")
    b = budzet(spec, w, limit, dzis or dt.date.today())
    elementy = sprawdz_meta(spec, baza, w) if plat == "meta" else sprawdz_google(spec, w)
    return w, b, elementy


# ------------------------------------------------------------------ paczka

def blok(t: str) -> str:
    return "```\n" + t.strip() + "\n```"


def pl_en(para: tuple[str, str]) -> str:
    return f"**{para[0]}** ({para[1]})"


def kroki_meta(spec: dict, b: dict, reklamy: list[dict]) -> list[str]:
    k, zest = spec["kampania"], spec.get("zestawy") or []
    cel = META_CELE[k["cel"]]
    kat = ", ".join(k.get("kategorie_specjalne") or []) or "żadna (zostaw puste)"
    typ = "Budżet łączny" if b["typ"] == "laczny" else "Budżet dzienny"
    s = [f"Otwórz [Menedżera reklam](https://adsmanager.facebook.com) na właściwym koncie reklamowym "
         f"({spec.get('konto') or 'sprawdź nazwę konta w lewym górnym rogu'}).",
         "Kliknij **+ Utwórz** (Create).",
         f"Cel kampanii: {pl_en(cel)} → **Kontynuuj**. Jeśli Meta proponuje kampanię Advantage+, zostaw ją tylko "
         "wtedy, gdy plan tak mówi.",
         f"Nazwa kampanii: `{k['nazwa']}`. Kategorie reklam specjalnych: {kat}.",
         f"Budżet: **{typ} {b['kwota']} {b['waluta']}**, harmonogram od **{k['od']}** do **{k['do']}** "
         "(data końca obowiązkowa: to twardy koniec wydatków)."]
    for z in zest:
        o = z.get("odbiorcy") or {}
        wiek = o.get("wiek") or [18, 65]
        s.append(f"Zestaw reklam `{z['nazwa']}`: lokalizacje {', '.join(o.get('lokalizacje') or ['Polska'])}, wiek "
                 f"{wiek[0]}–{wiek[1]}, płeć {o.get('plec', 'wszyscy')}"
                 + (f", zainteresowania: {', '.join(o['zainteresowania'])}" if o.get("zainteresowania") else ", odbiorcy szerocy")
                 + f"; miejsca emisji: {z.get('miejsca', 'Advantage+ (automatyczne)')}"
                 + (f"; optymalizacja: {z['optymalizacja']}" if z.get("optymalizacja") else "") + ".")
    for r in reklamy:
        cta = META_CTA[r.get("cta") or "LEARN_MORE"]
        pliki = ", ".join(f"`kreacje/{nazwa_kreacji(r, i, p)}`" for i, p in enumerate(r["_pliki"]))
        s.append(f"Reklama `{r['nazwa']}` (w zestawie `{r['zestaw']}`): tożsamość: strona na Facebooku i konto Instagram "
                 f"marki; multimedia: {pliki or '(pliki z paczki)'}; tekst główny, nagłówek"
                 + (" i opis" if r.get("opis") else "") + f" z `teksty.md` (sekcja `{r['nazwa']}`); "
                 f"wezwanie do działania {pl_en(cta)}; adres strony z `teksty.md` (już z UTM).")
    s.append("Śledzenie: zaznacz piksel/zbiór danych marki, jeśli jest (lista kontrolna niżej).")
    s.append("Przejrzyj podgląd każdej reklamy (Feed, Reels, Stories): tekst nie ucięty, ważne rzeczy poza paskami UI.")
    s.append("Zrób listę kontrolną poniżej, potem **Opublikuj** (Publish). Reklamy przechodzą przegląd Mety (zwykle do 24 h).")
    return s


def kroki_google(spec: dict, b: dict, grupy: list[dict]) -> list[str]:
    k = spec["kampania"]
    s = [f"Otwórz [Google Ads](https://ads.google.com) na właściwym koncie ({spec.get('konto') or 'sprawdź identyfikator konta u góry'}).",
         "**+ Nowa kampania** (New campaign) → cel z planu albo **Utwórz kampanię bez celu** (without guidance), "
         f"typ: {pl_en(GOOGLE_TYPY[k.get('typ') or 'search'])}.",
         f"Nazwa: `{k['nazwa']}`. Sieci: odznacz **sieć reklamową** (Display Network), zostaw samą wyszukiwarkę.",
         f"Lokalizacje: {', '.join(k.get('lokalizacje') or ['Polska'])} (opcja „Obecność: osoby w lokalizacji”), "
         f"języki: {', '.join(k.get('jezyki') or ['polski'])}.",
         f"Budżet dzienny: **{b['dzienny_sredni']} {b['waluta']}** (łącznie {b.get('laczny')} {b['waluta']} przez {b.get('dni')} dni). "
         f"Daty: start **{k['od']}**, koniec **{k['do']}** (Ustawienia dodatkowe → Data rozpoczęcia i zakończenia).",
         f"Ustalanie stawek: {k.get('stawki', 'Maksymalizacja kliknięć z limitem CPC albo konwersji, jak w planie')}."]
    for g in grupy:
        s.append(f"Grupa reklam `{g['nazwa']}`: słowa kluczowe i wykluczenia z `teksty.md` (sekcja `{g['nazwa']}`), "
                 "reklama elastyczna (RSA): nagłówki, opisy, ścieżki i końcowy URL stamtąd.")
    s.append("Rozszerzenia (linki do podstron, objaśnienia), jeśli plan je ma: z `teksty.md`.")
    s.append("Zrób listę kontrolną poniżej, potem **Opublikuj kampanię** (Publish campaign).")
    return s


def nazwa_kreacji(r: dict, i: int, p: dict) -> str:
    return f"{r['nazwa']}{'' if i == 0 else f'_{i + 1}'}{Path(p['plik']).suffix.lower()}"


def teksty_meta(reklamy: list[dict]) -> str:
    out = ["# Teksty do wklejenia (Meta)", ""]
    for r in reklamy:
        out += [f"## {r['nazwa']}", "", "Tekst główny (Primary text):", blok(r.get("tekst", "")), "",
                "Nagłówek (Headline):", blok(r.get("naglowek", ""))]
        if r.get("opis"):
            out += ["", "Opis (Description):", blok(r["opis"])]
        out += ["", "Adres strony (Website URL):", blok(r["_url"]), ""]
    return "\n".join(out)


def teksty_google(grupy: list[dict]) -> str:
    out = ["# Teksty do wklejenia (Google Ads)", ""]
    for g in grupy:
        rsa = g.get("reklama") or {}
        out += [f"## {g['nazwa']}", "", "Słowa kluczowe (po jednym w linii; [ścisłe], \"do wyrażenia\"):",
                blok("\n".join(g.get("slowa_kluczowe") or [])), ""]
        if g.get("wykluczenia"):
            out += ["Wykluczające słowa kluczowe:", blok("\n".join(g["wykluczenia"])), ""]
        out += ["Nagłówki (≤ 30 znaków, każdy osobno):", blok("\n".join(rsa.get("naglowki") or [])), "",
                "Opisy (≤ 90 znaków):", blok("\n".join(rsa.get("opisy") or [])), ""]
        if rsa.get("sciezki"):
            out += ["Ścieżki wyświetlanego URL:", blok(" / ".join(rsa["sciezki"])), ""]
        out += ["Końcowy URL (Final URL):", blok(g["_url"]), ""]
    return "\n".join(out)


def lista_kontrolna(spec: dict, b: dict) -> list[str]:
    s = [f"budżet {'łączny' if b['typ'] == 'laczny' else 'dzienny'} {b['kwota']} {b['waluta']} i data końca {spec['kampania']['do']} "
         f"wpisane (razem najwyżej {b.get('laczny')} {b['waluta']})",
         "limit wydatków konta ustawiony w ustawieniach płatności (ostatnia ochrona przed pomyłką)",
         "właściwe konto reklamowe, strona i profil marki (nie prywatne)",
         "adres strony otwiera się na telefonie, UTM w adresie",
         "piksel/konwersje działają albo kampania nie optymalizuje na konwersje",
         "teksty bez obietnic bez pokrycia, oznaczenie reklamy zgodne z zasadami (zgodnosc-reklam)"]
    return [f"- [ ] {x}" for x in s]


def zbuduj(spec: dict, b: dict, elementy: list[dict], out: Path, w: Wynik) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    plat = spec["platforma"]
    kreacje = []
    if plat == "meta":
        (out / "kreacje").mkdir(exist_ok=True)
        for r in elementy:
            for i, p in enumerate(r["_pliki"]):
                dst = out / "kreacje" / nazwa_kreacji(r, i, p)
                shutil.copy2(p["plik"], dst)
                kreacje.append({"reklama": r["nazwa"], "plik": str(dst), **{k: p[k] for k in ("rodzaj", "proporcja") if k in p}})
        (out / "teksty.md").write_text(teksty_meta(elementy), encoding="utf-8")
        kroki = kroki_meta(spec, b, elementy)
    else:
        (out / "teksty.md").write_text(teksty_google(elementy), encoding="utf-8")
        kroki = kroki_google(spec, b, elementy)
    k = spec["kampania"]
    md = [f"# Publikacja: {k['nazwa']}", "",
          f"Platforma: **{'Meta (Facebook, Instagram)' if plat == 'meta' else 'Google Ads'}** · budżet "
          f"{'łączny' if b['typ'] == 'laczny' else 'dzienny'} {b['kwota']} {b['waluta']} · {k['od']} → {k['do']} "
          f"({b.get('dni')} dni, razem najwyżej {b.get('laczny')} {b['waluta']}).", "",
          "Agent przygotował wszystko, ale nie ma dostępu do konta: kampanię publikujesz Ty. Nazwy przycisków podaję "
          "po polsku i (w nawiasie) po angielsku; w nowszej wersji panelu mogą się nieco różnić.", "",
          "## Krok po kroku", ""] + [f"{i}. {x}" for i, x in enumerate(kroki, 1)] + \
         ["", "## Lista kontrolna przed „Opublikuj”", ""] + lista_kontrolna(spec, b)
    if w.uwagi:
        md += ["", "## Uwagi agenta", ""] + [f"- {u}" for u in w.uwagi]
    md += ["", "## Po publikacji", "",
           "- Odpisz agentowi „opublikowane” (najlepiej z nazwą albo zrzutem kampanii).",
           "- Po 2–3 dniach wyeksportuj raport (Meta: Raporty → Eksportuj → CSV; Google: Raporty → Pobierz → CSV) "
           "i wrzuć go agentowi: dostaniesz raport i listę zmian do wyklikania (`raport-reklam`).",
           "- Coś niepokojącego (wydatki szybciej niż plan, odrzucone reklamy)? Wstrzymanie kampanii jest zawsze bezpieczne."]
    (out / "PUBLIKACJA.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    pod = {"kampania": k["nazwa"], "platforma": plat, "budzet": b, "katalog": str(out),
           "publikacja": str(out / "PUBLIKACJA.md"), "teksty": str(out / "teksty.md"), "kreacje": kreacje,
           "uwagi": w.uwagi}
    (out / "paczka.json").write_text(json.dumps(pod, ensure_ascii=False, indent=1), encoding="utf-8")
    return pod


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kampania", type=Path)
    ap.add_argument("-o", "--wyjscie", type=Path, help="katalog paczki (np. out/paczka)")
    ap.add_argument("--sprawdz", action="store_true", help="tylko sprawdzenie, bez plików")
    ap.add_argument("--limit", type=float, help="zgoda właściciela: najwyżej tyle łącznie (waluta kampanii)")
    a = ap.parse_args(argv)
    if not a.sprawdz and not a.wyjscie:
        ap.error("podaj -o katalog albo --sprawdz")
    try:
        spec = json.loads(a.kampania.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(json.dumps({"bledy": [f"nie czytam {a.kampania}: {exc}"]}, ensure_ascii=False))
        return 2
    w, b, elementy = sprawdz(spec, a.kampania.resolve().parent, a.limit)
    if w.bledy or a.sprawdz:
        print(json.dumps({"bledy": w.bledy, "uwagi": w.uwagi, "budzet": b}, ensure_ascii=False, indent=1))
        return 1 if w.bledy else 0
    print(json.dumps(zbuduj(spec, b, elementy, a.wyjscie, w), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
