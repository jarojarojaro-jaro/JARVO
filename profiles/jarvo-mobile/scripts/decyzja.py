#!/usr/bin/env python3
"""„Natywna czy PWA?”: potrzeby firmy → uczciwa rekomendacja z kosztami, zanim powstanie jakikolwiek kod.

    decyzja.py szablon > potrzeby.yaml                 # pusty kwestionariusz do wypełnienia z właścicielem
    decyzja.py funkcje                                 # katalog funkcji i co je obsługuje
    decyzja.py ocen potrzeby.yaml [--out katalog] [--json]

Rozwiązania: lepsza strona, PWA (strona z ikoną na ekranie głównym), karta w Apple/Google Wallet, gotowa platforma
(Booksy, Pyszne, Wolt…), aplikacja natywna w sklepach (Expo). Dla każdej funkcji z potrzeb sprawdza, co ją obsługuje
(2 = w pełni, 1 = z ograniczeniami, 0 = wcale), odrzuca rozwiązania bez funkcji „musi”, waży częstotliwość używania
i ryzyko odrzucenia w sklepie (4.2: aplikacja, która nie daje więcej niż strona). Wynik: REKOMENDACJA.md i decyzja.json.
Koszty licencji sprawdzone 2026-10-01 (Apple Developer 99 $/rok, Google Play 25 $ raz, EAS Free / Starter 19 $/mies.,
Supabase Free / Pro 25 $/mies.); czas pracy to szacunek, nie wycena.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROZWIAZANIA = {
    "strona": "lepsza strona mobilna",
    "pwa": "PWA (strona z ikoną na ekranie głównym)",
    "wallet": "karta w Apple Wallet i Google Wallet",
    "platforma": "gotowa platforma branżowa",
    "natywna": "aplikacja w App Store i Google Play",
}
KTO = {"strona": "jarvo-web", "pwa": "jarvo-web", "wallet": "jarvo-mobile", "platforma": "właściciel",
       "natywna": "jarvo-mobile"}

# funkcja: (opis, {rozwiązanie: 0|1|2}, uwaga o ograniczeniu)
FUNKCJE: dict[str, tuple[str, dict[str, int], str]] = {
    "rezerwacje": ("rezerwacja wizyt i terminów", {"strona": 2, "pwa": 2, "platforma": 2, "natywna": 2},
                   "platforma (np. Booksy) daje też ruch z wyszukiwarki platformy, ale bierze abonament"),
    "zamowienia": ("zamawianie (jedzenie, produkty) z historią", {"strona": 2, "pwa": 2, "platforma": 2, "natywna": 2},
                   "platformy dostaw biorą prowizję od zamówienia"),
    "platnosci": ("płatność w aplikacji (BLIK, karta, Przelewy24)", {"strona": 2, "pwa": 2, "platforma": 2, "natywna": 2},
                  "w natywnej: towary fizyczne i usługi przez Stripe/P24, treści cyfrowe tylko przez zakupy Apple/Google"),
    "powiadomienia": ("powiadomienia push (przypomnienia, promocje, status)",
                      {"pwa": 1, "wallet": 1, "platforma": 1, "natywna": 2},
                      "PWA na iPhonie dostaje powiadomienia tylko po dodaniu do ekranu głównego (iOS 16.4+); "
                      "Wallet tylko o zmianie karty; platforma wysyła swoje, nie Twoje"),
    "karta-lojalnosciowa": ("karta stałego klienta, pieczątki, punkty", {"strona": 1, "pwa": 1, "wallet": 2, "natywna": 2},
                            "Wallet: karta na ekranie blokady bez instalowania czegokolwiek"),
    "karnety-bilety": ("karnety, bilety, vouchery z kodem", {"pwa": 1, "wallet": 2, "natywna": 2}, ""),
    "offline": ("działanie bez internetu", {"pwa": 1, "natywna": 2},
                "PWA trzyma dane w przeglądarce, iOS może je usunąć po kilku tygodniach nieużywania"),
    "aparat": ("aparat, zdjęcia dokumentacji, skaner kodów", {"strona": 1, "pwa": 1, "natywna": 2},
               "w przeglądarce aparat działa, skanowanie kodów jest wolniejsze i słabsze na iPhonie"),
    "nfc": ("NFC (tagi, karty)", {"natywna": 2}, "Web NFC działa tylko w Chrome na Androidzie"),
    "lokalizacja": ("mapa, najbliższy punkt, dojazd", {"strona": 2, "pwa": 2, "platforma": 1, "natywna": 2}, ""),
    "lokalizacja-w-tle": ("lokalizacja w tle, geofencing (np. „jesteś blisko salonu”)", {"natywna": 2},
                          "wymaga mocnego uzasadnienia w sklepach (deklaracja w Google Play, 5.1.1 u Apple)"),
    "bluetooth": ("urządzenia Bluetooth (drukarki, czujniki)", {"natywna": 2}, "Web Bluetooth nie działa na iPhonie"),
    "biometria": ("logowanie twarzą lub odciskiem", {"strona": 1, "pwa": 1, "natywna": 2},
                  "w przeglądarce przez klucze dostępu (passkeys)"),
    "widget": ("widżet na ekranie głównym", {"natywna": 2}, ""),
    "podpis": ("podpis klienta na ekranie, protokoły", {"strona": 2, "pwa": 2, "natywna": 2}, ""),
    "czat": ("czat z firmą", {"strona": 2, "pwa": 2, "platforma": 1, "natywna": 2}, ""),
    "kalendarz": ("dodanie terminu do kalendarza", {"strona": 2, "pwa": 2, "platforma": 2, "natywna": 2},
                  "w przeglądarce przez plik .ics"),
    "praca-w-terenie": ("narzędzie dla ekipy w terenie (zlecenia, zdjęcia, offline, synchronizacja)",
                        {"pwa": 1, "natywna": 2}, "PWA wystarcza przy dobrym zasięgu i bez skanera"),
    "obecnosc-w-sklepie": ("„chcę być w App Store i Google Play”", {"pwa": 1, "natywna": 2},
                           "PWA trafi do Google Play (Trusted Web Activity), do App Store nie; sama obecność w sklepie "
                           "bez funkcji ponad stronę to częste odrzucenie (Apple 4.2)"),
}
NATYWNE_WARTOSCI = {"powiadomienia", "offline", "aparat", "nfc", "lokalizacja-w-tle", "bluetooth", "biometria", "widget",
                    "praca-w-terenie", "karta-lojalnosciowa", "karnety-bilety"}
CZESTOTLIWOSC = {"dzien": 3, "tydzien": 2, "miesiac": 1, "rzadziej": 0}
KOSZTY = {
    "strona": {"licencje_rok": "0 $", "praca": "w ramach strony (Web)", "utrzymanie": "jak strona"},
    "pwa": {"licencje_rok": "0 $", "praca": "1–3 dni Weba (manifest, ikony, tryb offline, powiadomienia)",
            "utrzymanie": "jak strona"},
    "wallet": {"licencje_rok": "99 $/rok (konto Apple Developer do podpisu kart); Google Wallet 0 $",
               "praca": "2–4 dni (projekt karty, serwer kart, aktualizacje)", "utrzymanie": "certyfikat co rok"},
    "platforma": {"licencje_rok": "abonament albo prowizja platformy (sprawdź cennik)", "praca": "konfiguracja profilu",
                  "utrzymanie": "zależność od platformy, klienci są jej, nie Twoi"},
    "natywna": {"licencje_rok": "Apple 99 $/rok + Google 25 $ raz; EAS 0 $ (15 buildów/mies.) albo 19 $/mies.; "
                                "backend Supabase 0 $ albo 25 $/mies. na produkcji",
                "praca": "prototyp w dniach, pierwsza wersja w sklepach 2–6 tygodni (recenzje, testy, konta)",
                "utrzymanie": "10–20 h/rok: aktualizacja SDK raz w roku, terminy sklepów (docelowe API Androida, Xcode)"},
}

SZABLON = """# Potrzeby firmy do decyzji „natywna czy PWA?” (decyzja.py ocen potrzeby.yaml)
firma: "Nazwa firmy"
branza: uslugi            # uslugi | gastronomia | handel | b2b | zdrowie | edukacja | inne
cel: "co aplikacja ma załatwić, jednym zdaniem"
odbiorcy: klienci         # klienci | pracownicy
klienci:
  powracajacy: tak        # czy ci sami ludzie wracają regularnie
  czestotliwosc: miesiac  # dzien | tydzien | miesiac | rzadziej (jak często typowy klient użyje aplikacji)
  liczba: 300             # ilu realnie by jej używało
funkcje:                  # klucze z `decyzja.py funkcje`; „musi” odrzuca rozwiązania, które ich nie obsługują
  musi: [rezerwacje, powiadomienia]
  fajnie: [karta-lojalnosciowa]
juz_ma: [strona]          # strona | sklep-internetowy | booksy | pyszne | wolt | glovo | aplikacja | ...
budzet_roczny_usd: 300    # ile może kosztować rocznie w licencjach (bez pracy)
"""


def ocen(p: dict) -> dict:
    fun = p.get("funkcje") or {}
    musi = [f for f in fun.get("musi") or [] if f]
    fajnie = [f for f in fun.get("fajnie") or [] if f]
    nieznane = sorted(set(musi + fajnie) - set(FUNKCJE))
    if nieznane:
        raise SystemExit(f"Nieznane funkcje: {', '.join(nieznane)} (lista: decyzja.py funkcje)")
    pracownicy = p.get("odbiorcy") == "pracownicy"
    kl = p.get("klienci") or {}
    czest = CZESTOTLIWOSC.get(str(kl.get("czestotliwosc", "miesiac")), 1)
    ma = {str(x).lower() for x in p.get("juz_ma") or []}
    budzet = p.get("budzet_roczny_usd")
    wyniki = {}
    for r in ROZWIAZANIA:
        if r == "platforma" and (pracownicy or not ({"rezerwacje", "zamowienia"} & set(musi))):
            continue                                       # platforma ma sens tylko dla rezerwacji i zamówień klientów
        braki = [f for f in musi if FUNKCJE[f][1].get(r, 0) == 0]
        ograniczenia = [f for f in musi + fajnie if FUNKCJE[f][1].get(r, 0) == 1]
        pokrycie_fajnie = sum(FUNKCJE[f][1].get(r, 0) for f in fajnie)
        punkty = 70 - 40 * len(braki) - 8 * sum(1 for f in musi if FUNKCJE[f][1].get(r, 0) == 1) + 3 * pokrycie_fajnie
        powody, ryzyka = [], []
        if r == "natywna":
            wartosc = [f for f in musi if f in NATYWNE_WARTOSCI and FUNKCJE[f][1].get("pwa", 0) < 2]
            if wartosc:
                powody.append("przeglądarka nie zrobi tego dobrze: " + ", ".join(FUNKCJE[f][0] for f in wartosc))
            if not wartosc and not pracownicy:
                punkty -= 35
                ryzyka.append("żadna funkcja „musi” nie wymaga aplikacji: w sklepie Apple to typowe odrzucenie 4.2 "
                              "(„przepakowana strona”), a klienci rzadko instalują aplikację, która robi to samo co strona")
            if czest <= 1 and not pracownicy:
                punkty -= 15 if czest == 1 else 30
                ryzyka.append("klient używałby jej raz w miesiącu albo rzadziej: aplikacja zostanie odinstalowana albo "
                              "nigdy nie zainstalowana; lepiej przypominać SMS-em, e-mailem albo kartą w Wallet")
            if czest >= 2 and kl.get("powracajacy"):
                punkty += 10
                powody.append("częste, powtarzalne użycie przez tych samych klientów: aplikacja na ekranie głównym zarabia")
            if pracownicy:
                punkty += 5
                powody.append("narzędzie dla pracowników: bez walki o instalację; dystrybucja przez TestFlight "
                              "(wersje ważne 90 dni) albo prywatne aplikacje Google Play")
            if isinstance(budzet, (int, float)) and budzet < 99:
                punkty -= 20
                ryzyka.append(f"budżet {budzet} $/rok nie pokrywa konta Apple Developer (99 $/rok)")
        if r == "pwa":
            if "powiadomienia" in musi:
                ryzyka.append("na iPhonie powiadomienia działają dopiero po dodaniu strony do ekranu głównego (trzeba "
                              "to klientom pokazać); Android bez ograniczeń")
            if czest >= 2:
                punkty += 5
            if "strona" in ma:
                punkty += 5
                powody.append("buduje na istniejącej stronie: najtańsza droga do ikony na telefonie")
        if r == "wallet":
            if not ({"karta-lojalnosciowa", "karnety-bilety"} & set(musi + fajnie)):
                punkty -= 50
            else:
                powody.append("karta na ekranie blokady bez instalowania aplikacji; działa na iPhonie i Androidzie")
        if r == "platforma":
            if ma & {"booksy", "pyszne", "wolt", "glovo", "uber-eats"}:
                punkty += 5
                powody.append("firma już jest na platformie: najpierw wykorzystać to, co jest")
            ryzyka.append("klienci i dane należą do platformy; prowizja od każdego zamówienia albo abonament")
        if r == "strona" and czest <= 1:
            punkty += 10
            powody.append("rzadkie użycie: wystarczy szybka strona z rezerwacją i przypomnieniami SMS/e-mail")
        if braki:
            ryzyka.insert(0, "nie obsługuje funkcji „musi”: " + ", ".join(FUNKCJE[f][0] for f in braki))
        wyniki[r] = {"rozwiazanie": ROZWIAZANIA[r], "punkty": max(0, punkty), "odpada": bool(braki),
                     "braki": braki, "ograniczenia": ograniczenia,
                     "uwagi": [FUNKCJE[f][2] for f in ograniczenia if FUNKCJE[f][2]],
                     "powody": powody, "ryzyka": ryzyka, "koszty": KOSZTY[r], "kto": KTO[r]}
    ranking = sorted(wyniki, key=lambda r: (wyniki[r]["odpada"], -wyniki[r]["punkty"]))
    pierwsza = ranking[0]
    uzupelnienie = None              # karta w Wallet uzupełnia stronę, PWA i platformę (natywna ma kartę u siebie)
    if pierwsza in ("strona", "pwa", "platforma") and {"karta-lojalnosciowa", "karnety-bilety"} & set(musi + fajnie):
        uzupelnienie = "wallet"
    nastepny = {"strona": "karta dla jarvo-web: strona mobilna (audyt-strony, nowa-strona)",
                "pwa": "karta dla jarvo-web: PWA (manifest, ikony, offline, powiadomienia web push)",
                "wallet": "Twórca aplikacji: projekt karty Wallet (po założeniu konta Apple Developer)",
                "platforma": "właściciel: profil na platformie; Web dodaje link i widżet na stronie",
                "natywna": "Twórca aplikacji: nowa-aplikacja (plan z profilem zgodności, prototyp na telefonie, bez kont)"}
    blisko = [r for r in ranking[1:] if not wyniki[r]["odpada"] and wyniki[pierwsza]["punkty"] - wyniki[r]["punkty"] <= 5]
    return {"firma": p.get("firma"), "cel": p.get("cel"), "odbiorcy": p.get("odbiorcy", "klienci"), "blisko": blisko,
            "musi": musi, "fajnie": fajnie, "ranking": ranking, "rekomendacja": pierwsza, "uzupelnienie": uzupelnienie,
            "nastepny_krok": nastepny[pierwsza], "wyniki": wyniki}


def raport_md(w: dict) -> str:
    r = w["wyniki"][w["rekomendacja"]]
    l = [f"# Natywna czy PWA: {w.get('firma') or 'firma'}", "", f"Cel: {w.get('cel') or '?'}", "",
         f"**Rekomendacja: {r['rozwiazanie']}**" + (f" + {w['wyniki'][w['uzupelnienie']]['rozwiazanie']}" if w["uzupelnienie"] else ""),
         ""]
    l += [f"- {x}" for x in r["powody"]] or ["- najlepiej pokrywa potrzeby najmniejszym kosztem"]
    for b in w["blisko"]:
        x = w["wyniki"][b]
        l += ["", f"**Blisko:** {x['rozwiazanie']} ({x['punkty']} pkt wobec {r['punkty']}): " +
              ("; ".join(x["powody"]) or "podobnie pokrywa potrzeby") + ". Tu decyduje właściciel."]
    l += ["", f"**Następny krok:** {w['nastepny_krok']}", "", "## Porównanie", "",
          "| Rozwiązanie | Punkty | Funkcje „musi” | Licencje | Praca | Ryzyka |", "|---|---|---|---|---|---|"]
    for k in w["ranking"]:
        x = w["wyniki"][k]
        musi = "✗ brak: " + ", ".join(x["braki"]) if x["braki"] else ("⚠ z ograniczeniami: " + ", ".join(x["ograniczenia"])
                                                                     if x["ograniczenia"] else "✓ wszystkie")
        l.append(f"| {x['rozwiazanie']} | {x['punkty']} | {musi} | {x['koszty']['licencje_rok']} | {x['koszty']['praca']} | "
                 f"{'; '.join(x['ryzyka']) or '—'} |")
    l += ["", "## Funkcje i co je obsługuje", "", "| Funkcja | " + " | ".join(ROZWIAZANIA[k] for k in ROZWIAZANIA) + " |",
          "|---|" + "---|" * len(ROZWIAZANIA)]
    znak = {2: "✓", 1: "⚠", 0: "✗"}
    for f in w["musi"] + w["fajnie"]:
        opis, wsparcie, _ = FUNKCJE[f]
        l.append(f"| {opis}{' (musi)' if f in w['musi'] else ''} | " + " | ".join(znak[wsparcie.get(k, 0)] for k in ROZWIAZANIA) + " |")
    uwagi = sorted({u for k in w["ranking"] for u in w["wyniki"][k]["uwagi"]})
    if uwagi:
        l += ["", "Ograniczenia (⚠):"] + [f"- {u}" for u in uwagi]
    l += ["", "Punkty: 70 na start, −40 za każdą brakującą funkcję „musi”, −8 za każdą „musi” z ograniczeniami, +3/+6 za "
          "funkcje „fajnie”, korekty za częstotliwość użycia, istniejącą stronę i ryzyko odrzucenia w sklepie.",
          "Koszty licencji sprawdzone 2026-10-01; czas pracy to szacunek. Decyzja należy do właściciela.", ""]
    return "\n".join(l)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("szablon")
    sub.add_parser("funkcje")
    o = sub.add_parser("ocen")
    o.add_argument("potrzeby")
    o.add_argument("--out")
    o.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "szablon":
        print(SZABLON, end="")
        return 0
    if args.cmd == "funkcje":
        for k, (opis, wsp, uwaga) in FUNKCJE.items():
            print(f"{k:22} {opis}  [{', '.join(f'{r}:{v}' for r, v in wsp.items())}]" + (f"  ({uwaga})" if uwaga else ""))
        return 0
    import yaml
    p = yaml.safe_load(Path(args.potrzeby).read_text(encoding="utf-8")) or {}
    w = ocen(p)
    md = raport_md(w)
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "REKOMENDACJA.md").write_text(md, encoding="utf-8")
        (out / "decyzja.json").write_text(json.dumps(w, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✓ {out}/REKOMENDACJA.md: {w['wyniki'][w['rekomendacja']]['rozwiazanie']}", file=sys.stderr)
    print(json.dumps(w, ensure_ascii=False, indent=2) if args.json else md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
