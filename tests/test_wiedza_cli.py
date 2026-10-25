"""`jarvo wiedza`, `jarvo rutyny` i sprawdzenia K08 (jarvo/wiedza_cli.py) na atrapie instalacji natywnej: kompilacja
Pythonem „Hermesa” (atrapa agent.auxiliary_client) bez basha, lint, indeks pod blokadą, stan, doctor (skarbiec poza
chmurą, FTS5, git, długie ścieżki, wiek kompilacji, lint, brama, rutyny), przełącznik rutyn i wpięcie w parser jarvo.
Korzeń instalacji ze spacją i polskimi znakami (docs/NATYWNIE.md T21)."""
import argparse
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from jarvo import instalator, sciezki, srodowisko  # noqa: E402
from jarvo import wiedza_cli as wc  # noqa: E402

sys.path.insert(0, str(REPO / "wiedza"))
import wiedza as w  # noqa: E402

FLEET = {"orchestrator": "jarvo", "agents": [
    {"name": "jarvo", "short": "Jarvo", "title": "Main Judge", "emoji": "🛰️", "kind": "orchestrator", "description": "Main Judge.",
     "room": "bridge", "label": "Mostek", "telegram_topic": "general", "autonomy_max": "A1", "skills": [], "scripts": ["patrol.py"]}]}
ATRAPA_HERMESA = """import json, os
def call_llm(task, messages, max_tokens, temperature):
    assert task == "jarvo_wiedza", task
    assert os.path.basename(os.environ["HERMES_HOME"]) == "jarvo", os.environ["HERMES_HOME"]
    tytul = next(l for l in messages[-1]["content"].splitlines() if l.startswith("- tytuł: "))[9:]
    return {"choices": [{"message": {"content": json.dumps({"wyniki": [{"decyzja": "nowa", "sciezka": "pojecia/" + tytul.lower(),
        "typ": "fakt", "tytul": tytul, "streszczenie": "Streszczenie: " + tytul, "tresc": "Treść notatki o tym. " * 6,
        "tagi": [], "linki": ["pojecia/_hub-pojecia"], "wazne_do": None, "powod": "atrapa"}]}, ensure_ascii=False)}}]}
"""
RUTYNY = ["jarvo-patrol", "jarvo-daily-brief", "jarvo-weekly-review", "jarvo-knowledge-freshness"]


class Nadzorca:
    """Atrapa modułu nadzorcy: kanał działa (status z bramą) albo nie (wyjątek), restarty zapisane."""

    def __init__(self, brama: str | None = "dziala"):
        self.brama, self.restarty = brama, []

    def polacz(self, _u):
        if self.brama is None:
            raise RuntimeError("Nadzorca Jarva nie działa")
        return self

    def status(self):
        return {"nadzorca": {"pid": 1}, "uslugi": {"brama": {"stan": self.brama, "pid": 4242, "gotowa": True,
                                                              "powod": "kod 78" if self.brama == "postoj" else None}}}

    def restart(self, nazwa):
        self.restarty.append(nazwa)
        return {"ok": True}


@pytest.fixture
def inst(tmp_path, monkeypatch):
    """Instalacja natywna w katalogu ze spacją i ogonkami: current.json (kod = repo, Hermes = atrapa), skarbiec po
    zasiewie, profil jarvo, Python „Hermesa” = bieżący interpreter."""
    monkeypatch.setenv("WIEDZA_DZIS", "2026-10-25")
    for z in ("JARVO_KNOWLEDGE_DIR", "JARVO_STATE_DIR", "HERMES_HOME", "JARVO_TELEGRAM_API", "OneDrive", "OneDriveConsumer",
              "OneDriveCommercial"):
        monkeypatch.delenv(z, raising=False)
    root = tmp_path / "Michał Żółć" / "Jarvo"
    root.mkdir(parents=True)                         # Windows: <program> w ścieżce ASCII przez krótką nazwę 8.3 (c1)
    try:
        u = sciezki.uklad({"JARVO_ROOT": str(root)})
    except sciezki.BladUkladu:                       # wolumin bez nazw 8.3: sama spacja w ścieżce
        root = tmp_path / "Jarvo test"
        root.mkdir()
        u = sciezki.uklad({"JARVO_ROOT": str(root)})
    for k in u.katalogi():
        k.mkdir(parents=True, exist_ok=True)
    checkout = tmp_path / "hermes"
    (checkout / "agent").mkdir(parents=True)
    (checkout / "agent" / "__init__.py").write_text("", encoding="utf-8")
    (checkout / "agent" / "auxiliary_client.py").write_text(ATRAPA_HERMESA, encoding="utf-8")
    (u.program / "current.json").write_text(json.dumps({"app": str(REPO), "hermes": str(checkout), "wersja": "test"}),
                                            encoding="utf-8")
    monkeypatch.setattr(srodowisko, "hermes_python", lambda _c: Path(sys.executable))
    fleet = tmp_path / "fleet.json"
    fleet.write_text(json.dumps(FLEET, ensure_ascii=False), encoding="utf-8")
    assert w.main(["--skarbiec", str(wc.skarbiec(u)), "--stan", str(wc.stan_skarbca(u)), "zasiej", "--fleet", str(fleet)]) == 0
    wc.profil(u).mkdir(parents=True)
    nadzorca = Nadzorca(brama=None)
    ot = instalator.Otoczenie(env={"PATH": os.environ.get("PATH", ""), "JARVO_ROOT": str(root)},
                              modul=lambda nazwa: nadzorca if nazwa == "nadzorca" else instalator.modul(nazwa))
    ot.nadzorca = nadzorca
    return u, ot


def _a(**kw):
    return argparse.Namespace(**kw)


def _szkic(u, tytul):
    sk = w.Skarbiec(wc.skarbiec(u), wc.stan_skarbca(u))
    return w.zapisz_szkic(sk, "fakt", tytul, f"Treść szkicu: {tytul}.", "próba", "jarvo")


def _jobs(u, *, wlaczone=False, deliver="local", brak=()):
    jobs = [{"id": i, "name": i, "enabled": wlaczone, "state": "scheduled" if wlaczone else "paused",
             "paused_at": None if wlaczone else "2026-10-25T02:00:00", "deliver": deliver, "schedule": {"expr": "every 30m"},
             "schedule_display": "every 30m"} for i in RUTYNY if i not in brak]
    p = wc.profil(u) / "cron" / "jobs.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"jobs": jobs}), encoding="utf-8")


# ---------------------------------------------------------------- kompilacja i reszta poleceń

def test_polecenie_kompilacji_bez_basha_z_profilem(inst):
    u, ot = inst
    argv, env, cwd = wc.polecenie_kompilacji(u, {**ot.env, "OPENAI_API_KEY": "sk-tajne", "HERMES_YOLO_MODE": "1"}, ["--json"])
    assert argv[:4] == [sys.executable, "-I", "-X", "utf8"] and Path(argv[4]) == REPO / "wiedza" / "kompilacja.py"
    assert argv[argv.index("--skarbiec") + 1] == str(wc.skarbiec(u)) and argv[argv.index("--profil") + 1] == "jarvo"
    assert not [x for x in argv if x.endswith(".sh") or "bash" in x.lower()]
    assert env["HERMES_HOME"] == str(wc.profil(u)) and env["HERMES_SRC"] == str(cwd) and env["PYTHONUTF8"] == "1"
    assert "OPENAI_API_KEY" not in env and "HERMES_YOLO_MODE" not in env      # sekrety powłoki właściciela nie przechodzą
    assert env["JARVO_KNOWLEDGE_DIR"] == str(wc.skarbiec(u))


def test_kompiluj_na_atrapie_hermesa(inst, capsys):
    """`jarvo wiedza kompiluj`: osobny proces Pythonem „Hermesa” (atrapa zadania jarvo_wiedza), notatki z polskimi
    znakami, LOG, lint po przebiegu, kod 0; zajęty skarbiec = kod 1 bez startu procesu."""
    u, ot = inst
    _szkic(u, "Żółty kłos")
    _szkic(u, "Łódź nad jeziorem")

    def uruchom(argv, env, cwd):
        return subprocess.run(argv, env=env, cwd=str(cwd) if cwd else None, timeout=180).returncode
    assert wc.polecenie_wiedza_kompiluj(u, _a(na_sucho=False, limit=0, json=False), [], ot, uruchom=uruchom) == 0
    assert "Skrzynka: 2 szkiców" in capsys.readouterr().out
    k = wc.skarbiec(u)
    assert (k / "pojecia" / "żółty kłos.md").is_file() and (k / "pojecia" / "łódź nad jeziorem.md").is_file()
    assert not list((k / "skrzynka").glob("*.md"))
    assert json.loads((wc.stan_skarbca(u) / "wiedza-lint.json").read_text(encoding="utf-8"))["bledy"] == 0
    assert "## [2026-10-25] kompilacja | szkice: 2 · nowe: 2" in (k / "LOG.md").read_text(encoding="utf-8")
    _szkic(u, "Trzeci")
    blok = w.Blokada(wc.stan_skarbca(u))
    assert blok.wez()
    try:
        wolane = []
        assert wc.polecenie_wiedza_kompiluj(u, _a(na_sucho=False, limit=0, json=False), [], ot,
                                            uruchom=lambda *x: wolane.append(x) or 0) == 1
        assert not wolane and "zajęty" in capsys.readouterr().err
    finally:
        blok.zwolnij()


def test_kompiluj_bez_profilu_tylko_na_sucho(inst, capsys):
    u, ot = inst
    wc.profil(u).rmdir()
    assert wc.polecenie_wiedza_kompiluj(u, _a(na_sucho=False, limit=0, json=False), [], ot, uruchom=lambda *x: 0) == 1
    assert "Profil jarvo nie jest zainstalowany" in capsys.readouterr().err
    argv = []
    assert wc.polecenie_wiedza_kompiluj(u, _a(na_sucho=True, limit=5, json=True), [], ot,
                                        uruchom=lambda a, e, c: argv.extend(a) or 0) == 0
    assert "--na-sucho" in argv and argv[argv.index("--limit") + 1] == "5" and "--json" in argv


def test_lint_indeksuj_status(inst, capsys):
    u, ot = inst
    assert wc.polecenie_wiedza_lint(u, _a(json=False, strict=True), [], ot) == 0
    assert "Lint skarbca:" in capsys.readouterr().out
    sk = w.Skarbiec(wc.skarbiec(u), wc.stan_skarbca(u))
    sk.zapisz_plik("pojecia/zła", "---\ntyp: fakt\n---\n# Zła\n\n[[nie/ma]]\n")
    assert wc.polecenie_wiedza_lint(u, _a(json=True, strict=True), [], ot) == 1
    r = json.loads(capsys.readouterr().out)
    assert any("martwy link" in b for b in r["bledy"])
    assert wc.polecenie_wiedza_indeksuj(u, _a(pelny=True), [], ot) == 0 and "Indeks:" in capsys.readouterr().out
    assert not (wc.stan_skarbca(u) / "wiedza.lock").exists()                 # blokada zwolniona
    assert wc.polecenie_wiedza_status(u, _a(json=True), [], ot) == 0
    st = json.loads(capsys.readouterr().out)
    assert st["lint"]["bledy"] >= 1 and st["blokada"] is None and st["kompilacja"]["ostatnia"] == 0


# ---------------------------------------------------------------- sprawdzenia K08

def test_synchronizowany():
    env = {"OneDrive": r"C:\Users\Michał\OneDrive"}
    assert wc.synchronizowany(Path(r"C:\Users\Michał\OneDrive\Jarvo\dane"), env) == "OneDrive"
    assert wc.synchronizowany(Path(r"C:\Users\Michał\OneDrive - Firma\x"), {}) == "OneDrive"
    assert wc.synchronizowany(Path("/Users/m/Library/Mobile Documents/com~apple~CloudDocs/Jarvo"), {}) == "iCloud"
    assert wc.synchronizowany(Path("/Users/m/Library/CloudStorage/Dropbox/x"), {}) in ("Dropbox", "folder chmury (CloudStorage)")
    assert wc.synchronizowany(Path(r"D:\JarvoTest\dane"), env) is None and wc.synchronizowany(Path("/home/m/.local/share/jarvo"), {}) is None


def test_sprawdzenia_niczego_nie_zapisuja(inst):
    u, ot = inst
    _szkic(u, "Czeka")
    _jobs(u)

    def spis():
        return sorted((str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in u.root.rglob("*") if p.is_file())
    przed = spis()
    wyniki = wc.sprawdzenia(u, ot)
    assert spis() == przed
    nazwy = [x["nazwa"] for x in wyniki]
    for n in ("skarbiec", "FTS5 w Pythonie Hermesa", "git skarbca", "kompilacja skarbca", "lint skarbca", "brama", "rutyny",
              "Telegram"):
        assert n in nazwy, n
    assert ("długie ścieżki" in nazwy) == (os.name == "nt")
    assert all(x["stan"] in ("ok", "uwaga", "blad") and x["opis"] for x in wyniki)


def test_skarbiec_w_onedrive_to_blad(inst):
    u, ot = inst
    r = wc.sprawdz_skarbiec(u, {"OneDrive": str(u.root.parent)})
    assert r["stan"] == "blad" and "OneDrive" in r["opis"] and "JARVO_ROOT" in r["rada"]
    assert wc.sprawdz_skarbiec(u, {})["stan"] == "ok"


def test_fts5_hermesa(inst):
    u, _ot = inst

    class R:
        def __init__(self, out):
            self.stdout = out
    assert wc.sprawdz_fts5_hermesa(u, lambda argv: R("ok\n"))["stan"] == "ok"
    zle = wc.sprawdz_fts5_hermesa(u, lambda argv: R("zle\n"))
    assert zle["stan"] == "blad" and "polskich znaków" in zle["rada"]
    assert wc.sprawdz_fts5_hermesa(u)["stan"] == "ok"                       # prawdziwy SQLite tego Pythona


def test_dlugie_sciezki(inst):
    u, _ot = inst
    assert wc.sprawdz_dlugie_sciezki(u, rejestr=lambda: 1)["stan"] == "ok"
    r = wc.sprawdz_dlugie_sciezki(u, rejestr=lambda: 0)
    assert r["stan"] == ("uwaga" if len(str(u.root)) > wc.SCIEZKA_KORZENIA_MAKS else "ok") and "LongPathsEnabled = 0" in r["opis"]
    if os.name != "nt":
        assert wc.sprawdz_dlugie_sciezki(u) is None


def test_wiek_kompilacji_i_lint(inst):
    u, _ot = inst
    assert wc.sprawdz_kompilacje(u)["stan"] == "ok"                        # skrzynka pusta
    assert wc.sprawdz_lint(u)["opis"] == "jeszcze nie biegł"                # po samym zasiewie
    _szkic(u, "Czeka od dawna")
    stary = time.time() - 3 * 86400
    (wc.stan_skarbca(u) / "wiedza-kompilacja.json").write_text(json.dumps({"ostatnia": stary, "raport": {}}), encoding="utf-8")
    r = wc.sprawdz_kompilacje(u)
    assert r["stan"] == "uwaga" and "1 szkiców czeka" in r["opis"] and "jarvo wiedza kompiluj" in r["rada"]
    blok = w.Blokada(wc.stan_skarbca(u))
    assert blok.wez()
    try:
        assert "trwa teraz" in wc.sprawdz_kompilacje(u)["opis"]
    finally:
        blok.zwolnij()
    (wc.stan_skarbca(u) / "wiedza-kompilacja.json").write_text(json.dumps({"ostatnia": time.time(), "raport": {"bledy": 2}}),
                                                              encoding="utf-8")
    assert "z błędami: 2" in wc.sprawdz_kompilacje(u)["opis"]
    ix = w.Indeks(w.Skarbiec(wc.skarbiec(u), wc.stan_skarbca(u)))
    try:
        w.lint(w.Skarbiec(wc.skarbiec(u), wc.stan_skarbca(u)), ix)
    finally:
        ix.zamknij()
    assert wc.sprawdz_lint(u)["stan"] == "ok"


def test_brama_ze_stanu_nadzorcy(inst):
    u, ot = inst
    assert wc.sprawdz_brame(u, ot)["stan"] == "uwaga"                      # nadzorca nie działa
    ot.nadzorca.brama = "dziala"
    assert wc.sprawdz_brame(u, ot)["stan"] == "ok"
    ot.nadzorca.brama = "postoj"
    assert wc.sprawdz_brame(u, ot)["stan"] == "blad"


def test_rutyny_w_diagnozie(inst):
    u, ot = inst
    assert wc.sprawdz_rutyny(u, ot, linux=False)[0]["opis"].startswith("brak rutyn")
    _jobs(u)
    r = wc.sprawdz_rutyny(u, ot, linux=False)[0]
    assert r["stan"] == "uwaga" and "wstrzymane" in r["opis"] and "jarvo telegram test" in r["rada"]
    _jobs(u, wlaczone=True)
    assert wc.sprawdz_rutyny(u, ot, linux=False)[0]["stan"] == "ok"
    (u.dane / ".env").write_text("TELEGRAM_BOT_TOKEN=123456:" + "a" * 35 + "\n", encoding="utf-8")
    assert "piszą lokalnie" in wc.sprawdz_rutyny(u, ot, linux=False)[0]["opis"]
    _jobs(u, wlaczone=True, deliver="telegram:123456789")
    assert wc.sprawdz_rutyny(u, ot, linux=False)[0]["opis"].endswith("dostarczanie: Telegram")
    _jobs(u, brak=("jarvo-patrol",))
    assert "brak jarvo-patrol" in wc.sprawdz_rutyny(u, ot, linux=False)[0]["opis"]
    _jobs(u)
    (wc.stan_skarbca(u) / "rutyny.json").write_text(json.dumps({"wlaczone": False, "reczne": True}), encoding="utf-8")
    assert wc.sprawdz_rutyny(u, ot, linux=False)[0] == {"nazwa": "rutyny", "stan": "ok",
                                                        "opis": "wyłączone przez Ciebie (jarvo rutyny off)", "rada": ""}
    (u.dane / "config.yaml").write_text("cron:\n  catch_up_missed: false\n", encoding="utf-8")
    assert "rutyny po uśpieniu" in [x["nazwa"] for x in wc.sprawdz_rutyny(u, ot, linux=False)]

    class R:
        stdout = "Linger=no\n"
    z_lingerem = wc.sprawdz_rutyny(u, ot, linux=True, uruchom=lambda argv: R())
    if instalator.systemowy("loginctl"):                                  # Linux z systemd: informacja, bez alarmu
        assert z_lingerem[-1]["stan"] == "ok" and "linger wyłączony" in z_lingerem[-1]["opis"]


# ---------------------------------------------------------------- przełącznik rutyn

def test_rutyny_on_off_przez_crona_hermesa(inst, capsys):
    """`jarvo rutyny on|off`: `hermes -p jarvo cron resume|pause <id>` dla każdej rutyny (równolegle), zapis decyzji
    właściciela w state/rutyny.json; status czyta jobs.json bez Hermesa."""
    u, ot = inst
    _jobs(u)
    wolane = []

    def hermes(argv, env, cwd):
        wolane.append([str(x) for x in argv])
        assert env["HERMES_HOME"] == str(u.dane) and "HERMES_YOLO_MODE" not in env
        return subprocess.CompletedProcess(argv, 0, "ok", "")
    assert wc.polecenie_rutyny(u, _a(akcja="on", json=False), [], ot, uruchom=hermes) == 0
    assert sorted(a[a.index("cron") + 2] for a in wolane) == sorted(RUTYNY)
    assert all(a[a.index("-p") + 1] == "jarvo" and a[a.index("cron") + 1] == "resume" for a in wolane)
    zapis = json.loads((wc.stan_skarbca(u) / "rutyny.json").read_text(encoding="utf-8"))
    assert zapis["wlaczone"] is True and zapis["reczne"] is True and set(zapis["wyniki"].values()) == {"ok"}
    assert "Telegram nie jest ustawiony" in capsys.readouterr().out
    wolane.clear()
    assert wc.polecenie_rutyny(u, _a(akcja="off", json=False), [], ot, uruchom=hermes) == 0
    assert {a[a.index("cron") + 1] for a in wolane} == {"pause"}

    def zly(argv, env, cwd):
        return subprocess.CompletedProcess(argv, 1, "", f"Failed to resume job: token 123456:{'b' * 35}")
    assert wc.polecenie_rutyny(u, _a(akcja="on", json=False), [], ot, uruchom=zly) == 1
    wyjscie = capsys.readouterr().out
    assert "błąd (kod 1)" in wyjscie and "b" * 35 not in wyjscie              # token z komunikatu zamaskowany
    assert wc.polecenie_rutyny(u, _a(akcja="status", json=False), [], ot) == 0
    assert "(jarvo-patrol): wstrzymana" in capsys.readouterr().out
    assert wc.polecenie_rutyny(u, _a(akcja="status", json=True), [], ot) == 0
    st = json.loads(capsys.readouterr().out)
    assert [r["id"] for r in st["lista"]] == RUTYNY and st["zapis"]["reczne"] is True


def test_rutyny_ids_z_jobs_yaml():
    assert wc.rutyny_ids(REPO) == RUTYNY
    assert wc.rutyny_ids(Path("/nie/ma")) == list(wc.RUTYNY)


# ---------------------------------------------------------------- wpięcie w CLI

def test_parser_i_polecenia_wolne_w_cli():
    """dodaj_polecenia: `wiedza`, `rutyny` i `telegram` z funkcjami (u, a, reszta, ot); nazwy nie kolidują z jarvo/cli.py."""
    from jarvo import cli
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="polecenie")
    wc.dodaj_polecenia(sub)
    a = p.parse_args(["wiedza", "kompiluj", "--na-sucho", "--limit", "3"])
    assert a.funkcja is wc.polecenie_wiedza_kompiluj and a.na_sucho and a.limit == 3
    assert p.parse_args(["rutyny"]).akcja == "status" and p.parse_args(["rutyny", "off"]).funkcja is wc.polecenie_rutyny
    a = p.parse_args(["telegram", "ustaw", "--wlasciciel", "123456789", "--token-ze-stdin"])
    assert a.funkcja is wc.polecenie_telegram_ustaw and a.wlasciciel == "123456789" and a.token_ze_stdin
    assert p.parse_args(["telegram", "test", "--bez-rutyn"]).bez_rutyn
    istniejace = next(x.choices for x in cli._parser()._actions if isinstance(x, argparse._SubParsersAction))
    assert not {"wiedza", "rutyny", "telegram"} & set(istniejace) or {"wiedza", "rutyny", "telegram"} <= set(istniejace)


def test_modul_jako_skrypt(inst):
    """`python -I -X utf8 jarvo/wiedza_cli.py …` (bez pakietu w sys.path): doctor w JSON, polskie znaki w UTF-8."""
    u, _ot = inst
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING", "HERMES_HOME")}
    env.update(JARVO_ROOT=str(u.root))
    r = subprocess.run([sys.executable, "-I", "-X", "utf8", str(REPO / "jarvo" / "wiedza_cli.py"), "wiedza", "doctor", "--json"],
                       capture_output=True, env=env, timeout=120)
    assert r.returncode in (0, 1), r.stderr.decode("utf-8", "replace")
    d = json.loads(r.stdout.decode("utf-8"))
    assert d["root"] == str(u.root) and any(x["nazwa"] == "skarbiec" for x in d["wyniki"])
