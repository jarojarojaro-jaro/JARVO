"""Wtyczka jarvo-zgody: tryby zgód jak w Claude Code dla natywnego Jarva (docs/NATYWNIE.md, sekcja (d); decyzja I08).

Bez kontenera terminal agenta działa z prawami właściciela, więc zgody są główną ochroną (NATYWNIE.md, zasada 9:
„kontrola, nie izolacja”). Hak `pre_tool_call` ocenia zapisy plików, terminal, execute_code, procesy w tle i rutyny;
polecenie `/tryb` zmienia tryb w sesji.

Tryby (wybór: `/tryb` w sesji > JARVO_TRYB_ZGOD z `jarvo chat --tryb` > plik stanu profilu > „projekt”):
  pytaj    approve dla write_file i patch (także V4A z nagłówkami *** Update/Add/Delete/Move File), execute_code,
           process_manage i cronjob_manage (działania zmieniające) oraz terminala spoza listy poleceń tylko do odczytu;
  projekt  (domyślny, I08) jak pytaj, ale bez pytania zapisy i proste polecenia plikowe (mkdir, touch, cp, mv, rm,
           rmdir, sed -i, tee, przekierowania > i >>), gdy rzeczywista ścieżka (po realpath) leży w folderze
           projektu (JARVO_FOLDER_PROJEKTU albo TERMINAL_CWD, czyli katalog startu czatu) albo w katalogu roboczym
           karty (HERMES_KANBAN_WORKSPACE); poza nimi approve;
  pelny    tylko na sesję: proces czatu z --yolo albo /yolo, wtedy Hermes sam zatwierdza prośby wtyczki. Wtyczka
           nigdy nie włącza YOLO i nie pozwala na nie profilowi jarvo-operator (pod YOLO blokuje jego narzędzia).
Zawsze, w każdym trybie: zapis config.yaml Hermesa = block; zgoda na AGENTS.md, CLAUDE.md, SOUL.md i chronione
miejsca (.git, .vscode, .idea, .claude, .hermes, .gitconfig, .bashrc, .zshrc, .npmrc, .mcp.json i podobne pliki
startowe powłoki, dane i kod Jarva). Pod YOLO o chronione miejsca nie da się zapytać, więc wtyczka je blokuje.
Bez człowieka (karta kanbana, cron, -q, podagent delegate_task, webhook, sesja bez nikogo, kto odpowie na prośbę):
nigdy approve. Zapisy w katalogu karty, skarbcu (JARVO_KNOWLEDGE_DIR) i misjach (JARVO_MISSIONS_DIR) oraz to, co
tryb przepuszcza bez pytania w folderze projektu (projekt i pełny), idą dalej; reszta zapisów to block z poradą
(na karcie: kanban_block(kind="needs_input")). Polecenia, których celów nie da się ustalić, zostają polityce Hermesa
(approvals.cron_mode, single_query_mode: deny), bo terminal i tak uruchomi dowolny skrypt.
Błąd w haku = block (nie przepuszczamy przy błędzie, odwrotnie niż strażnik jarvo-wiedza).

Jak to działa w Hermesie f97608f (sprawdzone w kodzie, plik:linia):
  - hermes_cli/plugins.py:1854-1906: dyrektywy pre_tool_call; block (z niepustym message) wygrywa z approve, a z wielu
    approve bierze pierwszy; rule_key bez spacji na brzegach. :1934-1963: approve idzie do
    tools.approval.request_tool_approval(tool, message, rule_key=rule_key or tool); błąd bramki = BLOCKED.
  - hermes_cli/plugins_dispatch.py:49, 58-64, 210-243: pre_tool_call jest hakiem polityki: wyjątek albo przekroczony
    plugins.hook_callback_timeout (30 s) dają block z nazwą funkcji i treścią wyjątku. Dlatego łapiemy wyjątki sami
    i zwracamy block bez treści argumentów (mogą zawierać sekret).
  - tools/approval.py:1095-1120: request_tool_approval → pattern_key `plugin_rule:<rule_key>`; bez człowieka
    fail_closed_when_no_human. :951-1021 _run_approval_gate: YOLO albo approvals.mode off = zgoda od razu (973-974),
    potem zgoda z sesji albo stała (975-977), potem praca bez człowieka (979-1015: deny = BLOCKED od razu,
    single_query_mode: approve = zgoda bez pytania), potem pytanie raz/sesja/zawsze/odmowa (1017-1021).
    :380-392 _persist_choice: „zawsze” zapisuje klucz w command_allowlist (save_permanent_allowlist), na stałe i dla
    każdej powierzchni, także bez człowieka: dlatego rule_key jest wąski (narzędzie + odcisk folderu + skrót treści).
  - YOLO: tools/approval.py:45 (_YOLO_MODE_FROZEN z HERMES_YOLO_MODE przy imporcie), :322-325 (_yolo_active: --yolo
    albo /yolo sesji), :484-493 (is_approval_bypass_active: YOLO, /yolo, approvals.mode off). --yolo ustawia
    HERMES_YOLO_MODE przed odkryciem wtyczek (hermes_cli/main.py:3595-3599), /yolo przełącza YOLO sesji
    (hermes_cli/cli_session_mixin.py:878-917; zamrożonego --yolo nie wyłącza), oneshot -z włącza YOLO i tryb -q
    (hermes_cli/oneshot.py:278-282).
  - Bez człowieka: tools/approval.py:934-948 (_presence: cron i -q zerują obecność człowieka), tools/approval_context.py
    :47-50 (HERMES_INTERACTIVE), :126-128 (HERMES_CRON_SESSION), :137-146 (webhook, msgraph_webhook, api_server),
    :148-154 (HERMES_SINGLE_QUERY_SESSION), :157-174 (brama); gateway/session_context.py:173-179 (get_session_env:
    najpierw ContextVar, potem os.environ). Ustawiają je: hermes_cli/cli_single_query.py:458 (-q),
    cron/scheduler.py:2305-2318 (ContextVar HERMES_CRON_SESSION = "1"), hermes_cli/kanban_db_dispatch.py:2820-2838
    (pracownik: HERMES_KANBAN_TASK, HERMES_KANBAN_WORKSPACE, TERMINAL_CWD = katalog karty). Podagent:
    agent/delegation_context.py:43-45, 87-89 (ContextVar albo HERMES_DELEGATED_CHILD_CONTEXT),
    tools/delegate_tool_child_run.py:855-859; w CLI jego prośby o zgodę odrzuca tools/delegate_tool_config.py:42-59.
  - Polecenie /tryb: hermes_cli/plugins.py:659-683 (register_command, handler(raw_args) -> str | None, nazwa zajęta
    przez polecenie wbudowane jest pomijana); wywołanie w CLI cli.py:1274-1285, w bramie gateway/run_inbound.py:1056-1080.
  - Czego nie dublujemy (nie pytać dwa razy): niebezpieczne polecenia terminala pyta sam Hermes
    (tools/approval_detection.py:180 detect_hardline_command, :1516 detect_dangerous_command; tools/approval_floors.py
    :23 approvals.deny, :188 command_allowlist z dokładnym tekstem albo wzorcem); AGENTS.md, CLAUDE.md, SOUL.md,
    .cursorrules i <projekt>/.hermes/* przez write_file/patch pyta zawsze, także pod YOLO, poza HERMES_HOME
    (tools/file_tools_write_guards.py:171-247, 329-339); config.yaml i ścieżki systemowe blokuje
    (tools/file_tools_write_guards.py:145-168); klucze i HERMES_WRITE_SAFE_ROOT odrzuca (agent/file_safety.py:176-297);
    execute_code pyta sam tylko w bramie i przez HERMES_EXEC_ASK (tools/approval.py:1233-1300).
  - Ścieżki jak w narzędziach plików: tools/file_tools_paths.py:121-134 (katalog bazowy: cwd sesji, nadpisanie,
    TERMINAL_CWD), :137-163 (na Windows ntpath.normpath bez realpath, więc dowiązania i junction sprawdzamy sami);
    Git Bash /c/... → C:\\... jak tools/environments/local.py:117-125; nagłówki V4A jak tools/file_tools.py:149-150
    (Hermes czyta je tylko przy mode="patch", my zawsze, ostrożniej); ~ jak hermes_constants.py:1003-1026.
  - Profil i dane: hermes_constants.py:112-119 (get_hermes_home: nadpisanie per tura przy multipleksie profili,
    potem HERMES_HOME); katalog startu czatu: hermes_cli/cli_config_load.py:140-147 (TERMINAL_CWD = os.getcwd()
    lokalnego CLI) i agent/runtime_cwd.py:62-73 (scope_terminal_cwd przy multipleksie).
  - Maskowanie sekretów w komunikatach: agent/redact.py:871 (redact_sensitive_text); prośba w CLI pokazuje opis bez
    maskowania (tools/approval.py:745-758, redact_cli=False), więc maskujemy sami.
Instalacja (build.py, install_fleet.py, `jarvo chat --tryb`) to etap E4: zgody/README.md.
"""
# bez `from __future__ import annotations`: dataclass z adnotacjami-napisami wymaga modułu w sys.modules, a wtyczkę
# może wczytać ktoś inny niż loader Hermesa (który go tam wpisuje, hermes_cli/plugins_loader.py:651)
import glob as _glob
import hashlib
import itertools
import json
import logging
import ntpath
import os
import re
import sys
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)
_HERE = Path(__file__).resolve().parent

NAZWA = "jarvo-zgody"
TRYBY = ("pytaj", "projekt", "pelny")
DOMYSLNY_TRYB = "projekt"                  # decyzja I08
ZMIENNA_TRYBU = "JARVO_TRYB_ZGOD"          # ustawia `jarvo chat --tryb` (etap E4)
ZMIENNA_FOLDERU = "JARVO_FOLDER_PROJEKTU"  # katalog startu czatu, gdy launcher go zna
OPERATOR = "jarvo-operator"                # nigdy tryb pełny (Komputer Jarva bez ograniczeń)

WINDOWS = os.name == "nt"
MACOS = sys.platform == "darwin"

OBSLUGIWANE = frozenset({"write_file", "patch", "terminal", "execute_code", "process_manage", "cronjob_manage"})
PROCESY_ODCZYT = frozenset({"list", "poll", "log", "wait"})      # process_manage: tylko podgląd
RUTYNY_ODCZYT = frozenset({"list"})                              # cronjob_manage: tylko podgląd
# jarvo-operator pod YOLO: tylko odczyt i raport na karcie, reszta block (I08, docs/NATYWNIE.md F09)
OPERATOR_PRZY_YOLO = frozenset({"read_file", "search_files", "todo_list", "clarify", "session_search", "skill_view",
                                "skills_list", "vision_analyze"})

# zawsze pytamy (pod YOLO blokujemy): katalogi z ustawieniami, które wykonują kod albo sterują agentem
CHRONIONE_KATALOGI = frozenset({".git", ".vscode", ".idea", ".claude", ".hermes"})
CHRONIONE_PLIKI = frozenset({".gitconfig", ".bashrc", ".zshrc", ".npmrc", ".mcp.json", ".bash_profile", ".bash_login",
                             ".profile", ".zprofile", ".zshenv", ".zlogin", ".envrc"})
PLIKI_INSTRUKCJI = frozenset({"agents.md", "claude.md", "soul.md", ".cursorrules"})
NAZWA_KONFIGU = "config.yaml"

KONTEKSTY = {"kanban": "karta kanbana", "cron": "rutyna (cron)", "q": "jednorazowe zapytanie (-q)",
             "podagent": "podagent (delegate_task)", "webhook": "webhook", "brak": "sesja bez człowieka"}
OPISY_TRYBOW = {
    "pytaj": "pytam o każdy zapis, polecenie spoza listy tylko do odczytu, execute_code, procesy w tle i rutyny",
    "projekt": "zapisy i proste polecenia plikowe w folderze projektu bez pytania, poza nim pytam",
    "pelny": "Hermes sam zatwierdza prośby (YOLO, tylko ta sesja)",
}

_MAX_POLECENIA = 100_000          # dłuższe polecenie: nie rozbieramy (i tak blokuje je Hermes)
_MAX_WARIANTOW = 64               # rozwinięcie klamer
_MAX_DOPASOWAN = 100              # rozwinięcie globu

_START: Optional[Dict[str, str]] = None              # zmienne z chwili startu (model nie zmieni ich w trakcie)
_TRYB_W_PROCESIE: Dict[str, str] = {}                # /tryb w tym procesie: klucz profilu → tryb
_STAN_CACHE: Dict[str, Tuple[Tuple[int, int], Optional[str]]] = {}
_ZAMEK = threading.Lock()


# ------------------------------------------------------------------------------------------------ zmienne startu

def _zamroz(env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Zmienne trybu czytamy raz, przy rejestracji wtyczki (jak Hermes HERMES_YOLO_MODE, approval.py:43-45)."""
    global _START
    e = os.environ if env is None else env
    _START = {"tryb": e.get(ZMIENNA_TRYBU, ""), "folder": e.get(ZMIENNA_FOLDERU, ""),
              "yolo": e.get("HERMES_YOLO_MODE", "")}
    return _START


def _start() -> Dict[str, str]:
    return _START if _START is not None else _zamroz()


def _prawda(v: Any) -> bool:
    return str(v or "").strip().lower() in {"1", "true", "yes", "on"}      # utils.TRUTHY_STRINGS Hermesa


def _norm_tryb(v: Any) -> Optional[str]:
    s = unicodedata.normalize("NFKD", str(v or "").strip().lower())
    s = "".join(c for c in s if not unicodedata.combining(c)).replace("ł", "l")
    return s if s in TRYBY else None


# ------------------------------------------------------------------------------------------------ łącznik z Hermesem
# Każda funkcja ma zapas bez Hermesa (testy, inne wersje); testy podmieniają je atrapami.

def _hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home
        return Path(get_hermes_home())
    except Exception:
        h = os.environ.get("HERMES_HOME", "").strip()
        return Path(h) if h else Path.home() / ".hermes"


def _env_sesji(nazwa: str) -> str:
    try:
        from gateway.session_context import get_session_env
        return str(get_session_env(nazwa, "") or "")
    except Exception:
        return os.environ.get(nazwa, "")


def _podagent() -> bool:
    try:
        from agent.delegation_context import is_delegated_child_process_context
        if is_delegated_child_process_context():
            return True
    except Exception:
        pass
    return bool(os.environ.get("HERMES_DELEGATED_CHILD_CONTEXT", "").strip())


def _ktos_odpowie() -> bool:
    """Czy bramka zgód ma kogo zapytać (CLI, TUI, ACP, brama, HQ przez HERMES_EXEC_ASK). Nie wiadomo = tak:
    approve trafi wtedy do bramki Hermesa, która bez człowieka i tak odmawia (fail-closed)."""
    try:
        from tools.approval_context import _is_gateway_approval_context, _is_interactive_cli
    except Exception:
        return True
    try:
        return bool(_is_interactive_cli() or _is_gateway_approval_context() or _prawda(os.environ.get("HERMES_EXEC_ASK")))
    except Exception:
        return True


def _yolo() -> bool:
    """Czy Hermes zatwierdza prośby sam: --yolo, /yolo sesji albo approvals.mode: off."""
    try:
        from tools.approval import is_approval_bypass_active
        return bool(is_approval_bypass_active())
    except Exception:
        return _prawda(_start()["yolo"])


def _hermes_niebezpieczne(polecenie: str) -> bool:
    """Czy Hermes sam zapyta o to polecenie albo je zablokuje (twarda blokada, approvals.deny, wzorzec niebezpieczny bez
    zapisanej zgody). Wtedy wtyczka nie pyta drugi raz."""
    try:
        from tools.approval_detection import detect_dangerous_command, detect_hardline_command
    except Exception:
        return False
    try:
        if detect_hardline_command(polecenie)[0]:
            return True
        try:
            from tools.approval_floors import _match_user_deny_rule
            if _match_user_deny_rule(polecenie):
                return True
        except Exception:
            pass
        groznie, klucz, _ = detect_dangerous_command(polecenie)
        if not groznie:
            return False
        try:
            from tools.approval import is_approved
            from tools.approval_context import get_current_session_key
            if is_approved(get_current_session_key(), klucz):
                return False
        except Exception:
            pass
        return not _hermes_dozwolone_na_stale(polecenie)
    except Exception:
        return False


def _hermes_dozwolone_na_stale(polecenie: str) -> bool:
    """command_allowlist właściciela: dokładny tekst polecenia albo wzorzec (tools/approval_floors.py:188)."""
    try:
        from tools.approval_floors import _command_matches_permanent_allowlist
        return bool(_command_matches_permanent_allowlist(polecenie))
    except Exception:
        return False


def _hermes_pyta_o_instrukcje(sciezka: str, task_id: str) -> bool:
    """Czy write_file/patch tej ścieżki zatrzyma bramka plików instrukcji Hermesa (pyta zawsze, także pod YOLO)."""
    try:
        from tools.file_tools_write_guards import _protected_instruction_reason
        return bool(_protected_instruction_reason(sciezka, task_id or "default"))
    except Exception:
        return False


def _hermes_odmowi_zapisu(sciezka: str) -> bool:
    """Czy narzędzia plików Hermesa i tak odmówią zapisu (klucze, dane sesji, HERMES_WRITE_SAFE_ROOT)."""
    try:
        from agent.file_safety import is_write_denied
        return bool(is_write_denied(sciezka))
    except Exception:
        return False


def _hermes_pyta_o_kod() -> bool:
    """execute_code: Hermes pyta o cały skrypt sam w bramie i przy HERMES_EXEC_ASK (tools/approval.py:1273-1279)."""
    try:
        from tools.approval_context import _is_gateway_approval_context
        return bool(_is_gateway_approval_context() or _prawda(os.environ.get("HERMES_EXEC_ASK")))
    except Exception:
        return _prawda(os.environ.get("HERMES_EXEC_ASK"))


def _terminal_cwd() -> str:
    try:
        from agent.runtime_cwd import scope_terminal_cwd
        return str(scope_terminal_cwd() or "").strip()
    except Exception:
        return os.environ.get("TERMINAL_CWD", "").strip()


def _baza(task_id: str) -> Optional[str]:
    """Katalog, od którego Hermes liczy ścieżki względne (cwd sesji po `cd`, nadpisanie, TERMINAL_CWD)."""
    try:
        from tools.file_tools_paths import _authoritative_workspace_root
        k = _authoritative_workspace_root(task_id or "default")
        if k:
            return str(k)
    except Exception:
        pass
    t = _terminal_cwd()
    if t and t.lower() not in {".", "./", "auto", "cwd"}:
        return t
    try:
        return os.getcwd()
    except OSError:
        return None


def _dom() -> str:
    """HOME procesów terminala (przy terminal.home_mode: profile to katalog profilu)."""
    try:
        from hermes_constants import get_subprocess_home
        h = get_subprocess_home()
        if h:
            return str(h)
    except Exception:
        pass
    return os.path.expanduser("~")


def _plik_konfigu() -> Optional[str]:
    try:
        from hermes_cli.config import get_config_path
        return str(get_config_path())
    except Exception:
        return None


# maski na wypadek braku agent.redact (i druga warstwa po nim)
_MASKI = [
    (re.compile(r"(?i)(authorization:\s*(?:bearer|token|basic)\s+)[^\s'\"]+"), r"\1***"),
    (re.compile(r"(?i)(\bbearer\s+)[A-Za-z0-9._~+/=-]{8,}"), r"\1***"),
    (re.compile(r"(?i)\b([A-Z0-9_]*(?:API_?KEY|TOKEN|SECRET|PASSWORD|PASSWD|PASS|PWD|CREDENTIAL|AUTH)[A-Z0-9_]*)"
                r"(\s*[=:]\s*)(['\"]?)(?!(?:bearer|basic|token)\b)([^\s'\"]+)\3"), r"\1\2\3***\3"),
    (re.compile(r"(?i)(--?(?:token|password|passwd|pass|api[-_]?key|secret|auth)(?:=|\s+))(?!-)\S+"), r"\1***"),
    (re.compile(r"\b(sk-|ghp_|gho_|ghs_|github_pat_|glpat-|xox[abprs]-|hf_|AKIA|AIza)[A-Za-z0-9_-]{8,}"), r"\1***"),
    (re.compile(r"(://)[^/\s:@]+:[^/\s@]+@"), r"\1***@"),
    (re.compile(r"(?<![\w/\\.-])[A-Za-z0-9_+=-]{40,}(?![\w/\\.-])"), "***"),
]


def _maskuj(tekst: Any) -> str:
    t = str(tekst)
    try:
        from agent.redact import redact_sensitive_text
        t = redact_sensitive_text(t, force=True)
    except Exception:
        pass
    for wzor, zamiana in _MASKI:
        t = wzor.sub(zamiana, t)
    return t


# ------------------------------------------------------------------------------------------------ ścieżki

_MSYS = re.compile(r"^/(?:(?:cygdrive|mnt)/)?([a-zA-Z])(/.*)?$")
_URZADZENIA_PUSTE = {"/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty", "/dev/fd/1", "/dev/fd/2"}


def _z_msys(s: str) -> str:
    """Git Bash /c/Users/x, /cygdrive/c/..., /mnt/c/... → C:\\Users\\x (tylko Windows; jak local.py:117-125)."""
    if not WINDOWS:
        return s
    m = _MSYS.match(s)
    if not m:
        return s
    ogon = (m.group(2) or "").replace("/", "\\")
    return f"{m.group(1).upper()}:{ogon or chr(92)}"


def _przestrzen_nt(s: str) -> bool:
    t = s.replace("/", "\\")
    return t.startswith("\\??\\") or t.startswith("\\\\.\\") or t.startswith("\\\\?\\")


def _unc(s: str) -> bool:
    return WINDOWS and (s.startswith("\\\\") or s.startswith("//")) and not _przestrzen_nt(s)


def _klucz(p: str) -> str:
    """Postać do porównań: bez \\\\?\\, bez wielkości liter na Windows i macOS (+ NFC na macOS), bez końcowego ukośnika."""
    s = str(p)
    if WINDOWS:
        if s.startswith("\\\\?\\UNC\\"):
            s = "\\\\" + s[8:]
        elif s.startswith("\\\\?\\"):
            s = s[4:]
        s = os.path.normcase(s)
    elif MACOS:
        s = unicodedata.normalize("NFC", s).casefold()
    while len(s) > 1 and s[-1] in "\\/" and os.path.dirname(s) != s:
        s = s[:-1]
    return s


def _wewnatrz(k: str, korzen: str) -> bool:
    if not korzen:
        return False
    if k == korzen:
        return True
    pref = korzen if korzen[-1] in "\\/" else korzen + os.sep
    return k.startswith(pref)


def _realna(surowa: str, baza: Optional[str], *, powloka: bool = False, dom: Optional[str] = None) -> Optional[str]:
    """Rzeczywista ścieżka (realpath: dowiązania, junction, `..`); None = nie wiadomo, gdzie leży.

    Ścieżek UNC nie rozwiązujemy (samo otwarcie \\\\serwer\\udzial wysyła skrót NTLM), tylko normalizujemy.
    `powloka`: ścieżka z polecenia Git Bash, gdzie /tmp i /usr to montowania Git, nie dysk C:."""
    s = str(surowa or "").strip()
    if not s or "\x00" in s or _przestrzen_nt(s):
        return None
    if s == "~" or s.startswith("~/") or (WINDOWS and s.startswith("~\\")):
        s = os.path.join(dom or _dom(), s[2:]) if len(s) > 1 else (dom or _dom())
    elif s.startswith("~"):
        s = os.path.expanduser(s)
        if s.startswith("~"):
            return None
    s = _z_msys(s)
    if WINDOWS:
        if _unc(s):
            return ntpath.normpath(s)
        if powloka and s[:1] in "/\\":
            return None
    if not os.path.isabs(s):
        if not baza:
            return None
        b = _z_msys(str(baza))
        if WINDOWS and (_unc(b) or _przestrzen_nt(b)):
            return None
        s = os.path.join(b, s)
    try:
        return os.path.realpath(s)
    except (OSError, ValueError, RuntimeError):
        return None


def _skladnik(s: str) -> str:
    """Nazwa do porównań: bez wielkości liter; na Windows bez strumienia ADS (`.git::$INDEX_ALLOCATION`) i bez końcowych
    kropek i spacji, które Windows i tak obcina (`.git.` = `.git`)."""
    if WINDOWS:
        s = s.split(":", 1)[0].rstrip(" .") or s
    return unicodedata.normalize("NFC", s).casefold()


def _skladniki(k: str, korzen: Optional[str]) -> List[str]:
    rel = k[len(korzen):] if korzen and _wewnatrz(k, korzen) else (ntpath.splitdrive(k)[1] if WINDOWS else k)
    return [_skladnik(c) for c in re.split(r"[\\/]+", rel) if c]


def _zbyt_szeroki(k: str) -> bool:
    """Folder startu, który nie może być „projektem”: korzeń dysku, katalog domowy i jego przodkowie."""
    if os.path.dirname(k) == k:
        return True
    domy = {os.path.expanduser("~"), os.environ.get("USERPROFILE", ""), os.environ.get("HOME", "")}
    for d in filter(None, domy):
        try:
            kd = _klucz(os.path.realpath(d))
        except (OSError, ValueError):
            continue
        if k == kd or _wewnatrz(kd, k):
            return True
    return False


@dataclass
class _Miejsca:
    """Katalogi tej decyzji (klucze do porównań + postać do komunikatów)."""
    tryb: str                                   # pytaj | projekt (pełny ocenia się jak projekt)
    bez_czl: Optional[str]                      # None albo klucz KONTEKSTY
    yolo: bool
    profil: str
    folder: Optional[str] = None
    folder_k: Optional[str] = None
    karta: Optional[str] = None
    karta_k: Optional[str] = None
    wiedza: str = ""
    misje: str = ""
    dozwolone: List[str] = field(default_factory=list)
    dane: List[str] = field(default_factory=list)
    robocze: List[str] = field(default_factory=list)
    konfig_k: Optional[str] = None


def _profil(home: Path) -> str:
    return home.name if home.parent.name.lower() == "profiles" else "host"


def _korzen_danych(home: Path) -> Path:
    return home.parent.parent if home.parent.name.lower() == "profiles" else home


def _k_realny(p: Any) -> Optional[str]:
    if not p:
        return None
    r = _realna(str(p), None)
    return _klucz(r) if r else None


def _folder_projektu(karta: Optional[str]) -> Optional[str]:
    if karta:                                   # pracownik karty: folderem jest katalog karty, nie folder czatu
        return karta
    f = _start()["folder"] or _terminal_cwd()
    if not f or f.strip().lower() in {".", "./", "auto", "cwd"}:
        return None
    r = _realna(f, None)
    if not r or _zbyt_szeroki(_klucz(r)):
        return None
    return r


def _miejsca(tryb: str, bez_czl: Optional[str], yolo: bool) -> _Miejsca:
    home = _hermes_home()
    root = _korzen_danych(home)
    m = _Miejsca(tryb="pytaj" if tryb == "pytaj" else "projekt", bez_czl=bez_czl, yolo=yolo, profil=_profil(home))
    ws = os.environ.get("HERMES_KANBAN_WORKSPACE", "").strip()
    if ws and os.path.isabs(_z_msys(ws)):
        m.karta = _realna(ws, None)
        m.karta_k = _klucz(m.karta) if m.karta else None
    pracownik = bool(os.environ.get("HERMES_KANBAN_TASK", "").strip())
    m.folder = _folder_projektu(m.karta if pracownik else None)
    m.folder_k = _klucz(m.folder) if m.folder else None
    m.wiedza = os.environ.get("JARVO_KNOWLEDGE_DIR") or str(root / "jarvo" / "knowledge")
    m.misje = os.environ.get("JARVO_MISSIONS_DIR") or str(root / "jarvo" / "missions")
    wiedza_k, misje_k = _k_realny(m.wiedza), _k_realny(m.misje)
    m.robocze = [k for k in (_k_realny(root / "jarvo" / "workspaces"), wiedza_k, misje_k, m.karta_k) if k]
    # dane i kod Jarva: zawsze pytamy (stan zgód, sekrety, profile, wtyczki, kod Hermesa i tej wtyczki)
    m.dane = [k for k in (_k_realny(home), _k_realny(root), _k_realny(os.environ.get("JARVO_ROOT")),
                          _k_realny(os.environ.get("HERMES_SRC")), _k_realny(os.environ.get("JARVO_REPO")),
                          _k_realny(_HERE)) if k]
    if bez_czl:
        m.dozwolone = [k for k in (m.karta_k, wiedza_k, misje_k) if k]
        if m.tryb != "pytaj" and m.folder_k:   # to, co tryb przepuszcza bez pytania, przechodzi też bez człowieka
            m.dozwolone.append(m.folder_k)
    else:
        m.dozwolone = [k for k in (m.folder_k, m.karta_k) if k]
    konf = _plik_konfigu()
    m.konfig_k = _k_realny(konf) if konf else None
    return m


@dataclass
class _Werdykt:
    rodzaj: str          # ok | pytaj | blokuj | hermes (Hermes zapyta albo odmówi sam) | nieznana
    sciezka: str         # do komunikatu
    powod: str = ""
    zawsze: bool = False  # powód z listy „zawsze pytaj”: nie omija go stała zgoda na polecenie


def _pokaz(p: str, limit: int = 110) -> str:
    """Ścieżka do komunikatu: zamaskowana, z końcem (nazwa pliku) zawsze widocznym."""
    s = _maskuj(p)
    return s if len(s) <= limit else "…" + s[-(limit - 1):]


def _poczatek(tekst: str, limit: int = 160) -> str:
    """Polecenie do komunikatu: zamaskowane, w jednej linii, z początkiem (program) zawsze widocznym."""
    s = _maskuj(" ".join(str(tekst).split()))
    return s if len(s) <= limit else s[:limit - 1] + "…"


def _ocen_sciezke(realna: Optional[str], surowa: str, m: _Miejsca, *, plikowe: bool, task_id: str = "") -> _Werdykt:
    """Werdykt dla jednej ścieżki zapisu (plikowe = write_file/patch, inaczej cel polecenia terminala)."""
    if realna is None:
        if plikowe and _przestrzen_nt(str(surowa)):
            return _Werdykt("hermes", _pokaz(surowa), "przestrzeń NT (odrzuca Hermes)")
        return _Werdykt("nieznana", _pokaz(surowa), "ścieżki nie da się sprawdzić")
    k = _klucz(realna)
    w_danych = any(_wewnatrz(k, d) for d in m.dane) and not any(_wewnatrz(k, r) for r in m.robocze)
    nazwa = _skladnik(os.path.basename(k) or k)
    pokaz = _pokaz(realna)
    if (m.konfig_k and k == m.konfig_k) or (nazwa == NAZWA_KONFIGU and w_danych):
        return _Werdykt("blokuj", pokaz, "config.yaml", zawsze=True)
    korzen = next((r for r in m.dozwolone if _wewnatrz(k, r)), None)
    skl = _skladniki(k, korzen)
    chronione = next((c for c in skl if c in CHRONIONE_KATALOGI), None)
    if not chronione and skl and (skl[-1] in CHRONIONE_PLIKI or skl[-1] in PLIKI_INSTRUKCJI):
        chronione = os.path.basename(realna)
    if not chronione and w_danych:
        chronione = "dane Jarva"
    if m.bez_czl:
        if korzen and not chronione:
            return _Werdykt("ok", pokaz)
        return _Werdykt("blokuj", pokaz, f"chronione: {chronione}" if chronione else "poza dozwolonymi katalogami",
                        zawsze=bool(chronione))
    if plikowe:
        if skl and skl[-1] in PLIKI_INSTRUKCJI and _hermes_pyta_o_instrukcje(surowa or realna, task_id):
            return _Werdykt("hermes", pokaz, "plik instrukcji (pyta Hermes)")
        if _hermes_odmowi_zapisu(realna):
            return _Werdykt("hermes", pokaz, "zapis odrzuca Hermes")
    if chronione:
        return _Werdykt("blokuj" if m.yolo else "pytaj", pokaz, f"chronione: {chronione}", zawsze=True)
    if m.tryb == "pytaj":
        return _Werdykt("pytaj", pokaz, "zapis")
    if korzen:
        return _Werdykt("ok", pokaz)
    return _Werdykt("pytaj", pokaz, "poza folderem projektu" if m.folder_k else "brak folderu projektu")


# ------------------------------------------------------------------------------------------------ powłoka: rozbiór
# Rozbiór polecenia bash na proste polecenia (słowa, przekierowania, łącznik). Wszystkiego, czego nie umiemy ocenić
# ($(...), `...`, <(...), podpowłoki, pętle, eval), nie zgadujemy: polecenie jest „złożone”, a cele nieznane.

class _Skladnia(Exception):
    """Polecenie, którego nie rozbieramy (niezamknięty cudzysłów, przekierowanie bez celu)."""


@dataclass
class _Slowo:
    czesci: List[Tuple[str, str]]   # (u = bez cudzysłowu, d = w "…", s = dosłownie, x = podstawienie), tekst

    def surowe(self) -> str:
        return "".join(t for _, t in self.czesci)

    def zwykle(self) -> Optional[str]:
        """Tekst słowa bez cudzysłowu i podstawień ($ zostaje); None, gdy ma $(…) albo `…`."""
        if any(r == "x" for r, _ in self.czesci):
            return None
        return "".join(t for _, t in self.czesci)


@dataclass
class _Polecenie:
    slowa: List[_Slowo] = field(default_factory=list)
    przekierowania: List[Tuple[str, _Slowo]] = field(default_factory=list)
    lacznik: str = ""


_SEPARATORY = ("&&", "||", ";;", "|&", ";", "|", "&", "(", ")")
_PRZEKIEROWANIA = ("&>>", "&>", "<<<", "<<-", "<<", "<>", "<&", ">>", ">|", ">&", "<", ">")
_ZAPISUJACE = frozenset({">", ">>", ">|", "&>", "&>>", ">&", "<>"})


def _koniec_nawiasu(t: str, i: int) -> int:
    """Indeks `)` zamykającego `$(` (i za `$(`), z zagnieżdżeniem i cudzysłowami; -1, gdy brak."""
    gl, n = 1, len(t)
    while i < n:
        c = t[i]
        if c == "\\":
            i += 2
            continue
        if c == "'":
            j = t.find("'", i + 1)
            if j < 0:
                return -1
            i = j + 1
            continue
        if c == '"':
            i += 1
            while i < n and t[i] != '"':
                i += 2 if t[i] == "\\" else 1
            i += 1
            continue
        if c == "(":
            gl += 1
        elif c == ")":
            gl -= 1
            if gl == 0:
                return i
        i += 1
    return -1


def _koniec_backticku(t: str, i: int) -> int:
    n = len(t)
    while i < n:
        if t[i] == "\\":
            i += 2
            continue
        if t[i] == "`":
            return i
        i += 1
    return -1


def _rozbierz(tekst: str) -> Tuple[List[_Polecenie], bool]:
    """Polecenie powłoki → (proste polecenia, złożone). Treść heredoców pomija (to dane)."""
    polecenia: List[_Polecenie] = []
    stan: Dict[str, Any] = {"biez": _Polecenie(), "czesci": [], "w_slowie": False, "oczekuje": None, "zlozone": False}
    heredoki: List[Tuple[str, bool, bool]] = []
    i, n = 0, len(tekst)

    def dodaj(rodzaj: str, t: str) -> None:
        cz = stan["czesci"]
        if cz and cz[-1][0] == rodzaj and rodzaj != "x":
            cz[-1] = (rodzaj, cz[-1][1] + t)
        else:
            cz.append((rodzaj, t))
        stan["w_slowie"] = True

    def zamknij_slowo() -> None:
        if not stan["w_slowie"]:
            return
        slowo = _Slowo(list(stan["czesci"]))
        stan["czesci"], stan["w_slowie"] = [], False
        op = stan["oczekuje"]
        if op is not None:
            stan["oczekuje"] = None
            if op in ("<<", "<<-"):
                cytowany = any(r in ("s", "d") for r, _ in slowo.czesci)
                heredoki.append((slowo.surowe(), op == "<<-", cytowany))
            else:
                stan["biez"].przekierowania.append((op, slowo))
        else:
            stan["biez"].slowa.append(slowo)

    def zamknij_polecenie(lacznik: str) -> None:
        zamknij_slowo()
        if stan["oczekuje"] is not None:
            raise _Skladnia("przekierowanie bez celu")
        b = stan["biez"]
        if b.slowa or b.przekierowania:
            b.lacznik = lacznik
            polecenia.append(b)
        stan["biez"] = _Polecenie()

    def podwojny(i: int) -> int:
        bufor: List[str] = []

        def wypusc() -> None:
            if bufor:
                dodaj("d", "".join(bufor))
                bufor.clear()

        while i < n:
            c = tekst[i]
            if c == '"':
                wypusc()
                dodaj("d", "")
                return i + 1
            if c == "\\" and i + 1 < n:
                nx = tekst[i + 1]
                if nx == "\n":
                    i += 2
                    continue
                if nx in '$`"\\':
                    wypusc()
                    dodaj("s", nx)
                    i += 2
                    continue
            if c == "`":
                wypusc()
                j = _koniec_backticku(tekst, i + 1)
                if j < 0:
                    raise _Skladnia("niezamknięty `")
                dodaj("x", tekst[i:j + 1])
                stan["zlozone"] = True
                i = j + 1
                continue
            if c == "$" and tekst.startswith("$(", i):
                wypusc()
                j = _koniec_nawiasu(tekst, i + 2)
                if j < 0:
                    raise _Skladnia("niezamknięte $(")
                dodaj("x", tekst[i:j + 1])
                stan["zlozone"] = True
                i = j + 1
                continue
            bufor.append(c)
            i += 1
        raise _Skladnia("niezamknięty cudzysłów")

    def wczytaj_heredoki(i: int) -> int:
        for ogr, bez_tabow, cytowany in heredoki:
            while i < n:
                j = tekst.find("\n", i)
                linia = (tekst[i:] if j < 0 else tekst[i:j]).rstrip("\r")
                i = n if j < 0 else j + 1
                if (linia.lstrip("\t") if bez_tabow else linia) == ogr:
                    break
                if not cytowany and ("$(" in linia or "`" in linia):
                    stan["zlozone"] = True
        heredoki.clear()
        return i

    while i < n:
        c = tekst[i]
        if c == "\\":
            if i + 1 < n and tekst[i + 1] == "\n":
                i += 2
            elif i + 1 < n:
                dodaj("s", tekst[i + 1])
                i += 2
            else:
                i += 1
            continue
        if c == "'":
            j = tekst.find("'", i + 1)
            if j < 0:
                raise _Skladnia("niezamknięty cudzysłów")
            dodaj("s", tekst[i + 1:j])
            i = j + 1
            continue
        if c == '"':
            i = podwojny(i + 1)
            continue
        if c == "`":
            j = _koniec_backticku(tekst, i + 1)
            if j < 0:
                raise _Skladnia("niezamknięty `")
            dodaj("x", tekst[i:j + 1])
            stan["zlozone"] = True
            i = j + 1
            continue
        if c == "$":
            if tekst.startswith("$(", i):
                j = _koniec_nawiasu(tekst, i + 2)
                if j < 0:
                    raise _Skladnia("niezamknięte $(")
                dodaj("x", tekst[i:j + 1])
                stan["zlozone"] = True
                i = j + 1
                continue
            if tekst.startswith("$'", i) or tekst.startswith('$"', i):
                q = tekst[i + 1]
                j = i + 2
                while j < n and tekst[j] != q:
                    j += 2 if tekst[j] == "\\" else 1
                if j >= n:
                    raise _Skladnia("niezamknięty cudzysłów")
                dodaj("x", tekst[i:j + 1])
                stan["zlozone"] = True
                i = j + 1
                continue
            dodaj("u", "$")
            i += 1
            continue
        if c == "#" and not stan["w_slowie"]:
            j = tekst.find("\n", i)
            i = n if j < 0 else j
            continue
        if c in " \t\r":
            zamknij_slowo()
            i += 1
            continue
        if c == "\n":
            zamknij_polecenie("\n")
            i += 1
            if heredoki:
                i = wczytaj_heredoki(i)
            continue
        if c in "<>" and i + 1 < n and tekst[i + 1] == "(":        # <(…) i >(…)
            j = _koniec_nawiasu(tekst, i + 2)
            if j < 0:
                raise _Skladnia("niezamknięte <(")
            zamknij_slowo()
            dodaj("x", tekst[i:j + 1])
            stan["zlozone"] = True
            i = j + 1
            continue
        if c in "<>&":
            op = next((o for o in _PRZEKIEROWANIA if tekst.startswith(o, i)), None)
            if op:
                cz = stan["czesci"]
                if stan["w_slowie"] and len(cz) == 1 and cz[0][0] == "u" and cz[0][1].isdigit():
                    stan["czesci"], stan["w_slowie"] = [], False      # deskryptor, np. 2>
                else:
                    zamknij_slowo()
                if stan["oczekuje"] is not None:
                    raise _Skladnia("dwa przekierowania")
                stan["oczekuje"] = op
                i += len(op)
                continue
        sep = next((s for s in _SEPARATORY if tekst.startswith(s, i)), None)
        if sep:
            if sep in ("(", ")"):
                stan["zlozone"] = True
            zamknij_polecenie(";" if sep in ("(", ")", ";;") else sep)
            i += len(sep)
            continue
        dodaj("u", c)
        i += 1
    zamknij_polecenie("")
    return polecenia, bool(stan["zlozone"])


# ------------------------------------------------------------------------------------------------ powłoka: rozwinięcie

_NAZWA_ZM = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_GLOB = {"*": "\ue000", "?": "\ue001", "[": "\ue002"}
_ODGLOB = {v: k for k, v in _GLOB.items()}
_PRZYPISANIE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\+?=")


# zmienne środowiska, które proces terminala ma na pewno takie jak wtyczka (reszta = nie wiadomo: Hermes i pliki
# shell_init Jarva zmieniają w terminalu np. USERPROFILE, APPDATA i XDG_CONFIG_HOME, a sekrety usuwa)
_ZMIENNE_ZNANE = re.compile(r"^(?:HERMES_\w+|JARVO_\w+|TERMINAL_CWD)$")
# przypisanie tych zmiennych zmienia działanie programów z listy tylko do odczytu (LESSOPEN, GIT_PAGER, PATH,
# LD_PRELOAD, HOME → ~/.gitconfig…) albo samą powłokę (IFS, CDPATH): polecenie jest wtedy „złożone”
_ZMIENNE_GROZNE = re.compile(
    r"^(?:PATH|LD_\w*|DYLD_\w*|BASH_ENV|ENV|SHELLOPTS|BASHOPTS|IFS|CDPATH|GLOBIGNORE|PS4|PROMPT_COMMAND|LESS\w*|PAGER"
    r"|MANPAGER|MANOPT|GIT_\w*|EDITOR|VISUAL|PYTHON\w*|NODE_\w*|NPM_CONFIG_\w*|PERL\w*|RUBY\w*|HOME|USERPROFILE"
    r"|XDG_CONFIG_\w*|GCONV_PATH|LOCPATH|SSH_ASKPASS|SUDO_ASKPASS|BROWSER|TERMINFO\w*|INPUTRC|ZDOTDIR|COMSPEC|PATHEXT"
    r"|MSYS\w*|CYGWIN)$", re.I)


def _wartosc(nazwa: str, zmienne: Dict[str, Optional[str]], dom: str) -> Optional[str]:
    if nazwa in zmienne:
        return zmienne[nazwa]
    if nazwa == "HOME":
        return dom
    return os.environ.get(nazwa) if _ZMIENNE_ZNANE.match(nazwa) else None


def _zmienne_w(t: str, zmienne: Dict[str, Optional[str]], dom: str, *, nieosloniete: bool) -> Optional[str]:
    """$NAZWA i ${NAZWA}; wszystko inne ($1, ${X:-y}, nieznana zmienna) = nie wiadomo (None)."""
    if "$" not in t:
        return t
    wynik: List[str] = []
    i, n = 0, len(t)
    while i < n:
        c = t[i]
        if c != "$" or i + 1 >= n:
            wynik.append(c)
            i += 1
            continue
        if t[i + 1] == "{":
            j = t.find("}", i + 2)
            if j < 0 or not _NAZWA_ZM.fullmatch(t[i + 2:j]):
                return None
            nazwa, i = t[i + 2:j], j + 1
        else:
            m = _NAZWA_ZM.match(t, i + 1)
            if not m:
                if t[i + 1] in "0123456789@*#?$!-":
                    return None
                wynik.append(c)
                i += 1
                continue
            nazwa, i = m.group(0), m.end()
        w = _wartosc(nazwa, zmienne, dom)
        if w is None or (nieosloniete and any(ch.isspace() for ch in w)):
            return None
        wynik.append(w)
    return "".join(wynik)


def _pierwsza_klamra(t: str) -> Optional[Tuple[int, int, List[str]]]:
    i, n = 0, len(t)
    while i < n:
        if t[i] == "$" and i + 1 < n and t[i + 1] == "{":
            j = t.find("}", i + 2)
            i = n if j < 0 else j + 1
            continue
        if t[i] == "{":
            gl, j, czesci, ost = 1, i + 1, [], i + 1
            while j < n and gl:
                if t[j] == "{":
                    gl += 1
                elif t[j] == "}":
                    gl -= 1
                elif t[j] == "," and gl == 1:
                    czesci.append(t[ost:j])
                    ost = j + 1
                j += 1
            if gl:
                return None
            srodek = t[i + 1:j - 1]
            if czesci:
                return i, j - 1, czesci + [t[ost:j - 1]]
            sek = re.fullmatch(r"(-?\d+)\.\.(-?\d+)(?:\.\.(-?\d+))?", srodek)
            if sek:
                a, b = int(sek.group(1)), int(sek.group(2))
                krok = abs(int(sek.group(3) or 1)) or 1
                if abs(b - a) // krok > _MAX_WARIANTOW:
                    return None
                zakres = range(a, b + 1, krok) if a <= b else range(a, b - 1, -krok)
                return i, j - 1, [str(x) for x in zakres]
            lit = re.fullmatch(r"([A-Za-z])\.\.([A-Za-z])", srodek)
            if lit:
                a, b = ord(lit.group(1)), ord(lit.group(2))
                zakres = range(a, b + 1) if a <= b else range(a, b - 1, -1)
                return i, j - 1, [chr(x) for x in zakres]
            i = j
            continue
        i += 1
    return None


def _klamry(t: str, glebokosc: int = 0) -> Optional[List[str]]:
    """Rozwinięcie klamer bash ({a,b}, {1..3}); None, gdy wynik byłby niepewny (niedomknięte klamry z przecinkiem)."""
    if "{" not in t and "}" not in t:
        return [t]
    if glebokosc > 8:
        return None
    k = _pierwsza_klamra(t)
    if k is None:
        bez_zm = re.sub(r"\$\{[^}]*\}", "", t)
        if bez_zm.count("{") != bez_zm.count("}") and ("," in bez_zm or ".." in bez_zm):
            return None
        return [t]
    a, b, czesci = k
    wynik: List[str] = []
    for c in czesci:
        dalej = _klamry(t[:a] + c + t[b + 1:], glebokosc + 1)
        if dalej is None:
            return None
        wynik.extend(dalej)
        if len(wynik) > _MAX_WARIANTOW:
            return None
    return wynik


def _rozwin(slowo: _Slowo, zmienne: Dict[str, Optional[str]], dom: str) -> Optional[List[str]]:
    """Warianty słowa po rozwinięciu (klamry, ~, zmienne); znaki globu bez cudzysłowu zamienione na \\ue000-\\ue002.
    None = nie wiadomo (podstawienie, nieznana zmienna, $1)."""
    warianty = [""]
    for idx, (rodzaj, t) in enumerate(slowo.czesci):
        if rodzaj == "x":
            return None
        if rodzaj == "s":
            kawalki = [t]
        else:
            if rodzaj == "u" and idx == 0 and t.startswith("~"):
                koniec = t.find("/")
                glowa = t if koniec < 0 else t[:koniec]
                if glowa == "~":
                    t = dom + ("" if koniec < 0 else t[koniec:])
                elif _NAZWA_ZM.fullmatch(glowa[1:]):
                    rozw = os.path.expanduser(glowa)
                    if rozw == glowa:
                        return None
                    t = rozw + ("" if koniec < 0 else t[koniec:])
                else:
                    return None                     # ~+, ~-, ~1: katalogi ze stosu powłoki
            surowe = _klamry(t) if rodzaj == "u" else [t]
            if surowe is None:
                return None
            kawalki = []
            for s in surowe:
                r = _zmienne_w(s, zmienne, dom, nieosloniete=(rodzaj == "u"))
                if r is None:
                    return None
                kawalki.append("".join(_GLOB.get(ch, ch) for ch in r) if rodzaj == "u" else r)
        warianty = [w + k for w in warianty for k in kawalki]
        if len(warianty) > _MAX_WARIANTOW:
            return None
    return warianty


@dataclass
class _Arg:
    """Jedno słowo polecenia po rozwinięciu (wariant klamer to osobny argument, jak w bash)."""
    tekst: Optional[str]          # ze znacznikami globu -; None = nie wiadomo
    pokaz: str                    # do komunikatu (zamaskowane)

    @property
    def plaski(self) -> Optional[str]:
        return None if self.tekst is None else "".join(_ODGLOB.get(ch, ch) for ch in self.tekst)


def _argumenty(slowo: _Slowo, zmienne: Dict[str, Optional[str]], dom: str) -> List[_Arg]:
    pokaz = _maskuj(slowo.surowe())[:120]
    warianty = _rozwin(slowo, zmienne, dom)
    if warianty is None:
        return [_Arg(None, pokaz)]
    return [_Arg(w, pokaz) for w in warianty]


def _plaski(slowo: _Slowo, zmienne: Dict[str, Optional[str]], dom: str) -> Optional[str]:
    """Jedna postać słowa (nazwa programu, wartość przypisania); None = nie wiadomo albo kilka wariantów."""
    w = _rozwin(slowo, zmienne, dom)
    if not w or len(w) != 1:
        return None
    return "".join(_ODGLOB.get(ch, ch) for ch in w[0])


def _sciezki_celu(tekst: str, cwd: Optional[str], dom: str) -> Optional[List[str]]:
    """Rzeczywiste ścieżki jednego wariantu celu; glob: katalog przed pierwszym znakiem globu + to, co pasuje."""
    if tekst in _URZADZENIA_PUSTE or (WINDOWS and tekst.lower() in ("nul", "nul:")):
        return []
    znaki = [i for i, ch in enumerate(tekst) if ch in _ODGLOB]
    if not znaki:
        r = _realna(tekst, cwd, powloka=True, dom=dom)
        return None if r is None else [r]
    pierwszy = znaki[0]
    sep = max(tekst.rfind("/", 0, pierwszy), tekst.rfind("\\", 0, pierwszy))
    reszta = re.split(r"[\\/]+", tekst[pierwszy:])
    if any(c == ".." for c in reszta[1:]) or ".." in tekst[pierwszy:].replace("\\", "/").split("/"):
        return None
    if sep < 0:
        prefiks = "."
    elif sep == 0:
        prefiks = tekst[0]
    else:
        prefiks = tekst[:sep]
        if prefiks.endswith(":"):
            prefiks += "\\"
    baza = _realna(prefiks, cwd, powloka=True, dom=dom)
    if baza is None:
        return None
    wynik = [baza]
    wzor = "".join(_ODGLOB[ch] if ch in _ODGLOB else (_glob.escape(ch) if ch in "*?[" else ch) for ch in tekst)
    wzor = _z_msys(wzor)
    if not os.path.isabs(wzor):
        if not cwd:
            return None
        wzor = os.path.join(_z_msys(cwd), wzor)
    try:
        trafienia = list(itertools.islice(_glob.iglob(wzor), _MAX_DOPASOWAN))    # leniwie: katalog bywa ogromny
    except (OSError, ValueError, re.error):
        trafienia = []
    for t in trafienia:
        try:
            wynik.append(os.path.realpath(t))
        except (OSError, ValueError):
            return None
    return wynik


def _sciezki_arg(arg: _Arg, cwd: Optional[str], dom: str) -> Optional[List[str]]:
    if arg.tekst is None:
        return None
    if arg.tekst == "":
        return []                    # pusty argument ('') nie jest plikiem
    return _sciezki_celu(arg.tekst, cwd, dom)


# ------------------------------------------------------------------------------------------------ powłoka: klasyfikacja

_ODCZYT = frozenset({
    "ls", "dir", "vdir", "cat", "tac", "head", "tail", "wc", "grep", "egrep", "fgrep", "file", "stat", "du", "df",
    "pwd", "echo", "printf", "which", "whereis", "type", "true", "false", ":", "test", "[", "[[", "whoami", "id",
    "uname", "printenv", "basename", "dirname", "realpath", "readlink", "cut", "tr", "nl", "column", "sleep", "diff",
    "cmp", "comm", "md5sum", "sha1sum", "sha256sum", "sha512sum", "cksum", "b2sum", "tree", "jq", "less", "more", "ps",
    "seq", "od", "strings", "nproc", "cygpath", "where", "tasklist", "locale", "exit", "return", "wait", "jobs",
    "help", "rev", "fold", "fmt", "expand", "unexpand", "join", "paste", "numfmt", "uptime", "free", "groups",
})
# programy z listy, które jedną opcją zapisują (tree -o plik, file -C, less -o plik): litery krótkich opcji, długie
_ODCZYT_ZAKAZANE_OPCJE = {"tree": ("o", ("--output",)), "file": ("C", ("--compile",)),
                          "less": ("oO", ("--log-file", "--LOG-FILE"))}
_PLIKOWE = frozenset({"mkdir", "touch", "cp", "mv", "rm", "rmdir", "tee"})      # + sed -i
_STAN_POWLOKI = frozenset({"export", "unset", "set", "shopt", "declare", "typeset", "local", "readonly", "umask"})
_KLUCZOWE = frozenset({"if", "then", "else", "elif", "fi", "for", "while", "until", "do", "done", "case", "esac",
                       "select", "function", "time", "!", "coproc", "]]", "in"})
_NAGLOWKI = frozenset({"for", "select", "case", "function"})
_GIT_ODCZYT = frozenset({"status", "log", "diff", "show", "rev-parse", "ls-files", "ls-tree", "cat-file", "blame",
                         "describe", "shortlog", "grep", "rev-list", "name-rev", "show-ref", "for-each-ref",
                         "merge-base", "count-objects", "check-ignore", "var", "help", "version", "whatchanged"})
_GIT_BRANCH_ODCZYT = frozenset({"-a", "-r", "-v", "-vv", "--all", "--remotes", "--list", "-l", "--show-current",
                                "--verbose", "--no-color", "--color", "--no-column", "--column"})
_FIND_ZAPIS = frozenset({"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf", "-fls"})
_WERSJA = frozenset({"--version", "-V", "-v", "--help", "-h"})
# opcje z wartością w osobnym słowie (krótkie litery, długie nazwy), żeby wartości nie brać za ścieżkę
_OPCJE_Z_WARTOSCIA = {
    "mkdir": ("m", {"--mode"}), "touch": ("dtr", {"--date", "--reference", "--time"}),
    "cp": ("tS", {"--target-directory", "--suffix"}), "mv": ("tS", {"--target-directory", "--suffix"}),
    "rm": ("", set()), "rmdir": ("", set()), "tee": ("", set()),
}


def _sed_do_ogranicznika(s: str, i: int, d: str) -> int:
    while i < len(s):
        if s[i] == "\\":
            i += 2
            continue
        if s[i] == d:
            return i
        if s[i] == "\n":
            return -1
        i += 1
    return -1


def _sed_bezpieczny(skrypt: str) -> bool:
    """Skrypt sed bez zapisu i wykonywania: adresy (N, $, N,M, /re/) i polecenia p d q = l n N P D g G h H x z F
    oraz s/…/…/[gIipMm0-9] i y/…/…/ (bez flag w i e). Wszystko inne = nie wiadomo."""
    s, i, n = skrypt, 0, len(skrypt)

    def spacje(i: int) -> int:
        while i < n and s[i] in " \t":
            i += 1
        return i

    def adres(i: int) -> int:
        i = spacje(i)
        if i < n and s[i].isdigit():
            while i < n and s[i].isdigit():
                i += 1
            if i < n and s[i] == "~":
                i += 1
                while i < n and s[i].isdigit():
                    i += 1
        elif i < n and s[i] == "$":
            i += 1
        elif i < n and s[i] == "/":
            j = _sed_do_ogranicznika(s, i + 1, "/")
            if j < 0:
                return -1
            i = j + 1
            while i < n and s[i] in "IM":
                i += 1
        return i

    while True:
        while i < n and s[i] in " \t;\n":
            i += 1
        if i >= n:
            return True
        i = adres(i)
        if i < 0:
            return False
        i = spacje(i)
        if i < n and s[i] == ",":
            i = adres(i + 1)
            if i < 0:
                return False
        i = spacje(i)
        if i < n and s[i] == "!":
            i = spacje(i + 1)
        if i >= n:
            return False
        c = s[i]
        if c in "pd=lnNPDgGhHxzF":
            i += 1
        elif c in "qQ":
            i += 1
            while i < n and s[i].isdigit():
                i += 1
        elif c in "sy":
            d = s[i + 1] if i + 1 < n else ""
            if not d or d in "\\\n " or d.isalnum():
                return False
            j = _sed_do_ogranicznika(s, i + 2, d)
            k = _sed_do_ogranicznika(s, j + 1, d) if j >= 0 else -1
            if k < 0:
                return False
            i = k + 1
            if c == "s":
                while i < n and s[i] in "gGiIpPmM0123456789":
                    i += 1
        else:
            return False
        i = spacje(i)
        if i < n and s[i] not in ";\n":
            return False


def _opcje(argi: List[_Arg], krotkie: str, dlugie: set) -> Tuple[List[_Arg], Dict[str, List[_Arg]], bool]:
    """Pozycyjne argumenty, wartości opcji (klucz: litera albo długa nazwa) i czy był argument o nieznanej treści."""
    pozycyjne: List[_Arg] = []
    wartosci: Dict[str, List[_Arg]] = {}
    nieznane = False
    po_kreskach = False
    i = 0
    while i < len(argi):
        arg = argi[i]
        t = arg.plaski
        i += 1
        if t is None:
            pozycyjne.append(arg)
            nieznane = True
            continue
        if po_kreskach or t == "-" or not t.startswith("-"):
            pozycyjne.append(arg)
            continue
        if t == "--":
            po_kreskach = True
            continue
        if t.startswith("--"):
            nazwa, rowna, wart = t.partition("=")
            if nazwa in dlugie:
                if rowna:
                    wartosci.setdefault(nazwa, []).append(_Arg(wart, arg.pokaz))
                elif i < len(argi):
                    wartosci.setdefault(nazwa, []).append(argi[i])
                    i += 1
            continue
        for j, litera in enumerate(t[1:], start=1):
            if litera in krotkie:
                reszta = t[j + 1:]
                if reszta:
                    wartosci.setdefault(litera, []).append(_Arg(reszta, arg.pokaz))
                elif i < len(argi):
                    wartosci.setdefault(litera, []).append(argi[i])
                    i += 1
                break
    return pozycyjne, wartosci, nieznane


def _plikowe(prog: str, argi: List[_Arg]) -> Tuple[List[_Arg], bool]:
    """Cele zapisu prostych poleceń plikowych: mkdir/touch/rm/rmdir/tee = wszystkie pozycyjne, cp = cel, mv = wszystko
    (źródła też znikają ze swojego miejsca)."""
    krotkie, dlugie = _OPCJE_Z_WARTOSCIA[prog]
    poz, wart, nieznane = _opcje(argi, krotkie, dlugie)
    katalog = wart.get("t", []) + wart.get("--target-directory", [])
    if prog == "cp":
        cele = (katalog or poz[-1:]) if (katalog or len(poz) >= 2) else []
    elif prog == "mv":
        cele = (poz + katalog) if (katalog or len(poz) >= 2) else []
    elif prog == "rmdir" and any((a.plaski or "") == "--parents" or re.fullmatch(r"-[a-z]*p[a-z]*", a.plaski or "")
                                 for a in argi):
        cele = []
        for a in poz:                             # -p usuwa też katalogi nadrzędne podanej ścieżki
            t = a.tekst
            if t is None or any(ch in t for ch in _ODGLOB):
                cele.append(a)
                continue
            while t and t not in ("/", ".", "\\") and not re.fullmatch(r"[A-Za-z]:[\\/]?", t):
                cele.append(_Arg(t, a.pokaz))
                nowy = os.path.dirname(t.rstrip("/\\"))
                if nowy == t:
                    break
                t = nowy
    else:
        cele = poz
    return cele, nieznane


def _sed(argi: List[_Arg]) -> Tuple[str, List[_Arg], bool]:
    """sed: z -i (--in-place) to polecenie plikowe (cele = pliki), bez -i odczyt, gdy skrypt nie pisze i nie wykonuje."""
    w_miejscu, skrypty, z_pliku, nieznane = False, [], False, False
    pozycyjne: List[_Arg] = []
    po_kreskach = False
    i = 0
    while i < len(argi):
        arg = argi[i]
        t = arg.plaski
        i += 1
        if t is None:
            pozycyjne.append(arg)
            nieznane = True
            continue
        if po_kreskach or t == "-" or not t.startswith("-"):
            pozycyjne.append(arg)
            continue
        if t == "--":
            po_kreskach = True
            continue
        if t.startswith("--"):
            nazwa, rowna, wart = t.partition("=")
            if nazwa == "--in-place":
                w_miejscu = True
            elif nazwa in ("--expression", "--file", "--line-length"):
                tresc = wart if rowna else (argi[i].plaski if i < len(argi) else None)
                if not rowna:
                    i += 1
                if nazwa == "--expression":
                    skrypty.append(tresc)
                elif nazwa == "--file":
                    z_pliku = True
            continue
        for j, litera in enumerate(t[1:], start=1):
            if litera == "i":                       # GNU: reszta słowa to przyrostek kopii (-i.bak, -ie)
                w_miejscu = True
                break
            if litera in "efl":
                tresc = t[j + 1:] or (argi[i].plaski if i < len(argi) else None)
                if not t[j + 1:]:
                    i += 1
                if litera == "e":
                    skrypty.append(tresc)
                elif litera == "f":
                    z_pliku = True
                break
    if not skrypty and not z_pliku and pozycyjne:
        skrypty.append(pozycyjne[0].plaski)
        pozycyjne = pozycyjne[1:]
    bezpieczny = not z_pliku and all(s is not None and _sed_bezpieczny(s) for s in skrypty)
    if w_miejscu:
        return ("plikowe" if bezpieczny else "inne"), pozycyjne, nieznane
    return ("odczyt" if bezpieczny else "inne"), [], nieznane


def _git_odczyt(teksty: List[Optional[str]]) -> bool:
    i = 0
    while i < len(teksty) and (teksty[i] or "").startswith("-"):
        o = teksty[i]
        if o == "-C":
            i += 2
            continue
        if o in ("--no-pager", "-P", "--no-optional-locks", "--version", "--help"):
            i += 1
            continue
        return False                # -c, --git-dir, --work-tree, --exec-path…: mogą wykonać kod albo zmienić repo
    if i >= len(teksty):
        return True
    sub, reszta = teksty[i], teksty[i + 1:]
    if sub is None or any(r is None or r.startswith(("--output", "-O", "--open-files-in-pager", "--ext-diff"))
                          for r in reszta):
        return False
    if sub in _GIT_ODCZYT:
        return True
    if sub == "branch":                           # bez nazwy (nazwa = nowa gałąź)
        return all(r in _GIT_BRANCH_ODCZYT or r.startswith(("--contains", "--merged", "--no-merged", "--format",
                                                            "--sort", "--points-at")) for r in reszta)
    if sub == "remote":
        return not reszta or all(r in ("-v", "--verbose") for r in reszta) or reszta[0] in ("show", "get-url")
    if sub == "tag":
        return not reszta or reszta[0] in ("-l", "--list", "-n")
    if sub == "config":
        return any(r in ("--get", "--get-all", "--get-regexp", "--list", "-l", "--get-urlmatch") for r in reszta)
    if sub == "stash":
        return bool(reszta) and reszta[0] in ("list", "show")
    if sub == "worktree":
        return bool(reszta) and reszta[0] == "list"
    if sub == "reflog":
        return not reszta or reszta[0] == "show"
    return False


def _klasyfikuj(prog: str, goly: bool, argi: List[_Arg]) -> Tuple[str, List[_Arg], bool]:
    """(rodzaj, cele zapisu, nieznane): rodzaj = odczyt | plikowe | zapis (odczyt z zapisem do pliku) | cd | stan | inne."""
    teksty = [a.plaski for a in argi]
    if not goly:                                  # ./skrypt, /usr/bin/x: nie wiemy, co to jest
        return "inne", [], False
    if prog in ("cd", "pushd", "popd"):
        return "cd", [], False
    if prog in _STAN_POWLOKI:
        return "stan", [], False
    if prog == "command":
        return ("odczyt" if teksty[:1] in (["-v"], ["-V"]) else "inne"), [], False
    if prog == "env":
        return ("odczyt" if not argi else "inne"), [], False
    if len(teksty) == 1 and teksty[0] in _WERSJA:
        return "odczyt", [], False
    if prog == "git":
        return ("odczyt" if _git_odczyt(teksty) else "inne"), [], False
    if prog == "find":
        return ("inne" if any(t is None or t in _FIND_ZAPIS for t in teksty) else "odczyt"), [], False
    if prog == "rg":
        return ("inne" if any(t is None or t.startswith("--pre") for t in teksty) else "odczyt"), [], False
    if prog == "sort":
        if any(t is None or t.startswith("--compress-program") for t in teksty):
            return "inne", [], False
        _, wart, niez = _opcje(argi, "otkSTy", {"--output", "--key", "--buffer-size", "--temporary-directory",
                                                "--field-separator", "--parallel", "--files0-from", "--batch-size"})
        cele = wart.get("o", []) + wart.get("--output", [])
        return ("zapis" if cele else "odczyt"), cele, niez
    if prog == "uniq":                            # uniq WEJŚCIE WYJŚCIE: drugi argument to plik wyniku
        poz, _, niez = _opcje(argi, "fsw", {"--skip-fields", "--skip-chars", "--check-chars", "--group",
                                            "--all-repeated"})
        return ("zapis" if len(poz) >= 2 else "odczyt"), poz[1:2], niez
    if prog == "date":
        return ("inne" if any(t is None or t == "-s" or t.startswith("--set") for t in teksty) else "odczyt"), [], False
    if prog == "hostname":
        return ("inne" if any(t is None or not t.startswith("-") for t in teksty) else "odczyt"), [], False
    if prog == "sed":
        return _sed(argi)
    if prog in _PLIKOWE:
        cele, niez = _plikowe(prog, argi)
        return ("plikowe" if cele or niez else "odczyt"), cele, niez       # `tee` bez plików pisze tylko na ekran
    if prog in _ODCZYT:
        if prog in _ODCZYT_ZAKAZANE_OPCJE:
            litery, dlugie = _ODCZYT_ZAKAZANE_OPCJE[prog]
            for t in teksty:
                if t is None or t.startswith(dlugie) or (t.startswith("-") and not t.startswith("--")
                                                         and any(c in litery for c in t[1:])):
                    return "inne", [], False
        return "odczyt", [], False
    return "inne", [], False


@dataclass
class _Analiza:
    cele: List[Tuple[str, Optional[List[str]]]] = field(default_factory=list)   # (pokaz, ścieżki albo None)
    inne: List[str] = field(default_factory=list)                              # programy spoza listy
    nieznane: bool = False
    tylko_odczyt: bool = True


def _jedno_slowo(slowo: _Slowo, wartosci: Any) -> bool:
    return len(slowo.czesci) == 1 and slowo.czesci[0][0] == "u" and slowo.czesci[0][1] in wartosci


def _analizuj_terminal(polecenie: str, cwd0: Optional[str], dom: str) -> _Analiza:
    """Cele zapisu, programy spoza listy tylko do odczytu i to, czego nie da się ocenić; cwd idzie za `cd`."""
    a = _Analiza()
    if len(polecenie) > _MAX_POLECENIA:
        a.nieznane, a.tylko_odczyt = True, False
        return a
    try:
        polecenia, zlozone = _rozbierz(polecenie)
    except _Skladnia:
        a.nieznane, a.tylko_odczyt = True, False
        return a
    a.nieznane = zlozone
    cwd: Optional[str] = cwd0
    zmienne: Dict[str, Optional[str]] = {"PWD": cwd0}
    w_potoku = False
    for p in polecenia:
        slowa = list(p.slowa)
        przypisania: List[_Slowo] = []
        while slowa and slowa[0].czesci[0][0] == "u" and _PRZYPISANIE.match(slowa[0].czesci[0][1]):
            przypisania.append(slowa.pop(0))
        for s in przypisania:                 # X=… przed poleceniem albo samo: groźna zmienna zmienia programy
            if _ZMIENNE_GROZNE.match(_PRZYPISANIE.match(s.czesci[0][1]).group(1)):
                a.nieznane = True
        while slowa and _jedno_slowo(slowa[0], _KLUCZOWE | {"{", "}"}):
            if not _jedno_slowo(slowa[0], {"{", "}"}):
                a.nieznane = True             # if/for/while/case…: pętli i warunków nie śledzimy
            if _jedno_slowo(slowa[0], _NAGLOWKI):
                slowa = []                    # `for x in …`, `case … in`, `function f`: to nie polecenie
                break
            slowa.pop(0)
        cele: List[_Arg] = []
        rodzaj = "pusty"
        if not slowa:
            for s in przypisania:             # X=wartość bez polecenia: zmienna powłoki na dalszą część polecenia
                surowy = s.czesci[0][1]
                m = _PRZYPISANIE.match(surowy)
                reszta = _Slowo([("u", surowy[m.end():])] + s.czesci[1:])
                zmienne[m.group(1)] = None if m.group(0).endswith("+=") else _plaski(reszta, zmienne, dom)
        else:
            nazwa = _plaski(slowa[0], zmienne, dom)
            if nazwa is None:
                rodzaj = "inne"
                a.inne.append(_maskuj(slowa[0].surowe())[:40])
                a.nieznane = True
            else:
                goly = not re.search(r"[\\/]", nazwa)
                prog = re.split(r"[\\/]", nazwa)[-1].lower()
                for rozsz in (".exe", ".cmd", ".bat", ".com"):
                    if prog.endswith(rozsz) and len(prog) > len(rozsz):
                        prog = prog[: -len(rozsz)]
                argi = [x for s in slowa[1:] for x in _argumenty(s, zmienne, dom)]
                rodzaj, cele, niez = _klasyfikuj(prog, goly, argi)
                a.nieznane = a.nieznane or niez
                if rodzaj == "inne":
                    a.inne.append(_maskuj(prog)[:40])
                elif rodzaj == "stan":
                    for x in argi:
                        t = x.plaski
                        if t is None:
                            a.nieznane = True
                            continue
                        m = _PRZYPISANIE.match(t)
                        nazwa_zm = m.group(1) if m else (t if prog in ("unset", "export", "declare", "typeset",
                                                                       "local", "readonly") else "")
                        if nazwa_zm and _ZMIENNE_GROZNE.match(nazwa_zm):
                            a.nieznane = True
                        if prog == "set" and (t in ("allexport", "-a") or re.fullmatch(r"-[a-zA-Z]*a[a-zA-Z]*", t)):
                            a.nieznane = True     # set -a: każde przypisanie trafia do środowiska programów
                        if m and prog != "unset":
                            zmienne[m.group(1)] = None if m.group(0).endswith("+=") else t[m.end():]
                        elif prog == "unset" and t:
                            zmienne[t] = None
                elif rodzaj == "cd" and p.lacznik in ("", ";", "&&", "||", "\n") and not w_potoku:
                    cel_cd = argi[0].plaski if argi else None
                    if prog == "popd" or cel_cd == "-":
                        cwd = None
                    elif not argi:
                        cwd = _realna(dom, None)
                    elif (os.environ.get("CDPATH") and cel_cd and not os.path.isabs(_z_msys(cel_cd))
                          and not cel_cd.startswith((".", "~"))):
                        cwd = None            # CDPATH: `cd x` może trafić w zupełnie inny katalog
                    else:
                        sc = _sciezki_arg(argi[0], cwd, dom)
                        cwd = sc[0] if sc and len(sc) == 1 else None
                    zmienne["PWD"] = cwd
        for op, cel in p.przekierowania:
            if op not in _ZAPISUJACE:
                continue
            t = cel.zwykle()
            if op == ">&" and t is not None and (t.isdigit() or t == "-"):
                continue                      # >&2, >&-: deskryptor, nie plik
            cele += _argumenty(cel, zmienne, dom)
        zapisy = [(cel.pokaz, _sciezki_arg(cel, cwd, dom)) for cel in cele]
        zapisy = [(pokaz, s) for pokaz, s in zapisy if s != []]      # /dev/null, '' to nie zapis
        if rodzaj not in ("odczyt", "cd", "stan", "pusty") or zapisy:
            a.tylko_odczyt = False
        a.cele += zapisy
        w_potoku = p.lacznik in ("|", "|&")
    if a.nieznane:
        a.tylko_odczyt = False
    return a


# ------------------------------------------------------------------------------------------------ decyzje

def _klucz_reguly(narzedzie: str, m: _Miejsca, tresc: str) -> str:
    """Wąski klucz „zawsze”: narzędzie + odcisk folderu projektu + skrót treści (Hermes zapisze plugin_rule:<klucz>)."""
    odcisk = hashlib.sha256((m.folder_k or "-").encode("utf-8", "surrogatepass")).hexdigest()[:10]
    skrot = hashlib.sha256(tresc.encode("utf-8", "surrogatepass")).hexdigest()[:16]
    return f"{NAZWA}:{narzedzie}:{odcisk}:{skrot}"


def _lista(werdykty: List[_Werdykt], ile: int = 3) -> str:
    sciezki = list(dict.fromkeys(w.sciezka for w in werdykty))
    s = ", ".join(sciezki[:ile])
    return s + (f" i {len(sciezki) - ile} innych" if len(sciezki) > ile else "")


def _porada_bez_czlowieka(m: _Miejsca) -> str:
    if m.bez_czl == "kanban":
        gdzie = _pokaz(m.karta) if m.karta else "$HERMES_KANBAN_WORKSPACE"
        return (f"Zapisuj w katalogu roboczym karty ({gdzie}), w skarbcu albo w misjach. Jeśli zadanie naprawdę wymaga "
                "tego zapisu, zatrzymaj kartę: kanban_block(kind=\"needs_input\", reason=\"potrzebna zgoda na …\").")
    if m.bez_czl == "podagent":
        return ("Zapisuj w folderze projektu, w skarbcu albo w misjach, a resztę opisz w wyniku dla agenta, który Cię "
                "wywołał: on zapyta właściciela.")
    return "Zapisuj w skarbcu albo w misjach, a resztę opisz w odpowiedzi; zgodę da właściciel w czacie."


def _blok(tresc: str) -> Dict[str, str]:
    return {"action": "block", "message": f"Zablokowane (jarvo-zgody): {tresc}"}


def _blok_werdyktow(werdykty: List[_Werdykt], m: _Miejsca, co: str) -> Dict[str, str]:
    konfig = [w for w in werdykty if w.powod == "config.yaml"]
    if konfig:
        return _blok(f"{_lista(konfig)} to konfiguracja Hermesa (zgody, modele, klucze). Agent nie zmienia jej w żadnym "
                     "trybie; zmianę robi właściciel (`jarvo`, `hermes config`).")
    if m.bez_czl:
        powody = "; ".join(dict.fromkeys(w.powod for w in werdykty))
        return _blok(f"{KONTEKSTY.get(m.bez_czl, m.bez_czl)} działa bez człowieka, więc nie ma kogo zapytać o zgodę na "
                     f"{co} {_lista(werdykty)} ({powody}). {_porada_bez_czlowieka(m)}")
    powody = ", ".join(dict.fromkeys(w.powod.replace("chronione: ", "") for w in werdykty))
    instrukcje = any(_skladnik(os.path.basename(w.sciezka)) in PLIKI_INSTRUKCJI for w in werdykty)
    return _blok(f"{_lista(werdykty)} to chronione miejsce ({powody}), a w trybie pełnym (YOLO) Hermes zatwierdza "
                 "wszystko sam, więc nie da się o nie zapytać. Wyłącz /yolo i ponów albo zrób to ręcznie."
                 + (" Pliki instrukcji zmieniaj przez write_file albo patch: o nie Hermes pyta zawsze." if instrukcje else ""))


def _prosba(narzedzie: str, m: _Miejsca, opis: str, tresc_klucza: str) -> Dict[str, str]:
    tryb = "pełny" if m.yolo else m.tryb
    return {"action": "approve", "rule_key": _klucz_reguly(narzedzie, m, tresc_klucza),
            "message": _maskuj(f"jarvo-zgody (tryb {tryb}): {opis}")[:400]}


def _opis_powodow(werdykty: List[_Werdykt]) -> str:
    grupy: Dict[str, List[_Werdykt]] = {}
    for w in werdykty:
        grupy.setdefault(w.powod, []).append(w)
    return "; ".join(f"{p}: {_lista(ws)}" for p, ws in grupy.items())


def _zapis_plikow(narzedzie: str, sciezki: List[str], m: _Miejsca, task_id: str) -> Optional[Dict[str, str]]:
    if not sciezki:
        return None
    baza = _baza(task_id)
    werdykty = [_ocen_sciezke(_realna(s, baza), s, m, plikowe=True, task_id=task_id) for s in sciezki]
    if m.bez_czl:
        for w in werdykty:
            if w.rodzaj == "nieznana":
                w.rodzaj, w.powod = "blokuj", "ścieżki nie da się sprawdzić"
    blok = [w for w in werdykty if w.rodzaj == "blokuj"]
    if blok:
        return _blok_werdyktow(blok, m, "zapis")
    pytaj = [w for w in werdykty if w.rodzaj in ("pytaj", "nieznana")]
    if not pytaj or m.bez_czl:
        return None
    co = "zapis pliku" if narzedzie == "write_file" else "zmiana plików"
    tresc = "\n".join(sorted(_klucz(_realna(s, baza) or s) for s in sciezki))
    return _prosba(narzedzie, m, f"{co} ({_opis_powodow(pytaj)})", tresc)


_V4A = re.compile(r"^\*\*\*\s*(?:Update|Add|Delete)\s+File:\s*(.+?)\s*$", re.M)
_V4A_MOVE = re.compile(r"^\*\*\*\s*Move\s+File:\s*(.+?)\s*->\s*(.+?)\s*$", re.M)
_V4A_MOVE_TO = re.compile(r"^\*\*\*\s*Move\s+to:\s*(.+?)\s*$", re.M)


def sciezki_latki(args: Dict[str, Any]) -> List[str]:
    """Ścieżki z narzędzia patch: `path` i każdy nagłówek V4A (Update, Add, Delete, Move File: a -> b, Move to:),
    niezależnie od `mode` (Hermes czyta nagłówki tylko przy mode="patch"; liczymy ostrożniej)."""
    wynik: List[str] = []
    if isinstance(args.get("path"), str) and args["path"].strip():
        wynik.append(args["path"].strip())
    latka = args.get("patch")
    if isinstance(latka, str) and latka:
        t = latka.replace("\r\n", "\n")
        wynik += [g.strip() for g in _V4A.findall(t)]
        for a, b in _V4A_MOVE.findall(t):
            wynik += [a.strip(), b.strip()]
        wynik += [g.strip() for g in _V4A_MOVE_TO.findall(t)]
    return list(dict.fromkeys(p for p in wynik if p))


def _terminal(args: Dict[str, Any], m: _Miejsca, task_id: str) -> Optional[Dict[str, str]]:
    polecenie = args.get("command")
    if not isinstance(polecenie, str) or not polecenie.strip():
        return None
    baza = _baza(task_id)
    wd = args.get("workdir")
    if isinstance(wd, str) and wd.strip():
        baza = _realna(wd, baza)
    dom = _dom()
    a = _analizuj_terminal(polecenie, baza, dom)
    werdykty: List[_Werdykt] = []
    for pokaz, sciezki in a.cele:
        if sciezki is None:
            werdykty.append(_Werdykt("nieznana", pokaz, "ścieżki nie da się sprawdzić"))
        else:
            werdykty += [_ocen_sciezke(s, pokaz, m, plikowe=False) for s in sciezki]
    blok = [w for w in werdykty if w.rodzaj == "blokuj"]
    if blok:
        return _blok_werdyktow(blok, m, "zapis")
    if m.bez_czl:
        return None       # bez człowieka: reszta (nieznane cele, inne programy) zostaje polityce Hermesa
    if _hermes_niebezpieczne(polecenie):
        return None       # niebezpieczne pyta albo blokuje Hermes (nie pytamy dwa razy)
    zawsze = [w for w in werdykty if w.rodzaj == "pytaj" and w.zawsze]
    zwykle = [w for w in werdykty if w.rodzaj in ("pytaj", "nieznana") and not w.zawsze]
    if m.tryb == "pytaj":                     # pytaj: wszystko poza poleceniami tylko do odczytu
        potrzebne = not a.tylko_odczyt or bool(zawsze or zwykle)
    else:                                     # projekt: zapisy poza folderem, chronione, inne programy, nieznane
        potrzebne = bool(zawsze or zwykle or a.inne or a.nieznane)
    if not potrzebne:
        return None
    if not zawsze and _hermes_dozwolone_na_stale(polecenie):
        return None       # właściciel dopuścił to polecenie na stałe w command_allowlist
    pokaz = _poczatek(polecenie)
    powody: List[str] = []
    if zawsze or zwykle:
        powody.append(_opis_powodow(zawsze + zwykle))
    if a.inne:
        powody.append("spoza listy tylko do odczytu: " + ", ".join(dict.fromkeys(a.inne[:4])))
    elif a.nieznane:
        powody.append("polecenie złożone, nie da się go sprawdzić")
    if not powody:
        powody.append("zapis")
    return _prosba("terminal", m, f"polecenie `{pokaz}` ({'; '.join(powody)})", polecenie.strip())


def _decyzja(tool_name: str, args: Dict[str, Any], task_id: str) -> Optional[Dict[str, str]]:
    yolo = _yolo()
    if yolo and _profil(_hermes_home()) == OPERATOR and not (tool_name in OPERATOR_PRZY_YOLO
                                                             or tool_name.startswith("kanban_")):
        return _blok("tryb pełny (YOLO) jest wyłączony dla jarvo-operator: Komputer Jarva działałby wtedy bez "
                     "ograniczeń. Uruchom czat bez --yolo albo wpisz /yolo, żeby je wyłączyć.")
    if tool_name not in OBSLUGIWANE:
        return None
    bez_czl = bez_czlowieka()
    tryb, _ = tryb_zgod()
    m = _miejsca(tryb, bez_czl, yolo and not bez_czl)
    if tool_name == "write_file":
        p = args.get("path")
        return _zapis_plikow(tool_name, [p] if isinstance(p, str) and p.strip() else [], m, task_id)
    if tool_name == "patch":
        return _zapis_plikow(tool_name, sciezki_latki(args), m, task_id)
    if tool_name == "terminal":
        return _terminal(args, m, task_id)
    if tool_name == "execute_code":
        if bez_czl:
            return _blok(f"execute_code to dowolny kod, a {KONTEKSTY.get(bez_czl, bez_czl)} działa bez człowieka. "
                         f"Użyj terminala albo narzędzi plików w dozwolonych katalogach. {_porada_bez_czlowieka(m)}")
        if _hermes_pyta_o_kod() and not yolo:
            return None
        kod = str(args.get("code") or "")
        return _prosba(tool_name, m, f"uruchomienie kodu Pythona (execute_code, {kod.count(chr(10)) + 1} linii)", kod)
    akcja = str(args.get("action") or "").strip().lower()
    if tool_name == "process_manage":
        if akcja in PROCESY_ODCZYT or bez_czl:
            return None
        cel = str(args.get("session_id") or "")
        return _prosba(tool_name, m, f"proces w tle: {akcja or '?'} {_pokaz(cel, 40)}".rstrip(),
                       f"{akcja}\n{cel}\n{args.get('data') or ''}")
    if tool_name == "cronjob_manage":
        if akcja in RUTYNY_ODCZYT:
            return None
        if bez_czl:
            return _blok(f"rutyny zakłada i zmienia człowiek, a {KONTEKSTY.get(bez_czl, bez_czl)} działa bez niego "
                         f"(cronjob_manage {akcja or '?'}). {_porada_bez_czlowieka(m)}")
        nazwa = str(args.get("name") or args.get("job_id") or args.get("schedule") or "")
        return _prosba(tool_name, m, f"rutyna (cron): {akcja or '?'} {_pokaz(nazwa, 60)}".rstrip(),
                       json.dumps(args, sort_keys=True, ensure_ascii=False, default=str))
    return None


def bez_czlowieka() -> Optional[str]:
    """Kto pracuje bez człowieka: podagent, kanban, cron, q, webhook, brak; None = człowiek może odpowiedzieć."""
    if _podagent():
        return "podagent"
    if os.environ.get("HERMES_KANBAN_TASK", "").strip():
        return "kanban"
    if _prawda(_env_sesji("HERMES_CRON_SESSION")):
        return "cron"
    if _prawda(_env_sesji("HERMES_SINGLE_QUERY_SESSION")):
        return "q"
    if _env_sesji("HERMES_SESSION_PLATFORM").strip().lower() in ("webhook", "msgraph_webhook"):
        return "webhook"
    if not _ktos_odpowie():
        return "brak"
    return None


def straznik_zgod(tool_name: str = "", args: Optional[Dict[str, Any]] = None, task_id: str = "", session_id: str = "",
                  **_kw: Any) -> Optional[Dict[str, str]]:
    """Hak pre_tool_call: None (dalej), {"action": "approve", "message", "rule_key"} albo {"action": "block", "message"}.
    Wyjątek = block (fail-closed, bez treści argumentów w komunikacie)."""
    try:
        wynik = _decyzja(str(tool_name or ""), args if isinstance(args, dict) else {}, str(task_id or ""))
        if wynik and wynik.get("action") == "approve" and bez_czlowieka():
            # bez człowieka Hermes odpowiedziałby BLOCKED od razu; nigdy nie zwracamy approve (sekcja d)
            return _blok("praca bez człowieka, a to wywołanie wymaga zgody. Zapisz wynik w katalogu karty, w skarbcu "
                         "albo w misjach albo zgłoś blokadę: kanban_block(kind=\"needs_input\").")
        return wynik
    except Exception as e:
        logger.warning("jarvo-zgody: błąd oceny %s (%s); blokuję", tool_name, type(e).__name__, exc_info=True)
        return _blok(f"wtyczka zgód nie mogła sprawdzić wywołania {str(tool_name)[:40]} (błąd {type(e).__name__}), "
                     "więc je zatrzymała. Spróbuj prościej (np. jawna ścieżka w folderze projektu) albo powiedz o tym "
                     "właścicielowi.")


# ------------------------------------------------------------------------------------------------ tryb i /tryb

def sciezka_stanu(home: Optional[Path] = None) -> Path:
    """Plik stanu profilu: <HERMES_HOME>/plugin-data/jarvo-zgody/stan.json (nie approvals.mode w config.yaml)."""
    return Path(home or _hermes_home()) / "plugin-data" / NAZWA / "stan.json"


def _tryb_z_pliku(home: Path) -> Optional[str]:
    p = sciezka_stanu(home)
    try:
        st = p.stat()
    except OSError:
        return None
    znak = (st.st_mtime_ns, st.st_size)
    with _ZAMEK:
        c = _STAN_CACHE.get(str(p))
        if c and c[0] == znak:
            return c[1]
    try:
        dane = json.loads(p.read_text(encoding="utf-8-sig"))
        t = dane.get("tryb") if isinstance(dane, dict) else None
        t = t if t in ("pytaj", "projekt") else None          # pełnego nie zapisujemy: działa tylko na sesję
    except (OSError, ValueError):
        t = None
    with _ZAMEK:
        _STAN_CACHE[str(p)] = (znak, t)
    return t


def _zapisz_tryb(home: Path, tryb: str) -> Path:
    p = sciezka_stanu(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f"{p.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps({"tryb": tryb, "zmieniono": time.strftime("%Y-%m-%dT%H:%M:%S"), "przez": "/tryb"},
                              ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    for proba in range(6):                    # Windows: plik czytany przez inny proces (WinError 5/32)
        try:
            os.replace(tmp, p)
            break
        except PermissionError:
            if proba == 5:
                raise
            time.sleep(0.05 * (proba + 1))
    return p


def tryb_zgod(home: Optional[Path] = None) -> Tuple[str, str]:
    """(tryb, źródło): /tryb w tym procesie > JARVO_TRYB_ZGOD > plik stanu profilu > domyślny „projekt”."""
    home = Path(home or _hermes_home())
    k = _klucz(str(home))
    with _ZAMEK:
        t = _TRYB_W_PROCESIE.get(k)
    if t:
        return t, "/tryb"
    t = _norm_tryb(_start()["tryb"])
    if t:
        if t == "pelny" and _profil(home) == OPERATOR:
            return "projekt", ZMIENNA_TRYBU
        return t, ZMIENNA_TRYBU
    t = _tryb_z_pliku(home)
    if t:
        return t, "plik"
    return DOMYSLNY_TRYB, "domyślny"


def _opis_stanu(home: Path) -> str:
    tryb, zrodlo = tryb_zgod(home)
    yolo = _yolo()
    folder = _folder_projektu(None)
    linie = [f"Tryb zgód: {'pełny' if tryb == 'pelny' else tryb} ({zrodlo}): {OPISY_TRYBOW[tryb]}."]
    if tryb == "pelny" and not yolo:
        linie.append("YOLO nie jest włączone, więc działa jak projekt (pełny włącza /yolo albo --yolo).")
    if yolo:
        linie.append("YOLO włączone: Hermes sam zatwierdza prośby; config.yaml i chronione miejsca nadal blokuję.")
    if folder:
        linie.append(f"Folder projektu: {_pokaz(folder)}")
    else:
        linie.append("Folder projektu: brak (start w katalogu domowym albo w korzeniu dysku), więc pytam o każdy zapis.")
    linie.append("Zmień: /tryb pytaj · /tryb projekt · /tryb pelny (= /yolo na tę sesję).")
    return "\n".join(linie)


def polecenie_tryb(raw_args: str = "") -> str:
    """/tryb [pytaj|projekt|pelny]: bez argumentu pokazuje stan, pytaj i projekt zapisuje w pliku profilu."""
    try:
        home = _hermes_home()
        arg = (raw_args or "").strip()
        if not arg or arg.lower() in ("status", "stan", "?"):
            return _opis_stanu(home)
        tryb = _norm_tryb(arg)
        if tryb in ("pytaj", "projekt"):
            _zapisz_tryb(home, tryb)
            with _ZAMEK:
                _TRYB_W_PROCESIE[_klucz(str(home))] = tryb
            dopisek = " Uwaga: YOLO jest włączone, więc Hermes nadal zatwierdza sam: wpisz /yolo, żeby je wyłączyć." \
                if _yolo() else ""
            return f"Tryb zgód: {tryb}: {OPISY_TRYBOW[tryb]}.{dopisek}"
        if tryb == "pelny":
            if _profil(home) == OPERATOR:
                return "Tryb pełny jest wyłączony dla jarvo-operator (Komputer Jarva działałby bez ograniczeń)."
            return ("Tryb pełny działa tylko na tę sesję i włącza go Hermes: wpisz /yolo albo uruchom "
                    "`jarvo chat --tryb pelny`. Wtyczka sama go nie włącza. Nawet wtedy config.yaml i chronione "
                    "miejsca zostają zablokowane.")
        return "Użycie: /tryb [pytaj|projekt|pelny]. Bez argumentu pokazuję bieżący tryb."
    except Exception as e:
        logger.warning("jarvo-zgody: /tryb: %s", e)
        return f"jarvo-zgody: nie udało się zmienić trybu ({type(e).__name__})."


# ------------------------------------------------------------------------------------------------ rejestracja

def register(ctx) -> None:
    """Hak pre_tool_call (bez niego wtyczka nie chroni, więc błąd rejestracji przerywa ładowanie) i polecenie /tryb."""
    _zamroz()
    ctx.register_hook("pre_tool_call", straznik_zgod)
    try:
        ctx.register_command("tryb", polecenie_tryb,
                             description="Tryb zgód Jarva: pytaj, projekt (domyślny) albo pelny (= /yolo na sesję)",
                             args_hint="[pytaj|projekt|pelny]")
    except Exception as e:
        logger.warning("jarvo-zgody: polecenie /tryb niezarejestrowane: %s", e)
