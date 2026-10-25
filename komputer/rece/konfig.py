"""Ścisły odczyt config.yaml Hermesa samą biblioteką standardową (bramka rąk działa na Pythonie Jarva, bez PyYAML).

Bramka musi wiedzieć na pewno, jak Hermes f97608f przeczyta zgody profilu rąk. Hermes czyta config PyYAML-em (YAML
1.1: gołe `off`, `no`, `false` to fałsz, `yes`, `on`, `true` to prawda), łączy go z wartościami domyślnymi
(hermes_cli/config_defaults.py: approvals.mode domyślnie `smart`, cron_mode, single_query_mode i unattended_mode
domyślnie `deny`) i z nakładką administratora (`$HERMES_MANAGED_DIR/config.yaml` albo `/etc/hermes/config.yaml`,
wygrywa przy każdym liściu), a `${ZMIENNA}` w wartościach rozwija ze środowiska. Tryb zgód normalizuje
tools/approval_context.py `_normalize_approval_mode` (fałsz → off, prawda → manual, napis bez wielkości liter
i spacji), tryby bez człowieka `_binary_approval_mode` (`str(wartość).lower().strip()` w approve, off, allow, yes
= zatwierdza sam). Zepsuty YAML Hermes zastępuje ostatnią dobrą kopią, której bramka nie widzi.

Dlatego ten moduł czyta tylko podzbiór YAML, który da się odczytać bez zgadywania, a resztę kończy wyjątkiem
Niepewne (bramka wtedy odmawia, jak przy złych zgodach):

  czyta     mapowania i listy blokowe (także lista w tym samym wcięciu co klucz, jak w zrzucie PyYAML), skalary
            zwykłe, w apostrofach i w cudzysłowie (z sekwencjami ucieczki, także na kilka wierszy), skalary
            blokowe | i > (treść tylko do przeszukania), listy i mapowania w nawiasach [] {} (także na kilka
            wierszy), komentarze i jedno `---` na początku
  odmawia   tabulatorów, znaków sterujących i separatorów NEL, LS, PS, kotwic (&), aliasów (*), tagów (!), kluczy
            złożonych (?), scalania (<<), dyrektyw (%), drugiego dokumentu i `...`, wskaźników wcięcia skalarów
            blokowych, kluczy najwyższego poziomu innych niż zwykła nazwa, powtórzonych kluczy na najwyższym
            poziomie, niezamkniętych cudzysłowów i nawiasów, nieznanych sekwencji ucieczki, plików ponad 1 MB i
            wszystkiego, czego PyYAML by nie przeczytał (np. dwukropek ze spacją w zwykłej wartości)

Na wynik czytania (Mapa, Lista, Skalar) patrzą funkcje zgód: problemy_zgod (approvals tak, jak przeczyta je Hermes)
i stale_zgody (klucze `cua:` w command_allowlist w każdej pisowni). Wszystko, czego nie da się rozstrzygnąć na
pewno (wartość wielowierszowa, zmienna środowiska, liczba w miejscu trybu), to Niepewne.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

MAKS_ROZMIAR = 1 << 20
MAKS_GLEBOKOSC = 40
MAKS_KLUCZ = 1024                   # PyYAML: prosty klucz najwyżej 1024 znaki w jednym wierszu
# znaki, od których nie zaczyna się zwykły skalar (yaml/scanner.py, check_plain); `-`, `?` i `:` tylko bez spacji po
WSKAZNIKI = frozenset(",[]{}#&*!|>%@`\"'")
# znaki, których PyYAML nie przyjmuje albo czyta jako koniec wiersza: tabulator (we wcięciu to błąd PyYAML, a poza nim
# czytelnik musiałby śledzić kolumny jak PyYAML), sterujące C0 i C1, NEL, LS, PS, BOM w środku, surogaty, U+FFFE/FFFF
ZLE_ZNAKI = re.compile("[^\n\r\x20-\x7e\xa0-‧‪-퟿-﻾＀-�\U00010000-\U0010ffff]")
ZWYKLY_KLUCZ = re.compile(r"[A-Za-z_][A-Za-z0-9_.\-]*")
# rozwiązywanie zwykłych skalarów jak PyYAML (yaml/resolver.py, YAML 1.1)
_BOOL = re.compile(r"yes|Yes|YES|no|No|NO|true|True|TRUE|false|False|FALSE|on|On|ON|off|Off|OFF")
_NULL = re.compile(r"~|null|Null|NULL|")
_INT = re.compile(r"[-+]?0b[0-1_]+|[-+]?0[0-7_]+|[-+]?(?:0|[1-9][0-9_]*)|[-+]?0x[0-9a-fA-F_]+"
                  r"|[-+]?[1-9][0-9_]*(?::[0-5]?[0-9])+")
_FLOAT = re.compile(r"[-+]?(?:[0-9][0-9_]*)\.[0-9_]*(?:[eE][-+][0-9]+)?|\.[0-9_]+(?:[eE][-+][0-9]+)?"
                    r"|[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+\.[0-9_]*|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN)")
_DATA = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}(?:[Tt]| +)[0-9]{1,2}:[0-9]{2}:[0-9]{2}"
                   r"(?:\.[0-9]*)?(?: *(?:Z|[-+][0-9]{1,2}(?::[0-9]{2})?))?")
# sekwencje ucieczki w cudzysłowie (yaml/scanner.py: ESCAPE_REPLACEMENTS, ESCAPE_CODES)
UCIECZKI = {"0": "\0", "a": "\x07", "b": "\x08", "t": "\x09", "n": "\x0a", "v": "\x0b", "f": "\x0c", "r": "\x0d",
            "e": "\x1b", " ": " ", '"': '"', "/": "/", "\\": "\\", "N": "\x85", "_": "\xa0", "L": " ",
            "P": " "}
KODY = {"x": 2, "u": 4, "U": 8}
# tools/approval_context.py
TRYBY = ("manual", "smart", "off")
ZATWIERDZA_SAM = frozenset({"approve", "off", "allow", "yes"})
TRYBY_BEZ_CZLOWIEKA = ("cron_mode", "single_query_mode", "unattended_mode")
CUA = re.compile(r"cua(?::|\\x3a|\\u003a|\\U0000003a)[^\s'\",\]}#]*", re.I)


class Niepewne(ValueError):
    """Configu nie da się przeczytać na pewno tak jak Hermes (bramka odmawia). `nr` to wiersz od 1 (0: cały plik)."""

    def __init__(self, nr: int, powod: str):
        super().__init__(f"wiersz {nr}: {powod}" if nr else powod)
        self.nr, self.powod = nr, powod


@dataclass
class Skalar:
    tekst: str                      # po rozkodowaniu (cudzysłów, apostrofy, łączenie wierszy)
    styl: str = ""                  # "" zwykły, "'" apostrofy, '"' cudzysłów, "|" albo ">" blokowy
    nr: int = 0
    wielowierszowy: bool = False

    def wartosc(self) -> tuple[str, object]:
        """(rodzaj, wartość) jak w PyYAML: ("null", None), ("bool", True|False), ("str", tekst) albo ("inny", tekst)
        dla liczb, dat i znaczników (ich wartość zależy od konstruktora PyYAML, więc tu jej nie zgadujemy)."""
        if self.styl:
            return "str", self.tekst
        if _NULL.fullmatch(self.tekst):
            return "null", None
        if _BOOL.fullmatch(self.tekst):
            return "bool", self.tekst.lower() in ("yes", "true", "on")
        if self.tekst in ("<<", "=") or any(r.fullmatch(self.tekst) for r in (_INT, _FLOAT, _DATA)):
            return "inny", self.tekst
        return "str", self.tekst


@dataclass
class Lista:
    elementy: list
    nr: int = 0
    blokowa: bool = True                                # False: w nawiasach [...]


@dataclass
class Mapa:
    pola: dict
    nr: int = 0
    numery: dict = field(default_factory=dict)          # klucz -> wiersz
    powtorzone: list = field(default_factory=list)      # PyYAML bierze ostatni, my odmawiamy, gdzie to ważne
    cytowane: set = field(default_factory=set)          # klucze w cudzysłowie albo apostrofach
    blokowa: bool = True                                # False: w nawiasach {...}


@dataclass(frozen=True)
class Problem:
    kod: str
    powod: str


# ---------------------------------------------------------------- czytnik

class _Czytnik:
    def __init__(self, tekst: str):
        if len(tekst) > MAKS_ROZMIAR:
            raise Niepewne(0, "config większy niż 1 MB")
        if tekst.startswith("﻿"):
            tekst = tekst[1:]
        if (zly := ZLE_ZNAKI.search(tekst)) is not None:
            nr = len(re.findall(r"\r\n|\r|\n", tekst[:zly.start()])) + 1
            opis = "tabulator" if zly.group() == "\t" else f"znak U+{ord(zly.group()):04X}"
            raise Niepewne(nr, f"{opis} (bramka czyta config bez tabulatorów, znaków sterujących i separatorów "
                               "wierszy innych niż koniec linii)")
        self.w = re.split(r"\r\n|\r|\n", tekst)
        self.li = 0
        self.k = 0
        self.glebokosc = 0

    # -- wiersze
    def _l(self, li: int | None = None) -> str:
        return self.w[self.li if li is None else li]

    def _wciecie(self, li: int) -> int:
        linia = self.w[li]
        return len(linia) - len(linia.lstrip(" "))

    def _pusta(self, li: int) -> bool:
        s = self.w[li].strip(" ")
        return not s or s.startswith("#")

    def _znacznik(self, li: int) -> bool:
        linia = self.w[li]
        return linia[:3] in ("---", "...") and (len(linia) == 3 or linia[3] == " ")

    def _nastepny(self, li: int) -> int | None:
        """Pierwszy wiersz z treścią od `li`; znacznik dokumentu i dyrektywa to odmowa."""
        while li < len(self.w):
            if self._znacznik(li):
                raise Niepewne(li + 1, "drugi dokument albo znacznik końca dokumentu (--- / ...)")
            if self.w[li].startswith("%"):
                raise Niepewne(li + 1, "dyrektywa YAML (%)")
            if not self._pusta(li):
                return li
            li += 1
        return None

    def _myslnik(self, li: int, k: int) -> bool:
        linia = self.w[li]
        return k < len(linia) and linia[k] == "-" and (k + 1 == len(linia) or linia[k + 1] == " ")

    def _koniec_wiersza(self) -> None:
        """Po wartości tylko spacje i komentarz; kursor na początek następnego wiersza."""
        linia, k = self._l(), self.k
        while k < len(linia) and linia[k] == " ":
            k += 1
        if k < len(linia):
            if linia[k] != "#" or (k > 0 and linia[k - 1] != " "):
                raise Niepewne(self.li + 1, f"nieoczekiwany tekst po wartości: {linia[k:k + 30]!r}")
        self.li, self.k = self.li + 1, 0

    def _glebiej(self) -> None:
        self.glebokosc += 1
        if self.glebokosc > MAKS_GLEBOKOSC:
            raise Niepewne(self.li + 1, "za głębokie zagnieżdżenie")

    # -- dokument
    def dokument(self) -> Mapa:
        li = 0
        while li < len(self.w) and self._pusta(li):
            li += 1
        if li < len(self.w) and self.w[li].startswith("%"):
            raise Niepewne(li + 1, "dyrektywa YAML (%)")
        if li < len(self.w) and self._znacznik(li):
            reszta = self.w[li][3:].strip(" ")
            if self.w[li].startswith("...") or (reszta and not reszta.startswith("#")):
                raise Niepewne(li + 1, "znacznik dokumentu z treścią albo `...` na początku")
            li += 1
        li = self._nastepny(li)
        if li is None:
            return Mapa({})
        if self._wciecie(li) or not self._czy_klucz(li, 0):
            raise Niepewne(li + 1, "config to nie mapowanie kluczy od kolumny 0")
        self.li, self.k = li, 0
        m = self._mapa(0, gora=True)
        if (reszta := self._nastepny(self.li)) is not None:
            raise Niepewne(reszta + 1, "wiersz poza strukturą configu")
        return m

    # -- bloki
    def _czy_klucz(self, li: int, k: int) -> bool:
        """Czy od (li, k) zaczyna się klucz mapowania (zwykły albo w cudzysłowie, przed `: ` albo `:` na końcu)."""
        linia = self.w[li]
        if k >= len(linia):
            return False
        c = linia[k]
        if c == "?" and (k + 1 == len(linia) or linia[k + 1] == " "):
            return True                                  # klucz złożony: _klucz odmówi
        if c in "\"'":
            j = _koniec_cytatu(linia, k)
            if j < 0:
                return False
            while j < len(linia) and linia[j] == " ":
                j += 1
            return j < len(linia) and linia[j] == ":" and (j + 1 == len(linia) or linia[j + 1] == " ")
        if c in "[{&*!|>%@`#,]}" or (c in "-:" and (k + 1 == len(linia) or linia[k + 1] == " ")):
            return False
        j = k
        while (j := linia.find(":", j)) >= 0:
            if j + 1 == len(linia) or linia[j + 1] == " ":
                return " #" not in linia[k:j]
            j += 1
        return False

    def _klucz(self) -> tuple[str, bool]:
        linia, k, nr = self._l(), self.k, self.li + 1
        c = linia[k]
        if c == "?":
            raise Niepewne(nr, "klucz złożony (?)")
        if c in "&*!":
            raise Niepewne(nr, "kotwica, alias albo tag (&, *, !) przy kluczu")
        if c in "\"'":
            s = self._cytat()
            if s.wielowierszowy:
                raise Niepewne(nr, "klucz w cudzysłowie na kilka wierszy")
            linia, j = self._l(), self.k
            while j < len(linia) and linia[j] == " ":
                j += 1
            if j >= len(linia) or linia[j] != ":" or (j + 1 < len(linia) and linia[j + 1] != " "):
                raise Niepewne(nr, "po kluczu w cudzysłowie nie ma dwukropka")
            self.k = j + 1
            return s.tekst, True
        if c in WSKAZNIKI or (c in "-:" and (k + 1 == len(linia) or linia[k + 1] == " ")):
            raise Niepewne(nr, f"klucz nie może zaczynać się od {c!r}")
        j = k
        while True:
            j = linia.find(":", j)
            if j < 0:
                raise Niepewne(nr, "wiersz bez dwukropka po kluczu")
            if j + 1 == len(linia) or linia[j + 1] == " ":
                break
            j += 1
        tekst = linia[k:j]
        if " #" in tekst:
            raise Niepewne(nr, "komentarz przed dwukropkiem klucza")
        tekst = tekst.rstrip(" ")
        if tekst == "<<":
            raise Niepewne(nr, "scalanie kluczy (<<)")
        if not tekst:
            raise Niepewne(nr, "pusty klucz")
        if len(tekst) > MAKS_KLUCZ:
            raise Niepewne(nr, "klucz dłuższy niż 1024 znaki")
        _sprawdz_zwykly(tekst, nr)
        self.k = j + 1
        return tekst, False

    def _mapa(self, kol: int, gora: bool = False) -> Mapa:
        self._glebiej()
        m = Mapa({}, self.li + 1)
        while True:
            nr = self.li + 1
            klucz, cytowany = self._klucz()
            if gora and (cytowany or not ZWYKLY_KLUCZ.fullmatch(klucz)):
                raise Niepewne(nr, f"klucz najwyższego poziomu {klucz[:40]!r}: bramka czyta tylko zwykłe nazwy")
            wartosc = self._wartosc_klucza(kol)
            if klucz in m.pola:
                m.powtorzone.append(klucz)
                if gora:
                    raise Niepewne(nr, f"klucz {klucz} powtórzony (PyYAML wziąłby ostatni)")
            m.pola[klucz] = wartosc
            m.numery[klucz] = nr
            if cytowany:
                m.cytowane.add(klucz)
            nl = self._nastepny(self.li)
            if nl is None:
                break
            ind = self._wciecie(nl)
            if ind < kol:
                break
            if ind > kol:
                raise Niepewne(nl + 1, "wiersz wcięty głębiej niż klucze mapowania")
            if self._myslnik(nl, ind):
                break
            self.li, self.k = nl, ind
        self.glebokosc -= 1
        return m

    def _wartosc_klucza(self, kol: int):
        linia, k = self._l(), self.k
        while k < len(linia) and linia[k] == " ":
            k += 1
        self.k = k
        if k < len(linia) and linia[k] != "#":
            return self._w_wierszu(kol)
        self._koniec_wiersza()
        nl = self._nastepny(self.li)
        if nl is None:
            return None
        ind = self._wciecie(nl)
        if ind > kol:
            self.li, self.k = nl, ind
            return self._wezel(kol)
        if ind == kol and self._myslnik(nl, ind):
            self.li, self.k = nl, ind
            return self._lista(ind)
        return None

    def _wezel(self, kol: int):
        """Węzeł od początku wiersza (self.li, self.k): lista, mapowanie albo wartość."""
        if self._myslnik(self.li, self.k):
            return self._lista(self.k)
        if self._czy_klucz(self.li, self.k):
            return self._mapa(self.k)
        return self._w_wierszu(kol)

    def _lista(self, kol: int) -> Lista:
        self._glebiej()
        wynik = Lista([], self.li + 1)
        while True:
            linia, k = self._l(), self.k + 1
            while k < len(linia) and linia[k] == " ":
                k += 1
            self.k = k
            if k >= len(linia) or linia[k] == "#":
                self._koniec_wiersza()
                nl = self._nastepny(self.li)
                if nl is not None and self._wciecie(nl) > kol:
                    self.li, self.k = nl, self._wciecie(nl)
                    wynik.elementy.append(self._wezel(kol))
                else:
                    wynik.elementy.append(None)
            elif self._myslnik(self.li, k):
                wynik.elementy.append(self._lista(k))
            elif self._czy_klucz(self.li, k):
                wynik.elementy.append(self._mapa(k))
            else:
                wynik.elementy.append(self._w_wierszu(kol))
            nl = self._nastepny(self.li)
            if nl is None:
                break
            ind = self._wciecie(nl)
            if ind < kol:
                break
            if ind > kol:
                raise Niepewne(nl + 1, "wiersz wcięty głębiej niż elementy listy")
            if not self._myslnik(nl, ind):
                break
            self.li, self.k = nl, ind
        self.glebokosc -= 1
        return wynik

    # -- wartości
    def _w_wierszu(self, kol: int):
        linia, k, nr = self._l(), self.k, self.li + 1
        c = linia[k]
        if c in "&*!":
            raise Niepewne(nr, "kotwica, alias albo tag (&, *, !)")
        if c in "%@`,]}":
            raise Niepewne(nr, f"wartość nie może zaczynać się od {c!r}")
        if c == "?" and (k + 1 == len(linia) or linia[k + 1] == " "):
            raise Niepewne(nr, "klucz złożony (?)")
        if c == "-" and (k + 1 == len(linia) or linia[k + 1] == " "):
            raise Niepewne(nr, "element listy w miejscu wartości klucza")
        if c in "|>":
            return self._blokowy(kol)
        if c in "\"'":
            s = self._cytat()
            self._koniec_wiersza()
            return s
        if c in "[{":
            w = self._flow(0)
            self._koniec_wiersza()
            return w
        return self._zwykly(kol)

    def _zwykly(self, kol: int) -> Skalar:
        linia, k, nr = self._l(), self.k, self.li + 1
        j = k
        while j < len(linia):
            if linia[j] == "#" and linia[j - 1] == " ":
                break
            if linia[j] == ":" and (j + 1 == len(linia) or linia[j + 1] == " "):
                raise Niepewne(nr, "dwukropek ze spacją w zwykłej wartości (PyYAML: mapping values are not allowed)")
            j += 1
        tekst = linia[k:j].rstrip(" ")
        komentarz = j < len(linia)
        self.k = j
        self._koniec_wiersza()
        if komentarz:
            _sprawdz_zwykly(tekst, nr)
            return Skalar(tekst, "", nr)
        czesci, puste, li, wiele = [tekst], 0, self.li, False
        while li < len(self.w):
            s = self.w[li]
            if not s.strip(" "):
                puste, li = puste + 1, li + 1
                continue
            if self._znacznik(li) or self._wciecie(li) <= kol or s.lstrip(" ").startswith("#"):
                break
            tresc = s.strip(" ")
            if ": " in tresc or tresc.endswith(":") or " #" in tresc or tresc[:2] in ("- ", "-"):
                raise Niepewne(li + 1, "wartość na kilka wierszy z dwukropkiem, komentarzem albo myślnikiem")
            czesci.append("\n" * puste if puste else " ")
            czesci.append(tresc)
            puste, li, wiele = 0, li + 1, True
            self.li = li
        tekst = "".join(czesci)
        _sprawdz_zwykly(tekst, nr)
        return Skalar(tekst, "", nr, wiele)

    def _cytat(self) -> Skalar:
        """Skalar w cudzysłowie albo apostrofach od (self.li, self.k); może iść przez kilka wierszy (jak w PyYAML:
        złamanie wiersza to spacja, pusty wiersz to nowa linia, `\\` na końcu wiersza łączy bez spacji)."""
        q, nr = self._l()[self.k], self.li + 1
        wynik: list[str] = []
        li, k, wiele = self.li, self.k + 1, False
        while True:
            linia = self.w[li]
            biezacy: list[str] = []
            spacje = 0                                   # zwykłe spacje na końcu `biezacy` (bez spacji z ucieczki)
            ucieczka_konca = False
            while k < len(linia):
                c = linia[k]
                if q == "'":
                    if c == "'":
                        if k + 1 < len(linia) and linia[k + 1] == "'":
                            biezacy.append("'")
                            spacje, k = 0, k + 2
                            continue
                        self.li, self.k = li, k + 1
                        return Skalar("".join(wynik + biezacy), q, nr, wiele)
                    biezacy.append(c)
                    spacje = spacje + 1 if c == " " else 0
                    k += 1
                    continue
                if c == '"':
                    self.li, self.k = li, k + 1
                    return Skalar("".join(wynik + biezacy), q, nr, wiele)
                if c == "\\":
                    if k + 1 == len(linia):
                        ucieczka_konca = True
                        k += 1
                        break
                    e = linia[k + 1]
                    if e in UCIECZKI:
                        biezacy.append(UCIECZKI[e])
                        k += 2
                    elif e in KODY:
                        cyfry = linia[k + 2:k + 2 + KODY[e]]
                        if len(cyfry) != KODY[e] or not re.fullmatch(r"[0-9A-Fa-f]+", cyfry):
                            raise Niepewne(li + 1, f"zła sekwencja ucieczki \\{e}{cyfry}")
                        kod = int(cyfry, 16)
                        if 0xD800 <= kod <= 0xDFFF or kod > 0x10FFFF:
                            raise Niepewne(li + 1, f"sekwencja ucieczki \\{e}{cyfry} poza Unicode")
                        biezacy.append(chr(kod))
                        k += 2 + KODY[e]
                    else:
                        raise Niepewne(li + 1, f"nieznana sekwencja ucieczki \\{e}")
                    spacje = 0
                    continue
                biezacy.append(c)
                spacje = spacje + 1 if c == " " else 0
                k += 1
            # koniec wiersza w środku skalaru: zwykłe spacje przed złamaniem znikają (jak w PyYAML)
            wiele = True
            if not ucieczka_konca and spacje:
                del biezacy[-spacje:]
            wynik += biezacy
            li += 1
            puste = 0
            while li < len(self.w) and not self.w[li].strip(" "):
                puste, li = puste + 1, li + 1
            if li >= len(self.w):
                raise Niepewne(nr, "niezamknięty cudzysłów")
            if self._znacznik(li):
                raise Niepewne(li + 1, "znacznik dokumentu w środku cudzysłowu")
            wynik.append("\n" * puste if puste else ("" if ucieczka_konca else " "))
            k = self._wciecie(li)

    def _blokowy(self, kol: int) -> Skalar:
        linia, nr = self._l(), self.li + 1
        if not re.compile(r"[|>][+-]?(?: +#.*| *)$").match(linia, self.k):
            raise Niepewne(nr, "nagłówek skalaru blokowego ze wskaźnikiem wcięcia albo tekstem")
        styl, chomp = linia[self.k], linia[self.k + 1:self.k + 2]
        li, wciecie, ostatni = self.li + 1, None, self.li
        tresc: list = []                                 # None: pusty wiersz
        while li < len(self.w):
            s = self.w[li]
            if not s.strip(" "):
                tresc.append(s[wciecie:] if wciecie is not None and len(s) > wciecie else None)
                li += 1
                continue
            ind = self._wciecie(li)
            if wciecie is None:
                if ind <= kol:
                    break
                wciecie = ind
            if ind < wciecie:
                if ind > kol and not s.lstrip(" ").startswith("#"):
                    raise Niepewne(li + 1, "wiersz skalaru blokowego wcięty płycej niż jego treść")
                break
            tresc.append(s[wciecie:])
            ostatni, li = li, li + 1
        bez_konca = ostatni == len(self.w) - 1 and ostatni > self.li     # ostatni wiersz pliku bez znaku końca
        self.li, self.k = ostatni + 1, 0
        return Skalar(_sklej_blok(tresc, styl, chomp, bez_konca), styl, nr, True)

    def _biale_flow(self, nr: int) -> None:
        """Spacje, końce wierszy i komentarze w nawiasach; koniec pliku to niezamknięty nawias."""
        while True:
            if self.li >= len(self.w):
                raise Niepewne(nr, "niezamknięty nawias")
            linia = self.w[self.li]
            while self.k < len(linia) and linia[self.k] == " ":
                self.k += 1
            if self.k < len(linia) and not (linia[self.k] == "#" and (self.k == 0 or linia[self.k - 1] == " ")):
                return
            self.li, self.k = self.li + 1, 0
            if self.li < len(self.w) and self._znacznik(self.li):
                raise Niepewne(self.li + 1, "znacznik dokumentu w środku nawiasu")

    def _flow(self, glebokosc: int):
        if glebokosc > MAKS_GLEBOKOSC:
            raise Niepewne(self.li + 1, "za głębokie zagnieżdżenie nawiasów")
        otw, nr = self._l()[self.k], self.li + 1
        zam = "]" if otw == "[" else "}"
        self.k += 1
        lista, mapa = Lista([], nr, blokowa=False), Mapa({}, nr, blokowa=False)
        while True:
            self._biale_flow(nr)
            if self._l()[self.k] == zam:
                self.k += 1
                break
            klucz = self._flow_wezel(glebokosc)
            wiersz_klucza = self.li
            self._biale_flow(nr)
            linia, para, wartosc = self._l(), False, None
            if linia[self.k] == ":" and (self.k + 1 == len(linia) or linia[self.k + 1] in " ,[]{}"
                                         or (isinstance(klucz, Skalar) and klucz.styl in ("'", '"'))):
                if self.li != wiersz_klucza or (isinstance(klucz, Skalar) and klucz.wielowierszowy):
                    raise Niepewne(self.li + 1, "klucz w nawiasie i jego dwukropek w różnych wierszach")
                if isinstance(klucz, Skalar) and len(klucz.tekst) > MAKS_KLUCZ:
                    raise Niepewne(self.li + 1, "klucz dłuższy niż 1024 znaki")
                self.k += 1
                para = True
                self._biale_flow(nr)
                if self._l()[self.k] not in ",]}":
                    wartosc = self._flow_wezel(glebokosc)
                    self._biale_flow(nr)
            if para or otw == "{":
                if not isinstance(klucz, Skalar):
                    raise Niepewne(self.li + 1, "klucz złożony w nawiasach")
                cel = Mapa({}, nr, blokowa=False) if otw == "[" else mapa
                if klucz.tekst in cel.pola:
                    cel.powtorzone.append(klucz.tekst)
                cel.pola[klucz.tekst] = wartosc
                cel.numery[klucz.tekst] = self.li + 1
                if otw == "[":
                    lista.elementy.append(cel)
            else:
                lista.elementy.append(klucz)
            c = self._l()[self.k]
            if c == ",":
                self.k += 1
                continue
            if c == zam:
                self.k += 1
                break
            raise Niepewne(self.li + 1, f"w nawiasie po wartości oczekiwany przecinek albo {zam!r}")
        return lista if otw == "[" else mapa

    def _flow_wezel(self, glebokosc: int):
        linia, k, nr = self._l(), self.k, self.li + 1
        c = linia[k]
        if c in "&*!":
            raise Niepewne(nr, "kotwica, alias albo tag (&, *, !) w nawiasie")
        if c in "[{":
            return self._flow(glebokosc + 1)
        if c in "\"'":
            return self._cytat()
        # w nawiasie zwykły skalar nie zaczyna się od `?` ani `:`, a `-` tylko bez spacji po (check_plain)
        if c in WSKAZNIKI or c in "?:" or (c == "-" and (k + 1 == len(linia) or linia[k + 1] == " ")):
            raise Niepewne(nr, f"w nawiasie wartość nie może zaczynać się od {c!r}")
        j = k
        while j < len(linia):
            ch = linia[j]
            if ch in ",?[]{}" or (ch == ":" and (j + 1 == len(linia) or linia[j + 1] in " ,[]{}")):
                break
            if ch == "#" and linia[j - 1] == " ":
                break
            j += 1
        tekst = linia[k:j].rstrip(" ")
        if not tekst:
            raise Niepewne(nr, "pusta wartość w nawiasie")
        _sprawdz_zwykly(tekst, nr)
        self.k = j
        return Skalar(tekst, "", nr)


def _sprawdz_zwykly(tekst: str, nr: int) -> None:
    """Zwykły skalar, z którym PyYAML zrobi coś innego niż napis: `=` i `<<` (znaczniki bez konstruktora poza
    scalaniem), daty (bramka ich nie czyta) i liczby, których konstruktor PyYAML nie przyjmie (np. `0x_`, `.__`):
    przy błędzie Hermes wziąłby ostatnią dobrą kopię configu, której bramka nie widzi."""
    if tekst in ("=", "<<"):
        raise Niepewne(nr, f"wartość {tekst!r} (dla PyYAML to znacznik specjalny)")
    if _DATA.fullmatch(tekst):
        raise Niepewne(nr, f"data {tekst!r} (bramka nie czyta dat)")
    liczba = _INT.fullmatch(tekst) is not None
    if not liczba and not _FLOAT.fullmatch(tekst):
        return
    v = tekst.replace("_", "") if liczba else tekst.replace("_", "").lower()
    if v and v[0] in "+-":
        v = v[1:]
    try:
        if liczba:
            if v.startswith("0b"):
                int(v[2:], 2)
            elif v.startswith("0x"):
                int(v[2:], 16)
            elif v.startswith("0") and v != "0":
                int(v, 8)
            else:
                [int(czesc) for czesc in v.split(":")]
        elif v not in (".inf", ".nan"):
            [float(czesc) for czesc in v.split(":")]
    except ValueError:
        raise Niepewne(nr, f"liczba {tekst!r}, której PyYAML nie zbuduje") from None


def _sklej_blok(linie: list, styl: str, chomp: str, bez_konca: bool = False) -> str:
    """Treść skalaru blokowego jak w PyYAML (yaml/scanner.py, scan_block_scalar): `>` składa wiersze spacją (poza
    wierszami wciętymi głębiej i pustymi), `|` zostawia złamania; `-` bez końcowego złamania, `+` z pustymi
    wierszami na końcu, bez wskaźnika jedno złamanie. `linie`: treść bez wcięcia, None to pusty wiersz;
    `bez_konca`: ostatni wiersz treści kończy plik bez znaku końca wiersza."""
    kawalki: list[str] = []
    zlamania: list[str] = []
    i = 0
    while i < len(linie) and linie[i] is None:
        zlamania.append("\n")
        i += 1
    zlamanie = ""
    while i < len(linie):
        kawalki += zlamania
        zlamania = []
        biezacy = linie[i]
        bez_spacji = not biezacy.startswith(" ")
        kawalki.append(biezacy)
        i += 1
        zlamanie = "" if bez_konca and i == len(linie) else "\n"
        while i < len(linie) and linie[i] is None:
            zlamania.append("\n")
            i += 1
        if i < len(linie):
            if styl == ">" and bez_spacji and not linie[i].startswith(" "):
                if not zlamania:
                    kawalki.append(" ")
            else:
                kawalki.append(zlamanie)
    if chomp != "-":
        kawalki.append(zlamanie)
    if chomp == "+":
        kawalki += zlamania
    return "".join(kawalki)


def _koniec_cytatu(linia: str, k: int) -> int:
    """Pozycja za cudzysłowem zamykającym skalar zaczęty w `k` albo -1, gdy nie zamyka się w tym wierszu."""
    q, j = linia[k], k + 1
    while j < len(linia):
        if q == "'" and linia[j] == "'":
            if j + 1 < len(linia) and linia[j + 1] == "'":
                j += 2
                continue
            return j + 1
        if q == '"' and linia[j] == "\\":
            j += 2
            continue
        if q == '"' and linia[j] == '"':
            return j + 1
        j += 1
    return -1


def czytaj(tekst: str) -> Mapa:
    """Config jako Mapa najwyższego poziomu albo Niepewne (z numerem wiersza i powodem)."""
    return _Czytnik(tekst).dokument()


# ---------------------------------------------------------------- zgody tak, jak przeczyta je Hermes

def _pewny(w, sciezka: str, nr: int) -> Skalar:
    if not isinstance(w, Skalar):
        raise Niepewne(nr, f"{sciezka} to nie prosta wartość")
    if w.wielowierszowy:
        raise Niepewne(w.nr, f"{sciezka}: wartość na kilka wierszy")
    if "${" in w.tekst:
        raise Niepewne(w.nr, f"{sciezka}: zmienna środowiska w wartości (Hermes rozwija ${{…}} ze swojego otoczenia)")
    return w


def problemy_zgod(m: Mapa, *, nakladka: bool = False) -> list[Problem]:
    """Powody, dla których Hermes z tym configiem nie pyta człowieka o każde działanie. `nakladka`: config
    administratora (wygrywa tylko tam, gdzie ma klucz), więc brak approvals.mode nie jest w nim błędem."""
    wynik: list[Problem] = []
    brak_trybu = Problem("zgody_nie_reczne", "brak approvals.mode: Hermes bierze wtedy domyślny tryb smart (zgody "
                                             "ocenia model); profil rąk potrzebuje approvals.mode: manual")
    a = m.pola.get("approvals")
    if a is None:
        return wynik if nakladka else [brak_trybu]
    if not isinstance(a, Mapa) or not a.blokowa:
        raise Niepewne(m.numery.get("approvals", 0), "approvals to nie mapowanie kluczy w wierszach (bramka nie "
                                                       "czyta zgód w nawiasach {…})")
    if a.powtorzone:
        raise Niepewne(a.numery.get(a.powtorzone[0], a.nr), f"approvals.{a.powtorzone[0]} powtórzony")
    if a.cytowane:
        raise Niepewne(a.nr, "klucz w cudzysłowie w approvals")
    if "mode" not in a.pola:
        if not nakladka:
            wynik.append(brak_trybu)
    else:
        s = _pewny(a.pola["mode"], "approvals.mode", a.numery["mode"])
        rodzaj, w = s.wartosc()
        if rodzaj == "bool":
            tryb = "manual" if w else "off"
        elif rodzaj == "str":
            tryb = str(w).strip().lower()
        else:
            raise Niepewne(s.nr, f"approvals.mode: {s.tekst or 'brak wartości'!r} (Hermes zgadłby tryb)")
        if tryb == "off":
            wynik.append(Problem("zgody_wylaczone", f"approvals.mode: {s.tekst} (dla Hermesa to off: przepuszcza "
                                                    "wszystko bez pytania)"))
        elif tryb == "smart":
            wynik.append(Problem("zgody_nie_reczne", "approvals.mode: smart (zgody ocenia model); na ekranie "
                                                     "właściciela każde działanie zatwierdza człowiek: manual"))
        elif tryb != "manual":
            wynik.append(Problem("zgody_nie_reczne", f"approvals.mode: nieznana wartość {s.tekst[:30]!r} (Hermes "
                                                     "zgadłby manual); wpisz manual"))
    for klucz in TRYBY_BEZ_CZLOWIEKA:
        if klucz not in a.pola:
            continue                                  # domyślnie deny
        s = _pewny(a.pola[klucz], f"approvals.{klucz}", a.numery[klucz])
        rodzaj, w = s.wartosc()
        if rodzaj == "str" and str(w).lower().strip() in ZATWIERDZA_SAM:
            wynik.append(Problem("zgody_bez_czlowieka", f"approvals.{klucz}: {s.tekst} (bez człowieka: rutyna, "
                                                        "-q, webhook, Hermes zatwierdza sam); ma być deny"))
    return wynik


def stale_zgody(m: Mapa) -> list[str]:
    """Klucze `cua:` w command_allowlist (Hermes porównuje je bez celu, więc na ekranie właściciela żadna stała zgoda
    nie może obowiązywać). Lista w innej postaci niż lista napisów to Niepewne."""
    if m.pola.get("command_allowlist") is None:
        return []
    w, nr = m.pola["command_allowlist"], m.numery.get("command_allowlist", 0)
    if isinstance(w, Skalar):
        if w.wartosc()[0] == "null":
            return []
        if znalezione := CUA.findall(w.tekst):
            return sorted(set(znalezione))
        raise Niepewne(nr, "command_allowlist jako napis (stara postać, Hermes czyta go jeszcze raz jako YAML)")
    if not isinstance(w, Lista):
        raise Niepewne(nr, "command_allowlist to nie lista")
    wynik: list[str] = []
    for e in w.elementy:
        if not isinstance(e, Skalar):
            raise Niepewne(nr, "command_allowlist: element, który nie jest napisem")
        wynik += CUA.findall(e.tekst)
    return sorted(set(wynik))


def zgody_w_tekscie(tekst: str) -> list[str]:
    """Klucze `cua:` w tekście poza komentarzami (także zapisane sekwencją ucieczki): opis odmowy, gdy configu nie
    da się przeczytać (odmowa i tak zapada, bo plik jest niepewny)."""
    wynik: list[str] = []
    for linia in re.split(r"\r\n|\r|\n", tekst):
        if linia.lstrip(" ").startswith("#"):
            continue
        kod = re.split(r"\s#", linia, maxsplit=1)[0]
        wynik += CUA.findall(kod)
    return sorted(set(wynik))


def wartosc(m: Mapa, *sciezka: str):
    """Węzeł pod `sciezka` (np. "computer_use", "permission_mode") albo None."""
    w = m
    for klucz in sciezka:
        if not isinstance(w, Mapa):
            return None
        w = w.pola.get(klucz)
    return w


def napis(m: Mapa, *sciezka: str) -> str | None:
    """Prosta wartość pod `sciezka` jako tekst (bez zmiennych środowiska i wielu wierszy) albo None."""
    w = wartosc(m, *sciezka)
    if not isinstance(w, Skalar) or w.wielowierszowy or "${" in w.tekst:
        return None
    rodzaj, x = w.wartosc()
    return x if rodzaj == "str" else None
