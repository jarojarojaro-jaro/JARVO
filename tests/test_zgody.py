"""Wtyczka jarvo-zgody (zgody/plugin): tryby zgód na atrapie kontekstu wtyczki, bez Hermesa (docs/NATYWNIE.md, sekcja d).

Atrapy łącznika z Hermesem (człowiek obecny, bez YOLO, Hermes sam o nic nie pyta) ustawia fixture `sr`; test, który
sprawdza inną sytuację, podmienia jedną funkcję. Ścieżki to katalogi tymczasowe: <tmp>/dane (HERMES_HOME profilu
jarvo = <tmp>/dane/profiles/jarvo), <tmp>/projekt (TERMINAL_CWD, czyli katalog startu czatu) i <tmp>/poza.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
WINDOWS = os.name == "nt"
LINUX = sys.platform.startswith("linux")

_spec = importlib.util.spec_from_file_location("jarvo_zgody_plugin", REPO / "zgody" / "plugin" / "__init__.py")
z = importlib.util.module_from_spec(_spec)
sys.modules["jarvo_zgody_plugin"] = z
_spec.loader.exec_module(z)
DOMYSLNY_W_KODZIE = z.DOMYSLNY_TRYB        # prawdziwy domyślny tryb (test niżej); reszta testów stoi na „projekt”

ZMIENNE = ["HERMES_HOME", "TERMINAL_CWD", "JARVO_FOLDER_PROJEKTU", "JARVO_TRYB_ZGOD", "HERMES_KANBAN_TASK",
           "HERMES_KANBAN_WORKSPACE", "HERMES_CRON_SESSION", "HERMES_SINGLE_QUERY_SESSION",
           "HERMES_DELEGATED_CHILD_CONTEXT", "HERMES_YOLO_MODE", "HERMES_SESSION_PLATFORM", "HERMES_EXEC_ASK",
           "JARVO_KNOWLEDGE_DIR", "JARVO_MISSIONS_DIR", "JARVO_ROOT", "HERMES_SRC", "JARVO_REPO", "NIEZNANA_ZM"]


class AtrapaKontekstu:
    """To, czego wtyczka używa z hermes_cli.plugins.PluginContext: register_hook i register_command (plugins.py:659-683)."""

    def __init__(self):
        self.haki: dict = {}
        self.polecenia: dict = {}

    def register_hook(self, nazwa, funkcja):
        self.haki.setdefault(nazwa, []).append(funkcja)

    def register_command(self, nazwa, handler, description="", args_hint="", argument_mode=None):
        self.polecenia[nazwa] = {"handler": handler, "description": description, "args_hint": args_hint}


@dataclass
class Sr:
    tmp: Path
    dane: Path
    home: Path
    proj: Path
    poza: Path
    dom: Path
    wiedza: Path
    misje: Path
    ws_root: Path


@pytest.fixture
def sr(tmp_path, monkeypatch):
    dane = tmp_path / "dane"
    home = dane / "profiles" / "jarvo"
    s = Sr(tmp_path, dane, home, tmp_path / "projekt", tmp_path / "poza", tmp_path / "dom",
           dane / "jarvo" / "knowledge", dane / "jarvo" / "missions", dane / "jarvo" / "workspaces")
    for d in (home, s.proj / "src", s.poza, s.dom, s.wiedza, s.misje, s.ws_root / "jarvo"):
        d.mkdir(parents=True)
    (s.proj / "a.txt").write_text("a\n", encoding="utf-8")
    for k in ZMIENNE:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("TERMINAL_CWD", str(s.proj))
    monkeypatch.setattr(z, "_hermes_home", lambda: Path(os.environ["HERMES_HOME"]))
    monkeypatch.setattr(z, "_ktos_odpowie", lambda: True)
    monkeypatch.setattr(z, "_yolo", lambda: False)
    monkeypatch.setattr(z, "_hermes_niebezpieczne", lambda polecenie: False)
    monkeypatch.setattr(z, "_hermes_dozwolone_na_stale", lambda polecenie: False)
    monkeypatch.setattr(z, "_hermes_pyta_o_instrukcje", lambda sciezka, task_id: False)
    monkeypatch.setattr(z, "_hermes_odmowi_zapisu", lambda sciezka: False)
    monkeypatch.setattr(z, "_hermes_pyta_o_kod", lambda: False)
    monkeypatch.setattr(z, "_plik_konfigu", lambda: os.path.join(os.environ["HERMES_HOME"], "config.yaml"))
    monkeypatch.setattr(z, "_baza", lambda task_id: os.environ.get("TERMINAL_CWD"))
    monkeypatch.setattr(z, "_terminal_cwd", lambda: os.environ.get("TERMINAL_CWD", ""))
    monkeypatch.setattr(z, "_dom", lambda: str(s.dom))
    monkeypatch.setattr(z, "_domy", lambda: [str(s.dom)])                 # strażnik kasowania: tylko dom testu
    monkeypatch.setattr(z, "_tymczasowe", lambda: [str(tmp_path / "temp")])
    monkeypatch.setattr(z, "_podagent", lambda: bool(os.environ.get("HERMES_DELEGATED_CHILD_CONTEXT")))
    monkeypatch.setattr(z, "_env_sesji", lambda nazwa: os.environ.get(nazwa, ""))
    monkeypatch.setattr(z, "_TRYB_W_PROCESIE", {})
    monkeypatch.setattr(z, "_STAN_CACHE", {})
    monkeypatch.setattr(z, "DOMYSLNY_TRYB", "projekt")    # testy trybu projekt i wyboru źródła; auto osobno
    monkeypatch.setattr(z, "_START", None)
    z._zamroz()
    return s


def hak(narzedzie, **args):
    return z.straznik_zgod(tool_name=narzedzie, args=args, task_id="t1", session_id="s1")


def akcja(wynik):
    return None if wynik is None else wynik["action"]


def ustaw_tryb(monkeypatch, tryb):
    monkeypatch.setenv("JARVO_TRYB_ZGOD", tryb)
    z._zamroz()


def msys(p: Path) -> str:
    s = str(p)
    return "/" + s[0].lower() + s[2:].replace("\\", "/")


V4A_W_PROJEKCIE = ("*** Begin Patch\n*** Update File: src/a.py\n@@\n-a\n+b\n*** Add File: src/nowy.py\n+x = 1\n"
                   "*** Delete File: src/stary.py\n*** End Patch\n")


def v4a_z_plikiem_poza(sr):
    return f"*** Begin Patch\n*** Update File: src/a.py\n@@\n-a\n+b\n*** Add File: {sr.poza / 'obcy.py'}\n+x\n*** End Patch"


# ------------------------------------------------------------------------------------------------ rejestracja

def test_rejestracja_haka_i_polecenia_oraz_manifest():
    ctx = AtrapaKontekstu()
    z.register(ctx)
    assert ctx.haki["pre_tool_call"] == [z.straznik_zgod]
    assert "tryb" in ctx.polecenia and "pytaj" in ctx.polecenia["tryb"]["args_hint"]
    manifest = yaml.safe_load((REPO / "zgody" / "plugin" / "plugin.yaml").read_text(encoding="utf-8"))
    assert manifest["name"] == "jarvo-zgody" and manifest["provides_hooks"] == ["pre_tool_call"]
    assert manifest["kind"] == "standalone"


# ------------------------------------------------------------------------------------------------ tryb × narzędzie

ZAPIS = {"pytaj": "approve", "projekt": None, "auto": None, "pelny": None}    # pełny bez YOLO działa jak projekt
ZAWSZE = {"pytaj": "approve", "projekt": "approve", "auto": None, "pelny": "approve"}
NIGDY = {"pytaj": None, "projekt": None, "auto": None, "pelny": None}

PRZYPADKI = [
    ("write w projekcie", "write_file", lambda s: {"path": str(s.proj / "b.txt"), "content": "x"}, ZAPIS),
    ("write względny", "write_file", lambda s: {"path": "src/b.txt", "content": "x"}, ZAPIS),
    ("write poza", "write_file", lambda s: {"path": str(s.poza / "b.txt"), "content": "x"}, ZAWSZE),
    ("write w misjach", "write_file", lambda s: {"path": str(s.misje / "Z-1" / "MISSION.md"), "content": "x"}, ZAPIS),
    ("write w skarbcu", "write_file", lambda s: {"path": str(s.wiedza / "user" / "USER.md"), "content": "x"}, ZAPIS),
    ("terminal mkdir w misjach", "terminal", lambda s: {"command": f"mkdir -p '{s.misje}/Z-1/out'"}, ZAPIS),
    ("patch w projekcie", "patch", lambda s: {"path": str(s.proj / "a.txt"), "old_string": "a", "new_string": "b"}, ZAPIS),
    ("patch poza", "patch", lambda s: {"path": str(s.poza / "a.txt"), "old_string": "a", "new_string": "b"}, ZAWSZE),
    ("patch V4A w projekcie", "patch", lambda s: {"mode": "patch", "patch": V4A_W_PROJEKCIE}, ZAPIS),
    ("patch V4A z plikiem poza", "patch", lambda s: {"mode": "patch", "patch": v4a_z_plikiem_poza(s)}, ZAWSZE),
    ("patch V4A bez mode", "patch", lambda s: {"patch": v4a_z_plikiem_poza(s)}, ZAWSZE),
    ("execute_code", "execute_code", lambda s: {"code": "print(1)\nprint(2)"}, ZAWSZE),
    ("process kill", "process_manage", lambda s: {"action": "kill", "session_id": "proc_1"}, ZAWSZE),
    ("process poll", "process_manage", lambda s: {"action": "poll", "session_id": "proc_1"}, NIGDY),
    ("cron create", "cronjob_manage", lambda s: {"action": "create", "schedule": "every 1h", "prompt": "x"}, ZAWSZE),
    ("cron list", "cronjob_manage", lambda s: {"action": "list"}, NIGDY),
    ("terminal odczyt", "terminal", lambda s: {"command": "ls -la && git status && cat a.txt | grep -n a | wc -l"}, NIGDY),
    ("terminal sed -n", "terminal", lambda s: {"command": "sed -n '1,20p' a.txt; sed 's/a/b/g' a.txt"}, NIGDY),
    ("terminal find", "terminal", lambda s: {"command": "find . -name '*.py' -type f"}, NIGDY),
    ("terminal /dev/null", "terminal", lambda s: {"command": "ls > /dev/null 2>&1; echo ok >&2"}, NIGDY),
    ("terminal wersja", "terminal", lambda s: {"command": "python3 --version"}, NIGDY),
    ("terminal npm", "terminal", lambda s: {"command": "npm install"}, ZAWSZE),
    ("terminal git commit", "terminal", lambda s: {"command": "git commit -m 'zmiana'"}, ZAWSZE),
    ("terminal git -c", "terminal", lambda s: {"command": "git -c core.pager=cat log"}, ZAWSZE),
    ("terminal find -delete", "terminal", lambda s: {"command": "find . -name '*.tmp' -delete"}, ZAWSZE),
    ("terminal mkdir+touch", "terminal", lambda s: {"command": "mkdir -p build && touch build/x.txt"}, ZAPIS),
    ("terminal przekierowanie", "terminal", lambda s: {"command": "echo hej > notatka.txt && echo dwa >> notatka.txt"}, ZAPIS),
    ("terminal przekierowanie poza", "terminal", lambda s: {"command": f"echo hej > '{s.poza / 'x.txt'}'"}, ZAWSZE),
    ("terminal cp do projektu", "terminal", lambda s: {"command": f"cp '{s.poza / 'zrodlo.txt'}' src/"}, ZAPIS),
    ("terminal cp poza", "terminal", lambda s: {"command": f"cp a.txt '{s.poza / 'b.txt'}'"}, ZAWSZE),
    ("terminal cp -t poza", "terminal", lambda s: {"command": f"cp -t '{s.poza}' a.txt"}, ZAWSZE),
    ("terminal mv źródło poza", "terminal", lambda s: {"command": f"mv '{s.poza / 'x.txt'}' ."}, ZAWSZE),
    ("terminal rm w projekcie", "terminal", lambda s: {"command": "rm -f src/*.tmp a.txt"}, ZAPIS),
    ("terminal rmdir -p", "terminal", lambda s: {"command": "rmdir -p src/a/b"}, ZAPIS),
    ("terminal sed -i", "terminal", lambda s: {"command": "sed -i 's/a/b/' a.txt"}, ZAPIS),
    ("terminal sed -i poza", "terminal", lambda s: {"command": f"sed -i.bak -e 's/a/b/' '{s.poza / 'x'}'"}, ZAWSZE),
    ("terminal sed w", "terminal", lambda s: {"command": "sed 's/a/b/w wynik.txt' a.txt"}, ZAWSZE),
    ("terminal tee", "terminal", lambda s: {"command": "echo x | tee -a log.txt"}, ZAPIS),
    ("terminal tee poza", "terminal", lambda s: {"command": f"echo x | tee '{s.poza / 'log.txt'}'"}, ZAWSZE),
    ("terminal sort -o poza", "terminal", lambda s: {"command": f"sort a.txt -o '{s.poza / 'b.txt'}'"}, ZAWSZE),
    ("terminal heredoc", "terminal", lambda s: {"command": "cat > raport.md <<'EOF'\n# Raport\nrm -rf /\nEOF"}, ZAPIS),
    ("terminal klamry", "terminal", lambda s: {"command": "mkdir -p src/{a,b}/c src/{1..3}"}, ZAPIS),
    ("terminal klamry poza", "terminal", lambda s: {"command": f"touch {{x.txt,'{s.poza}'/y.txt}}"}, ZAWSZE),
    ("terminal klamry jako opcja", "terminal", lambda s: {"command": f"rm {{-f,'{s.poza}'/w.txt}}"}, ZAWSZE),
    ("terminal podstawienie", "terminal", lambda s: {"command": "echo \"$(whoami)\" > kto.txt"}, ZAWSZE),
    ("terminal zmienna", "terminal", lambda s: {"command": "OUT=build/out; mkdir -p \"$OUT\" && touch $OUT/x"}, ZAPIS),
    ("terminal nieznana zmienna", "terminal", lambda s: {"command": "touch $NIEZNANA_ZM/x"}, ZAWSZE),
    ("terminal cudzysłów", "terminal", lambda s: {"command": "echo 'bez końca"}, ZAWSZE),
    ("inne narzędzie", "read_file", lambda s: {"path": str(s.poza / "x")}, NIGDY),
    ("web", "web_search", lambda s: {"query": "rm -rf"}, NIGDY),
]


@pytest.mark.parametrize("tryb", ["pytaj", "projekt", "auto", "pelny"])
@pytest.mark.parametrize("opis,narzedzie,argumenty,oczekiwane", PRZYPADKI, ids=[p[0] for p in PRZYPADKI])
def test_tryb_razy_narzedzie(sr, monkeypatch, tryb, opis, narzedzie, argumenty, oczekiwane):
    ustaw_tryb(monkeypatch, tryb)
    wynik = hak(narzedzie, **argumenty(sr))
    assert akcja(wynik) == oczekiwane[tryb], wynik
    if wynik and wynik["action"] == "approve":
        assert wynik["message"].startswith("jarvo-zgody (tryb ") and wynik["rule_key"].startswith(f"jarvo-zgody:{narzedzie}:")


def test_tryb_domyslny_to_auto_bez_prosb(sr, monkeypatch):
    """Decyzja właściciela 14.11: „czemu aż tyle rzeczy muszę approvować, ma być auto all”. Dziesięć próśb o terminal
    w 9 min (kopiowanie zrzutów, ffmpeg) przy jednym zadaniu; „zawsze” zapamiętuje tylko to jedno polecenie."""
    monkeypatch.setattr(z, "DOMYSLNY_TRYB", DOMYSLNY_W_KODZIE)
    assert z.tryb_zgod() == ("auto", "domyślny")
    assert hak("write_file", path=str(sr.poza / "x.txt"), content="x") is None
    assert hak("terminal", command=f"cp a.txt '{sr.poza / 'b.txt'}' && ffmpeg -y -i a.png out.mp4") is None
    assert hak("execute_code", code="print(1)") is None
    assert hak("cronjob_manage", action="create", schedule="every 1h", prompt="x") is None


def test_tryb_auto_zostawia_strazniki(sr, monkeypatch):
    ustaw_tryb(monkeypatch, "auto")
    assert akcja(hak("write_file", path=str(sr.home / "config.yaml"), content="x")) == "block"   # config Hermesa
    assert akcja(hak("write_file", path=str(sr.proj / "SOUL.md"), content="x")) == "approve"     # plik instrukcji
    assert akcja(hak("terminal", command=f"echo x >> '{sr.proj / '.git' / 'config'}'")) == "approve"
    assert akcja(hak("terminal", command=f"rm -rf '{sr.dom}'")) == "block"                        # strażnik kasowania
    # telefon w rozmowie: zwykłe potwierdzenie przechodzi, płatność i usunięcie konta dalej pyta
    assert hak("mcp__phone__act", phone="first", cmd="tap", args={"text": "Continue"}, confirm=True) is None
    assert akcja(hak("mcp__phone__act", cmd="tap", args={"text": "Kup teraz"}, confirm=True)) == "approve"
    assert akcja(hak("mcp__phone__batch", steps=[{"cmd": "tap", "text": "Usuń konto", "confirm": True}])) == "approve"


def test_tryb_auto_brudnopis_i_home_profilu_bez_prosb(sr, monkeypatch):
    """14.11 12:52 i 12:56: właściciel klikał zgody na zapis cache/scratch/gpu_audyt.py w profilu Jarva („no limits,
    tylko security, nie normalna praca”). Katalogi robocze Hermesa przechodzą; wtyczki, skille i sekrety dalej pytają."""
    ustaw_tryb(monkeypatch, "auto")
    for rel in ("cache/scratch/gpu_audyt.py", "home/notatki.txt", "workspace/a.md", "plans/plan.md"):
        (sr.home / rel).parent.mkdir(parents=True, exist_ok=True)
        assert hak("write_file", path=str(sr.home / rel), content="x") is None, rel
    (sr.dane / "profiles" / "jarvo-web" / "cache").mkdir(parents=True)
    assert hak("write_file", path=str(sr.dane / "profiles" / "jarvo-web" / "cache" / "x.py"), content="x") is None
    assert hak("terminal", command=f"python3 a.py > '{sr.home / 'cache' / 'scratch' / 'wynik.json'}'") is None
    for rel in ("plugins/jarvo-zgody/__init__.py", "skills/x/SKILL.md", ".env"):
        (sr.home / rel).parent.mkdir(parents=True, exist_ok=True)
        assert akcja(hak("write_file", path=str(sr.home / rel), content="x")) == "approve", rel


def test_komunikat_prosby_z_nazwa_pliku_i_polecenia(sr):
    w = hak("write_file", path=str(sr.poza / "raport.txt"), content="x")
    assert "raport.txt" in w["message"] and "poza folderem projektu" in w["message"]
    w = hak("terminal", command="npm run build")
    assert "npm run build" in w["message"] and "spoza listy tylko do odczytu: npm" in w["message"]


# ------------------------------------------------------------------------------------------------ ścieżki: .., dowiązania, Windows

def test_kropki_wyprowadzaja_poza_projekt(sr):
    assert akcja(hak("write_file", path="src/../../poza/x.txt", content="x")) == "approve"
    assert akcja(hak("terminal", command="touch ../poza/x.txt")) == "approve"
    assert akcja(hak("terminal", command="cd ../poza && touch x.txt")) == "approve"
    assert hak("terminal", command="cd src && touch x.txt") is None
    assert hak("terminal", command="cd src | true; touch x.txt") is None            # cd w potoku nie zmienia katalogu
    assert akcja(hak("terminal", command="cd - && touch x.txt")) == "approve"     # nie wiadomo, dokąd


def test_rmdir_p_obejmuje_katalogi_nadrzedne(sr):
    assert hak("terminal", command="rmdir -p src/a/b") is None
    assert akcja(hak("terminal", command=f"rmdir -p '{sr.proj / 'src' / 'a'}'")) == "approve"   # aż do korzenia dysku
    assert akcja(hak("terminal", command="rmdir --parents ../poza/a")) == "approve"


def test_workdir_terminala(sr):
    assert akcja(hak("terminal", command="touch x.txt", workdir=str(sr.poza))) == "approve"
    assert hak("terminal", command="touch x.txt", workdir=str(sr.proj / "src")) is None


@pytest.mark.wymaga_symlinku
def test_dowiazanie_z_projektu_na_zewnatrz(sr):
    os.symlink(sr.poza, sr.proj / "link", target_is_directory=True)
    assert akcja(hak("write_file", path=str(sr.proj / "link" / "a.txt"), content="x")) == "approve"
    assert akcja(hak("terminal", command="touch link/b.txt")) == "approve"
    os.symlink(sr.proj / "src", sr.poza / "do-projektu", target_is_directory=True)
    assert hak("write_file", path=str(sr.poza / "do-projektu" / "c.txt"), content="x") is None
    (sr.poza / "x.txt").write_text("x", encoding="utf-8")
    assert akcja(hak("terminal", command="rm -f */x.txt")) == "approve"      # glob trafia przez dowiązanie poza projekt


@pytest.mark.windows_only
def test_junction_na_windows(sr):
    import _winapi
    _winapi.CreateJunction(str(sr.poza), str(sr.proj / "skrot"))
    assert akcja(hak("write_file", path=str(sr.proj / "skrot" / "a.txt"), content="x")) == "approve"
    assert akcja(hak("terminal", command="echo x > skrot/b.txt")) == "approve"
    (sr.poza / "x.txt").write_text("x", encoding="utf-8")
    assert akcja(hak("terminal", command="rm -f */x.txt")) == "approve"      # glob trafia przez junction poza projekt
    assert hak("terminal", command="rm -f src/*.txt") is None


@pytest.mark.windows_only
def test_sciezki_git_bash_i_windows(sr):
    w_projekcie = msys(sr.proj) + "/c.txt"
    assert hak("terminal", command=f"touch '{w_projekcie}'") is None
    assert hak("terminal", command=f"echo x > '/cygdrive{msys(sr.proj)}/d.txt'") is None
    assert hak("write_file", path=w_projekcie, content="x") is None
    assert hak("write_file", path=str(sr.proj).replace("\\", "/") + "/e.txt", content="x") is None
    assert akcja(hak("terminal", command=f"touch '{msys(sr.poza)}/x.txt'")) == "approve"
    assert akcja(hak("terminal", command="touch /tmp/x.txt")) == "approve"         # montowanie Git Bash, nie C:\tmp
    assert akcja(hak("terminal", command="cd /c && touch x.txt")) == "approve"


@pytest.mark.skipif(LINUX, reason="na Linuksie system plików rozróżnia wielkość liter")
def test_bez_wielkosci_liter_na_windows_i_macos(sr):
    inny = sr.tmp / "PROJEKT" / "SRC" / "x.txt"
    assert hak("write_file", path=str(inny), content="x") is None
    assert hak("terminal", command=f"touch '{inny}'") is None


@pytest.mark.linux_only
def test_wielkosc_liter_na_linuksie(sr):
    assert akcja(hak("write_file", path=str(sr.tmp / "PROJEKT" / "x.txt"), content="x")) == "approve"


@pytest.mark.windows_only
def test_ads_i_kropka_na_koncu_nie_omijaja_ochrony(sr):
    assert akcja(hak("write_file", path=str(sr.proj / ".git." / "config"), content="x")) == "approve"
    assert akcja(hak("write_file", path=str(sr.proj / ".GIT" / "hooks" / "pre-commit"), content="x")) == "approve"
    assert akcja(hak("write_file", path=str(sr.proj) + "\\.git::$INDEX_ALLOCATION\\hooks\\x", content="x")) == "approve"


@pytest.mark.windows_only
def test_unc_bez_dotykania_sieci(sr, monkeypatch):
    prawdziwy = os.path.realpath

    def pilnuj(p, *a, **k):
        assert not str(p).startswith(("\\\\", "//")), "realpath na ścieżce UNC wysłałby skrót NTLM"
        return prawdziwy(p, *a, **k)

    monkeypatch.setattr(os.path, "realpath", pilnuj)
    assert akcja(hak("write_file", path="\\\\serwer.example\\udzial\\x.txt", content="x")) == "approve"
    assert akcja(hak("terminal", command="cp a.txt //serwer.example/udzial/")) == "approve"


def test_przestrzen_nt_zostawiamy_hermesowi(sr):
    # write_file \\?\…: Hermes odrzuca sam (agent/file_safety.py), więc nie pytamy na próżno
    assert hak("write_file", path="\\\\?\\C:\\x.txt", content="x") is None


def test_katalog_domowy_i_korzen_nie_sa_projektem(sr, monkeypatch):
    dom = os.path.expanduser("~")
    monkeypatch.setenv("TERMINAL_CWD", dom)
    w = hak("write_file", path=os.path.join(dom, "plik-testowy-zgod.txt"), content="x")
    assert akcja(w) == "approve" and "brak folderu projektu" in w["message"]
    monkeypatch.setenv("TERMINAL_CWD", os.path.abspath(os.sep))
    assert akcja(hak("write_file", path=str(sr.proj / "x.txt"), content="x")) == "approve"
    assert "brak" in z.polecenie_tryb("")


def test_katalog_karty_w_rozmowie_z_czlowiekiem(sr, monkeypatch):
    karta = sr.ws_root / "jarvo" / "t_9"
    karta.mkdir(parents=True)
    monkeypatch.setenv("HERMES_KANBAN_WORKSPACE", str(karta))          # bez HERMES_KANBAN_TASK: to nie pracownik
    assert z.bez_czlowieka() is None
    assert hak("write_file", path=str(karta / "a.md"), content="x") is None
    assert hak("write_file", path=str(sr.proj / "a.md"), content="x") is None     # folder czatu dalej działa


def test_folder_projektu_ze_zmiennej_launchera(sr, monkeypatch):
    monkeypatch.setenv("JARVO_FOLDER_PROJEKTU", str(sr.poza))
    z._zamroz()
    assert hak("write_file", path=str(sr.poza / "x.txt"), content="x") is None
    assert akcja(hak("write_file", path=str(sr.proj / "x.txt"), content="x")) == "approve"


# ------------------------------------------------------------------------------------------------ zawsze: config.yaml, instrukcje, chronione

@pytest.mark.parametrize("tryb", ["pytaj", "projekt", "pelny"])
@pytest.mark.parametrize("yolo", [False, True])
def test_config_yaml_zawsze_zablokowany(sr, monkeypatch, tryb, yolo):
    ustaw_tryb(monkeypatch, tryb)
    monkeypatch.setattr(z, "_yolo", lambda: yolo)
    for args in ({"path": str(sr.home / "config.yaml"), "content": "approvals: {mode: off}"},
                 {"path": str(sr.dane / "config.yaml"), "content": "x"},
                 {"path": str(sr.dane / "profiles" / "jarvo-web" / "CONFIG.yaml"), "content": "x"}):
        w = hak("write_file", **args)
        assert akcja(w) == "block" and "konfiguracja Hermesa" in w["message"], args
    latka = f"*** Begin Patch\n*** Update File: {sr.home / 'config.yaml'}\n@@\n-a\n+b\n*** End Patch"
    assert akcja(hak("patch", mode="patch", patch=latka)) == "block"
    assert akcja(hak("terminal", command=f"sed -i 's/manual/off/' '{sr.home / 'config.yaml'}'")) == "block"
    assert akcja(hak("terminal", command=f"echo 'x: 1' >> '{sr.dane / 'config.yaml'}'")) == "block"
    assert akcja(hak("terminal", command=f"cp nowy.yaml '{sr.home}/config.yaml'")) == "block"


def test_config_yaml_projektu_to_zwykly_plik(sr):
    assert hak("write_file", path=str(sr.proj / "config.yaml"), content="x") is None


def test_config_yaml_wygrywa_z_niebezpiecznym_poleceniem(sr, monkeypatch):
    monkeypatch.setattr(z, "_hermes_niebezpieczne", lambda polecenie: True)
    assert akcja(hak("terminal", command=f"sed -i 's/a/b/' '{sr.home / 'config.yaml'}'")) == "block"


@pytest.mark.parametrize("sciezka", [".git/hooks/pre-commit", ".vscode/settings.json", ".idea/workspace.xml",
                                     ".claude/settings.json", ".hermes/config.yaml", ".gitconfig", ".bashrc", ".zshrc",
                                     ".npmrc", ".mcp.json", "src/AGENTS.md", "CLAUDE.md", "soul.md"])
def test_chronione_w_projekcie_zawsze_pytaja(sr, sciezka):
    w = hak("write_file", path=str(sr.proj / sciezka), content="x")
    assert akcja(w) == "approve" and "chronione" in w["message"], sciezka
    assert akcja(hak("terminal", command=f"echo x > '{sciezka}'")) == "approve"


def test_pliki_instrukcji_przez_write_file_pyta_hermes(sr, monkeypatch):
    monkeypatch.setattr(z, "_hermes_pyta_o_instrukcje", lambda sciezka, task_id: True)
    assert hak("write_file", path=str(sr.proj / "AGENTS.md"), content="x") is None      # Hermes pyta raz, my nie
    assert akcja(hak("terminal", command="cp nowe.md AGENTS.md")) == "approve"          # terminalu Hermes nie pilnuje


def test_dane_jarva_zawsze_pytaja_poza_katalogami_roboczymi(sr, monkeypatch):
    monkeypatch.setenv("TERMINAL_CWD", str(sr.dane))        # czat odpalony w katalogu danych
    for p in (sr.home / "SOUL.md", sr.home / ".env", sr.dane / "plugins" / "x" / "__init__.py",
              sr.home / "plugin-data" / "jarvo-zgody" / "stan.json"):
        assert akcja(hak("write_file", path=str(p), content="x")) == "approve", p
    assert hak("write_file", path=str(sr.ws_root / "jarvo" / "raport.md"), content="x") is None
    assert hak("write_file", path=str(sr.wiedza / "notatka.md"), content="x") is None


def test_brama_z_folderem_w_katalogu_roboczym(sr, monkeypatch):
    monkeypatch.setenv("TERMINAL_CWD", str(sr.ws_root / "jarvo"))      # Telegram i HQ: terminal.cwd profilu
    assert hak("write_file", path=str(sr.ws_root / "jarvo" / "strona" / "index.html"), content="x") is None
    assert akcja(hak("write_file", path=str(sr.home / "memories" / "x.md"), content="x")) == "approve"


def test_kod_wtyczki_i_jarva_chroniony(sr, monkeypatch):
    monkeypatch.setenv("TERMINAL_CWD", str(REPO))
    assert akcja(hak("write_file", path=str(REPO / "zgody" / "plugin" / "__init__.py"), content="x")) == "approve"
    assert hak("write_file", path=str(REPO / "docs" / "nowy.md"), content="x") is None
    monkeypatch.setenv("JARVO_ROOT", str(sr.tmp))
    assert akcja(hak("write_file", path=str(sr.tmp / "program" / "hermes" / "x.py"), content="x")) == "approve"


# ------------------------------------------------------------------------------------------------ niebezpieczne i stałe zgody Hermesa

def test_niebezpieczne_polecenia_zostawiamy_bramce_hermesa(sr, monkeypatch):
    ustaw_tryb(monkeypatch, "pytaj")
    monkeypatch.setattr(z, "_hermes_niebezpieczne", lambda polecenie: True)
    assert hak("terminal", command="rm -rf build") is None
    assert hak("terminal", command=f"rm -rf '{sr.poza}'") is None              # Hermes pokaże całe polecenie


def test_stala_zgoda_wlasciciela_w_command_allowlist(sr, monkeypatch):
    monkeypatch.setattr(z, "_hermes_dozwolone_na_stale", lambda polecenie: True)
    assert hak("terminal", command="npm install") is None
    assert akcja(hak("terminal", command="echo x >> .bashrc")) == "approve"    # chronione: pytamy mimo to


def test_execute_code_w_bramie_pyta_hermes(sr, monkeypatch):
    monkeypatch.setattr(z, "_hermes_pyta_o_kod", lambda: True)
    assert hak("execute_code", code="print(1)") is None


def test_odmowa_zapisu_przez_hermesa_bez_pytania(sr, monkeypatch):
    monkeypatch.setattr(z, "_hermes_odmowi_zapisu", lambda sciezka: True)
    assert hak("write_file", path=str(sr.poza / "x.txt"), content="x") is None


# ------------------------------------------------------------------------------------------------ YOLO (tryb pełny)

def test_yolo_chronione_blokuje_reszte_zostawia_hermesowi(sr, monkeypatch):
    ustaw_tryb(monkeypatch, "pelny")
    monkeypatch.setattr(z, "_yolo", lambda: True)
    assert hak("write_file", path=str(sr.proj / "x.txt"), content="x") is None
    w = hak("write_file", path=str(sr.poza / "x.txt"), content="x")
    assert akcja(w) == "approve" and "tryb pełny" in w["message"]                # YOLO zatwierdzi sam
    w = hak("write_file", path=str(sr.proj / ".git" / "hooks" / "pre-commit"), content="x")
    assert akcja(w) == "block" and "/yolo" in w["message"]
    w = hak("terminal", command="cp nowe.md AGENTS.md")
    assert akcja(w) == "block" and "write_file albo patch" in w["message"]
    assert akcja(hak("write_file", path=str(sr.home / "skills" / "x.md"), content="x")) == "block"
    monkeypatch.setattr(z, "_hermes_niebezpieczne", lambda polecenie: True)
    assert akcja(hak("terminal", command="rm -rf .git")) == "block"


def test_jarvo_pod_yolo_bez_ekranu_i_telefonu(sr, monkeypatch):
    """Profil jarvo (Komputer Jarva i telefon) pod YOLO: narzędzia ekranu i telefonu block, reszta jak w trybie pełnym."""
    jarvo = sr.dane / "profiles" / "jarvo"
    jarvo.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(jarvo))
    monkeypatch.setattr(z, "_yolo", lambda: True)
    for narzedzie, args in (("computer_use", {}), ("komputer", {"akcja": "klik"}),
                            ("mcp__phone__screen", {"phone": "first"}), ("mcp__phone__act", {"cmd": "tap"})):
        w = hak(narzedzie, **args)
        assert akcja(w) == "block" and "ekranu ani telefonu" in w["message"], narzedzie
    assert hak("write_file", path=str(sr.proj / "x"), content="x") is None
    assert hak("read_file", path="x") is None
    assert hak("kanban_block", reason="YOLO") is None
    assert "ekran i telefon" in z.polecenie_tryb("pelny")
    ustaw_tryb(monkeypatch, "pelny")
    assert z.tryb_zgod()[0] == "pelny"
    monkeypatch.setattr(z, "_yolo", lambda: False)
    assert hak("komputer", akcja="patrz") is None
    assert hak("mcp__phone__screen", phone="first") is None


# ------------------------------------------------------------------------------------------------ bez człowieka

KONTEKSTY = ["kanban", "cron", "q", "podagent", "webhook", "brak"]


def bez_czlowieka(sr, monkeypatch, kontekst):
    ws = sr.ws_root / "jarvo" / "t_1"
    ws.mkdir(parents=True, exist_ok=True)
    if kontekst == "kanban":
        monkeypatch.setenv("HERMES_KANBAN_TASK", "t_1")
        monkeypatch.setenv("HERMES_KANBAN_WORKSPACE", str(ws))
        monkeypatch.setenv("TERMINAL_CWD", str(ws))
    elif kontekst == "cron":
        monkeypatch.setenv("HERMES_CRON_SESSION", "1")
    elif kontekst == "q":
        monkeypatch.setenv("HERMES_SINGLE_QUERY_SESSION", "1")
    elif kontekst == "podagent":
        monkeypatch.setenv("HERMES_DELEGATED_CHILD_CONTEXT", "1")
    elif kontekst == "webhook":
        monkeypatch.setenv("HERMES_SESSION_PLATFORM", "webhook")
    else:
        monkeypatch.setattr(z, "_ktos_odpowie", lambda: False)
    assert z.bez_czlowieka() == kontekst
    return ws


@pytest.mark.parametrize("kontekst", KONTEKSTY)
def test_bez_czlowieka_zapis_poza_to_block(sr, monkeypatch, kontekst):
    bez_czlowieka(sr, monkeypatch, kontekst)
    w = hak("write_file", path=str(sr.poza / "x.txt"), content="x")
    assert akcja(w) == "block" and "bez człowieka" in w["message"]
    assert ('kanban_block(kind="needs_input"' in w["message"]) == (kontekst == "kanban")
    assert akcja(hak("terminal", command=f"touch '{sr.poza / 'y.txt'}'")) == "block"
    assert akcja(hak("terminal", command=f"mv '{sr.poza / 'zdjecie.png'}' out/")) == "block"
    assert akcja(hak("patch", mode="patch", patch=v4a_z_plikiem_poza(sr))) == "block"
    assert akcja(hak("execute_code", code="print(1)")) == "block"
    assert akcja(hak("cronjob_manage", action="create", schedule="every 1h", prompt="x")) == "block"
    assert akcja(hak("write_file", path=str(sr.home / "config.yaml"), content="x")) == "block"


@pytest.mark.parametrize("kontekst", KONTEKSTY)
def test_bez_czlowieka_skarbiec_misje_i_karta_przechodza(sr, monkeypatch, kontekst):
    ws = bez_czlowieka(sr, monkeypatch, kontekst)
    assert hak("write_file", path=str(sr.wiedza / "skrzynka" / "x.md"), content="x") is None
    assert hak("write_file", path=str(sr.misje / "INDEX.md"), content="x") is None
    assert hak("terminal", command=f"mkdir -p '{sr.misje}/m1' && echo x > '{sr.misje}/m1/raport.md'") is None
    assert hak("terminal", command="npm test") is None                        # reszta: polityka Hermesa (-q, cron)
    assert hak("terminal", command="touch $NIEZNANA_ZM/x") is None            # nie wiadomo gdzie = jak python3
    assert hak("process_manage", action="kill", session_id="proc_1") is None
    if kontekst == "kanban":
        assert hak("write_file", path=str(ws / "out" / "raport.md"), content="x") is None
        assert hak("terminal", command="mkdir -p $HERMES_KANBAN_WORKSPACE/out && cat > out/a.md <<'EOF'\nx\nEOF") is None
        assert akcja(hak("write_file", path=str(ws / ".git" / "config"), content="x")) == "block"


@pytest.mark.parametrize("kontekst", ["cron", "q", "podagent"])
def test_bez_czlowieka_folder_projektu_wedlug_trybu(sr, monkeypatch, kontekst):
    bez_czlowieka(sr, monkeypatch, kontekst)
    assert hak("write_file", path=str(sr.proj / "src" / "x.py"), content="x") is None     # projekt: bez pytania
    ustaw_tryb(monkeypatch, "pytaj")
    assert akcja(hak("write_file", path=str(sr.proj / "src" / "x.py"), content="x")) == "block"


@pytest.mark.parametrize("kontekst", KONTEKSTY)
@pytest.mark.parametrize("tryb", ["pytaj", "projekt", "pelny"])
def test_bez_czlowieka_nigdy_approve(sr, monkeypatch, kontekst, tryb):
    bez_czlowieka(sr, monkeypatch, kontekst)
    ustaw_tryb(monkeypatch, tryb)
    for _, narzedzie, argumenty, _ in PRZYPADKI:
        assert akcja(hak(narzedzie, **argumenty(sr))) != "approve", (narzedzie, argumenty(sr))
    monkeypatch.setattr(z, "_yolo", lambda: True)
    assert akcja(hak("write_file", path=str(sr.poza / "x"), content="x")) == "block"


def test_siatka_bezpieczenstwa_approve_bez_czlowieka(sr, monkeypatch):
    bez_czlowieka(sr, monkeypatch, "q")
    monkeypatch.setattr(z, "_decyzja", lambda *a: {"action": "approve", "message": "x", "rule_key": "x"})
    assert akcja(hak("write_file", path="x", content="x")) == "block"


# ------------------------------------------------------------------------------------------------ telefon (PHONEUSE)

def test_telefon_confirm_z_czlowiekiem_to_prosba_o_te_jedna_akcje(sr):
    w = hak("mcp__phone__act", phone="first", cmd="tap", args={"text": "Kup teraz"}, confirm=True)
    assert akcja(w) == "approve" and "Kup teraz" in w["message"] and "confirm" in w["message"]
    drugi = hak("mcp__phone__act", phone="first", cmd="tap", args={"text": "Kup teraz"}, confirm=True)
    assert drugi["rule_key"] != w["rule_key"]                        # „zawsze” nie zapamięta zgody na następne
    assert akcja(hak("mcp__phone__act", cmd="tap", args={"index": 4, "confirm": True})) == "approve"   # przez args
    kroki = [{"cmd": "tap", "text": "Szukaj"}, {"cmd": "tap", "text": "Usuń konto", "confirm": True}]
    w = hak("mcp__phone__batch", steps=kroki)
    assert akcja(w) == "approve" and "Usuń konto" in w["message"]
    assert akcja(hak("mcp__phone__batch", steps='[{"cmd": "enter", "confirm": "true"}]')) == "approve"   # JSON w napisie


def test_telefon_bez_confirm_i_inne_narzedzia_bez_zdania(sr):
    assert hak("mcp__phone__act", cmd="tap", args={"index": 3}, confirm=False) is None
    assert hak("mcp__phone__act", cmd="tap", args={"index": 3, "confirm": "false"}) is None
    assert hak("mcp__phone__batch", steps=[{"cmd": "tap", "text": "Szukaj"}, {"cmd": "type", "text": "rower"}]) is None
    assert hak("mcp__phone__screen", phone="first") is None
    assert hak("mcp__inny__act", cmd="tap", confirm=True) is None    # tylko serwer phone


@pytest.mark.parametrize("kontekst", KONTEKSTY)
def test_telefon_confirm_bez_czlowieka_block(sr, monkeypatch, kontekst):
    bez_czlowieka(sr, monkeypatch, kontekst)
    w = hak("mcp__phone__batch", steps=[{"cmd": "tap", "text": "Wyślij", "confirm": True}])
    assert akcja(w) == "block" and "confirm" in w["message"]
    assert ('kanban_block(kind="needs_input"' in w["message"]) == (kontekst == "kanban")
    assert hak("mcp__phone__act", cmd="tap", args={"index": 3}) is None


def test_telefon_confirm_na_karcie_z_zgoda_wlasciciela(sr, monkeypatch):
    """13.11: rejestracja na telefonie z karty stawała na każdym needs_confirm (regulamin, „Załóż konto”), bo na
    karcie nie ma kogo zapytać. Polecenie właściciela wpisane w kartę linią ZGODA WŁAŚCICIELA jest jego „tak”."""
    import sqlite3
    bez_czlowieka(sr, monkeypatch, "kanban")
    sr.dane.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(sr.dane / "kanban.db") as c:
        c.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, body TEXT)")
        c.execute("INSERT INTO tasks VALUES ('t_1', ?)", ("CEL: konto InstaBox przez Google na telefonie\n"
                  "ZGODA WŁAŚCICIELA: konto — „załóż konto na instabox, sam masz zrobić wszystko” (2026-11-13)",))
    kroki = [{"cmd": "tap", "text": "Akceptuję regulamin", "confirm": True}]
    assert hak("mcp__phone__batch", steps=kroki) is None
    with sqlite3.connect(sr.dane / "kanban.db") as c:
        c.execute("UPDATE tasks SET body = 'CEL: konto InstaBox (bez zgody w karcie)'")
    assert akcja(hak("mcp__phone__batch", steps=kroki)) == "block"


def test_telefon_confirm_pod_yolo_block(sr, monkeypatch):
    monkeypatch.setattr(z, "_yolo", lambda: True)                    # YOLO zatwierdziłoby prośbę bez człowieka
    assert akcja(hak("mcp__phone__act", cmd="enter", confirm=True)) == "block"
    jarvo = sr.dane / "profiles" / "jarvo"
    jarvo.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(jarvo))
    assert akcja(hak("mcp__phone__screen", phone="first")) == "block"   # jarvo pod YOLO: telefon jak computer_use


# ------------------------------------------------------------------------------------------------ werdykty na kartach

@pytest.mark.parametrize("narzedzie", sorted(z.WERDYKTY_KART))
def test_rozmowa_nie_ocenia_karty_w_toku(sr, monkeypatch, narzedzie):
    statusy = {"t_w_toku": "running", "t_ocena": "review", "t_stoi": "blocked", "t_gotowa": "ready"}
    monkeypatch.setattr(z, "_status_karty", lambda tid, tablica: statusy.get(tid))
    for tid in ("t_w_toku", "t_ocena"):
        w = hak(narzedzie, task_id=tid, summary="Zaakceptowane")
        assert akcja(w) == "block" and tid in w["message"] and "[SILENT]" in w["message"]
    assert hak(narzedzie, task_id="t_stoi", summary="Przeniesione do t_9") is None   # przeniesienie zablokowanej karty
    assert hak(narzedzie, task_id="t_gotowa") is None
    assert hak(narzedzie, task_id="t_nieznana") is None                               # brak statusu: bez blokady
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_ocena")                                # pracownik karty (tor review)
    assert hak(narzedzie, task_id="t_ocena", summary="Zaakceptowane") is None



# ------------------------------------------------------------------------------------------------ błąd = blokada

def test_wyjatek_w_haku_blokuje_bez_tresci_argumentow(sr, monkeypatch):
    def zly(*a, **k):
        raise RuntimeError("tajne-haslo-z-argumentow")

    monkeypatch.setattr(z, "_decyzja", zly)
    w = hak("terminal", command="echo tajne-haslo-z-argumentow")
    assert akcja(w) == "block" and "RuntimeError" in w["message"] and "tajne-haslo" not in w["message"]


def test_wyjatek_w_srodku_oceny_tez_blokuje(sr, monkeypatch):
    def zly(*a, **k):
        raise OSError("dysk")

    monkeypatch.setattr(z, "_miejsca", zly)
    assert akcja(hak("write_file", path="a.txt", content="x")) == "block"
    assert akcja(hak("terminal", command="ls")) == "block"
    assert hak("read_file", path="a.txt") is None                 # narzędzi spoza listy wtyczka nie ocenia


def test_zle_argumenty_nie_przepuszczaja(sr):
    assert akcja(z.straznik_zgod(tool_name="write_file", args=None)) is None        # brak ścieżki: Hermes zgłosi błąd
    assert hak("terminal", command=None) is None
    assert akcja(hak("terminal", command="x" * (z._MAX_POLECENIA + 1))) == "approve"


# ------------------------------------------------------------------------------------------------ /tryb i stan

def test_polecenie_tryb_zmienia_stan(sr):
    stan = z.polecenie_tryb("")
    assert "projekt" in stan and "domyślny" in stan and str(sr.proj.name) in stan
    assert akcja(hak("write_file", path=str(sr.proj / "x.txt"), content="x")) is None
    odp = z.polecenie_tryb("pytaj")
    assert odp.startswith("Tryb zgód: pytaj")
    plik = z.sciezka_stanu(sr.home)
    assert plik == sr.home / "plugin-data" / "jarvo-zgody" / "stan.json"
    assert json.loads(plik.read_text(encoding="utf-8"))["tryb"] == "pytaj"
    assert z.tryb_zgod() == ("pytaj", "/tryb")
    assert akcja(hak("write_file", path=str(sr.proj / "x.txt"), content="x")) == "approve"
    z._TRYB_W_PROCESIE.clear()                                   # nowy proces czatu: tryb z pliku profilu
    assert z.tryb_zgod() == ("pytaj", "plik")
    z.polecenie_tryb("Projekt")
    assert z.tryb_zgod()[0] == "projekt"
    assert hak("write_file", path=str(sr.proj / "x.txt"), content="x") is None


def test_polecenie_tryb_pelny_nie_wlacza_yolo(sr):
    odp = z.polecenie_tryb("pełny")
    assert "/yolo" in odp and "sama go nie włącza" in odp
    assert z.tryb_zgod() == ("projekt", "domyślny")
    assert not z.sciezka_stanu(sr.home).exists()
    assert z.polecenie_tryb("cokolwiek").startswith("Użycie: /tryb")


def test_kolejnosc_zrodel_trybu(sr, monkeypatch):
    z.polecenie_tryb("pytaj")
    z._TRYB_W_PROCESIE.clear()
    ustaw_tryb(monkeypatch, "projekt")                            # jarvo chat --tryb projekt wygrywa z plikiem
    assert z.tryb_zgod() == ("projekt", "JARVO_TRYB_ZGOD")
    z.polecenie_tryb("pytaj")                                     # /tryb w sesji wygrywa ze zmienną
    assert z.tryb_zgod() == ("pytaj", "/tryb")
    z.sciezka_stanu(sr.home).write_text(json.dumps({"tryb": "pelny"}), encoding="utf-8")
    z._TRYB_W_PROCESIE.clear()
    monkeypatch.delenv("JARVO_TRYB_ZGOD")
    z._zamroz()
    assert z.tryb_zgod() == ("projekt", "domyślny")              # pełnego z pliku nie bierzemy


def test_zmienna_trybu_czytana_raz(sr, monkeypatch):
    ustaw_tryb(monkeypatch, "pytaj")
    monkeypatch.setenv("JARVO_TRYB_ZGOD", "pelny")                # zmiana w trakcie (np. przez agenta) nic nie daje
    assert z.tryb_zgod() == ("pytaj", "JARVO_TRYB_ZGOD")


def test_tryb_osobno_dla_kazdego_profilu(sr, monkeypatch):
    z.polecenie_tryb("pytaj")
    inny = sr.dane / "profiles" / "jarvo-web"
    inny.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(inny))
    assert z.tryb_zgod() == ("projekt", "domyślny")


# ------------------------------------------------------------------------------------------------ klucz reguły i sekrety

def test_klucz_reguly_waski(sr, monkeypatch):
    k1 = hak("write_file", path=str(sr.poza / "a.txt"), content="x")["rule_key"]
    assert k1 == hak("write_file", path=str(sr.poza / "a.txt"), content="inna treść")["rule_key"]
    assert k1 != hak("write_file", path=str(sr.poza / "b.txt"), content="x")["rule_key"]
    t1 = hak("terminal", command="npm install")["rule_key"]
    assert t1 != hak("terminal", command="npm install lodash")["rule_key"] and "npm" not in t1
    monkeypatch.setenv("TERMINAL_CWD", str(sr.poza))              # ten sam plik, inny folder projektu
    (sr.poza / "sub").mkdir()
    assert hak("terminal", command="npm install")["rule_key"] != t1
    nazwa, narzedzie, odcisk, skrot = t1.split(":")
    assert (nazwa, narzedzie, len(odcisk), len(skrot)) == ("jarvo-zgody", "terminal", 10, 16)


def test_sekrety_w_komunikatach_zamaskowane(sr):
    token = "ghp_" + "A1b2C3d4" * 5
    for polecenie in ("curl -H 'Authorization: Bearer abcdefghijklmnop123456' https://api.example.com",
                      "API_KEY=supersekret123456789 npm run deploy",
                      f"git push https://uzytkownik:{token}@github.com/x/y.git",
                      "mysql --password=haslo-bardzo-tajne -e 'select 1'"):
        w = hak("terminal", command=polecenie)
        assert akcja(w) == "approve"
        for sekret in ("abcdefghijklmnop123456", "supersekret123456789", token, "haslo-bardzo-tajne"):
            assert sekret not in w["message"], (polecenie, w["message"])
        assert "***" in w["message"]


@pytest.mark.parametrize("polecenie", [
    "LESSOPEN='|rm -rf ~ %s' less a.txt",            # program z listy z groźną zmienną przed nim
    "GIT_PAGER='rm -rf ~' git log",
    "HOME=/x git status",                             # ~/.gitconfig spod innego HOME (core.pager)
    "PATH=.:$PATH; ls",                               # ./ls zamiast ls
    "export LD_PRELOAD=./zly.so && cat a.txt",
    "CDPATH=/; cd tmp && rm -f x",                    # cd x z CDPATH trafia gdzie indziej
    "set -a; LESSOPEN='|x %s'; less a.txt",
    "IFS=/; x=a/b; touch $x",
    "tree -o raport.txt", "tree -ao raport.txt", "file -C -m magia", "history -w plik",
    "for f in *.md; do rm \"$f\"; done", "touch $USERPROFILE/x.txt",     # zmienne, których terminal może nie mieć
])
def test_sztuczki_powloki_pytaja_w_trybie_projekt(sr, polecenie):
    assert akcja(hak("terminal", command=polecenie)) == "approve", polecenie


@pytest.mark.parametrize("polecenie", ["set -euo pipefail; ls", "LANG=C ls -la", "[[ -f a.txt ]] && cat a.txt",
                                       "OUT=build; mkdir -p $OUT", "export X=1; echo $X"])
def test_zwykle_konstrukcje_bez_pytania(sr, polecenie):
    assert hak("terminal", command=polecenie) is None, polecenie


def test_rozbior_polecen_powloki():
    polecenia, zlozone = z._rozbierz("A=1 cmd 'x y' \"z $B\" 2>err.log >> out.txt | tee -a log && echo ok # komentarz")
    assert not zlozone and [p.lacznik for p in polecenia] == ["|", "&&", ""]
    pierwsze = polecenia[0]
    assert [s.surowe() for s in pierwsze.slowa] == ["A=1", "cmd", "x y", "z $B"]
    assert [(op, s.surowe()) for op, s in pierwsze.przekierowania] == [(">", "err.log"), (">>", "out.txt")]
    assert z._rozbierz("echo $(rm -rf ~)")[1] and z._rozbierz("cat <(ls)")[1] and z._rozbierz("(cd x; rm y)")[1]
    with pytest.raises(z._Skladnia):
        z._rozbierz("echo 'bez końca")
    assert z._klamry("a{b,c{d,e}}f") == ["abf", "acdf", "acef"] and z._klamry("x{1..3}") == ["x1", "x2", "x3"]
    assert z._klamry("${HOME}/{a,b}") == ["${HOME}/a", "${HOME}/b"] and z._klamry("{a,") is None
    assert z._sed_bezpieczny("1,20p") and z._sed_bezpieczny("/start/,/koniec/p;s|a|b|g")
    assert not z._sed_bezpieczny("s/a/b/w plik") and not z._sed_bezpieczny("1e rm -rf /")
    assert z.sciezki_latki({"mode": "patch", "patch": "*** Move File: a.py -> b/c.py\n*** Update File: d.py\n"}) == \
        ["d.py", "a.py", "b/c.py"]


# ------------------------------------------------------------------------------------------------ strażnik kasowania

TRYBY_PRACY = ["pytaj", "projekt", "yolo", "kanban", "cron"]


def q(p) -> str:
    return "'" + Path(p).as_posix() + "'"


def tryb_pracy(sr, monkeypatch, tryb):
    """Tryb z człowiekiem, YOLO albo praca bez człowieka; Hermes „zapytałby sam”, a właściciel dał stałą zgodę:
    masowego kasowania nie przepuszcza ani jedno, ani drugie."""
    monkeypatch.setattr(z, "_hermes_niebezpieczne", lambda polecenie: True)
    monkeypatch.setattr(z, "_hermes_dozwolone_na_stale", lambda polecenie: True)
    if tryb in ("pytaj", "projekt"):
        ustaw_tryb(monkeypatch, tryb)
    elif tryb == "yolo":
        ustaw_tryb(monkeypatch, "pelny")
        monkeypatch.setattr(z, "_yolo", lambda: True)
    else:
        bez_czlowieka(sr, monkeypatch, tryb)


def drzewo(sr):
    """Dom właściciela z projektami i kluczami, projekt czatu (repozytorium z wynikami budowania), klon w temp."""
    for p in (sr.dom / "dev" / "projekt-a" / ".git", sr.dom / "dev" / "projekt-a" / "src",
              sr.dom / "dev" / "projekt-a" / "node_modules" / "x", sr.dom / "strony" / "site" / ".git",
              sr.dom / "jarvo-testy", sr.dom / ".config" / "app", sr.dom / ".phoneuse", sr.dom / ".ssh",
              sr.proj / ".git", sr.proj / "node_modules" / "pkg", sr.proj / "dist", sr.proj / ".svelte-kit",
              sr.proj / "src" / "__pycache__", sr.proj / "build", sr.tmp / "temp" / "klon" / ".git",
              sr.wiedza / "skrzynka" / "stare", sr.ws_root / "jarvo" / "t_1" / "out", sr.home / "sessions"):
        p.mkdir(parents=True, exist_ok=True)
    for p, tresc in ((sr.dom / ".ssh" / "config", "Host x\n"), (sr.dom / ".config" / "app" / "x.json", "{}\n"),
                     (sr.dom / ".phoneuse" / "stan", "x\n"), (sr.dom / ".bashrc", "export X=1\n"),
                     (sr.proj / "AGENTS.md", "# Zasady\n"), (sr.proj / "src" / "stary.py", "x = 1\n"),
                     (sr.proj / "src" / "__pycache__" / "a.pyc", "x"), (sr.proj / ".git" / "config", "[core]\n"),
                     (sr.proj / "build" / "a.o", "x"), (sr.home / "sessions" / "s1.json", "{}")):
        p.write_text(tresc, encoding="utf-8")


BLOKOWANE = [
    # rm w każdej kolejności flag, długie flagi, flagi po celach, owijki, sztuczki z cudzysłowem
    ("rm -rf ~/dev", None), ("rm -r -f ~/dev/projekt-a", None), ("rm --recursive --force ~/strony", None),
    ("rm ~/dev/projekt-a -rf", None), ("rm -fR ~", None), ("rm -rf ~/dev/*", None), ("/bin/rm -rf ~/jarvo-testy", None),
    ("sudo -u root rm -rf ~/dev", None), ("\\rm -rf ~/dev", None), ("r''m -rf ~/strony/site", None),
    ("command rm -rf ~/dev", None), ("nice -n 5 timeout 10 rm -rf ~/dev", None), ("rm -rf ~/strony/site/.git", None),
    ("rm -rf ~/dev/projekt-a/../projekt-a", None),
    # klucze, tokeny i konfiguracja: także pojedyncze pliki
    ("rm -rf ~/.ssh", None), ("rm ~/.ssh/config", None), ("rm -f ~/.config/app/x.json", None), ("rm -rf ~/.phoneuse", None),
    ("rm ~/.bashrc", None),
    # dane Jarva, skarbiec, misje i katalogi kart w całości
    ("rm -rf ~/.local", None), ("rm -rf {dane}/profiles", None), ("rm -rf {home}/sessions", None),
    ("rm -rf {wiedza}", None), ("rm -rf {misje}", None), ("rm -rf {ws}", None), ("rm -rf {ws}/*", None),
    # find
    ("find ~/dev -delete", None), ("find ~/dev -exec rm -rf {{}} +", None), ("find ~/.ssh -name 'id_*' -delete", None),
    ("find ~ -name '*.log' -delete", None), ("find ~/dev -name '*' -delete", None),
    ("find ~/strony ! -name x -delete", None), ("find ~/dev -type d -print0 | xargs -0 rm -rf", None),
    # Python, inne języki i powłoki w powłoce
    ("python3 -c 'import shutil; shutil.rmtree(\"{dom_p}/dev\")'", None),
    ("python3 - <<'EOF'\nimport os, shutil\nshutil.rmtree(os.path.expanduser('~/dev'))\nEOF", None),
    ("python3 <<EOF\nfrom pathlib import Path\nimport shutil\nshutil.rmtree(Path.home() / 'strony')\nEOF", None),
    ("python3 -c 'import os; os.removedirs(\"{dom_p}/jarvo-testy\")'", None),
    ("python3 -c 'import shutil,sys; shutil.rmtree(sys.argv[1])' ~/dev", "nie da się ustalić"),
    ("python3 -c 'from shutil import rmtree as r; r(\"/x\")'", "pod inną nazwą"),
    ("python3 -c 'import subprocess; subprocess.run([\"rm\", \"-rf\", \"{dom_p}/dev\"])'", None),
    ("uv run python -c 'import os; os.system(\"rm -rf ~/dev\")'", None),
    ("node -e \"require('fs').rmSync('{dom_p}/dev', {{recursive: true}})\"", None),
    ("bash -c 'rm -rf ~/dev'", None), ("sh -lc \"rm -rf $HOME/strony\"", None), ("eval 'rm -rf ~/dev'", None),
    ("echo $(rm -rf ~/dev)", None), ("(cd ~ && rm -rf dev)", None), ("cd ~/dev && rm -rf ./*", None),
    ("bash <<'EOF'\nrm -rf ~/dev\nEOF", None), ("D=~/dev; rm -rf $D", None),
    # cele, których nie da się ustalić, przy -r albo -f
    ("rm -rf $NIEZNANA_ZM", "nie da się ustalić"), ("rm -rf \"$(cat lista.txt)\"", "nie da się ustalić"),
    ("for d in a b; do rm -rf $d; done", "nie da się ustalić"), ("rm -f $NIEZNANA_ZM/plik", "nie da się ustalić"),
    ("ls | xargs rm", "z wejścia"), ("bash -c \"rm -rf $NIEZNANA_ZM\"", "nieznaną treścią"),
    # rsync --delete, git, truncate, dd, mkfs, przekierowania
    ("rsync -a --delete /tmp/pusty/ ~/dev/", None), ("rsync -a --delete-after {proj_p}/dist/ ~/strony/site/", None),
    ("git -C {proj_p} clean -fdx", None), ("git -C ~/dev/projekt-a reset --hard HEAD~3", None),
    ("cd ~/dev/projekt-a && git reset --hard", None), ("cd {proj_p} && git push --force origin main", None),
    ("git -C {proj_p} push -f", None), ("git -C {proj_p} push --mirror backup", None),
    ("git -C {proj_p} push origin +main", None), ("git -C $NIEZNANA_ZM reset --hard", "repozytorium"),
    ("truncate -s 0 ~/.ssh/config", None), ("dd if=/dev/zero of=~/.ssh/config", None),
    ("dd if=/dev/zero of=/dev/sda bs=1M", "dysk"), ("mkfs.ext4 /dev/sdb1", "dysk"), ("sudo wipefs -a /dev/sdb", "dysk"),
    (": > ~/.ssh/config", None), ("> ~/.bashrc", None), ("cat /dev/null > ~/.ssh/config", None),
    ("echo nowy > ~/.config/app/x.json", None), ("cp /dev/null ~/.bashrc", None), ("echo x | tee ~/.bashrc", None),
    ("truncate -s 0 {proj_p}/AGENTS.md", None), ("echo x > {proj_p}/.git/config", None),
]


def polecenie_z(sr, wzor):
    return wzor.format(dane=q(sr.dane), home=q(sr.home), wiedza=q(sr.wiedza), misje=q(sr.misje), ws=q(sr.ws_root),
                       dom_p=sr.dom.as_posix(), proj_p=sr.proj.as_posix())


@pytest.mark.parametrize("tryb", TRYBY_PRACY)
@pytest.mark.parametrize("wzor,fragment", BLOKOWANE, ids=[b[0][:60] for b in BLOKOWANE])
def test_masowe_kasowanie_zablokowane_w_kazdym_trybie(sr, monkeypatch, tryb, wzor, fragment):
    drzewo(sr)
    tryb_pracy(sr, monkeypatch, tryb)
    polecenie = polecenie_z(sr, wzor)
    w = hak("terminal", command=polecenie)
    assert akcja(w) == "block" and "masowe kasowanie" in w["message"], (polecenie, w)
    assert "nie da się jej zatwierdzić" in w["message"]
    if fragment:
        assert fragment in w["message"], w["message"]
    if tryb == "kanban":
        assert 'kanban_block(kind="needs_input"' in w["message"]
    else:
        assert "poproś właściciela" in w["message"] and "skasuj konkretne pliki" in w["message"]


DOZWOLONE = [
    "cd {proj_p} && rm -rf node_modules dist .svelte-kit src/__pycache__",
    "cd {proj_p} && rm -f src/stary.py && rm src/__pycache__/a.pyc",
    "cd {proj_p} && rm -rf build/*",
    "cd {proj_p} && find . -name __pycache__ -type d -exec rm -rf {{}} +",
    "find {proj_p} -name '*.pyc' -delete",
    "find ~/dev -name node_modules -prune -exec rm -rf {{}} +",
    "rm -rf ~/dev/projekt-a/node_modules ~/dev/projekt-a/src",
    "rm -rf {temp_p}/klon", "cd {temp_p}/klon && git clean -fdx && git reset --hard",
    "rm -rf {ws}/jarvo/t_1/out", "rm -rf {ws}/jarvo/t_1", "git -C {ws}/jarvo/t_1 reset --hard",
    "rm -rf {wiedza}/skrzynka/stare",
    "python3 -c 'import shutil, tempfile; d = tempfile.mkdtemp(); shutil.rmtree(d)'",
    "python3 - <<'EOF'\nimport shutil, tempfile\nwith tempfile.TemporaryDirectory() as d:\n    shutil.rmtree(d)\nEOF",
    "python3 -c 'import shutil; shutil.rmtree(\"{proj_p}/dist\")'",
    "cd {proj_p} && git clean -n && git reset --soft HEAD~1 && git push origin main",
    "truncate -s +1M {proj_p}/build/a.o", "echo x >> ~/.bashrc", "echo x > {proj_p}/src/stary.py",
    "rsync -a --delete {proj_p}/dist/ {temp_p}/site/", "rsync -a --delete dist/ serwer:/var/www/",
    "grep -rn rmtree {proj_p}/src", "cat > {proj_p}/raport.md <<'EOF'\nrm -rf ~/dev\nshutil.rmtree('/')\nEOF",
    "for f in *.tmp; do rm \"$f\"; done", "rm \"$NIEZNANA_ZM\"",
]


@pytest.mark.parametrize("tryb", TRYBY_PRACY)
@pytest.mark.parametrize("wzor", DOZWOLONE, ids=[d[:60] for d in DOZWOLONE])
def test_zwykle_sprzatanie_bez_blokady_kasowania(sr, monkeypatch, tryb, wzor):
    drzewo(sr)
    tryb_pracy(sr, monkeypatch, tryb)
    polecenie = wzor.format(proj_p=sr.proj.as_posix(), temp_p=(sr.tmp / "temp").as_posix(), ws=q(sr.ws_root),
                            wiedza=q(sr.wiedza))
    w = hak("terminal", command=polecenie)
    assert w is None or "masowe kasowanie" not in w["message"], (polecenie, w)


@pytest.mark.wymaga_symlinku
def test_kasowanie_dowiazania_to_nie_kasowanie_celu(sr, monkeypatch):
    drzewo(sr)
    tryb_pracy(sr, monkeypatch, "projekt")
    os.symlink(sr.dom / "dev", sr.proj / "link", target_is_directory=True)
    assert hak("terminal", command=f"cd {q(sr.proj)} && rm -rf link") is None          # znika samo łącze
    assert akcja(hak("terminal", command=f"cd {q(sr.proj)} && rm -rf link/")) == "block"   # treść ~/dev


def test_repozytorium_w_srodku_kasowanego_katalogu(sr, monkeypatch):
    drzewo(sr)
    tryb_pracy(sr, monkeypatch, "projekt")
    (sr.poza / "klienci" / "firma-x" / ".git").mkdir(parents=True)
    w = hak("terminal", command=f"rm -rf {q(sr.poza / 'klienci')}")
    assert akcja(w) == "block" and "firma-x" in w["message"]
    assert hak("terminal", command=f"rm -rf {q(sr.poza / 'klienci' / 'firma-x' / 'node_modules')}") is None


@pytest.mark.parametrize("tryb", TRYBY_PRACY)
def test_execute_code_i_proces_w_tle_z_kasowaniem(sr, monkeypatch, tryb):
    drzewo(sr)
    tryb_pracy(sr, monkeypatch, tryb)
    kod = f"import shutil\nshutil.rmtree('{sr.dom.as_posix()}/dev')\n"
    w = hak("execute_code", code=kod)
    assert akcja(w) == "block" and "masowe kasowanie" in w["message"]
    w = hak("process_manage", action="write", session_id="proc_1", data="rm -rf ~/dev\n")
    assert akcja(w) == "block" and "masowe kasowanie" in w["message"]
    w = hak("execute_code", code="print(1)")
    assert w is None or "masowe kasowanie" not in w["message"]


@pytest.mark.parametrize("tryb", TRYBY_PRACY)
def test_write_file_i_patch_nie_oprozniaja_chronionych_plikow(sr, monkeypatch, tryb):
    drzewo(sr)
    tryb_pracy(sr, monkeypatch, tryb)
    for sciezka in (sr.dom / ".ssh" / "config", sr.dom / ".bashrc", sr.proj / "AGENTS.md", sr.home / "sessions" / "s1.json"):
        w = hak("write_file", path=str(sciezka), content="")
        assert akcja(w) == "block" and "masowe kasowanie" in w["message"] and sciezka.name in w["message"], sciezka
    w = hak("patch", path=str(sr.dom / ".bashrc"), old_string="export X=1\n", new_string="")
    assert akcja(w) == "block" and "patch" in w["message"]
    latka = f"*** Begin Patch\n*** Delete File: {sr.dom.as_posix()}/.ssh/config\n*** End Patch\n"
    assert akcja(hak("patch", mode="patch", patch=latka)) == "block"
    for args in ({"path": str(sr.proj / "src" / "stary.py"), "content": ""},
                 {"path": str(sr.proj / "AGENTS.md"), "content": "# Nowe zasady\n"}):
        w = hak("write_file", **args)
        assert w is None or "masowe kasowanie" not in w["message"], args
    w = hak("patch", path=str(sr.dom / ".bashrc"), old_string="X=1", new_string="X=2")
    assert w is None or "masowe kasowanie" not in w["message"]


def test_blokada_kasowania_w_dzienniku(sr, monkeypatch, caplog):
    drzewo(sr)
    tryb_pracy(sr, monkeypatch, "yolo")
    with caplog.at_level("WARNING", logger=z.__name__):
        assert akcja(hak("terminal", command="rm -rf ~/dev")) == "block"
    assert any("zablokowane kasowanie" in r.getMessage() and "YOLO" in r.getMessage() for r in caplog.records)


def test_rozbior_zachowuje_tresc_heredocow():
    polecenia, _ = z._rozbierz("python3 - <<'EOF'\nimport shutil\nEOF\ncat <<-X\n\tlinia\n\tX\n")
    assert polecenia[0].heredoki == ["import shutil"] and polecenia[1].heredoki == ["linia"]
