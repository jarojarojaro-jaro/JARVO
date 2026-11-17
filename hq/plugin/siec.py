"""Panel w sieci Tailscale (docs/HQ.md „Panel w sieci”, docs/NATYWNIE.md H10 i I11): drugi nasłuch tego samego
dashboardu na adresie Tailscale, z logowaniem kluczem jednorazowym.

Dlaczego drugi nasłuch w tym samym procesie, a nie drugi dashboard: bramka logowania Hermesa włącza się dla całego
procesu (`app.state.auth_required` przy bindzie spoza pętli zwrotnej albo z `dashboard.public_url`), więc panel na
127.0.0.1 straciłby tryb bez hasła. Drugi proces dashboardu miałby drugi silnik rozmów Jarvo HQ (silnik.py: jeden
na proces, jedno połączenie piszące rozmowy.db) i drugą usługę pokojów Hermesa na tych samych bazach. Dlatego
dashboard słucha dalej na 127.0.0.1 bez zmian (bez hasła), a ten moduł dokłada w tym samym procesie i na tej samej
pętli zdarzeń serwer uvicorn na `<adres Tailscale>:<port panelu>`, który przed aplikacją Hermesa stawia `Bramka`:

  1. Host: dokładnie adres z ustawień albo nazwa MagicDNS (z portem albo bez), inaczej 400 jak strażnik Hosta
     Hermesa (DNS rebinding, GHSA-ppp5-vxwm-4cf7). Origin, gdy jest, wskazuje ten sam serwer, inaczej 403.
  2. Bez sesji przechodzą tylko strona logowania Hermesa (`/login`, `/auth/password-login`, `/auth/logout`)
     i statyczne zasoby (strona HTML z nich = 404: brakujący plik w /fonts/ Hermes odsyła jako index.html SPA
     z tokenem sesji loopbacku); reszta: `/api/…` = 401 JSON, strona = 302 na `/login?next=…`, WebSocket = odmowa
     przed przyjęciem. Sesja to ciasteczka Hermesa (`hermes_session_at`, `hermes_session_rt`), wydane przez trasę
     `/auth/password-login` Hermesa i dostawcę `jarvo` (rejestr dostawców Hermesa, `register_global_provider`),
     podpisane HMAC sekretem z `<dane>/jarvo/konfig/panel-siec.sekret`. Dostęp 12 h, odświeżenie 30 dni
     (przesuwane przy każdym odświeżeniu, jak ciasteczko RT Hermesa), więc zalogowany Mac zostaje zalogowany.
  3. Zalogowane żądanie idzie do aplikacji Hermesa jak lokalne: Host i Origin = `127.0.0.1:<port>` (strażnik
     Hosta Hermesa i ochrona zapisu HQ porównują je ze sobą), bez nagłówków X-Forwarded-* i Forwarded od klienta;
     WebSocket dostaje też adres klienta 127.0.0.1 (Hermes przyjmuje WebSocket loopbacku tylko z pętli zwrotnej).
     Dalej działa zwykła ochrona trybu loopback: token sesji z index.html, CSRF HQ, limity.
  4. Szybkość: sesja = jeden HMAC bez zapytań do Hermesa; pełne odpowiedzi tekstowe z Content-Length idą gzipem
     (front Hermesa nie jest kompresowany, ok. 2,7 MB), pliki /assets/ skompresowane raz; strumienie bez zmian.

Logowanie: `jarvo panel klucz` wydaje klucz JRV-XXXX-XXXX-XXXX (alfabet Crockforda, 60 bitów) z ważnością
(domyślnie 1 h); na dysku zostaje tylko skrót SHA-256 z czasem wygaśnięcia w `<dane>/jarvo/wejscie` (katalog 700,
pliki 600, jak dawny infra/bin/jarvo-klucz). Pierwsze użycie przenosi plik skrótu atomowo, więc klucz działa raz,
także przy dwóch równoczesnych próbach. Link `http://<adres>:<port>/login#klucz=…`: klucz jest w części po #, nie
idzie do serwera z adresem; skrypt dopisany do strony logowania wpisuje go w formularz Hermesa i wysyła.
`jarvo panel siec wyloguj` zmienia sekret: każda sesja traci ważność od razu (sekret czytamy przy zmianie pliku).

Włączenie: `<dane>/jarvo/konfig/panel-siec.json` (`jarvo panel siec on|off`): {"wlaczony", "adres", "nazwa"}.
Pętla `_petla` sprawdza go co 5 s: włączony = rejestracja dostawcy i nasłuch, wyłączony albo inny adres =
zatrzymanie (bez restartu panelu, więc bez przerwy w rozmowach). Adres niedostępny (Tailscale jeszcze nie wstał)
= ponowienie co 5 s. Stan nasłuchu: `<dane>/jarvo/state/panel-siec.json` (czyta go `jarvo panel siec status`).
Wpięcie: `zahacz()` owija `uvicorn.Server.startup` (jak silnik.zahacz_uvicorn owija handle_exit): po starcie
serwera dashboardu pętla rusza na jego pętli zdarzeń, a kończy się razem z nim.

Moduł działa bez Hermesa i bez FastAPI przy imporcie (czysty ASGI, biblioteka standardowa): ten sam plik czyta
`jarvo/panel_siec.py` (wydanie klucza, sekret, ustawienia), a testy wołają Bramkę wprost.
"""

from __future__ import annotations

import asyncio
import base64
import gzip
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import re
import secrets
import socket
import tempfile
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

USTAWIENIA = "panel-siec.json"          # <dane>/jarvo/konfig: {"wlaczony", "adres", "nazwa", "kiedy"}
SEKRET = "panel-siec.sekret"            # <dane>/jarvo/konfig: 32 bajty hex, tylko właściciel
KLUCZE = "wejscie"                      # <dane>/jarvo/wejscie/<sha256 klucza>: {"wygasa"}
STAN = "panel-siec.json"                # <dane>/jarvo/state: stan nasłuchu z procesu panelu
DOSTAWCA = "jarvo"                      # nazwa dostawcy logowania w rejestrze Hermesa
ZNAKI = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"     # Crockford: bez I, L, O, U
WZOR_KLUCZA = re.compile(r"JRV(-[0-9A-HJKMNP-TV-Z]{4}){3}")
NAJWIECEJ_KLUCZY = 5                    # tyle naraz ważnych kluczy
WAZNOSC_KLUCZA = 3600                   # s: domyślnie 1 h (operator wysyła klucz właścicielowi)
WAZNOSC_MAKS = 24 * 3600
CZAS_DOSTEPU = 12 * 3600                # s: token dostępu (ciasteczko hermes_session_at)
CZAS_ODSWIEZENIA = 30 * 24 * 3600       # s: token odświeżenia, jak _RT_MAX_AGE ciasteczka Hermesa
CO_ILE = 5.0                            # s: ustawienia i ponowienie nasłuchu
ZAMKNIECIE = 5                          # s: łagodne zamknięcie nasłuchu sieci (strumienie SSE kończy HQ)

# ciasteczka sesji Hermesa (hermes_cli/dashboard_auth/cookies.py, f97608f): po HTTP bez przedrostka, po HTTPS
# z __Host- / __Secure-; czytamy każdy wariant jak Hermes (_read_with_fallback)
CIASTKO_AT, CIASTKO_RT, CIASTKO_DOSTAWCY = "hermes_session_at", "hermes_session_rt", "hermes_session_provider"
PRZEDROSTKI = ("__Host-", "__Secure-", "")

# bez sesji: strona logowania Hermesa i zasoby statyczne (te same co w bramce Hermesa, bez OAuth i /api/status:
# w trybie loopback /api/status pokazuje ścieżki instalacji)
TRASY_LOGOWANIA = frozenset({"/login", "/auth/password-login", "/auth/logout"})
PUBLICZNE = TRASY_LOGOWANIA | {"/favicon.ico", "/favicon.svg"}
PUBLICZNE_PRZEDROSTKI = ("/assets/", "/fonts/", "/fonts-terminal/", "/ds-assets/")
# kompresja w sieci (Bramka._gzip): typy tekstowe, od 1 KB do 8 MB, pliki /assets/ zapamiętane (najwyżej 64)
GZIP_TYPY = frozenset({b"text/html", b"text/css", b"text/plain", b"text/javascript", b"application/javascript",
                       b"application/json", b"image/svg+xml", b"application/manifest+json"})
GZIP_MIN, GZIP_MAKS = 1024, 8 * 2 ** 20
_GZIP_PAMIEC: dict = {}
NAGLOWKI_POSREDNIKA = frozenset({b"x-forwarded-for", b"x-forwarded-host", b"x-forwarded-proto",
                                 b"x-forwarded-prefix", b"x-forwarded-port", b"forwarded", b"x-real-ip"})
ODMOWA_HOSTA = {"detail": "Invalid Host header. Dashboard requests must use the bound hostname or the configured "
                          "public hostname."}

# dopisek do strony logowania Hermesa: pole użytkownika ukryte (dostawca go nie potrzebuje), hasło = klucz, a klucz
# z części adresu po # wpisany i wysłany od razu (formularz obsługuje skrypt Hermesa: fetch /auth/password-login)
SKRYPT_LOGOWANIA = """<script>
(function () {
  var f = document.querySelector('form.provider-form[data-provider="jarvo"]');
  if (!f) return;
  var u = f.querySelector('input[name=username]'), p = f.querySelector('input[name=password]');
  var t = f.querySelector('.form-title'), b = f.querySelector('button[type=submit]');
  if (t) t.textContent = 'Jarvo: wejście kluczem';
  if (b) b.textContent = 'Wejdź';
  if (u) { u.value = 'jarvo'; var lu = u.closest('label'); if (lu) lu.style.display = 'none'; }
  if (!p) return;
  var lp = p.closest('label') && p.closest('label').querySelector('.field-label');
  if (lp) lp.textContent = 'Klucz jednorazowy (od operatora: jarvo panel klucz)';
  p.setAttribute('autocomplete', 'one-time-code');
  p.setAttribute('placeholder', 'JRV-XXXX-XXXX-XXXX');
  var m = /(?:^#|&)klucz=([A-Za-z0-9-]{10,40})(?:&|$)/.exec(location.hash || '');
  if (location.hash) { try { history.replaceState(null, '', location.pathname + location.search); } catch (e) {} }
  if (!m) return;
  p.value = m[1].toUpperCase();
  if (f.requestSubmit) f.requestSubmit(); else if (b) b.click();
})();
</script>"""

_log = logging.getLogger("jarvo.hq.siec")


# ---------------------------------------------------------------------------------------------- ścieżki i pliki

class Sciezki:
    """Pliki trybu sieci w `<dane>/jarvo` (`jarvo_dir`)."""

    def __init__(self, jarvo_dir: Path | str):
        self.jarvo = Path(jarvo_dir)
        self.ustawienia = self.jarvo / "konfig" / USTAWIENIA
        self.sekret = self.jarvo / "konfig" / SEKRET
        self.klucze = self.jarvo / KLUCZE
        self.stan = self.jarvo / "state" / STAN


def zapisz_atomowo(cel: Path, tresc: str, tryb: int = 0o600) -> None:
    """Cały plik naraz (czytelnik widzi starą albo nową treść), od razu z trybem `tryb` na POSIX."""
    cel.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{cel.name}.", suffix=".tmp", dir=str(cel.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(tresc)
            f.flush()
            os.fsync(f.fileno())
        if os.name != "nt":
            os.chmod(tmp, tryb)
        os.replace(tmp, cel)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _json(p: Path) -> dict:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def adres_poprawny(adres: str) -> bool:
    """Konkretny adres IP tego komputera do nasłuchu: nie wieloznaczny (0.0.0.0, ::) i nie pętla zwrotna."""
    try:
        ip = ipaddress.ip_address(str(adres or "").strip())
    except ValueError:
        return False
    return not (ip.is_unspecified or ip.is_loopback or ip.is_multicast)


def nazwa_poprawna(nazwa: str) -> bool:
    return bool(re.fullmatch(r"(?=.{1,253}$)[a-z0-9]([a-z0-9-]{0,62})(\.[a-z0-9]([a-z0-9-]{0,62}))*", nazwa or ""))


def ustawienia(sc: Sciezki) -> dict:
    """{"wlaczony": bool, "adres": str, "nazwa": str} z pliku ustawień; zły wpis = wyłączony."""
    d = _json(sc.ustawienia)
    adres = str(d.get("adres") or "").strip()
    nazwa = str(d.get("nazwa") or "").strip().lower().rstrip(".")
    return {"wlaczony": d.get("wlaczony") is True and adres_poprawny(adres), "adres": adres,
            "nazwa": nazwa if nazwa_poprawna(nazwa) else "", "kiedy": d.get("kiedy")}


def zapisz_ustawienia(sc: Sciezki, *, wlaczony: bool, adres: str, nazwa: str = "") -> dict:
    d = {"wlaczony": bool(wlaczony), "adres": adres, "nazwa": nazwa, "kiedy": time.strftime("%Y-%m-%dT%H:%M:%S")}
    zapisz_atomowo(sc.ustawienia, json.dumps(d, ensure_ascii=False, indent=2) + "\n")
    return d


def stan(sc: Sciezki) -> dict:
    return _json(sc.stan)


def dostep(sc: Sciezki) -> dict:
    """Ustawienia › Dostęp w aplikacji (tylko odczyt): włączenie, adres, nazwa MagicDNS, port i nasłuch. Bez sekretu
    i kluczy; klucz jednorazowy wydaje `jarvo panel klucz`."""
    u, s = ustawienia(sc), stan(sc)
    return {"wlaczony": u["wlaczony"], "adres": u["adres"], "nazwa": u["nazwa"], "port": s.get("port"),
            "nasluch": bool(s.get("nasluch")), "od": s.get("od"), "blad": s.get("blad")}


def _zapisz_stan(sc: Sciezki, **pola: Any) -> None:
    try:
        zapisz_atomowo(sc.stan, json.dumps({**pola, "pid": os.getpid(),
                                            "zapisano": time.strftime("%Y-%m-%dT%H:%M:%S")},
                                           ensure_ascii=False, indent=2) + "\n", 0o644)
    except OSError as e:
        _log.warning("panel w sieci: nie zapisałem stanu (%s)", type(e).__name__)


# ---------------------------------------------------------------------------------------------- sekret i klucze

def nowy_sekret(sc: Sciezki) -> None:
    """Nowy sekret podpisu sesji (każda dotychczasowa sesja traci ważność). Wartości nigdzie nie wypisujemy."""
    zapisz_atomowo(sc.sekret, secrets.token_hex(32) + "\n")


def nowy_kod() -> str:
    return "JRV-" + "-".join("".join(secrets.choice(ZNAKI) for _ in range(4)) for _ in range(3))


def skrot(kod: str) -> str:
    return hashlib.sha256(kod.strip().upper().encode()).hexdigest()


def _sprzataj(katalog: Path, teraz: float) -> None:
    """Usuwa wygasłe i zużyte wpisy, a z ważnych zostawia NAJWIECEJ_KLUCZY - 1 najnowszych (miejsce na nowy)."""
    wazne = []
    for p in katalog.iterdir():
        wygasa = _json(p).get("wygasa", 0)
        if p.name.endswith(".zuzyty") or not isinstance(wygasa, int) or wygasa <= teraz:
            p.unlink(missing_ok=True)
        else:
            wazne.append((wygasa, p))
    for _, p in sorted(wazne)[:max(0, len(wazne) - (NAJWIECEJ_KLUCZY - 1))]:
        p.unlink(missing_ok=True)


def wydaj_klucz(sc: Sciezki, waznosc: int = WAZNOSC_KLUCZA, chron: Callable[[Path], None] | None = None
                ) -> tuple[str, int]:
    """Nowy klucz jednorazowy: (kod, unix czas wygaśnięcia). Na dysku tylko skrót; `chron` zamyka katalog przed
    zapisem (Windows: ACL właściciela, jarvo/przenosne.chron), bez niego na POSIX tryb 700."""
    waznosc = min(WAZNOSC_MAKS, max(60, int(waznosc)))
    sc.klucze.mkdir(mode=0o700, parents=True, exist_ok=True)
    if chron is not None:
        chron(sc.klucze)
    elif os.name != "nt":
        os.chmod(sc.klucze, 0o700)
    teraz = time.time()
    _sprzataj(sc.klucze, teraz)
    kod = nowy_kod()
    wygasa = int(teraz) + waznosc
    fd = os.open(sc.klucze / skrot(kod), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"wygasa": wygasa}, f)
    return kod, wygasa


def zuzyj_klucz(sc: Sciezki, kod: str) -> bool:
    """Klucz ważny i jeszcze nie użyty: plik skrótu przenosimy atomowo przed odczytem, więc drugi raz (także
    równolegle) nie przejdzie, nawet po błędzie."""
    kod = (kod or "").strip().upper()
    if not WZOR_KLUCZA.fullmatch(kod):
        return False
    plik = sc.klucze / skrot(kod)
    zuzyty = plik.with_name(plik.name + ".zuzyty")
    try:
        os.rename(plik, zuzyty)
    except OSError:
        return False
    try:
        wygasa = _json(zuzyty).get("wygasa", 0)
    finally:
        zuzyty.unlink(missing_ok=True)
    return isinstance(wygasa, int) and wygasa > time.time()


# ---------------------------------------------------------------------------------------------- sesje (HMAC)

def _b64(dane: bytes) -> str:
    return base64.urlsafe_b64encode(dane).rstrip(b"=").decode("ascii")      # bez „=”: ciasteczko bez cudzysłowu


def _z_b64(tekst: str) -> bytes:
    return base64.urlsafe_b64decode(tekst + "=" * (-len(tekst) % 4))


class Sesje:
    """Tokeny sesji: base64url(JSON + HMAC-SHA256) sekretem z pliku (czytanym ponownie po zmianie pliku, więc
    `jarvo panel siec wyloguj` działa od razu). Bez sekretu nie ma sesji."""

    DLUGOSC_PODPISU = hashlib.sha256().digest_size

    def __init__(self, sc: Sciezki):
        self.sc = sc
        self._sekret: bytes | None = None
        self._odcisk: tuple | None = None

    def sekret(self) -> bytes | None:
        try:
            st = self.sc.sekret.stat()
        except OSError:
            self._sekret, self._odcisk = None, None
            return None
        odcisk = (st.st_mtime_ns, st.st_size, st.st_ino)
        if odcisk != self._odcisk:
            try:
                surowy = bytes.fromhex(self.sc.sekret.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                surowy = b""
            self._sekret, self._odcisk = (surowy if len(surowy) >= 16 else None), odcisk
        return self._sekret

    def _podpisz(self, tresc: dict, sekret: bytes) -> str:
        surowe = json.dumps(tresc, separators=(",", ":")).encode()
        return _b64(surowe + hmac.new(sekret, surowe, hashlib.sha256).digest())

    def odczytaj(self, token: str, rodzaj: str) -> dict | None:
        sekret = self.sekret()
        if not sekret or not token or len(token) > 4096:
            return None
        try:
            blob = _z_b64(token)
        except (ValueError, TypeError):
            return None
        if len(blob) <= self.DLUGOSC_PODPISU:
            return None
        surowe, podpis = blob[:-self.DLUGOSC_PODPISU], blob[-self.DLUGOSC_PODPISU:]
        if not hmac.compare_digest(podpis, hmac.new(sekret, surowe, hashlib.sha256).digest()):
            return None
        try:
            tresc = json.loads(surowe)
        except ValueError:
            return None
        if not isinstance(tresc, dict) or tresc.get("rodzaj") != rodzaj:
            return None
        wygasa = tresc.get("wygasa")
        return tresc if isinstance(wygasa, int) and wygasa > time.time() else None

    def nowa(self, kto: str = "wlasciciel") -> dict | None:
        """{"kto", "at", "rt", "wygasa"} albo None bez sekretu."""
        sekret = self.sekret()
        if not sekret:
            return None
        teraz = int(time.time())
        wygasa = teraz + CZAS_DOSTEPU
        return {"kto": kto, "wygasa": wygasa,
                "at": self._podpisz({"kto": kto, "rodzaj": "dostep", "wygasa": wygasa}, sekret),
                "rt": self._podpisz({"kto": kto, "rodzaj": "odswiezenie", "wygasa": teraz + CZAS_ODSWIEZENIA}, sekret)}

    def zaloguj(self, kod: str) -> dict | None:
        """Sesja za klucz jednorazowy (zużywa go) albo None. Bez sekretu klucza nie zużywamy."""
        if not self.sekret() or not zuzyj_klucz(self.sc, kod):
            return None
        return self.nowa()

    def sprawdz(self, at: str) -> dict | None:
        t = self.odczytaj(at, "dostep")
        return None if t is None else {"kto": str(t.get("kto") or ""), "wygasa": t["wygasa"], "at": at, "rt": ""}

    def odswiez(self, rt: str) -> dict | None:
        t = self.odczytaj(rt, "odswiezenie")
        return None if t is None else self.nowa(str(t.get("kto") or "wlasciciel"))


def dostawca_hermesa(sesje: Sesje):
    """Dostawca `jarvo` dla rejestru logowania Hermesa (hermes_cli/dashboard_auth/base.py): hasłem jest klucz
    jednorazowy, nazwa użytkownika bez znaczenia. Import Hermesa dopiero tutaj (proces dashboardu)."""
    from hermes_cli.dashboard_auth.base import (DashboardAuthProvider, InvalidCredentialsError, RefreshExpiredError,
                                                Session)

    def _sesja(t: dict) -> Session:
        return Session(user_id=t["kto"], email="", display_name="Właściciel", org_id="", provider=DOSTAWCA,
                       expires_at=int(t["wygasa"]), access_token=t["at"], refresh_token=t["rt"])

    class DostawcaJarva(DashboardAuthProvider):
        name = DOSTAWCA
        display_name = "Jarvo"
        supports_password = True

        def start_login(self, *, redirect_uri: str):
            raise NotImplementedError("Jarvo: logowanie kluczem jednorazowym przez /auth/password-login")

        def complete_login(self, *, code: str, state: str, code_verifier: str, redirect_uri: str):
            raise NotImplementedError("Jarvo: logowanie kluczem jednorazowym przez /auth/password-login")

        def complete_password_login(self, *, username: str, password: str):
            t = sesje.zaloguj(password)
            if t is None:
                raise InvalidCredentialsError("klucz zły, zużyty albo wygasły")
            return _sesja(t)

        def verify_session(self, *, access_token: str):
            t = sesje.sprawdz(access_token)
            return None if t is None else _sesja(t)

        def refresh_session(self, *, refresh_token: str):
            t = sesje.odswiez(refresh_token)
            if t is None:
                raise RefreshExpiredError("sesja Jarva wygasła albo wylogowana")
            return _sesja(t)

        def revoke_session(self, *, refresh_token: str) -> None:
            return None          # tokeny bez stanu: wylogowanie wszystkich = nowy sekret (jarvo panel siec wyloguj)

    return DostawcaJarva()


# ---------------------------------------------------------------------------------------------- bramka (ASGI)

def nazwa_hosta(autorytet: str) -> str:
    """Nazwa z nagłówka Host (autorytet, nie URL), małymi literami, albo "" dla wartości niejednoznacznej:
    te same odmowy co _host_header_hostname Hermesa (URL, znaki specjalne, port nie z cyfr, IPv6 bez nawiasów)."""
    v = (autorytet or "").strip()
    if not v or "://" in v or any(c in v for c in "\"'<> \n\r\t/?#@\\"):
        return ""
    if v.startswith("["):
        koniec = v.find("]")
        if koniec == -1 or ":" not in v[1:koniec]:
            return ""
        reszta = v[koniec + 1:]
        if reszta and not re.fullmatch(r":\d+", reszta):
            return ""
        return v[1:koniec].lower()
    if v.count(":") > 1:
        return ""
    if ":" in v:
        v, port = v.rsplit(":", 1)
        if not v or not port.isdigit():
            return ""
    return v.lower()


def ciasteczka(naglowek: str) -> dict[str, str]:
    """Nagłówek Cookie → {nazwa: wartość} (pierwsza wygrywa, cudzysłowy zdjęte)."""
    wynik: dict[str, str] = {}
    for kawalek in (naglowek or "").split(";"):
        nazwa, rowna, wartosc = kawalek.strip().partition("=")
        if rowna and nazwa and nazwa not in wynik:
            wartosc = wartosc.strip()
            if len(wartosc) >= 2 and wartosc[0] == wartosc[-1] == '"':
                wartosc = wartosc[1:-1]
            wynik[nazwa] = wartosc
    return wynik


def _ciastko(c: dict[str, str], nazwa: str) -> str:
    return next((c[p + nazwa] for p in PRZEDROSTKI if c.get(p + nazwa)), "")


def ustaw_ciastka(sesja: dict) -> list[tuple[bytes, bytes]]:
    """Set-Cookie po odświeżeniu, w kształcie set_session_cookies Hermesa po HTTP (bez przedrostka, Path=/,
    HttpOnly, SameSite=lax)."""
    def jedno(nazwa: str, wartosc: str, wiek: int) -> tuple[bytes, bytes]:
        return b"set-cookie", f"{nazwa}={wartosc}; HttpOnly; Max-Age={wiek}; Path=/; SameSite=lax".encode()
    return [jedno(CIASTKO_AT, sesja["at"], max(1, int(sesja["wygasa"] - time.time()))),
            jedno(CIASTKO_RT, sesja["rt"], CZAS_ODSWIEZENIA),
            jedno(CIASTKO_DOSTAWCY, DOSTAWCA, CZAS_ODSWIEZENIA)]


def publiczna(sciezka: str) -> bool:
    return sciezka in PUBLICZNE or sciezka.startswith(PUBLICZNE_PRZEDROSTKI)


def bezpieczny_next(sciezka: str, zapytanie: str) -> str:
    """Cel po zalogowaniu (jak is_safe_next_path Hermesa): ścieżka strony, nie /api i nie trasy logowania."""
    if not sciezka.startswith("/") or sciezka.startswith("//") or sciezka == "/api" or sciezka.startswith("/api/"):
        return ""
    if sciezka.startswith(("/login", "/auth/")):
        return ""
    return sciezka + (f"?{zapytanie}" if zapytanie else "")


class Bramka:
    """ASGI przed aplikacją Hermesa na nasłuchu sieci (docstring modułu). `hosty`: dokładne nazwy dozwolone
    w Host i Origin (adres Tailscale, nazwa MagicDNS); `lokalny`: autorytet loopbacku, np. "127.0.0.1:9119"."""

    def __init__(self, app, sesje: Sesje, hosty: set[str] | frozenset[str], lokalny: str):
        self.app, self.sesje, self.lokalny = app, sesje, lokalny
        self.hosty = frozenset(h.lower() for h in hosty if h)

    # -- pomocnicze
    def _naglowek(self, scope: dict, nazwa: bytes) -> str:
        for k, v in scope.get("headers") or ():
            if k == nazwa:
                return v.decode("latin-1")
        return ""

    def _origin_dobry(self, origin: str) -> bool:
        if not origin:
            return True
        schemat, _, reszta = origin.partition("://")
        return schemat in ("http", "https") and nazwa_hosta(reszta) in self.hosty

    def _jak_lokalne(self, scope: dict, klient_lokalny: bool) -> dict:
        lokalny = self.lokalny.encode("latin-1")
        naglowki = []
        for k, v in scope.get("headers") or ():
            if k in NAGLOWKI_POSREDNIKA:
                continue
            if k == b"host":
                v = lokalny
            elif k == b"origin":
                v = b"http://" + lokalny
            naglowki.append((k, v))
        nowy = dict(scope)
        nowy["headers"] = naglowki
        host, _, port = self.lokalny.rpartition(":")
        nowy["server"] = (host, int(port) if port.isdigit() else 80)
        if klient_lokalny:
            nowy["client"] = ("127.0.0.1", (scope.get("client") or ("", 0))[1])
        return nowy

    def _sesja(self, scope: dict, *, odswiez: bool) -> tuple[dict | None, dict | None]:
        """(sesja, nowa sesja do ciasteczek po odświeżeniu) z ciasteczek żądania."""
        c = ciasteczka(self._naglowek(scope, b"cookie"))
        at, rt = _ciastko(c, CIASTKO_AT), _ciastko(c, CIASTKO_RT)
        if at:
            s = self.sesje.sprawdz(at)
            if s is not None:
                return s, None
        if rt:
            if not odswiez:                       # WebSocket nie ustawi ciasteczek: ważny RT wystarcza
                t = self.sesje.odczytaj(rt, "odswiezenie")
                return (({"kto": str(t.get("kto") or ""), "wygasa": t["wygasa"]}, None) if t else (None, None))
            nowa = self.sesje.odswiez(rt)
            if nowa is not None:
                return nowa, nowa
        return None, None

    @staticmethod
    async def _odpowiedz(send, kod: int, tresc: bytes, typ: bytes, dodatkowe=()) -> None:
        await send({"type": "http.response.start", "status": kod,
                    "headers": [(b"content-type", typ), (b"content-length", str(len(tresc)).encode()),
                                (b"cache-control", b"no-store"), *dodatkowe]})
        await send({"type": "http.response.body", "body": tresc})

    async def _json(self, send, kod: int, dane: dict) -> None:
        await self._odpowiedz(send, kod, json.dumps(dane, ensure_ascii=False).encode(),
                              b"application/json; charset=utf-8")

    async def _bez_sesji(self, scope: dict, send) -> None:
        sciezka = scope.get("path") or "/"
        nastepny = bezpieczny_next(sciezka, (scope.get("query_string") or b"").decode("latin-1"))
        logowanie = f"/login?next={quote(nastepny, safe='')}" if nastepny else "/login"
        if sciezka.startswith("/api/") or scope.get("method") not in ("GET", "HEAD"):
            await self._json(send, 401, {"error": "unauthenticated", "detail": "Unauthorized",
                                         "login_url": logowanie, "jarvo": "panel-siec"})
            return
        await self._odpowiedz(send, 302, b"", b"text/plain; charset=utf-8", [(b"location", logowanie.encode())])

    # -- ASGI
    async def __call__(self, scope: dict, receive, send) -> None:
        typ = scope.get("type")
        if typ not in ("http", "websocket"):
            return
        ws = typ == "websocket"
        if nazwa_hosta(self._naglowek(scope, b"host")) not in self.hosty:
            if ws:
                await send({"type": "websocket.close", "code": 1008})
            else:
                await self._json(send, 400, ODMOWA_HOSTA)
            return
        if not self._origin_dobry(self._naglowek(scope, b"origin")):
            if ws:
                await send({"type": "websocket.close", "code": 1008})
            else:
                await self._json(send, 403, {"detail": "Origin spoza panelu Jarva"})
            return
        sciezka = scope.get("path") or "/"
        if ws:
            sesja, _ = self._sesja(scope, odswiez=False)
            if sesja is None:
                await send({"type": "websocket.close", "code": 1008})
                return
            await self.app(self._jak_lokalne(scope, klient_lokalny=True), receive, send)
            return
        wyslij = self._gzip(scope, send)
        if publiczna(sciezka):
            if sciezka == "/login" and scope.get("method") == "GET":
                wyslij = self._z_dopiskiem(wyslij)
            elif sciezka not in TRASY_LOGOWANIA:
                wyslij = self._bez_strony(wyslij)
            await self.app(self._jak_lokalne(scope, klient_lokalny=False), receive, wyslij)
            return
        sesja, nowa = self._sesja(scope, odswiez=True)
        if sesja is None:
            await self._bez_sesji(scope, send)
            return
        await self.app(self._jak_lokalne(scope, klient_lokalny=False), receive,
                       self._z_ciastkami(wyslij, nowa) if nowa else wyslij)

    @staticmethod
    def _bez_strony(send):
        """Zasób statyczny bez sesji: brak pliku w /fonts/ albo /ds-assets/ Hermes odsyła jako index.html SPA (z tokenem
        sesji trybu loopback), więc każdą stronę HTML zamieniamy na 404."""
        async def wyslij(wiadomosc: dict) -> None:
            if wiadomosc.get("type") == "http.response.start":
                typ = dict(wiadomosc.get("headers") or ()).get(b"content-type", b"")
                if typ.startswith(b"text/html"):
                    wyslij.odrzucone = True
                    await Bramka._odpowiedz(send, 404, b'{"detail":"Not Found"}', b"application/json")
                    return
            elif getattr(wyslij, "odrzucone", False):
                return
            await send(wiadomosc)
        return wyslij

    @staticmethod
    def _gzip(scope: dict, send):
        """Kompresja gzip w sieci (pierwsze wyświetlenie na Macu i telefonie: front Hermesa to ok. 2,7 MB JS i CSS
        bez kompresji, Hermes nie kompresuje). Tylko GET z Accept-Encoding gzip i tylko pełne odpowiedzi 200 z
        Content-Length (pliki, JSON, HTML); strumienie (SSE, odpowiedzi bez długości) idą bez zmian i bez
        buforowania. Skompresowane pliki /assets/ (niezmienne, nazwa z hashem) zostają w pamięci."""
        akceptuje = b""
        for k, v in scope.get("headers") or ():
            if k == b"accept-encoding":
                akceptuje = v.lower()
        if scope.get("method") != "GET" or b"gzip" not in akceptuje:
            return send
        start: dict = {}
        czesci: list[bytes] = []

        async def wyslij(wiadomosc: dict) -> None:
            typ = wiadomosc.get("type")
            if typ == "http.response.start":
                h = {k.lower(): v for k, v in wiadomosc.get("headers") or ()}
                dlugosc = h.get(b"content-length", b"")
                if (wiadomosc.get("status") == 200 and dlugosc.isdigit()
                        and GZIP_MIN <= int(dlugosc) <= GZIP_MAKS and b"content-encoding" not in h
                        and h.get(b"content-type", b"").split(b";")[0].strip() in GZIP_TYPY):
                    start.update(wiadomosc)
                    start["_klucz"] = (scope.get("path"), dlugosc, h.get(b"etag", b""))
                    return
                await send(wiadomosc)
                return
            if typ != "http.response.body" or not start:
                await send(wiadomosc)
                return
            czesci.append(wiadomosc.get("body") or b"")
            if wiadomosc.get("more_body"):
                return
            klucz = start.pop("_klucz")
            tresc = b"".join(czesci)
            spakowane = _GZIP_PAMIEC.get(klucz)
            if spakowane is None:
                spakowane = (await asyncio.to_thread(gzip.compress, tresc, 6) if len(tresc) > 256 * 1024
                             else gzip.compress(tresc, 6))
                if str(klucz[0]).startswith("/assets/") and klucz[2]:
                    if len(_GZIP_PAMIEC) >= 64:
                        _GZIP_PAMIEC.pop(next(iter(_GZIP_PAMIEC)))
                    _GZIP_PAMIEC[klucz] = spakowane
            if len(spakowane) >= len(tresc):
                await send(start)
                await send({"type": "http.response.body", "body": tresc})
                return
            naglowki = [(k, v) for k, v in start.get("headers") or () if k.lower() not in (b"content-length", b"vary")]
            naglowki += [(b"content-encoding", b"gzip"), (b"vary", b"Accept-Encoding"),
                         (b"content-length", str(len(spakowane)).encode())]
            await send({**start, "headers": naglowki})
            await send({"type": "http.response.body", "body": spakowane})
        return wyslij

    @staticmethod
    def _z_ciastkami(send, sesja: dict):
        async def wyslij(wiadomosc: dict) -> None:
            if wiadomosc.get("type") == "http.response.start":
                wiadomosc = {**wiadomosc, "headers": [*(wiadomosc.get("headers") or ()), *ustaw_ciastka(sesja)]}
            await send(wiadomosc)
        return wyslij

    @staticmethod
    def _z_dopiskiem(send):
        """Strona logowania Hermesa (HTML, cała w jednej odpowiedzi) z SKRYPT_LOGOWANIA przed </body>."""
        start: dict = {}
        czesci: list[bytes] = []

        async def wyslij(wiadomosc: dict) -> None:
            if wiadomosc.get("type") == "http.response.start":
                start.update(wiadomosc)
                return
            if wiadomosc.get("type") != "http.response.body" or not start:
                await send(wiadomosc)
                return
            czesci.append(wiadomosc.get("body") or b"")
            if wiadomosc.get("more_body"):
                return
            tresc = b"".join(czesci)
            naglowki = [(k, v) for k, v in start.get("headers") or () if k != b"content-length"]
            if start.get("status") == 200 and b"</body>" in tresc:
                i = tresc.rfind(b"</body>")
                tresc = tresc[:i] + SKRYPT_LOGOWANIA.encode() + tresc[i:]
            await send({**start, "headers": [*naglowki, (b"content-length", str(len(tresc)).encode())]})
            await send({"type": "http.response.body", "body": tresc})
        return wyslij


# ---------------------------------------------------------------------------------------------- nasłuch w procesie

class Nasluch:
    """Serwer uvicorn na adresie sieci w pętli zdarzeń dashboardu (bez lifespanu: ten ma serwer główny)."""

    def __init__(self, serwer, gniazdo: socket.socket, zadanie: asyncio.Task):
        self.serwer, self.gniazdo, self.zadanie = serwer, gniazdo, zadanie

    async def zatrzymaj(self) -> None:
        self.serwer.should_exit = True
        try:
            await self.zadanie
        except BaseException:   # noqa: BLE001 - zamknięcie nasłuchu nie może zatrzymać dashboardu
            pass
        try:
            await self.serwer.shutdown(sockets=[self.gniazdo])
        except BaseException:   # noqa: BLE001
            pass


def gniazdo(adres: str, port: int) -> socket.socket:
    """Gniazdo TCP na (adres, port). POSIX: SO_REUSEADDR (szybki powrót po restarcie); Windows: SO_EXCLUSIVEADDRUSE
    (jak podgląd :9120, docs/NATYWNIE.md W10)."""
    rodzina = socket.AF_INET6 if ":" in adres else socket.AF_INET
    s = socket.socket(rodzina, socket.SOCK_STREAM)
    try:
        if os.name == "nt":
            s.setsockopt(socket.SOL_SOCKET, getattr(socket, "SO_EXCLUSIVEADDRUSE", -5), 1)
        else:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((adres, port))
        s.setblocking(False)
    except BaseException:
        s.close()
        raise
    return s


async def uruchom_nasluch(app, adres: str, port: int) -> Nasluch:
    """Serwer uvicorn z `app` (Bramka) na gnieździe (adres, port); OSError = adres niedostępny albo port zajęty."""
    import uvicorn
    s = gniazdo(adres, port)
    try:
        try:
            from hermes_cli.web_server import _DESKTOP_ATTACHMENT_WS_MAX_BYTES as maks_ws
        except ImportError:
            maks_ws = 16 * 1024 * 1024
        konfig = uvicorn.Config(app, host=adres, port=port, lifespan="off", proxy_headers=False, log_config=None,
                                log_level="warning", ws_ping_interval=20.0, ws_ping_timeout=20.0,
                                ws_max_size=maks_ws, timeout_graceful_shutdown=ZAMKNIECIE, server_header=False)
        konfig.load()
        serwer = uvicorn.Server(konfig)
        serwer._jarvo_siec = True
        serwer.lifespan = konfig.lifespan_class(konfig)
        await serwer.startup(sockets=[s])
        if not serwer.started:
            raise OSError("uvicorn nie wystartował nasłuchu")
    except BaseException:
        s.close()
        raise
    return Nasluch(serwer, s, asyncio.get_running_loop().create_task(serwer.main_loop()))


def _hermes_app():
    from hermes_cli.web_server import app
    return app


async def _petla(glowny, sc: Sciezki, log: Callable[[str], None]) -> None:
    """Ustawienia co CO_ILE s: włączony = dostawca w rejestrze Hermesa i nasłuch; zmiana adresu, wyłączenie albo
    koniec serwera głównego = zatrzymanie. Rejestr Hermesa jest wspólny dla procesu (register_global_provider)."""
    from hermes_cli.dashboard_auth.registry import register_global_provider, unregister_global_provider
    port = int(getattr(glowny.config, "port", 0) or 0)
    sesje = Sesje(sc)
    dostawca = None
    nasluch: Nasluch | None = None
    cel: tuple | None = None
    ostatni_blad = ""
    nastepny = 0.0
    while not glowny.should_exit:
        if time.monotonic() >= nastepny:
            nastepny = time.monotonic() + CO_ILE
            u = ustawienia(sc)
            nowy_cel = (u["adres"], port, u["nazwa"]) if u["wlaczony"] and port else None
            if nowy_cel != cel and nasluch is not None:
                await nasluch.zatrzymaj()
                nasluch, cel = None, None
                log("panel w sieci: nasłuch zatrzymany")
                _zapisz_stan(sc, nasluch=False, adres=u["adres"], port=port, blad=None)
            if nowy_cel is None and dostawca is not None:
                unregister_global_provider(DOSTAWCA, dostawca)
                dostawca = None
            if nowy_cel is not None and nasluch is None:
                if dostawca is None:
                    dostawca = dostawca_hermesa(sesje)
                    register_global_provider(dostawca)
                adres, _, nazwa = nowy_cel
                hosty = {adres.lower(), *([nazwa] if nazwa else [])}
                try:
                    if sesje.sekret() is None:
                        raise OSError(f"brak sekretu sesji {sc.sekret} (jarvo panel siec on)")
                    nasluch = await uruchom_nasluch(Bramka(_hermes_app(), sesje, hosty, f"127.0.0.1:{port}"),
                                                    adres, port)
                    cel, ostatni_blad = nowy_cel, ""
                    log(f"panel w sieci: słucham na http://{adres}:{port}" + (f" i http://{nazwa}:{port}"
                                                                              if nazwa else ""))
                    _zapisz_stan(sc, nasluch=True, adres=adres, nazwa=nazwa, port=port, blad=None,
                                 od=time.strftime("%Y-%m-%dT%H:%M:%S"))
                except (OSError, SystemExit) as e:
                    blad = f"{adres}:{port}: {getattr(e, 'strerror', None) or e}"
                    if blad != ostatni_blad:        # stan i dziennik tylko przy zmianie powodu, nie co 5 s
                        log(f"panel w sieci: nie słucham ({blad}); ponawiam co {int(CO_ILE)} s")
                        ostatni_blad = blad
                        _zapisz_stan(sc, nasluch=False, adres=adres, nazwa=nazwa, port=port, blad=blad)
            elif nowy_cel is None and cel is None and _json(sc.stan).get("nasluch"):
                _zapisz_stan(sc, nasluch=False, adres=u["adres"], port=port, blad=None)
        await asyncio.sleep(0.5)
    if nasluch is not None:
        await nasluch.zatrzymaj()
        _zapisz_stan(sc, nasluch=False, adres=cel[0] if cel else "", port=port, blad=None)


_ZADANIA: set = set()


def zahacz(jarvo_dir: Path | str, log: Callable[[str], None] | None = None) -> bool:
    """Owija `uvicorn.Server.startup`: po starcie serwera dashboardu rusza `_petla` na jego pętli zdarzeń
    (raz na proces). True = hak założony (bez uvicorn, np. w testach, False)."""
    try:
        import uvicorn  # noqa: PLC0415
    except ImportError:
        return False
    Server = uvicorn.Server
    Server._jarvo_siec_konfig = (Sciezki(jarvo_dir), log or (lambda linia: _log.info("%s", linia)))
    if getattr(Server.startup, "_jarvo_siec", False):
        return True
    oryginal = Server.startup

    async def startup(self, sockets=None):
        await oryginal(self, sockets=sockets)
        if not self.started or getattr(self, "_jarvo_siec", False) or _ZADANIA:
            return
        sc, zapis = Server._jarvo_siec_konfig

        async def pilnuj():
            try:
                await _petla(self, sc, zapis)
            except Exception as e:  # noqa: BLE001 - awaria trybu sieci nie zatrzymuje panelu
                zapis(f"panel w sieci: pętla zakończona błędem ({type(e).__name__})")
                _zapisz_stan(sc, nasluch=False, blad=f"awaria: {type(e).__name__}")

        _ZADANIA.add(asyncio.get_running_loop().create_task(pilnuj()))

    startup._jarvo_siec = True
    Server.startup = startup
    return True
