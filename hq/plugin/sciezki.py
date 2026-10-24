"""Ścieżki danych floty w HQ (docs/NATYWNIE.md W05, W12; bliźniak przeglądarki: hq/web/src/07-sciezki.js).

Kontener trzyma dane w /opt/data. Instalacja natywna ma je w faktycznym korzeniu (HERMES_HOME, np.
`C:\\Users\\Michał Żółć\\AppData\\Local\\Jarvo\\dane` albo `~/.jarvo/dane`), a stare rozmowy i projekty dalej mają
ścieżki /opt/data/…: `na_dysk` kieruje je pod faktyczny korzeń (w kontenerze korzeń = alias, nic się nie zmienia).
`wzorzec` znajduje ścieżki danych w tekście (wiadomości agentów, blok kontekstu): /opt/data/… i faktyczny korzeń.
Korzeń z literą dysku: litera dowolnej wielkości, separatory „/” i „\\” (też mieszane), zapis Git Bash (/c/Users/…);
spacje tylko w samym korzeniu (np. w nazwie użytkownika), dalej ścieżka biegnie do pierwszego znaku spoza `reszta`.
Czyste funkcje (korzeń zawsze podany wprost, bez pamięci między wywołaniami); testy: tests/test_hq_core.py,
tests/test_kontekst.py, tests/test_scalanie.py.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

ALIAS = "/opt/data"          # korzeń danych w kontenerze: ścieżki w starych rozmowach i projektach
_DYSK = re.compile(r"^([A-Za-z]):(?:[\\/]|$)")
_GIT_BASH = re.compile(r"^/([A-Za-z])(?=/|$)")


def korzen_danych(home: str | None = None) -> Path:
    """Korzeń danych Hermesa (HERMES_HOME, domyślnie /opt/data). Wykonawca karty działa z HERMES_HOME profilu
    (`<korzeń>/profiles/<agent>`), a dane floty leżą w `<korzeń>/jarvo`."""
    h = Path(os.environ.get("HERMES_HOME", ALIAS) if home is None else home)
    return h.parent.parent if h.parent.name == "profiles" else h


def jako_tekst(korzen: Path | str) -> str:
    """Korzeń jako napis z „/” bez końcowego (C:/Users/x/dane, /opt/data); ścieżka z literą dysku także
    na Linuksie (testy) jest ścieżką Windows."""
    s = str(korzen)
    s = s.replace("\\", "/") if _DYSK.match(s) else Path(s).as_posix()
    return s.rstrip("/") or "/"


def z_dyskiem(korzen: Path | str) -> bool:
    return bool(_DYSK.match(jako_tekst(korzen)))


def _zrodlo(korzen: Path | str) -> str | None:
    """Wyrażenie faktycznego korzenia bez separatora na końcu; None, gdy korzeń to alias."""
    s = jako_tekst(korzen)
    if s == ALIAS:
        return None
    czesci = [c for c in s.split("/") if c]
    if z_dyskiem(s):
        litera = czesci[0][0]
        dysk = f"(?:[{litera.upper()}{litera.lower()}]:|/[{litera.upper()}{litera.lower()}])"
        return dysk + "".join(r"[\\/]" + re.escape(c) for c in czesci[1:])
    return "".join("/" + re.escape(c) for c in czesci)


def wzorzec(reszta: str, korzen: Path | str | None = None) -> re.Pattern:
    """Ścieżki danych w tekście: `/opt/data/` + `reszta`, a przy innym korzeniu najpierw `<korzeń>/` + `reszta`
    (`reszta` = dalsza część, np. `[^\\s,;"'<>()\\[\\]{}]+`). `findall` daje całe ścieżki."""
    alternatywy = [re.escape(ALIAS) + "/" + reszta]
    z = _zrodlo(korzen) if korzen is not None else None
    if z:
        alternatywy.insert(0, z + (r"[\\/]" if z_dyskiem(korzen) else "/") + reszta)
    return re.compile("|".join(f"(?:{a})" for a in alternatywy))


def na_dysk(raw: str, korzen: Path | str) -> str:
    """Ścieżka z tekstu albo z przeglądarki → ścieżka na tym komputerze: /opt/data/… pod faktycznym korzeniem
    (stare rozmowy), zapis Git Bash /c/… jako C:/… (tylko przy korzeniu z literą dysku); inna bez zmian."""
    s, k = str(raw or ""), jako_tekst(korzen)
    if k != ALIAS and (s == ALIAS or s.startswith(ALIAS + "/")):
        return k + s[len(ALIAS):]
    m = _GIT_BASH.match(s) if z_dyskiem(k) else None
    if m:
        return f"{m.group(1).upper()}:{s[2:] or '/'}"
    return s
