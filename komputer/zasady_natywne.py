"""Twarde zasady Komputera natywnie (docs/NATYWNIE.md J05): `infra/komputer/zasady.py` bez zmian + to, czego
przeglądarka na pulpicie właściciela wymaga ponad kontener.

Rdzeń (płatność, zakup, wysyłka, publikacja i usunięcie konta tylko ze zgodą właściciela w karcie, karty, sekrety,
adresy, skróty narzędzi deweloperskich, accesskey, okno nieaktywne, pauza) ocenia zasady.ocen na opisie elementu ze
sterownika CDP (role w słowniku zasad: sterownik_cdp.ROLE i rola_zasad). Logowanie, rejestrację, hasła i kody agent
robi sam, okienko „jestem człowiekiem” raz (niżej). Ten moduł dokłada zasady, które ocenia się PRZED rdzeniem:
  schowek            Ctrl/Cmd+V, Shift+Insert, Ctrl+Shift+V (wklejanie ze schowka właściciela: mógł tam skopiować
                     hasło) oraz Ctrl/Cmd+C, Ctrl/Cmd+X, Ctrl+Insert (agent nie zmienia schowka właściciela): odmowa
  skrot_przegladarki skróty, które w oknie przeglądarki otwierają pasek adresu, nową kartę lub okno, plik z dysku,
                     zapis, druk, historię, pobrane, ustawienia albo przełączają karty: odmowa (adresy idą przez
                     launch_app i linki strony, gdzie sprawdza je zasada adresów i proxy)
  okno_wrazliwe      OK (klik, Enter) w oknie JavaScript (confirm, prompt, beforeunload) z tekstem płatności,
                     zakupu, logowania, wysyłki, publikacji albo usunięcia konta: robi właściciel; Anuluj wolno
  wybor_pliku        klik, Enter albo spacja na polu wyboru pliku (<input type=file>): plik wybiera właściciel
  pole_wrazliwe      pojedynczy znak przez press_key (także z Shift) w polu karty, CVV albo BLIK bez zgody `platnosc`:
                     to też pisanie (rdzeń sprawdza pole tylko przy type_text); pole, którego nie da się
                     sprawdzić: odmowa `nieznany_cel`
  weryfikacja_czlowieka  klik, Enter albo spacja w okienku „jestem człowiekiem” (Cloudflare Turnstile, reCAPTCHA,
                     hCaptcha: napis elementu albo ramka serwisu weryfikacji): jedno kliknięcie na stronę (domenę)
                     w karcie (bez karty: w sesji); drugie albo każde po nieudanej weryfikacji na stronie: odmowa
                     (16.11 Jarvo klikał to samo pole Turnstile godzinę i nie dał znać właścicielowi). Odmowa wskazuje
                     drogę: ten sam krok na telefonie floty (MCP `phone`, to samo konto), a gdy i tam nie przejdzie,
                     koniec pracy karty na ekranie: `kanban_block` z `kind: needs_input` i jednym zdaniem dla
                     właściciela. Bez ponawiania w Komputerze, innej przeglądarki, user-agenta ani obchodzenia.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

_INFRA = Path(__file__).resolve().parent.parent / "infra" / "komputer"
if str(_INFRA) not in sys.path:
    sys.path.insert(0, str(_INFRA))
import zasady  # noqa: E402  (infra/komputer/zasady.py: rdzeń bez zmian)

SCHOWEK = frozenset({("ctrl", "v"), ("super", "v"), ("shift", "insert"), ("ctrl", "shift", "v"),
                     ("shift", "super", "v"), ("ctrl", "c"), ("super", "c"), ("ctrl", "x"), ("super", "x"),
                     ("ctrl", "insert"), ("ctrl", "shift", "c")})
# skróty okna przeglądarki (Windows i Linux z Ctrl, macOS z Cmd); Ctrl+Shift+I/J/C/O/Delete i F12 ma już rdzeń
_LITERY_PRZEGLADARKI = "ltnosphjudkeqmwfg"
SKROTY_PRZEGLADARKI = frozenset(
    {(m, k) for m in ("ctrl", "super") for k in _LITERY_PRZEGLADARKI}
    | {("ctrl", "shift", k) for k in "ntbwamqd"} | {("shift", "super", k) for k in "ntbwamqd"}
    | {("alt", k) for k in ("d", "e", "f", "home", "left", "right")} | {("f6",), ("f1",), ("f10",), ("f11",), ("f3",)}
    | {("ctrl", "tab"), ("ctrl", "shift", "tab"), ("ctrl", "page_up"), ("ctrl", "page_down"), ("ctrl", "prior"),
       ("ctrl", "next"), ("ctrl", "pageup"), ("ctrl", "pagedown"), ("alt", "super", "left"), ("alt", "super", "right"),
       ("super", "comma"), ("super", ","), ("ctrl", "f4"), ("alt", "f4")}
    | {(m, str(i)) for m in ("ctrl", "super", "alt") for i in range(10)})
KLAWISZE_AKCEPTUJACE = zasady.KLAWISZE_ENTER
# Tekst okna JavaScript, którego OK zatwierdza właściciel: rdzenie słów (okno pyta pełnym zdaniem: „Czy na pewno
# zapłacić…?”, a zasady.WRAZLIWE szuka całych słów przycisków). Usunięcie samo w sobie nie (pozycja w koszyku),
# usunięcie konta tak.
OKNO_WRAZLIWE = re.compile(
    r"zap[lł]ac|p[lł]atno|op[lł]ac|przelew|blik|kup|zakup|zam[oó]w|subskryb|wykup|zaloguj|logowan|rejestr|"
    r"wy[sś][lł]|prze[sś][lł]|opublik|publik|udost[eę]pni|usu[nń]\w*\s+(?:\w+\s+)?kont|zamkn\w*\s+(?:\w+\s+)?kont|"
    r"\bpay|\bbuy|purchase|\border|checkout|subscri|sign ?in|log ?in|register|\bsend|submit|publish|\bshare|"
    r"delete\s+(?:\w+\s+)?account|close\s+(?:\w+\s+)?account", re.I)

# Okienko „jestem człowiekiem” (zasada weryfikacja_czlowieka): napis elementu albo adres ramki, w której leży
WERYFIKACJA = re.compile(
    r"\b(?:re|h)?captcha\b|turnstile|nie jestem robotem|jestem cz[lł]owiekiem|"
    r"(?:potwierd[zź]|zweryfikuj),? [zż]e jeste[sś] cz[lł]owiekiem|i.?m not a robot|i am not a robot|"
    r"(?:verify|confirm) (?:that )?you(?: a|.)re (?:a )?human|human verification|are you (?:a )?(?:human|robot)",
    re.I)
RAMKA_WERYFIKACJI = re.compile(
    r"^https?://(?:[^/]*\.)?(?:challenges\.cloudflare\.com|hcaptcha\.com|recaptcha\.net|captcha-delivery\.com|"
    r"arkoselabs\.com|funcaptcha\.com)(?:[:/]|$)|^https?://(?:www\.)?google\.com/recaptcha/", re.I)
# Strona po nieudanej weryfikacji. Składnia wspólna Pythona i JavaScriptu: sterownik sprawdza nią tekst ramek strony
# (Sterownik.jest_wzorzec), wejście napisy ostatniej migawki sesji.
WERYFIKACJA_NIEUDANA = (
    r"weryfikacja (?:negatywna|nieudana|nie powiod[lł]a si[eę])|nie uda[lł]o si[eę] (?:zweryfikowa|potwierdzi)|"
    r"nie mo[zż]emy (?:zweryfikowa|potwierdzi)|(?:could ?n.?t|could not|unable to|failed to) verify|"
    r"verification (?:failed|unsuccessful|expired)|sorry, you have been blocked")
_NIEUDANA = re.compile(WERYFIKACJA_NIEUDANA, re.I)
_DRUGI_POZIOM = frozenset({"co", "com", "org", "net", "gov", "edu", "ac"})


def strona(adres: str) -> str:
    """Strona (domena) adresu karty do liczenia prób weryfikacji: app.dataannotation.tech i
    www.dataannotation.tech to ta sama strona; „example.co.uk” bierze trzy człony."""
    try:
        host = (urlsplit(str(adres or "")).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""
    czlony = host.split(".")
    if len(czlony) > 2 and len(czlony[-1]) == 2 and czlony[-2] in _DRUGI_POZIOM:
        return ".".join(czlony[-3:])
    return ".".join(czlony[-2:])


def weryfikacja_czlowieka(el: Optional[dict]) -> bool:
    """Element okienka „jestem człowiekiem”: jego napis, ramka serwisu weryfikacji (Turnstile, reCAPTCHA, hCaptcha,
    DataDome, Arkose) albo przodek-ramka lub dokument z takim napisem. Każde działanie w takiej ramce to próba (także
    obrazki po pierwszym kliknięciu)."""
    if not el:
        return False
    ramki = [p for p in el.get("sciezka_przodkow") or el.get("przodkowie") or []
             if isinstance(p, dict) and p.get("rola") in ("internal frame", "document web")]
    return bool(WERYFIKACJA.search(zasady._etykieta(el))
                or RAMKA_WERYFIKACJI.search(str(el.get("adres_ramki") or ""))
                or any(WERYFIKACJA.search(zasady._napis(str(p.get("nazwa") or ""))) for p in ramki))


def nieudana_weryfikacja(tekst: str) -> bool:
    return bool(_NIEUDANA.search(zasady._napis(str(tekst or ""))))


def _weryfikacja(el: Optional[dict], args: dict, ctx) -> Optional[zasady.Werdykt]:
    """Jedno kliknięcie okienka „jestem człowiekiem” na stronę w karcie. Kontekst z pamięcią prób (KontekstCDP:
    `weryfikacja(args)` → (strona, próby, nieudana)) dostaje w `proba_weryfikacji` stronę dozwolonej próby; wejście
    liczy ją dopiero, gdy działanie przeszło wszystkie zasady (SesjaNatywna._zapisz)."""
    sprawdz = getattr(ctx, "weryfikacja", None)
    if sprawdz is None or not weryfikacja_czlowieka(el):
        return None
    adres, proby, nieudana = sprawdz(args)
    if not proby and not nieudana:
        ctx.proba_weryfikacji = adres
        return None
    nazwa = adres or "tej stronie"
    przyczyna = ("strona pokazuje nieudaną weryfikację" if nieudana
                 else "jedno kliknięcie na tej stronie w tej karcie już było i nie przeszło")
    return zasady.Werdykt(
        zasady.ODMOWA, "weryfikacja_czlowieka",
        f"okienko „jestem człowiekiem” na {nazwa}: {przyczyna}. Drugiej próby w Komputerze nie ma: nie klikaj go "
        "ponownie, nie zmieniaj przeglądarki ani user-agenta i nie obchodź sprawdzenia. Ten sam krok dokończ teraz "
        "na telefonie floty: MCP `phone` (`third` albo `first`), Chrome na telefonie, to samo konto i ten sam adres. "
        "Telefon też nie przejdzie → zakończ pracę karty na ekranie: `kanban_block` z `kind: needs_input` i jednym "
        f"zdaniem dla właściciela, np. „{nazwa}: sprawdzenie „jestem człowiekiem” nie przepuszcza Komputera ani "
        "telefonu, kliknij je raz na telefonie albo przez VNC”; w rozmowie bez karty to samo zdanie "
        "właścicielowi", zasady.opis(el), {"strona": adres} if adres else {})


def _skrot(args: dict, nazwa: str) -> tuple:
    klawisze = [args.get("key")] + list(args.get("modifiers") or []) if nazwa == "press_key" \
        else list(args.get("keys") or [])
    return zasady._skrot([k for k in klawisze if k])


def _okno_js(el: Optional[dict]) -> Optional[zasady.Werdykt]:
    d = (el or {}).get("dialog")
    if not d or not d.get("akceptuje"):
        return None
    tekst = zasady._napis(str(d.get("wiadomosc") or ""))
    if zasady._wrazliwa_etykieta(tekst) or OKNO_WRAZLIWE.search(tekst):
        return zasady.Werdykt(zasady.CZLOWIEK, "okno_wrazliwe",
                              f"okno potwierdzenia „{zasady._pokaz(str(d.get('wiadomosc') or ''), 80)}” zatwierdza "
                              "właściciel (Anuluj możesz kliknąć sam)", zasady.opis(el))
    return None


def _plik(el: Optional[dict]) -> Optional[zasady.Werdykt]:
    atr = (el or {}).get("atrybuty") or {}
    if (el or {}).get("plik") or (str(atr.get("tag", "")).lower() == "input"
                                  and str(atr.get("text-input-type", "")).lower() == "file"):
        return zasady.Werdykt(zasady.CZLOWIEK, "wybor_pliku", "plik do wysłania wybiera właściciel (wybór pliku "
                              "z jego dysku)", zasady.opis(el))
    return None


def ocen(nazwa: str, args: Optional[dict], ctx) -> Optional[zasady.Werdykt]:
    """Werdykt zasady natywnej albo None (wtedy ocenia rdzeń: zasady.ocen)."""
    args = args if isinstance(args, dict) else {}
    if nazwa not in zasady.DZIALANIA or (ctx.wstrzymane and nazwa not in zasady.SESJA_BEZ_EKRANU):
        return None
    if nazwa in ("press_key", "hotkey"):
        skrot = _skrot(args, nazwa)
        if skrot in SCHOWEK:
            return zasady.Werdykt(zasady.ODMOWA, "schowek", "schowek właściciela jest poza Komputerem: agent nie "
                                  "wkleja z niego i go nie zmienia; tekst wpisz przez type_text")
        if skrot in SKROTY_PRZEGLADARKI:
            return zasady.Werdykt(zasady.ODMOWA, "skrot_przegladarki", f"skrót {'+'.join(skrot)} steruje oknem "
                                  "przeglądarki (pasek adresu, karty, pliki, druk, ustawienia); adres otwórz przez "
                                  "navigate, paskiem adresu (element 0 migawki: klik, type, Enter), launch_app albo "
                                  "linkiem na stronie")
    celowane = zasady._celowane(args)
    if nazwa in ("click", "double_click", "drag", "right_click"):
        el = ctx.cel("click", args) if celowane else None
        if el and not el.get("nieznany"):
            if nazwa == "right_click":
                return _okno_js(el)
            return _okno_js(el) or _plik(el) or _weryfikacja(el, args, ctx)
        return None
    if nazwa in ("press_key", "hotkey"):
        skrot = _skrot(args, nazwa)
        if skrot and len(skrot[-1]) == 1 and not set(skrot[:-1]) - {"shift"}:
            # znak po znaku to też pisanie: numer karty albo kod BLIK wpisany klawiszami tylko ze zgodą `platnosc`
            el = ctx.cel(nazwa, args) if celowane else ctx.fokus(args)
            if el is not None and el.get("nieznany"):
                return zasady.Werdykt(zasady.ODMOWA, "nieznany_cel", "nie wiem, gdzie trafi znak (fokus się zmienił "
                                      "albo pola nie da się sprawdzić); zrób get_window_state i kliknij pole")
            powod = zasady.pole_platnosci(el)
            if powod and not zasady.Zgody(ctx).ma("platnosc"):
                return zasady.Werdykt(zasady.CZLOWIEK, "pole_wrazliwe", f"{powod}: kartę, CVV i BLIK, także znak po "
                                      f"znaku ({zasady._bez_zgody('platnosc')})", zasady.opis(el),
                                      {"kategoria": "platnosc"})
            return None
        if not skrot or skrot[-1] not in zasady.KLAWISZE_AKTYWUJACE:
            return None
        el = ctx.cel(nazwa, args) if celowane else ctx.fokus(args)
        if el and not el.get("nieznany"):
            if skrot[-1] in KLAWISZE_AKCEPTUJACE:
                zly = _okno_js(el)
                if zly:
                    return zly
            return _plik(el) or _weryfikacja(el, args, ctx)
        return None
    if nazwa == "type_text":
        el = ctx.cel(nazwa, args) if celowane else ctx.fokus(args)
        if el and not el.get("nieznany"):
            tekst = str(args.get("text") or "")
            if el.get("dialog") and ("\n" in tekst or "\r" in tekst):
                zly = _okno_js({**el, "dialog": {**el["dialog"], "akceptuje": True}})
                if zly:
                    return zly
        return None
    if nazwa == "set_value":
        el = ctx.cel(nazwa, args)
        return _plik(el) if el and not el.get("nieznany") else None
    return None
