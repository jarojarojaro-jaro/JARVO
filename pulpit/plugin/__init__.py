"""Wtyczka jarvo-pulpit: narzędzie `pulpit` dla agentów z `pulpit: true` we fleet.yaml (docs/PULPIT.md).

Agent obsługuje programy na pulpicie serwera (X11 `:0`, właściciel ogląda go przez VNC) jak człowiek: uruchamia
program, widzi ekran, klika, pisze, przeciąga i sprawdza wynik. Całą pracę z ekranem robi silnik (silnik.py obok)
w Pythonie systemu, bo tylko on ma AT-SPI, Wnck i Gdk; wtyczka trzyma jeden silnik na proces Hermesa, pilnuje,
żeby pulpitem sterowało naraz jedno zadanie agenta, i oddaje zrzut modelowi jako obraz w wyniku narzędzia
(koperta `_multimodal`, ta sama co `capture` computer_use Hermesa; gdy Hermes kieruje obrazy do auxiliary.vision,
wynik jest tekstem ze ścieżką zrzutu).

  zobacz       zrzut z numerami elementów aktywnego okna + lista elementów (AT-SPI, przycięta), `obszar` powiększa,
  klik         numer z zobacz albo xy z obrazu; prawy, środkowy, podwójny,
  pisz         tekst (polskie znaki) w pole z fokusem albo w numer/xy, `zamien` czyści pole,
  klawisz      Return, ctrl+s, alt+F4 …, `razy`,
  przewin      gora, dol, lewo, prawo, nad numerem albo xy,
  przeciagnij  od numer/xy do do_numer/do_xy,
  okna, aktywuj, zamknij, uruchom (programy z listy; Kdenlive i Inkscape z manifestu vendor/natywne.yaml, pobierane
               przy pierwszym uruchomieniu), czekaj (tekst, okno, zniknięcie albo spokojny ekran, do 60 s),
  kroki        do 20 działań w jednym wywołaniu z paragonem po każdym; `zobacz_po` dokłada zrzut na końcu.

Twarde zasady (płatności, terminale, okno Komputera Jarva, skróty systemowe) sprawdza silnik przed działaniem.
build.py kopiuje wtyczkę do plugins/jarvo-pulpit razem z infra/komputer/zasady.py i komputer/zgoda_karty.py,
install_fleet.py dowiązuje ją w profilach z `pulpit: true` (build dokłada im toolset `pulpit`).
"""
from __future__ import annotations

import atexit
import base64
import fcntl
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

NAZWA = "jarvo-pulpit"
TU = Path(__file__).resolve().parent
SILNIK = TU / "silnik.py"
PYTHON_SYSTEMU = os.environ.get("JARVO_PULPIT_PYTHON", "/usr/bin/python3")
BEZCZYNNOSC = 900.0          # s bez wywołania: silnik się kończy (numery elementów i tak wymagają nowego zobacz)
ZAJETE_S = 120.0             # s od ostatniego działania innego zadania agenta, przez które pulpit jest zajęty
ZRZUTY = 20                  # ile ostatnich zrzutów zostaje w cache obrazów Hermesa
CZASY = {"uruchom": 200.0, "czekaj": 75.0, "kroki": 400.0}
DZIALANIA = frozenset({"klik", "pisz", "klawisz", "przewin", "przeciagnij", "aktywuj", "zamknij", "uruchom", "kroki"})
AKCJE = ["zobacz", "klik", "pisz", "klawisz", "przewin", "przeciagnij", "okna", "aktywuj", "zamknij", "uruchom",
         "czekaj", "kroki"]
Z_MANIFESTU = ("kdenlive", "inkscape")

SCHEMAT: Dict[str, Any] = {
    "name": "pulpit",
    "description": (
        "Pulpit serwera (ekran :0, właściciel widzi go na żywo przez VNC): programy z oknami jak człowiek. "
        "Pętla: uruchom albo aktywuj → zobacz (zrzut z numerami elementów aktywnego okna i ich lista) → klik, pisz, "
        "klawisz, przewin, przeciagnij (cel: numer z ostatniego zobacz albo xy z obrazu) → paragon po działaniu mówi, "
        "co się zmieniło; kroki: kilka działań w jednym wywołaniu. Współrzędne zawsze jak na obrazie z zobacz "
        "(cały ekran 1280×720), obszar powiększa fragment w tych samych współrzędnych. Strony w Komputerze Jarva "
        "robisz narzędziem komputer, polecenia narzędziem terminal; pulpit jest do programów z oknami (GIMP, "
        "LibreOffice, Kdenlive, Inkscape, edytor HQ w przeglądarce) i do sprawdzenia wyniku na ekranie."),
    "parameters": {
        "type": "object",
        "properties": {
            "akcja": {"type": "string", "enum": AKCJE},
            "numer": {"type": "integer", "description": "Element z ostatniego zobacz (klik, pisz, przewin, przeciagnij)."},
            "xy": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2,
                   "description": "Punkt [x, y] z obrazu zobacz, gdy element nie ma numeru (płótno, oś czasu)."},
            "przycisk": {"type": "string", "enum": ["lewy", "prawy", "srodkowy"], "description": "Dla klik (domyślnie lewy)."},
            "podwojny": {"type": "boolean", "description": "Dla klik: podwójne kliknięcie."},
            "tekst": {"type": "string", "description": (
                "Dla pisz: tekst (polskie znaki, \\n to Enter). Dla czekaj: napis, na który czekasz w aktywnym oknie.")},
            "zamien": {"type": "boolean", "description": "Dla pisz: najpierw zaznacz całą zawartość pola (ctrl+a)."},
            "klawisz": {"type": "string", "description": "Dla klawisz: np. Return, Escape, Tab, ctrl+s, ctrl+shift+z, alt+F4, Down."},
            "razy": {"type": "integer", "description": "Dla klawisz: ile razy (1–50)."},
            "kierunek": {"type": "string", "enum": ["gora", "dol", "lewo", "prawo"], "description": "Dla przewin."},
            "ile": {"type": "integer", "description": "Dla przewin: ile ząbków kółka (1–30, domyślnie 3)."},
            "do_numer": {"type": "integer", "description": "Dla przeciagnij: element docelowy."},
            "do_xy": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2,
                      "description": "Dla przeciagnij: punkt docelowy [x, y] z obrazu."},
            "okno": {"type": "string", "description": (
                "Dla aktywuj i zamknij: fragment tytułu albo id z akcji okna. Dla czekaj: czekasz, aż okno o takim "
                "tytule się pojawi (albo zniknie).")},
            "program": {"type": "string", "description": (
                "Dla uruchom: gimp, calc, writer, impress, draw, libreoffice, mousepad, thunar, ristretto, parole, "
                "firefox (przeglądarka, np. edytor HQ), kdenlive, inkscape (pierwsze uruchomienie pobiera program).")},
            "argumenty": {"type": "array", "items": {"type": "string"}, "description": (
                "Dla uruchom: pełne ścieżki plików do otwarcia albo adres (bez opcji programu).")},
            "obszar": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4, "description": (
                "Dla zobacz: [x, y, szerokość, wysokość] z obrazu: ten fragment w pełnej rozdzielczości.")},
            "maks": {"type": "integer", "description": "Dla zobacz: ile elementów na liście (domyślnie 60, najwyżej 200)."},
            "elementy": {"type": "boolean", "description": "Dla zobacz: false = sam obraz, bez listy elementów."},
            "zniknie": {"type": "boolean", "description": "Dla czekaj: czekaj, aż tekst albo okno zniknie."},
            "sekundy": {"type": "number", "description": "Dla czekaj (do 60, domyślnie 10) i uruchom (do 180, domyślnie 60)."},
            "kroki": {"type": "array", "maxItems": 20, "items": {"type": "object"}, "description": (
                "Dla kroki, po kolei, te same pola co pojedyncze akcje: [{\"akcja\": \"klik\", \"numer\": 12}, "
                "{\"akcja\": \"pisz\", \"tekst\": \"Tytuł\"}, {\"akcja\": \"klawisz\", \"klawisz\": \"Return\"}, "
                "{\"akcja\": \"czekaj\", \"okno\": \"Eksport\"}]. Paczka staje na pierwszym błędzie albo odmowie.")},
            "zobacz_po": {"type": "boolean", "description": "Dla kroki: po ostatnim kroku zrzut i lista elementów."},
        },
        "required": ["akcja"],
    },
}


# ---------------------------------------------------------------------------------------------- silnik

class _Silnik:
    """Proces silnik.py (Python systemu) z rozmową JSON w wierszach; jedno polecenie naraz."""

    def __init__(self) -> None:
        ekran = os.environ.get("JARVO_PULPIT_DISPLAY") or os.environ.get("DISPLAY") or ":0"
        self.p = subprocess.Popen([PYTHON_SYSTEMU, "-I", str(SILNIK), ekran], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  env={**os.environ, "JARVO_PULPIT_LOGI": str(katalog_stanu())},
                                  text=True, encoding="utf-8", bufsize=1)
        self.ostatnio = time.monotonic()
        self.n = 0
        gotowy = self._linia(30.0)
        if not gotowy.get("gotowy"):
            self.zamknij()
            raise RuntimeError(gotowy.get("blad") or "silnik pulpitu nie wstał")

    def _linia(self, czas: float) -> dict:
        wynik: List[str] = []
        w = threading.Thread(target=lambda: wynik.append(self.p.stdout.readline()), daemon=True)
        w.start()
        w.join(czas)
        if not wynik:
            self.zamknij()
            raise TimeoutError(f"silnik pulpitu nie odpowiedział w {czas:g} s")
        if not wynik[0]:
            raise ConnectionError("silnik pulpitu zakończył pracę")
        try:
            return json.loads(wynik[0])
        except ValueError:
            return {"ok": False, "blad": "silnik pulpitu odpowiedział nie po JSON-owemu"}

    def zyje(self) -> bool:
        return self.p.poll() is None

    def wywolaj(self, argumenty: dict, czas: float) -> dict:
        self.n += 1
        self.ostatnio = time.monotonic()
        self.p.stdin.write(json.dumps({"id": self.n, "argumenty": argumenty}, ensure_ascii=False) + "\n")
        self.p.stdin.flush()
        odp = self._linia(czas)
        self.ostatnio = time.monotonic()
        return odp

    def zamknij(self) -> None:
        try:
            self.p.stdin.close()
        except OSError:
            pass
        try:
            self.p.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.p.kill()


_LOCK = threading.Lock()
_STAN: Dict[str, Any] = {"silnik": None, "sprzatacz": None}


def _sprzataj() -> None:
    while True:
        time.sleep(60)
        with _LOCK:
            s = _STAN["silnik"]
            if s is not None and time.monotonic() - s.ostatnio > BEZCZYNNOSC:
                s.zamknij()
                _STAN["silnik"] = None


def _silnik() -> _Silnik:
    s = _STAN["silnik"]
    if s is None or not s.zyje():
        s = _STAN["silnik"] = _Silnik()
        if _STAN["sprzatacz"] is None:
            _STAN["sprzatacz"] = threading.Thread(target=_sprzataj, daemon=True, name="jarvo-pulpit-sprzatanie")
            _STAN["sprzatacz"].start()
    return s


@atexit.register
def _koniec() -> None:
    s = _STAN.get("silnik")
    if s is not None:
        s.zamknij()


# ---------------------------------------------------------------------------------------------- zamek pulpitu

def katalog_stanu() -> Path:
    root = os.environ.get("JARVO_ROOT", "").strip()
    k = Path(root) / "stan" / "pulpit" if root else Path(tempfile.gettempdir()) / f"jarvo-pulpit-{os.getuid()}"
    k.mkdir(parents=True, exist_ok=True)
    return k


def kto() -> str:
    """Profil Hermesa i zadanie agenta tego procesu (do komunikatu `zajęte`)."""
    dom = Path(os.environ.get("HERMES_HOME", "") or ".")
    profil = dom.name if dom.parent.name == "profiles" else "jarvo"
    karta = os.environ.get("HERMES_KANBAN_TASK", "").strip()
    return profil + (f" (zadanie {karta})" if karta else "")


def zajmij(klucz: str, teraz: Optional[float] = None) -> Optional[str]:
    """Pulpit dla zadania `klucz` (proces i sesja); powód odmowy, gdy inne zadanie działało w ostatnich ZAJETE_S s."""
    teraz = time.time() if teraz is None else teraz
    plik = katalog_stanu() / "zamek.json"
    with open(katalog_stanu() / "zamek.lock", "a+") as z:
        fcntl.flock(z, fcntl.LOCK_EX)
        try:
            stan = json.loads(plik.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            stan = {}
        if stan.get("klucz") not in (None, klucz) and teraz - float(stan.get("czas") or 0) < ZAJETE_S:
            zostalo = int(ZAJETE_S - (teraz - float(stan["czas"])))
            return (f"pulpit zajęty: pracuje na nim {stan.get('kto') or 'inny agent'} (ostatnie działanie "
                    f"{int(teraz - float(stan['czas']))} s temu); zwolni się najpóźniej za {zostalo} s: zrób w tym "
                    "czasie inną część zadania albo czekaj i spróbuj ponownie")
        tmp = plik.with_suffix(".tmp")
        tmp.write_text(json.dumps({"klucz": klucz, "kto": kto(), "czas": teraz}, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, plik)
    return None


# ---------------------------------------------------------------------------------------------- programy z manifestu

def program_z_manifestu(nazwa: str) -> List[str]:
    """Pełna ścieżka programu `nazwa` (Kdenlive, Inkscape) z manifestu instalacji: gotowy zostaje, brakujący
    pobiera jarvo/przy_uzyciu.py z sumą sha256 (raz, potem z dysku)."""
    root = os.environ.get("JARVO_ROOT", "").strip() or os.path.expanduser("~/.local/share/jarvo")
    try:
        app = json.loads((Path(root) / "program" / "current.json").read_text(encoding="utf-8"))["app"]
    except (OSError, ValueError, KeyError):
        raise RuntimeError(f"{nazwa}: brak instalacji natywnej Jarva w {root}")
    kod = ("import json, sys\nsys.path.insert(0, sys.argv[1])\nfrom jarvo import przy_uzyciu as p\n"
           "u = p.uklad()\nw = p.narzedzie(u, sys.argv[2], log=lambda t: None, pasek=False)\n"
           "print(json.dumps({'program': str(p.program_narzedzia(w, sys.argv[2]) or '')}))\n")
    r = subprocess.run([sys.executable, "-I", "-c", kod, app, nazwa], capture_output=True, text=True,
                       encoding="utf-8", timeout=1500, env={**os.environ, "JARVO_ROOT": root})
    try:
        program = json.loads(r.stdout.strip().splitlines()[-1])["program"]
    except (ValueError, IndexError, KeyError):
        program = ""
    if r.returncode != 0 or not program:
        blad = (r.stderr.strip().splitlines() or ["nieznany błąd"])[-1][:300]
        raise RuntimeError(f"{nazwa} nie jest gotowy: {blad}")
    return [program]


# ---------------------------------------------------------------------------------------------- wynik dla modelu

def _obraz_natywnie() -> bool:
    """Czy model główny dostaje obraz w wyniku narzędzia (ta sama decyzja co `capture` computer_use Hermesa)."""
    try:
        from tools.computer_use.tool import _should_route_through_aux_vision
    except Exception:  # noqa: BLE001 - poza Hermesem (testy, wiersz poleceń): obraz natywnie
        return True
    return not _should_route_through_aux_vision()


def _zapisz_zrzut(b64: str) -> Optional[str]:
    """Kopia zrzutu w cache obrazów Hermesa (do wysłania właścicielowi albo vision_analyze), najwyżej ZRZUTY plików."""
    try:
        try:
            from hermes_constants import get_hermes_dir
            k = Path(get_hermes_dir("cache/images", "image_cache"))
        except Exception:  # noqa: BLE001
            k = Path(os.environ.get("HERMES_HOME") or tempfile.gettempdir()) / "cache" / "images"
        k.mkdir(parents=True, exist_ok=True)
        stare = sorted(k.glob("pulpit_*.jpg"), key=lambda p: p.stat().st_mtime)
        for p in stare[: max(0, len(stare) - (ZRZUTY - 1))]:
            p.unlink(missing_ok=True)
        p = k / f"pulpit_{uuid.uuid4().hex}.jpg"
        p.write_bytes(base64.b64decode(b64))
        return str(p)
    except Exception:  # noqa: BLE001 - zrzut bez kopii dalej trafia do modelu
        return None


def wynik(odp: dict) -> Any:
    if not odp.get("ok"):
        return ("ODMOWA: " if odp.get("odmowa") else "BŁĄD pulpit: ") + str(odp.get("blad") or "nieznany błąd")
    tekst = str(odp.get("tekst") or "ok")
    b64 = odp.get("obraz")
    if not b64:
        return tekst
    sciezka = _zapisz_zrzut(b64)
    if sciezka:
        tekst += f"\nzrzut: {sciezka}"
    if not _obraz_natywnie():
        return tekst + "\n(obraz nie idzie do Ciebie wprost: obejrzysz go vision_analyze tej ścieżki)"
    return {"_multimodal": True,
            "content": [{"type": "text", "text": tekst},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}],
            "text_summary": tekst,
            "meta": {"szer": odp.get("szer"), "wys": odp.get("wys"), **({"zrzut": sciezka} if sciezka else {})}}


def obsluz(args: Dict[str, Any], **kontekst: Any) -> Any:
    args = dict(args or {})
    akcja = str(args.get("akcja") or "zobacz")
    if akcja not in AKCJE:
        return "BŁĄD pulpit: akcja " + ", ".join(AKCJE)
    if akcja in DZIALANIA:
        klucz = f"{os.getpid()}:{kontekst.get('session_id') or kontekst.get('task_id') or ''}"
        zajete = zajmij(klucz)
        if zajete:
            return "ODMOWA: " + zajete
    try:
        for k in ([args] if akcja == "uruchom" else []) + [k for k in (args.get("kroki") or [])
                                                            if isinstance(k, dict) and k.get("akcja") == "uruchom"]:
            if str(k.get("program") or "").strip().lower() in Z_MANIFESTU:
                k["polecenie"] = program_z_manifestu(str(k["program"]).strip().lower())
    except (RuntimeError, OSError, subprocess.SubprocessError) as e:
        return f"BŁĄD pulpit: {e}"
    with _LOCK:
        try:
            s = _silnik()
            return wynik(s.wywolaj(args, CZASY.get(akcja, 60.0)))
        except (RuntimeError, ConnectionError, TimeoutError, OSError) as e:
            stary = _STAN.get("silnik")
            if stary is not None:
                stary.zamknij()
            _STAN["silnik"] = None
            return f"BŁĄD pulpit: {e}"


def dostepny() -> bool:
    """Linux z ekranem X11 i Pythonem systemu (silnik sprawdza resztę przy starcie i mówi, czego brak)."""
    return sys.platform.startswith("linux") and os.path.exists(PYTHON_SYSTEMU) and SILNIK.is_file() \
        and bool(os.environ.get("JARVO_PULPIT_DISPLAY") or os.environ.get("DISPLAY") or os.path.exists("/tmp/.X11-unix/X0"))


def register(ctx) -> None:
    ctx.register_tool(name="pulpit", toolset="pulpit", schema=SCHEMAT, handler=obsluz, check_fn=dostepny, emoji="🖱️",
                      description="Pulpit serwera: programy z oknami (zobacz, klik, pisz, klawisz, okna, uruchom, kroki)")


if __name__ == "__main__":       # próba z wiersza poleceń: python3 pulpit/plugin/__init__.py '{"akcja": "zobacz"}'
    w = obsluz(json.loads(sys.argv[1]) if len(sys.argv) > 1 else {"akcja": "zobacz"})
    print(w if isinstance(w, str) else w["text_summary"])
