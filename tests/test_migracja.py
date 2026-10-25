"""`jarvo migruj`: migracja ze starej instalacji z Dockerem i WSL (jarvo/migracja.py, docs/NATYWNIE.md: f1–f5, I33,
E12).

Stara instalacja to syntetyczne archiwum tar, jakie daje `wsl --export Ubuntu -` (albo `sudo tar` na Linuksie i
`docker cp jarvo-hermes:/opt/data -` na macOS): ~/jarvo-local z danymi uid 10000, bazy SQLite w trybie WAL
(rozmowy.db tylko w pliku -wal), .git skarbca, dowiązania bezwzględne i względne, twarde dowiązanie, auth.json
w profilu, ścieżki /opt w state.db, kanban.db, projects.db i rozmowy.db, sekrety w secrets/ i compose/. Wszystko, co
dotyka WSL, Dockera, sudo, rejestru i procesów, idzie przez atrapy SystemMigracji i Natywne: testy nie uruchamiają
wsl.exe, docker ani sudo (na Windows conftest.py i tak blokuje wsl), a zapisują tylko w katalogu tymczasowym.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import sqlite3
import subprocess
import sys
import tarfile
import time
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from conftest import REPO, WINDOWS, uruchom_bash

sys.path.insert(0, str(REPO))
from jarvo import migracja as mig  # noqa: E402
from jarvo.sciezki import Uklad  # noqa: E402

STARY_DOM = "/home/jarvo"
LOKALNY = f"{STARY_DOM}/jarvo-local"
DANE = f"{LOKALNY}/data/hermes"
REPO_STARE = f"{STARY_DOM}/jarvo"
TOKEN_TG = "123:FALSZYWY-TOKEN-TELEGRAMA"          # krótki: scripts/validate.py nie bierze go za prawdziwy token
KLUCZ_API = "sk-test-FALSZYWY-KLUCZ-OPENROUTER"
HASLO_PANELU = "haslo-panelu-testowe"
TERAZ = time.mktime(time.strptime("2026-10-25 12:00:00", "%Y-%m-%d %H:%M:%S"))
GIT_HEAD = "a" * 40
# `jarvo migruj` działa na Pythonie instalacji (PBS 20261021, SQLite 3.53.1); Python testów bywa starszy (bramka Z14)
SQLITE_INSTALACJI = (3, 53, 1)


# ---------------------------------------------------------------- stara instalacja: pliki i archiwum

def _baza_stanu(p: Path, cwds: list[str]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript("""
        CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT NOT NULL, started_at REAL NOT NULL, cwd TEXT,
                               git_repo_root TEXT, title TEXT);
        CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL REFERENCES sessions(id),
                               role TEXT NOT NULL, content TEXT, timestamp REAL NOT NULL);
    """)
    with contextlib.suppress(sqlite3.OperationalError):        # FTS5 jest w Pythonie z python.org i PBS
        con.executescript("""
            CREATE VIRTUAL TABLE messages_fts USING fts5(content);
            CREATE TRIGGER messages_fts_insert AFTER INSERT ON messages BEGIN
              INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content); END;
            CREATE TRIGGER messages_fts_update AFTER UPDATE ON messages BEGIN
              UPDATE messages_fts SET content = new.content WHERE rowid = new.id; END;
        """)
    for i, cwd in enumerate(cwds):
        con.execute("INSERT INTO sessions VALUES (?, 'cli', ?, ?, ?, ?)",
                    (f"s{i}", 1.0 + i, cwd, "/opt/jarvo/repo", f"Rozmowa {i}"))
        con.execute("INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, 'user', ?, 1.0)",
                    (f"s{i}", "Zdjęcie: MEDIA:/opt/data/jarvo/inbox/zdjecie.png"))
        con.execute("INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, 'assistant', ?, 2.0)",
                    (f"s{i}", "Gotowe, plik w /opt/data/jarvo/workspaces/jarvo/wynik.md"))
    con.commit()
    con.close()


def _kanban(p: Path, sciezka: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript("""
        CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL, created_at INTEGER NOT NULL,
                            workspace_kind TEXT NOT NULL DEFAULT 'scratch', workspace_path TEXT);
        CREATE TABLE task_attachments (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
                                       filename TEXT NOT NULL, stored_path TEXT NOT NULL, created_at INTEGER NOT NULL);
    """)
    con.execute("INSERT INTO tasks VALUES ('t1', 'Karta migracji', 'triage', 1, 'dir', ?)", (sciezka,))
    con.execute("INSERT INTO tasks VALUES ('t2', 'Karta bez katalogu', 'todo', 2, 'scratch', NULL)")
    con.execute("INSERT INTO task_attachments (task_id, filename, stored_path, created_at) VALUES "
                "('t1', 'plik.pdf', '/opt/data/kanban/attachments/t1/plik.pdf', 1)")
    con.commit()
    con.close()


def _projekty(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    con.executescript("""
        CREATE TABLE projects (id TEXT PRIMARY KEY, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL, primary_path TEXT,
                               created_at INTEGER NOT NULL);
        CREATE TABLE project_folders (project_id TEXT NOT NULL, path TEXT NOT NULL, PRIMARY KEY (project_id, path));
        CREATE TABLE discovered_repos (root TEXT PRIMARY KEY, last_seen INTEGER NOT NULL);
    """)
    con.execute("INSERT INTO projects VALUES ('p1', 'strona', 'Strona', '/opt/jarvo/repo', 1)")
    # ta sama ścieżka pod nazwą z kontenera i ze starego hosta: po migracji zostaje jeden wiersz
    con.execute("INSERT INTO project_folders VALUES ('p1', '/opt/data/jarvo/workspaces/strona')")
    con.execute("INSERT INTO project_folders VALUES ('p1', ?)", (f"{DANE}/jarvo/workspaces/strona",))
    con.execute("INSERT INTO discovered_repos VALUES ('/opt/database/obce', 1)")      # granica ścieżki: bez zmian
    con.commit()
    con.close()


def _rozmowy_w_wal(p: Path) -> sqlite3.Connection:
    """rozmowy.db, której cała treść jest w pliku -wal: połączenie zostaje otwarte (bez punktu kontrolnego)."""
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA wal_autocheckpoint=0")
    con.executescript("""
        CREATE TABLE watki (id TEXT PRIMARY KEY, utworzony_at REAL NOT NULL);
        CREATE TABLE wpisy (id TEXT PRIMARY KEY, watek_id TEXT NOT NULL, seq INTEGER NOT NULL,
                            tekst TEXT NOT NULL DEFAULT '', zalaczniki TEXT NOT NULL DEFAULT '[]',
                            obrazy TEXT NOT NULL DEFAULT '[]', utworzony_at REAL NOT NULL);
        CREATE TABLE przekazy (klucz TEXT PRIMARY KEY, pliki TEXT NOT NULL DEFAULT '[]');
    """)
    con.execute("INSERT INTO watki VALUES ('w1', 1.0)")
    con.execute("INSERT INTO wpisy VALUES ('e1', 'w1', 1, 'Ostatnia rozmowa przed migracją', ?, '[]', 1.0)",
                (json.dumps([{"path": "/opt/data/jarvo/inbox/plik.txt", "nazwa": "plik.txt"}]),))
    con.execute("INSERT INTO przekazy VALUES ('k1', ?)", (json.dumps(["/opt/data/jarvo/workspaces/web/a.html"]),))
    con.commit()
    return con


def _zapisz(p: Path, tresc: str | bytes) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(tresc, str):
        p.write_text(tresc, encoding="utf-8", newline="\n")
    else:
        p.write_bytes(tresc)


def stare_dane(katalog: Path) -> tuple[Path, list[sqlite3.Connection]]:
    """Katalog ~/jarvo-local starej instalacji (data/hermes, compose, secrets, build) w `katalog`."""
    l = katalog / "jarvo-local"
    d = l / "data" / "hermes"
    otwarte = []
    _zapisz(d / "config.yaml", "model:\n  default: gpt\nterminal:\n  cwd: /opt/data\n")
    _zapisz(d / "install_id", "stary0000000000000000000000000000\n")
    _zapisz(d / "auth.json", json.dumps({"openai-codex": {"refresh_token": "odswiezanie-stare"}}))
    _zapisz(d / ".env", f"TELEGRAM_BOT_TOKEN={TOKEN_TG}\nIMPECCABLE_HOME=/opt/data/jarvo/narzedzia/impeccable\n"
                        "PUSTA=\nAPI_SERVER_KEY=klucz-bramy\n")
    _baza_stanu(d / "state.db", ["/opt/data/jarvo/workspaces/jarvo/projekt", f"{DANE}/jarvo/workspaces/host",
                                 "/opt/database/obce", "/srv/inne"])
    _kanban(d / "kanban.db", "/opt/data/jarvo/workspaces/migracja")
    _projekty(d / "projects.db")
    _zapisz(d / "kanban" / "boards" / "projekt" / "board.json",
            json.dumps({"name": "Projekt", "default_workdir": "/opt/data/jarvo/workspaces/projekt"}, indent=2))
    _zapisz(d / "kanban" / "attachments" / "t1" / "plik.pdf", b"%PDF-1.4 testowy")
    p = d / "profiles" / "jarvo"
    _zapisz(p / "auth.json", json.dumps({"openai-codex": {"refresh_token": "odswiezanie-profilu"}}))
    _zapisz(p / ".env", f"OPENROUTER_API_KEY={KLUCZ_API}\nIMPECCABLE_HOME=/opt/data/jarvo/narzedzia/impeccable\n")
    _zapisz(p / "config.yaml", "model:\n  default: gpt\n")
    _zapisz(p / "distribution.yaml", "name: jarvo\nsource: /opt/jarvo/build/profiles/jarvo\ninstalled_at: 1\n")
    _zapisz(p / "cron" / "jobs.json", json.dumps({"jobs": [
        {"id": "patrol", "enabled": True, "state": "scheduled", "workdir": "/opt/data/jarvo/workspaces/jarvo",
         "prompt": "Sprawdź /opt/data/jarvo/knowledge"},
        {"id": "brief", "enabled": False, "state": "paused", "workdir": None}], "updated_at": "x"}, indent=2))
    _zapisz(p / "memories" / "MEMORY.md", "Właściciel lubi krótkie odpowiedzi.\n")
    _zapisz(p / "sessions" / "s1.json", json.dumps({"id": "s1", "cwd": "/opt/data"}))
    _baza_stanu(p / "state.db", ["/opt/data/profiles/jarvo/home"])
    _zapisz(p / "bin" / "narzedzie", b"\x7fELF linuksowa binarka")
    _zapisz(p / "home" / ".gitconfig", "[user]\n  name = jarvo\n")
    # inne logowania w katalogu domowym agenta: przechodzą, ale nie do próby (f3 p.7)
    _zapisz(p / "home" / ".config" / "gh" / "hosts.yml", "github.com:\n  oauth_token: proba-gh\n")
    _zapisz(p / "home" / ".git-credentials", "https://jarvo:proba-git@github.com\n")
    _zapisz(p / "home" / ".ssh" / "id_ed25519", "klucz ssh agenta (próba, bez nagłówka PEM)\n")
    _zapisz(d / "pairing" / "telegram.json", json.dumps({"approved": ["1"]}))
    _zapisz(d / "cron" / "jobs.json", json.dumps({"jobs": [], "updated_at": "x"}))
    _zapisz(d / "memories" / "USER.md", "Michał\n")
    _zapisz(d / "sessions" / "sesja.json", "{}")
    s = d / "jarvo" / "state"
    otwarte.append(_rozmowy_w_wal(s / "rozmowy.db"))
    _zapisz(s / "agenci.json", "{}")
    for n in ("update.json", "praca.json", "preview-1.json", "wiedza.db"):
        _zapisz(s / n, "{}")
    k = d / "jarvo" / "knowledge"
    _zapisz(k / "notatki" / "test.md", "# Notatka sprzed migracji\n")
    _zapisz(k / ".git" / "HEAD", "ref: refs/heads/main\n")
    _zapisz(k / ".git" / "refs" / "heads" / "main", GIT_HEAD + "\n")
    _zapisz(k / ".git" / "objects" / "aa" / ("a" * 38), b"x\x9c obiekt gita")
    _zapisz(k / ".git" / "index.lock", "")
    w = d / "jarvo" / "workspaces" / "migracja"
    _zapisz(w / "oryginal.txt", "treść oryginału\n")
    _zapisz(w / "uv.lock", "version = 1\n")
    # pliki właściciela o nazwach baz Hermesa: nie jego bazy, więc bez przepisania (baza_hermesa) i bez liczenia
    _kanban(w / "kanban.db", "/opt/data/projekt-wlasciciela")
    _zapisz(w / "state.db", "to nie jest baza SQLite\n")
    _zapisz(w / "node_modules" / "x" / "index.js", "module.exports = 1\n")
    _zapisz(w / "__pycache__" / "a.cpython-312.pyc", b"\x00")
    _zapisz(d / "jarvo" / "narzedzia" / "impeccable" / "bin" / "impeccable", b"#!/bin/sh\n")
    _zapisz(d / "jarvo" / "models" / "paradee" / "model.onnx", b"onnx" * 10)
    _zapisz(d / ".npm" / "_cacache" / "x", b"cache")
    _zapisz(d / ".cache" / "ms-playwright" / "x", b"cache")
    _zapisz(d / "cache" / "images" / "a.png", b"\x89PNG")
    _zapisz(d / "cache" / "models_dev.json", "{}")
    _zapisz(d / "lazy-packages" / "x" / "y.py", "")
    for n in ("gateway.pid", "gateway_state.json", "processes.json", "cron.pid", "gateway.lock", "inne.lock",
              "gateway.sock.path"):
        _zapisz(d / n, "1")
    _zapisz(d / "plugins" / "jarvo-hq" / "plugin.yaml", "name: jarvo-hq\n")
    _zapisz(d / "plugins" / "inny" / "plugin.yaml", "name: inny\n")
    _zapisz(d / "skins" / "jarvo.yaml", "x: 1\n")
    _zapisz(d / "runtime" / "x", "")
    _zapisz(d / "sandboxes" / "x", "")
    _zapisz(d / "bin" / "tirith", b"\x7fELF")
    _zapisz(d / "node" / "bin" / "node", b"\x7fELF")
    _zapisz(l / "compose" / ".env", f"JARVO_DATA={LOKALNY}/data\nJARVO_REPO={REPO_STARE}\n"
                                    f"JARVO_SECRETS={LOKALNY}/secrets\nDASHBOARD_USER=jarvo\n"
                                    f"DASHBOARD_PASSWORD={HASLO_PANELU}\nSEARXNG_SECRET=sekret-searxng\n")
    _zapisz(l / "compose" / "jarvo.env", "TELEGRAM_OWNER_ID=1\nJARVO_MODEL_PROVIDER=\n")
    _zapisz(l / "compose" / ".host-version", "5\n")
    _zapisz(l / "secrets" / "host.env", f"TELEGRAM_BOT_TOKEN={TOKEN_TG}\nOPENROUTER_API_KEY={KLUCZ_API}\n")
    _zapisz(l / "secrets" / "jarvo-web.env", "OPENROUTER_API_KEY=\n")
    _zapisz(l / "secrets" / "host.env.example", "TELEGRAM_BOT_TOKEN=\n")
    _zapisz(l / "build" / "BUILD.json", "{}")
    _zapisz(l / "install.log", "usermod -aG docker jarvo\n")
    return l, otwarte


# dowiązania i pliki specjalne dopisujemy do archiwum wprost (zwykły użytkownik Windows nie tworzy symlinków)
DOWIAZANIA = {
    "jarvo/workspaces/migracja/skarbiec": "/opt/data/jarvo/knowledge",
    "jarvo/workspaces/migracja/notatka.md": "../../knowledge/notatki/test.md",
    "jarvo/workspaces/migracja/zewnetrzne": "/etc/passwd",
    "profiles/jarvo/plugins/jarvo-hq": "/opt/data/plugins/jarvo-hq",
}


def archiwum(l: Path, *, przedrostek: str = "./", korzen_danych: str | None = None, dodatki=None,
             tylko_dane: bool = False) -> bytes:
    """Tar jak z `wsl --export` (cały system: ./etc, ./var/lib/docker, ./home/…) albo z `docker cp` (korzen_danych:
    "data", same dane). Dane mają uid 10000, jak w kontenerze."""
    bufor = io.BytesIO()

    def jako_kontener(info: tarfile.TarInfo) -> tarfile.TarInfo:
        info.uid = info.gid = 10000
        info.uname = info.gname = "hermes"
        return info

    with tarfile.open(fileobj=bufor, mode="w", format=tarfile.PAX_FORMAT) as t:
        def plik(nazwa: str, tresc: bytes, uid: int = 0) -> None:
            info = tarfile.TarInfo(nazwa)
            info.size, info.uid, info.mode = len(tresc), uid, 0o644
            t.addfile(info, io.BytesIO(tresc))

        dane = korzen_danych or f"{przedrostek}{DANE.lstrip('/')}"
        if not korzen_danych and not tylko_dane:
            plik(f"{przedrostek}etc/hostname", b"ubuntu\n")
            plik(f"{przedrostek}var/lib/docker/overlay2/abc/diff/plik", b"warstwa obrazu")
            plik(f"{przedrostek}home/jarvo/.bashrc", b"# bashrc\n", 1000)
            plik(f"{przedrostek}home/jarvo/jarvo/README.md", b"# repo\n", 1000)
        t.add(l / "data" / "hermes", arcname=dane, filter=jako_kontener)
        if not korzen_danych and not tylko_dane:
            for nazwa in ("compose", "secrets", "build"):
                t.add(l / nazwa, arcname=f"{przedrostek}{LOKALNY.lstrip('/')}/{nazwa}")
            t.add(l / "install.log", arcname=f"{przedrostek}{LOKALNY.lstrip('/')}/install.log")
        for rel, cel in DOWIAZANIA.items():
            info = tarfile.TarInfo(f"{dane}/{rel}")
            info.type, info.linkname, info.uid = tarfile.SYMTYPE, cel, 10000
            t.addfile(info)
        info = tarfile.TarInfo(f"{dane}/jarvo/workspaces/migracja/twardy.txt")
        info.type, info.linkname = tarfile.LNKTYPE, f"{dane}/jarvo/workspaces/migracja/oryginal.txt"
        t.addfile(info)
        info = tarfile.TarInfo(f"{dane}/gateway.sock")
        info.type = tarfile.FIFOTYPE
        t.addfile(info)
        for nazwa, tresc in (dodatki or {}).items():
            plik(f"{dane}/{nazwa}", tresc, 10000)
    return bufor.getvalue()


# ---------------------------------------------------------------- atrapy

class Rejestr:
    def __init__(self, dane: dict):
        self.dane = dane                                # {klucz: {nazwa: wartość}}
        self.usuniete: list[tuple[str, str]] = []

    def podklucze(self, klucz: str) -> list[str]:
        przedrostek = klucz + "\\"
        return [k[len(przedrostek):] for k in self.dane
                if k.startswith(przedrostek) and "\\" not in k[len(przedrostek):]]

    def czytaj(self, klucz: str, nazwa: str):
        return self.dane.get(klucz, {}).get(nazwa)

    def zapisz(self, klucz: str, nazwa: str, wartosc: str) -> None:
        self.dane.setdefault(klucz, {})[nazwa] = wartosc

    def usun(self, klucz: str, nazwa: str) -> None:
        self.usuniete.append((klucz, nazwa))
        self.dane.get(klucz, {}).pop(nazwa, None)


WYNIK_ROZBROJENIA = "\n".join([
    "jakieś komunikaty systemd", "JARVO|uzytkownik|jarvo", f"JARVO|dom|{STARY_DOM}", f"JARVO|lokalny|{LOKALNY}",
    f"JARVO|env:JARVO_DATA|{LOKALNY}/data", f"JARVO|env:JARVO_SECRETS|{LOKALNY}/secrets",
    f"JARVO|env:JARVO_BUILD|{LOKALNY}/build", f"JARVO|env:JARVO_REPO|{REPO_STARE}", "JARVO|env:JARVO_VOL_HERMES|",
    "JARVO|docker|tak", "JARVO|kontener|jarvo-hermes|running", "JARVO|kontener|jarvo-searxng|running",
    "JARVO|updater|jednostka", "JARVO|linger|tak", f"JARVO|polecenie|{REPO_STARE}/bin/jarvo",
    "JARVO|krok|U1 zatrzymany", "JARVO|krok|U2 jednostka", "JARVO|krok|U2 linger", "JARVO|krok|U3 compose",
    "JARVO|zostalo|0", f"JARVO|krok|U4 {REPO_STARE}/bin/jarvo", "JARVO|koniec|ok"]) + "\n"


class Atrapa:
    """Programy starego systemu: zapisuje każde wywołanie (argv, stdin), odpowiada jak wsl.exe, docker, sudo."""

    def __init__(self, tar: bytes, *, dzialajace=("Ubuntu",), docker_kontenery=("jarvo-hermes|created",),
                 docker_dziala: bool = True):
        self.tar = tar
        self.wywolania: list[list[str]] = []
        self.wejscia: list[str] = []
        self.dzialajace = set(dzialajace)
        self.docker_kontenery = list(docker_kontenery)
        self.docker_dziala = docker_dziala
        self.przeniesione: list[str] = []
        self.blad_strumienia: Exception | None = None
        self.wynik_rozbrojenia = WYNIK_ROZBROJENIA
        self.argumenty_skryptow: list[list[str]] = []
        self.env_wsl: list[dict | None] = []

    def _nazwy(self, kierunek: str) -> str:
        pliki = ["auth.json", ".env", "profiles/jarvo/auth.json", "profiles/jarvo/.env"]
        klucz = "przeniesiony" if kierunek == "ukryj" else "przywrocony"
        return "".join(f"JARVO|{klucz}|{p}\n" for p in pliki) + "JARVO|koniec|ok\n"

    def uruchom(self, argv, wejscie=None, czas=None, env=None):
        argv = [str(a) for a in argv]
        self.wywolania.append(argv)
        self.wejscia.append(wejscie.decode("utf-8") if wejscie else "")
        prog = PurePosixPath(argv[0].replace("\\", "/")).name.lower()
        if prog in ("wsl.exe", "wsl"):
            self.env_wsl.append(env)
            if argv[1:3] == ["-l", "--running"]:
                return 0, "\n".join(sorted(self.dzialajace)) + "\n"
            if argv[1] == "--terminate":
                self.dzialajace.discard(argv[2])
                return 0, ""
            if argv[1] == "--unregister":
                return 0, ""
            if argv[1] == "-d":
                self.dzialajace.add(argv[2])                      # każdy start dystrybucji ją budzi
                return self._skrypt(argv, wejscie)
            return 1, "nieznane polecenie wsl"
        if prog in ("sudo",) and argv[1:3] == ["sh", "-s"]:
            return self._skrypt(argv, wejscie)
        if prog in ("docker", "docker.exe"):
            return self._docker(argv[1:], wejscie)
        if prog in ("taskkill.exe", "taskkill", "launchctl", "systemctl", "colima", "wscript.exe"):
            return 0, ""
        return 127, f"atrapa: nie znam {prog}"

    def _skrypt(self, argv, wejscie):
        skrypt = (wejscie or b"").decode("utf-8")
        argumenty = argv[argv.index("--") + 1:] if "--" in argv else []
        self.argumenty_skryptow.append(argumenty)
        if "rozbrojenie starej floty" in skrypt:
            if self.wynik_rozbrojenia != WYNIK_ROZBROJENIA:
                return 0, self.wynik_rozbrojenia
            if argumenty[1] == "tak" and not argv[0].lower().endswith("wsl.exe"):
                self.docker_kontenery = []                # Linux: ten sam Docker co host (U3 compose down)
            return 0, WYNIK_ROZBROJENIA
        if "nazwy starych logowań" in skrypt:
            kierunek = argv[-1]
            self.przeniesione.append(kierunek)
            return 0, self._nazwy(kierunek)
        if "wycofanie migracji" in skrypt:
            return 0, "JARVO|krok|jednostka\nJARVO|krok|linger\nJARVO|krok|polecenie\nJARVO|koniec|ok\n"
        if "sprzątanie starego systemu" in skrypt:
            return 0, "JARVO|krok|usuniete\nJARVO|koniec|ok\n"
        return 1, "atrapa: nieznany skrypt"

    def _docker(self, argv, wejscie):
        if not self.docker_dziala:
            return 1, "error during connect: Docker Desktop is not running"
        if argv[:2] == ["ps", "-a"] and "--format" in argv:
            return 0, "\n".join(self.docker_kontenery) + "\n"
        if argv[:2] == ["ps", "-q"]:
            wzor = next((a.split("=", 1)[1] for a in argv if a.startswith("name=")), "^")
            dzialajace = [k.split("|")[0] for k in self.docker_kontenery if k.endswith(("|running", "|restarting"))]
            dokladnie = wzor.endswith("$")
            wzor = wzor.strip("^$")
            return 0, "".join(f"{n}\n" for n in dzialajace if (n == wzor if dokladnie else n.startswith(wzor)))
        if argv[0] == "stop":
            self.docker_kontenery = [k.replace("|running", "|exited") if k.startswith(argv[-1] + "|") else k
                                     for k in self.docker_kontenery]
            return 0, ""
        if argv[:2] == ["ps", "-aq"]:
            return 0, "\n".join(k.split("|")[0] for k in self.docker_kontenery) + "\n"
        if argv[:3] == ["compose", "-p", "jarvo"] and argv[3] == "down":
            self.docker_kontenery = []
            return 0, ""
        if argv[:2] == ["run", "-i"]:
            return self._skrypt(argv, wejscie)
        if argv[0] in ("info", "update", "stop", "inspect", "images", "image", "volume"):
            return 0, ""
        return 1, f"atrapa docker: {argv}"

    @contextlib.contextmanager
    def strumien(self, argv):
        self.wywolania.append([str(a) for a in argv])
        self.wejscia.append("")
        if self.blad_strumienia:
            raise self.blad_strumienia
        yield io.BytesIO(self.tar)


class Natywne:
    """Instalacja natywna: zapisuje wywołania; hermes() sprawdza, że próba nie ma sekretów."""

    def __init__(self):
        self.wywolania: list[tuple] = []
        self.blad_hermesa: str | None = None
        self.katalogi_hermesa: list[Path] = []

    def zatrzymaj(self, u):
        self.wywolania.append(("zatrzymaj",))

    def uruchom(self, u):
        self.wywolania.append(("uruchom",))
        return "http://127.0.0.1:9119/"

    def konfiguracja(self, u, profile):
        self.wywolania.append(("konfiguracja", tuple(profile)))

    def skarbiec(self, u):
        self.wywolania.append(("skarbiec",))
        return "indeks 1 plików, punkt zapisu: tak"

    def flota(self, u):
        self.wywolania.append(("flota",))
        return {"agenci": ["jarvo"]}

    def hermes(self, u, argumenty, dom):
        self.wywolania.append(("hermes", tuple(argumenty), str(dom)))
        dom = Path(dom)
        if dom != u.dane:
            self.katalogi_hermesa.append(dom)
            assert dom.is_dir()
            sekrety = [p for p in dom.rglob("*") if p.is_file() and mig.sekretny(p.relative_to(dom).as_posix())]
            assert not sekrety, f"próba z sekretami: {sekrety}"
            assert not (dom / "profiles" / "jarvo" / "home" / ".ssh").exists()
        if self.blad_hermesa and dom != u.dane:
            return 1, self.blad_hermesa
        return 0, "ok"

    def doctor(self, u):
        self.wywolania.append(("doctor",))
        return {"bledy": 0, "uwagi": 1, "wyniki": []}

    def zajete_porty(self, u):
        return []

    def polecenie_cmd(self, u):
        return (f"@echo off\r\nrem {mig.ZNACZNIK_NATYWNY}: polecenie jarvo.\r\n\"python.exe\" -I -X utf8 "
                f"\"start.py\" --korzen \"{u.root}\" %*\r\n").encode("utf-8")

    def jako(self) -> mig.Natywne:
        return mig.Natywne(zatrzymaj=self.zatrzymaj, uruchom=self.uruchom, konfiguracja=self.konfiguracja,
                           skarbiec=self.skarbiec, flota=self.flota, hermes=self.hermes, doctor=self.doctor,
                           zajete_porty=self.zajete_porty, polecenie_cmd=self.polecenie_cmd)


def uklad(tmp: Path) -> Uklad:
    """Instalacja natywna w katalogu ze spacją i polskimi znakami (program w ścieżce ASCII, jak w c1)."""
    root = tmp / "Michał Żółć" / "Jarvo"
    u = Uklad(root=root, program=tmp / "program", dane=root / "dane", stan=root / "stan", logi=root / "logi",
              cache=root / "cache", build=root / "build")
    for k in (u.root, u.dane, u.stan, u.logi, u.program):
        k.mkdir(parents=True, exist_ok=True)
    app, hermes = u.program / "app" / "abc123", u.program / "hermes" / "f97608f178d1"
    (app / "jarvo").mkdir(parents=True)
    (app / "jarvo" / "start.py").write_text("", encoding="utf-8")
    hermes.mkdir(parents=True)
    (u.program / "current.json").write_text(json.dumps({"app": str(app), "hermes": str(hermes)}), encoding="utf-8")
    _zapisz(u.dane / "config.yaml", "natywny: tak\n")
    _zapisz(u.dane / "install_id", "natywny11111111111111111111111111\n")
    return u


@pytest.fixture
def windows(tmp_path):
    """Komputer Windows właściciela: Startup\\Jarvo.vbs, stary jarvo.cmd, Lxss z Ubuntu i Jarvo, RunOnce, Docker Desktop
    z martwą kopią stosu; archiwum eksportu WSL z ~/jarvo-local."""
    l, otwarte = stare_dane(tmp_path / "stara")
    tar = archiwum(l)
    for con in otwarte:
        con.close()
    u = uklad(tmp_path)
    la, ad, dom = tmp_path / "LocalAppData", tmp_path / "AppData", tmp_path / "dom"
    startup = ad / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    _zapisz(startup / "Jarvo.vbs", "' Jarvo\r\nCreateObject(\"WScript.Shell\").Run \"wsl.exe -d Ubuntu -u root -e "
                                   "sleep infinity\", 0, False\r\n")
    stary_cmd = ("@echo off\r\nrem Jarvo (install.ps1): jarvo in Windows runs jarvo in Linux (Ubuntu).\r\n"
                 "wsl.exe -d Ubuntu -u jarvo --cd ~ -e bash -c \"exec jarvo \\\"$@\\\"\" jarvo %*\r\n")
    _zapisz(la / "Jarvo" / "bin" / "jarvo.cmd", stary_cmd)
    (la / "Jarvo" / "wsl").mkdir(parents=True)
    _zapisz(la / "Jarvo" / "token.dat", "zaszyfrowany")
    dom.mkdir()
    rejestr = Rejestr({
        mig.LXSS: {"DefaultDistribution": "{u}"},
        mig.LXSS + "\\{u}": {"DistributionName": "Ubuntu", "BasePath": str(la / "Packages" / "Ubuntu"), "Version": 2},
        mig.LXSS + "\\{j}": {"DistributionName": "Jarvo", "BasePath": str(la / "Jarvo" / "wsl"), "Version": 2},
        mig.LXSS + "\\{d}": {"DistributionName": "docker-desktop", "BasePath": "x", "Version": 2},
        mig.RUNONCE: {mig.WPIS_RUNONCE: "powershell.exe -File install.ps1"},
    })
    atrapa = Atrapa(tar)
    log: list[str] = []
    s = mig.SystemMigracji(nazwa="windows", env={"LOCALAPPDATA": str(la), "APPDATA": str(ad)}, dom=dom,
                           uruchom=atrapa.uruchom, strumien=atrapa.strumien, rejestr=rejestr,
                           procesy=lambda: [{"pid": 4242, "wiersz": "wsl.exe -d Ubuntu -u root -e sleep infinity"}],
                           pytaj=lambda q: True, wypisz=log.append, teraz=lambda: TERAZ,
                           program=lambda n: "docker.exe" if n == "docker" else None, wsl="wsl.exe",
                           taskkill="taskkill.exe", polecenia_systemowe=(), sqlite=SQLITE_INSTALACJI)
    n = Natywne()
    return {"u": u, "s": s, "atrapa": atrapa, "n": n, "log": log, "rejestr": rejestr, "startup": startup,
            "cmd": la / "Jarvo" / "bin" / "jarvo.cmd", "stary_cmd": stary_cmd, "katalog": tmp_path / "Migracja D",
            "l": l}


def migruj(sr: dict, *argumenty: str) -> int:
    kod = mig.main(["--tak", "--katalog", str(sr["katalog"]), *argumenty], uklad=sr["u"], system=sr["s"],
                   natywne=sr["n"].jako())
    if kod:
        print("\n".join(sr["log"][-25:]))           # widać w raporcie pytest, gdy test się nie uda
    return kod


def _wartosc(db: Path, sql: str, *parametry):
    con = sqlite3.connect(db)
    try:
        return con.execute(sql, parametry).fetchall()
    finally:
        con.close()


def _natywna(u: Uklad, rel: str) -> str:
    """Ścieżka natywna w postaci bazy (Windows z „\\”)."""
    return str(u.dane.joinpath(*rel.split("/")))


# ---------------------------------------------------------------- filtr, nazwy, ścieżki

@pytest.mark.parametrize("rel,katalog,pominiety", [
    ("state.db", False, False), ("state.db-wal", False, False), ("state.db-shm", False, True),
    ("auth.json", False, False), (".env", False, False), ("pairing/telegram.json", False, False),
    ("cron/jobs.json", False, False), ("memories/USER.md", False, False), ("sessions/x.json", False, False),
    ("profiles/jarvo/home/.gitconfig", False, False), ("jarvo/knowledge/.git/objects/aa/bb", False, False),
    ("jarvo/knowledge/.git/index.lock", False, True), ("jarvo/workspaces/a/uv.lock", False, False),
    ("gateway.lock", False, True), ("inne.lock", False, True), ("gateway_state.json", False, True),
    ("profiles/jarvo/gateway.pid", False, True), ("processes.json", False, True), ("cron.pid", False, True),
    ("lazy-packages", True, True), ("bin/tirith", False, True), ("profiles/jarvo/bin/x", False, True),
    ("jarvo/workspaces/a/bin/cli.js", False, False), ("node_modules", True, True),
    ("jarvo/workspaces/a/node_modules/x.js", False, True), (".venv", True, True), ("a/__pycache__/b.pyc", False, True),
    (".npm/x", False, True), (".cache/x", False, True), ("cache/images/a.png", False, False),
    ("cache/models_dev.json", False, True), ("runtime/x", False, True), ("sandboxes", True, True),
    ("jarvo/narzedzia/x", False, True), ("jarvo/state/update.json", False, True),
    ("jarvo/state/praca.json", False, True),
    ("jarvo/state/preview-3.json", False, True), ("jarvo/state/agenci.json", False, False),
    ("jarvo/state/rozmowy.db", False, False), ("jarvo/state/wiedza.db", False, True),
    ("plugins/jarvo-hq/plugin.yaml", False, True), ("plugins/inny/plugin.yaml", False, False),
    ("profiles/jarvo/plugins/jarvo-wiedza", False, True), ("skins/jarvo.yaml", False, True), ("build/x", False, True),
    ("jarvo/models/paradee/model.onnx", False, False), ("browser-profiles", True, True), ("models/x", False, False),
])
def test_filtr_kopii(rel, katalog, pominiety):
    assert (mig.pomin(rel, katalog=katalog) is not None) is pominiety, mig.pomin(rel, katalog=katalog)


def test_nazwy_w_systemie_docelowym():
    assert mig.zla_nazwa("a:b.txt", "windows")
    assert mig.zla_nazwa("plik.", "windows")
    assert mig.zla_nazwa("CON", "windows") and mig.zla_nazwa("nul.txt", "windows")
    assert mig.zla_nazwa("a\\b", "windows")
    assert mig.zla_nazwa("zła\udc8anazwa", "macos") and mig.zla_nazwa("zła\udc8anazwa", "windows")
    assert mig.zla_nazwa("a:b.txt", "linux") is None and mig.zla_nazwa("a:b.txt", "macos") is None
    assert mig.zla_nazwa("Żółć notatka.md", "windows") is None
    assert mig.klucz_kolizji("A/Plik", "windows") == mig.klucz_kolizji("a/plik", "windows")
    assert mig.klucz_kolizji("zo\u0301lc", "macos") == mig.klucz_kolizji("zólc", "macos")
    assert mig.klucz_kolizji("A", "linux") is None


def test_mapa_sciezek_granica_i_najdluzszy_prefiks(tmp_path):
    u = uklad(tmp_path)
    z = mig.Zrodlo(rodzaj="wsl", system="windows", dane=DANE, repo=REPO_STARE)
    m = mig.mapa_sciezek(u, z)
    assert m.zamien("/opt/data/jarvo/workspaces/a") == _natywna(u, "jarvo/workspaces/a")
    assert m.zamien(f"{DANE}/jarvo/x") == _natywna(u, "jarvo/x")
    assert m.zamien("/opt/data") == str(u.dane)
    assert m.zamien("/opt/database/x") is None and m.zamien("/opt/dataX") is None
    assert m.zamien("/srv/inne") is None and m.zamien("tekst /opt/data/x") is None and m.zamien(5) is None
    assert m.zamien("/opt/data/jarvo/narzedzia/impeccable") == str(u.program / "narzedzia-floty" / "impeccable")
    assert m.zamien(f"{REPO_STARE}/scripts/a.py") == str(Path(json.loads(
        (u.program / "current.json").read_text(encoding="utf-8"))["app"]) / "scripts" / "a.py")
    assert m.zamien(f"{REPO_STARE}-local/x") is None                      # ~/jarvo nie łapie ~/jarvo-local
    assert m.zamien("/opt/jarvo/build/profiles/jarvo", posix=True) == (u.build / "profiles" / "jarvo").as_posix()
    w = mig.Mapa((("/opt/data", r"C:\Users\Michał Żółć\Jarvo\dane"),), windows=True)
    assert w.zamien("/opt/data/jarvo/a b") == r"C:\Users\Michał Żółć\Jarvo\dane\jarvo\a b"
    assert w.zamien("/opt/data/jarvo/a", posix=True) == "C:/Users/Michał Żółć/Jarvo/dane/jarvo/a"


def test_przepisanie_env_yaml_bez_zmian_reszty():
    m = mig.Mapa((("/opt/data", "/n/dane z spacją"), ("/opt/jarvo/build", "/n/build")), windows=False)
    tekst, n = mig.przepisz_env_tekst("# /opt/data komentarz\nA=/opt/data/x\nB='/opt/data/y'\nC=/srv/z\n"
                                      "export D=/opt/data\nPATH=/opt/jarvo/bin:/usr/bin\nE=\n", m)
    assert n == 3
    assert tekst.splitlines() == ["# /opt/data komentarz", 'A="/n/dane z spacją/x"', "B='/n/dane z spacją/y'",
                                  "C=/srv/z", 'export D="/n/dane z spacją"', "PATH=/opt/jarvo/bin:/usr/bin", "E="]
    tekst, n = mig.przepisz_yaml_tekst("name: jarvo\nsource: /opt/jarvo/build/profiles/jarvo  # komentarz\n"
                                       "lista:\n  - /opt/data/a\n  - \"/opt/data/b\"\nurl: http://x/opt/data\n", m)
    assert n == 3
    assert "source: /n/build/profiles/jarvo  # komentarz" in tekst
    assert "  - /n/dane z spacją/a" in tekst and '  - "/n/dane z spacją/b"' in tekst
    assert "url: http://x/opt/data" in tekst


def test_baza_sciezki_w_transakcji_messages_bez_zmian(tmp_path):
    db = tmp_path / "state.db"
    _baza_stanu(db, ["/opt/data/a", "/opt/database/b"])
    m = mig.Mapa((("/opt/data", "/nowe"), ("/opt/jarvo/repo", "/kod")), windows=False)
    zmiany = mig.przepisz_baze(db, m)
    assert zmiany == {"sessions.cwd": 1, "sessions.git_repo_root": 2}
    assert _wartosc(db, "SELECT cwd, git_repo_root FROM sessions ORDER BY id") == [("/nowe/a", "/kod"),
                                                                                  ("/opt/database/b", "/kod")]
    assert all("/opt/data/" in t for (t,) in _wartosc(db, "SELECT content FROM messages"))
    assert _wartosc(db, "PRAGMA integrity_check") == [("ok",)]
    assert not (tmp_path / "state.db-wal").exists() or (tmp_path / "state.db-wal").stat().st_size == 0
    assert mig.przepisz_baze(db, m) == {}                                      # drugi raz nic


def test_projekty_duplikaty_po_mapie(tmp_path):
    db = tmp_path / "projects.db"
    _projekty(db)
    m = mig.Mapa(((DANE, "/n"), ("/opt/data", "/n"), ("/opt/jarvo/repo", "/kod")), windows=False)
    zmiany = mig.przepisz_baze(db, m)
    assert _wartosc(db, "SELECT path FROM project_folders") == [("/n/jarvo/workspaces/strona",)]
    assert zmiany["project_folders.path (duplikaty)"] == 1
    assert _wartosc(db, "SELECT root FROM discovered_repos") == [("/opt/database/obce",)]


def test_rozmowy_tylko_w_wal_przechodza_razem_z_wal(tmp_path):
    """Kopia bez -wal zgubiłaby ostatnie rozmowy (f2): spis ma oba pliki, a po rozpakowaniu wpis jest w bazie."""
    d = tmp_path / "stare"
    con = _rozmowy_w_wal(d / "rozmowy.db")
    try:
        assert (d / "rozmowy.db-wal").stat().st_size > 0
        kopia_bez_wal = tmp_path / "bez-wal" / "rozmowy.db"
        kopia_bez_wal.parent.mkdir()
        kopia_bez_wal.write_bytes((d / "rozmowy.db").read_bytes())
        with contextlib.suppress(sqlite3.Error):
            assert _wartosc(kopia_bez_wal, "SELECT count(*) FROM wpisy") == [(0,)]
        bufor = io.BytesIO()
        with tarfile.open(fileobj=bufor, mode="w") as t:
            t.add(d, arcname="data")
    finally:
        con.close()
    spis = mig.kopiuj(io.BytesIO(bufor.getvalue()), [("data", "dane")], tmp_path / "kopia.tar", system_docelowy="linux")
    assert {"dane/rozmowy.db", "dane/rozmowy.db-wal"} <= set(spis["pliki"])
    cel = tmp_path / "cel"
    mig.rozpakuj(tmp_path / "kopia.tar", cel, mapa=None)
    assert _wartosc(cel / "rozmowy.db", "SELECT tekst FROM wpisy") == [("Ostatnia rozmowa przed migracją",)]


def test_kopia_filtr_dowiazania_problemy(tmp_path):
    l, otwarte = stare_dane(tmp_path / "stara")
    tar = archiwum(l, dodatki={"sessions/zła:nazwa.json": b"{}", "memories/Notatka.md": b"a",
                               "memories/notatka.md": b"b"})
    for con in otwarte:
        con.close()
    z = mig.Zrodlo(rodzaj="wsl", system="windows", dane=DANE, compose=f"{LOKALNY}/compose",
                   sekrety=f"{LOKALNY}/secrets")
    spis = mig.kopiuj(io.BytesIO(tar), z.reguly(), tmp_path / "kopia.tar", system_docelowy="windows")
    pliki = set(spis["pliki"])
    assert {"dane/state.db", "dane/jarvo/state/rozmowy.db", "dane/jarvo/state/rozmowy.db-wal", "dane/auth.json",
            "dane/profiles/jarvo/auth.json", "dane/jarvo/knowledge/.git/HEAD", "dane/cache/images/a.png",
            "dane/plugins/inny/plugin.yaml", "dane/jarvo/workspaces/migracja/uv.lock", "compose/.env",
            "compose/jarvo.env", "secrets/host.env", "secrets/jarvo-web.env"} <= pliki
    for zly in ("dane/gateway.pid", "dane/profiles/jarvo/bin/narzedzie", "dane/.npm/_cacache/x",
                "dane/jarvo/state/update.json", "dane/plugins/jarvo-hq/plugin.yaml", "dane/jarvo/state/wiedza.db",
                "dane/jarvo/knowledge/.git/index.lock", "compose/.host-version", "secrets/host.env.example"):
        assert zly not in pliki
    assert not any(p.startswith(("dane/../", "etc", "var")) or "build/BUILD.json" in p for p in pliki)
    assert spis["dowiazania"]["jarvo/workspaces/migracja/skarbiec"] == "/opt/data/jarvo/knowledge"
    assert "profiles/jarvo/plugins/jarvo-hq" not in spis["dowiazania"]
    assert spis["twarde"] == {"jarvo/workspaces/migracja/twardy.txt": "jarvo/workspaces/migracja/oryginal.txt"}
    assert spis["pliki"]["dane/auth.json"]["uid"] == 10000
    powody = {p["powod"].split(":")[0] for p in spis["problemy"]}
    assert any("niedozwolony" in p for p in powody) and any("kolizja" in p for p in powody)
    assert (tmp_path / "kopia.tar").is_file() and spis["sha256"] == hashlib.sha256(
        (tmp_path / "kopia.tar").read_bytes()).hexdigest()
    spis_linux = mig.kopiuj(io.BytesIO(tar), z.reguly(), tmp_path / "kopia2.tar", system_docelowy="linux")
    assert spis_linux["problemy"] == []


# ---------------------------------------------------------------- pełna migracja: Windows z WSL

def test_wykrycie_tylko_odczyt_bez_startu_wsl(windows):
    przed = sorted(p.relative_to(windows["u"].root).as_posix() for p in windows["u"].root.rglob("*"))
    kod = mig.main(["--tylko-wykryj"], uklad=windows["u"], system=windows["s"], natywne=windows["n"].jako())
    assert kod == 0
    tekst = "\n".join(windows["log"])
    assert "W1" in tekst and "Jarvo.vbs" in tekst and "W2" in tekst and "W4" in tekst and "W3" in tekst
    assert "dystrybucja WSL Ubuntu" in tekst and "Jarvo z przerwanej instalacji" in tekst and "token.dat" in tekst
    assert not any(a[1:2] == ["-d"] or a[1:2] == ["--export"] for a in windows["atrapa"].wywolania)
    assert windows["cmd"].read_bytes() == windows["stary_cmd"].encode()
    assert (windows["startup"] / "Jarvo.vbs").is_file()
    assert sorted(p.relative_to(windows["u"].root).as_posix() for p in windows["u"].root.rglob("*")) == przed


def test_bez_zgody_nic_sie_nie_zmienia(windows):
    windows["s"].pytaj = lambda q: False
    kod = mig.main(["--katalog", str(windows["katalog"])], uklad=windows["u"], system=windows["s"],
                   natywne=windows["n"].jako())
    assert kod == 3
    assert not any(a[1:2] in (["-d"], ["--export"], ["--terminate"]) for a in windows["atrapa"].wywolania)
    assert (windows["startup"] / "Jarvo.vbs").is_file() and windows["cmd"].read_bytes() == windows["stary_cmd"].encode()
    assert not (windows["u"].stan / mig.PLIK_STANU).exists() and not windows["katalog"].exists()


def test_migracja_windows_pelna(windows):
    u, a, n = windows["u"], windows["atrapa"], windows["n"]
    assert migruj(windows) == 0
    log = "\n".join(windows["log"])
    w = a.wywolania
    # kolejność: W1–W4 bez startu WSL, potem jeden start jako root, terminate, eksport, później drugi start (nazwy)
    indeks = {tuple(x[:2]): i for i, x in reversed(list(enumerate(w)))}
    start = next(i for i, x in enumerate(w) if x[1:2] == ["-d"])
    assert any(x[0] == "taskkill.exe" and "4242" in x for x in w[:start])
    assert any(x[:4] == ["docker.exe", "compose", "-p", "jarvo"] for x in w[:start])
    assert w[start][:7] == ["wsl.exe", "-d", "Ubuntu", "-u", "root", "-e", "sh"]
    assert "rozbrojenie starej floty" in a.wejscia[start]
    assert w[start + 1] == ["wsl.exe", "--terminate", "Ubuntu"]
    eksport = w.index(["wsl.exe", "--export", "Ubuntu", "-"])
    assert eksport == start + 2 and indeks[("wsl.exe", "--export")] == eksport
    starty = [i for i, x in enumerate(w) if x[1:2] == ["-d"]]
    assert len(starty) == 2 and "nazwy starych logowań" in a.wejscia[starty[1]]
    assert w[starty[1]][-3:] == [DANE, ".przeniesione-20261025", "ukryj"]
    assert w[starty[1] + 1] == ["wsl.exe", "--terminate", "Ubuntu"]
    assert not (windows["startup"] / "Jarvo.vbs").exists()
    assert (windows["katalog"] / "kopia-zapasowa" / "Jarvo.vbs").is_file()
    assert mig.ZNACZNIK_NATYWNY in windows["cmd"].read_text(encoding="utf-8")
    assert (windows["katalog"] / "kopia-zapasowa" / "jarvo.cmd").read_bytes() == windows["stary_cmd"].encode()
    assert windows["rejestr"].usuniete == [(mig.RUNONCE, mig.WPIS_RUNONCE)]
    # dane: bazy z -wal, przepisane ścieżki, messages bez zmian, skarbiec z .git
    d = u.dane
    assert _wartosc(d / "jarvo" / "state" / "rozmowy.db", "SELECT tekst, zalaczniki FROM wpisy") == [
        ("Ostatnia rozmowa przed migracją", json.dumps([{"path": _natywna(u, "jarvo/inbox/plik.txt"),
                                                          "nazwa": "plik.txt"}], ensure_ascii=False,
                                                        separators=(",", ":")))]
    assert json.loads(_wartosc(d / "jarvo" / "state" / "rozmowy.db", "SELECT pliki FROM przekazy")[0][0]) == [
        _natywna(u, "jarvo/workspaces/web/a.html")]
    cwds = dict(_wartosc(d / "state.db", "SELECT id, cwd FROM sessions"))
    assert cwds == {"s0": _natywna(u, "jarvo/workspaces/jarvo/projekt"), "s1": _natywna(u, "jarvo/workspaces/host"),
                    "s2": "/opt/database/obce", "s3": "/srv/inne"}
    assert {r for (r,) in _wartosc(d / "state.db", "SELECT DISTINCT git_repo_root FROM sessions")} == {
        str(Path(json.loads((u.program / "current.json").read_text(encoding="utf-8"))["app"]))}
    assert all("MEDIA:/opt/data/" in t or "/opt/data/jarvo/workspaces" in t
               for (t,) in _wartosc(d / "state.db", "SELECT content FROM messages"))
    assert _wartosc(d / "kanban.db", "SELECT workspace_path FROM tasks ORDER BY id") == [
        (_natywna(u, "jarvo/workspaces/migracja"),), (None,)]
    assert _wartosc(d / "kanban.db", "SELECT stored_path FROM task_attachments") == [
        (_natywna(u, "kanban/attachments/t1/plik.pdf"),)]
    assert _wartosc(d / "profiles" / "jarvo" / "state.db", "SELECT cwd FROM sessions") == [
        (_natywna(u, "profiles/jarvo/home"),)]
    for db in ("state.db", "kanban.db", "jarvo/state/rozmowy.db"):
        assert _wartosc(d / db, "PRAGMA integrity_check") == [("ok",)]
    assert (d / "jarvo" / "knowledge" / ".git" / "refs" / "heads" / "main").read_text(encoding="utf-8").strip() == \
        GIT_HEAD
    assert not (d / "jarvo" / "knowledge" / ".git" / "index.lock").exists()
    assert (d / "jarvo" / "knowledge" / "notatki" / "test.md").is_file()
    assert json.loads((d / "kanban" / "boards" / "projekt" / "board.json").read_text(encoding="utf-8"))[
        "default_workdir"] == _natywna(u, "jarvo/workspaces/projekt")
    dystrybucja = (d / "profiles" / "jarvo" / "distribution.yaml").read_text(encoding="utf-8")
    assert f"source: {(u.build / 'profiles' / 'jarvo').as_posix()}" in dystrybucja
    impeccable = (u.program / "narzedzia-floty" / "impeccable").as_posix()
    assert f"IMPECCABLE_HOME={impeccable}" in (d / "profiles" / "jarvo" / ".env").read_text(encoding="utf-8")
    assert f"TELEGRAM_BOT_TOKEN={TOKEN_TG}" in (d / ".env").read_text(encoding="utf-8")
    # rutyny wstrzymane do próbnej wiadomości na Telegram (I36)
    prace = {p["id"]: p for p in json.loads((d / "profiles" / "jarvo" / "cron" / "jobs.json").read_text(
        encoding="utf-8"))["jobs"]}
    assert prace["patrol"]["enabled"] is False and prace["patrol"]["state"] == "paused"
    assert prace["patrol"]["paused_reason"] == mig.POWOD_RUTYN
    assert prace["patrol"]["workdir"] == _natywna(u, "jarvo/workspaces/jarvo")
    assert prace["patrol"]["prompt"] == "Sprawdź /opt/data/jarvo/knowledge"            # proza zostaje
    # pominięte i natywne
    for zly in ("gateway.pid", "profiles/jarvo/bin/narzedzie", ".npm", "lazy-packages", "plugins/jarvo-hq", "skins",
                "jarvo/narzedzia", "jarvo/state/update.json", "jarvo/workspaces/migracja/node_modules"):
        assert not (d / zly).exists(), zly
    assert (d / "install_id").read_text(encoding="utf-8").startswith("natywny")
    assert (windows["katalog"] / "natywne-przed-importem" / "config.yaml").read_text(encoding="utf-8") == \
        "natywny: tak\n"
    assert "terminal" in (d / "config.yaml").read_text(encoding="utf-8")
    # dowiązania: bezwzględne przez mapę (Windows: junction), względne w danych, obce pominięte
    skarbiec = d / "jarvo" / "workspaces" / "migracja" / "skarbiec"
    assert (skarbiec / "notatki" / "test.md").is_file()
    if WINDOWS:
        assert os.path.isjunction(skarbiec)
    else:
        assert os.readlink(skarbiec) == str(d / "jarvo" / "knowledge")
    assert (d / "jarvo" / "workspaces" / "migracja" / "notatka.md").read_text(encoding="utf-8").startswith("# Notatka")
    assert not (d / "jarvo" / "workspaces" / "migracja" / "zewnetrzne").exists()
    assert "zewnetrzne" in log
    assert (d / "jarvo" / "workspaces" / "migracja" / "twardy.txt").read_text(encoding="utf-8") == "treść oryginału\n"
    # sekrety: scalenie do <dane>/jarvo/konfig, DASHBOARD_* tylko z --lan, bez SEARXNG_SECRET
    konfig = u.jarvo_dane / "konfig"
    assert f"TELEGRAM_BOT_TOKEN={TOKEN_TG}" in (konfig / "host.env").read_text(encoding="utf-8")
    assert (konfig / "jarvo.env").read_text(encoding="utf-8") == "TELEGRAM_OWNER_ID=1\n"
    assert (konfig / "jarvo-web.env").read_text(encoding="utf-8") == ""
    assert not (konfig / "panel.env").exists() and not (konfig / ".env").exists()
    # próba: bez sekretów (atrapa hermes to sprawdza), polecenia tylko do odczytu, katalog znika
    proby = [x for x in n.wywolania if x[0] == "hermes" and x[2] != str(u.dane)]
    assert [x[1] for x in proby] == [("-p", "default", "sessions", "list"), ("kanban", "list"),
                                     ("-p", "default", "cron", "list"), ("profile", "list")]
    assert not (windows["katalog"] / "proba").exists()
    # natywna instalacja: zatrzymana przed importem, konfiguracja I13, skarbiec, flota, start, doctor
    kroki = [x[0] for x in n.wywolania]
    assert kroki.index("zatrzymaj") < kroki.index("konfiguracja") < kroki.index("skarbiec") < kroki.index("flota") \
        < kroki.index("uruchom") < kroki.index("doctor")
    assert ("konfiguracja", ("jarvo",)) in n.wywolania
    # stan, dziennik, raport, manifest
    stan = json.loads((u.stan / mig.PLIK_STANU).read_text(encoding="utf-8"))
    assert stan["zakonczona"] and set(stan["etapy"]) == {"rozbrojenie-windows", "rozbrojenie", "kopia", "proba",
                                                         "import", "konfiguracja", "skarbiec", "unieszkodliwienie",
                                                         "kontrola", "flota", "start"}
    assert stan["zrodlo"]["dane"] == DANE and stan["zrodlo"]["uzytkownik"] == "jarvo"
    assert stan["wstrzymane_rutyny"] == [{"plik": "profiles/jarvo/cron/jobs.json", "id": "patrol"}]
    raport = json.loads((windows["katalog"] / "raport.json").read_text(encoding="utf-8"))
    assert raport["manifest_zgodny"] is True
    assert (windows["katalog"] / "kopia.tar.sha256").read_text(encoding="utf-8").split()[0] == \
        hashlib.sha256((windows["katalog"] / "kopia.tar").read_bytes()).hexdigest()
    dziennik = [json.loads(x) for x in (u.stan / mig.PLIK_DZIENNIKA).read_text(encoding="utf-8").splitlines()]
    assert [x["krok"] for x in dziennik][:4] == ["W1", "W2", "W3", "W4"]
    # żaden sekret nie trafił do wyjścia, logu, dziennika, stanu ani raportu
    pliki_tekstowe = [u.logi / mig.PLIK_LOGU, u.stan / mig.PLIK_DZIENNIKA, u.stan / mig.PLIK_STANU,
                      windows["katalog"] / "raport.json", windows["katalog"] / "spis.json",
                      windows["katalog"] / "resztki.json"]
    for sekret in (TOKEN_TG, KLUCZ_API, HASLO_PANELU, "odswiezanie-stare", "klucz-bramy", "proba-gh", "proba-git"):
        assert sekret not in log
        for p in pliki_tekstowe:
            assert sekret not in p.read_text(encoding="utf-8"), (sekret, p)
    # inne logowania agenta przeszły (próba ich nie miała: atrapa hermes to sprawdza)
    dom_agenta = d / "profiles" / "jarvo" / "home"
    assert (dom_agenta / ".config" / "gh" / "hosts.yml").is_file() and (dom_agenta / ".ssh" / "id_ed25519").is_file()
    assert (dom_agenta / ".git-credentials").is_file()
    # pliki właściciela o nazwach baz Hermesa: bez zmian (kanban.db z /opt w katalogu roboczym to jego dane)
    wlasne = d / "jarvo" / "workspaces" / "migracja"
    assert _wartosc(wlasne / "kanban.db", "SELECT workspace_path FROM tasks WHERE id='t1'") == [
        ("/opt/data/projekt-wlasciciela",)]
    assert (wlasne / "state.db").read_text(encoding="utf-8") == "to nie jest baza SQLite\n"
    assert not (d / "gateway.sock.path").exists() and not (d / "gateway.sock").exists()


def test_porownanie_manifestu_starych_danych_z_importem(windows):
    """To samo sprawdza CI (f5): manifest starego katalogu z filtrem kopii = manifest <dane> po imporcie."""
    windows["n"].flota = lambda u: {}
    assert mig.main(["--tak", "--bez-floty", "--bez-startu", "--katalog", str(windows["katalog"])],
                    uklad=windows["u"], system=windows["s"], natywne=windows["n"].jako()) == 0
    przed = mig.manifest(windows["l"] / "data" / "hermes", filtr=True)
    po = json.loads((windows["katalog"] / "manifest-po.json").read_text(encoding="utf-8"))
    stan = json.loads((windows["u"].stan / mig.PLIK_STANU).read_text(encoding="utf-8"))
    przed["dowiazania"].update({k: v for k, v in DOWIAZANIA.items() if not mig.pomin(k)})   # dowiązania są w tar
    assert przed["bazy"]["jarvo/state/rozmowy.db"]["wpisy"] == 1
    assert stan["pominiete_dowiazania"] == ["jarvo/workspaces/migracja/zewnetrzne"]         # cel poza danymi
    assert stan["duplikaty"] == {"projects.db": {"project_folders": 1}}
    opcje = {"przepisane": stan["przepisane"], "mapa": stan["mapa"], "duplikaty": stan["duplikaty"],
             "bez": {*mig.NATYWNE_ZOSTAJA, *stan["pominiete_dowiazania"]}}
    assert mig.porownaj(przed, po, **opcje) == []
    # manifest kopii liczy pliki jak manifest(): plik *.db bez nagłówka SQLite z sumą, bazy SQLite bez
    kopii = json.loads((windows["katalog"] / "manifest-kopii.json").read_text(encoding="utf-8"))
    assert kopii["pliki"]["jarvo/workspaces/migracja/state.db"] == przed["pliki"]["jarvo/workspaces/migracja/state.db"]
    assert not {"state.db", "jarvo/workspaces/migracja/kanban.db", "jarvo/state/rozmowy.db-wal"} & set(kopii["pliki"])
    po_zle = json.loads(json.dumps(po))
    po_zle["bazy"]["kanban.db"]["tasks"] = 1
    del po_zle["pliki"]["memories/USER.md"]
    po_zle["dowiazania"]["jarvo/workspaces/migracja/skarbiec"] = "/gdzie/indziej"
    assert len(mig.porownaj(przed, po_zle, **opcje)) == 3
    pliki = {"przed": windows["katalog"] / "a.json", "po": windows["katalog"] / "manifest-po.json"}
    pliki["przed"].write_text(json.dumps(przed), encoding="utf-8")
    assert mig.main(["--porownaj", str(pliki["przed"]), str(pliki["po"]), "--stan",
                     str(windows["u"].stan / mig.PLIK_STANU)], system=windows["s"]) == 0
    assert "Manifesty zgodne." in windows["log"][-1]


def test_drugi_przebieg_nic_nie_zmienia(windows):
    assert migruj(windows) == 0

    def migawka():
        wynik = {}
        for korzen in (windows["u"].root, windows["katalog"], windows["startup"].parent, windows["cmd"].parent):
            for p in sorted(korzen.rglob("*")):
                if p.is_file() and not p.is_symlink():
                    wynik[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        return wynik

    przed = migawka()
    wywolania = len(windows["atrapa"].wywolania)
    natywne = len(windows["n"].wywolania)
    assert migruj(windows) == 0
    assert "Nic do zrobienia" in windows["log"][-2] and "--wznow-rutyny" in windows["log"][-1]
    assert migawka() == przed
    nowe = windows["atrapa"].wywolania[wywolania:]
    assert all(x[1:3] == ["-l", "--running"] or x[1:3] == ["ps", "-a"] for x in nowe), nowe
    assert len(windows["n"].wywolania) == natywne


def test_drugi_przebieg_rozbraja_to_co_wrocilo(windows, posix):
    """Ktoś odtworzył autostart starej floty po migracji: drugi przebieg rozbraja go jeszcze raz, bez kopii
    i importu."""
    assert migruj(windows) == 0
    _zapisz(windows["startup"] / "Jarvo.vbs", "CreateObject(\"WScript.Shell\").Run \"wsl.exe -d Ubuntu -u root -e "
                                              "sleep infinity\", 0, False\r\n")
    przed = len(windows["atrapa"].wywolania)
    assert migruj(windows) == 0
    assert not (windows["startup"] / "Jarvo.vbs").exists()
    assert not any(x[1:2] in (["-d"], ["--export"]) for x in windows["atrapa"].wywolania[przed:])
    sr = posix("macos")
    assert migruj(sr) == 0
    plist = sr["dom"] / "Library" / "LaunchAgents" / f"{mig.AGENT_MACOS}.plist"
    _zapisz(plist, "<plist/>")
    przed = len(sr["atrapa"].wywolania)
    assert migruj(sr) == 0
    assert not plist.exists()
    assert not any(x[:2] in (["docker", "cp"], ["docker", "run"]) for x in sr["atrapa"].wywolania[przed:])


def test_przerwanie_i_wznowienie_bez_drugiego_eksportu(windows):
    windows["n"].blad_hermesa = "symulowany błąd próby"
    assert migruj(windows) == 1
    assert "symulowany" in "\n".join(windows["log"])
    stan = json.loads((windows["u"].stan / mig.PLIK_STANU).read_text(encoding="utf-8"))
    assert set(stan["etapy"]) == {"rozbrojenie-windows", "rozbrojenie", "kopia"}
    assert not (windows["katalog"] / "proba").exists()
    assert not (windows["u"].dane / "kanban.db").exists()                    # nic nie zaimportowane
    windows["n"].blad_hermesa = None
    przed = len(windows["atrapa"].wywolania)
    assert migruj(windows) == 0
    nowe = windows["atrapa"].wywolania[przed:]
    assert not any(x[1:2] in (["--export"],) for x in nowe)
    assert sum(1 for x in nowe if x[1:2] == ["-d"]) == 1                     # tylko drugi start (nazwy)
    assert (windows["u"].dane / "kanban.db").is_file()


def test_przerwany_import_wznawia_sie_bez_szkody(windows, monkeypatch):
    """kill -9 w połowie importu (f5): drugi przebieg rozpakowuje kopię od nowa, a natywne pliki zapisane wcześniej
    nie trafiają drugi raz do natywne-przed-importem."""
    prawdziwe = mig.przepisz_bazy
    wywolania = []

    def przerwij(katalog, mapa):
        wywolania.append(katalog)
        if len(wywolania) == 2:                      # 1 = próba, 2 = import
            raise mig.BladMigracji("symulowane przerwanie importu")
        return prawdziwe(katalog, mapa)

    monkeypatch.setattr(mig, "przepisz_bazy", przerwij)
    assert migruj(windows) == 1
    assert (windows["katalog"] / "natywne-przed-importem" / "config.yaml").is_file()
    monkeypatch.setattr(mig, "przepisz_bazy", prawdziwe)
    assert migruj(windows) == 0
    assert (windows["katalog"] / "natywne-przed-importem" / "config.yaml").read_text(encoding="utf-8") == \
        "natywny: tak\n"
    assert _wartosc(windows["u"].dane / "kanban.db", "SELECT workspace_path FROM tasks WHERE id='t1'") == [
        (_natywna(windows["u"], "jarvo/workspaces/migracja"),)]


def test_zle_nazwy_zatrzymuja_przed_importem(windows):
    l = windows["l"]
    windows["atrapa"].tar = archiwum(l, dodatki={"sessions/zła:nazwa.json": b"{}", "memories/Notatka.md": b"a",
                                                 "memories/notatka.md": b"b"})
    windows["s"].nazwa = "windows"
    assert migruj(windows) == 1
    log = "\n".join(windows["log"])
    assert "nazw nie da się utworzyć" in log and "zła:nazwa.json" in log and "kolizja" in log
    assert not (windows["u"].dane / "kanban.db").exists() and not (windows["u"].dane / "auth.json").exists()
    assert (windows["katalog"] / "kopia.tar").is_file() and (windows["katalog"] / "spis.json").is_file()


def test_wycofanie(windows):
    assert migruj(windows) == 0
    kod = mig.main(["--tak", "--wycofaj"], uklad=windows["u"], system=windows["s"], natywne=windows["n"].jako())
    assert kod == 0
    assert (windows["startup"] / "Jarvo.vbs").is_file()
    assert windows["cmd"].read_bytes() == windows["stary_cmd"].encode()
    assert windows["atrapa"].przeniesione == ["ukryj", "przywroc"]
    skrypty = [w for w in windows["atrapa"].wejscia if "wycofanie migracji" in w]
    assert len(skrypty) == 1
    wycofanie = next(x for x, w in zip(windows["atrapa"].wywolania, windows["atrapa"].wejscia)
                     if "wycofanie migracji" in w)
    assert wycofanie[-6:] == ["jarvo", ".przeniesione-20261025", "nie", "tak", f"{REPO_STARE}/bin/jarvo", "tak"]
    assert windows["n"].wywolania.count(("zatrzymaj",)) == 2
    stan = json.loads((windows["u"].stan / mig.PLIK_STANU).read_text(encoding="utf-8"))
    assert stan["wycofana"]
    assert mig.main(["--tak", "--wycofaj"], uklad=windows["u"], system=windows["s"], natywne=windows["n"].jako()) == 0
    assert "wycofana już" in windows["log"][-1]


def test_w2_bez_podmiany_przenosi_stare_polecenie(windows):
    """Korzeń spoza ASCII bez nazwy 8.3: cmd.exe nie odczyta natywnego jarvo.cmd (próba na żywo), więc stary plik
    idzie do kopii zapasowej, a `jarvo` z PATH trafia do instalacji natywnej; wycofanie go przywraca."""
    def bez_ascii(u):
        raise RuntimeError("ścieżka ma znaki spoza ASCII albo %, a cmd.exe ich nie odczyta. Ustaw JARVO_ROOT")
    windows["n"].polecenie_cmd = bez_ascii
    assert migruj(windows) == 0
    assert not windows["cmd"].exists()
    assert (windows["katalog"] / "kopia-zapasowa" / "jarvo.cmd").read_bytes() == windows["stary_cmd"].encode()
    assert "natywnego polecenia nie da się tu zapisać" in "\n".join(windows["log"])
    assert mig.main(["--tak", "--wycofaj"], uklad=windows["u"], system=windows["s"], natywne=windows["n"].jako()) == 0
    assert windows["cmd"].read_bytes() == windows["stary_cmd"].encode()


def test_nieoczekiwany_blad_bez_sladu_stosu_i_wznowienie(windows):
    def zepsuta(u, profile):
        raise RuntimeError("symulowany błąd konfiguracji")
    windows["n"].konfiguracja = zepsuta
    assert migruj(windows) == 1
    assert "BŁĄD: RuntimeError: symulowany błąd konfiguracji" in windows["log"][-1]
    windows["n"].konfiguracja = lambda u, profile: None
    assert migruj(windows) == 0
    assert any(t.startswith("Wznawiam migrację") for t in windows["log"])


def test_sprzatanie_po_okresie_przejsciowym(windows):
    assert migruj(windows) == 0
    sprzatanie = ["--sprzatanie", "--katalog", str(windows["katalog"])]
    assert mig.main(sprzatanie, uklad=windows["u"], system=windows["s"], natywne=windows["n"].jako()) == 1
    assert "Okres przejściowy" in windows["log"][-1]
    assert not any(x[1:2] == ["--unregister"] for x in windows["atrapa"].wywolania)
    windows["s"].teraz = lambda: TERAZ + 15 * 86400
    odpowiedzi = []
    # zgoda tylko na pytania o pustą dystrybucję i resztki instalatora (po początku pytania: ścieżka testu na
    # D:\JarvoTest\… też zawiera „Jarvo”, a pytanie o stare dane ma w sobie ścieżkę)
    windows["s"].pytaj = lambda q: (odpowiedzi.append(q),
                                    q.startswith(("Wyrejestrować dystrybucję Jarvo", "Resztki starego instalatora")))[1]
    assert mig.main(sprzatanie, uklad=windows["u"], system=windows["s"], natywne=windows["n"].jako()) == 0
    assert ["wsl.exe", "--unregister", "Jarvo"] in windows["atrapa"].wywolania
    assert not any(x[1:2] == ["--unregister"] and x[2] != "Jarvo" for x in windows["atrapa"].wywolania)
    assert not (windows["cmd"].parent.parent / "token.dat").exists()
    assert any("Stare dane" in q for q in odpowiedzi)
    assert not any("sprzątanie starego systemu" in w for w in windows["atrapa"].wejscia)   # bez zgody nic


def test_wznowienie_rutyn(windows):
    assert migruj(windows) == 0
    assert mig.main(["--wznow-rutyny"], uklad=windows["u"], system=windows["s"], natywne=windows["n"].jako()) == 0
    assert ("hermes", ("-p", "jarvo", "cron", "resume", "patrol"), str(windows["u"].dane)) in windows["n"].wywolania
    assert mig.main(["--wznow-rutyny"], uklad=windows["u"], system=windows["s"], natywne=windows["n"].jako()) == 0
    assert "wznowione już" in windows["log"][-1]


def test_lan_przenosi_tylko_dashboard(windows):
    assert migruj(windows, "--lan") == 0
    panel = mig.czytaj_env((windows["u"].jarvo_dane / "konfig" / "panel.env").read_text(encoding="utf-8"))
    assert panel == {"DASHBOARD_USER": "jarvo", "DASHBOARD_PASSWORD": HASLO_PANELU}


def test_bez_instalacji_natywnej_jasna_rada(windows):
    (windows["u"].program / "current.json").unlink()
    assert migruj(windows) == 1
    assert "nie jest zainstalowane" in windows["log"][-1]
    assert not any(x[1:2] == ["-d"] for x in windows["atrapa"].wywolania)


def test_docker_desktop_nie_dziala(windows):
    windows["atrapa"].docker_dziala = False
    assert migruj(windows) == 0
    log = "\n".join(windows["log"])
    assert "Docker Desktop nie działa" in log and "Docker Desktop nie odpowiada" in log


# ---------------------------------------------------------------- Linux (katalog z uid 10000) i macOS (wolumen)

@pytest.fixture
def posix(tmp_path):
    def zrob(system: str):
        baza = tmp_path / f"stary-{system}"
        dom = baza / "dom"
        l, otwarte = stare_dane(dom)
        if system == "macos":
            (l / "compose" / ".env").write_text("JARVO_VOL_HERMES=jarvo-hermes-data\nJARVO_BUILD=jarvo-build\n"
                                                f"DASHBOARD_PASSWORD={HASLO_PANELU}\n", encoding="utf-8")
            tar = archiwum(l, korzen_danych="data")
            _zapisz(dom / "Library" / "LaunchAgents" / f"{mig.AGENT_MACOS}.plist", "<plist/>")
        else:
            tar = archiwum(l, przedrostek="", tylko_dane=True)
            _zapisz(dom / ".config" / "systemd" / "user" / mig.JEDNOSTKA, "[Unit]\n")
        for con in otwarte:
            con.close()
        u = uklad(baza)
        atrapa = Atrapa(tar, dzialajace=(), docker_kontenery=("jarvo-hermes|running", "jarvo-searxng|running"))
        log: list[str] = []
        s = mig.SystemMigracji(nazwa=system, env={"USER": "jarvo"}, dom=dom, uruchom=atrapa.uruchom,
                               strumien=atrapa.strumien, rejestr=None, procesy=lambda: [], pytaj=lambda q: True,
                               wypisz=log.append, teraz=lambda: TERAZ,
                               program=lambda nazwa: nazwa if nazwa in ("docker", "colima") else None,
                               polecenia_systemowe=(), sqlite=SQLITE_INSTALACJI)
        return {"u": u, "s": s, "atrapa": atrapa, "n": Natywne(), "log": log, "katalog": baza / "migracja",
                "l": l, "dom": dom}
    return zrob


def test_migracja_linux_sudo_tar(posix):
    sr = posix("linux")
    # JARVO_DATA ze starego hosta (ścieżka z „/”, jak w compose/.env na Linuksie)
    (sr["l"] / "compose" / ".env").write_text(f"JARVO_DATA={LOKALNY}/data\nJARVO_REPO={REPO_STARE}\n",
                                              encoding="utf-8")
    assert migruj(sr) == 0
    w, wejscia = sr["atrapa"].wywolania, sr["atrapa"].wejscia
    rozbr = next(i for i, x in enumerate(w) if x[:3] == ["sudo", "sh", "-s"])
    assert "rozbrojenie starej floty" in wejscia[rozbr]
    # bez U5 i bez lingera; katalog starej instalacji znany z wykrycia (także spod JARVO_LOCAL)
    assert w[rozbr][-6:] == ["jarvo", "tak", "nie", "nie", ".przeniesione-20261025", str(sr["l"])]
    tar = next(i for i, x in enumerate(w) if x[:2] == ["sudo", "tar"])
    assert rozbr < tar and w[tar] == ["sudo", "tar", "-C", "/", "-cf", "-", DANE.lstrip("/")]
    assert not any("wsl" in x[0] for x in w)
    d = sr["u"].dane
    assert _wartosc(d / "kanban.db", "SELECT workspace_path FROM tasks WHERE id='t1'") == [
        (_natywna(sr["u"], "jarvo/workspaces/migracja"),)]
    konfig = sr["u"].jarvo_dane / "konfig"
    assert f"OPENROUTER_API_KEY={KLUCZ_API}" in (konfig / "host.env").read_text(encoding="utf-8")
    assert (konfig / "jarvo.env").is_file()
    nazwy = next(i for i, x in enumerate(w) if x[:3] == ["sudo", "sh", "-s"] and "nazwy starych" in wejscia[i])
    assert w[nazwy][-3:] == [DANE, ".przeniesione-20261025", "ukryj"]
    assert (sr["dom"] / ".config" / "systemd" / "user" / mig.JEDNOSTKA).is_file()   # jednostkę rusza skrypt (root)


@pytest.mark.posix_only          # U4 dotyczy gospodarza Linux/macOS: cel dowiązania to ścieżka POSIX (…/bin/jarvo)
@pytest.mark.wymaga_symlinku
def test_linux_stare_polecenie_w_local_bin(posix):
    sr = posix("linux")
    (sr["l"] / "compose" / ".env").write_text(f"JARVO_DATA={LOKALNY}/data\n", encoding="utf-8")
    link = sr["dom"] / ".local" / "bin" / "jarvo"
    link.parent.mkdir(parents=True)
    os.symlink(str(sr["dom"] / "jarvo" / "bin" / "jarvo"), link)
    assert migruj(sr) == 0
    assert not link.is_symlink()
    dziennik = (sr["u"].stan / mig.PLIK_DZIENNIKA).read_text(encoding="utf-8")
    assert "usuniete-dowiazanie" in dziennik


def test_migracja_macos_wolumen(posix):
    sr = posix("macos")
    assert migruj(sr) == 0
    w, wejscia = sr["atrapa"].wywolania, sr["atrapa"].wejscia
    stop = w.index(["docker", "stop", "-t", "70", "jarvo-hermes"])
    cp = w.index(["docker", "cp", "jarvo-hermes:/opt/data", "-"])
    down = w.index(["docker", "compose", "-p", "jarvo", "down"])
    assert any(x[:2] == ["launchctl", "bootout"] for x in w[:stop])
    assert stop < cp < down
    assert not (sr["dom"] / "Library" / "LaunchAgents" / f"{mig.AGENT_MACOS}.plist").exists()
    assert (sr["katalog"] / "kopia-zapasowa" / f"{mig.AGENT_MACOS}.plist").is_file()
    nazwy = next(i for i, x in enumerate(w) if x[:3] == ["docker", "run", "-i"])
    assert "nazwy starych logowań" in wejscia[nazwy] and w[nazwy][-3:] == ["/opt/data", ".przeniesione-20261025",
                                                                          "ukryj"]
    assert "-v" in w[nazwy] and "jarvo-hermes-data:/opt/data" in w[nazwy]
    d = sr["u"].dane
    assert _wartosc(d / "jarvo" / "state" / "rozmowy.db", "SELECT count(*) FROM wpisy") == [(1,)]
    konfig = sr["u"].jarvo_dane / "konfig"
    assert (konfig / "host.env").is_file() and not (konfig / "panel.env").exists()
    assert HASLO_PANELU not in "\n".join(sr["log"])


# ---------------------------------------------------------------- skrypty dla starego systemu

@pytest.mark.wymaga_bash
@pytest.mark.parametrize("nazwa", ["SKRYPT_ROZBROJENIA", "SKRYPT_NAZW", "SKRYPT_WYCOFANIA", "SKRYPT_SPRZATANIA"])
def test_skrypty_skladnia(nazwa, tmp_path):
    plik = tmp_path / f"{nazwa}.sh"
    plik.write_bytes(getattr(mig, nazwa).encode("utf-8"))
    w = uruchom_bash("-n", str(plik))
    assert w.returncode == 0, w.stderr
    assert "\r" not in getattr(mig, nazwa)


@pytest.mark.posix_only
@pytest.mark.parametrize("nazwa", ["SKRYPT_ROZBROJENIA", "SKRYPT_NAZW", "SKRYPT_WYCOFANIA", "SKRYPT_SPRZATANIA"])
def test_skrypty_skladnia_sh(nazwa, tmp_path):
    """W WSL i na Linuksie skrypty idą przez `sh -s` (Ubuntu: dash): bez konstrukcji basha."""
    plik = tmp_path / f"{nazwa}.sh"
    plik.write_bytes(getattr(mig, nazwa).encode("utf-8"))
    w = subprocess.run(["sh", "-n", str(plik)], capture_output=True, text=True)
    assert w.returncode == 0, w.stderr


@pytest.mark.wymaga_bash
def test_skrypt_nazw_ukrywa_i_przywraca(tmp_path):
    d = tmp_path / "dane"
    for rel in ("auth.json", ".env", "profiles/jarvo/auth.json", "profiles/jarvo/.env", "profiles/web/.env",
                ".codex/auth.json", "profiles/jarvo/memories/MEMORY.md"):
        _zapisz(d / rel, rel)
    skrypt = tmp_path / "nazwy.sh"
    skrypt.write_bytes(mig.SKRYPT_NAZW.encode("utf-8"))
    w = uruchom_bash(str(skrypt), d.as_posix(), ".przeniesione-20261025", "ukryj")
    wynik = mig.parsuj_wynik(w.stdout)
    assert wynik["koniec"] == "ok" and len(wynik["przeniesiony"]) == 6, w.stdout + w.stderr
    assert not (d / "auth.json").exists() and (d / "auth.json.przeniesione-20261025").is_file()
    assert (d / "profiles" / "jarvo" / "memories" / "MEMORY.md").is_file()
    w = uruchom_bash(str(skrypt), d.as_posix(), ".przeniesione-20261025", "przywroc")
    assert len(mig.parsuj_wynik(w.stdout)["przywrocony"]) == 6
    assert (d / "profiles" / "web" / ".env").read_text(encoding="utf-8") == "profiles/web/.env"


def test_parsuj_wynik():
    wynik = mig.parsuj_wynik(WYNIK_ROZBROJENIA.replace("\n", "\r\n") + "\x00")
    assert wynik["lokalny"] == LOKALNY and wynik["kontener"] == ["jarvo-hermes|running", "jarvo-searxng|running"]
    assert wynik["krok"][0] == "U1 zatrzymany" and wynik["koniec"] == "ok" and wynik["env:JARVO_VOL_HERMES"] == ""


# ---------------------------------------------------------------- pliki i systemy

def test_scal_env_jak_merge_env(tmp_path):
    cel = tmp_path / "konfig" / "host.env"
    _zapisz(cel, "# komentarz\nA=stare\nB=zostaje\n")
    klucze, zmieniony = mig.scal_env({"A": "nowe", "C": "dopisane", "D": "", "E": '""'}, cel)
    assert klucze == ["A", "C"] and zmieniony
    assert cel.read_text(encoding="utf-8") == "# komentarz\nA=nowe\nB=zostaje\nC=dopisane\n"
    assert mig.scal_env({"A": "nowe"}, cel) == (["A"], False)


@pytest.mark.posix_only
def test_tryby_plikow_po_imporcie(windows):
    assert migruj(windows) == 0
    d = windows["u"].dane
    for p in (d / "auth.json", d / ".env", d / "profiles" / "jarvo" / "auth.json", d / "state.db",
              windows["u"].jarvo_dane / "konfig" / "host.env"):
        assert (p.stat().st_mode & 0o777) == 0o600, p
    assert (windows["u"].jarvo_dane / "konfig").stat().st_mode & 0o777 == 0o700
    assert windows["katalog"].stat().st_mode & 0o777 == 0o700


@pytest.mark.windows_only
def test_junction_i_acl_na_windows(windows):
    assert migruj(windows) == 0
    skarbiec = windows["u"].dane / "jarvo" / "workspaces" / "migracja" / "skarbiec"
    assert os.path.isjunction(skarbiec)
    assert mig._cel_dowiazania(skarbiec).lower() == str(windows["u"].dane / "jarvo" / "knowledge").lower()
    w = subprocess.run(["icacls", str(windows["u"].jarvo_dane / "konfig" / "host.env")], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    assert os.environ.get("USERNAME", "").lower() in w.stdout.lower()
    assert "(I)" not in w.stdout                                       # bez dziedziczenia: tylko właściciel


def test_resztki_same_liczby(tmp_path):
    d = tmp_path / "d"
    _baza_stanu(d / "state.db", ["/opt/data/a"])
    _zapisz(d / "config.yaml", "a: /opt/data\nb: /opt/jarvo/bin/x\n")
    wynik = mig.resztki(d)
    assert wynik["pliki"] == {"config.yaml": 2}
    assert wynik["bazy"]["state.db:sessions.cwd"] == 1 and wynik["bazy"]["state.db:messages.content"] == 2
    assert all(isinstance(v, int) for v in wynik["bazy"].values())


def test_manifest_cli_i_git(tmp_path):
    d = tmp_path / "d"
    _zapisz(d / "jarvo" / "knowledge" / ".git" / "HEAD", GIT_HEAD + "\n")
    _zapisz(d / "a.txt", "a")
    _zapisz(d / "gateway.pid", "1")
    _kanban(d / "kanban.db", "/opt/data/x")
    wyjscie = tmp_path / "m.json"
    assert mig.main(["--manifest", str(d), "--filtr", "--wyjscie", str(wyjscie)]) == 0
    m = json.loads(wyjscie.read_text(encoding="utf-8"))
    assert m["git"] == {"jarvo/knowledge": GIT_HEAD} and "gateway.pid" not in m["pliki"] and "a.txt" in m["pliki"]
    assert m["bazy"]["kanban.db"]["tasks"] == 2 and not any(k.endswith("-wal") for k in m["pliki"])


def test_wstrzymaj_rutyny_drugi_raz_nic(tmp_path):
    p = tmp_path / "profiles" / "web" / "cron" / "jobs.json"
    _zapisz(p, json.dumps({"jobs": [{"id": "a", "enabled": True}, {"id": "b", "enabled": True, "state": "paused"}]}))
    assert mig.wstrzymaj_rutyny(tmp_path) == [{"plik": "profiles/web/cron/jobs.json", "id": "a"}]
    przed = p.read_bytes()
    assert mig.wstrzymaj_rutyny(tmp_path) == [] and p.read_bytes() == przed


def test_domyslny_system_pelne_sciezki():
    """Domyślny SystemMigracji (bez uruchamiania czegokolwiek): wsl.exe i taskkill z System32 pełną ścieżką (goła nazwa
    w CreateProcess szuka najpierw w katalogu bieżącym), na Windows rejestr przez winreg."""
    s = mig.SystemMigracji(pytaj=lambda q: False, wypisz=lambda t: None)
    if WINDOWS:
        assert s.wsl.lower().endswith("\\system32\\wsl.exe") and s.taskkill.lower().endswith("\\system32\\taskkill.exe")
        assert isinstance(s.rejestr, mig.RejestrWindows) and s.nazwa == "windows"
    else:
        assert s.rejestr is None and s.nazwa in ("linux", "macos")
    assert s.folder_autostartu() == (mig._folder_autostartu(s.env))


# ---------------------------------------------------------------- przegląd: bramki, nazwy, bazy właściciela, wycofanie

def test_pomoc_i_zle_argumenty_bez_wyjatku(capsys):
    """`jarvo migruj --help` i złe argumenty: kod jak w cli.main (argparse nie kończy procesu polecenia jarvo)."""
    assert mig.main(["--help"]) == 0
    assert "jarvo migruj" in capsys.readouterr().out
    assert mig.main(["--nieznana-opcja"]) == 2
    assert mig.main(["--linger", "zawsze"]) == 2


def test_stary_sqlite_zatrzymuje_przed_zmianami(windows):
    """Z14: bazy w WAL przepisujemy tylko na SQLite 3.51.3+; na starszym nic się nie zmienia, a rada wskazuje jarvo."""
    windows["s"].sqlite = (3, 49, 1)
    assert migruj(windows) == 1
    assert "WAL-reset" in windows["log"][-1] and "jarvo migruj" in windows["log"][-1]
    assert not any(x[1:2] in (["-d"], ["--export"], ["--terminate"]) for x in windows["atrapa"].wywolania)
    assert (windows["startup"] / "Jarvo.vbs").is_file() and windows["cmd"].read_bytes() == windows["stary_cmd"].encode()
    assert not (windows["u"].stan / mig.PLIK_STANU).exists() and not windows["katalog"].exists()


def test_wywolania_wsl_z_utf8(windows):
    """Każde wywołanie wsl.exe z migracji ma WSL_UTF8=1 (bez niej wsl.exe pisze do potoku w UTF-16)."""
    assert windows["s"].env_wsl()["WSL_UTF8"] == "1"
    assert migruj(windows) == 0
    assert windows["atrapa"].env_wsl and all(e and e.get("WSL_UTF8") == "1" for e in windows["atrapa"].env_wsl)


@pytest.mark.parametrize("rel,nazwa", [
    ("state.db", "state.db"), ("profiles/jarvo/state.db", "state.db"), ("projects.db", "projects.db"),
    ("profiles/web/projects.db", "projects.db"), ("kanban.db", "kanban.db"),
    ("kanban/boards/projekt/kanban.db", "kanban.db"), ("jarvo/state/rozmowy.db", "rozmowy.db"),
    ("jarvo/workspaces/a/state.db", None), ("jarvo/workspaces/a/kanban.db", None),
    ("profiles/jarvo/home/state.db", None),
    ("kanban/kanban.db", None), ("rozmowy.db", None), ("profiles/jarvo/jarvo/state/rozmowy.db", None),
])
def test_bazy_hermesa_tylko_w_ich_miejscach(rel, nazwa):
    assert mig.baza_hermesa(rel) == nazwa


@pytest.mark.parametrize("rel,sekret", [
    ("auth.json", True), ("profiles/jarvo/.env", True), ("profiles/jarvo/home/.codex/auth.json", True),
    ("vault.key", True), ("profiles/jarvo/home/.ssh/id_ed25519", True), ("profiles/jarvo/home/.ssh", True),
    ("home/.gnupg/pubring.kbx", True), ("profiles/jarvo/home/.config/gh/hosts.yml", True),
    (".docker/config.json", True), ("profiles/jarvo/home/.git-credentials", True), ("home/.netrc", True),
    ("profiles/jarvo/home/.npmrc", True), ("jarvo/workspaces/a/hosts.yml", False), ("memories/USER.md", False),
    ("profiles/jarvo/home/.gitconfig", False), ("jarvo/workspaces/a/config.json", False), ("sessions/x.json", False),
])
def test_sekretny(rel, sekret):
    assert mig.sekretny(rel) is sekret


def test_jest_sqlite(tmp_path):
    db = tmp_path / "a.db"
    _kanban(db, "/opt/data/x")
    (tmp_path / "pusta.db").write_bytes(b"")
    (tmp_path / "tekst.db").write_text("nie baza", encoding="utf-8")
    assert mig.jest_sqlite(db) and mig.jest_sqlite(tmp_path / "pusta.db")
    assert not mig.jest_sqlite(tmp_path / "tekst.db") and not mig.jest_sqlite(tmp_path / "nie-ma.db")


def test_manifest_i_porownanie_baz_nieczytelnych(tmp_path):
    """Plik *.db bez nagłówka SQLite to zwykły plik z sumą; baza nieczytelna przed i po to nie różnica."""
    d = tmp_path / "d"
    _zapisz(d / "jarvo" / "workspaces" / "a" / "notatki.db", "tekst właściciela")
    _kanban(d / "kanban.db", "/opt/data/x")
    m = mig.manifest(d)
    assert "jarvo/workspaces/a/notatki.db" in m["pliki"] and set(m["bazy"]) == {"kanban.db"}
    przed = {"bazy": {"x.db": {"blad": "database disk image is malformed"}, "kanban.db": {"tasks": 2}}}
    assert mig.porownaj(przed, {"bazy": dict(przed["bazy"])}) == []
    assert mig.porownaj(przed, {"bazy": {"x.db": {"tasks": 1}, "kanban.db": {"tasks": 2}}}) == [
        "x.db: przed migracją nieczytelna (database disk image is malformed), po: czytelna"]


def test_projekt_zachowuje_folder_glowny_przy_duplikacie(tmp_path):
    db = tmp_path / "projects.db"
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE project_folders (project_id TEXT NOT NULL, path TEXT NOT NULL, label TEXT,
                                      is_primary INTEGER NOT NULL DEFAULT 0, added_at INTEGER NOT NULL,
                                      PRIMARY KEY (project_id, path));
    """)
    con.execute("INSERT INTO project_folders VALUES ('p1', '/opt/data/jarvo/workspaces/s', NULL, 0, 1)")
    con.execute("INSERT INTO project_folders VALUES ('p1', ?, NULL, 1, 2)", (f"{DANE}/jarvo/workspaces/s",))
    con.commit()
    con.close()
    m = mig.Mapa(((DANE, "/n"), ("/opt/data", "/n")), windows=False)
    zmiany = mig.przepisz_baze(db, m)
    assert _wartosc(db, "SELECT path, is_primary FROM project_folders") == [("/n/jarvo/workspaces/s", 1)]
    assert zmiany["project_folders.path (duplikaty)"] == 1


def test_wstrzymane_rutyny_maja_czas_iso_jak_hermes(tmp_path):
    import datetime
    p = tmp_path / "cron" / "jobs.json"
    _zapisz(p, json.dumps({"jobs": [{"id": "a", "enabled": True}]}))
    mig.wstrzymaj_rutyny(tmp_path)
    praca = json.loads(p.read_text(encoding="utf-8"))["jobs"][0]
    assert datetime.datetime.fromisoformat(praca["paused_at"]).tzinfo is not None
    assert praca["enabled"] is False and praca["state"] == "paused"


def test_rozbrojenie_bez_jarvo_local_nic_nie_zmienia(windows):
    """Zła dystrybucja (bez ~/jarvo-local): skrypt kończy się po inspekcji, eksportu nie ma, a dane zostają."""
    windows["atrapa"].wynik_rozbrojenia = "JARVO|uzytkownik|\nJARVO|dom|\nJARVO|lokalny|\nJARVO|koniec|brak\n"
    assert migruj(windows) == 1
    assert "nie ma ~/jarvo-local" in windows["log"][-1] and "niczego tam nie zmieniłem" in windows["log"][-1]
    assert not any(x[1:2] == ["--export"] for x in windows["atrapa"].wywolania)
    stan = json.loads((windows["u"].stan / mig.PLIK_STANU).read_text(encoding="utf-8"))
    assert set(stan["etapy"]) == {"rozbrojenie-windows"}
    assert ["wsl.exe", "--terminate", "Ubuntu"] in windows["atrapa"].wywolania      # start skryptu i tak ją obudził


def test_wsl_dane_w_wolumenie_dockera(windows, tmp_path):
    """JARVO_VOLUMES=1 w WSL: dane w wolumenie Dockera dystrybucji; eksport ma je w katalogu Dockera."""
    wolumen = "/var/lib/docker/volumes/jarvo-hermes-data/_data"
    l, otwarte = stare_dane(tmp_path / "stara-wolumen")
    for con in otwarte:
        con.close()
    bufor = io.BytesIO()
    with tarfile.open(fileobj=bufor, mode="w", format=tarfile.PAX_FORMAT) as t:
        t.add(l / "data" / "hermes", arcname=f".{wolumen}")
        for nazwa in ("compose", "secrets"):
            t.add(l / nazwa, arcname=f"./{LOKALNY.lstrip('/')}/{nazwa}")
    windows["atrapa"].tar = bufor.getvalue()
    windows["atrapa"].wynik_rozbrojenia = WYNIK_ROZBROJENIA.replace(
        "JARVO|env:JARVO_VOL_HERMES|", f"JARVO|env:JARVO_VOL_HERMES|jarvo-hermes-data\nJARVO|wolumen|{wolumen}")
    assert migruj(windows) == 0
    stan = json.loads((windows["u"].stan / mig.PLIK_STANU).read_text(encoding="utf-8"))
    assert stan["zrodlo"]["dane"] == wolumen and stan["zrodlo"]["wolumen"] == "jarvo-hermes-data"
    nazwy = [a for a in windows["atrapa"].argumenty_skryptow if a[-1:] == ["ukryj"]]
    assert nazwy == [[wolumen, ".przeniesione-20261025", "ukryj"]]
    assert _wartosc(windows["u"].dane / "kanban.db", "SELECT workspace_path FROM tasks WHERE id='t1'") == [
        (_natywna(windows["u"], "jarvo/workspaces/migracja"),)]
    # sprzątanie po okresie przejściowym: wolumen danych tylko za osobną zgodą, przez skrypt w dystrybucji
    windows["s"].teraz = lambda: TERAZ + 15 * 86400
    windows["s"].pytaj = lambda q: "Wolumen danych" in q
    assert mig.main(["--sprzatanie", "--katalog", str(windows["katalog"])], uklad=windows["u"], system=windows["s"],
                    natywne=windows["n"].jako()) == 0
    assert windows["atrapa"].argumenty_skryptow[-1] == ["wolumen", "jarvo-hermes-data"]


def test_druga_migracja_po_wycofaniu(windows):
    """Wycofanie, potem migracja od nowa: natywne pliki sprzed pierwszego importu zostają w swoim katalogu, a drugie
    wycofanie cofa tylko zmiany drugiej migracji (dziennik zostaje po pierwszej)."""
    assert migruj(windows) == 0
    pierwsza = json.loads((windows["u"].stan / mig.PLIK_STANU).read_text(encoding="utf-8"))["id"]
    assert mig.main(["--tak", "--wycofaj"], uklad=windows["u"], system=windows["s"], natywne=windows["n"].jako()) == 0
    windows["atrapa"].docker_kontenery = ["jarvo-hermes|created"]
    assert migruj(windows) == 0
    stan = json.loads((windows["u"].stan / mig.PLIK_STANU).read_text(encoding="utf-8"))
    assert stan["id"] != pierwsza and not stan.get("wycofana")
    katalog = windows["katalog"]
    assert (katalog / "natywne-przed-importem" / "config.yaml").read_text(encoding="utf-8") == "natywny: tak\n"
    drugi = Path(stan["import"]["katalog_natywnych"])
    assert drugi != katalog / "natywne-przed-importem" and (drugi / "config.yaml").is_file()
    assert "terminal" in (drugi / "config.yaml").read_text(encoding="utf-8")       # dane z pierwszego importu
    wpisy = mig.wpisy_dziennika(windows["u"])
    assert {w.get("migracja") for w in wpisy} == {pierwsza, stan["id"]}
    przywrocone = len([t for t in windows["log"] if "przywrócony" in t])
    assert mig.main(["--tak", "--wycofaj"], uklad=windows["u"], system=windows["s"], natywne=windows["n"].jako()) == 0
    assert len([t for t in windows["log"] if "przywrócony" in t]) - przywrocone == 2         # vbs i jarvo.cmd raz
    assert (windows["startup"] / "Jarvo.vbs").is_file() and windows["cmd"].read_bytes() == windows["stary_cmd"].encode()


def test_wycofanie_macos(posix):
    sr = posix("macos")
    assert migruj(sr) == 0
    assert mig.main(["--tak", "--wycofaj"], uklad=sr["u"], system=sr["s"], natywne=sr["n"].jako()) == 0
    plist = sr["dom"] / "Library" / "LaunchAgents" / f"{mig.AGENT_MACOS}.plist"
    assert plist.is_file()
    w = sr["atrapa"].wywolania
    assert ["launchctl", "bootstrap", f"gui/{os.getuid() if hasattr(os, 'getuid') else 0}", str(plist)] in w
    assert sr["atrapa"].przeniesione == ["ukryj", "przywroc"]
    assert any(x[-3:] == ["/opt/data", ".przeniesione-20261025", "przywroc"] and "-v" in x for x in w)


@pytest.mark.wymaga_bash
def test_skrypt_rozbrojenia_bez_jarvo_local_konczy_po_inspekcji(tmp_path):
    """Prawdziwy skrypt (Git Bash albo bash): nieznany użytkownik i brak ~/jarvo-local = „koniec brak” zaraz po
    inspekcji, przed Dockerem i przed U1–U5."""
    plik = tmp_path / "rozbrojenie.sh"
    plik.write_bytes(mig.SKRYPT_ROZBROJENIA.encode("utf-8"))
    w = uruchom_bash(str(plik), "nie-ma-takiego-uzytkownika-jarvo", "tak", "nie", "nie", ".przeniesione-x", "-",
                     timeout=60)
    wynik = mig.parsuj_wynik(w.stdout)
    assert wynik.get("koniec") == "brak" and wynik.get("lokalny") == "", w.stdout + w.stderr
    assert "docker" not in wynik and "krok" not in wynik


@pytest.mark.posix_only
def test_potoki_i_gniazda_nie_blokuja_manifestu():
    """Gniazdo bramy (gateway.sock) i potoki w danych: manifest, resztki i przepisanie plików je pomijają (otwarcie
    potoku czekałoby bez końca), tak jak kopia."""
    import shutil
    import socket
    import tempfile
    d = Path(tempfile.mkdtemp(prefix="jm", dir="/tmp"))           # krótka ścieżka: AF_UNIX ma limit 104 bajtów
    try:
        _zapisz(d / "a.txt", "/opt/data/x\n")
        os.mkfifo(d / "potok")
        gniazdo = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        gniazdo.bind(str(d / "gateway.sock"))
        try:
            m = mig.manifest(d)
            assert set(m["pliki"]) == {"a.txt"}
            assert mig.resztki(d)["pliki"] == {"a.txt": 1}
            assert mig.przepisz_pliki(d, mig.Mapa((("/opt/data", "/n"),), windows=False)) == {}
        finally:
            gniazdo.close()
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.mark.posix_only
def test_sekrety_bez_prawa_odczytu_ida_przez_sudo_tar(posix):
    """secrets/ z plikiem, którego ten użytkownik nie przeczyta (np. po chown na root): katalog idzie do `sudo tar`."""
    sr = posix("linux")
    sekret = sr["l"] / "secrets" / "host.env"
    sekret.chmod(0)
    try:
        if os.access(sekret, os.R_OK):
            pytest.skip("root czyta każdy plik")
        assert not mig._czytelne_env(sr["l"] / "secrets") and mig._czytelne_env(sr["l"] / "compose")
    finally:
        sekret.chmod(0o600)


def test_dowiazanie_bezwzgledne_z_kropkami_nie_wychodzi_poza_dane(tmp_path):
    """Cel z „..” pod starym prefiksem (/opt/data/../../etc/passwd) po samej zamianie prefiksu wskazywałby poza
    <dane>; po normpath to /etc/passwd, poza mapą, więc dowiązania nie ma. Cel w danych z „.” i „..” działa."""
    dane = tmp_path / "dane"
    (dane / "jarvo" / "knowledge").mkdir(parents=True)
    mapa = mig.Mapa((("/opt/data", str(dane)),))
    for cel in ("/opt/data/../../etc/passwd", "/opt/data/jarvo/../../../etc", "/opt/data/./jarvo/../../.."):
        opis = mig._utworz_dowiazanie(dane, "w/ucieczka", cel, mapa, junction=WINDOWS)
        assert opis and "poza danymi" in opis, cel
        assert not os.path.lexists(dane / "w" / "ucieczka"), cel
    assert mig._utworz_dowiazanie(dane, "w/skarbiec", "/opt/data/jarvo/./x/../knowledge", mapa, junction=WINDOWS) is None
    assert (dane / "w" / "skarbiec").resolve() == (dane / "jarvo" / "knowledge").resolve()
    przed = {"dowiazania": {"w/skarbiec": "/opt/data/jarvo/./x/../knowledge"}, "pliki": {}, "bazy": {}, "git": {}}
    po = {"dowiazania": {"w/skarbiec": str(dane / "jarvo" / "knowledge")}, "pliki": {}, "bazy": {}, "git": {}}
    assert mig.porownaj(przed, po, mapa={"/opt/data": str(dane)}, bez=()) == []
