"""Rozmowa w panelu HQ (api_server /v1/runs z HERMES_EXEC_ASK) z prawdziwym kodem Hermesa: które wywołania czekają na
człowieka. Uruchamia go test_zgody.py (test_panel_hermesa_nic_nie_czeka) Pythonem Hermesa w jego katalogu:

    python -P tests/zgody_panel_hermesa.py <katalog wtyczki zgód> <werdykt strażnika smart: approve|deny|escalate>

Środowisko jak w panelu: HERMES_HOME = <dom>/.local/share/jarvo/dane/profiles/jarvo-hacker (config.yaml z approvals
i security), HERMES_EXEC_ASK=1, HERMES_SESSION_PLATFORM=api_server, TERMINAL_CWD = katalog roboczy Hackera, TMPDIR.
Bramka zgód dostaje zarejestrowany notify jak w /v1/runs (gateway/platforms/api_server_runs.py:771), a czekanie na
odpowiedź (_await_gateway_decision) od razu kończy się tak jak po approvals.timeout bez odpowiedzi i zostaje zapisane.
Strażnik smart odpowiada werdyktem z argumentu (bez modelu i sieci). Wynik: linia `WYNIK {przypadek: wynik}`, gdzie
wynik to `blok`, `blok (Hermes)`, `przechodzi`, `CZEKA (prośba wtyczki)` albo `CZEKA (Hermes)`.
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

WTYCZKA, SMART = Path(sys.argv[1]), sys.argv[2]
P = Path(os.environ["HERMES_HOME"])
DANE = P.parent.parent
W = DANE / "jarvo" / "workspaces" / "jarvo-hacker"
DOM = Path(os.environ["HOME"])
PROJ = DOM / "dev" / "strona"
KLON = Path(os.environ["TMPDIR"]) / "klon"
for d in (P / "baza", P / "memories", W / "out" / "stare", PROJ / ".git", DANE / "baza", DOM / ".ssh"):
    d.mkdir(parents=True, exist_ok=True)
(P / "baza" / "hackatony.db").write_bytes(b"")
(P / "memories" / "MEMORY.md").write_text("x\n", encoding="utf-8")
(W / "out" / "a.txt").write_text("x\n", encoding="utf-8")
subprocess.run(["git", "init", "-q", str(KLON)], check=True)

import tools.approval as ap                                     # noqa: E402  (po przygotowaniu katalogów)
import tools.approval_gateway_wait as gw                        # noqa: E402
import tools.approval_smart as sm                               # noqa: E402
from tools.approval_context import set_current_session_key     # noqa: E402
from tools.file_tools_write_guards import _check_approval_required_write, _check_protected_instruction_write  # noqa

SESJA = "agent:jarvo-hacker:api_server:panel"
set_current_session_key(SESJA)
ap.register_gateway_notify(SESJA, lambda dane: None)
CZEKANIA = []


def czekaj(session_key, notify_cb, data, surface="gateway"):
    CZEKANIA.append(data.get("description"))
    return {"resolved": False, "choice": None}


ap._await_gateway_decision = gw._await_gateway_decision = czekaj
sm._smart_approve = lambda command, description: SMART

spec = importlib.util.spec_from_file_location("jarvo_zgody_panel", WTYCZKA / "__init__.py")
z = importlib.util.module_from_spec(spec)
sys.modules["jarvo_zgody_panel"] = z
spec.loader.exec_module(z)
z._zamroz()
z._tymczasowe = lambda: [str(KLON.parent)]     # katalog testu leży w /tmp: tymczasowy jest tylko TMPDIR testu


def wywolaj(narzedzie, args):
    n = len(CZEKANIA)
    w = z.straznik_zgod(tool_name=narzedzie, args=args, task_id="t", session_id=SESJA)
    if w and w["action"] == "block":
        return "blok"
    if w and w["action"] == "approve":            # hermes_cli/plugins.py: approve → request_tool_approval
        r = ap.request_tool_approval(narzedzie, w["message"], rule_key=w.get("rule_key", ""))
        if len(CZEKANIA) > n:
            return "CZEKA (prośba wtyczki)"
        if not r["approved"]:
            return "blok"
    if narzedzie == "terminal":
        r = ap.check_all_command_guards(args["command"], "local")
        if len(CZEKANIA) > n:
            return "CZEKA (Hermes)"
        return "przechodzi" if r["approved"] else "blok (Hermes)"
    blad = _check_protected_instruction_write([args["path"]]) or _check_approval_required_write([args["path"]])
    if len(CZEKANIA) > n:
        return "CZEKA (Hermes)"
    return "blok (Hermes)" if blad else "przechodzi"


PRZYPADKI = {
    "incydent 27.11: rm -f pliku bazy w profilu + rmdir":
        ("terminal", f'F={P}/baza/hackatony.db; ls -la "$F"; rm -f "$F"; rmdir {P}/baza'),
    "rm -rf katalogu w danych Jarva (05:15:38)": ("terminal", f"rm -rf {DANE}/baza"),
    "rm -r katalogu w workspace": ("terminal", f"rm -r {W}/out/stare"),
    "rm pliku w workspace": ("terminal", f"rm {W}/out/a.txt"),
    "find -name -delete w workspace": ("terminal", f"find {W}/out -name '*.tmp' -delete"),
    "nadpisanie pliku > w workspace": ("terminal", f"echo nowe > {W}/out/a.txt"),
    "nadpisanie pamięci > w danych Jarva": ("terminal", f"echo x > {P}/memories/MEMORY.md"),
    "dopisanie >> do .git/config projektu": ("terminal", f"echo x >> {PROJ}/.git/config"),
    "git reset --hard w projekcie": ("terminal", f"git -C {PROJ} reset --hard"),
    "git reset --hard w klonie w temp": ("terminal", f"git -C {KLON} reset --hard"),
    "pkill -f chromium": ("terminal", "pkill -f chromium"),
    "pkill -9 -f chromium": ("terminal", "pkill -9 -f chromium"),
    "python3 -c": ("terminal", "python3 -c 'print(1)'"),
    "SQL DROP na bazie profilu": ("terminal", f"sqlite3 {P}/baza/hackatony.db 'DROP TABLE x'"),
    "płatność w heredocu": ("terminal", "python3 - <<'PY'\nimport stripe\nstripe.checkout.Session.create()\nPY"),
    "write_file AGENTS.md w projekcie": ("write_file", str(PROJ / "AGENTS.md")),
    "write_file ~/.ssh/config": ("write_file", str(DOM / ".ssh" / "config")),
    "write_file pamięci w danych Jarva": ("write_file", str(P / "memories" / "MEMORY.md")),
}
wynik = {}
for opis, (narzedzie, tresc) in PRZYPADKI.items():
    args = {"command": tresc} if narzedzie == "terminal" else {"path": tresc, "content": "nowa treść\n"}
    wynik[opis] = wywolaj(narzedzie, args)
print("WYNIK " + json.dumps(wynik, ensure_ascii=False))
