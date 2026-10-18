#!/usr/bin/env python3
"""Losowanie ruchów z biblioteki 273 technik (cinetic, MIT), żeby filmy nie zbiegały się do tych samych kilku ruchów.

    python3 ruchy.py losuj --rodzaj promo --sekundy 30             # plan na cały film (ok. 1 ruch na 2,5 s)
    python3 ruchy.py losuj --rodzaj pion --energia spokojna         # spokojnie: bez ruchów o wysokiej energii
    python3 ruchy.py losuj --rodzaj promo --ziarno 41               # ten sam plan jeszcze raz
    python3 ruchy.py losuj --kategoria przejscie --ile 3 --rodzaj promo   # trzy przejścia
    python3 ruchy.py losuj --unikaj out/wideo/ruchy-poprzednie.json --bez tr-mask-wipe-swap
    python3 ruchy.py lista [--kategoria kamera] [--rodzaj petla] [--energia wysoka] [--szukaj counter]
    python3 ruchy.py karta tr-mask-wipe-swap                        # jedna technika w całości
    python3 ruchy.py kategorie                                      # 14 kategorii z liczbą technik
    python3 ruchy.py sprawdz                                        # poprawność pliku biblioteki

Agent sam, bez podpowiedzi, wybiera pierwszy znany ruch: ten sam fade-up, ten sam najazd, ta sama plansza końcowa.
Losowanie bierze z biblioteki z wagami: rola (koń roboczy 3, akcent 2, podpis 1) × dowód (1 + dowody/4, najwyżej 3)
× zgodność energii (ta sama 1,0, „dowolna” 0,7, inna 0,25). Spokojne losowanie nigdy nie bierze ruchu o wysokiej
energii. Technika bez naszego rodzaju filmu (ani „any”) nie wypada nigdy. Plan ma ok. 1 ruch na 2,5 s filmu
(spokojny na 3,5 s), sloty wypełnia w kolejności potrzeb rodzaju (logo-intro najpierw plansza i hook, przejście
przez aplikację najpierw demo produktu), z 1 ruchem-podpisem (2, gdy ruchów jest 10 i więcej). Kategoria bez
niczego przy tej energii oddaje slot następnej w kolejności. Ziarno jest wypisane: plan da się powtórzyć.

Zasady (skill losowanie-ruchow): losujesz przed projektowaniem; budujesz to, co koncept uniesie, opowiedziane
przedmiotami filmu; ruch, który walczy z konceptem, losujesz jeszcze raz (`--bez id`, ta sama `--kategoria`)
najwyżej 2 razy albo go odrzucasz z powodem; nie dodajesz ruchu, którego losowanie nie dało (dobierz `--kategoria`).

Przepisy są po angielsku i w języku Remotion (klatki przy 60 kl./s): tłumaczenie na nasz kontrakt HTML
(`/_lib/jarvo/tokeny.js`, sekundy) jest w `references/przepisy.md`. Kod wyjścia: 0 dobrze, 1 nic nie pasuje,
2 zły argument albo zepsuta biblioteka (opis po polsku).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent / "skills" / "wideo" / "losowanie-ruchow"
BIBLIOTEKA = SKILL / "assets" / "cinetic" / "techniques.json"

# nasza nazwa → nazwa w bibliotece (kategorie, rodzaje filmu, energia, role)
KATEGORIE = {
    "otwarcie": "opening_hook", "przejscie": "transition", "kamera": "camera", "typografia": "typography_motion",
    "choreografia-ui": "ui_choreography", "dane": "data_and_numbers", "demo-produktu": "product_demo",
    "logo-i-plansza": "logo_and_end_card", "kolor-i-swiatlo": "color_and_light", "faktura": "texture_and_finish",
    "kompozycja": "layout_and_composition", "tempo-i-budowa": "pacing_structure",
    "mikrointerakcje": "micro_interaction", "glebia-3d": "depth_and_3d",
}
KAT_PL = {v: k for k, v in KATEGORIE.items()}
RODZAJE = {"promo": "launch", "funkcja": "feature", "petla": "loop", "logo": "sting", "aplikacja": "walkthrough",
           "pion": "vertical"}
RODZ_PL = {v: k for k, v in RODZAJE.items()}
ENERGIE = {"spokojna": "calm", "srednia": "medium", "wysoka": "high", "dowolna": "any"}
EN_PL = {v: k for k, v in ENERGIE.items()}
ROLE = {"workhorse": 3.0, "accent": 2.0, "signature": 1.0}
ROLE_PL = {"workhorse": "koń roboczy", "accent": "akcent", "signature": "podpis"}
WYMAGANE = ("id", "name", "category", "summary", "recipe", "timing", "use_when", "avoid_when", "formats", "energy",
            "role", "ban_safe", "evidence")

# kolejność wypełniania slotów planu dla rodzaju: najpierw to, bez czego ten rodzaj filmu się nie obejdzie
KOLEJNOSC = {
    "launch": ["opening_hook", "transition", "typography_motion", "product_demo", "ui_choreography",
               "logo_and_end_card", "camera", "transition", "data_and_numbers", "micro_interaction",
               "color_and_light", "pacing_structure", "typography_motion", "depth_and_3d",
               "layout_and_composition", "texture_and_finish", "transition", "ui_choreography"],
    "feature": ["product_demo", "ui_choreography", "opening_hook", "transition", "micro_interaction",
                "typography_motion", "logo_and_end_card", "data_and_numbers", "camera", "color_and_light",
                "ui_choreography", "layout_and_composition"],
    "loop": ["ui_choreography", "product_demo", "micro_interaction", "typography_motion", "transition",
             "camera", "pacing_structure", "color_and_light"],
    "sting": ["logo_and_end_card", "opening_hook", "typography_motion", "micro_interaction", "camera",
              "texture_and_finish"],
    "walkthrough": ["product_demo", "ui_choreography", "opening_hook", "transition", "micro_interaction",
                    "camera", "typography_motion", "logo_and_end_card", "ui_choreography", "product_demo",
                    "transition", "pacing_structure", "layout_and_composition", "micro_interaction"],
    "vertical": ["opening_hook", "product_demo", "ui_choreography", "typography_motion", "transition",
                 "logo_and_end_card", "micro_interaction", "data_and_numbers", "camera", "color_and_light",
                 "transition", "typography_motion"],
}
SEKUNDY = {"launch": 30, "feature": 15, "loop": 10, "sting": 6, "walkthrough": 45, "vertical": 15}
MIN_RUCHOW = {"launch": 6, "feature": 5, "loop": 4, "sting": 4, "walkthrough": 6, "vertical": 5}


class Blad(Exception):
    """Błąd z opisem po polsku (kod wyjścia 2, albo 1 gdy nic nie pasuje)."""

    def __init__(self, tekst: str, kod: int = 2):
        super().__init__(tekst)
        self.kod = kod


def wczytaj(sciezka: Path = BIBLIOTEKA) -> list[dict]:
    try:
        dane = json.loads(sciezka.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Blad(f"nie da się przeczytać biblioteki {sciezka}: {e}") from e
    techniki = dane.get("techniques") if isinstance(dane, dict) else dane
    bledy = sprawdz(techniki)
    if bledy:
        raise Blad("zepsuta biblioteka:\n  " + "\n  ".join(bledy[:20]))
    return techniki


def sprawdz(techniki) -> list[str]:
    if not isinstance(techniki, list) or not techniki:
        return ["biblioteka nie ma żadnej techniki"]
    bledy, widziane = [], set()
    for i, t in enumerate(techniki):
        gdzie = t.get("id", f"#{i}") if isinstance(t, dict) else f"#{i}"
        if not isinstance(t, dict):
            bledy.append(f"{gdzie}: to nie obiekt")
            continue
        bledy += [f"{gdzie}: brak pola {k}" for k in WYMAGANE if t.get(k) in ("", None)]
        if t.get("id") in widziane:
            bledy.append(f"{gdzie}: powtórzone id")
        widziane.add(t.get("id"))
        if t.get("category") not in KAT_PL:
            bledy.append(f"{gdzie}: nieznana kategoria {t.get('category')!r}")
        fm = t.get("formats")
        if not isinstance(fm, list) or not fm or any(x not in RODZ_PL and x != "any" for x in fm):
            bledy.append(f"{gdzie}: formats spoza {sorted(RODZ_PL)} + any")
        if t.get("energy") not in EN_PL:
            bledy.append(f"{gdzie}: nieznana energia {t.get('energy')!r}")
        if t.get("role") not in ROLE:
            bledy.append(f"{gdzie}: nieznana rola {t.get('role')!r}")
        if t.get("ban_safe") is False and not t.get("ban_safe_variant"):
            bledy.append(f"{gdzie}: ban_safe false bez ban_safe_variant")
        if isinstance(t.get("evidence"), bool) or not isinstance(t.get("evidence", 0), (int, float)):
            bledy.append(f"{gdzie}: evidence musi być liczbą")
    return bledy


def waga(t: dict, energia: str | None) -> float:
    w = ROLE[t["role"]] * min(3.0, 1.0 + float(t.get("evidence") or 0) / 4.0)
    if energia == "calm" and t["energy"] == "high":
        return 0.0                                   # spokojny film nigdy nie losuje uderzenia, śmignięcia ani glitcha
    if energia and energia != "any":
        w *= 1.0 if t["energy"] == energia else (0.7 if t["energy"] == "any" else 0.25)
    return w


def pasuje(t: dict, rodzaj: str | None) -> bool:
    return not rodzaj or "any" in t["formats"] or rodzaj in t["formats"]


def ile_ruchow(rodzaj: str, sekundy: float, energia: str | None) -> int:
    n = int(round(sekundy / (3.5 if energia == "calm" else 2.5)))
    return max(MIN_RUCHOW[rodzaj], min(len(KOLEJNOSC[rodzaj]), n))


def sloty(rodzaj: str, sekundy: float, energia: str | None) -> dict[str, int]:
    wynik: dict[str, int] = {}
    for kat in KOLEJNOSC[rodzaj][:ile_ruchow(rodzaj, sekundy, energia)]:
        wynik[kat] = wynik.get(kat, 0) + 1
    return wynik


def _losuj(pula: list[dict], n: int, rng: random.Random, energia: str | None, zajete: set[str],
           podpisy: int) -> tuple[list[dict], int]:
    """Losowanie z wagami bez zwracania. Zwraca (wybrane, ile podpisów jeszcze wolno)."""
    wybrane = []
    kand = [t for t in pula if t["id"] not in zajete and waga(t, energia) > 0]
    while len(wybrane) < n and kand:
        if podpisy <= 0:
            kand = [t for t in kand if t["role"] != "signature"]
            if not kand:
                break
        t = rng.choices(kand, weights=[waga(x, energia) for x in kand], k=1)[0]
        wybrane.append(t)
        zajete.add(t["id"])
        podpisy -= t["role"] == "signature"
        kand = [x for x in kand if x["id"] != t["id"]]
    return wybrane, podpisy


def losuj(techniki: list[dict], rodzaj: str = "launch", energia: str | None = "medium", sekundy: float | None = None,
          kategoria: str | None = None, ile: int = 1, ziarno: int | None = None,
          bez: set[str] | None = None) -> dict:
    """Plan na film (bez kategorii) albo `ile` technik jednej kategorii. Nazwy jak w bibliotece (launch, calm…)."""
    if ile < 1:
        raise Blad("--ile musi być co najmniej 1")
    ziarno = ziarno if ziarno is not None else int.from_bytes(os.urandom(4), "big")
    rng = random.Random(ziarno)
    zajete = set(bez or ())
    pula = [t for t in techniki if pasuje(t, rodzaj)]
    if kategoria:
        wybrane, _ = _losuj([t for t in pula if t["category"] == kategoria], ile, rng, energia, zajete, ile)
        if not wybrane:
            zostalo = sum(1 for t in pula if t["category"] == kategoria and t["id"] not in zajete)
            raise Blad(f"w kategorii {KAT_PL[kategoria]} nic nie zostało dla rodzaju {RODZ_PL.get(rodzaj, rodzaj)} "
                       f"({len(zajete)} wykluczonych, {zostalo} zostało). Odrzuć ten ruch z powodem w planie albo weź "
                       "slot z innej kategorii", 1)
    else:
        sekundy = sekundy or SEKUNDY[rodzaj]
        rozmiar = ile_ruchow(rodzaj, sekundy, energia)
        podpisy = 2 if rozmiar >= 10 else 1
        wybrane = []
        for kat, n in sloty(rodzaj, sekundy, energia).items():
            got, podpisy = _losuj([t for t in pula if t["category"] == kat], n, rng, energia, zajete, podpisy)
            wybrane += got
        reszta = KOLEJNOSC[rodzaj][rozmiar:] + KOLEJNOSC[rodzaj]   # pusta kategoria oddaje slot dalej
        while len(wybrane) < rozmiar and reszta:
            kat = reszta.pop(0)
            got, podpisy = _losuj([t for t in pula if t["category"] == kat], 1, rng, energia, zajete, podpisy)
            wybrane += got
        if not wybrane:
            raise Blad("nic nie pasuje do tych filtrów (spróbuj innego --rodzaj albo --energia dowolna)", 1)
    return {"ziarno": ziarno, "rodzaj": RODZ_PL.get(rodzaj, rodzaj), "energia": EN_PL.get(energia, energia),
            "sekundy": None if kategoria else sekundy, "kategoria": KAT_PL.get(kategoria) if kategoria else None,
            "ruchy": wybrane}


def karta(t: dict) -> str:
    linie = [f"### {t['name']}  `{t['id']}`",
             f"*{KAT_PL[t['category']]} · {ROLE_PL[t['role']]} · energia {EN_PL[t['energy']]} · rodzaje "
             f"{', '.join(RODZ_PL.get(x, 'każdy') for x in t['formats'])}*", "", t["summary"], "",
             f"**Przepis:** {t['recipe']}"]
    if t.get("ban_safe") is False:
        linie.append(f"**Wariant bez {', '.join(t.get('bans') or [])}** (gdy marka tego nie niesie): "
                     f"{t['ban_safe_variant']}")
    linie += [f"**Czas (klatki przy 60 kl./s; f(n) = n/60 s):** {t['timing']}", f"**Kiedy:** {t['use_when']}",
              f"**Kiedy nie:** {t['avoid_when']}", ""]
    return "\n".join(linie)


def plan_md(plan: dict) -> str:
    cmd = f"ruchy.py losuj --ziarno {plan['ziarno']} --rodzaj {plan['rodzaj']} --energia {plan['energia']}"
    cmd += f" --kategoria {plan['kategoria']} --ile {len(plan['ruchy'])}" if plan["kategoria"] else \
        f" --sekundy {plan['sekundy']:g}"
    out = [f"<!-- {cmd} -->", f"# Wylosowane ruchy (ziarno {plan['ziarno']})", "",
           "Zbuduj te, które koncept uniesie, każdy opowiedziany przedmiotami filmu. Ruch walczący z konceptem: "
           "najwyżej 2 nowe losowania (`--bez id`) albo odrzucenie z powodem w planie.", ""]
    if len(plan["ruchy"]) > 1:
        out += [f"- {KAT_PL[t['category']]}: {t['name']} (`{t['id']}`, {ROLE_PL[t['role']]})" for t in plan["ruchy"]]
        out.append("")
    out += [karta(t) for t in plan["ruchy"]]
    return "\n".join(out)


def plan_json(plan: dict) -> dict:
    return {**{k: v for k, v in plan.items() if k != "ruchy"},
            "ruchy": [{"id": t["id"], "nazwa": t["name"], "kategoria": KAT_PL[t["category"]],
                       "rola": ROLE_PL[t["role"]]} for t in plan["ruchy"]]}


def _wybor(slownik: dict, wartosc: str | None, co: str) -> str | None:
    if wartosc is None:
        return None
    if wartosc not in slownik:
        raise Blad(f"{co} {wartosc!r}: {', '.join(slownik)}")
    return slownik[wartosc]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], epilog=__doc__.split("\n\n", 1)[1],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    lo = sub.add_parser("losuj", help="plan ruchów na film albo kilka ruchów jednej kategorii")
    lo.add_argument("--rodzaj", default="promo", help=f"rodzaj filmu: {', '.join(RODZAJE)} (domyślnie promo)")
    lo.add_argument("--energia", default="srednia",
                    help=f"{', '.join(ENERGIE)} (domyślnie srednia; spokojna wyklucza ruchy o wysokiej energii)")
    lo.add_argument("--sekundy", type=float, help="długość filmu (domyślnie wg rodzaju)")
    lo.add_argument("--kategoria", help=f"tylko z tej kategorii: {', '.join(KATEGORIE)}")
    lo.add_argument("--ile", type=int, default=1, help="ile z --kategoria (domyślnie 1)")
    lo.add_argument("--ziarno", type=int, help="ziarno losowania (domyślnie losowe, wypisane)")
    lo.add_argument("--bez", default="", help="id po przecinku, których nie losować (np. ponowne losowanie)")
    lo.add_argument("--unikaj", action="append", default=[], help="JSON wcześniejszego losowania: jego ruchy odpadają")
    lo.add_argument("--json", help="zapisz losowanie także do tego pliku (do --unikaj w następnym filmie)")
    lo.add_argument("--format", choices=("md", "json"), default="md")
    li = sub.add_parser("lista", help="id i nazwy technik")
    li.add_argument("--kategoria")
    li.add_argument("--rodzaj")
    li.add_argument("--energia")
    li.add_argument("--szukaj", help="słowo w nazwie, opisie albo przepisie")
    ka = sub.add_parser("karta", help="jedna technika w całości")
    ka.add_argument("id")
    sub.add_parser("kategorie", help="kategorie i liczba technik")
    sub.add_parser("sprawdz", help="sprawdź plik biblioteki")
    a = p.parse_args(argv)
    try:
        techniki = wczytaj()
        if a.cmd == "sprawdz":
            print(f"ruchy.py: {len(techniki)} technik w {len({t['category'] for t in techniki})} kategoriach, bez błędów")
            return 0
        if a.cmd == "kategorie":
            for pl, en in KATEGORIE.items():
                print(f"{pl:<17} {sum(1 for t in techniki if t['category'] == en):>3}")
            return 0
        if a.cmd == "karta":
            t = next((t for t in techniki if t["id"] == a.id), None)
            if not t:
                raise Blad(f"nie ma techniki {a.id!r} (ruchy.py lista)", 1)
            print(karta(t))
            return 0
        if a.cmd == "lista":
            kat = _wybor(KATEGORIE, a.kategoria, "nieznana kategoria")
            rodz = _wybor(RODZAJE, a.rodzaj, "nieznany rodzaj")
            en, fraza = _wybor(ENERGIE, a.energia, "nieznana energia"), (a.szukaj or "").casefold()
            n = 0
            for t in techniki:
                if (kat and t["category"] != kat) or not pasuje(t, rodz) or (en and t["energy"] not in (en, "any")):
                    continue
                if fraza and fraza not in " ".join((t["name"], t["summary"], t["recipe"])).casefold():
                    continue
                print(f"{t['id']:<36} {KAT_PL[t['category']]:<16} {ROLE_PL[t['role']]:<11} {t['name']}")
                n += 1
            print(f"\n{n} z {len(techniki)} · karta: ruchy.py karta <id>")
            return 0
        bez = {x.strip() for x in a.bez.split(",") if x.strip()}
        for plik in a.unikaj:
            try:
                bez |= {r["id"] for r in json.loads(Path(plik).read_text(encoding="utf-8")).get("ruchy", [])}
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
                raise Blad(f"--unikaj {plik}: {e}") from e
        plan = losuj(techniki, _wybor(RODZAJE, a.rodzaj, "nieznany rodzaj"), _wybor(ENERGIE, a.energia, "nieznana energia"),
                     a.sekundy, _wybor(KATEGORIE, a.kategoria, "nieznana kategoria"), a.ile, a.ziarno, bez)
        if a.json:
            Path(a.json).parent.mkdir(parents=True, exist_ok=True)
            Path(a.json).write_text(json.dumps(plan_json(plan), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(json.dumps(plan_json(plan), ensure_ascii=False, indent=1) if a.format == "json" else plan_md(plan))
        return 0
    except Blad as e:
        print(f"ruchy.py: {e}", file=sys.stderr)
        return e.kod


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:                      # `ruchy.py lista | head`
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
