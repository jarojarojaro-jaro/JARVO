#!/usr/bin/env python3
"""Sufit pamięci kontenerów floty dopasowany do pamięci, którą ma Docker.

Limity w docker-compose.yml (Hermes 5 GB, Komputer 2 GB, telefon testowy 2–4 GB) są dobre dla VPS-a z 8+ GB.
W maszynie wirtualnej Dockera na Macu z 8 GB RAM (Colima 5 GB) albo na małym VPS-ie ich suma przekracza pamięć:
przy pełnej pracy kończy się to brakiem pamięci całej maszyny (pada dockerd i cała flota), a nie jednego kontenera.

Dlatego suma limitów włączonych usług (Hermes zawsze, Komputer i telefon testowy według COMPOSE_PROFILES) mieści się
w pamięci Dockera minus zapas na system, dockerd i małe usługi (SearXNG, Valkey, monitoring, ekran telefonu).
Gdy się nie mieści, dzielimy dostępną pamięć proporcjonalnie do domyślnych limitów (z dolnym progiem każdej usługi)
i zapisujemy wynik w compose/.env. Wartości dobrane tu pamięta compose/.limity-auto: przy kolejnym wdrożeniu
(więcej pamięci, wyłączony Komputer) liczymy je od nowa albo wracamy do domyślnych. Limit ustawiony ręcznie przez
właściciela zostaje (tylko ostrzeżenie).

    python3 scripts/limity.py --compose <katalog compose> [--pamiec-mib N] [--na-zywo]

--na-zywo: działającym kontenerom zmieniamy limit od razu (docker update), bez restartu agentów.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# klucz w .env, domyślny limit (MiB), dolny próg (MiB), profil compose (None: zawsze), kontener
USLUGI = [
    ("HERMES_MEM_LIMIT", 5120, 1536, None, "jarvo-hermes"),
    ("KOMPUTER_MEM_LIMIT", 2048, 1024, "komputer", "jarvo-komputer"),
    ("ANDROID_MEM_LIMIT", 2048, 1024, "android", "jarvo-android"),
    ("ANDROID_EMU_MEM_LIMIT", 4096, 2048, "android-kvm", "jarvo-android"),
]
# stałe limity małych usług (docker-compose.yml) i ich profile; None: zawsze
MALE = [(384, None), (96, None), (256 + 128 + 64, "monitoring"), (256, "android"), (256, "android-kvm")]
SYSTEM_MIB = 640   # jądro maszyny wirtualnej, dockerd, containerd
AUTO = ".limity-auto"


def mib(wartosc: str) -> int | None:
    """'5g', '2048m', '1.5G', '512M', '3221225472' → MiB."""
    m = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*([bkmg]?)b?\s*", wartosc.lower())
    if not m:
        return None
    n, j = float(m.group(1)), m.group(2)
    return int(n * {"": 1 / 1048576, "b": 1 / 1048576, "k": 1 / 1024, "m": 1, "g": 1024}[j])


def czytaj_env(sciezka: Path) -> dict[str, str]:
    env = {}
    if sciezka.exists():
        for linia in sciezka.read_text(encoding="utf-8").splitlines():
            if "=" in linia and not linia.lstrip().startswith("#"):
                k, v = linia.split("=", 1)
                env[k.strip()] = v.strip().strip("'\"")
    return env


def ustaw_env(sciezka: Path, zmiany: dict[str, str | None]) -> None:
    """Zmienia wartości kluczy (None: usuwa linię) bez ruszania reszty pliku i jego uprawnień."""
    linie = sciezka.read_text(encoding="utf-8").splitlines() if sciezka.exists() else []
    nowe = [l for l in linie if l.split("=", 1)[0].strip() not in zmiany]
    nowe += [f"{k}={v}" for k, v in zmiany.items() if v is not None]
    with sciezka.open("w", encoding="utf-8") as f:   # open("w") zostawia uprawnienia (.env ma 600)
        f.write("\n".join(nowe) + "\n")


def pamiec_dockera() -> int | None:
    try:
        r = subprocess.run(["docker", "info", "--format", "{{.MemTotal}}"], capture_output=True, text=True, timeout=20)
        return int(r.stdout.strip()) // 1048576 if r.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def gb(m: int) -> str:
    return f"{m / 1024:.1f}".replace(".", ",") + " GB"


def policz(pamiec: int, env: dict[str, str], auto: dict[str, str]) -> tuple[dict[str, str | None], list[str]]:
    """Zwraca (zmiany w .env, komunikaty). Zmiany: klucz → nowa wartość albo None (wraca domyślna)."""
    profile = {p.strip() for p in env.get("COMPOSE_PROFILES", "").split(",") if p.strip()}
    wlaczone = [u for u in USLUGI if u[3] is None or u[3] in profile]
    budzet = pamiec - SYSTEM_MIB - sum(m for m, p in MALE if p is None or p in profile)
    stale, ruchome = {}, {}
    for klucz, dom, prog, _, _ in wlaczone:
        w = env.get(klucz)
        # ustawione ręcznie przez właściciela (inna wartość niż domyślna z compose.env.example i niż nasza)
        if w and auto.get(klucz) != w and mib(w) != dom:
            stale[klucz] = mib(w) or dom
        else:
            ruchome[klucz] = (dom, prog)
    zmiany: dict[str, str | None] = {}
    # wyłączona usługa: dobrany przez nas limit wraca do domyślnego
    for klucz, *_ in USLUGI:
        if klucz in auto and klucz not in ruchome and klucz not in stale and env.get(klucz) == auto[klucz]:
            zmiany[klucz] = None
    wolne = budzet - sum(stale.values())
    chce = sum(d for d, _ in ruchome.values())
    if chce <= wolne:   # mieści się: nasze wcześniejsze wartości wracają do domyślnych
        zmiany.update({k: None for k in ruchome if k in auto and env.get(k) == auto[k]})
    else:
        for klucz, (dom, prog) in ruchome.items():
            zmiany[klucz] = f"{max(prog, int(max(wolne, 0) * dom / chce) // 64 * 64)}m"
    zmiany = {k: v for k, v in zmiany.items() if env.get(k) != v}

    def limit(klucz: str, dom: int) -> int:
        v = zmiany[klucz] if klucz in zmiany else env.get(klucz)
        return (mib(v) or dom) if v else dom

    razem = sum(limit(k, d) for k, d, *_ in wlaczone)
    komunikaty = []
    if any(zmiany.values()):
        komunikaty.append(f"Docker ma {gb(pamiec)} pamięci, więc limity kontenerów to "
                          + ", ".join(f"{k}={v}" for k, v in zmiany.items() if v))
    elif zmiany:
        komunikaty.append("domyślne limity kontenerów: " + ", ".join(zmiany))
    reczne = [k for k, w in stale.items() if w > budzet]
    for klucz in reczne:
        komunikaty.append(f"{klucz}={env[klucz]} (ustawiony ręcznie) jest większy niż pamięć Dockera dla floty"
                          f" (ok. {gb(budzet)})")
    if razem > budzet and not reczne:
        komunikaty.append(f"za mało pamięci w Dockerze ({gb(pamiec)}) na włączone usługi: wyłącz Komputer albo "
                          "telefon testowy, albo daj Dockerowi więcej pamięci")
    return zmiany, komunikaty


def na_zywo(zmiany: dict[str, str | None]) -> None:
    kontenery = {k: c for k, _, _, _, c in USLUGI}
    domyslne = {k: d for k, d, _, _, _ in USLUGI}
    for klucz, v in zmiany.items():
        m = mib(v) if v else domyslne[klucz]
        subprocess.run(["docker", "update", "--memory", f"{m}m", "--memory-swap", f"{2 * m}m", kontenery[klucz]],
                       capture_output=True, timeout=30)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--compose", required=True, type=Path)
    ap.add_argument("--pamiec-mib", type=int, help="pamięć Dockera (testy); domyślnie docker info")
    ap.add_argument("--na-zywo", action="store_true", help="docker update działających kontenerów")
    a = ap.parse_args(argv)
    pamiec = a.pamiec_mib or pamiec_dockera()
    if not pamiec:
        return 0   # Docker nie odpowiada: zostawiamy limity bez zmian
    env_plik, auto_plik = a.compose / ".env", a.compose / AUTO
    env, auto = czytaj_env(env_plik), czytaj_env(auto_plik)
    zmiany, komunikaty = policz(pamiec, env, auto)
    for k in komunikaty:
        print(f"limity pamięci: {k}")
    if zmiany:
        ustaw_env(env_plik, zmiany)
        nowe_auto = {k: v for k, v in auto.items() if k not in zmiany}
        nowe_auto.update({k: v for k, v in zmiany.items() if v})
        auto_plik.write_text("".join(f"{k}={v}\n" for k, v in sorted(nowe_auto.items())), encoding="utf-8")
        if a.na_zywo:
            na_zywo(zmiany)
    return 0


if __name__ == "__main__":
    sys.exit(main())
