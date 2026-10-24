#!/usr/bin/env python3
"""Wspólne klucze floty: klucze dostawców modeli i narzędzi z głównego .env trafiają do każdego agenta.

    python share_keys.py <hermes_home>          # jednorazowo (deploy)
    python share_keys.py <hermes_home> --watch  # na bieżąco (co kilka sekund, gdy główny .env się zmieni)

Dlaczego: przy wielu profilach Hermes celowo izoluje klucze (każdy profil czyta tylko swój .env, bez
podglądania głównego). Klucz dodany w dashboardzie przy profilu „default” widzi więc tylko profil główny,
a agenci (jarvo, jarvo-sherlock, …) nie. Ten skrypt dopisuje je na końcu .env każdego agenta w bloku
zarządzanym automatycznie.

Zasady:
- dzielone są tylko klucze dostawców i narzędzi (kategorie `provider` i `tool` w katalogu Hermesa oraz
  zmienne zarejestrowanych dostawców); tokeny komunikatorów (Telegram, Discord…) i ustawienia NIE,
- klucz ustawiony w agencie (niepusty, poza blokiem) ma pierwszeństwo i nie jest nadpisywany,
- klucz zmieniony w agencie wewnątrz bloku (np. w dashboardzie przy wybranym agencie) zostaje wyjęty
  z bloku jako ustawienie tego agenta, a nie cofnięty,
- klucz usunięty z głównego .env znika z bloków. Wartości nigdy nie są wypisywane,
- .env agentów i plik stanu są tylko dla właściciela (POSIX: tryb 600, Windows: ACL przez icacls).
Skrypt jest samodzielny (bez fleetlib), bo build kopiuje go do wtyczki Jarvo HQ (scripts/hqbuild.py).
OAuth (logowanie przez przeglądarkę) nie wymaga tego: Hermes sam czyta główny auth.json jako zapas.
"""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")
BEGIN = "# >>> Jarvo: klucze wspólne z głównego .env (zarządzane automatycznie, nie edytuj tego bloku)"
END = "# <<< Jarvo: klucze wspólne"
STATE = ".jarvo-shared-keys.json"
# gdy katalogu Hermesa nie da się zaimportować: klucze dostawców/narzędzi po nazwie
FALLBACK_SUFFIXES = ("_API_KEY", "_API_TOKEN", "_BASE_URL", "_API_URL", "_ACCESS_KEY", "_SECRET_KEY")
NEVER_SHARED = {"API_SERVER_KEY", "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD", "SUDO_PASSWORD"}


def shareable_names() -> tuple[set[str] | None, set[str]]:
    """(nazwy do dzielenia albo None = heurystyka, nazwy nigdy niedzielone)."""
    try:
        from hermes_cli.config_defaults import OPTIONAL_ENV_VARS
    except Exception:
        return None, set(NEVER_SHARED)
    names = {k for k, v in OPTIONAL_ENV_VARS.items() if v.get("category") in ("provider", "tool")}
    blocked = {k for k, v in OPTIONAL_ENV_VARS.items() if v.get("category") not in ("provider", "tool")}
    try:
        from providers import list_providers  # type: ignore
        for p in list_providers():
            names.update(getattr(p, "env_vars", ()) or ())
    except Exception:
        pass
    return names - NEVER_SHARED, blocked | NEVER_SHARED


def is_shared(name: str, names: set[str] | None, blocked: set[str]) -> bool:
    if name in blocked:
        return False
    if names is not None and name in names:
        return True
    return name.endswith(FALLBACK_SUFFIXES)


def parse(text: str) -> tuple[list[str], list[str]]:
    """(linie poza blokiem, linie w bloku)."""
    outside, inside, in_block = [], [], False
    for line in text.splitlines():
        if line.strip() == BEGIN:
            in_block = True
        elif line.strip() == END:
            in_block = False
        else:
            (inside if in_block else outside).append(line)
    return outside, inside


def assignments(lines: list[str]) -> dict[str, tuple[str, str]]:
    """nazwa → (cała linia, wartość); ostatnia wygrywa, jak w Hermesie."""
    out = {}
    for line in lines:
        m = LINE.match(line)
        if m and not line.lstrip().startswith("#"):
            out[m.group(1)] = (line.strip(), m.group(2).strip())
    return out


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def tylko_dla_wlasciciela(path: Path) -> None:
    """Plik z sekretami tylko dla właściciela. POSIX: tryb 600. Windows: os.chmod niczego tam nie chroni, więc ACL
    bez dziedziczenia z jednym wpisem (pełny dostęp bieżącego użytkownika) przez wbudowany icacls. Najpierw /reset:
    `/inheritance:r` usuwa tylko wpisy dziedziczone, a jawne (np. z narzędzi MSYS) zostałyby obok naszego."""
    if os.name != "nt":
        os.chmod(path, 0o600)
        return
    # konto z domeną (inne konto o tej samej nazwie nie dostanie dostępu), icacls z System32 (nie z katalogu bieżącego)
    kto = os.environ.get("USERNAME") or getpass.getuser()
    if os.environ.get("USERDOMAIN"):
        kto = f"{os.environ['USERDOMAIN']}\\{kto}"
    icacls = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "icacls.exe"
    for argumenty in (["/reset"], ["/inheritance:r", "/grant:r", f"{kto}:F"]):
        r = subprocess.run([str(icacls), str(path), *argumenty], capture_output=True, encoding="oem", errors="replace",
                           creationflags=subprocess.CREATE_NO_WINDOW)
        if r.returncode:
            raise OSError(f"icacls {path}: {(r.stdout + r.stderr).strip()[:300]}")


def zamien(tmp: Path, cel: Path) -> None:
    """os.replace; na Windows cel otwarty chwilę w innym procesie (Hermes czyta .env, antywirus) daje PermissionError,
    więc ponawiamy kilka razy. Na POSIX bez ponowień."""
    for proba in range(10):
        try:
            tmp.replace(cel)
            return
        except PermissionError:
            if os.name != "nt" or proba == 9:
                raise
            time.sleep(0.1)


def sync_profile(env_path: Path, shared: dict[str, tuple[str, str]], last: dict[str, str]) -> dict[str, str]:
    text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    outside, inside = parse(text)
    own = {k for k, (_, v) in assignments(outside).items() if v}
    # zmienione w agencie wewnątrz bloku → ustawienie agenta (wyjmujemy z bloku)
    for name, (line, value) in assignments(inside).items():
        if value and name in last and digest(value) != last[name] and name not in own:
            if name not in shared or shared[name][1] != value:
                outside.append(line)
                own.add(name)
    block = [line for name, (line, _) in sorted(shared.items()) if name not in own]
    while outside and not outside[-1].strip():
        outside.pop()
    new = "\n".join(outside) + "\n"
    if block:
        new += "\n" + BEGIN + "\n" + "\n".join(block) + "\n" + END + "\n"
    if new != text:
        tmp = env_path.with_name(env_path.name + ".jarvo-tmp")
        tmp.write_text(new, encoding="utf-8", newline="\n")
        tylko_dla_wlasciciela(tmp)          # przeniesienie w obrębie dysku zachowuje uprawnienia i ACL
        zamien(tmp, env_path)
    return {name: digest(v) for name, (_, v) in shared.items() if name not in own}


def sync(home: Path) -> int:
    names, blocked = shareable_names()
    root = assignments(parse((home / ".env").read_text(encoding="utf-8"))[0]) if (home / ".env").exists() else {}
    shared = {k: lv for k, lv in root.items() if lv[1] and is_shared(k, names, blocked)}
    state_path = home / STATE
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        state = {}
    profiles = sorted(p for p in (home / "profiles").glob("*/") if (p / "config.yaml").exists())
    for prof in profiles:
        state[prof.name] = sync_profile(prof / ".env", shared, state.get(prof.name, {}))
    state_path.write_text(json.dumps(state, indent=1), encoding="utf-8", newline="\n")
    tylko_dla_wlasciciela(state_path)
    return len(profiles)


def watch(home: Path, every: float = 3.0) -> None:
    last = None
    while True:
        try:
            sig = (home / ".env").stat().st_mtime_ns
        except OSError:
            sig = None
        if sig != last:
            try:
                sync(home)
                last = sig
            except Exception as exc:  # nie zabijamy pętli jednym błędem zapisu
                print(f"share_keys: {exc}", file=sys.stderr)
        time.sleep(every)


def main(argv: list[str]) -> int:
    home = Path(argv[0])
    if "--watch" in argv:
        watch(home)
        return 0
    n = sync(home)
    print(f"wspólne klucze: {n} agentów")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
