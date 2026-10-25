"""Twarde zasady Komputera natywnie (docs/NATYWNIE.md J05): `infra/komputer/zasady.py` bez zmian + to, czego
przeglądarka na pulpicie właściciela wymaga ponad kontener.

Rdzeń (płatność, zakup, logowanie, wysyłka, publikacja, hasła, karty, kody, sekrety, adresy, skróty narzędzi
deweloperskich, accesskey, okno nieaktywne, pauza) ocenia zasady.ocen na opisie elementu ze sterownika CDP
(role w słowniku zasad: sterownik_cdp.ROLE i rola_zasad). Ten moduł dokłada zasady, które ocenia się PRZED rdzeniem:
  schowek            Ctrl/Cmd+V, Shift+Insert, Ctrl+Shift+V (wklejanie ze schowka właściciela: mógł tam skopiować
                     hasło) oraz Ctrl/Cmd+C, Ctrl/Cmd+X, Ctrl+Insert (agent nie zmienia schowka właściciela): odmowa
  skrot_przegladarki skróty, które w oknie przeglądarki otwierają pasek adresu, nową kartę lub okno, plik z dysku,
                     zapis, druk, historię, pobrane, ustawienia albo przełączają karty: odmowa (adresy idą przez
                     launch_app i linki strony, gdzie sprawdza je zasada adresów i proxy)
  okno_wrazliwe      OK (klik, Enter) w oknie JavaScript (confirm, prompt, beforeunload) z tekstem płatności,
                     zakupu, logowania, wysyłki, publikacji albo usunięcia konta: robi właściciel; Anuluj wolno
  wybor_pliku        klik, Enter albo spacja na polu wyboru pliku (<input type=file>): plik wybiera właściciel
  captcha            klik albo pisanie w CAPTCHA (reCAPTCHA, hCaptcha, Turnstile, „Nie jestem robotem”): robi człowiek
  pole_wrazliwe      pojedynczy znak przez press_key (także z Shift) w polu hasła, karty albo kodu: to też pisanie,
                     więc robi je właściciel (rdzeń sprawdza tak tylko type_text); pole, którego nie da się
                     sprawdzić: odmowa `nieznany_cel`
Pauza (poza odczytem) zostaje dla rdzenia: ocena zwraca None i rdzeń odpowiada `wstrzymane`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional

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
CAPTCHA = re.compile(r"captcha|recaptcha|hcaptcha|turnstile|nie jestem robotem|i'?m not a robot|"
                     r"zweryfikuj,? że jesteś człowiekiem|verify (?:that )?you are (?:a )?human|"
                     r"potwierdź,? że jesteś człowiekiem", re.I)
KLAWISZE_AKCEPTUJACE = zasady.KLAWISZE_ENTER
# Tekst okna JavaScript, którego OK zatwierdza właściciel: rdzenie słów (okno pyta pełnym zdaniem: „Czy na pewno
# zapłacić…?”, a zasady.WRAZLIWE szuka całych słów przycisków). Usunięcie samo w sobie nie (pozycja w koszyku),
# usunięcie konta tak.
OKNO_WRAZLIWE = re.compile(
    r"zap[lł]ac|p[lł]atno|op[lł]ac|przelew|blik|kup|zakup|zam[oó]w|subskryb|wykup|zaloguj|logowan|rejestr|"
    r"wy[sś][lł]|prze[sś][lł]|opublik|publik|udost[eę]pni|usu[nń]\w*\s+(?:\w+\s+)?kont|zamkn\w*\s+(?:\w+\s+)?kont|"
    r"\bpay|\bbuy|purchase|\border|checkout|subscri|sign ?in|log ?in|register|\bsend|submit|publish|\bshare|"
    r"delete\s+(?:\w+\s+)?account|close\s+(?:\w+\s+)?account", re.I)


def _skrot(args: dict, nazwa: str) -> tuple:
    klawisze = [args.get("key")] + list(args.get("modifiers") or []) if nazwa == "press_key" \
        else list(args.get("keys") or [])
    return zasady._skrot([k for k in klawisze if k])


def _napisy(el: Optional[dict]) -> list[str]:
    if not el:
        return []
    napisy = [str(el.get("nazwa") or "")]
    napisy += [str(p.get("nazwa") or "") for p in (el.get("sciezka_przodkow") or el.get("przodkowie") or [])]
    return [n for n in napisy if n]


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


def _captcha(el: Optional[dict]) -> Optional[zasady.Werdykt]:
    for napis in _napisy(el):
        if CAPTCHA.search(zasady._napis(napis)):
            return zasady.Werdykt(zasady.CZLOWIEK, "captcha", "CAPTCHA rozwiązuje człowiek", zasady.opis(el))
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
                                  "przeglądarki (pasek adresu, karty, pliki, druk, ustawienia); adres otwórz paskiem "
                                  "adresu (element 0 migawki: klik, type, Enter), launch_app albo linkiem na stronie")
    celowane = zasady._celowane(args)
    if nazwa in ("click", "double_click", "drag", "right_click"):
        el = ctx.cel("click", args) if celowane else None
        if el and not el.get("nieznany"):
            return _okno_js(el) or (_plik(el) if nazwa != "right_click" else None) or _captcha(el)
        return None
    if nazwa in ("press_key", "hotkey"):
        skrot = _skrot(args, nazwa)
        if skrot and len(skrot[-1]) == 1 and not set(skrot[:-1]) - {"shift"}:
            # znak po znaku to też pisanie: hasło albo kod BLIK wpisany klawiszami robi właściciel
            el = ctx.cel(nazwa, args) if celowane else ctx.fokus(args)
            if el is not None and el.get("nieznany"):
                return zasady.Werdykt(zasady.ODMOWA, "nieznany_cel", "nie wiem, gdzie trafi znak (fokus się zmienił "
                                      "albo pola nie da się sprawdzić); zrób get_window_state i kliknij pole")
            powod = zasady.pole_wrazliwe(el)
            if powod:
                return zasady.Werdykt(zasady.CZLOWIEK, "pole_wrazliwe", f"{powod}: hasło, kartę i kody wpisuje "
                                      "właściciel (także znak po znaku)", zasady.opis(el))
            return None
        if not skrot or skrot[-1] not in zasady.KLAWISZE_AKTYWUJACE:
            return None
        el = ctx.cel(nazwa, args) if celowane else ctx.fokus(args)
        if el and not el.get("nieznany"):
            if skrot[-1] in KLAWISZE_AKCEPTUJACE:
                zly = _okno_js(el)
                if zly:
                    return zly
            return _plik(el) or _captcha(el)
        return None
    if nazwa == "type_text":
        el = ctx.cel(nazwa, args) if celowane else ctx.fokus(args)
        if el and not el.get("nieznany"):
            tekst = str(args.get("text") or "")
            if el.get("dialog") and ("\n" in tekst or "\r" in tekst):
                zly = _okno_js({**el, "dialog": {**el["dialog"], "akceptuje": True}})
                if zly:
                    return zly
            return _captcha(el)
        return None
    if nazwa == "set_value":
        el = ctx.cel(nazwa, args)
        return (_plik(el) or _captcha(el)) if el and not el.get("nieznany") else None
    return None
