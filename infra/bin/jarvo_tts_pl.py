"""Polski normalizator tekstu lektora (jarvo-tts, głosy pl-PL-Matcha-*): liczby, daty, godziny, kwoty, procenty,
jednostki, numery telefonów, skróty i skrótowce → słowa, zanim tekst trafi do fonemizera.

espeak-ng czyta cyfry tylko w mianowniku („od 5 zł” → „od pięć złotych”), daty jak liczby, a skrótowce jak słowa
(„PDF” → „pdf”). Tu: liczebniki z odmianą tam, gdzie przypadek widać po przyimku (od/do/około → dopełniacz,
„w 2026 r.” → miejscownik), zgoda rzeczownika z liczbą (1 złoty, 2 złote, 5 złotych, 2,5 złotego), daty i lata
jako liczebniki porządkowe, skrótowce litera po literze po polsku („PDF” → „pe de ef”), „AI” → „ej aj”.
Słowa w klamrach („{feedback}”) zostają bez zmian: to angielskie wstawki dla fonemizera (jarvo_tts_matcha.py).

Czysty Python bez zależności (testy: tests/test_lektor_pl.py). Kod Jarvo; listę skrótów z polish_cleaners.py
Matcha-TTS-PL v2 (machinekind, CC BY-SA 4.0) rozszerzamy tu o kolejne, a sam port fonemizera jest w jarvo_tts_matcha.py.
"""

from __future__ import annotations

import re

# ------------------------------------------------------------------ liczebniki główne

_JEDN = ["zero", "jeden", "dwa", "trzy", "cztery", "pięć", "sześć", "siedem", "osiem", "dziewięć"]
_NASCIE = ["dziesięć", "jedenaście", "dwanaście", "trzynaście", "czternaście", "piętnaście", "szesnaście",
           "siedemnaście", "osiemnaście", "dziewiętnaście"]
_DZIES = ["", "", "dwadzieścia", "trzydzieści", "czterdzieści", "pięćdziesiąt", "sześćdziesiąt", "siedemdziesiąt",
          "osiemdziesiąt", "dziewięćdziesiąt"]
_SETKI = ["", "sto", "dwieście", "trzysta", "czterysta", "pięćset", "sześćset", "siedemset", "osiemset", "dziewięćset"]
# dopełniacz (od pięciu, do dwudziestu dwóch)
_JEDN_D = ["zera", "jednego", "dwóch", "trzech", "czterech", "pięciu", "sześciu", "siedmiu", "ośmiu", "dziewięciu"]
_NASCIE_D = ["dziesięciu", "jedenastu", "dwunastu", "trzynastu", "czternastu", "piętnastu", "szesnastu",
             "siedemnastu", "osiemnastu", "dziewiętnastu"]
_DZIES_D = ["", "", "dwudziestu", "trzydziestu", "czterdziestu", "pięćdziesięciu", "sześćdziesięciu",
            "siedemdziesięciu", "osiemdziesięciu", "dziewięćdziesięciu"]
_SETKI_D = ["", "stu", "dwustu", "trzystu", "czterystu", "pięciuset", "sześciuset", "siedmiuset", "ośmiuset",
            "dziewięciuset"]
# rzędy wielkości: (1, 2–4, 5+) w mianowniku, (1, liczba mnoga) w dopełniaczu
_RZEDY = [None, ("tysiąc", "tysiące", "tysięcy"), ("milion", "miliony", "milionów"),
          ("miliard", "miliardy", "miliardów"), ("bilion", "biliony", "bilionów")]
_RZEDY_D = [None, ("tysiąca", "tysięcy"), ("miliona", "milionów"), ("miliarda", "miliardów"), ("biliona", "bilionów")]


def odmiana(n: int, formy: tuple) -> str:
    """Forma rzeczownika po liczbie: (1, 2–4, 5+); 12–14 i 22, 25… jak 5+ (dwanaście złotych, dwadzieścia dwa złote)."""
    if n == 1:
        return formy[0]
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return formy[1]
    return formy[2]


def _trojka(n: int, dop: bool, rodzaj: str, sama: bool) -> list[str]:
    """0 < n < 1000 → słowa. `sama`: ta trójka to cała liczba (tylko wtedy „jeden” odmienia się przez rodzaj)."""
    s, r = divmod(n, 100)
    out = [(_SETKI_D if dop else _SETKI)[s]] if s else []
    if 10 <= r < 20:
        out.append((_NASCIE_D if dop else _NASCIE)[r - 10])
        return out
    d, j = divmod(r, 10)
    if d:
        out.append((_DZIES_D if dop else _DZIES)[d])
    if j:
        if j == 1 and not (sama and n == 1):
            out.append("jeden")                                   # dwadzieścia jeden (minut, złotych): bez odmiany
        elif j == 1:
            out.append({"m": "jednego", "z": "jednej", "n": "jednego"}[rodzaj] if dop
                       else {"m": "jeden", "z": "jedna", "n": "jedno"}[rodzaj])
        elif j == 2 and rodzaj == "z" and not dop:
            out.append("dwie")                                    # dwie minuty, dwadzieścia dwie godziny
        else:
            out.append((_JEDN_D if dop else _JEDN)[j])
    return out


def liczebnik(n: int, dop: bool = False, rodzaj: str = "m") -> str:
    """Liczebnik główny: mianownik (dop=False) albo dopełniacz; rodzaj m/z/n wpływa na 1 i 2."""
    if n < 0:
        return "minus " + liczebnik(-n, dop, rodzaj)
    if n == 0:
        return "zera" if dop else "zero"
    if n >= 10 ** 15:
        return cyfry(str(n))
    grupy, k = [], 0
    while n:
        n, g = divmod(n, 1000)
        grupy.append((k, g))
        k += 1
    slowa: list[str] = []
    for k, g in reversed(grupy):
        if not g:
            continue
        if k == 0:
            slowa += _trojka(g, dop, rodzaj, sama=len(slowa) == 0)
        elif g == 1:
            slowa.append(_RZEDY_D[k][0] if dop else _RZEDY[k][0])     # tysiąc, nie „jeden tysiąc”
        else:
            slowa += _trojka(g, dop, "m", sama=False)
            slowa.append(_RZEDY_D[k][1] if dop else odmiana(g, _RZEDY[k]))
    return " ".join(slowa)


def cyfry(s: str) -> str:
    """Cyfra po cyfrze: „007” → „zero zero siedem”."""
    return " ".join(_JEDN[int(c)] for c in s if c.isdigit())


def grupa(s: str) -> str:
    """Grupa cyfr numeru telefonu: zera z przodu osobno („05” → „zero pięć”), reszta jako liczba."""
    zera = len(s) - len(s.lstrip("0"))
    reszta = s[zera:]
    return " ".join(["zero"] * zera + ([liczebnik(int(reszta))] if reszta else []))


# ------------------------------------------------------------------ liczebniki porządkowe

_POR_JEDN = ["", "pierwsz", "drug", "trzec", "czwart", "piąt", "szóst", "siódm", "ósm", "dziewiąt"]
_POR_NASCIE = ["dziesiąt", "jedenast", "dwunast", "trzynast", "czternast", "piętnast", "szesnast", "siedemnast",
               "osiemnast", "dziewiętnast"]
_POR_DZIES = ["", "", "dwudziest", "trzydziest", "czterdziest", "pięćdziesiąt", "sześćdziesiąt", "siedemdziesiąt",
              "osiemdziesiąt", "dziewięćdziesiąt"]
_POR_SETKI = ["", "setn", "dwusetn", "trzechsetn", "czterechsetn", "pięćsetn", "sześćsetn", "siedemsetn",
              "osiemsetn", "dziewięćsetn"]
_POR_TYS = ["", "", "dwu", "trzy", "cztero", "pięcio", "sześcio", "siedmio", "ośmio", "dziewięcio"]
# formy: m = mianownik męski (pierwszy), d = dopełniacz męski/nijaki (pierwszego), ms = miejscownik męski (pierwszym),
#        zm = mianownik żeński (pierwsza), zd = dopełniacz/miejscownik żeński (pierwszej), zn = biernik żeński (pierwszą)
_KONC = {"m": "y", "d": "ego", "ms": "ym", "zm": "a", "zd": "ej", "zn": "ą"}
_KONC_MIEKKIE = {"m": "i", "d": "iego", "ms": "im", "zm": "a", "zd": "iej", "zn": "ą"}      # drugi, drugiego, druga
_KONC_TRZEC = {"m": "i", "d": "iego", "ms": "im", "zm": "ia", "zd": "iej", "zn": "ią"}     # trzeci, trzecia


def _por(rdzen: str, forma: str) -> str:
    if rdzen == "trzec":
        return rdzen + _KONC_TRZEC[forma]
    return rdzen + (_KONC_MIEKKIE if rdzen[-1] in "gk" else _KONC)[forma]


def porzadkowy(n: int, forma: str = "m") -> str:
    """Liczebnik porządkowy (1–9999): tysiące i setki główne, porządkowe tylko ostatnie człony
    (2026 → „dwa tysiące dwudziestego szóstego”, 1900 → „tysiąc dziewięćsetnego”, 2000 → „dwutysięcznego”)."""
    if not 0 < n < 10000:
        return liczebnik(n)
    t, r = divmod(n, 1000)
    if r == 0:
        return _por(_POR_TYS[t] + "tysięczn", forma)
    slowa = [liczebnik(t * 1000)] if t else []
    s, r2 = divmod(r, 100)
    if s:
        slowa.append(_por(_POR_SETKI[s], forma) if r2 == 0 else _SETKI[s])
    if r2:
        if r2 < 10:
            slowa.append(_por(_POR_JEDN[r2], forma))
        elif r2 < 20:
            slowa.append(_por(_POR_NASCIE[r2 - 10], forma))
        else:
            d, j = divmod(r2, 10)
            slowa.append(_por(_POR_DZIES[d], forma))
            if j:
                slowa.append(_por(_POR_JEDN[j], forma))
    return " ".join(slowa)


def rzymska(s: str) -> int:
    wart = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    n = 0
    for a, b in zip(s, s[1:] + " "):
        n += -wart[a] if wart.get(b, 0) > wart[a] else wart[a]
    return n


# ------------------------------------------------------------------ jednostki i waluty po liczbie

# skrót → (1, 2–4, 5+, dopełniacz l. poj. po ułamku, rodzaj liczebnika)
JEDNOSTKI = {
    "zł": ("złoty", "złote", "złotych", "złotego", "m"),
    "pln": ("złoty", "złote", "złotych", "złotego", "m"),
    "gr": ("grosz", "grosze", "groszy", "grosza", "m"),
    "€": ("euro", "euro", "euro", "euro", "n"),
    "eur": ("euro", "euro", "euro", "euro", "n"),
    "euro": ("euro", "euro", "euro", "euro", "n"),
    "$": ("dolar", "dolary", "dolarów", "dolara", "m"),
    "usd": ("dolar", "dolary", "dolarów", "dolara", "m"),
    "%": ("procent", "procent", "procent", "procent", "m"),
    "proc.": ("procent", "procent", "procent", "procent", "m"),
    "km/h": ("kilometr na godzinę", "kilometry na godzinę", "kilometrów na godzinę", "kilometra na godzinę", "m"),
    "km": ("kilometr", "kilometry", "kilometrów", "kilometra", "m"),
    "cm": ("centymetr", "centymetry", "centymetrów", "centymetra", "m"),
    "mm": ("milimetr", "milimetry", "milimetrów", "milimetra", "m"),
    "m": ("metr", "metry", "metrów", "metra", "m"),
    "kg": ("kilogram", "kilogramy", "kilogramów", "kilograma", "m"),
    "g": ("gram", "gramy", "gramów", "grama", "m"),
    "ml": ("mililitr", "mililitry", "mililitrów", "mililitra", "m"),
    "l": ("litr", "litry", "litrów", "litra", "m"),
    "tb": ("terabajt", "terabajty", "terabajtów", "terabajta", "m"),
    "gb": ("gigabajt", "gigabajty", "gigabajtów", "gigabajta", "m"),
    "mb": ("megabajt", "megabajty", "megabajtów", "megabajta", "m"),
    "kb": ("kilobajt", "kilobajty", "kilobajtów", "kilobajta", "m"),
    "°c": ("stopień Celsjusza", "stopnie Celsjusza", "stopni Celsjusza", "stopnia Celsjusza", "m"),
    "°": ("stopień", "stopnie", "stopni", "stopnia", "m"),
    "h": ("godzina", "godziny", "godzin", "godziny", "z"),
    "godz.": ("godzina", "godziny", "godzin", "godziny", "z"),
    "min.": ("minuta", "minuty", "minut", "minuty", "z"),
    "min": ("minuta", "minuty", "minut", "minuty", "z"),
    "sek.": ("sekunda", "sekundy", "sekund", "sekundy", "z"),
    "s": ("sekunda", "sekundy", "sekund", "sekundy", "z"),
    "x": ("raz", "razy", "razy", "razy", "m"),
    "×": ("raz", "razy", "razy", "razy", "m"),
}
# częste rzeczowniki żeńskie po liczbie: mianownik l. poj. i mnogiej (= dopełniacz l. poj.), np. minuta/minuty
_ZENSKIE_RDZENIE = ("minut", "godzin", "sekund", "osob", "sztuk", "stron", "firm", "dob", "zmian", "klas", "metod",
                    "zasad", "scen", "kart", "liczb", "liter", "kaw", "herbat", "płyt", "warstw", "ulic", "szkoł",
                    "umow", "faktur", "reklam", "grafik", "procedur", "tabel", "kolumn", "szans", "prób", "rund",
                    "nagrod", "cen", "mark", "usług", "ofert", "notatk", "platform", "kamer", "spółk", "książk",
                    "lampk", "butelk", "łyżk", "córk", "siostr", "kobiet", "dziewczyn", "złotówk", "minutk", "gwiazdk",
                    "sylab", "drog", "ścieżk", "nog", "głow")
ZENSKIE = ({r + "a" for r in _ZENSKIE_RDZENIE} | {r + ("i" if r[-1] in "kg" else "y") for r in _ZENSKIE_RDZENIE}
           | {"wersja", "wersje", "wersji", "opcja", "opcje", "opcji", "aplikacja", "aplikacje", "aplikacji",
              "lekcja", "lekcje", "lekcji", "funkcja", "funkcje", "funkcji", "kategoria", "kategorie", "kategorii",
              "linia", "linie", "linii", "porcja", "porcje", "porcji", "sekcja", "sekcje", "sekcji", "decyzja",
              "decyzje", "decyzji", "kampania", "kampanie", "kampanii", "historia", "historie", "historii",
              "rzecz", "rzeczy", "noc", "noce", "nocy", "część", "części", "wiadomość", "wiadomości",
              "odpowiedź", "odpowiedzi", "chwila", "chwile", "chwili", "rola", "role", "roli", "dłoń", "dłonie"})
# mnożniki: tys. / mln / mld (po nich jednostka zawsze w dopełniaczu l. mnogiej: 2 mln złotych)
MNOZNIKI = {"tys.": 1, "tys": 1, "mln": 2, "mld": 3, "bln": 4}
# przyimki z dopełniaczem: liczba po nich w dopełniaczu (od pięciu, do dwudziestu procent)
PRZYIMKI_D = {"od", "do", "około", "ok.", "bez", "dla", "u", "wśród", "spośród", "oprócz", "zamiast", "według", "wg",
              "powyżej", "poniżej", "blisko", "niespełna", "kilku", "spod", "sprzed", "znad", "zza", "naprzeciw"}

_LIT = "A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż"
# jednostki z kilku znaków bez względu na wielkość liter (GB, gb, °C, PLN), jednoliterowe dokładnie (m, g, s, h, l)
_JEDN_RX = "|".join(re.escape(k) if len(k) < 2 else f"(?i:{re.escape(k)})"
                    for k in sorted(JEDNOSTKI, key=len, reverse=True))
_MNOZ_RX = r"tys\.|tys\b|mln\b|mld\b|bln\b"
_LICZBA = r"\d+(?:,\d+)?"


def _ulamek(calk: int, ulam: str, dop: bool, rodzaj: str) -> str:
    """2,5 → „dwa i pół”, 1,5 → „półtora/półtorej”, 3,14 → „trzy przecinek czternaście”."""
    if ulam == "5":
        if calk == 1:
            return "półtorej" if rodzaj == "z" else "półtora"
        return liczebnik(calk, dop, rodzaj) + " i pół"
    return f"{liczebnik(calk, dop, rodzaj)} przecinek {grupa(ulam)}"


def _slowo_przed(tekst: str, poz: int) -> str:
    m = re.search(rf"([{_LIT}]+\.?)\s*$", tekst[:poz])
    return m.group(1).lower() if m else ""


def _kwota(liczba: str, mnoznik: str | None, jedn: str | None, dop: bool) -> str:
    """Liczba (z ułamkiem po przecinku) z mnożnikiem i jednostką w zgodzie: 1 zł, 2 zł, 2,5 mln zł, od 5 %."""
    calk_s, _, ulam = liczba.partition(",")
    calk = int(calk_s)
    j = JEDNOSTKI.get(jedn.lower()) if jedn else None
    k = MNOZNIKI.get(mnoznik.lower()) if mnoznik else None
    rodzaj = "m" if k else (j[4] if j else "m")
    if ulam:
        slowa = [_ulamek(calk, ulam.rstrip("0") or "0", dop, rodzaj)]
        if k:
            slowa.append(_RZEDY_D[k][0])                        # dwa i pół miliona
        if j:
            slowa.append(j[2] if k else j[3])                   # … złotych / dwa i pół złotego
        return " ".join(slowa)
    if k:
        if calk == 1:
            slowa = [_RZEDY_D[k][0] if dop else _RZEDY[k][0]]
        else:
            slowa = [liczebnik(calk, dop), _RZEDY_D[k][1] if dop else odmiana(calk, _RZEDY[k])]
        if j:
            slowa.append(j[2])
        return " ".join(slowa)
    slowa = [liczebnik(calk, dop, rodzaj)]
    if j:
        if dop:
            slowa.append(j[3] if calk == 1 else j[2])           # od jednego złotego, do pięciu złotych
        else:
            slowa.append(odmiana(calk, j[:3]))
    return " ".join(slowa)


# ------------------------------------------------------------------ daty i godziny

MIESIACE = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września",
            "października", "listopada", "grudnia"]
_MIES_RX = "|".join(MIESIACE)
PRZYIMKI_MS = {"w", "we", "o", "przy", "po"}                  # w 2026 roku → miejscownik


def _data(d: int, m: int, r: int | None) -> str | None:
    if not (1 <= d <= 31 and 1 <= m <= 12):
        return None
    out = f"{porzadkowy(d, 'd')} {MIESIACE[m - 1]}"
    return out + (f" {porzadkowy(r, 'd')} roku" if r else "")


def _godzina_forma(przyimek: str) -> str:
    if przyimek in ("o", "po", "od", "do", "około", "ok.", "godzinie", "godziny"):
        return "zd"                                               # o piętnastej, do piętnastej
    if przyimek in ("przed", "za", "między", "na", "pomiędzy"):
        return "zn"                                               # przed piętnastą
    return "zm"                                                   # piętnasta trzydzieści


def _godzina(h: int, mi: int, przyimek: str) -> str:
    out = porzadkowy(h, _godzina_forma(przyimek)) if h else "zero"
    if mi:
        out += " " + (grupa(f"{mi:02d}") if mi < 10 else liczebnik(mi))
    return out


# ------------------------------------------------------------------ skróty i skrótowce

# skrót → rozwinięcie; przy skrócie z kropką na końcu zdania kropka zostaje (koniec zdania dla lektora)
SKROTY = {
    "np.": "na przykład", "m.in.": "między innymi", "itd.": "i tak dalej", "itp.": "i tym podobne",
    "tzn.": "to znaczy", "tj.": "to jest", "tzw.": "tak zwany", "ok.": "około", "wg": "według", "ds.": "do spraw",
    "im.": "imienia", "ul.": "ulica", "al.": "aleja", "os.": "osiedle", "nr": "numer", "nr.": "numer",
    "tel.": "telefon", "dr": "doktor", "dr.": "doktor", "prof.": "profesor", "inż.": "inżynier", "mgr": "magister",
    "św.": "święty", "pt.": "pod tytułem", "zob.": "zobacz", "por.": "porównaj", "maks.": "maksymalnie",
    "godz.": "godzina", "proc.": "procent", "tys.": "tysięcy", "mln": "milionów", "mld": "miliardów",
    "zł": "złotych", "gr": "groszy", "ws.": "w sprawie", "jw.": "jak wyżej", "etc.": "et cetera", "vs": "kontra",
    "vs.": "kontra", "min.": "minimum",
}
# skróty, po których zdanie często się kończy (tylko po nich kropka zostaje jako koniec zdania)
SKROTY_KONCOWE = {"itd.", "itp.", "etc.", "jw.", "tys.", "proc.", "maks.", "min."}
# po przyimku inna forma (na ul. Długiej → na ulicy; o godz. → o godzinie)
SKROTY_PO = {
    ("ul.", "na"): "ulicy", ("ul.", "przy"): "ulicy", ("ul.", "z"): "ulicy", ("ul.", "do"): "ulicy",
    ("al.", "na"): "alei", ("al.", "przy"): "alei", ("al.", "z"): "alei", ("al.", "do"): "alei",
    ("godz.", "o"): "godzinie", ("godz.", "po"): "godzinie", ("godz.", "od"): "godziny", ("godz.", "do"): "godziny",
    ("godz.", "około"): "godziny", ("godz.", "ok."): "godziny", ("godz.", "przed"): "godziną", ("godz.", "za"): "godzinę",
    ("nr", "pod"): "numerem", ("nr", "z"): "numerem", ("nr.", "pod"): "numerem",
}
# litery po polsku (do czytania skrótowców)
LITERY = {"A": "a", "Ą": "ą", "B": "be", "C": "ce", "Ć": "cie", "D": "de", "E": "e", "Ę": "ę", "F": "ef", "G": "gie",
          "H": "ha", "I": "i", "J": "jot", "K": "ka", "L": "el", "Ł": "eł", "M": "em", "N": "en", "Ń": "eń", "O": "o",
          "Ó": "o kreskowane", "P": "pe", "Q": "ku", "R": "er", "S": "es", "Ś": "eś", "T": "te", "U": "u",
          "V": "fau", "W": "wu", "X": "iks", "Y": "igrek", "Z": "zet", "Ź": "ziet", "Ż": "żet"}
# skrótowce czytane inaczej niż litera po literze (po angielsku albo jak słowo)
SKROTOWCE = {"AI": "ej aj", "OK": "okej", "CEO": "si i oł", "PR": "pi ar", "IT": "aj ti", "VAT": "wat", "PIN": "pin",
             "NATO": "nato", "NASA": "nasa", "ZUS": "zus", "GUS": "gus", "NIK": "nik", "PIT": "pit", "NIP": "nip",
             "PESEL": "pesel", "REGON": "regon", "KRUS": "krus", "UNESCO": "unesko", "WiFi": "łajfaj",
             "Wi-Fi": "łajfaj", "iOS": "aj o es", "macOS": "mak o es", "B2B": "bi tu bi", "B2C": "bi tu si"}


def literuj(s: str) -> str:
    """Skrótowiec litera po literze po polsku: „PDF” → „pe de ef”, „HQ” → „ha ku”."""
    return " ".join(LITERY.get(c, c.lower()) for c in s)


def _skrotowiec(m: re.Match, caps_zdanie: bool) -> str:
    slowo, konc = m.group(1), m.group(2) or ""
    if slowo in SKROTOWCE:
        out = SKROTOWCE[slowo]
    elif not slowo.isupper():
        return m.group(0)
    elif caps_zdanie:
        return m.group(0).lower()                                 # NAPIS WIELKIMI LITERAMI: słowa, nie skrótowce
    elif len(slowo) > 4 and re.search(r"[AEIOUYĄĘÓ]", slowo) and not konc:
        return m.group(0).lower()                                 # długie słowo pisane wielkimi (UWAGA) czytamy jak słowo
    else:
        out = literuj(slowo)
    return out + (konc[1:] if konc else "")                       # PDF-a → pe de efa


_TLD = {"pl": "pe el", "com": "kom", "eu": "e u", "io": "aj oł", "ai": "ej aj", "org": "org", "net": "net",
        "dev": "dev", "app": "ap"}


# ------------------------------------------------------------------ całość

def _poza_klamrami(tekst: str, f) -> str:
    """f() tylko na tekście poza {klamrami} (angielskie wstawki zostają dla fonemizera)."""
    czesci = re.split(r"(\{[^{}]*\})", tekst)
    return "".join(c if c.startswith("{") and c.endswith("}") else f(c) for c in czesci)


def _przed(m: re.Match) -> str:
    """Słowo tuż przed dopasowaniem, małymi literami (przyimek decyduje o przypadku)."""
    return _slowo_przed(m.string, m.start())


def _kropka(m: re.Match) -> str:
    """Kropka skrótu („r.”, „w.”, „itd.”) była też końcem zdania: przed końcem tekstu albo wielką literą zostaje."""
    return "." if m.group(0).endswith(".") and re.match(r"\s*(?:$|[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż])", m.string[m.end():]) else ""


def _wiek(m: re.Match) -> str:
    n = rzymska(m.group(1))
    if m.group(2).lower() == "wiek":
        return f"{porzadkowy(n, 'm')} wiek"
    return f"{porzadkowy(n, 'ms' if _przed(m) in PRZYIMKI_MS else 'd')} wieku" + _kropka(m)


def _rok(m: re.Match) -> str:
    n, slowo = int(m.group(1)), (m.group(2) or "").strip().lower()
    if slowo == "rok":
        return f"{porzadkowy(n, 'm')} rok"
    return f"{porzadkowy(n, 'ms' if _przed(m) in PRZYIMKI_MS else 'd')} roku" + _kropka(m)


def _godz(m: re.Match) -> str:
    """[godz.] 15:30 → (godzinie) piętnastej trzydzieści; przypadek z przyimka przed godziną albo przed „godz.”."""
    h, mi = int(m.group(2)), int(m.group(3) or 0)
    if h > 24 or mi > 59:
        return m.group(0)
    przyimek = _przed(m)
    if m.group(1):
        slowo = SKROTY_PO.get(("godz.", przyimek), "godzina")
        return f"{slowo} {_godzina(h, mi, slowo if slowo in ('godzinie', 'godziny') else przyimek)}"
    return _godzina(h, mi, przyimek)


def _tel(m: re.Match) -> str:
    kier, grupy = m.group(1), re.findall(r"\d+", m.group(2))
    if len(grupy) == 1:
        g = grupy[0]
        grupy = [g[i:i + 3] for i in range(0, len(g), 3)]
    return (f"plus {liczebnik(int(kier.strip()[1:]))} " if kier else "") + " ".join(grupa(g) for g in grupy)


def _zakres(m: re.Match) -> str:
    """10–15 minut → od dziesięciu do piętnastu minut (lata 2019–2021 zostają: czyta je reguła lat)."""
    a, b, mn, j = m.group(1), m.group(2), m.group(3), m.group(4)
    if len(a) == 4 and len(b) == 4 and not j:
        return m.group(0)
    jedn = JEDNOSTKI.get(j.lower()) if j else None
    zb = _kwota(b, mn, None, True)
    if jedn:
        zb += " " + (jedn[3] if "," in b and not mn else jedn[2])
    return f"od {_kwota(a, None, None, True)} do {zb}"


def _rodzaj_po(dalej: str) -> str:
    """Rodzaj rzeczownika po liczbie (dla „jedna/jedno”, „dwie”): lista częstych rzeczowników żeńskich
    (dwie minuty, jedna osoba, do jednej firmy), nijakie po końcówce -o/-e/-um (jedno zdanie), reszta męskie."""
    m = re.match(rf"\s*([{_LIT}]+)", dalej)
    if not m:
        return "m"
    w = m.group(1).lower()
    if w in ZENSKIE:
        return "z"
    return "n" if w.endswith(("o", "e", "um")) else "m"


def _liczba(m: re.Match) -> str:
    """Liczba [mnożnik] [jednostka] w przypadku z przyimka; zera z przodu cyfra po cyfrze, ≥ 9 cyfr grupami po trzy."""
    minus, liczba, mn, j = ("minus " if m.group(1) else ""), m.group(2), m.group(3), m.group(4)
    if j and j.lower() in ("x", "×", "m") and mn:
        j = None                                                  # „2 mln m” się nie zdarza; „5 tys. x” też nie
    if "," not in liczba and not mn and not j:
        if len(liczba) > 1 and liczba.startswith("0"):
            return minus + cyfry(liczba)
        if len(liczba) >= 9:
            return " ".join(grupa(liczba[i:i + 3]) for i in range(0, len(liczba), 3))
    if not mn and not j and "," not in liczba:
        return minus + liczebnik(int(liczba), _przed(m) in PRZYIMKI_D, _rodzaj_po(m.string[m.end():]))
    return minus + _kwota(liczba, mn, j, _przed(m) in PRZYIMKI_D)


def _skrot(m: re.Match) -> str:
    s = m.group(1)
    klucz = s.lower()
    rozw = SKROTY_PO.get((klucz, _przed(m)), SKROTY[klucz])
    if s[0].isupper():
        rozw = rozw[0].upper() + rozw[1:]
    if klucz in SKROTY_KONCOWE:
        rozw += _kropka(m)                                        # itd. na końcu zdania: kropka zostaje
    return rozw


_SKROTY_RX = re.compile(rf"(?<![{_LIT}.])({'|'.join(re.escape(k) for k in sorted(SKROTY, key=len, reverse=True))})"
                        rf"(?![{_LIT}])", re.I)
_SKROTOWCE_RX = re.compile(
    rf"(?<![\w-])({'|'.join(re.escape(k) for k in sorted(SKROTOWCE, key=len, reverse=True) if not k.isupper())}"
    rf"|[A-ZĄĆĘŁŃÓŚŹŻ][A-ZĄĆĘŁŃÓŚŹŻ0-9]*[A-ZĄĆĘŁŃÓŚŹŻ])(-[a-ząćęłńóśźż]+)?(?!\w)")
_LICZBA_RX = re.compile(rf"(?<![\w,.])(-)?({_LICZBA})(?:\s?({_MNOZ_RX}))?(?:\s?({_JEDN_RX})(?![{_LIT}0-9]))?")


def _normalizuj(t: str) -> str:
    t = re.sub(r"[   ]", " ", t)

    # adresy: e-mail i domeny (jarvo.pl → jarvo kropka pe el)
    t = t.replace("@", " małpa ")
    t = re.sub(rf"\b([\w-]+)\.({'|'.join(_TLD)})\b(?!\.?\w)",
               lambda m: f"{m.group(1)} kropka {_TLD[m.group(2).lower()]}", t, flags=re.I)

    # daty: 2026-10-11, 11.10.2026 (r.), 11 października (2026 r.)
    t = re.sub(r"\b(\d{4})-(\d{2})-(\d{2})\b",
               lambda m: _data(int(m.group(3)), int(m.group(2)), int(m.group(1))) or m.group(0), t)
    t = re.sub(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})(?:\s*r\.|\s+roku\b)?",
               lambda m: (_data(int(m.group(1)), int(m.group(2)), int(m.group(3))) + _kropka(m)
                          if _data(int(m.group(1)), int(m.group(2)), 1) else m.group(0)), t)
    t = re.sub(rf"\b(\d{{1,2}})\s+({_MIES_RX})(?:\s+(\d{{4}})(?:\s*r\.|\s+roku\b)?)?",
               lambda m: f"{porzadkowy(int(m.group(1)), 'd')} {m.group(2)}"
                         + (f" {porzadkowy(int(m.group(3)), 'd')} roku" if m.group(3) else "") + _kropka(m), t)

    # wieki i lata: XXI w., w XX wieku, 2026 r., w 2026 roku, 2026 rok, w 2026
    t = re.sub(r"\b([IVXLC]{1,6})\s?(w\.|wieku\b|wiek\b)", _wiek, t)
    t = re.sub(r"\b(\d{4})(\s*r\.|\s+roku\b|\s+rok\b)", _rok, t)
    t = re.sub(rf"(?<=\b[wW] )((?:1[5-9]|20)\d{{2}})()\b(?!\s?(?:{_JEDN_RX}|{_MNOZ_RX}|[,.]\d|[–-]\d))", _rok, t)
    t = re.sub(rf"(?<=\b[wW]e )((?:1[5-9]|20)\d{{2}})()\b(?!\s?(?:{_JEDN_RX}|{_MNOZ_RX}|[,.]\d|[–-]\d))", _rok, t)

    # godziny: 15:30, o godz. 15.30, do godz. 9
    t = re.sub(r"(godz\.\s*)(\d{1,2})(?:[:.](\d{2}))?\b", _godz, t)
    t = re.sub(r"()(?<![\d:])(\d{1,2}):(\d{2})\b(?!:)", _godz, t)

    # telefony: +48 600 700 800, 600-700-800, 12 345 67 89, +48600700800, tel. 600700800
    t = re.sub(r"(\+\d{2}\s?)?\b(\d{3}[ -]\d{3}[ -]\d{3}|\d{2} \d{3} \d{2} \d{2})\b", _tel, t)
    t = re.sub(r"(\+\d{2}\s?)(\d{9})\b", _tel, t)
    t = re.sub(r"(?<=tel\. )()(\d{9})\b", _tel, t)

    # liczby z separatorem tysięcy: 12 500, 1 000 000, 10.000; ułamek z kropką: 3.5 → 3,5
    t = re.sub(r"\b\d{1,3}(?: \d{3})+(?:,\d+)?\b", lambda m: m.group(0).replace(" ", ""), t)
    t = re.sub(r"\b\d{1,3}(?:\.\d{3})+\b(?!\.\d)", lambda m: m.group(0).replace(".", ""), t)
    t = re.sub(r"\b(\d+)\.(\d{1,2})\b(?!\.\d)", r"\1,\2", t)

    # waluta przed liczbą: $5, € 10 mln
    t = re.sub(rf"([$€])\s?({_LICZBA})(?:\s?({_MNOZ_RX}))?",
               lambda m: f"{m.group(2)}{' ' + m.group(3) if m.group(3) else ''} {m.group(1)}", t)

    # zakresy, potem pojedyncze liczby z mnożnikiem i jednostką
    t = re.sub(rf"(?<![\d,.])({_LICZBA})\s?[–-]\s?({_LICZBA})(?:\s?({_MNOZ_RX}))?"
               rf"(?:\s?({_JEDN_RX})(?![{_LIT}0-9]))?", _zakres, t)
    t = _LICZBA_RX.sub(_liczba, t)

    # znaki i skróty
    t = re.sub(r"\s&\s", " i ", t)
    t = re.sub(r"\s\+\s", " plus ", t)
    t = re.sub(r"\s=\s", " równa się ", t)
    t = _SKROTY_RX.sub(_skrot, t)

    # skrótowce: PDF, HQ, AI-a; napis wielkimi literami czytany jako słowa
    wielkie = re.findall(r"\b[A-ZĄĆĘŁŃÓŚŹŻ]{3,}\b", t)
    litery = re.sub(r"[^A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]", "", t)
    caps_zdanie = len(wielkie) >= 3 and sum(map(len, wielkie)) > 0.6 * max(1, len(litery))
    t = _SKROTOWCE_RX.sub(lambda m: _skrotowiec(m, caps_zdanie), t)
    return re.sub(r"[ \t]+", " ", t)


def normalizuj(tekst: str) -> str:
    """Tekst po polsku → tekst do fonemizera: same słowa (poza {angielskimi wstawkami}) i interpunkcja."""
    return re.sub(r"[ \t]+", " ", _poza_klamrami(tekst, _normalizuj)).strip()
