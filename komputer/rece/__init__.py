"""Ręce: Operator na ekranie właściciela (docs/KOMPUTER.md, etap K6; docs/NATYWNIE.md J14, J15, decyzja I19).

Domyślnie wyłączone. Włącza je tylko właściciel, ze swojego terminala, na czas i tylko w aplikacjach, które sam
wskaże: `jarvo komputer rece on --aplikacje notatnik,mspaint --na 30m` (jarvo/rece.py). Polecenie zakłada albo
odświeża profil rąk `jarvo-ekran` (profil.py) i zapisuje zgodę podpisaną kluczem HMAC z `<stan>/rece.klucz` oraz
manifest trybu bounded sterownika. Bramka `komputer/jarvo_cua.py` przekazuje tu czasowniki rąk (`serve`,
`mcp --socket`, `status --socket`, `stop`, `call`), a ten pakiet przepuszcza je tylko przy ważnej zgodzie,
profilu, w którym Hermes pyta o każde działanie, i sprawdzonym sterowniku cua-driver-rs 0.38.0.

Moduły:
  zgoda      klucz, podpisana zgoda (`<stan>/rece/zgoda.json`), manifest bounded sterownika (`manifest.yaml`)
  aplikacje  nazwy z --aplikacje → tożsamości sterownika (ścieżka programu na Windows i Linuksie, bundle id na macOS);
             launch_app tylko z tożsamością ze zgody
  konfig     ścisły odczyt config.yaml Hermesa bez PyYAML: zgody (approvals, command_allowlist) tak, jak przeczyta je
             Hermes, a wszystko niepewne to odmowa
  profil     profil rąk `jarvo-ekran` (bounded z manifestem zgody, approvals manual, bez terminala i plików)
  sterownik  miejsce programu, suma sha256 z przeglądu, podpis (Authenticode, codesign), środowisko bez telemetrii,
             prawa procesu (okna administratora poza zasięgiem), ekran na Linuksie
  procesy    odcisk procesu, rejestr działających sterowników rąk, zatrzymanie
  dziennik   `<stan>/rece/dziennik.jsonl`: decyzje bez treści (bez wpisywanego tekstu i bez zawartości ekranu)
  bramka     serve (nadzór sterownika), mcp (filtr rozmowy i twarde zasady), status, stop

Pakiet działa samą biblioteką standardową. Moduły `jarvo` (układ katalogów, zapis atomowy, ACL) bierze z katalogu
kodu Jarva, w którym leży (`<app>/komputer/rece` → `<app>/jarvo`).
"""
from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[2]
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

WERSJA = "0.38.0"                       # cua-driver-rs (trycua/cua, tag cua-driver-rs-v0.38.0 = commit 85e2b131)
COMMIT = "85e2b1318bd77ccf3cfa88ccdf875a4bb7eaed19"

# sha256 programu sterownika po rozpakowaniu archiwum z wydania (przegląd 2026-10-25: suma archiwum z SHA256SUMS
# = digest GitHuba = własne liczenie, a program policzony z archiwum). Inny plik = odmowa, także przy dobrej sumie
# archiwum: bramka sprawdza sam program przed każdym uruchomieniem. Na macOS ścieżka w CuaDriver.app.
PROGRAMY = {
    "windows-x64": ("cua-driver.exe", "ffa58d88779ee219304b0c307f4cfa970fe822f830c6ecf9254eda5c29e22bf2"),
    "windows-arm64": ("cua-driver.exe", "2d6a0822be887a8a51678f57682d7362d484d4049b769ef964f0c2dffda29de1"),
    "macos-arm64": ("Contents/MacOS/cua-driver", "b4d974a9c1c92a700cd7be7ede987aea4a1e6835e37039ce3d628b71bd5f0ca8"),
    "linux-x64": ("cua-driver", "bf57b2f3778a0a7daa9388e241f20ce948b32a7a2f4dd102e497f34e54137934"),
    "linux-arm64": ("cua-driver", "26e9eee8165e9ce7b614b5e3d68e5d963231385a82b65236406718b5ce1ff936"),
}
# Windows: podpis Authenticode (Microsoft ID Verified CS AOC CA 04, znacznik czasu Microsoftu); macOS: Developer ID.
PODPIS_WINDOWS = "Cua AI, Inc."
MACOS_ID = "com.trycua.driver"
MACOS_ZESPOLY = ("YCK386LBJ7",)
MACOS_APLIKACJA = Path("/Applications/CuaDriver.app")
# pracownik UIAccess (manifest uiAccess="true") omija UIPI, czyli sięga do okien administratora: manifest
# `vendor/natywne.yaml` usuwa go po rozpakowaniu, a bramka odmawia, gdy leży obok programu
UIACCESS = "cua-driver-uia.exe"

# Narzędzia sterownika na ekranie właściciela. Bez pełnego ekranu (get_desktop_state, capture_scope desktop),
# skryptów (page, run_script, run_steps), schowka, zamykania programów, nagrywania, przeglądarki CDP, historii,
# surowego wejścia myszy, rozszerzeń i aktualizacji. Każde nowe narzędzie z kolejnej wersji wymaga przeglądu.
NARZEDZIA = (
    "start_session", "end_session", "get_config", "set_config", "get_screen_size", "get_cursor_position",
    "list_apps", "list_windows", "get_window_state",
    "click", "double_click", "drag", "scroll", "type_text", "press_key", "hotkey", "set_value",
    "launch_app", "bring_to_front", "set_agent_cursor_enabled",
)
# jawna odmowa w manifeście bounded (deny wygrywa z allow; nazwy z authorization.rs 0.38.0)
ZAKAZANE_NARZEDZIA = (
    "get_desktop_state", "page", "run_script", "run_steps", "clipboard_read", "clipboard_write", "kill_app",
    "escalate_session", "start_recording", "stop_recording", "replay_trajectory", "install_ffmpeg",
    "install_extension", "browser_prepare", "browser_navigate", "browser_click", "browser_type", "browser_select",
    "browser_pointer", "browser_dialog", "browser_set_input_files", "browser_download", "get_browser_state",
    "history_status", "history_query", "zoom", "get_accessibility_tree", "mouse_button_down", "mouse_button_up",
    "mouse_drag", "parallel_mouse_drag", "set_window_frame", "invoke_menu", "move_cursor", "set_agent_cursor_motion",
    "set_agent_cursor_theme", "debug_window_info", "verify_state", "parse_visual_regions", "check_for_update",
)
# set_config tylko z tym kluczem i wartością z profilu (Hermes: computer_use.max_image_dimension)
KONFIGURACJA = {"max_image_dimension": 1456}

CZAS_DOMYSLNY = 30 * 60                 # s
CZAS_MIN = 60
CZAS_MAKS = 8 * 60 * 60                 # sterownik przyjmuje do 24 h; na ekranie właściciela najwyżej 8 h
BEZCZYNNOSC = 10 * 60                   # idle_timeout sterownika: bez działań przez 10 min ręce gasną same
# profil rąk (profil.py): osobny od jarvo-operator, który na Komputerze Jarva ma approvals.mode smart i stałe zgody
# cua:* (tam słuszne, na ekranie właściciela nie); nie `jarvo-rece`, bo myli się z agentem jarvo-reka
PROFIL = "jarvo-ekran"
