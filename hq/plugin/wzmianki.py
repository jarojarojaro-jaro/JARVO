"""Wzmianki w rozmowie aplikacji Jarvo: `@uchwyt` na początku wiadomości wysyła ją wprost do agenta.

Zasady (docs/HQ.md „Rozmowy”, bliźniak przeglądarki: hq/web/src/12-wzmianki.js, wspólne wektory testów
w tests/data/wzmianki.json):
  - tylko wzmianki na początku wiadomości wybierają adresata; bez nich wiadomość idzie do koordynatora wątku
    (Jarvo); nic nie przechodzi na następną wiadomość (brak „przyklejonego” adresata);
  - uchwyt i aliasy porównujemy po złożeniu (bez polskich znaków, małe litery): `@Łowca` = `@lowca`;
  - słowa zarezerwowane (`@file:…`, `@all`) i nieznane uchwyty zostawiają tekst bez zmian;
  - `@agent` w środku zdania nie wysyła, tylko daje ostrzeżenie (`srodek:<agent>`), a `@agent:x` w treści dostaje
    spację po dwukropku, żeby żadna platforma nie wzięła go za odwołanie do kontekstu;
  - koordynator razem z innymi (`@jarvo @web …`): pracę dostaje tylko koordynator, a pozostali trafiają do treści
    jako dopisek (Jarvo rozdzieli pracę kartami).
Czysty Python, bez Hermesa i FastAPI.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable, Mapping

ZNAK_UCHWYTU = r"[\w-]"          # litery i cyfry Unicode, _ i -: '@łowca' czytamy, potem składamy do 'lowca'
UCHWYT_RE = re.compile(r"^[a-z][a-z0-9]{1,15}$")
# rodzaje odwołań Hermesa do kontekstu (@file:, @url:, …) i słowa „do wszystkich”: nigdy nie są wzmianką
ZAREZERWOWANE = frozenset({"all", "everyone", "wszyscy", "here", "diff", "staged", "file", "folder", "git", "url"})
KOORDYNATOR = "jarvo"
WIELU = 3                         # powyżej tylu adresatów aplikacja pyta o potwierdzenie (ostrzeżenie `wielu:<n>`)

_SLOWO = re.compile(ZNAK_UCHWYTU + "+")


def zloz(s: str) -> str:
    """Postać do porównań: NFKD bez znaków łączących, ł→l, małe litery („Ręka” → „reka”, „Łowca” → „lowca”)."""
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.category(c).startswith("M"))
    return s.replace("ł", "l").replace("Ł", "L").lower()


@dataclass(frozen=True)
class Wynik:
    adresaci: tuple[str, ...]        # nazwy profili w kolejności, bez powtórzeń
    bezposrednio: tuple[str, ...]    # adresaci bez koordynatora (tryb „bezpośrednio”, bez karty)
    tresc: str                       # tekst do wysłania (bez wiodących wzmianek, oczyszczony, przycięty)
    wiodace: bool                    # były wiodące wzmianki (UI: „Do: Web · tylko ta wiadomość”)
    ostrzezenia: tuple[str, ...]     # pusta_tresc | nieznany:<w> | zarezerwowane:<w> | srodek:<agent> | wielu:<n> | koordynuje:<a,b>

    def jako_slownik(self) -> dict:
        return {"adresaci": list(self.adresaci), "bezposrednio": list(self.bezposrednio), "tresc": self.tresc,
                "wiodace": self.wiodace, "ostrzezenia": list(self.ostrzezenia)}


def aliasy_agenta(agent: Mapping) -> list[str]:
    """Złożone aliasy jednego agenta: pole `aliasy` (fleet.json z hqbuild), inaczej uchwyt i nazwa profilu."""
    surowe = list(agent.get("aliasy") or []) or [agent.get("handle") or "", agent.get("name") or ""]
    return list(dict.fromkeys(a for a in (zloz(x) for x in surowe) if a and _SLOWO.fullmatch(a)))


def mapa_aliasow(agenci: Iterable[Mapping]) -> dict[str, str]:
    """{złożony alias: nazwa profilu} z listy agentów (flota + agenci testowi/własni). Słowa zarezerwowane nie
    trafiają do mapy; przy powtórce wygrywa pierwszy agent (walidator nie dopuszcza kolizji we flocie)."""
    mapa: dict[str, str] = {}
    for a in agenci:
        for alias in aliasy_agenta(a):
            if alias not in ZAREZERWOWANE:
                mapa.setdefault(alias, str(a["name"]))
    return mapa


def nazwy_agentow(agenci: Iterable[Mapping]) -> dict[str, str]:
    """{nazwa profilu: nazwa wyświetlana} (pole `nazwa`, `short` z fleet.json albo nazwa profilu)."""
    return {str(a["name"]): str(a.get("nazwa") or a.get("short") or a["name"]) for a in agenci}


def _nazwa(agent: str, nazwy: Mapping[str, str] | None) -> str:
    if nazwy and nazwy.get(agent):
        return nazwy[agent]
    return agent.removeprefix("jarvo-").capitalize()


def _granica_przed(tekst: str, i: int) -> bool:
    return i == 0 or tekst[i - 1].isspace() or tekst[i - 1] == ","


def _granica_po(tekst: str, j: int) -> bool:
    return j >= len(tekst) or tekst[j].isspace() or tekst[j] in ",:"


def _wzmianki_w_tresci(tresc: str, aliasy: Mapping[str, str], pomin: set[str]) -> tuple[str, list[str]]:
    """Treść z `@alias:x` → `@alias: x` (znane aliasy) i lista agentów wspomnianych w środku (`srodek:`)."""
    wyjscie, srodek, i = [], [], 0
    while True:
        k = tresc.find("@", i)
        if k < 0:
            wyjscie.append(tresc[i:])
            break
        m = _SLOWO.match(tresc, k + 1)
        if not m or not _granica_przed(tresc, k) or not _granica_po(tresc, m.end()):
            wyjscie.append(tresc[i:k + 1])
            i = k + 1
            continue
        agent = aliasy.get(zloz(m.group()))
        j = m.end()
        wyjscie.append(tresc[i:j])
        if agent:
            if agent not in pomin and agent not in srodek:
                srodek.append(agent)
            if j < len(tresc) and tresc[j] == ":" and j + 1 < len(tresc) and not tresc[j + 1].isspace():
                wyjscie.append(": ")
                j += 1
        i = j
    return "".join(wyjscie), srodek


def parsuj(tekst: str, aliasy: Mapping[str, str], *, koordynator: str = KOORDYNATOR,
           nazwy: Mapping[str, str] | None = None) -> Wynik:
    """Adresaci i treść jednej wiadomości. Bezstanowe: brak wiodących wzmianek = koordynator wątku."""
    tekst = str(tekst or "")
    n = len(tekst)
    i = 0
    while i < n and tekst[i].isspace():
        i += 1
    agenci: list[str] = []
    ostrzezenia: list[str] = []
    reszta_od = 0
    while i < n and tekst[i] == "@" and _granica_przed(tekst, i):
        m = _SLOWO.match(tekst, i + 1)
        if not m or not _granica_po(tekst, m.end()):
            break                                   # @web.pl, @web! – zwykły tekst
        w, j = m.group(), m.end()
        klucz = zloz(w)
        if klucz in ZAREZERWOWANE:
            ostrzezenia.append(f"zarezerwowane:{w}")
            break
        agent = aliasy.get(klucz)
        if not agent:
            ostrzezenia.append(f"nieznany:{w}")
            break
        if agent not in agenci:
            agenci.append(agent)
        if j < n and tekst[j] == ":":
            j += 1
        while j < n and (tekst[j] == "," or tekst[j].isspace()):
            j += 1
        i = reszta_od = j
    wiodace = bool(agenci)
    tresc = (tekst[reszta_od:] if wiodace else tekst).strip()
    adresaci = agenci if wiodace else [koordynator]
    tresc, srodek = _wzmianki_w_tresci(tresc, aliasy, set(adresaci))
    tresc = tresc.strip()
    if not tresc:
        ostrzezenia.append("pusta_tresc")
    if koordynator in adresaci and len(adresaci) > 1:
        inni = [a for a in adresaci if a != koordynator]
        adresaci = [koordynator]
        if tresc:
            tresc += "\n\n(Właściciel chce w tym udziału: " + ", ".join(_nazwa(a, nazwy) for a in inni) + ".)"
        ostrzezenia.append("koordynuje:" + ",".join(inni))
    ostrzezenia += [f"srodek:{a}" for a in srodek if a not in adresaci]
    if len(adresaci) > WIELU:
        ostrzezenia.append(f"wielu:{len(adresaci)}")
    return Wynik(adresaci=tuple(adresaci), bezposrednio=tuple(a for a in adresaci if a != koordynator),
                 tresc=tresc, wiodace=wiodace, ostrzezenia=tuple(ostrzezenia))
