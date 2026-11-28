"""Wtyczka jarvo-zgody: tryby zgód jak w Claude Code dla natywnego Jarva (docs/NATYWNIE.md, sekcja (d); decyzja I08).

Bez kontenera terminal agenta działa z prawami właściciela, więc zgody są główną ochroną (NATYWNIE.md, zasada 9:
„kontrola, nie izolacja”). Hak `pre_tool_call` ocenia zapisy plików, terminal, execute_code, procesy w tle i rutyny;
polecenie `/tryb` zmienia tryb w sesji.

Tryby (wybór: `/tryb` w sesji > JARVO_TRYB_ZGOD z `jarvo chat --tryb` > plik stanu profilu > „auto”):
  pytaj    approve dla write_file i patch (także V4A z nagłówkami *** Update/Add/Delete/Move File), execute_code,
           process_manage i cronjob_manage (działania zmieniające) oraz terminala spoza listy poleceń tylko do odczytu;
  projekt  (I08) jak pytaj, ale bez pytania zapisy i proste polecenia plikowe (mkdir, touch, cp, mv, rm,
           rmdir, sed -i, tee, przekierowania > i >>), gdy rzeczywista ścieżka (po realpath) leży w folderze
           projektu (JARVO_FOLDER_PROJEKTU albo TERMINAL_CWD, czyli katalog startu czatu) albo w katalogu roboczym
           karty (HERMES_KANBAN_WORKSPACE); poza nimi approve;
  auto     (domyślny; decyzje właściciela 14.11 i 27.11: cała flota pyta tylko o płatności i zakupy) bez pytania
           zapisy, polecenia, execute_code, procesy i rutyny, także w chronionych miejscach; z człowiekiem jedyna
           prośba to płatność albo zakup (confirm na telefonie, terminal i execute_code, których strażnik smart Hermesa
           nie zatwierdził). To, o co Hermes zapytałby człowieka i czekał approvals.timeout (300 s), wtyczka
           rozstrzyga od razu: polecenie terminala i execute_code tym samym strażnikiem smart (APPROVE = zgoda w Hermesie
           dla wzorca, DENY albo brak oceny = block z radą), zapis ~/.ssh/config i pliku instrukcji przy włączonym
           security.protected_instruction_files = block z radą;
  pelny    tylko na sesję: proces czatu z --yolo albo /yolo, wtedy Hermes sam zatwierdza prośby wtyczki. Wtyczka
           nigdy nie włącza YOLO; pod YOLO blokuje w każdym profilu narzędzia ekranu i telefonu (computer_use,
           komputer, pulpit, mcp__phone__*), bo Komputer Jarva, pulpit i telefon działałyby wtedy bez człowieka.
Zawsze, w każdym trybie: zapis config.yaml Hermesa = block; zapis w kodzie floty (skills, plugins, hooks, scripts,
SOUL.md i mcp.json profili i hosta, <JARVO_ROOT>/program i build, kod Hermesa, Jarva i tej wtyczki) = block z radą
„zlecenie dla Claude Code w misjach/DLA-CLAUDE.md”, bez pytania (także bez człowieka i pod YOLO). W trybach pytaj
i projekt zgoda na AGENTS.md, CLAUDE.md, SOUL.md i chronione miejsca (.git, .vscode, .idea, .claude, .hermes,
.gitconfig, .bashrc, .zshrc, .npmrc, .mcp.json i podobne pliki startowe powłoki, reszta danych Jarva), a w treści
takiej prośby uwaga, że „Always” obejmie tylko ten sam plik albo to samo polecenie; w auto przechodzą. Pod YOLO
o chronione miejsca nie da się zapytać, więc wtyczka je blokuje.
Telefon (serwer MCP `phone` z PHONEUSE, `jarvo telefon on`): mcp__phone__act i mcp__phone__batch z confirm=true
(na wierzchu, w args albo w kroku batch) przechodzą bramkę needs_confirm telefonu, więc z człowiekiem to prośba
z treścią akcji (zgoda = „tak” dla tej jednej akcji, bez zapamiętania), bez człowieka i pod YOLO block. Reszta
narzędzi telefonu bez zdania wtyczki. Surowe adb do telefonu floty, które steruje ekranem albo go czyta (input,
uiautomator dump, screencap, am start, monkey), w każdym trybie = block z radą „narzędzie telefonu”, gdy profil ma ten
telefon w serwerze `phone`, a jego ciało PhoneUse odpowiada na /ping (pamięć 60 s, brak 15 s); bez ciała adb przechodzi.
Bez człowieka (karta kanbana, cron, -q, podagent delegate_task, webhook, sesja bez nikogo, kto odpowie na prośbę):
nigdy approve. Zapisy w katalogu karty, skarbcu (JARVO_KNOWLEDGE_DIR) i misjach (JARVO_MISSIONS_DIR) oraz to, co
tryb przepuszcza bez pytania w folderze projektu (projekt i pełny), idą dalej; reszta zapisów to block z poradą
(na karcie: kanban_block(kind="needs_input")). Polecenia, których celów nie da się ustalić, zostają polityce Hermesa
(approvals.cron_mode, single_query_mode: deny), bo terminal i tak uruchomi dowolny skrypt; wyjątek to kasowanie
rekurencyjne albo wymuszone (strażnik kasowania niżej).
Błąd w haku = block (nie przepuszczamy przy błędzie, odwrotnie niż strażnik jarvo-wiedza).
Strażnik kasowania (przed wszystkim innym, w każdym trybie, z człowiekiem, bez niego i pod YOLO, bez pytania i bez
omijania przez command_allowlist): block dla masowego kasowania i niszczenia danych. Chronione w całości (samo miejsce
i wszystko nad nim): katalog domowy, ~/dev, ~/strony, ~/jarvo-testy, każde repozytorium git (poza katalogami
tymczasowymi i kart), skarbiec, misje i katalogi robocze kart; w całości i w środku: ~/.ssh, ~/.config, ~/.phoneuse;
dane i kod Jarva (poza skarbcem, misjami, katalogami kart i HOME terminala) bez kasowania drzew i nadpisywania plików,
a pojedynczego pliku (rm, unlink, os.remove) poza tymi miejscami i katalogami roboczymi profili (cache, home,
workspace, plans, sandboxes, audio_cache, image_cache) też nie (27.11: `rm -f` pliku bazy w profilu Hackera).
Formy: rm -r/-f (każda kolejność flag, długie flagi, flagi po celach, owijki sudo/env/nice/timeout/xargs), find -delete
i -exec rm (bez zawężenia nazwą albo czasem), shutil.rmtree/os.removedirs/os.system/subprocess w python -c, heredocu,
here-stringu i execute_code, fs.rmSync/rimraf/rmtree w node/perl/ruby -e, bash -c, eval, $(…), rsync --delete,
git clean -f, git reset --hard i git push --force/-f/--mirror/+gałąź w chronionym repozytorium, truncate, dd of=,
mkfs/wipefs, `>`, tee i cp /dev/null na chroniony plik, write_file z pustą treścią, patch usuwający całą treść i V4A
`*** Delete File`. Rekurencyjne albo wymuszone kasowanie, którego celów nie da się ustalić (zmienna, $(…), xargs,
glob w nieznanym katalogu), też block. Wolno: sprzątanie katalogu karty i katalogów tymczasowych, wyniki budowania
w projekcie (node_modules, dist, .svelte-kit, __pycache__), podkatalogi i pojedyncze pliki w drzewie roboczym,
zawężone find. Blokada idzie do logu (logger.warning) i ma w treści poradę, co zrobić zamiast.
Strażnik pracowników kart (razem ze strażnikiem kasowania, w każdym trybie): block dla kill, pkill i killall (także
spod owijek, w bash -c, $(…), xargs, python -c i execute_code z os.kill), które trafiają w pracownika karty kanbana
(`… chat -q work kanban task <karta>` albo HERMES_KANBAN_TASK w otoczeniu procesu), w proces Hermesa tej wtyczki albo
we wszystkie procesy (kill -1), oraz dla celu, w którego treści widać kanban, hermes, numer karty albo $PPID. Rada:
kartę zatrzymuje kanban_block albo kanban_complete, bo zabitego pracownika dyspozytor uruchamia od nowa.
Przypisanie decyzji właścicielowi (w każdym trybie): tekst narzędzi kanbana (komentarz, powód blokady, podsumowanie,
treść karty) i zapis w misjach albo skarbcu z „decyzja właściciela”, „właściciel zdecydował” i podobnymi bez cytatu
jego słów („…”) i godziny albo daty obok = block z radą: cytat z czasem albo „decyzja Jarva”.
Strażnik nagrywania ekranu (w każdym trybie, z człowiekiem, bez niego i pod YOLO): surowe `ffmpeg -f x11grab`
(gdigrab, avfoundation, kmsgrab) i programy nagrywające pulpit w terminalu, procesie w tle i execute_code = block
z radą: nagraj.py ze skilla praca-na-ekranie (krótkie odcinki udanych kroków; 16.11 ~20 min nagrania pętli błędów).
Strażnik rutyn (w każdym trybie, z człowiekiem, bez niego i pod YOLO): cronjob_manage `run` (przebieg na próbę trafia do
Aktualizacji właściciela) oraz `create` rutyny próbnej (test, próba w nazwie) albo o nazwie już istniejącej w profilu
(także wstrzymanej) = block z radą: sprawdź prompt i skrypty w rozmowie, istniejącą rutynę popraw albo wznów.

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
  - Czego nie dublujemy w trybach pytaj i projekt (nie pytać dwa razy): niebezpieczne polecenia terminala pyta sam Hermes
    (tools/approval_detection.py:180 detect_hardline_command, :1516 detect_dangerous_command; tools/approval_floors.py
    :23 approvals.deny, :188 command_allowlist z dokładnym tekstem albo wzorcem); AGENTS.md, CLAUDE.md, SOUL.md,
    .cursorrules i <projekt>/.hermes/* przez write_file/patch pyta zawsze, także pod YOLO, poza HERMES_HOME
    (tools/file_tools_write_guards.py:171-247, 329-339); config.yaml i ścieżki systemowe blokuje
    (tools/file_tools_write_guards.py:145-168); klucze i HERMES_WRITE_SAFE_ROOT odrzuca (agent/file_safety.py:176-297);
    execute_code pyta sam tylko w bramie i przez HERMES_EXEC_ASK (tools/approval.py:1233-1300). W trybie auto to samo
    rozstrzyga od razu _bez_czekania: strażnik smart (tools/approval_smart.py:134), zgoda approve_session
    (tools/approval.py:249) albo block; bez tego DENY i ESCALATE strażnika smart czekały na człowieka (approval.py:761-790,
    852-892), a prośba wtyczki (request_tool_approval, :1095-1120, _ACTION_GATE :745-758) do approvals.timeout.
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
import ast
import collections
import contextvars
import glob as _glob
import hashlib
import itertools
import json
import logging
import ntpath
import os
import re
import shlex
import sys
import tempfile
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)
_HERE = Path(__file__).resolve().parent

NAZWA = "jarvo-zgody"
TRYBY = ("pytaj", "projekt", "auto", "pelny")
# decyzja właściciela 14.11 („czemu aż tyle rzeczy muszę approvować, ma być auto all”; 11.11: Jarvo z pełnym dostępem,
# „safe” = strażniki): w trybie auto nic nie pyta poza chronionymi miejscami i płatnością na telefonie. Było „projekt”
# (I08): 14.11 dziesięć próśb o terminal w 9 min przy jednym zadaniu, „zawsze” pamięta tylko to jedno polecenie.
DOMYSLNY_TRYB = "auto"
ZMIENNA_TRYBU = "JARVO_TRYB_ZGOD"          # ustawia `jarvo chat --tryb` (etap E4)
ZMIENNA_FOLDERU = "JARVO_FOLDER_PROJEKTU"  # katalog startu czatu, gdy launcher go zna

WINDOWS = os.name == "nt"
MACOS = sys.platform == "darwin"

OBSLUGIWANE = frozenset({"write_file", "patch", "terminal", "execute_code", "process_manage", "cronjob_manage"})
PROCESY_ODCZYT = frozenset({"list", "poll", "log", "wait"})      # process_manage: tylko podgląd
RUTYNY_ODCZYT = frozenset({"list"})                              # cronjob_manage: tylko podgląd
# pod YOLO w każdym profilu: narzędzia ekranu i telefonu block (I08, docs/NATYWNIE.md F09), reszta jak w trybie pełnym;
# ekran i telefon ma Jarvo i agent biznesowy z przydziałem (fleet.yaml `komputer: true`, `jarvo telefon przydziel`),
# więc blokada nie zależy od profilu: nowy agent z ekranem albo telefonem nie wypada spod niej
NARZEDZIA_EKRANU = frozenset({"computer_use", "komputer", "pulpit"})
# telefon przez PHONEUSE (jarvo telefon on, serwer MCP `phone`): act i batch z confirm=true przechodzą bramkę
# needs_confirm telefonu, więc confirm daje tylko „tak” człowieka dla tej jednej akcji
TELEFON = "phone"
TELEFON_POTWIERDZENIA = frozenset({f"mcp__{TELEFON}__act", f"mcp__{TELEFON}__batch"})
_NIE = frozenset({"", "false", "0", "no", "off", "none", "null", "nie"})
# tryb auto: confirm na telefonie przechodzi bez pytania, chyba że cel wygląda na płatność albo usunięcie konta; ten sam
# wzór rozstrzyga terminal i execute_code, których strażnik smart Hermesa nie zatwierdził (_bez_czekania)
PLATNOSC = re.compile(
    r"(?i)(?<!\w)(?:kup(?:uj[eę])?|zap[lł]a[cć]|p[lł]ac[eę]|p[lł]atno[sś][cć]|zam[oó]w(?:ienie)?|zamawiam|blik|"
    r"przelew|do[lł]aduj|subskrybuj|wykup|buy|purchase|pay|check ?out|place (?:your )?order|subscribe|top ?up|"
    r"usu[nń] konto|delete (?:my )?account|zamknij konto|close (?:my )?account)(?!\w)")

# pytamy w trybach pytaj i projekt, w auto przechodzą (niszczenie blokuje strażnik kasowania), pod YOLO blokujemy:
# katalogi z ustawieniami, które wykonują kod albo sterują agentem
CHRONIONE_KATALOGI = frozenset({".git", ".vscode", ".idea", ".claude", ".hermes"})
CHRONIONE_PLIKI = frozenset({".gitconfig", ".bashrc", ".zshrc", ".npmrc", ".mcp.json", ".bash_profile", ".bash_login",
                             ".profile", ".zprofile", ".zshenv", ".zlogin", ".envrc"})
PLIKI_INSTRUKCJI = frozenset({"agents.md", "claude.md", "soul.md", ".cursorrules"})
NAZWA_KONFIGU = "config.yaml"
# katalogi robocze Hermesa w każdym profilu i w hoście (brudnopis cache/scratch, HOME terminala, plany, piaskownice):
# zwykła praca, nie „dane Jarva”. 14.11 właściciel klikał zgody na cache/scratch/gpu_audyt.py („no limits, tylko
# security, nie normalna praca”); pytamy dalej o config, sekrety, bazy i pamięć, a kod floty blokujemy (niżej).
ROBOCZE_PROFILU = ("cache", "home", "workspace", "plans", "sandboxes", "audio_cache", "image_cache")
# kod floty w każdym profilu i w hoście: buduje go repo JARVO (build.py, skan skilli) i podmienia przy aktualizacji.
# 14.11 21:21–21:26 Jarvo wgrał ręcznie skill do jarvo-web (cp, write_file, patch), a właściciel osiem razy klikał
# „Always”, które obejmuje tylko ten sam plik albo to samo polecenie. Zapis tu = block z radą, bez prośby do właściciela.
KOD_FLOTY_PROFILU = (("skills", "zainstalowane skille"), ("plugins", "wtyczki"), ("hooks", "haki bramy"),
                     ("scripts", "skrypty floty"), ("SOUL.md", "instrukcja agenta"), ("mcp.json", "serwery MCP"))
ZLECENIE_FLOTY = "DLA-CLAUDE.md"           # zlecenia dla Claude Code w katalogu misji (SOUL Jarva, zasada 8)
KOD_FLOTY = "kod floty"
# Decyzja właściciela 27.11 (ostateczna): cała flota pyta o zgodę tylko przy płatnościach i zakupach. 27.11 05:15:45
# i 05:21:36 Hacker w panelu czekał dwa razy po 300 s na zgodę (prośba tej wtyczki o `rm -f` pliku w danych Jarva).
# W trybie auto z człowiekiem nic nie czeka na przycisk zgody poza płatnością: niszczenie blokuje strażnik kasowania,
# a to, o co Hermes zapytałby sam, wtyczka rozstrzyga od razu (_bez_czekania niżej).
HERMES_CZEKA = "zapis, o który Hermes pyta człowieka"
SMART_LIMIT_S = 20.0               # ocena strażnika smart w haku; hak dłuższy niż 30 s Hermes blokuje i wycisza na 60 s

# Nagrywanie ekranu tylko przez nagraj.py ze skilla praca-na-ekranie (krótkie odcinki udanych kroków, koniec przy
# pierwszej odmowie Komputera albo bez ruchu, film tylko z udanych kroków). 16.11 Jarvo nagrywał surowym
# `ffmpeg -f x11grab` pulpit przez ~20 min: w kółko tę samą nieudaną weryfikację, gdy sam pracował już na telefonie.
# Blokada w każdym trybie, z człowiekiem, bez niego i pod YOLO (terminal, proces w tle, execute_code).
NAGRYWANIE_EKRANU = re.compile(
    r"\b(?:ffmpeg|avconv)(?:\.exe)?\b.*?-f[\s\"',]*(?:x11grab|gdigrab|avfoundation|kmsgrab|fbdev)\b|"
    r"\b(?:ddagrab|ximagesrc|wf-recorder|recordmydesktop|byzanz-record|simplescreenrecorder|vokoscreen(?:ng)?|"
    r"kazam)\b", re.I | re.S)
NAGRAJ = "$HERMES_HOME/skills/ekran/praca-na-ekranie/scripts/nagraj.py"

KONTEKSTY = {"kanban": "karta kanbana", "cron": "rutyna (cron)", "q": "jednorazowe zapytanie (-q)",
             "podagent": "podagent (delegate_task)", "webhook": "webhook", "brak": "sesja bez człowieka"}
OPISY_TRYBOW = {
    "pytaj": "pytam o każdy zapis, polecenie spoza listy tylko do odczytu, execute_code, procesy w tle i rutyny",
    "projekt": "zapisy i proste polecenia plikowe w folderze projektu bez pytania, poza nim pytam",
    "auto": "bez pytania: polecenia, zapisy, kod, procesy i rutyny, także w chronionych miejscach; pytam tylko o "
            "płatność albo zakup; masowe kasowanie, usuwanie danych Jarva, config.yaml i kod floty blokuję od razu, "
            "a to, o co Hermes zapytałby człowieka, rozstrzygam od razu jego strażnikiem smart",
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


def _hermes_pyta_o_zapis(sciezka: str) -> bool:
    """Czy write_file/patch tej ścieżki zatrzyma bramka zgód plików Hermesa (~/.ssh/config, agent/file_safety.py
    build_write_approval_paths, tools/file_tools_write_guards.py _check_approval_required_write)."""
    try:
        from agent.file_safety import is_write_approval_required
        return bool(is_write_approval_required(sciezka))
    except Exception:
        return False


def _hermes_pyta_o_kod() -> bool:
    """execute_code: Hermes pyta o cały skrypt sam w bramie i przy HERMES_EXEC_ASK (tools/approval.py:1273-1279)."""
    try:
        from tools.approval_context import _is_gateway_approval_context
        return bool(_is_gateway_approval_context() or _prawda(os.environ.get("HERMES_EXEC_ASK")))
    except Exception:
        return _prawda(os.environ.get("HERMES_EXEC_ASK"))


# zgody strażnika smart wydane przez wtyczkę w Hermesie: (klucz sesji, klucz wzorca). Hermes pamięta zgodę dla całej
# sesji i wzorca, więc każde następne wywołanie z tym wzorcem wtyczka ocenia od nowa (_hermes_zapyta niżej).
_PRZEPUSZCZONE: "collections.OrderedDict[Tuple[str, str], None]" = collections.OrderedDict()


def _hermes_zapyta(narzedzie: str, tresc: str) -> Optional[Tuple[str, str, str]]:
    """(klucz sesji, klucz wzorca, opis), gdy Hermes w trybie smart da to wywołanie strażnikowi smart, a przy jego DENY
    albo ESCALATE człowiekowi na approvals.timeout (tools/approval.py:1159-1224 terminal, :1233-1300 execute_code,
    :761-790 _smart_gate, :852-892 czekanie w bramie i w HQ przez /v1/runs); None, gdy Hermes rozstrzygnie sam od razu
    (twarda blokada, approvals.deny, YOLO, tryb off albo manual, command_allowlist, zgoda człowieka w sesji, praca bez
    człowieka, execute_code na platformie bez człowieka, np. api_server)."""
    try:
        from tools import approval as ap
        from tools.approval_context import _get_approval_mode
        from tools.approval_detection import detect_dangerous_command, detect_hardline_command
        from tools.approval_floors import _command_matches_permanent_allowlist, _match_user_deny_rule
        if _get_approval_mode() != "smart" or ap._yolo_active():
            return None
        _, cli, brama, pyta = ap._presence()
        if narzedzie == "execute_code":
            if ap._unattended_contexts() or not (brama or pyta):
                return None
            klucz, opis = "execute_code", ap._EXECUTE_CODE_DESCRIPTION
        else:
            if not (cli or brama or pyta) or detect_hardline_command(tresc)[0] or _match_user_deny_rule(tresc) \
                    or _command_matches_permanent_allowlist(tresc):
                return None
            groznie, klucz, opis = detect_dangerous_command(tresc)
            if not groznie:
                return None
        sesja = ap.get_current_session_key()
        with _ZAMEK:
            nasza = (sesja, klucz) in _PRZEPUSZCZONE
        if ap.is_approved(sesja, klucz) and not nasza:
            return None
        return sesja, klucz, opis
    except Exception:
        logger.debug("jarvo-zgody: nie ustaliłem, czy Hermes zapyta o %s", narzedzie, exc_info=True)
        return None


def _smart_werdykt(tresc: str, opis: str, klucz: str, sesja: str) -> str:
    """Werdykt strażnika smart Hermesa: approve, deny albo escalate (ten sam model i approvals.smart_policy profilu,
    tools/approval_smart.py:134 _smart_verdict); „brak”, gdy nie odpowie w SMART_LIMIT_S albo go nie ma."""
    try:
        from tools.approval_smart import _smart_verdict
    except Exception:
        return "brak"
    wynik: Dict[str, str] = {}
    gotowe = threading.Event()
    kontekst = contextvars.copy_context()

    def ocen() -> None:
        try:
            wynik["werdykt"] = kontekst.run(_smart_verdict, tresc, opis, klucz, [klucz], sesja)
        except Exception:
            logger.debug("jarvo-zgody: strażnik smart zawiódł", exc_info=True)
        finally:
            gotowe.set()

    threading.Thread(target=ocen, name="jarvo-zgody-smart", daemon=True).start()
    if not gotowe.wait(SMART_LIMIT_S):
        return "brak"
    return str(wynik.get("werdykt") or "brak")


def _hermes_przepusc(sesja: str, klucz: str) -> None:
    """Zgoda w Hermesie dla wzorca w tej sesji (tools/approval.py:249 approve_session), żeby bramka nie pytała."""
    from tools.approval import approve_session
    approve_session(sesja, klucz)
    with _ZAMEK:
        _PRZEPUSZCZONE[(sesja, klucz)] = None
        _PRZEPUSZCZONE.move_to_end((sesja, klucz))
        while len(_PRZEPUSZCZONE) > 512:
            _PRZEPUSZCZONE.popitem(last=False)


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
    flota: List[Tuple[str, str]] = field(default_factory=list)   # (klucz, opis): kod floty, zapis = block z radą
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
    m = _Miejsca(tryb=tryb if tryb in ("pytaj", "auto") else "projekt", bez_czl=bez_czl, yolo=yolo, profil=_profil(home))
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
    profile = [root, home, *(p for p in (root / "profiles").glob("*") if p.is_dir())] if (root / "profiles").is_dir() \
        else [root, home]
    m.robocze += [k for d in dict.fromkeys(profile) for n in ROBOCZE_PROFILU if (k := _k_realny(d / n))]
    # kod floty: zawsze block z radą (zlecenie dla Claude Code), bez pytania właściciela i bez zgody „zawsze”
    jarvo_root = Path(os.environ["JARVO_ROOT"]) if os.environ.get("JARVO_ROOT") else \
        (root.parent if root.name.lower() == "dane" else None)               # <root>/dane, <root>/program (sciezki.py)
    flota = [(d / n, opis) for d in dict.fromkeys(profile) for n, opis in KOD_FLOTY_PROFILU]
    flota += [(jarvo_root / n, "program Jarva") for n in ("program", "build")] if jarvo_root else []
    flota += [(os.environ.get("HERMES_SRC"), "kod Hermesa"), (os.environ.get("JARVO_REPO"), "kod Jarva"),
              (_HERE, "kod wtyczki zgód")]
    m.flota = list({k: opis for p, opis in flota if (k := _k_realny(p))}.items())
    # reszta danych i kodu Jarva: zawsze pytamy (stan zgód, sekrety, sesje, pamięć)
    m.dane = [k for k in (_k_realny(home), _k_realny(root), _k_realny(os.environ.get("JARVO_ROOT")),
                          _k_realny(os.environ.get("HERMES_SRC")), _k_realny(os.environ.get("JARVO_REPO")),
                          _k_realny(_HERE)) if k]
    if bez_czl:
        m.dozwolone = [k for k in (m.karta_k, wiedza_k, misje_k) if k]
        if m.tryb != "pytaj" and m.folder_k:   # to, co tryb przepuszcza bez pytania, przechodzi też bez człowieka
            m.dozwolone.append(m.folder_k)
    else:
        # z człowiekiem: tryb projekt nie pyta też o skarbiec i misje (dziennik Jarva). Bez tego czat w HQ pytał
        # o każdy MISSION.md i INDEX.md, a odmowa albo brak odpowiedzi gubiły dziennik (26.10: 6 próśb w 96 s).
        # Tryb pytaj dalej pyta o każdy zapis (sprawdzany przed `korzen` w _ocen_sciezke).
        m.dozwolone = [k for k in (m.folder_k, m.karta_k, wiedza_k, misje_k) if k]
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
    flota = next((opis for r, opis in m.flota if _wewnatrz(k, r)), None)
    if flota:
        return _Werdykt("blokuj", pokaz, f"{KOD_FLOTY}: {flota}", zawsze=True)
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
        czeka = ((skl and skl[-1] in PLIKI_INSTRUKCJI and _hermes_pyta_o_instrukcje(surowa or realna, task_id))
                 or _hermes_pyta_o_zapis(realna))
        if czeka:          # Hermes zapyta sam (pliki instrukcji przy security.protected_instruction_files, ~/.ssh/config)
            if m.tryb == "auto":                      # auto nie czeka na człowieka: od razu blokada z radą
                return _Werdykt("blokuj", pokaz, HERMES_CZEKA)
            return _Werdykt("hermes", pokaz, "zapis z prośbą Hermesa")
        if _hermes_odmowi_zapisu(realna):
            return _Werdykt("hermes", pokaz, "zapis odrzuca Hermes")
    if chronione:
        if m.tryb == "auto" and not m.yolo:   # decyzja 27.11: pytamy tylko o płatności; niszczenie łapie strażnik kasowania
            return _Werdykt("ok", pokaz)
        return _Werdykt("blokuj" if m.yolo else "pytaj", pokaz, f"chronione: {chronione}", zawsze=True)
    if m.tryb == "pytaj":
        return _Werdykt("pytaj", pokaz, "zapis")
    if m.tryb == "auto":                      # auto: każdy zapis poza chronionymi miejscami bez pytania
        return _Werdykt("ok", pokaz)
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
    heredoki: List[str] = field(default_factory=list)   # treść heredoców (dane; strażnik kasowania czyta kod w nich)


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
    """Polecenie powłoki → (proste polecenia, złożone). Treść heredoców to dane: nie rozbieramy jej, tylko zapisujemy
    przy poleceniu (`heredoki`), bo dla python3 albo bash to kod."""
    polecenia: List[_Polecenie] = []
    stan: Dict[str, Any] = {"biez": _Polecenie(), "czesci": [], "w_slowie": False, "oczekuje": None, "zlozone": False}
    heredoki: List[Tuple[str, bool, bool, _Polecenie]] = []
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
                heredoki.append((slowo.surowe(), op == "<<-", cytowany, stan["biez"]))
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
        for ogr, bez_tabow, cytowany, wlasciciel in heredoki:
            linie: List[str] = []
            while i < n:
                j = tekst.find("\n", i)
                linia = (tekst[i:] if j < 0 else tekst[i:j]).rstrip("\r")
                i = n if j < 0 else j + 1
                if (linia.lstrip("\t") if bez_tabow else linia) == ogr:
                    break
                linie.append(linia.lstrip("\t") if bez_tabow else linia)
                if not cytowany and ("$(" in linia or "`" in linia):
                    stan["zlozone"] = True
            wlasciciel.heredoki.append("\n".join(linie))
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


def _dom_powloki(dom: str) -> str:
    """HOME tak, jak widzi go Git Bash: C:\\Users\\x → /c/Users/x, \\\\serwer\\u → //serwer/u. Bez tego tekst po
    rozwinięciu $HOME albo ~ w `sh -c "…"` czy `eval` zgubiłby ukośniki odwrotne przy drugim czytaniu przez powłokę."""
    if not WINDOWS:
        return dom
    s = dom.replace("\\", "/")
    m = re.match(r"^([A-Za-z]):(/.*)?$", s)
    return f"/{m.group(1).lower()}{(m.group(2) or '').rstrip('/')}" if m else s


def _wartosc(nazwa: str, zmienne: Dict[str, Optional[str]], dom: str) -> Optional[str]:
    if nazwa in zmienne:
        return zmienne[nazwa]
    if nazwa == "HOME":
        return _dom_powloki(dom)
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
                    t = _dom_powloki(dom) + ("" if koniec < 0 else t[koniec:])
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


def _analizuj_terminal(polecenie: str, cwd0: Optional[str], dom: str, kasowania: Optional[List["_Kasowanie"]] = None,
                       glebokosc: int = 0) -> _Analiza:
    """Cele zapisu, programy spoza listy tylko do odczytu i to, czego nie da się ocenić; cwd idzie za `cd`.
    `kasowania`: lista, do której strażnik kasowania zbiera usunięcia i nadpisania (także z $(…), bash -c, python -c
    i heredoców); `glebokosc` liczy te zagnieżdżenia."""
    a = _Analiza()
    if len(polecenie) > _MAX_POLECENIA:
        a.nieznane, a.tylko_odczyt = True, False
        if kasowania is not None:
            _kasowanie_nierozebrane(polecenie, "polecenie za długie, żeby je rozebrać", kasowania)
        return a
    try:
        polecenia, zlozone = _rozbierz(polecenie)
    except _Skladnia as e:
        a.nieznane, a.tylko_odczyt = True, False
        if kasowania is not None:
            _kasowanie_nierozebrane(polecenie, f"polecenia nie da się rozebrać ({e})", kasowania)
        return a
    a.nieznane = zlozone
    cwd: Optional[str] = cwd0
    zmienne: Dict[str, Optional[str]] = {"PWD": cwd0}
    w_potoku = False
    for p in polecenia:
        if kasowania is not None:
            _kasowania_podstawien(p, cwd, dom, kasowania, glebokosc)
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
                if kasowania is not None:
                    _kasowania_polecenia(prog, argi, p, cwd, dom, kasowania, glebokosc)
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
            if kasowania is not None and op in _NADPISUJACE:
                for x in _argumenty(cel, zmienne, dom):
                    _dodaj_cel(kasowania, x, cwd, dom, f"przekierowanie {op}", "oproznij",
                               pusto=_bez_tresci(slowa, zmienne, dom))
            cele += _argumenty(cel, zmienne, dom)
        zapisy = [(cel.pokaz, _sciezki_arg(cel, cwd, dom)) for cel in cele]
        zapisy = [(pokaz, s) for pokaz, s in zapisy if s != []]      # /dev/null, '' to nie zapis
        if rodzaj not in ("odczyt", "cd", "stan", "pusty") or zapisy:
            a.tylko_odczyt = False
        a.cele += zapisy
        w_potoku = p.lacznik in ("|", "|&")
    if a.nieznane:
        a.tylko_odczyt = False
    if kasowania is not None:
        _zabijanie_z_potoku(polecenie, kasowania)
    return a


# ------------------------------------------------------------------------------------------------ strażnik kasowania
# Masowe kasowanie i niszczenie danych blokujemy w każdym trybie: z człowiekiem (pytaj, projekt), bez niego (karta,
# cron, -q, podagent) i pod YOLO, przed resztą oceny, bez pytania i bez omijania przez command_allowlist albo zgodę
# „zawsze”. Hermes łapie sam tylko część form (tools/approval_detection.py: detect_dangerous_command pyta o rm -r,
# find -delete, git reset --hard bez -C, git clean -f, git push --force, python -c; twarda blokada detect_hardline_command
# tylko dla /, katalogów systemowych, samego ~ i mkfs), a pod YOLO, przy approvals.mode: off, po zgodzie „zawsze” albo
# zgodzie strażnika smart przepuszcza je bez człowieka. rsync --delete, truncate, git push --mirror, git -C … reset
# --hard i unlink nie są dla Hermesa groźne wcale.

_NADPISUJACE = frozenset({">", ">|", "&>", ">&"})
# katalogi, w których nie szukamy zagnieżdżonych repozytoriów git (wyniki budowania i zależności: duże, odtwarzalne)
_WYNIKI_BUDOWANIA = frozenset({"node_modules", "dist", "build", ".svelte-kit", "__pycache__", ".next", ".nuxt",
                               ".turbo", ".parcel-cache", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
                               ".nox", "coverage", "htmlcov", "target", ".gradle", ".venv", "venv", ".cache"})
_SKAN_KATALOGOW = 3000            # ile katalogów najwyżej przeglądamy, szukając repozytorium w kasowanym drzewie
_SKAN_GLEBOKOSC = 4
_MAX_ZAGNIEZDZEN = 4              # $(…), bash -c, python -c z os.system… w sobie
_POWLOKI = frozenset({"sh", "bash", "zsh", "dash", "ksh", "ash", "mksh", "yash"})
_PYTHON = re.compile(r"^(?:python|pypy|py)(?:\d+(?:\.\d+)*)?w?$")
_INNE_JEZYKI = {"node": ("-e", "--eval", "-p", "--print"), "bun": ("-e", "--eval", "-p", "--print"),
                "deno": ("eval",), "perl": ("-e", "-E"), "ruby": ("-e",), "php": ("-r",)}
_KASUJACE_PROGRAMY = frozenset({"rm", "shred", "unlink"})
_FORMATUJACE = re.compile(r"^(?:mkfs(?:\..+)?|mke2fs|mkswap|wipefs|blkdiscard|mkntfs|mkdosfs|newfs(?:_.+)?)$")
# owijki, pod którymi działa inny program: (krótkie opcje z wartością, długie opcje z wartością, ile pozycyjnych
# argumentów owijki przed programem)
_OWIJKI: Dict[str, Tuple[str, Tuple[str, ...], int]] = {
    "sudo": ("ugCDhprtUT", ("--user", "--group", "--chdir", "--host", "--prompt", "--role", "--type", "--other-user",
                            "--close-from", "--command-timeout"), 0),
    "doas": ("uC", (), 0), "env": ("uCS", ("--unset", "--chdir", "--split-string"), 0),
    "nice": ("n", ("--adjustment",), 0), "ionice": ("cnpPu", ("--class", "--classdata", "--pid", "--pgid", "--uid"), 0),
    "nohup": ("", (), 0), "time": ("fo", ("--format", "--output"), 0), "exec": ("a", (), 0), "builtin": ("", (), 0),
    "command": ("", (), 0), "stdbuf": ("ioe", ("--input", "--output", "--error"), 0), "setsid": ("", (), 0),
    "chronic": ("", (), 0), "unbuffer": ("", (), 0), "busybox": ("", (), 0), "catchsegv": ("", (), 0),
    "timeout": ("sk", ("--signal", "--kill-after"), 1), "flock": ("wE", ("--timeout", "--conflict-exit-code"), 1),
    "taskset": ("", (), 1), "chrt": ("", (), 1),
    "xargs": ("adEILnPs", ("--arg-file", "--delimiter", "--eof", "--replace", "--max-lines", "--max-args",
                           "--max-procs", "--max-chars", "--process-slot-var"), 0),
}
_URUCHAMIACZE = frozenset({"uv", "poetry", "pipenv", "pdm", "rye", "hatch"})       # `uv run python -c …`
_URUCHAMIACZE_Z_WARTOSCIA = frozenset({"--with", "--python", "-p", "--directory", "--project", "--package", "--extra",
                                       "--group", "--env-file", "--index", "-e", "--env"})
_FIND_NAZWY = frozenset({"-name", "-iname", "-path", "-ipath", "-wholename", "-iwholename", "-regex", "-iregex",
                         "-lname", "-ilname"})
_FIND_FILTRY = frozenset({"-newer", "-anewer", "-cnewer", "-mtime", "-mmin", "-atime", "-amin", "-ctime", "-cmin",
                          "-size", "-user", "-group", "-uid", "-gid", "-perm", "-links", "-inum", "-samefile", "-used",
                          "-newermt", "-newerct", "-newerat", "-fstype"})
_FIND_FILTRY_BEZ_WARTOSCI = frozenset({"-empty", "-nouser", "-nogroup", "-executable", "-readable", "-writable"})
_FIND_Z_WARTOSCIA = frozenset({"-maxdepth", "-mindepth", "-type", "-xtype", "-printf", "-fprint", "-fprintf",
                               "-fprint0", "-fls", "-regextype", "-D"})
_RSYNC_Z_WARTOSCIA = frozenset({
    "-e", "--rsh", "--rsync-path", "--exclude", "--include", "--filter", "-f", "--files-from", "--exclude-from",
    "--include-from", "--link-dest", "--compare-dest", "--copy-dest", "--backup-dir", "--suffix", "--chmod", "--chown",
    "--usermap", "--groupmap", "--log-file", "--log-file-format", "--partial-dir", "--temp-dir", "-T", "--timeout",
    "--contimeout", "--port", "--password-file", "--bwlimit", "--max-size", "--min-size", "--max-delete",
    "--out-format", "--info", "--debug", "-B", "--block-size", "-M", "--remote-option", "--iconv", "--checksum-choice",
    "--compress-choice", "--compress-level", "--skip-compress", "--modify-window", "--sockopts", "--outbuf",
    "--stop-after", "--stop-at", "--write-batch", "--only-write-batch", "--read-batch", "--protocol", "--address",
    "--checksum-seed", "--copy-as", "--early-input"})
# słowa, po których w poleceniu, którego nie umiemy rozebrać, widać kasowanie
_KASUJACE_RE = re.compile(
    r"(?<![\w.-])(?:rm|shred|unlink|truncate|wipefs|mkfs(?:\.\w+)?|rmtree|removedirs|rm_rf|rmSync)(?![\w-])"
    r"|(?<![\w-])-delete\b|--del(?:ete)?\b|\bgit\b[^\n]*?\b(?:clean|reset|push)\b|\bdd\b[^\n]*?\bof=")
_OBCE_KASOWANIE = re.compile(
    r"(?:\.(?:rmSync|rmdirSync|rm|rmdir)\b|\brimraf(?:\.sync)?|\bFileUtils\.(?:rm_rf|rm_r|remove_dir|"
    r"remove_entry(?:_secure)?)|\brmtree|\bremove_tree|\bDeno\.remove)\s*\(?\s*(?:(['\"])([^'\"\n]*)\1)?")
_PY_SCIEZKI = frozenset({"Path", "PurePath", "PosixPath", "WindowsPath", "PurePosixPath", "PureWindowsPath", "fspath",
                         "str", "abspath", "realpath", "normpath", "expanduser", "join"})
_PY_METODY = frozenset({"expanduser", "resolve", "absolute", "as_posix", "__fspath__", "__str__"})
_PY_POWLOKA = frozenset({"system", "popen", "run", "call", "check_call", "check_output", "Popen", "getoutput",
                         "getstatusoutput"})


@dataclass
class _Kasowanie:
    """Jedno usunięcie albo nadpisanie znalezione w poleceniu, kodzie albo zapisie pliku; także zabicie pracownika
    karty (rodzaj `zabij`: strażnik pracowników kart) albo `xargs kill` o celach z potoku (`zabij_xargs`)."""
    forma: str                       # jak kasuje (do komunikatu): rm -rf, find -delete, rmtree (Python), git clean…
    rodzaj: str                      # usun | zawartosc | filtr | plik | oproznij | repo | urzadzenie | xargs | zabij…
    sciezki: Optional[List[str]]     # rzeczywiste ścieżki; None = nie wiadomo (zmienna, $(…), nieznany katalog)
    pokaz: str                       # argument do komunikatu
    rekurencyjne: bool = False
    wymuszone: bool = False
    pusto: bool = False              # oproznij: po zmianie plik na pewno jest pusty
    uwaga: str = ""                  # powód, gdy celu nie da się ustalić (zabij: powód blokady)
    karta: str = ""                  # zabij: karta kanbana zabijanego pracownika, gdy wiadomo


@dataclass
class _Krytyczne:
    """Miejsca, których nie wolno skasować hurtem (klucze do porównań + opis do komunikatu)."""
    cale: List[Tuple[str, str]]       # chronione w całości: samo miejsce i wszystko nad nim
    wnetrze: List[Tuple[str, str]]    # chronione całe i w środku: także pojedyncze pliki
    jarvo: List[Tuple[str, str]]      # dane i kod Jarva: w środku bez kasowania drzew i nadpisywania plików
    robocze: List[str]                # wyjątki w danych Jarva: skarbiec, misje, katalogi kart, HOME terminala
    jednorazowe: List[str]            # katalogi tymczasowe i kart: repozytoria git w nich nie są chronione
    konfig_k: Optional[str] = None
    # pojedynczy plik w danych Jarva wolno usunąć tylko tu: robocze wyżej i katalogi robocze profili (ROBOCZE_PROFILU)
    robocze_plikow: List[str] = field(default_factory=list)


def _domy() -> List[str]:
    """Katalogi domowe: HOME terminala (przy terminal.home_mode: profile w danych Jarva) i właściciela."""
    wynik: List[str] = []
    for d in (_dom(), os.path.expanduser("~"), os.environ.get("HOME", ""), os.environ.get("USERPROFILE", "")):
        r = _realna(d, None) if d else None
        if r and r not in wynik:
            wynik.append(r)
    return wynik


def _tymczasowe() -> List[str]:
    """Katalogi tymczasowe (istniejące), w których klon repozytorium można skasować."""
    wynik: List[str] = []
    for d in (tempfile.gettempdir(), os.environ.get("TMPDIR", ""), "/tmp", "/var/tmp"):
        r = _realna(d, None) if d else None
        if r and os.path.isdir(r) and r not in wynik:
            wynik.append(r)
    return wynik


def _krytyczne(m: _Miejsca) -> _Krytyczne:
    cale: List[Tuple[str, str]] = []
    wnetrze: List[Tuple[str, str]] = []
    jarvo: List[Tuple[str, str]] = []

    def dodaj(lista: List[Tuple[str, str]], sciezka: Any, opis: str) -> None:
        k = _k_realny(sciezka)
        if k and all(k != x for x, _ in lista):
            lista.append((k, opis))

    for d in _domy():
        dodaj(cale, d, "katalog domowy")
        for nazwa in ("dev", "strony", "jarvo-testy"):
            dodaj(cale, os.path.join(d, nazwa), f"~/{nazwa}")
        for nazwa in (".ssh", ".config", ".phoneuse"):
            dodaj(wnetrze, os.path.join(d, nazwa), f"~/{nazwa}")
        for sciezka in (os.path.join(d, ".local", "share", "jarvo"), os.path.join(d, ".jarvo")):
            dodaj(jarvo, sciezka, "dane Jarva")
    if os.environ.get("LOCALAPPDATA"):
        dodaj(jarvo, os.path.join(os.environ["LOCALAPPDATA"], "Jarvo"), "dane Jarva")
    home = _hermes_home()
    korzen = _korzen_danych(home)
    for sciezka in (home, korzen, os.environ.get("JARVO_ROOT"), os.environ.get("HERMES_SRC")):
        dodaj(jarvo, sciezka, "dane Jarva")
    ws = korzen / "jarvo" / "workspaces"
    for sciezka, opis in ((m.wiedza, "skarbiec wiedzy"), (m.misje, "misje"), (ws, "katalogi robocze kart")):
        dodaj(cale, sciezka, opis)
    for r, _ in list(jarvo):                     # układ instalacji (<korzeń>/dane/jarvo/…), gdy HERMES_HOME jest inny
        for dane in (os.path.join(r, "dane", "jarvo"), os.path.join(r, "jarvo")):
            for nazwa, opis in (("knowledge", "skarbiec wiedzy"), ("missions", "misje"),
                                ("workspaces", "katalogi robocze kart")):
                if os.path.isdir(os.path.join(dane, nazwa)):
                    dodaj(cale, os.path.join(dane, nazwa), opis)
    robocze = [k for k, _ in cale if any(_wewnatrz(k, j) for j, _ in jarvo)]
    jednorazowe = [k for k in (_k_realny(t) for t in _tymczasowe()) if k] + \
        [k for k, opis in cale if opis == "katalogi robocze kart"]
    return _Krytyczne(cale, wnetrze, jarvo, robocze, jednorazowe, m.konfig_k, robocze + list(m.robocze))


def _korzen_repo(p: str) -> Optional[str]:
    """Katalog repozytorium git, w którym leży p (z `.git` w środku albo repozytorium bez drzewa roboczego)."""
    d = p
    for _ in range(64):
        if os.path.lexists(os.path.join(d, ".git")):
            return d
        if os.path.isfile(os.path.join(d, "HEAD")) and os.path.isdir(os.path.join(d, "objects")):
            return d
        wyzej = os.path.dirname(d)
        if wyzej == d:
            return None
        d = wyzej
    return None


def _repo_w_srodku(katalog: str) -> Optional[str]:
    """Pierwsze repozytorium git w drzewie (bez dowiązań i wyników budowania); przegląd ograniczony, więc w ogromnym
    drzewie może go nie znaleźć."""
    kolejka = collections.deque([(katalog, 0)])
    odwiedzone = 0
    while kolejka:
        d, gl = kolejka.popleft()
        try:
            with os.scandir(d) as it:
                wpisy = list(it)
        except OSError:
            continue
        if any(e.name == ".git" for e in wpisy):
            return d
        for e in wpisy:
            try:
                if e.name in _WYNIKI_BUDOWANIA or not e.is_dir(follow_symlinks=False):
                    continue
            except OSError:
                continue
            odwiedzone += 1
            if odwiedzone > _SKAN_KATALOGOW:
                return None
            if gl + 1 <= _SKAN_GLEBOKOSC:
                kolejka.append((e.path, gl + 1))
    return None


def _nazwa_programu(nazwa: str) -> str:
    prog = re.split(r"[\\/]", nazwa)[-1].lower()
    for rozsz in (".exe", ".cmd", ".bat", ".com"):
        if prog.endswith(rozsz) and len(prog) > len(rozsz):
            return prog[: -len(rozsz)]
    return prog


def _caly_glob(tekst: str) -> bool:
    """Glob, który bierze wszystko w katalogu (`*`, `.*`, `*.*`, `?*`) jako ostatni składnik ścieżki."""
    skl = [c for c in re.split(r"[\\/]+", tekst) if c]
    idx = next((i for i, c in enumerate(skl) if any(ch in c for ch in _ODGLOB)), None)
    return (idx is not None and idx == len(skl) - 1
            and re.fullmatch("\\.?[\ue000\ue001]+(?:\\.[\ue000\ue001]+)?", skl[idx]) is not None)


def _lacze(plaski: str, cwd: Optional[str], dom: str) -> Optional[str]:
    """Ścieżka samego dowiązania (bez rozwiązania ostatniego składnika), gdy cel nim jest: rm kasuje wtedy łącze."""
    nazwa = os.path.basename(plaski.rstrip("/\\"))
    if nazwa in ("", ".", ".."):
        return None
    rodzic = _realna(os.path.dirname(plaski.rstrip("/\\")) or ".", cwd, powloka=True, dom=dom)
    if rodzic is None:
        return None
    sciezka = os.path.join(rodzic, nazwa)
    return sciezka if os.path.islink(sciezka) else None


def _dodaj_cel(wynik: List[_Kasowanie], arg: "_Arg", cwd: Optional[str], dom: str, forma: str, rodzaj: str, *,
               rek: bool = False, wym: bool = False, pusto: bool = False) -> None:
    """Cel kasowania (słowo po rozwinięciu) → _Kasowanie z rzeczywistymi ścieżkami; glob: dopasowania, a glob na
    wszystko w katalogu (albo ze 100 trafieniami) to też skasowanie zawartości tego katalogu."""
    t = arg.tekst
    if t is None:
        wynik.append(_Kasowanie(forma, rodzaj, None, arg.pokaz, rek, wym, pusto))
        return
    if t == "" or t in _URZADZENIA_PUSTE:
        return
    if any(ch in t for ch in _ODGLOB):
        sc = _sciezki_celu(t, cwd, dom)
        if sc is None:
            wynik.append(_Kasowanie(forma, rodzaj, None, arg.pokaz, rek, wym, pusto))
            return
        baza, trafienia = sc[0], sc[1:]
        if rodzaj in ("usun", "zawartosc", "filtr") and (_caly_glob(t) or len(trafienia) >= _MAX_DOPASOWAN):
            wynik.append(_Kasowanie(forma, "zawartosc", [baza], arg.pokaz, True, wym))
        if trafienia:
            wynik.append(_Kasowanie(forma, rodzaj, trafienia, arg.pokaz, rek, wym, pusto))
        return
    plaski = arg.plaski or ""
    if rodzaj in ("usun", "plik") and not plaski.endswith(("/", "\\")):
        lacze = _lacze(plaski, cwd, dom)
        if lacze:
            wynik.append(_Kasowanie(forma, "plik", [lacze], arg.pokaz))
            return
    r = _realna(plaski, cwd, powloka=True, dom=dom)
    wynik.append(_Kasowanie(forma, rodzaj, [r] if r else None, arg.pokaz, rek, wym, pusto))


def _kasowanie_nierozebrane(tekst: str, powod: str, wynik: List[_Kasowanie]) -> None:
    """Polecenie albo kod, którego nie rozbieramy: jeśli widać w nim kasowanie, to kasowanie o nieznanych celach."""
    if _KASUJACE_RE.search(tekst):
        wynik.append(_Kasowanie("kasowanie", "usun", None, _poczatek(tekst, 80), True, True,
                                uwaga=f"{powod}, a widać w nim kasowanie"))


def _zagniezdzone_polecenie(tekst: str, cwd: Optional[str], dom: str, wynik: List[_Kasowanie], glebokosc: int) -> None:
    if glebokosc >= _MAX_ZAGNIEZDZEN:
        _kasowanie_nierozebrane(tekst, "polecenie zagnieżdżone zbyt głęboko", wynik)
        return
    _analizuj_terminal(tekst, cwd, dom, wynik, glebokosc + 1)


def _kasowania_podstawien(p: _Polecenie, cwd: Optional[str], dom: str, wynik: List[_Kasowanie],
                          glebokosc: int) -> None:
    """Polecenia w $(…), `…`, <(…) i >(…) (także w przypisaniach i celach przekierowań) wykonują się naprawdę."""
    for slowo in list(p.slowa) + [s for _, s in p.przekierowania]:
        for rodzaj, t in slowo.czesci:
            if rodzaj != "x":
                continue
            if t.startswith(("$(", "<(", ">(")):
                _zagniezdzone_polecenie(t[2:-1], cwd, dom, wynik, glebokosc)
            elif t.startswith("`"):
                _zagniezdzone_polecenie(t[1:-1], cwd, dom, wynik, glebokosc)


def _kod_z_wejscia(p: _Polecenie) -> List[str]:
    """Treść heredoców i here-stringów (<<<) polecenia: dla python3, bash i node to kod."""
    wynik = list(p.heredoki)
    for op, slowo in p.przekierowania:
        if op == "<<<":
            t = slowo.zwykle()
            if t is not None:
                wynik.append(t)
    return wynik


def _bez_tresci(slowa: List[_Slowo], zmienne: Dict[str, Optional[str]], dom: str) -> bool:
    """Czy przekierowanie `>` zapisze pusty plik (`> f`, `: > f`, `true > f`, `cat /dev/null > f`, `echo -n > f`)."""
    if not slowa:
        return True
    nazwa = _plaski(slowa[0], zmienne, dom)
    if nazwa is None:
        return False
    prog = _nazwa_programu(nazwa)
    reszta = [_plaski(s, zmienne, dom) for s in slowa[1:]]
    if prog in (":", "true", "false"):
        return True
    if prog == "cat":
        return bool(reszta) and all(r in _URZADZENIA_PUSTE for r in reszta)
    if prog == "echo":
        return bool(reszta) and all(r == "-n" for r in reszta)
    if prog == "printf":
        return all(r == "" for r in reszta)
    return False


def _pomin_opcje(argi: List["_Arg"], krotkie: str, dlugie: Tuple[str, ...], *, przypisania: bool = False) -> int:
    """Indeks pierwszego argumentu po opcjach owijki (z wartościami opcji, `--` i przypisaniami env)."""
    i = 0
    while i < len(argi):
        t = argi[i].plaski
        if t is None:
            return i
        if przypisania and _PRZYPISANIE.match(t):
            i += 1
            continue
        if t == "--":
            return i + 1
        if not t.startswith("-") or t == "-":
            return i
        if t.startswith("--"):
            i += 2 if (t in dlugie and "=" not in t) else 1
            continue
        i += 1
        for j, litera in enumerate(t[1:], start=1):
            if litera in krotkie:
                if not t[j + 1:]:
                    i += 1
                break
    return i


def _bez_owijek(prog: str, argi: List["_Arg"], cwd: Optional[str], dom: str
                ) -> Tuple[str, List["_Arg"], Optional[str], bool]:
    """Program spod sudo, env, nice, timeout, xargs, `uv run`…: (program, argumenty, katalog, czy spod xargs)."""
    xargs = False
    for _ in range(8):
        if prog in _URUCHAMIACZE and argi and argi[0].plaski == "run":
            i = 1
            while i < len(argi) and (argi[i].plaski or "").startswith("-"):
                i += 2 if argi[i].plaski in _URUCHAMIACZE_Z_WARTOSCIA else 1
        elif prog in _OWIJKI:
            if prog == "command" and argi and argi[0].plaski in ("-v", "-V"):
                return "", [], cwd, xargs
            krotkie, dlugie, pozycyjne = _OWIJKI[prog]
            if prog == "env":
                for j, a in enumerate(argi):         # env -C katalog: program rusza gdzie indziej
                    if a.plaski in ("-C", "--chdir") or (a.plaski or "").startswith("--chdir="):
                        cwd = None
            xargs = xargs or prog == "xargs"
            i = _pomin_opcje(argi, krotkie, dlugie, przypisania=prog in ("env", "sudo", "doas")) + pozycyjne
        else:
            break
        if i >= len(argi) or argi[i].plaski is None:
            return "", [], cwd, xargs
        prog, argi = _nazwa_programu(argi[i].plaski), argi[i + 1:]
    return prog, argi, cwd, xargs


def _rm(argi: List["_Arg"], cwd: Optional[str], dom: str, wynik: List[_Kasowanie]) -> None:
    """rm: flagi w dowolnej kolejności, także po celach (GNU) i w długiej postaci; -r/-R/--recursive, -f/--force."""
    rek = wym = po_kreskach = False
    cele: List[_Arg] = []
    for a in argi:
        t = a.plaski
        if t is None or po_kreskach or t == "-" or not t.startswith("-"):
            cele.append(a)
        elif t == "--":
            po_kreskach = True
        elif t.startswith("--"):
            rek = rek or t == "--recursive"
            wym = wym or t == "--force"
        else:
            rek = rek or "r" in t or "R" in t
            wym = wym or "f" in t
    forma = "rm -" + ("r" if rek else "") + ("f" if wym else "") if (rek or wym) else "rm"
    for a in cele:
        _dodaj_cel(wynik, a, cwd, dom, forma, "usun" if rek else "plik", rek=rek, wym=wym)


def _czysty_wzorzec(v: Optional[str]) -> bool:
    """Wzorzec find, który pasuje do wszystkiego (`*`, `.*`, `*.*`; dla -regex `.*`)."""
    return v is not None and (re.fullmatch(r"\.?[*?]+(?:\.[*?]+)?", v) is not None or v in (".*", ".+", "^.*$"))


def _find(argi: List["_Arg"], cwd: Optional[str], dom: str, wynik: List[_Kasowanie]) -> None:
    """find … -delete / -exec rm: bez zawężenia (nazwa, czas, rozmiar) kasuje całe drzewo od punktu startu."""
    i = 0
    while i < len(argi) and argi[i].plaski in ("-H", "-L", "-P") or (i < len(argi)
                                                                     and (argi[i].plaski or "").startswith("-O")):
        i += 1
    starty: List[_Arg] = []
    while i < len(argi) and not ((argi[i].plaski or "x")[0] in "-(!)" or argi[i].plaski == ","):
        starty.append(argi[i])
        i += 1
    wyr = argi[i:]
    kasuje = rek = filtr = negacja = False
    j = 0
    while j < len(wyr):
        t = wyr[j].plaski
        if t == "-delete":
            kasuje = True
        elif t in ("-exec", "-execdir", "-ok", "-okdir"):
            k = j + 1
            while k < len(wyr) and wyr[k].plaski not in (";", "+"):
                k += 1
            polecenie = wyr[j + 1:k]
            nazwa = _nazwa_programu(polecenie[0].plaski or "") if polecenie else ""
            tekst = " ".join(a.plaski or a.pokaz for a in polecenie)
            if nazwa in _KASUJACE_PROGRAMY or (nazwa in _POWLOKI and _KASUJACE_RE.search(tekst)):
                kasuje = True
                rek = rek or any(re.fullmatch(r"-[a-zA-Z]*[rR][a-zA-Z]*|--recursive", a.plaski or "")
                                 for a in polecenie[1:])
            j = k
        elif t in ("!", "-not", "-o", "-or"):
            negacja = True
        elif t in _FIND_NAZWY:
            filtr = filtr or not _czysty_wzorzec(wyr[j + 1].plaski if j + 1 < len(wyr) else None)
            j += 1
        elif t in _FIND_FILTRY:
            filtr = True
            j += 1
        elif t in _FIND_FILTRY_BEZ_WARTOSCI:
            filtr = True
        elif t in _FIND_Z_WARTOSCIA:
            j += 1
        j += 1
    if not kasuje:
        return
    rodzaj = "filtr" if filtr and not negacja else "usun"
    forma = "find -delete" if not rek else "find -exec rm -r"
    for a in starty or [_Arg(".", ".")]:
        _dodaj_cel(wynik, a, cwd, dom, forma, rodzaj, rek=True, wym=True)


def _rsync(argi: List["_Arg"], cwd: Optional[str], dom: str, wynik: List[_Kasowanie]) -> None:
    """rsync --delete (--del, --delete-*): kasuje w katalogu docelowym wszystko, czego nie ma w źródle."""
    teksty = [a.plaski for a in argi]
    if not any(t and (t == "--del" or t.startswith("--delete")) for t in teksty):
        return
    poz: List[_Arg] = []
    i = 0
    while i < len(argi):
        t = teksty[i]
        if t is not None and t.startswith("-"):
            i += 2 if (t in _RSYNC_Z_WARTOSCIA and "=" not in t) else 1
            continue
        poz.append(argi[i])
        i += 1
    if len(poz) < 2:
        return
    cel, zrodla = poz[-1], poz[:-1]
    if cel.plaski is not None and (re.match(r"^[^/\\]*:", cel.plaski) and not re.match(r"^[A-Za-z]:[\\/]",
                                                                                         cel.plaski)):
        return                                    # host:ścieżka, rsync://: kasuje na innym komputerze
    for z in zrodla:
        zt = z.plaski
        if cel.tekst is None or zt is None or zt.endswith(("/", "\\", "/.")) or zt == ".":
            efekt = _Arg(cel.tekst, cel.pokaz)
        else:
            efekt = _Arg(cel.tekst.rstrip("/\\") + "/" + re.split(r"[\\/:]", zt.rstrip("/\\"))[-1], cel.pokaz)
        _dodaj_cel(wynik, efekt, cwd, dom, "rsync --delete", "zawartosc", rek=True, wym=True)


def _git(argi: List["_Arg"], cwd: Optional[str], dom: str, wynik: List[_Kasowanie]) -> None:
    """git clean -f, git reset --hard, git push --force/-f/--mirror/+gałąź (także z -C, --git-dir, --work-tree)."""
    sciezka, i, n = cwd, 0, len(argi)
    while i < n:
        t = argi[i].plaski
        if t is None:
            sciezka, i = None, i + 1
            continue
        if t == "-C":
            x = argi[i + 1].plaski if i + 1 < n else None
            sciezka = _realna(x, sciezka, powloka=True, dom=dom) if x and sciezka else None
            i += 2
            continue
        if t.startswith(("--git-dir", "--work-tree")):
            if "=" in t:
                x, i = t.split("=", 1)[1], i + 1
            else:
                x, i = (argi[i + 1].plaski if i + 1 < n else None), i + 2
            r = _realna(x, sciezka, powloka=True, dom=dom) if x else None
            if r and t.startswith("--git-dir") and os.path.basename(r) == ".git":
                r = os.path.dirname(r)
            sciezka = r
            continue
        if t in ("-c", "--namespace", "--exec-path", "--config-env", "--super-prefix"):
            i += 2
            continue
        if t.startswith("-"):
            i += 1
            continue
        break
    if i >= n:
        return
    pod, reszta = argi[i].plaski, [a.plaski for a in argi[i + 1:]]
    krotkie = [x for x in reszta if x and x.startswith("-") and not x.startswith("--")]
    forma = ""
    if pod == "clean":
        sila = None in reszta or "--force" in reszta or any("f" in x[1:] for x in krotkie)
        proba = "--dry-run" in reszta or any("n" in x[1:] for x in krotkie)
        forma = "git clean -f" if sila and not proba else ""
    elif pod == "reset":
        forma = "git reset --hard" if any(x and len(x) >= 3 and "--hard".startswith(x) for x in reszta) else ""
    elif pod == "push":
        if "--mirror" in reszta:
            forma = "git push --mirror"
        elif any(x and (x.startswith("--force") or (x.startswith("+") and len(x) > 1)) for x in reszta) or \
                any("f" in x[1:] for x in krotkie):
            forma = "git push --force"
    if forma:
        wynik.append(_Kasowanie(forma, "repo", [sciezka] if sciezka else None, forma, True, True,
                                uwaga="nie wiadomo, w którym repozytorium (katalog ze zmiennej albo po `cd -`)"))


def _kasowania_polecenia(prog: str, argi: List["_Arg"], p: _Polecenie, cwd: Optional[str], dom: str,
                         wynik: List[_Kasowanie], glebokosc: int) -> None:
    """Usunięcia i nadpisania jednego prostego polecenia (po rozwinięciu słów), także spod owijek i w kodzie."""
    prog, argi, cwd, xargs = _bez_owijek(prog, argi, cwd, dom)
    if not prog:
        return
    if prog in _ZABIJAJACE:
        if xargs:                                  # cele z potoku: ocenia je _analizuj_terminal po treści polecenia
            pokaz = _poczatek(" ".join(a.pokaz for a in argi), 80)
            wynik.append(_Kasowanie(f"xargs {prog}", "zabij_xargs", None, pokaz))
        _zabijanie(prog, argi, wynik)
        return
    if xargs and (prog in _KASUJACE_PROGRAMY or prog in _POWLOKI):
        wynik.append(_Kasowanie(f"xargs {prog}", "xargs", None, _poczatek(" ".join(a.pokaz for a in argi), 80)))
    teksty = [a.plaski for a in argi]
    if prog == "rm":
        _rm(argi, cwd, dom, wynik)
    elif prog == "unlink":
        for a in argi:
            if not (a.plaski or "").startswith("-"):
                _dodaj_cel(wynik, a, cwd, dom, "unlink", "plik")
    elif prog == "shred":
        poz, _, _ = _opcje(argi, "ns", {"--iterations", "--size", "--random-source"})
        for a in poz:
            if (a.plaski or "").startswith("/dev/") and a.plaski not in _URZADZENIA_PUSTE:
                wynik.append(_Kasowanie("shred", "urzadzenie", None, a.pokaz))
            else:
                _dodaj_cel(wynik, a, cwd, dom, "shred", "oproznij", pusto=True)
    elif prog == "find":
        _find(argi, cwd, dom, wynik)
    elif prog == "rsync":
        _rsync(argi, cwd, dom, wynik)
    elif prog == "git":
        _git(argi, cwd, dom, wynik)
    elif prog == "truncate":
        poz, wart, _ = _opcje(argi, "sr", {"--size", "--reference"})
        rozmiar = [x.plaski for x in wart.get("s", []) + wart.get("--size", [])]
        if any(r and r.startswith("+") for r in rozmiar):
            return                                 # truncate -s +N wydłuża plik
        pusto = any(r is not None and re.fullmatch(r"0+[a-zA-Z]*", r) for r in rozmiar)
        for a in poz:
            _dodaj_cel(wynik, a, cwd, dom, "truncate", "oproznij", pusto=pusto)
    elif prog == "dd":
        for a in argi:
            if a.plaski and a.plaski.startswith("of="):
                cel = _Arg(a.tekst[3:] if a.tekst else None, a.pokaz)
                if (cel.plaski or "").startswith("/dev/") and cel.plaski not in _URZADZENIA_PUSTE:
                    wynik.append(_Kasowanie("dd of=", "urzadzenie", None, a.pokaz))
                else:
                    _dodaj_cel(wynik, cel, cwd, dom, "dd of=", "oproznij")
    elif _FORMATUJACE.match(prog):
        wynik.append(_Kasowanie(prog, "urzadzenie", None, _poczatek(" ".join(a.pokaz for a in argi), 80)))
    elif prog == "tee":
        if not any(t is not None and (t == "--append" or re.fullmatch(r"-[a-z]*a[a-z]*", t)) for t in teksty):
            for a in argi:
                if not (a.plaski or "").startswith("-"):
                    _dodaj_cel(wynik, a, cwd, dom, "tee", "oproznij")
    elif prog == "cp":
        poz, wart, _ = _opcje(argi, *_OPCJE_Z_WARTOSCIA["cp"])
        katalog = wart.get("t", []) + wart.get("--target-directory", [])
        zrodla = poz if katalog else poz[:-1]
        if any(a.plaski in _URZADZENIA_PUSTE for a in zrodla) and (katalog or len(poz) >= 2):
            for a in katalog or poz[-1:]:
                _dodaj_cel(wynik, a, cwd, dom, "cp /dev/null", "oproznij", pusto=True)
    elif prog in _POWLOKI:
        i = 0
        while i < len(argi):
            t = argi[i].plaski
            if t is None:
                return
            if t.startswith("-") and not t.startswith("--") and "c" in t[1:]:
                if i + 1 < len(argi):
                    kod = argi[i + 1]
                    if kod.plaski is None:
                        _kasowanie_nierozebrane(kod.pokaz, "polecenie z nieznaną treścią ($…)", wynik)
                    else:
                        _zagniezdzone_polecenie(kod.plaski, cwd, dom, wynik, glebokosc)
                return
            if not t.startswith(("-", "+")):
                return                             # skrypt z pliku: nie czytamy go
            i += 2 if t in ("-o", "+o", "-O", "+O", "--rcfile", "--init-file") else 1
        for tresc in _kod_z_wejscia(p):
            _zagniezdzone_polecenie(tresc, cwd, dom, wynik, glebokosc)
    elif prog == "eval":
        if any(t is None for t in teksty):
            _kasowanie_nierozebrane(" ".join(a.pokaz for a in argi), "eval z nieznaną treścią ($…)", wynik)
        else:
            _zagniezdzone_polecenie(" ".join(t for t in teksty if t is not None), cwd, dom, wynik, glebokosc)
    elif _PYTHON.match(prog):
        i = 0
        while i < len(argi):
            t = argi[i].plaski
            if t is None or t == "-m" or not t.startswith("-"):
                return                             # moduł, skrypt z pliku albo nieznany argument
            if t == "-":
                break
            if re.fullmatch(r"-[a-zA-Z]*c", t):
                if i + 1 < len(argi):
                    kod = argi[i + 1]
                    if kod.plaski is None:
                        _kasowanie_nierozebrane(kod.pokaz, "kod Pythona z nieznaną treścią ($…)", wynik)
                    else:
                        _kasowania_pythona(kod.plaski, cwd, dom, wynik, glebokosc)
                return
            i += 2 if t in ("-X", "-W", "-Q") else 1
        for tresc in _kod_z_wejscia(p):
            _kasowania_pythona(tresc, cwd, dom, wynik, glebokosc)
    elif prog in _INNE_JEZYKI:
        flagi = _INNE_JEZYKI[prog]
        kody = [k for k in _kod_z_wejscia(p)]
        for i, a in enumerate(argi[:-1]):
            t = a.plaski
            if t is not None and (t in flagi or (prog in ("perl", "ruby") and re.fullmatch(r"-[a-zA-Z]*[eE]", t))):
                kody.append(argi[i + 1].plaski if argi[i + 1].plaski is not None else argi[i + 1].pokaz)
        for kod in kody:
            _kasowania_obcego_kodu(kod, prog, cwd, dom, wynik)


def _kasowania_obcego_kodu(kod: str, prog: str, cwd: Optional[str], dom: str, wynik: List[_Kasowanie]) -> None:
    """node/bun/deno/perl/ruby/php: fs.rmSync, rimraf, rmtree, remove_tree, FileUtils.rm_rf z dosłowną ścieżką."""
    for m in _OBCE_KASOWANIE.finditer(kod):
        sciezka = m.group(2) if m.group(1) else None
        _dodaj_cel(wynik, _Arg(sciezka, _maskuj(m.group(0))[:80]), cwd, dom, f"{prog}: {m.group(0).split('(')[0].strip()}",
                   "usun", rek=True, wym=True)


def _py_nazwa(n: Any) -> str:
    """Nazwa z kropkami (os.path.join, shutil.rmtree); "" gdy u podstawy nie stoi nazwa."""
    czesci: List[str] = []
    while isinstance(n, ast.Attribute):
        czesci.append(n.attr)
        n = n.value
    if not isinstance(n, ast.Name):
        return ""
    czesci.append(n.id)
    return ".".join(reversed(czesci))


class _PyWartosci:
    """Wartości napisów w kodzie Pythona bez jego uruchamiania: stałe, f-napisy ze znanymi zmiennymi, Path(…) / „x”,
    os.path.join, expanduser, Path.home(), os.environ["HOME"], tempfile.mkdtemp(). Reszta = None (nie wiadomo)."""

    def __init__(self, cwd: Optional[str], dom: str) -> None:
        self.cwd, self.dom = cwd, dom
        tmp = _tymczasowe()
        self.tmp = os.path.join(tmp[0] if tmp else tempfile.gettempdir(), "jarvo-zgody-tmp")
        self.zm: Dict[str, Optional[str]] = {}

    def _env(self, nazwa: Optional[str]) -> Optional[str]:
        if nazwa in ("HOME", "USERPROFILE"):
            return self.dom
        if nazwa in ("TMPDIR", "TEMP", "TMP"):
            return self.tmp
        if nazwa == "PWD":
            return self.cwd
        return os.environ.get(nazwa) if nazwa and _ZMIENNE_ZNANE.match(nazwa) else None

    def zbierz(self, drzewo: Any) -> None:
        """Przypisania w kolejności z kodu; nazwa przypisana dwa razy różnie, w pętli albo jako parametr = None."""
        wiazania: List[Tuple[int, int, str, Any, bool]] = []      # (linia, kolumna, nazwa, wyrażenie, tymczasowy)

        def nazwy(cel: Any) -> List[str]:
            return [w.id for w in ast.walk(cel) if isinstance(w, ast.Name)]

        for w in ast.walk(drzewo):
            poz = (getattr(w, "lineno", 0), getattr(w, "col_offset", 0))
            if isinstance(w, ast.Assign):
                for cel in w.targets:
                    for nz in nazwy(cel):
                        wiazania.append((*poz, nz, w.value if isinstance(cel, ast.Name) else None, False))
            elif isinstance(w, (ast.AnnAssign, ast.NamedExpr)) and isinstance(w.target, ast.Name):
                wiazania.append((*poz, w.target.id, w.value, False))
            elif isinstance(w, (ast.AugAssign, ast.For, ast.AsyncFor, ast.comprehension)):
                for nz in nazwy(w.target):
                    wiazania.append((*poz, nz, None, False))
            elif isinstance(w, ast.withitem) and w.optional_vars is not None:
                tymczasowy = isinstance(w.context_expr, ast.Call) and \
                    _py_nazwa(w.context_expr.func).endswith("TemporaryDirectory")
                for nz in nazwy(w.optional_vars):
                    wiazania.append((getattr(w.context_expr, "lineno", 0), 0, nz, None, tymczasowy))
            elif isinstance(w, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                for a in w.args.args + w.args.posonlyargs + w.args.kwonlyargs + \
                        [x for x in (w.args.vararg, w.args.kwarg) if x]:
                    wiazania.append((*poz, a.arg, None, False))
            elif isinstance(w, ast.ExceptHandler) and w.name:
                wiazania.append((*poz, w.name, None, False))
        for _, _, nz, wyr, tymczasowy in sorted(wiazania, key=lambda x: (x[0], x[1])):
            wartosc = self.tmp if tymczasowy else (self.wartosc(wyr) if wyr is not None else None)
            self.zm[nz] = wartosc if (nz not in self.zm or self.zm[nz] == wartosc) else None

    def wartosc(self, n: Any, gl: int = 0) -> Optional[str]:
        if n is None or gl > 30:
            return None
        w = lambda x: self.wartosc(x, gl + 1)          # noqa: E731
        if isinstance(n, ast.Constant):
            return n.value if isinstance(n.value, str) else None
        if isinstance(n, ast.JoinedStr):
            czesci = []
            for v in n.values:
                x = str(v.value) if isinstance(v, ast.Constant) else (w(v.value) if isinstance(v, ast.FormattedValue)
                                                                       else None)
                if x is None:
                    return None
                czesci.append(x)
            return "".join(czesci)
        if isinstance(n, ast.Name):
            return self.zm.get(n.id)
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Div, ast.Add)):
            a, b = w(n.left), w(n.right)
            if a is None or b is None:
                return None
            return os.path.join(a, b) if isinstance(n.op, ast.Div) else a + b
        if isinstance(n, ast.Subscript) and _py_nazwa(n.value) in ("os.environ", "environ"):
            return self._env(w(n.slice))
        if isinstance(n, ast.Attribute) and n.attr == "parent":
            x = w(n.value)
            return os.path.dirname(x.rstrip("/\\")) if x else None
        if not isinstance(n, ast.Call):
            return None
        f, pelna = n.func, _py_nazwa(n.func)
        argi = [w(a) for a in n.args]
        if isinstance(f, ast.Attribute) and f.attr in _PY_METODY and not n.args:
            return w(f.value)                           # Path(…).expanduser(), p.resolve()
        if isinstance(f, ast.Attribute) and f.attr == "joinpath":
            baza = w(f.value)
            return None if baza is None or None in argi else os.path.join(baza, *argi)
        if pelna in ("Path.home", "pathlib.Path.home"):
            return self.dom
        if pelna in ("Path.cwd", "pathlib.Path.cwd", "os.getcwd"):
            return self.cwd
        if pelna in ("os.environ.get", "environ.get", "os.getenv", "getenv") and argi:
            return self._env(argi[0]) or (argi[1] if len(argi) > 1 else None)
        if pelna.rsplit(".", 1)[-1] in ("mkdtemp", "gettempdir") and pelna.startswith(("tempfile.", "mkdtemp",
                                                                                         "gettempdir")):
            return self.tmp
        ostatnia = pelna.rsplit(".", 1)[-1] if pelna else ""
        if ostatnia in _PY_SCIEZKI:
            if not n.args:
                return self.cwd if ostatnia.endswith("Path") else None
            return None if None in argi else os.path.join(*argi)
        return None

    def polecenie(self, n: Any) -> Optional[str]:
        """Polecenie powłoki z os.system(…)/subprocess.run(…): napis albo lista (nieznany element → $(:))."""
        if isinstance(n, (ast.List, ast.Tuple)):
            czesci = [self.wartosc(e) for e in n.elts]
            return " ".join(shlex.quote(c) if c is not None else "$(:)" for c in czesci) if czesci else None
        return self.wartosc(n)


def _kasowania_pythona(kod: str, cwd: Optional[str], dom: str, wynik: List[_Kasowanie], glebokosc: int) -> None:
    """shutil.rmtree, os.removedirs, os.remove/unlink, Path.unlink i os.system/subprocess w kodzie Pythona."""
    try:
        drzewo = ast.parse(kod)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        _kasowanie_nierozebrane(kod, "kodu Pythona nie da się rozebrać", wynik)
        return
    ocena = _PyWartosci(cwd, dom)
    ocena.zbierz(drzewo)
    drzewa = 0
    for w in ast.walk(drzewo):
        if not isinstance(w, ast.Call):
            continue
        f, pelna = w.func, _py_nazwa(w.func)
        ostatnia = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
        arg0 = w.args[0] if w.args else next((k.value for k in w.keywords if k.arg in ("path", "name", "args", "cmd")),
                                             None)
        pokaz = _maskuj(ast.unparse(arg0) if arg0 is not None else "?")[:80]
        if ostatnia in ("rmtree", "removedirs"):
            drzewa += 1
            _dodaj_cel(wynik, _Arg(ocena.wartosc(arg0), pokaz), cwd, dom, f"{ostatnia} (Python)", "usun", rek=True,
                       wym=True)
        elif pelna in ("os.remove", "os.unlink", "remove", "unlink"):
            sciezka = ocena.wartosc(arg0)
            if sciezka:
                _dodaj_cel(wynik, _Arg(sciezka, pokaz), cwd, dom, f"{pelna} (Python)", "plik")
        elif isinstance(f, ast.Attribute) and f.attr == "unlink":
            sciezka = ocena.wartosc(f.value)
            if sciezka:
                _dodaj_cel(wynik, _Arg(sciezka, sciezka), cwd, dom, "Path.unlink (Python)", "plik")
        elif pelna in ("os.kill", "os.killpg", "kill", "killpg") and arg0 is not None:
            _zabijanie_pid(f"{pelna} (Python)", _py_pid(arg0, grupa=ostatnia == "killpg"), pokaz, wynik)
        elif ostatnia in _PY_POWLOKA and arg0 is not None:
            polecenie = ocena.polecenie(arg0)
            if polecenie:
                _zagniezdzone_polecenie(polecenie, cwd, dom, wynik, glebokosc)
    if not drzewa and re.search(r"\b(?:rmtree|removedirs)\b", kod):
        wynik.append(_Kasowanie("rmtree (Python)", "usun", None, "rmtree", True, True,
                                uwaga="rmtree albo removedirs pod inną nazwą, więc nie wiadomo, co skasuje"))


# ------------------------------------------------------------------------------------------------ strażnik pracowników
# 16.11 22:35 wtyczka odmówiła rozmowie kanban_block na karcie w toku (t_87d11e3a), więc Jarvo zabił jej pracownika
# poleceniem kill. Dyspozytor kanbana uznaje zabitego pracownika za awarię (protocol violation) i uruchamia kartę od
# nowa: trzy takie awarie z rzędu. Pracownika rozpoznajemy po tym, jak uruchamia go Hermes
# (hermes_cli/kanban_db_dispatch.py:2676-2706: `… chat -q "work kanban task <karta>"`, :2821: HERMES_KANBAN_TASK).
# Kartę kończy kanban_block albo kanban_complete; po końcu przebiegu pracownika zamyka sam dyspozytor
# (reap_terminal_workers, kanban_db_dispatch.py:503).

_ZABIJAJACE = frozenset({"kill", "pkill", "killall"})
# cel albo wzorzec, w którym widać Hermesa, kanban, numer karty albo rodzica powłoki terminala (proces Hermesa)
_SLOWA_PRACOWNIKA = re.compile(r"kanban|hermes|\bt_[0-9a-f]{8}\b|\$\{?PPID\b|getppid", re.I)
_KARTA_PRACOWNIKA = re.compile(r"\bwork kanban task\s+(\S+)")
_SYGNAL = re.compile(r"(?:SIG)?(?:HUP|INT|QUIT|ILL|TRAP|ABRT|IOT|BUS|FPE|KILL|USR1|SEGV|USR2|PIPE|ALRM|TERM|STKFLT|CHLD|"
                     r"CONT|STOP|TSTP|TTIN|TTOU|URG|XCPU|XFSZ|VTALRM|PROF|WINCH|IO|POLL|PWR|SYS|RTMIN(?:\+\d+)?|"
                     r"RTMAX(?:-\d+)?)|\d+")
# krótkie opcje z wartością (procps-ng pkill, psmisc killall) i długie opcje z wartością
_PKILL_Z_WARTOSCIA = {"pkill": "sugGPtFrq", "killall": "suoynZ"}
_PKILL_DLUGIE_Z_WARTOSCIA = frozenset({"--signal", "--session", "--euid", "--uid", "--group", "--parent", "--pgroup",
                                       "--terminal", "--pidfile", "--ns", "--nslist", "--runstates", "--queue",
                                       "--user", "--older-than", "--younger-than", "--context", "--cgroup", "--env"})


@dataclass
class _Proces:
    pid: int
    ppid: int
    pgid: int
    nazwa: str                 # comm (pkill bez -f, killall), najwyżej 15 znaków
    polecenie: str             # pełna linia poleceń (pkill -f)
    program: str = ""          # nazwa pliku z argv[0] (killall)
    karta: str = ""            # karta kanbana, gdy to jej pracownik


def _ja() -> int:
    return os.getpid()


def _procesy() -> List[_Proces]:
    """Procesy komputera: /proc na Linuksie, `ps` na macOS; na Windows pusto (zostaje sprawdzanie treści polecenia)."""
    wynik: List[_Proces] = []
    if os.path.isdir("/proc/self"):
        for wpis in os.scandir("/proc"):
            if not wpis.name.isdigit():
                continue
            try:
                with open(f"/proc/{wpis.name}/stat", "rb") as f:
                    stat = f.read().decode("utf-8", "replace")
                with open(f"/proc/{wpis.name}/cmdline", "rb") as f:
                    argv = [a.decode("utf-8", "replace") for a in f.read().split(b"\0") if a]
            except OSError:
                continue
            pola = stat[stat.rfind(")") + 2:].split()
            if len(pola) < 3:
                continue
            p = _Proces(int(wpis.name), int(pola[1]), int(pola[2]), stat[stat.find("(") + 1:stat.rfind(")")],
                        " ".join(argv), os.path.basename(argv[0]) if argv else "")
            m = _KARTA_PRACOWNIKA.search(p.polecenie)
            if m:
                p.karta = m.group(1)
            elif p.nazwa == "hermes" or "hermes_cli" in p.polecenie:
                try:
                    with open(f"/proc/{wpis.name}/environ", "rb") as f:
                        m2 = re.search(rb"(?:^|\0)HERMES_KANBAN_TASK=([^\0]+)", f.read())
                    p.karta = m2.group(1).decode("utf-8", "replace").strip() if m2 else ""
                except OSError:
                    pass
            wynik.append(p)
    elif not WINDOWS:
        import subprocess
        try:
            wyjscie = subprocess.run(["ps", "-axww", "-o", "pid=,ppid=,pgid=,args="], capture_output=True, text=True,
                                     timeout=5, check=False).stdout
        except (OSError, subprocess.SubprocessError):
            return wynik
        for linia in wyjscie.splitlines():
            pola = linia.split(None, 3)
            if len(pola) < 4 or not all(x.isdigit() for x in pola[:3]):
                continue
            program = os.path.basename(pola[3].split()[0])
            m = _KARTA_PRACOWNIKA.search(pola[3])
            wynik.append(_Proces(int(pola[0]), int(pola[1]), int(pola[2]), program[:15], pola[3], program,
                                 m.group(1) if m else ""))
    return wynik


def _chronione() -> List[Tuple[_Proces, str]]:
    """Procesy, których agent nie zabija, z opisem: pracownicy kart i proces Hermesa, w którym działa ta wtyczka."""
    ja = _ja()
    wynik: List[Tuple[_Proces, str]] = []
    for p in _procesy():
        if p.karta:
            wynik.append((p, f"pracownika karty {p.karta}" + (" (to Ty)" if p.pid == ja else "")))
        elif p.pid == ja:
            wynik.append((p, "proces Hermesa, w którym działasz (rozmowa albo brama)"))
    if not any(p.pid == ja for p, _ in wynik):
        wynik.append((_Proces(ja, -1, -1, "", ""), "proces Hermesa, w którym działasz"))
    return wynik


def _zabij(wynik: List[_Kasowanie], forma: str, pokaz: str, powod: str, karta: str = "") -> None:
    wynik.append(_Kasowanie(forma, "zabij", None, pokaz, uwaga=powod, karta=karta))


def _zabijanie_pid(forma: str, pid: Optional[int], pokaz: str, wynik: List[_Kasowanie],
                   chronione: Optional[List[Tuple[_Proces, str]]] = None) -> None:
    """Jeden cel kill/os.kill: PID (ujemny = grupa procesów) albo None, gdy celu nie znamy (zmienna, $(…))."""
    if pid is None:
        slad = _SLOWA_PRACOWNIKA.search(pokaz)
        if slad:
            _zabij(wynik, forma, pokaz, f"`{forma} {pokaz}` celuje w proces Hermesa albo pracownika karty (widać "
                                        f"`{slad.group(0)}`)")
        return
    if pid == -1:
        _zabij(wynik, forma, pokaz, f"`{forma} -1` wysyła sygnał do wszystkich Twoich procesów, także do Hermesa "
                                    "i pracowników kart")
        return
    for p, opis in (_chronione() if chronione is None else chronione):
        if (pid > 0 and p.pid == pid) or (pid < -1 and p.pgid == -pid):
            co = f"grupę procesów {-pid}, a w niej {opis}" if pid < 0 else opis
            _zabij(wynik, forma, pokaz, f"`{forma} {pid}` zabija {co}", p.karta)
            return


def _py_pid(n: Any, *, grupa: bool = False) -> Optional[int]:
    """PID z os.kill(…)/os.killpg(…) w kodzie Pythona: stała liczba (killpg: grupa, czyli ujemny); None = nie wiadomo."""
    znak = 1
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
        znak, n = -1, n.operand
    if not (isinstance(n, ast.Constant) and isinstance(n.value, int) and not isinstance(n.value, bool)):
        return None
    pid = znak * n.value
    return -pid if grupa and pid > 0 else pid


def _bez_sygnalu(sygnal: str) -> bool:
    """Sygnał 0 (kill -0, pkill -0) tylko sprawdza, czy proces żyje."""
    s = sygnal.strip().upper()
    return (s[3:] if s.startswith("SIG") else s) == "0"


def _kill(argi: List["_Arg"], wynik: List[_Kasowanie]) -> None:
    """kill [-SYGNAŁ | -s SYGNAŁ | -n NUMER] [--] PID… (jeden sygnał, jak w bash); %zadanie to zadanie powłoki."""
    sygnal, i = "", 0
    while i < len(argi):
        t = argi[i].plaski
        if t is None or not t.startswith("-") or t == "-":
            break
        i += 1
        if t == "--":
            break
        if t in ("-l", "-L", "--list", "--table"):
            return                                 # lista sygnałów
        if t in ("-s", "-n", "--signal"):
            sygnal = (argi[i].plaski or "?") if i < len(argi) else ""
            i += 1
        elif t.startswith("--signal="):
            sygnal = t.split("=", 1)[1]
        else:
            sygnal = t[1:]
        break                                      # po sygnale same cele (kill -9 -1: -1 to wszystkie procesy)
    if _bez_sygnalu(sygnal):
        return
    forma = "kill" + (f" -{sygnal}" if sygnal else "")
    chronione: Optional[List[Tuple[_Proces, str]]] = None
    for a in argi[i:]:
        t = a.plaski
        if t is not None and t.startswith("%"):
            continue
        if t is not None and re.fullmatch(r"-?\d+", t):
            chronione = _chronione() if chronione is None else chronione
            _zabijanie_pid(forma, int(t), a.pokaz, wynik, chronione)
        else:
            _zabijanie_pid(forma, None, a.pokaz if t is None else t, wynik)


def _liczby(wartosc: str) -> Optional[set]:
    """Lista PID-ów po przecinku (pkill -P, -g); None = nie wiadomo (wtedy bez zawężenia)."""
    try:
        return {int(x) for x in wartosc.split(",") if x.strip()} or None
    except ValueError:
        return None


def _pasuje(wzorzec: str, tekst: str, bez_wielkosci: bool, dokladnie: bool) -> bool:
    try:
        r = re.compile(wzorzec, re.I if bez_wielkosci else 0)
    except re.error:
        return (wzorzec.lower() in tekst.lower()) if bez_wielkosci else wzorzec in tekst
    return bool(r.fullmatch(tekst) if dokladnie else r.search(tekst))


def _pkill(prog: str, argi: List["_Arg"], wynik: List[_Kasowanie]) -> None:
    """pkill (wzorzec na nazwie albo z -f na całej linii poleceń, -x, -i, -v, -P rodzic, -g grupa) i killall (nazwy,
    -r wzorce, -I bez wielkości liter): czy trafia w pracownika karty albo proces Hermesa tej wtyczki."""
    z_wartoscia = _PKILL_Z_WARTOSCIA[prog]
    pelny = dokladnie = bez_wielkosci = odwrotnie = wyrazenie = po = False
    sygnal = ""
    rodzice: Optional[set] = None
    grupy: Optional[set] = None
    wzorce: List[_Arg] = []
    i = 0
    while i < len(argi):
        a, t = argi[i], argi[i].plaski
        i += 1
        if t is None or po or not t.startswith("-") or t == "-":
            wzorce.append(a)
            continue
        if t == "--":
            po = True
            continue
        if t.startswith("--"):
            nazwa, rowna, wart = t.partition("=")
            if not rowna and nazwa in _PKILL_DLUGIE_Z_WARTOSCIA and i < len(argi):
                wart, i = argi[i].plaski or "", i + 1
            pelny = pelny or nazwa == "--full"
            dokladnie = dokladnie or nazwa == "--exact"
            bez_wielkosci = bez_wielkosci or nazwa == "--ignore-case"
            odwrotnie = odwrotnie or nazwa == "--inverse"
            wyrazenie = wyrazenie or nazwa == "--regexp"
            if nazwa == "--parent":
                rodzice = _liczby(wart)
            elif nazwa == "--pgroup":
                grupy = _liczby(wart)
            elif nazwa == "--signal":
                sygnal = wart
            continue
        if _SYGNAL.fullmatch(t[1:]):               # -9, -KILL, -SIGTERM
            sygnal = t[1:]
            continue
        for j, litera in enumerate(t[1:], start=1):
            if litera in z_wartoscia:
                wart = t[j + 1:]
                if not wart and i < len(argi):
                    wart, i = argi[i].plaski or "", i + 1
                if prog == "pkill" and litera == "P":
                    rodzice = _liczby(wart)
                elif prog == "pkill" and litera == "g":
                    grupy = _liczby(wart)
                elif prog == "killall" and litera == "s":
                    sygnal = wart
                break
            if prog == "pkill":
                pelny = pelny or litera == "f"
                dokladnie = dokladnie or litera == "x"
                bez_wielkosci = bez_wielkosci or litera == "i"
                odwrotnie = odwrotnie or litera == "v"
            else:
                dokladnie = dokladnie or litera == "e"
                bez_wielkosci = bez_wielkosci or litera == "I"
                wyrazenie = wyrazenie or litera == "r"
    if _bez_sygnalu(sygnal):
        return
    forma = prog + (f" -{sygnal}" if sygnal else "") + (" -f" if pelny else "")
    for a in wzorce:
        slad = _SLOWA_PRACOWNIKA.search(a.pokaz if a.plaski is None else a.plaski)
        if slad:
            _zabij(wynik, forma, a.pokaz, f"`{forma} {a.pokaz}`: wzorzec trafia w procesy Hermesa albo pracowników "
                                          f"kart (widać `{slad.group(0)}`)")
            return
    if any(a.plaski is None for a in wzorce) or (not wzorce and rodzice is None and grupy is None):
        return                                     # nieznany wzorzec bez śladu Hermesa albo brak celu (błąd pkill)
    for p, opis in _chronione():
        if prog == "pkill":
            if (rodzice is not None and p.ppid not in rodzice) or (grupy is not None and p.pgid not in grupy):
                continue
            trafia = not wzorce or _pasuje(wzorce[0].plaski, p.polecenie if pelny else p.nazwa, bez_wielkosci,
                                           dokladnie)
            trafia = trafia != (odwrotnie and bool(wzorce))
        elif wyrazenie:
            trafia = any(_pasuje(a.plaski, p.nazwa, bez_wielkosci, False) for a in wzorce)
        else:
            male = (lambda s: s.lower()) if bez_wielkosci else (lambda s: s)       # noqa: E731
            nazwy = {male(n) for n in (p.nazwa, p.program) if n}
            trafia = any(male(a.plaski) in nazwy or male(a.plaski[:15]) in nazwy for a in wzorce)
        if trafia:
            cel = _poczatek(" ".join(a.pokaz for a in argi), 80)
            _zabij(wynik, forma, cel, f"`{prog} {cel}` zabija {opis}", p.karta)
            return


def _zabijanie(prog: str, argi: List["_Arg"], wynik: List[_Kasowanie]) -> None:
    if prog == "kill":
        _kill(argi, wynik)
    else:
        _pkill(prog, argi, wynik)


def _zabijanie_z_potoku(polecenie: str, kasowania: List[_Kasowanie]) -> None:
    """`… | xargs kill`: PID-y przychodzą z potoku; blokada, gdy w poleceniu widać Hermesa, kanban albo numer karty."""
    slad = _SLOWA_PRACOWNIKA.search(polecenie)
    for i in range(len(kasowania) - 1, -1, -1):
        k = kasowania[i]
        if k.rodzaj != "zabij_xargs":
            continue
        if slad:
            kasowania[i] = _Kasowanie(k.forma, "zabij", None, k.pokaz,
                                      uwaga=f"`{k.forma}` bierze PID-y z potoku, a w poleceniu widać "
                                            f"`{slad.group(0)}` (proces Hermesa albo pracownik karty)")
        else:
            del kasowania[i]


def _straznik_zabijania(narzedzie: str, zabicia: List[_Kasowanie], m: _Miejsca) -> Dict[str, str]:
    """Blokada zabicia pracownika karty albo Hermesa: w każdym trybie, z radą, jak zatrzymać kartę."""
    powody = "; ".join(dict.fromkeys(k.uwaga for k in zabicia[:3]))
    karta = next((k.karta for k in zabicia if k.karta), "") or "<karta>"
    kontekst = KONTEKSTY.get(m.bez_czl or "", "pełny (YOLO)" if m.yolo else f"tryb {m.tryb} z człowiekiem")
    logger.warning("jarvo-zgody: zablokowane zabicie pracownika karty (%s, %s): %s", narzedzie, kontekst,
                   _maskuj(powody)[:600])
    if m.bez_czl == "kanban":
        rada = ("swoją kartę kończysz narzędziem kanbana: kanban_block(kind=\"needs_input\", reason=\"…\"), gdy czekasz "
                "na właściciela albo coś Cię blokuje, albo kanban_complete(summary=\"…\"), gdy praca jest skończona")
    else:
        rada = (f"kartę zatrzymaj narzędziem kanbana: kanban_block(task_id=\"{karta}\", kind=\"needs_input\", "
                "reason=\"…\") (pracownika zamknie sam dyspozytor), a skończoną kończy kanban_complete")
    return _blok(f"zabicie pracownika karty albo Hermesa ({narzedzie}): {_maskuj(powody)}. Dyspozytor kanbana uznaje "
                 "zabitego pracownika za awarię (protocol violation) i uruchamia kartę od nowa (16.11 trzy razy "
                 "z rzędu). Ta blokada działa w każdym trybie i nie da się jej zatwierdzić. Co zrobić: "
                 f"{rada}. Proces, który sam uruchomiłeś (nagrywanie, serwer), zatrzymasz przez "
                 "process_manage(action=\"kill\") albo kill jego własnego PID.")



def _powod_kasowania(ks: _Kasowanie, kr: _Krytyczne) -> Optional[str]:
    """Dlaczego to kasowanie jest masowe albo niszczy chronione dane; None = wolno."""
    if ks.rodzaj == "urzadzenie":
        return f"`{ks.pokaz}`: formatowanie albo zapis wprost na dysk niszczy cały system plików"
    if ks.rodzaj == "xargs":
        return f"{ks.forma} bierze cele z wejścia (potoku), więc nie wiadomo, co skasuje"
    if ks.sciezki is None:
        if ks.rekurencyjne or ks.wymuszone or ks.rodzaj in ("zawartosc", "filtr", "repo"):
            return f"`{ks.pokaz}`: " + (ks.uwaga or "nie da się ustalić, co skasuje (zmienna, $(…), glob albo nieznany "
                                                   "katalog), a kasowanie jest rekurencyjne albo wymuszone (-r/-f)")
        return None
    for p in ks.sciezki:
        powod = _powod_sciezki(ks, p, kr)
        if powod:
            return powod
    return None


def _powod_sciezki(ks: _Kasowanie, p: str, kr: _Krytyczne) -> Optional[str]:
    k = _klucz(p)
    nad = lambda lista: next((opis for r, opis in lista if _wewnatrz(r, k)), None)     # noqa: E731  k = r albo nad r
    w = lambda lista: next((opis for r, opis in lista if _wewnatrz(k, r)), None)       # noqa: E731
    roboczy = any(_wewnatrz(k, r) for r in kr.robocze)
    jednorazowy = any(_wewnatrz(k, r) for r in kr.jednorazowe)
    pokaz = _pokaz(p)
    if ks.rodzaj == "repo":
        repo = _korzen_repo(p)
        if repo is None or any(_wewnatrz(_klucz(repo), r) for r in kr.jednorazowe):
            return None
        return f"{ks.forma} w repozytorium {_pokaz(repo)} niszczy niezatwierdzoną pracę albo historię"
    if ks.rodzaj in ("oproznij", "plik"):
        if not os.path.lexists(p) or (ks.rodzaj == "oproznij" and not os.path.isfile(p)):
            return None
        nazwa = _skladnik(os.path.basename(k))
        opis = w(kr.wnetrze) or ("dane Jarva" if ks.rodzaj == "oproznij" and not roboczy and w(kr.jarvo) else None)
        # 27.11 Hacker chciał usunąć `rm -f` plik bazy w profilu i czekał 300 s na zgodę: plik w danych Jarva poza
        # katalogami roboczymi (stan, sesje, bazy, pamięć) jest nie do odtworzenia, więc to blokada, a nie prośba
        if not opis and ks.rodzaj == "plik" and w(kr.jarvo) and not any(_wewnatrz(k, r) for r in kr.robocze_plikow):
            opis = "dane Jarva"
        if not opis and nazwa in CHRONIONE_PLIKI:
            opis = os.path.basename(p)
        if ks.rodzaj == "oproznij" and not opis:
            if ".git" in _skladniki(k, None)[:-1]:
                opis = "wnętrze .git"
            elif ks.pusto and nazwa in PLIKI_INSTRUKCJI:
                opis = f"plik instrukcji {os.path.basename(p)}"
            elif kr.konfig_k and k == kr.konfig_k:
                opis = "config.yaml Hermesa"
        if not opis:
            return None
        co = "usunie" if ks.rodzaj == "plik" else "opróżni albo nadpisze"
        return f"`{ks.forma}` {co} chroniony plik {pokaz} ({opis})"
    opis = nad(kr.wnetrze)
    if opis:
        return f"`{ks.forma}` skasuje {pokaz}, a w nim {opis} (klucze, tokeny, konfiguracja)"
    opis = w(kr.wnetrze)
    if opis:
        return f"`{ks.forma}` skasuje {pokaz} w {opis} (klucze, tokeny, konfiguracja)"
    opis = nad(kr.jarvo)
    if opis:
        return f"`{ks.forma}` skasuje {pokaz}, a w nim {opis} (profile, sesje, kod Jarva)"
    if not roboczy and w(kr.jarvo):
        return f"`{ks.forma}` skasuje {pokaz} w danych Jarva (profile, sesje, kod Jarva)"
    if ks.rodzaj == "filtr":
        return None                     # zawężone find w projekcie, skarbcu albo misjach: wolno
    opis = nad(kr.cale)
    if opis:
        cale = any(r == k for r, _ in kr.cale)
        return (f"`{ks.forma}` skasuje {'całe chronione miejsce' if cale else 'katalog nad chronionym miejscem'} "
                f"{pokaz} ({opis})")
    if jednorazowy or not os.path.isdir(p):
        return None
    if _skladnik(os.path.basename(k)) == ".git":
        return f"`{ks.forma}` skasuje historię repozytorium {pokaz}"
    if os.path.lexists(os.path.join(p, ".git")):
        return f"`{ks.forma}` skasuje całe repozytorium git {pokaz} (projekt z historią)"
    zagniezdzone = _repo_w_srodku(p)
    if zagniezdzone:
        return f"`{ks.forma}` skasuje {pokaz}, a w środku jest repozytorium git {_pokaz(zagniezdzone)}"
    return None


def _rada_kasowania(kasowania: List[_Kasowanie], m: _Miejsca) -> str:
    rady: List[str] = []
    formy = {k.forma for k in kasowania}
    if any(f.startswith("git ") for f in formy):
        rady.append("przy git zamiast reset --hard i clean użyj `git stash` albo nowej gałęzi, a zamiast push --force "
                    "zwykłego push albo nowej gałęzi")
    if any(k.rodzaj == "oproznij" for k in kasowania):
        rady.append("chroniony plik zmieniaj konkretnymi liniami (patch) albo dopisuj (`>>`), nie opróżniaj go")
    if any(k.rodzaj == "plik" for k in kasowania):
        rady.append("chroniony plik (dane Jarva, ~/.ssh, pliki startowe powłoki) zostaw, a zbędny opisz właścicielowi "
                    "jednym zdaniem ze ścieżką, to usunie go sam")
    if any(k.sciezki is None for k in kasowania):
        rady.append("podaj jawne ścieżki (bez zmiennych, $(…), xargs i globów spoza projektu)")
    rady.append("skasuj konkretne pliki albo wyniki budowania w projekcie (node_modules, dist, .svelte-kit, "
                "__pycache__) po ścieżce")
    if m.bez_czl == "kanban":
        rady.append("a jeśli naprawdę trzeba usunąć całość, zatrzymaj kartę: kanban_block(kind=\"needs_input\", "
                    "reason=\"potrzebne kasowanie …: zrobi je właściciel\")")
    elif m.bez_czl == "podagent":
        rady.append("a jeśli naprawdę trzeba usunąć całość, opisz to w wyniku: właściciel zrobi to sam")
    else:
        rady.append("a jeśli naprawdę trzeba usunąć całość, poproś właściciela, żeby zrobił to sam")
    return "; ".join(rady) + "."


def _straznik_kasowania(narzedzie: str, kasowania: List[_Kasowanie], m: _Miejsca) -> Optional[Dict[str, str]]:
    """Blokada masowego kasowania i niszczenia danych: w każdym trybie, z człowiekiem i pod YOLO, bez pytania.
    Najpierw zabicie pracownika karty albo Hermesa (strażnik pracowników, zbierany razem z kasowaniami)."""
    zabicia = [k for k in kasowania if k.rodzaj == "zabij"]
    if zabicia:
        return _straznik_zabijania(narzedzie, zabicia, m)
    kasowania = [k for k in kasowania if k.rodzaj != "zabij_xargs"]
    if not kasowania:
        return None
    kr = _krytyczne(m)
    zle = [(k, p) for k in kasowania for p in [_powod_kasowania(k, kr)] if p]
    if not zle:
        return None
    powody = "; ".join(dict.fromkeys(p for _, p in zle[:3])) + (f" (i {len(zle) - 3} innych)" if len(zle) > 3 else "")
    kontekst = KONTEKSTY.get(m.bez_czl or "", "pełny (YOLO)" if m.yolo else f"tryb {m.tryb} z człowiekiem")
    logger.warning("jarvo-zgody: zablokowane kasowanie (%s, %s): %s", narzedzie, kontekst, _maskuj(powody)[:600])
    return _blok(f"masowe kasowanie albo zniszczenie danych ({narzedzie}): {_maskuj(powody)}. Ta blokada działa w "
                 "każdym trybie (z człowiekiem, na karcie, w rutynie i pod YOLO) i nie da się jej zatwierdzić. "
                 f"Co zrobić: {_rada_kasowania([k for k, _ in zle], m)}")


def _kasowania_zapisu(narzedzie: str, args: Dict[str, Any], baza: Optional[str], dom: str) -> List[_Kasowanie]:
    """write_file z pustą treścią, patch zastępujący (prawie) całą treść pustą i V4A `*** Delete File:`."""
    wynik: List[_Kasowanie] = []
    p = args.get("path")
    sciezka = _realna(p, baza) if isinstance(p, str) and p.strip() else None
    if narzedzie == "write_file":
        tresc = args.get("content")
        if sciezka and isinstance(tresc, str) and not tresc.strip():
            wynik.append(_Kasowanie("write_file z pustą treścią", "oproznij", [sciezka], p, pusto=True))
        return wynik
    stare, nowe = args.get("old_string"), args.get("new_string")
    if sciezka and isinstance(stare, str) and stare.strip() and (nowe is None or (isinstance(nowe, str)
                                                                                  and not nowe.strip())):
        try:
            rozmiar = os.path.getsize(sciezka)
        except OSError:
            rozmiar = -1
        if rozmiar >= 0 and len(stare.encode("utf-8", "surrogatepass")) * 2 >= rozmiar:
            wynik.append(_Kasowanie("patch usuwający treść", "oproznij", [sciezka], p, pusto=True))
    latka = args.get("patch")
    if isinstance(latka, str):
        for nazwa in re.findall(r"^\*\*\*\s*Delete\s+File:\s*(.+?)\s*$", latka.replace("\r\n", "\n"), re.M):
            r = _realna(nazwa, baza)
            if r:
                wynik.append(_Kasowanie("patch *** Delete File", "oproznij", [r], nazwa, pusto=True))
    return wynik


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


def _nagrywanie_ekranu(narzedzie: str, tekst: str) -> Optional[Dict[str, str]]:
    """Block dla surowego nagrywania ekranu (NAGRYWANIE_EKRANU) z radą: nagraj.py ze skilla praca-na-ekranie."""
    if not NAGRYWANIE_EKRANU.search(tekst[:_MAX_POLECENIA]):
        return None
    logger.warning("jarvo-zgody: zablokowane surowe nagrywanie ekranu (%s)", narzedzie)
    return _blok(f"surowe nagrywanie ekranu ({narzedzie}: ffmpeg x11grab, gdigrab, avfoundation albo inny program "
                 "nagrywający) jest wyłączone w każdym trybie: nagrywa pulpit bez końca, także pętlę nieudanych kroków. "
                 f"Nagrywaj tylko przez `python3 \"{NAGRAJ}\"` (skill praca-na-ekranie): `start \"<krok>\"` przed "
                 "krokiem, który ma się udać, `stop` po jego potwierdzeniu, `film` na końcu. Skrypt nagrywa krótkie "
                 "odcinki, sam kończy przy odmowie Komputera albo bez ruchu na ekranie, a film skleja tylko z udanych "
                 "kroków. Przy pierwszej blokadzie przestań nagrywać.")


# 26.11 Hacker zaczął weryfikację maila HF na telefonie first i przeskoczył (surowym adb) na third i second, a każdy
# telefon ma inne konta Google: zadanie (karta kanbana albo rozmowa) działa na pierwszym telefonie, na którym coś
# zrobiło. Odczyt (ekran, lista aplikacji, dumpsys, getprop) nie wiąże i nie jest blokowany (27.11: Jarvo nie mógł
# sprawdzić, czy na którymś telefonie jest OLX). W rozmowie wiązanie wygasa po 30 min bez działania na telefonie.
TELEFON_DOMYSLNY = "first"
TELEFON_AKCJE = frozenset({f"mcp__{TELEFON}__act", f"mcp__{TELEFON}__batch", f"mcp__{TELEFON}__run_recipe"})
_ADB = re.compile(r"\badb\b|ANDROID_SERIAL", re.I)
_ADB_AKCJA = re.compile(r"\binput\s|\bam\s+(?:start|broadcast|force-stop|kill|startservice)\b|\bmonkey\b|\bsendevent\b"
                        r"|\bsettings\s+put\b|\bcontent\s+(?:insert|update|delete|call)\b|\bpm\s+(?:install|grant|enable)\b"
                        r"|\s(?:push|install|install-multiple)\s|\bsvc\s|\bcmd\s+(?:connectivity|wifi|statusbar|notification)\b", re.I)
_IP = re.compile(r"(?<![\d.])\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?![\d.])")
_MAPA_TTL = 60.0
_WIAZANIE_ROZMOWY = 1800.0
_ZAJETY_S = 600.0                 # inne zadanie z krokiem na telefonie w tym czasie = telefon zajęty
_MAPA: Dict[str, Any] = {"t": 0.0, "ip": {}}       # IP adb telefonu → nazwa, plus `wlaczony` i `przydzialy`
_TELEFON_ZADANIA: "collections.OrderedDict[str, Tuple[str, float]]" = collections.OrderedDict()


def _stan_telefonow() -> Dict[str, Any]:
    """<stan>/telefon.json (ten sam plik co `stan_telefonu` w jarvo/telefon.py; <stan> = <korzeń>/stan obok
    <korzeń>/dane): `ip` = IP adb telefonu floty → nazwa (z `adresy`, {"first": "100.x.y.z:5555"}), `wlaczony`,
    `przydzialy` (`profile`: agent biznesowy → telefon). Cache _MAPA_TTL s."""
    teraz = time.monotonic()
    if _MAPA["ip"] and teraz - _MAPA["t"] < _MAPA_TTL:
        return _MAPA
    mapa: Dict[str, str] = {}
    wlaczony, przydzialy = False, {}
    try:
        plik = _korzen_danych(_hermes_home()).parent / "stan" / "telefon.json"
        dane = json.loads(plik.read_text(encoding="utf-8"))
        for nazwa, adres in (dane.get("adresy") or {}).items():
            ip = str(adres).rsplit(":", 1)[0].strip()
            if ip:
                mapa[ip] = str(nazwa)
        wlaczony = dane.get("wlaczony") is True
        przydzialy = {str(p): str(t) for p, t in (dane.get("profile") or {}).items()}
    except (OSError, ValueError, AttributeError):
        pass
    _MAPA.update(t=teraz, ip=mapa, wlaczony=wlaczony, przydzialy=przydzialy)
    return _MAPA


def _mapa_ip() -> Dict[str, str]:
    """IP adb telefonu floty → nazwa (_stan_telefonow)."""
    return _stan_telefonow()["ip"]


def _telefony_wywolania(tool_name: str, args: Dict[str, Any]) -> List[str]:
    """Telefony floty, na których wywołanie coś robi (nazwa); [] = nie dotyczy telefonu albo tylko odczyt."""
    if tool_name.startswith(f"mcp__{TELEFON}__"):
        if tool_name not in TELEFON_AKCJE:
            return []
        p = str(args.get("phone") or "").strip()
        return [p or os.environ.get("PHONEUSE_ONLY", "").strip() or TELEFON_DOMYSLNY]
    pole = {"terminal": "command", "execute_code": "code", "process_manage": "data"}.get(tool_name)
    tekst = str(args.get(pole) or "")[:_MAX_POLECENIA] if pole else ""
    if not _ADB.search(tekst) or not _ADB_AKCJA.search(tekst):
        return []
    mapa = _mapa_ip()
    wynik: List[str] = []
    for ip in _IP.findall(tekst):
        if ip in mapa and mapa[ip] not in wynik:
            wynik.append(mapa[ip])
    return wynik


def _klucz_zadania(task_id: str, session_id: str) -> str:
    karta = os.environ.get("HERMES_KANBAN_TASK", "").strip()
    return f"karta:{karta}" if karta else f"sesja:{session_id or task_id or 'default'}"


def _zajmij_zasob(zasob: str, klucz: str) -> Optional[Tuple[str, int]]:
    """Telefon i pulpit prowadzą jedno zadanie naraz: <stan>/telefon-zadania.json trzyma ostatnie działające zadanie
    każdego zasobu (nazwa telefonu albo "pulpit"; plik, bo karty kanbana to osobne procesy, a oś floty pokazuje z niego
    zajęte urządzenia). Inne zadanie z krokiem w ostatnich _ZAJETY_S s = (jego klucz, ile s temu); inaczej zasób
    przechodzi na to zadanie i None. Błąd pliku nie blokuje."""
    telefon = zasob
    try:
        plik = _korzen_danych(_hermes_home()).parent / "stan" / "telefon-zadania.json"
        try:
            dane = json.loads(plik.read_text(encoding="utf-8"))
            dane = dane if isinstance(dane, dict) else {}
        except (OSError, ValueError):
            dane = {}
        teraz, jest = time.time(), dane.get(telefon)
        if isinstance(jest, dict) and jest.get("klucz") != klucz:
            temu = teraz - float(jest.get("t") or 0)
            if 0 <= temu < _ZAJETY_S:
                return str(jest.get("klucz")), int(temu)
        dane[telefon] = {"klucz": klucz, "t": teraz}
        plik.parent.mkdir(parents=True, exist_ok=True)
        tmp = plik.with_name(f"{plik.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(dane), encoding="utf-8")
        os.replace(tmp, plik)
    except (OSError, ValueError, TypeError):
        pass
    return None


def _jeden_telefon(tool_name: str, args: Dict[str, Any], task_id: str, session_id: str) -> Optional[Dict[str, str]]:
    """Pierwszy telefon, na którym zadanie coś zrobiło, wiąże je (karta kanbana: do końca, rozmowa: do 30 min bez
    działania na telefonie); działanie na innym telefonie = block. Telefon, na którym inne zadanie działało
    w ostatnich _ZAJETY_S s, też = block (28.11: SMS Jarva i test OLX stukały naraz w first i zgubiły się oba)."""
    telefony = _telefony_wywolania(tool_name, args)
    if not telefony:
        return None
    klucz, teraz = _klucz_zadania(task_id, session_id), time.monotonic()
    with _ZAMEK:
        x, kiedy = _TELEFON_ZADANIA.get(klucz) or (None, 0.0)
        if x is None or (klucz.startswith("sesja:") and teraz - kiedy > _WIAZANIE_ROZMOWY):
            x = telefony[0]
        if all(t == x for t in telefony):
            zajety = _zajmij_zasob(x, klucz)
            if zajety is not None:
                logger.warning("jarvo-zgody: telefon %s zajęty przez %s (%s s temu)", x, zajety[0], zajety[1])
                return _blok(f"Telefon {x} prowadzi teraz inne zadanie ({zajety[0]}, ostatni krok {zajety[1]} s temu), "
                             "a dwa zadania na jednym telefonie przestawiają sobie ekran, więc nic na nim nie rób: "
                             f"ponów za kilka minut, a gdy sprawa jest pilna, napisz JARO jednym zdaniem, że {x} "
                             "jest zajęty.")
            _TELEFON_ZADANIA[klucz] = (x, teraz)
            _TELEFON_ZADANIA.move_to_end(klucz)
            while len(_TELEFON_ZADANIA) > 256:
                _TELEFON_ZADANIA.popitem(last=False)
            return None
    logger.warning("jarvo-zgody: przeskok telefonu %s -> %s (%s)", x, telefony, tool_name)
    return _blok(f"To zadanie działa na telefonie {x}; na innym telefonie nie działasz bez wyraźnego polecenia JARO "
                 f"(odczyt, np. lista aplikacji albo ekran, jest wolny), więc dokończ na {x} albo zapytaj go jednym zdaniem.")


PULPIT_ODCZYT = frozenset({"zobacz", "okna", "czekaj"})


def _jeden_pulpit(tool_name: str, args: Dict[str, Any], task_id: str, session_id: str) -> Optional[Dict[str, str]]:
    """Pulpit (ekran :0 serwera) jak telefon: krok, który klika albo pisze, gdy inne zadanie działało na nim w ostatnich
    _ZAJETY_S s = block; odczyt (`zobacz`, `okna`, `czekaj`) jest wolny."""
    if tool_name != "pulpit":
        return None
    akcje = {str(k.get("akcja")) for k in args.get("kroki") or [] if isinstance(k, dict)} or {str(args.get("akcja") or "zobacz")}
    if akcje <= PULPIT_ODCZYT:
        return None
    zajety = _zajmij_zasob("pulpit", _klucz_zadania(task_id, session_id))
    if zajety is None:
        return None
    logger.warning("jarvo-zgody: pulpit zajęty przez %s (%s s temu)", zajety[0], zajety[1])
    return _blok(f"Pulpit prowadzi teraz inne zadanie ({zajety[0]}, ostatni krok {zajety[1]} s temu), a dwa zadania na "
                 "jednym ekranie przestawiają sobie okna i kursor, więc nic na nim nie klikaj: ponów za kilka minut, "
                 "a gdy sprawa jest pilna, napisz JARO jednym zdaniem, że pulpit jest zajęty.")


# 26.11 20:40 Jarvo wpisał w formularz weryfikacji SMS prywatny numer JARO: numery z listy sha256 ostatnich 9 cyfr
# (<korzeń danych>/jarvo/konfig/prywatne-numery.json) blokujemy w każdym trybie, także pod YOLO.
PRYWATNE_NUMERY = ("jarvo", "konfig", "prywatne-numery.json")
# 27.11 JARO zdecydował, że prywatny numer jest obowiązkowy w zgłoszeniach Hackera i Bigshorta na hackathony i granty.
PROFILE_PRYWATNEGO_NUMERU = frozenset({"jarvo-hacker", "jarvo-bigshort"})
NARZEDZIA_TEKSTU = frozenset({"terminal", "execute_code", "process_manage", "browser_type", "browser_fill",
                              "send_message", "computer_use", "komputer", "pulpit", "write_file", "patch"})
_CIAG_CYFR = re.compile(r"\d[\d\s().\-]{7,}\d")
_NUMERY_CACHE: Dict[str, Tuple[Tuple[int, int], frozenset]] = {}


def _hashe_prywatnych() -> frozenset:
    plik = _korzen_danych(_hermes_home()).joinpath(*PRYWATNE_NUMERY)
    try:
        st = plik.stat()
    except OSError:
        return frozenset()
    sygn = (st.st_mtime_ns, st.st_size)
    stare = _NUMERY_CACHE.get(str(plik))
    if stare and stare[0] == sygn:
        return stare[1]
    try:
        lista = json.loads(plik.read_text(encoding="utf-8")).get("sha256_9") or []
        hashe = frozenset(str(h).strip().lower() for h in lista if str(h).strip())
    except (OSError, ValueError, AttributeError):
        hashe = frozenset()
    _NUMERY_CACHE[str(plik)] = (sygn, hashe)
    return hashe


def _prywatny_numer(tool_name: str, args: Dict[str, Any]) -> Optional[Dict[str, str]]:
    if tool_name not in NARZEDZIA_TEKSTU and not tool_name.startswith(f"mcp__{TELEFON}__"):
        return None
    if _profil(_hermes_home()) in PROFILE_PRYWATNEGO_NUMERU:
        return None
    hashe = _hashe_prywatnych()
    if not hashe:
        return None
    tekst = json.dumps(args, ensure_ascii=False, default=str)[:_MAX_POLECENIA]
    for mm in _CIAG_CYFR.finditer(tekst):
        cyfry = re.sub(r"\D", "", mm.group(0))
        if len(cyfry) >= 9 and hashlib.sha256(cyfry[-9:].encode()).hexdigest() in hashe:
            logger.warning("jarvo-zgody: zablokowany prywatny numer JARO (%s)", tool_name)
            return _blok("To prywatny numer JARO: podają go tylko Hacker i Bigshort w zgłoszeniach na hackathony i "
                         "granty; numer telefonu floty bierzesz ze spisu fleet/telefony.md.")
    return None


# 26.11 Hacker zrobił `adb -s … shell pm clear com.android.chrome` i skasował loginy Chrome, a o 21:10 tryb
# samolotowy przez adb odciął second od sieci: takie polecenia adb blokujemy w każdym trybie.
_ADB_KONTEKST = re.compile(r"\badb\b|ANDROID_SERIAL|-s\s+\S+\s+shell\b", re.I)
ADB_NISZCZACE = re.compile(
    r"\bpm\s+(?:clear|uninstall|disable(?:-user)?|hide|suspend|reset-permissions|revoke)\b|"
    r"\bcmd\s+package\s+(?:clear|uninstall|disable(?:-user)?|hide|suspend)\b|"
    r"\badb\b[^;&|\n]*?\buninstall\b|\bshell\b[^;&|\n]*?(?<![\w.-])rm(?![\w.-])|"
    r"\bwipe\b|\brecovery\b|\bsettings\s+delete\b|\bcmd\s+appops\s+reset\b|"
    r"\bcmd\s+connectivity\s+airplane-mode\s+enable\b|\bsettings\s+put\s+global\s+airplane_mode_on\s+1\b|"
    r"\bsvc\s+wifi\s+disable\b|\bcmd\s+wifi\s+set-wifi-enabled\s+disabled\b", re.I)


def _adb_niszczace(tool_name: str, args: Dict[str, Any]) -> Optional[Dict[str, str]]:
    pole = {"terminal": "command", "execute_code": "code", "process_manage": "data"}.get(tool_name)
    tekst = str(args.get(pole) or "")[:_MAX_POLECENIA] if pole else ""
    if not (_ADB_KONTEKST.search(tekst) and ADB_NISZCZACE.search(tekst)):
        return None
    logger.warning("jarvo-zgody: zablokowane niszczące polecenie adb (%s)", tool_name)
    return _blok("Czyszczenie danych, odinstalowanie, wyłączenie aplikacji i kasowanie plików na telefonie floty albo "
                 "to, co odcina telefon od sieci, tylko na wyraźne polecenie JARO: zapytaj go jednym zdaniem.")


# 27.11 Jarvo czytał Sklep Play surowym `uiautomator dump` z grepem, wziął planszę „Complete account setup” za płatność
# i nie przewinął do „Skip”; w 7 dni 377 kroków adb obok PhoneUse. Adb, które steruje ekranem telefonu floty albo go
# czyta, idzie do narzędzia telefonu (bramka, paragon, cały ekran z flagami), gdy ciało PhoneUse tego telefonu odpowiada
# i profil ma ten telefon w serwerze `phone`; bez ciała adb działa jak dawniej. Instalacja, pm list, dumpsys, getprop
# i logcat zostają wolne. Odpowiedź ciała (GET /ping bez tokenu, ~0,15 s) pamiętamy, żeby nie spowalniać poleceń.
_ODST = r"['\"]?(?:\s*,\s*|\s+)['\"]?"                  # odstęp w powłoce albo w liście argumentów (subprocess)
ADB_EKRAN = re.compile(
    rf"\binput{_ODST}(?:-d{_ODST}\S+?{_ODST})?(?:tap|swipe|text|keyevent|press|roll|draganddrop|motionevent|"
    r"keycombination|touchscreen|touchpad|touchnavigation|mouse|keyboard|stylus|gamepad|dpad|trackball|joystick)\b|"
    rf"\buiautomator{_ODST}dump\b|\bscreencap\b|\bam{_ODST}start(?:-activity)?\b|\bmonkey\b", re.I)
_SERIAL_ADB = re.compile(r"\badb\b[^;&|\n]*?\s-s\s*['\"]?([^\s'\";&|)]+)|\bANDROID_SERIAL\s*=\s*['\"]?([^\s'\";&|)]+)",
                         re.I)
PORT_CIALA = 18888                 # ciało PhoneUse na adresie Tailscale telefonu (PHONEUSE docs/body-api.md, sekcja 3)
_CIALO_TIMEOUT = 0.8
_CIALO_ZYWE_TTL = 60.0
_CIALO_MARTWE_TTL = 15.0
_CIALA: Dict[str, Tuple[bool, float]] = {}


def _telefony_adb(tekst: str) -> List[str]:
    """Telefony floty, w które celuje polecenie adb: po IP z telefon.json; bez IP i bez jawnego serialu (adb bez -s,
    serial w zmiennej) każdy telefon floty; jawny inny serial (emulator, obcy telefon) = []."""
    mapa = _mapa_ip()
    trafione = list(dict.fromkeys(mapa[ip] for ip in _IP.findall(tekst) if ip in mapa))
    if trafione:
        return trafione
    if any("$" not in s for m in _SERIAL_ADB.finditer(tekst) for s in m.groups() if s):
        return []
    return list(dict.fromkeys(mapa.values()))


def _telefony_profilu() -> frozenset:
    """Telefony, które ten profil ma w serwerze MCP `phone` (jarvo/telefon.py): jarvo wszystkie, agent biznesowy
    swój przydział, przy wyłączonym telefonie żaden."""
    st = _stan_telefonow()
    if not st.get("wlaczony"):
        return frozenset()
    profil = _profil(_hermes_home())
    if profil == "jarvo":
        return frozenset(st["ip"].values())
    t = (st.get("przydzialy") or {}).get(profil)
    return frozenset({t}) if t else frozenset()


def _cialo_odpowiada(nazwa: str) -> bool:
    """Ciało PhoneUse telefonu odpowiada na GET /ping (bez tokenu) i ma token; wynik pamiętany 60 s, brak 15 s."""
    ip = next((i for i, n in _mapa_ip().items() if n == nazwa), None)
    if not ip:
        return False
    teraz = time.monotonic()
    with _ZAMEK:
        hit = _CIALA.get(nazwa)
    if hit and teraz - hit[1] < (_CIALO_ZYWE_TTL if hit[0] else _CIALO_MARTWE_TTL):
        return hit[0]
    import urllib.request
    zywe = False
    try:
        otwieracz = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with otwieracz.open(f"http://{ip}:{PORT_CIALA}/ping", timeout=_CIALO_TIMEOUT) as r:
            ping = json.loads(r.read(8192).decode("utf-8", "replace"))
        zywe = ping.get("service") == "PhoneUseBody" and ping.get("token_set") is not False
    except (OSError, ValueError, AttributeError):
        pass
    with _ZAMEK:
        _CIALA[nazwa] = (zywe, teraz)
    return zywe


def _adb_ekranu(tool_name: str, args: Dict[str, Any]) -> Optional[Dict[str, str]]:
    pole = {"terminal": "command", "execute_code": "code", "process_manage": "data"}.get(tool_name)
    tekst = str(args.get(pole) or "")[:_MAX_POLECENIA] if pole else ""
    if not (_ADB.search(tekst) and ADB_EKRAN.search(tekst)):
        return None
    wolno = _telefony_profilu()
    zywe = [t for t in _telefony_adb(tekst) if t in wolno and _cialo_odpowiada(t)]
    if not zywe:
        return None
    logger.warning("jarvo-zgody: surowe adb ekranu przy działającym ciele PhoneUse %s (%s)", zywe, tool_name)
    t = zywe[0]
    return _blok(f"Ciało PhoneUse telefonu {t} działa, więc ekran czytasz i sterujesz nim narzędziem telefonu z "
                 f"phone=\"{t}\" (`mcp__phone__screen`, `act`, `batch`, `wait`, `shot`; `am start` to `act` `open` "
                 "z `url` albo `package`, pętla w skillu `telefon`), a nie surowym adb (input, uiautomator dump, "
                 "screencap, am start, monkey), bo ono omija bramkę, paragon i cały ekran z flagami; instalacja APK, "
                 "`pm list`, `dumpsys`, `getprop` i `logcat` przez adb są wolne.")


def _blok_werdyktow(werdykty: List[_Werdykt], m: _Miejsca, co: str) -> Dict[str, str]:
    flota = [w for w in werdykty if w.powod.startswith(KOD_FLOTY)]
    if flota:
        opisy = ", ".join(dict.fromkeys(w.powod.split(": ", 1)[-1] for w in flota))
        logger.warning("jarvo-zgody: zablokowany zapis w kodzie floty (%s): %s", opisy, _maskuj(_lista(flota))[:300])
        return _blok(f"{_lista(flota)} to {KOD_FLOTY} ({opisy}). Zapis tutaj znika przy aktualizacji floty i omija skan "
                     "bezpieczeństwa, więc nie robisz go i nie pytasz o niego właściciela. Zmiana floty (nowy albo "
                     "zmieniony skill, wtyczka, config agenta) = zlecenie dla Claude Code: dopisz `- [ ] data · co · po "
                     f"co · plik` w {_pokaz(os.path.join(m.misje, ZLECENIE_FLOTY))} (repo JARVO, skan bezpieczeństwa, "
                     "wdrożenie) i powiedz właścicielowi jednym zdaniem, że zlecenie czeka. Lekcję na następny raz "
                     "zapisz przez skill_manage (poczekalnia skilli).")
    konfig = [w for w in werdykty if w.powod == "config.yaml"]
    if konfig:
        return _blok(f"{_lista(konfig)} to konfiguracja Hermesa (zgody, modele, klucze). Agent nie zmienia jej w żadnym "
                     "trybie; zmianę robi właściciel (`jarvo`, `hermes config`).")
    czeka = [w for w in werdykty if w.powod == HERMES_CZEKA]
    if czeka:
        logger.warning("jarvo-zgody: zablokowany zapis, o który Hermes pytałby człowieka: %s", _maskuj(_lista(czeka)))
        return _blok(f"o zapis {_lista(czeka)} Hermes pyta człowieka i czekałby na zgodę do 5 min, a w trybie auto nic "
                     "nie czeka na zgodę poza płatnością, więc zapisz proponowaną treść obok jako plik roboczy i powiedz "
                     "właścicielowi jednym zdaniem, co i gdzie ma wkleić.")
    if m.bez_czl:
        powody = "; ".join(dict.fromkeys(w.powod for w in werdykty))
        return _blok(f"{KONTEKSTY.get(m.bez_czl, m.bez_czl)} działa bez człowieka, więc nie ma kogo zapytać o zgodę na "
                     f"{co} {_lista(werdykty)} ({powody}). {_porada_bez_czlowieka(m)}")
    powody = ", ".join(dict.fromkeys(w.powod.replace("chronione: ", "") for w in werdykty))
    instrukcje = any(_skladnik(os.path.basename(w.sciezka)) in PLIKI_INSTRUKCJI for w in werdykty)
    return _blok(f"{_lista(werdykty)} to chronione miejsce ({powody}), a w trybie pełnym (YOLO) Hermes zatwierdza "
                 "wszystko sam, więc nie da się o nie zapytać. Wyłącz /yolo i ponów albo zrób to ręcznie."
                 + (" Pliki instrukcji zmieniaj przez write_file albo patch: o nie Hermes pyta zawsze." if instrukcje else ""))


# Hermes nie pozwala wtyczce ukryć przycisku „Always” (tools/approval.py:1095-1120 request_tool_approval woła bramkę
# bez permanent_capable), a nasz rule_key to narzędzie + folder + skrót ścieżek (write_file, patch) albo polecenia
# (terminal): „Always” i „Session” obejmują tylko ten sam plik albo to samo polecenie. 14.11 21:21–21:26 właściciel
# klikał „Always” osiem razy i prośby wracały (każdy nowy plik to nowa prośba), więc przy powodzie „zawsze pytaj”
# mówimy to w treści prośby.
STALA_ZGODA = (" Stała zgoda tu nie działa: o chronione miejsce pytam przy każdym nowym pliku i poleceniu, a „Always” "
               "obejmie tylko ten sam plik albo to samo polecenie.")


def _prosba(narzedzie: str, m: _Miejsca, opis: str, tresc_klucza: str, *, zawsze: bool = False) -> Dict[str, str]:
    tryb = "pełny" if m.yolo else m.tryb
    uwaga = STALA_ZGODA if zawsze else ""
    return {"action": "approve", "rule_key": _klucz_reguly(narzedzie, m, tresc_klucza),
            "message": _maskuj(f"jarvo-zgody (tryb {tryb}): {opis}")[:400 - len(uwaga)] + uwaga}


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
    return _prosba(narzedzie, m, f"{co} ({_opis_powodow(pytaj)})", tresc, zawsze=any(w.zawsze for w in pytaj))


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
    kasowania: List[_Kasowanie] = []
    a = _analizuj_terminal(polecenie, baza, dom, kasowania)
    straznik = _straznik_kasowania("terminal", kasowania, m)
    if straznik:
        return straznik   # masowe kasowanie: w każdym trybie, przed zgodami Hermesa i command_allowlist
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
    if m.tryb == "auto":  # auto: chronione miejsca przechodzą (_ocen_sciezke), Hermes nie czeka na człowieka
        return None if m.yolo else _bez_czekania("terminal", polecenie, m)
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
    return _prosba("terminal", m, f"polecenie `{pokaz}` ({'; '.join(powody)})", polecenie.strip(),
                   zawsze=bool(zawsze))


def _bez_czekania(narzedzie: str, tresc: str, m: _Miejsca) -> Optional[Dict[str, str]]:
    """Tryb auto z człowiekiem (decyzja 27.11): polecenie terminala albo execute_code, o które Hermes zapytałby człowieka
    po ocenie strażnika smart, wtyczka rozstrzyga od razu tym samym strażnikiem. APPROVE = zgoda w Hermesie dla wzorca
    (następne takie wywołanie wtyczka ocenia od nowa), DENY = blokada z radą, ESCALATE albo brak oceny = prośba tylko
    przy płatności albo zakupie, inaczej blokada z radą. Nic nie czeka approvals.timeout (300 s) na przycisk zgody."""
    ocena = _hermes_zapyta(narzedzie, tresc)
    if not ocena:
        return None
    sesja, klucz, opis = ocena
    polecenie = tresc if narzedzie == "terminal" else f"execute_code <<'PY'\n{tresc}\nPY"   # jak approval.py:1283
    werdykt = _smart_werdykt(polecenie, opis, klucz, sesja)
    if werdykt == "approve":
        _hermes_przepusc(sesja, klucz)
        return None
    pokaz = _poczatek(tresc, 120) if narzedzie == "terminal" else f"execute_code ({tresc.count(chr(10)) + 1} linii)"
    if werdykt != "deny" and PLATNOSC.search(tresc[:_MAX_POLECENIA]):
        _hermes_przepusc(sesja, klucz)        # o płatność pyta wtyczka, Hermes nie pyta drugi raz
        return _prosba(narzedzie, m, f"płatność albo zakup ({opis}): `{pokaz}`. Zgoda = Twoje „tak” dla tego jednego "
                       "wywołania.", f"{tresc}\n{os.urandom(8).hex()}")
    logger.warning("jarvo-zgody: strażnik smart: %s dla %s (%s), blokuję zamiast czekać na zgodę", werdykt, narzedzie,
                   _maskuj(pokaz))
    if werdykt == "deny":
        return _blok(f"strażnik smart uznał `{pokaz}` za niszczące ({opis}), więc nie uruchamiam tego, tylko zrób to "
                     "bezpieczniej (jawne ścieżki w katalogu roboczym, `git stash` zamiast reset --hard, kopia przed "
                     "zmianą) albo poproś właściciela jednym zdaniem, żeby zrobił to sam.")
    return _blok(f"strażnik smart nie ocenił `{pokaz}` ({opis}), a w trybie auto nic nie czeka na zgodę poza płatnością, "
                 "więc rozbij to na prostsze kroki (skrypt zapisz do pliku i uruchom go po ścieżce), a płatność albo "
                 "zakup opisz właścicielowi jednym zdaniem.")


def _potwierdza(v: Any) -> bool:
    """Wartość `confirm`, którą telefon może uznać za tak (niepewna też: lepiej zapytać)."""
    return not (v is None or v is False or (isinstance(v, (int, float)) and v == 0)
                or str(v).strip().lower() in _NIE)


def _z_potwierdzeniem(x: Any, glebokosc: int = 0) -> bool:
    """Czy w argumentach act/batch jest `confirm` (na wierzchu, w `args` albo w którymś kroku batch, także w JSON
    podanym jako napis). Zbyt głęboko = tak (fail-closed)."""
    if glebokosc > 8:
        return True
    if isinstance(x, str) and x.strip()[:1] in ("{", "["):
        try:
            return _z_potwierdzeniem(json.loads(x), glebokosc + 1)
        except ValueError:
            return "confirm" in x.lower()
    if isinstance(x, dict):
        return any((str(k).strip().lower() == "confirm" and _potwierdza(v)) or _z_potwierdzeniem(v, glebokosc + 1)
                   for k, v in x.items())
    if isinstance(x, (list, tuple)):
        return any(_z_potwierdzeniem(v, glebokosc + 1) for v in x)
    return False


def _zgoda_karty_kanbana() -> bool:
    """Karta pracownika (HERMES_KANBAN_TASK) ma poprawną linię `ZGODA WŁAŚCICIELA` (komputer/zgoda_karty.py, kopiowany
    przy buildzie obok wtyczki; w repo katalog `komputer/`). Czyta treść karty z kanban.db tylko do odczytu; każdy
    błąd = brak zgody."""
    try:
        nazwa = "jarvo_zgoda_karty"
        zk = sys.modules.get(nazwa)
        if zk is None:
            plik = next((p for p in (_HERE / "zgoda_karty.py", _HERE.parent.parent / "komputer" / "zgoda_karty.py")
                         if p.is_file()), None)
            if plik is None:
                return False
            import importlib.util
            spec = importlib.util.spec_from_file_location(nazwa, plik)
            zk = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(zk)
            sys.modules[nazwa] = zk
        karta = os.environ.get("HERMES_KANBAN_TASK", "").strip()
        return bool(karta and zk.zgoda_z_tresci(zk.tresc_karty(karta)))
    except Exception:
        return False


def _telefon(tool_name: str, args: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """mcp__phone__act / batch z confirm: prośba z treścią akcji (zgoda człowieka = jego „tak”), bez człowieka
    i pod YOLO (Hermes zatwierdziłby sam) block. Bez confirm: None (bramka telefonu i tak zatrzyma ryzykowną akcję).
    Klucz reguły z losowym składnikiem: „zawsze” nie zapisze zgody na następne potwierdzenia."""
    if not _z_potwierdzeniem(args):
        return None
    akcja = _poczatek(json.dumps(args, sort_keys=True, ensure_ascii=False, default=str), 240)
    bez_czl = bez_czlowieka()
    if bez_czl == "kanban" and _zgoda_karty_kanbana():
        return None                 # polecenie właściciela w karcie (linia ZGODA WŁAŚCICIELA) jest jego „tak”
    if bez_czl:
        if bez_czl == "kanban":
            rada = ("Nie wysyłaj confirm; zatrzymaj kartę: kanban_block(kind=\"needs_input\", reason=\"potrzebne „tak” "
                    "właściciela dla akcji na telefonie: …\").")
        elif bez_czl == "podagent":
            rada = "Nie wysyłaj confirm; opisz akcję w wyniku dla agenta, który Cię wywołał: on zapyta właściciela."
        else:
            rada = "Nie wysyłaj confirm; opisz akcję w odpowiedzi, a zgodę da właściciel w czacie."
        return _blok(f"confirm=true na telefonie ({tool_name}) to „tak” człowieka dla tej jednej akcji, a "
                     f"{KONTEKSTY.get(bez_czl, bez_czl)} działa bez niego. {rada}")
    if _yolo():
        return _blok(f"confirm=true na telefonie ({tool_name}) wymaga „tak” człowieka, a w trybie pełnym (YOLO) Hermes "
                     "zatwierdza wszystko sam. Wyłącz /yolo i ponów.")
    tryb, _ = tryb_zgod()
    if tryb == "auto" and not PLATNOSC.search(json.dumps(args, ensure_ascii=False, default=str)):
        return None                 # auto: polecenie właściciela w rozmowie jest zgodą; płatność dalej pytamy
    m = _miejsca(tryb, None, False)
    return _prosba(tool_name, m, f"telefon: ryzykowna akcja z confirm=true (bramka needs_confirm telefonu): {akcja}. "
                   "Zgoda = Twoje „tak” dla tej jednej akcji.", f"{akcja}\n{os.urandom(8).hex()}")


# Werdykt na karcie (zakończenie, oddanie do oceny, poprawki, blokada) w trakcie pracy albo oceny wydaje tylko
# pracownik karty (tor review: osobny pracownik-sędzia). 12.11 Jarvo w czacie z właścicielem, budzony zdarzeniami
# tablicy (Hermes subskrybuje czat przy kanban_create w trybie notify+wake), oceniał te same karty co tor review:
# sprzeczne werdykty, wycofania i godzina wiadomości na Telegramie.
# Wyjątek: kanban_block karty `running` z rozmowy to zatrzymanie, nie ocena. 16.11 22:35 wtyczka go odmówiła
# (karta t_87d11e3a), a Jarvo zabił pracownika poleceniem kill i dyspozytor trzy razy uruchamiał kartę od nowa.
# Komentarz z rozmowy nie zatrzyma karty Jarva: pracownik pomija komentarze własnego profilu
# (tools/kanban_tools.py:574-612), a po blokadzie z rozmowy pracownika zamyka dyspozytor (reap_terminal_workers).
WERDYKTY_KART = frozenset({"kanban_complete", "kanban_request_review", "kanban_request_changes", "kanban_block"})
KARTA_W_TOKU = frozenset({"running", "review"})


def _status_karty(tid: str, tablica: Optional[str]) -> Optional[str]:
    """Status karty z bazy kanbana Hermesa; None, gdy nie da się go odczytać (wtedy nie blokujemy)."""
    try:
        from hermes_cli import kanban_db as kb
        from hermes_cli import kanban_db_connect as kbc
        with kbc.connect_closing(board=tablica) as conn:
            karta = kb.get_task(conn, tid)
        return getattr(karta, "status", None)
    except Exception:
        logger.debug("jarvo-zgody: nie odczytałem statusu karty %s", tid, exc_info=True)
        return None


def _werdykt_z_rozmowy(tool_name: str, args: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Rozmowa (bez HERMES_KANBAN_TASK) nie wydaje werdyktu na karcie, nad którą pracuje albo którą ocenia pracownik."""
    if os.environ.get("HERMES_KANBAN_TASK", "").strip():
        return None
    tid = str(args.get("task_id") or "").strip()
    if not tid:
        return None
    status = _status_karty(tid, str(args.get("board") or "").strip() or None)
    if status not in KARTA_W_TOKU or (tool_name == "kanban_block" and status == "running"):
        return None       # zatrzymanie karty w pracy z powodem: pracownika zamknie dyspozytor
    return _blok(f"karta {tid} jest w toku ({status}): pracuje nad nią albo ocenia ją pracownik karty (tor review). "
                 "Werdykt wydaje tylko on, rozmowa nie ocenia kart. Zdarzenie tablicy w rozmowie przemilcz ([SILENT]); "
                 "uwagę właściciela do karty przekaż przez kanban_comment, a kartę w pracy (running) zatrzymasz "
                 "przez kanban_block z powodem.")


# ------------------------------------------------------------------------------------------------ decyzje właściciela
# 16.11 23:10 Jarvo napisał w komentarzu karty t_87d11e3a „Decyzja Jarva: zaznaczyć NDA”, a 27 min później w raporcie
# misji „decyzja właściciela z 23:15”, choć właściciel od 22:49 do 23:36 nic nie napisał. Decyzję właściciela wolno
# zapisać tylko z jego słowami w cudzysłowie i czasem (godzina albo data); inaczej to decyzja agenta.
TEKSTY_KANBANA = {"kanban_comment": ("body",), "kanban_block": ("reason",), "kanban_complete": ("summary", "result"),
                  "kanban_request_review": ("summary",), "kanban_request_changes": ("reason",),
                  "kanban_create": ("title", "body"), "kanban_heartbeat": ("note",)}
_KTO_DECYDUJE = r"(?:w[łl]a[śs]ciciel\w*|u[żz]ytkownik\w*)"
_PRZYPISANIE_DECYZJI = re.compile(
    rf"\b(?:decyzj\w*|zgod\w*|polece\w*|wyb[oó]r\w*)\s+{_KTO_DECYDUJE}"
    rf"|\b{_KTO_DECYDUJE}\s+(?:(?!nie\b)\w+\s+){{0,2}}?(?:zdecydowa\w*|postanowi\w*|zgodzi\w*|zatwierdzi\w*|"
    r"wybra\w*|kaza\w*|poleci\w*|zleci\w*|potwierdzi\w*|pozwoli\w*|da\w*\s+zgod\w*)"
    r"|\bowner(?:'s)?\s+(?:decided|decision|approved|chose|confirmed)"
    rf"|\|\s*{_KTO_DECYDUJE}\s*(?=[|(])", re.I)      # kolumna „Kto” tabeli Decyzje w MISSION.md
# tuż przed: prośba o decyzję, pytanie, przeczenie albo warunek („czeka na decyzję właściciela”, „bez zgody …”)
_PROSBA_O_DECYZJE = re.compile(
    r"(?:\b(?:nie|bez|czy|do|na|o|jeśli|jeżeli|gdy|aż|until|without|no|needs?|awaiting)\s+"
    r"|\b(?:brak\w*|wymag\w*|potrzeb\w*|czeka\w*|oczekuj\w*|pytani\w*|pytam|zapyta\w*|prośb\w*|prosz\w*|proś\w*)"
    r"\s+(?:\w+\s+){0,2})$", re.I)
_CYTAT = re.compile(r"„[^„”“\n]{3,}[”“]|“[^”\n]{3,}”|\"[^\"\n]{3,}\"|«[^»\n]{3,}»")
_CZAS = re.compile(r"\b(?:[01]?\d|2[0-3])[:.][0-5]\d\b|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}\.\d{1,2}\.\d{2,4}\b")


def _decyzje_bez_cytatu(tekst: str, stary: str = "") -> List[str]:
    """Fragmenty, które przypisują decyzję właścicielowi bez jego cytatu („…”) i czasu w tym samym akapicie (do 300
    znaków od przypisania; w wierszu tabeli: w tym wierszu). Linie, które już są w `stary` (poprzednia treść pliku),
    pomijamy."""
    stare = {linia.strip() for linia in stary.splitlines() if linia.strip()}
    wynik: List[str] = []
    for m in _PRZYPISANIE_DECYZJI.finditer(tekst):
        s, e = m.span()
        if _PROSBA_O_DECYZJE.search(tekst[max(0, s - 40):s]):
            continue
        l0, l1 = tekst.rfind("\n", 0, s) + 1, tekst.find("\n", e)
        l1 = len(tekst) if l1 < 0 else l1
        if tekst[l0:l1].lstrip().startswith("|"):
            okno = tekst[l0:l1]
        else:
            a0, a1 = tekst.rfind("\n\n", 0, s), tekst.find("\n\n", e)
            okno = tekst[max(a0 + 1, s - 300):min(a1 if a1 >= 0 else len(tekst), e + 300)]
        if (_CYTAT.search(okno) and _CZAS.search(okno)) or tekst[l0:l1].strip() in stare:
            continue
        wynik.append(" ".join(tekst[max(l0, s - 40):min(l1, e + 40)].split()))
    return wynik


def _blok_przypisania(gdzie: str, fragmenty: List[str]) -> Dict[str, str]:
    profil = _profil(_hermes_home())
    ja = "decyzja Jarva" if profil in ("jarvo", "host") else f"decyzja agenta {profil}"
    pokaz = _maskuj(_poczatek(fragmenty[0], 120))
    logger.warning("jarvo-zgody: zablokowane przypisanie decyzji właścicielowi (%s): %s", gdzie, pokaz)
    return _blok(f"{gdzie} przypisuje decyzję właścicielowi bez jego słów w cudzysłowie i czasu: „{pokaz}”. Właściciel "
                 "zdecydował tylko to, co sam napisał: podaj jego cytat z godziną, np. `decyzja właściciela (16.11 "
                 "23:15): „tak, zaznacz NDA”`. Jeśli tego nie napisał, to Twoja decyzja: napisz `" + ja + ": …`, "
                 "a gdy potrzebne jest jego „tak”, zapytaj go (na karcie: kanban_block(kind=\"needs_input\", "
                 "reason=\"…\")). Ta blokada działa w każdym trybie.")


def _przypisanie_w_kanbanie(tool_name: str, args: Dict[str, Any]) -> Optional[Dict[str, str]]:
    teksty = [args.get(k) for k in TEKSTY_KANBANA[tool_name]]
    fragmenty = [f for t in teksty if isinstance(t, str) for f in _decyzje_bez_cytatu(t)]
    return _blok_przypisania(tool_name, fragmenty) if fragmenty else None


def _przypisanie_w_zapisie(tool_name: str, args: Dict[str, Any], m: _Miejsca, task_id: str
                           ) -> Optional[Dict[str, str]]:
    """write_file i patch w misjach albo skarbcu (MISSION.md, DLA-CLAUDE.md, raporty, notatki): nowe linie."""
    korzenie = [k for k in (_k_realny(m.misje), _k_realny(m.wiedza)) if k]
    baza = _baza(task_id)
    sciezki = [args.get("path")] if tool_name == "write_file" else sciezki_latki(args)
    realne = [r for p in sciezki if isinstance(p, str) and p.strip() for r in [_realna(p, baza)] if r]
    if not any(_wewnatrz(_klucz(r), k) for r in realne for k in korzenie):
        return None
    if tool_name == "write_file":
        nowy, stary = args.get("content"), ""
        try:
            if realne and os.path.isfile(realne[0]) and os.path.getsize(realne[0]) <= 2_000_000:
                stary = Path(realne[0]).read_text(encoding="utf-8", errors="replace")
        except OSError:
            stary = ""
    elif isinstance(args.get("patch"), str):
        linie = args["patch"].replace("\r\n", "\n").split("\n")
        nowy = "\n".join(x[1:] for x in linie if x.startswith("+"))
        stary = "\n".join(x[1:] for x in linie if x.startswith(("-", " ")))
    else:
        nowy, stary = args.get("new_string"), args.get("old_string")
    if not isinstance(nowy, str):
        return None
    fragmenty = _decyzje_bez_cytatu(nowy, stary if isinstance(stary, str) else "")
    return _blok_przypisania(f"{tool_name} {_pokaz(realne[0], 60)}", fragmenty) if fragmenty else None


# Strażnik rutyn (w każdym trybie, z człowiekiem, bez niego i pod YOLO; 26.11 właściciel: „nie może być więcej takich
# błędów” po 4 rodzajach raportów Bigshorta z prób i kopii rutyny): każdy przebieg rutyny trafia do Aktualizacji
# właściciela, więc `run` (przebieg na próbę) = block, a `create` rutyny próbnej albo o nazwie już istniejącej w profilu
# (także wstrzymanej) = block z radą: popraw albo wznów istniejącą.
RUTYNA_PROBNA = re.compile(r"\b(test\w*|prob[aye]\w*|próba|próbn\w*|sprawdz\w*|dry[ -]?run)\b", re.I)


def _rutyny_profilu() -> List[Dict[str, Any]]:
    home = os.environ.get("HERMES_HOME")
    try:
        dane = json.loads((Path(home) / "cron" / "jobs.json").read_text(encoding="utf-8")) if home else {}
    except (OSError, ValueError):
        return []
    jobs = dane.get("jobs") if isinstance(dane, dict) else dane
    return [j for j in jobs or [] if isinstance(j, dict)]


def _straznik_rutyn(args: Dict[str, Any]) -> Optional[Dict[str, str]]:
    akcja = str(args.get("action") or "").strip().lower()
    if akcja == "run":
        return _blok("rutyny nie uruchamiam na próbę: każdy przebieg trafia do Aktualizacji właściciela. Sprawdź prompt "
                     "i skrypty rutyny tutaj, tymi samymi poleceniami, a rutyna ruszy sama o swojej porze.")
    if akcja != "create":
        return None
    nazwa = str(args.get("name") or "").strip()
    if RUTYNA_PROBNA.search(nazwa):
        return _blok(f"rutyna próbna („{_pokaz(nazwa, 40)}”) dałaby raport w Aktualizacjach właściciela. Sprawdź prompt "
                     "i skrypty tutaj, a rutynę zakładaj od razu docelową.")
    takie = [j for j in _rutyny_profilu() if nazwa and str(j.get("name") or "").strip().casefold() == nazwa.casefold()]
    if takie:
        j = takie[0]
        stan = "wstrzymana" if j.get("enabled") is False or j.get("state") == "paused" else "włączona"
        return _blok(f"rutyna „{_pokaz(nazwa, 40)}” już jest ({stan}, job_id={j.get('id')}): druga dałaby drugi raport "
                     "w Aktualizacjach. Popraw ją przez cronjob_manage update albo resume z tym job_id.")
    return None


def _decyzja(tool_name: str, args: Dict[str, Any], task_id: str) -> Optional[Dict[str, str]]:
    yolo = _yolo()
    if yolo and (tool_name in NARZEDZIA_EKRANU or tool_name.startswith(f"mcp__{TELEFON}__")):
        return _blok("tryb pełny (YOLO) nie obejmuje ekranu ani telefonu: Komputer Jarva i telefon działałyby wtedy "
                     "bez ograniczeń. Uruchom czat bez --yolo albo wpisz /yolo, żeby je wyłączyć.")
    if tool_name in TELEFON_POTWIERDZENIA:
        return _telefon(tool_name, args)
    if tool_name in TEKSTY_KANBANA:
        przypisanie = _przypisanie_w_kanbanie(tool_name, args)
        if przypisanie:
            return przypisanie
    if tool_name in WERDYKTY_KART:
        return _werdykt_z_rozmowy(tool_name, args)
    if tool_name not in OBSLUGIWANE:
        return None
    if tool_name == "cronjob_manage":
        straznik = _straznik_rutyn(args)
        if straznik:
            return straznik
    bez_czl = bez_czlowieka()
    tryb, _ = tryb_zgod()
    m = _miejsca(tryb, bez_czl, yolo and not bez_czl)
    if tool_name in ("write_file", "patch"):
        straznik = (_straznik_kasowania(tool_name, _kasowania_zapisu(tool_name, args, _baza(task_id), _dom()), m)
                    or _przypisanie_w_zapisie(tool_name, args, m, task_id))
        if straznik:
            return straznik
    if tool_name == "write_file":
        p = args.get("path")
        return _zapis_plikow(tool_name, [p] if isinstance(p, str) and p.strip() else [], m, task_id)
    if tool_name == "patch":
        return _zapis_plikow(tool_name, sciezki_latki(args), m, task_id)
    if tool_name == "terminal":
        return _nagrywanie_ekranu(tool_name, str(args.get("command") or "")) or _terminal(args, m, task_id)
    nagrywanie = _nagrywanie_ekranu(tool_name, str(args.get("code") or "") if tool_name == "execute_code"
                                    else str(args.get("data") or "") if tool_name == "process_manage" else "")
    if nagrywanie:
        return nagrywanie
    kasowania: List[_Kasowanie] = []
    if tool_name == "execute_code":
        _kasowania_pythona(str(args.get("code") or ""), _baza(task_id), _dom(), kasowania, 0)
    elif tool_name == "process_manage" and isinstance(args.get("data"), str):
        _analizuj_terminal(args["data"], None, _dom(), kasowania)       # wejście procesu w tle (np. powłoki)
    straznik = _straznik_kasowania(tool_name, kasowania, m)
    if straznik:
        return straznik
    if tool_name == "execute_code":
        if bez_czl:
            return _blok(f"execute_code to dowolny kod, a {KONTEKSTY.get(bez_czl, bez_czl)} działa bez człowieka. "
                         f"Użyj terminala albo narzędzi plików w dozwolonych katalogach. {_porada_bez_czlowieka(m)}")
        kod = str(args.get("code") or "")
        if m.tryb == "auto":
            return None if yolo else _bez_czekania(tool_name, kod, m)
        if _hermes_pyta_o_kod() and not yolo:
            return None
        return _prosba(tool_name, m, f"uruchomienie kodu Pythona (execute_code, {kod.count(chr(10)) + 1} linii)", kod)
    akcja = str(args.get("action") or "").strip().lower()
    if tool_name == "process_manage":
        if akcja in PROCESY_ODCZYT or bez_czl or m.tryb == "auto":
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
        if m.tryb == "auto":
            return None
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
        tool_name, args = str(tool_name or ""), args if isinstance(args, dict) else {}
        wynik = (_prywatny_numer(tool_name, args) or _adb_niszczace(tool_name, args) or _adb_ekranu(tool_name, args)
                 or _decyzja(tool_name, args, str(task_id or "")))
        if not wynik or wynik.get("action") != "block":     # zablokowane wywołanie nie wiąże telefonu ani pulpitu
            wynik = (_jeden_telefon(tool_name, args, str(task_id or ""), str(session_id or ""))
                     or _jeden_pulpit(tool_name, args, str(task_id or ""), str(session_id or "")) or wynik)
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
        t = t if t in ("pytaj", "projekt", "auto") else None  # pełnego nie zapisujemy: działa tylko na sesję
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
    """(tryb, źródło): /tryb w tym procesie > JARVO_TRYB_ZGOD > plik stanu profilu > domyślny „auto”."""
    home = Path(home or _hermes_home())
    k = _klucz(str(home))
    with _ZAMEK:
        t = _TRYB_W_PROCESIE.get(k)
    if t:
        return t, "/tryb"
    t = _norm_tryb(_start()["tryb"])
    if t:
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
    linie.append("Zmień: /tryb auto · /tryb projekt · /tryb pytaj · /tryb pelny (= /yolo na tę sesję).")
    return "\n".join(linie)


def polecenie_tryb(raw_args: str = "") -> str:
    """/tryb [pytaj|projekt|pelny]: bez argumentu pokazuje stan, pytaj i projekt zapisuje w pliku profilu."""
    try:
        home = _hermes_home()
        arg = (raw_args or "").strip()
        if not arg or arg.lower() in ("status", "stan", "?"):
            return _opis_stanu(home)
        tryb = _norm_tryb(arg)
        if tryb in ("pytaj", "projekt", "auto"):
            _zapisz_tryb(home, tryb)
            with _ZAMEK:
                _TRYB_W_PROCESIE[_klucz(str(home))] = tryb
            dopisek = " Uwaga: YOLO jest włączone, więc Hermes nadal zatwierdza sam: wpisz /yolo, żeby je wyłączyć." \
                if _yolo() else ""
            return f"Tryb zgód: {tryb}: {OPISY_TRYBOW[tryb]}.{dopisek}"
        if tryb == "pelny":
            return ("Tryb pełny działa tylko na tę sesję i włącza go Hermes: wpisz /yolo albo uruchom "
                    "`jarvo chat --tryb pelny`. Wtyczka sama go nie włącza. Nawet wtedy config.yaml i chronione "
                    "miejsca zostają zablokowane, a w każdym profilu także ekran i telefon.")
        return "Użycie: /tryb [auto|projekt|pytaj|pelny]. Bez argumentu pokazuję bieżący tryb."
    except Exception as e:
        logger.warning("jarvo-zgody: /tryb: %s", e)
        return f"jarvo-zgody: nie udało się zmienić trybu ({type(e).__name__})."


# ------------------------------------------------------------------------------------------------ rejestracja

def register(ctx) -> None:
    """Hak pre_tool_call (bez niego wtyczka nie chroni, więc błąd rejestracji przerywa ładowanie), polecenie /tryb
    i obraz z narzędzi MCP jako obraz dla modelu głównego (obraz.py)."""
    _zamroz()
    ctx.register_hook("pre_tool_call", straznik_zgod)
    try:
        ctx.register_command("tryb", polecenie_tryb,
                             description="Tryb zgód Jarva: auto (domyślny), projekt, pytaj albo pelny (= /yolo na sesję)",
                             args_hint="[auto|projekt|pytaj|pelny]")
    except Exception as e:
        logger.warning("jarvo-zgody: polecenie /tryb niezarejestrowane: %s", e)
    try:
        from . import obraz
        obraz.zarejestruj(ctx)
    except Exception as e:
        logger.warning("jarvo-zgody: obraz z narzędzi MCP niezarejestrowany: %s", e)
    try:
        from . import ciaglosc
        ciaglosc.zarejestruj(ctx)
    except Exception as e:
        logger.warning("jarvo-zgody: ciągłość tury (samo rozumowanie w trakcie pracy) niezarejestrowana: %s", e)
