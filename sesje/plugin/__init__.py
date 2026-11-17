"""Wtyczka jarvo-sesje: wiadomość właściciela zakończona dopiskiem (np. „gpu”) idzie do innej sesji agenta.

Właściciel ma poza flotą długie sesje agenta kodującego (np. sesja omp o kernelach GPU jego silnika, przeniesiona na
serwer Jarva 13.11). Chce wysyłać do nich tweety i linki z telefonu tym samym botem: wiadomość zakończona słowem
z `<dane>/jarvo/konfig/sesje.json` nie trafia do Jarva, tylko jako plik JSON do skrzynki tej sesji; bot odpowiada
krótkim potwierdzeniem, a odpowiedź sesji wysyła jej własny proces (`jarvo telegram wyslij`).

Hak `pre_gateway_dispatch` (brama, przed autoryzacją i modelem): przechwytuje tylko wiadomości od osoby
z listy dozwolonych; reszta idzie dalej zwykłą drogą. Osobna zwykła wtyczka hosta bramy (plugins.enabled w config.yaml
hosta), nie część jarvo-wiedza: Hermes ładuje dostawcę pamięci dopiero przy pierwszym agencie, więc do 14.11 po każdym
restarcie bramy pierwsza wiadomość „… gpu” trafiała do Jarva. Wiadomość do zajętej rozmowy (Jarvo w trakcie tury)
omija `pre_gateway_dispatch` (gateway/platforms/base.py `_handle_message_while_active` → obsługa zajętej sesji), więc
hak przy każdym wywołaniu owija tę obsługę w adapterach bramy (`set_busy_session_handler`): tak samo łapie „… gpu”
wysłane, gdy Jarvo pracuje (14.11: trzy linki z 04:22 trafiły do jego tury). Wtyczka musi być włączona w każdym
profilu, nie tylko w hoście: brama obsługuje wiadomość w zakresie profilu trasy (DM właściciela → jarvo,
gateway/run_adapters.py `_make_profile_message_handler`) i bierze haki z menedżera wtyczek tego profilu (14.11 14:21:
wtyczka tylko w hoście, wiadomość poszła do Jarva). Konfiguracja (bez sekretów):

    {"gpu": {"nazwa": "Kernel", "skrzynka": "/home/<użytkownik>/kernel/skrzynka", "czat": "-100…", "watek": "7"},
     "sklep": {"nazwa": "Sklep", "profil": "jarvo-sklep"}}

Plik w skrzynce: `nowe/<RRRRMMDD-HHMMSS>-<id wiadomości>.json` z polami dopisek, nazwa, tekst (bez dopisku),
odpowiedz_na (cytowana wiadomość), media (kopie zdjęć i plików obok JSON-a), czas, chat_id, message_id, watek: gdzie
sesja odpowiada. Sesja z wątkiem w grupie (`czat` i `watek` w sesje.json) odpowiada zawsze w swoim wątku, także na
„… gpu” z DM (17.11: DM tylko wejściem zapasowym, odpowiedź Kernela w temacie KERNEL; skąd przyszło: zrodlo_chat_id
i zrodlo_watek). Bez wątku: tam, skąd przyszła (pusty watek w DM = odpowiedź do DM).

Grupa „Jarvo HQ” z tematami (14.11): wątek na agenta. Wpis skrzynki z `czat` i `watek` (zapisuje je
`jarvo telegram tematy`) łapie każdą wiadomość właściciela w tym wątku, bez dopisku. Wpis z `profil` zamiast
`skrzynka` to agent floty: „… sklep” zakłada kartę kanbana przypisaną do tego profilu (API kanbana Hermesa, jak
narzędzie kanban_create; recenzenta wybiera pracownik przy kanban_request_review według floty), bot odpowiada
„📥 Sklep: przyjąłem, karta <id>”. Wpis z `profil`, `czat` i `watek` (temat agenta, np. JARODEV) to rozmowa: wiadomość
w tym temacie hak przepuszcza do bramy profilu (D6 z 17.11), a kartę zakłada tylko dopisek spoza tematu. Każda
wiadomość właściciela w grupie zapisuje też grupę i wątek (nazwa tematu
z `reply_to_message.forum_topic_created`) w `<dane>/jarvo/state/telegram-grupy.json`: stąd `jarvo telegram tematy`
bierze ID grupy i istniejące tematy. Samo „start” w grupie tylko to zapisuje i potwierdza (nie budzi Jarva), a gdy
grupa nie ma jeszcze wątków agentów, dopisuje jedno zlecenie dla Claude Code w `missions/DLA-CLAUDE.md`
(`jarvo telegram tematy`): polecenia na serwerze uruchamia operator, nigdy właściciel (15.11).
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

PLIK_KONFIGURACJI = "sesje.json"
PLIK_GRUP = "telegram-grupy.json"
PLIK_ZLECEN = "DLA-CLAUDE.md"                    # zlecenia dla Claude Code w katalogu misji (SOUL Jarva, zasada 8)
TYPY_GRUP = frozenset({"group", "forum"})        # Hermes: supergrupa = "group" (adapter._build_message_event)
WATEK_OGOLNY = "1"                               # temat General forum (adapter._GENERAL_TOPIC_THREAD_ID)
MAKS_GRUP, MAKS_WATKOW = 20, 200
_OSTATNIE_SLOWO = re.compile(r"(?:^|\s)([^\s]+)\s*$")
_START = re.compile(r"/?start(?:@\w+)?", re.I)
_PROFIL = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
_ID_GRUPY = re.compile(r"-\d{3,20}")
_PRZYJETE: dict[tuple[str, str], float] = {}     # (chat, wiadomość) → czas: ten sam event dwa razy (dwie rejestracje
_PAMIEC_S = 600                                  # wtyczki, ponowienie Telegrama) nie robi drugiego pliku ani potwierdzenia


def _dane() -> Optional[Path]:
    h = os.environ.get("HERMES_HOME")
    if not h:
        return None
    p = Path(h)
    return p.parent.parent if p.parent.name == "profiles" else p


def konfiguracja(dane: Optional[Path] = None) -> dict[str, dict]:
    """Dopisek (małe litery) → {nazwa, skrzynka[, czat, watek]} albo {nazwa, profil}; brak pliku albo błąd = nic."""
    dane = dane or _dane()
    if dane is None:
        return {}
    try:
        surowe = json.loads((dane / "jarvo" / "konfig" / PLIK_KONFIGURACJI).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    wynik = {}
    for dopisek, wpis in (surowe if isinstance(surowe, dict) else {}).items():
        if not isinstance(wpis, dict):
            continue
        klucz, nazwa = str(dopisek).strip().lower(), str(wpis.get("nazwa") or dopisek)
        if wpis.get("skrzynka"):
            cel = {"nazwa": nazwa, "skrzynka": str(wpis["skrzynka"])}
            if wpis.get("czat") and wpis.get("watek"):
                cel.update(czat=str(wpis["czat"]), watek=str(wpis["watek"]))
            wynik[klucz] = cel
        elif _PROFIL.fullmatch(str(wpis.get("profil") or "")):
            cel = {"nazwa": nazwa, "profil": str(wpis["profil"])}
            if wpis.get("czat") and wpis.get("watek"):     # temat agenta w grupie = rozmowa z jego bramą (D6)
                cel.update(czat=str(wpis["czat"]), watek=str(wpis["watek"]))
            wynik[klucz] = cel
    return wynik


def rozpoznaj(tekst: str, dopiski: dict[str, dict]) -> Optional[tuple[str, str]]:
    """(dopisek, tekst bez dopisku), gdy ostatnie słowo wiadomości to dopisek („… gpu”, „…, GPU.”); inaczej None."""
    m = _OSTATNIE_SLOWO.search(tekst or "")
    if not m:
        return None
    slowo = m.group(1).strip(".,;:!?…\"'()").lower()
    if slowo not in dopiski:
        return None
    return slowo, tekst[: m.start(1)].rstrip(" \t\n,;:-–—")


def _rdzen(event: Any) -> tuple[str, str]:
    mid = re.sub(r"[^0-9A-Za-z_-]", "", str(getattr(event, "message_id", "") or "")) or "0"
    return f"{time.strftime('%Y%m%d-%H%M%S')}-{mid}", mid


def _kopiuj_media(event: Any, katalog: Path, rdzen: str) -> list[str]:
    media = []
    for i, sciezka in enumerate(getattr(event, "media_urls", None) or []):
        p = Path(str(sciezka))
        if p.is_file():
            katalog.mkdir(parents=True, exist_ok=True)
            cel = katalog / f"{rdzen}-{i}{p.suffix}"
            shutil.copy2(p, cel)
            media.append(str(cel))
    return media


def _zapisz_atomowo(plik: Path, tresc: str) -> None:
    plik.parent.mkdir(parents=True, exist_ok=True)
    tymczasowy = plik.with_name(f".{plik.name}.{os.getpid()}.tmp")
    tymczasowy.write_text(tresc, encoding="utf-8")
    tymczasowy.replace(plik)


def _watek_grupy(zrodlo: Any) -> str:
    """Wątek grupy (forum: General = "1"); pusty poza grupą, bo w DM sesja odpowiada właścicielowi wprost."""
    if str(getattr(zrodlo, "chat_type", "") or "") not in TYPY_GRUP:
        return ""
    return str(getattr(zrodlo, "thread_id", "") or "")


def zapisz(skrzynka: Path, dopisek: str, cel: dict, tekst: str, event: Any) -> Path:
    """Wiadomość jako JSON w `nowe/` (zapis przez plik tymczasowy, więc proces sesji nie przeczyta połowy). chat_id
    i watek = gdzie sesja odpowiada: jej wątek w grupie, gdy go ma, inaczej czat i wątek wiadomości."""
    nowe = skrzynka / "nowe"
    nowe.mkdir(parents=True, exist_ok=True)
    zrodlo = getattr(event, "source", None)
    rdzen, mid = _rdzen(event)
    czat, watek = str(getattr(zrodlo, "chat_id", "") or ""), _watek_grupy(zrodlo)
    wpis = {"dopisek": dopisek, "nazwa": cel["nazwa"], "tekst": tekst,
            "odpowiedz_na": getattr(event, "reply_to_text", None) or "",
            "media": _kopiuj_media(event, nowe, rdzen), "czas": time.strftime("%Y-%m-%d %H:%M:%S"),
            "chat_id": cel.get("czat") or czat, "message_id": mid, "watek": cel.get("watek") or watek,
            "zrodlo_chat_id": czat, "zrodlo_watek": watek}
    tymczasowy = nowe / f".{rdzen}.json.tmp"
    tymczasowy.write_text(json.dumps(wpis, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    plik = nowe / f"{rdzen}.json"
    tymczasowy.replace(plik)
    return plik


# ---------------------------------------------------------------- karta kanbana (wpis z `profil`)

def tytul_karty(tekst: str, slow: int = 10, znakow: int = 80) -> str:
    """Pierwsze słowa pierwszej niepustej linii (do `slow` słów i `znakow` znaków)."""
    linia = next((x.strip() for x in (tekst or "").splitlines() if x.strip()), "")
    slowa = linia.split()
    tytul = " ".join(slowa[:slow])
    if len(tytul) > znakow:
        return tytul[: znakow - 1].rstrip() + "…"
    return (tytul + ("…" if len(slowa) > slow else "")) or "Wiadomość od właściciela z Telegrama"


def tresc_karty(tekst: str, dopisek: str, event: Any, media: list[str]) -> str:
    czesci = [tekst or "(bez tekstu)"]
    if getattr(event, "reply_to_text", None):
        czesci.append(f"Odpowiedź na wiadomość:\n{event.reply_to_text}")
    if media:
        czesci.append("Załączniki:\n" + "\n".join(f"- {m}" for m in media))
    czesci.append(f"— od właściciela przez Telegram, dopisek {dopisek}")
    return "\n\n".join(czesci)


def zaloz_karte(profil: str, tytul: str, tresc: str, klucz: str) -> str:
    """Karta na tablicy floty przez API kanbana Hermesa (hermes_cli/kanban_db.py create_task, jak narzędzie
    kanban_create w tools/kanban_tools.py); `klucz` (idempotency_key) = ta sama wiadomość nie robi drugiej karty."""
    from hermes_cli import kanban_db as kb
    from hermes_cli import kanban_db_connect as kbc
    with kbc.connect_closing() as conn:
        return str(kb.create_task(conn, title=tytul, body=tresc, assignee=profil, created_by="user",
                                  idempotency_key=klucz))


def karta(cel: dict, dopisek: str, tekst: str, event: Any, dane: Optional[Path]) -> str:
    rdzen, mid = _rdzen(event)
    media = _kopiuj_media(event, dane / "jarvo" / "workspaces" / "telegram", rdzen) if dane else []
    czat = str(getattr(getattr(event, "source", None), "chat_id", "") or "")
    return zaloz_karte(cel["profil"], tytul_karty(tekst), tresc_karty(tekst, dopisek, event, media),
                       f"telegram:{czat}:{mid}")


# ---------------------------------------------------------------- grupa „Jarvo HQ”: wykrycie grupy i wątków

def nazwa_tematu(event: Any) -> str:
    """Nazwa tematu forum: wiadomość w temacie odpowiada na usługową `forum_topic_created` (Bot API), a zmiana nazwy
    przychodzi jako `forum_topic_edited`; bez nich nazwa z wiązań tematów Hermesa (`chat_topic`)."""
    surowa = getattr(event, "raw_message", None)
    for usluga in (getattr(surowa, "forum_topic_edited", None), getattr(surowa, "forum_topic_created", None),
                   getattr(getattr(surowa, "reply_to_message", None), "forum_topic_created", None)):
        nazwa = getattr(usluga, "name", None)
        if isinstance(nazwa, str) and nazwa.strip():
            return nazwa.strip()
    temat = getattr(getattr(event, "source", None), "chat_topic", None)
    return temat.strip() if isinstance(temat, str) else ""


def zapamietaj_grupe(event: Any, dane: Optional[Path] = None) -> bool:
    """Grupa i wątek wiadomości właściciela → `<dane>/jarvo/state/telegram-grupy.json` (zapis tylko przy zmianie).
    Kształt: {"grupy": {"-100…": {"nazwa", "forum", "od", "watki": {"<wątek>": {"nazwa", "od"}}}}}."""
    dane = dane or _dane()
    zrodlo = getattr(event, "source", None)
    czat = str(getattr(zrodlo, "chat_id", "") or "")
    if dane is None or str(getattr(zrodlo, "chat_type", "") or "") not in TYPY_GRUP or not _ID_GRUPY.fullmatch(czat):
        return False
    plik = dane / "jarvo" / "state" / PLIK_GRUP
    try:
        stan = json.loads(plik.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        stan = {}
    grupy = stan.get("grupy") if isinstance(stan, dict) and isinstance(stan.get("grupy"), dict) else {}
    stara = grupy.get(czat) if isinstance(grupy.get(czat), dict) else {}
    teraz = time.strftime("%Y-%m-%d %H:%M:%S")
    surowa = getattr(event, "raw_message", None)
    nowa = {**stara, "od": stara.get("od") or teraz}
    nazwa = getattr(zrodlo, "chat_name", None) or getattr(getattr(surowa, "chat", None), "title", None)
    if isinstance(nazwa, str) and nazwa.strip():
        nowa["nazwa"] = nazwa.strip()
    forum = getattr(getattr(surowa, "chat", None), "is_forum", None)
    if isinstance(forum, bool):
        nowa["forum"] = forum
    watki = dict(stara.get("watki") or {})
    watek = str(getattr(zrodlo, "thread_id", "") or "")
    if watek:
        byl = watki.get(watek) if isinstance(watki.get(watek), dict) else {}
        temat = nazwa_tematu(event) or byl.get("nazwa") or ("General" if watek == WATEK_OGOLNY else "")
        if not byl or byl.get("nazwa") != temat:
            watki[watek] = {"nazwa": temat, "od": byl.get("od") or teraz}
        if len(watki) > MAKS_WATKOW:
            watki = dict(sorted(watki.items(), key=lambda kv: str(kv[1].get("od", "")))[-MAKS_WATKOW:])
    nowa["watki"] = watki
    if nowa == stara:
        return False
    grupy = {**grupy, czat: nowa}
    if len(grupy) > MAKS_GRUP:
        grupy = dict(sorted(grupy.items(), key=lambda kv: str(kv[1].get("od", "")))[-MAKS_GRUP:])
    _zapisz_atomowo(plik, json.dumps({"grupy": grupy}, ensure_ascii=False, indent=1) + "\n")
    return True


def zlec_tematy(czat: str, dopiski: dict[str, dict], dane: Optional[Path] = None) -> bool:
    """„start” w grupie bez wątków agentów: zlecenie `jarvo telegram tematy --grupa <czat>` dla Claude Code
    (operatora) w `<dane>/jarvo/missions/DLA-CLAUDE.md`; jedno otwarte na grupę. Bez zlecenia, gdy któraś skrzynka
    ma już wątek w tej grupie (tematy założone). 14.11 bot kazał właścicielowi uruchomić to na serwerze."""
    dane = dane or _dane()
    if dane is None or not _ID_GRUPY.fullmatch(czat) or any(c.get("czat") == czat for c in dopiski.values()):
        return False
    plik = dane / "jarvo" / "missions" / PLIK_ZLECEN
    try:
        tekst = plik.read_text(encoding="utf-8")
    except FileNotFoundError:
        tekst = "# Zlecenia dla Claude Code\n"
    polecenie = f"jarvo telegram tematy --grupa {czat}"
    if any(l.startswith("- [ ]") and polecenie in l for l in tekst.splitlines()):
        return False
    wiersz = (f"- [ ] {time.strftime('%Y-%m-%d')} · `{polecenie}` (właściciel napisał „start” w grupie Jarvo HQ) · wątki "
              f"agentów w grupie, właściciel nie uruchamia poleceń na serwerze · {dane / 'jarvo' / 'state' / PLIK_GRUP}")
    plik.parent.mkdir(parents=True, exist_ok=True)
    _zapisz_atomowo(plik, tekst.rstrip("\n") + "\n" + wiersz + "\n")
    return True


# ---------------------------------------------------------------- hak bramy

def _cel_watku(dopiski: dict[str, dict], zrodlo: Any) -> Optional[tuple[str, dict]]:
    """Skrzynka, której wątek w grupie to wątek tej wiadomości (wpis z `czat` i `watek`)."""
    czat, watek = str(getattr(zrodlo, "chat_id", "") or ""), _watek_grupy(zrodlo)
    if not watek:
        return None
    return next(((d, c) for d, c in dopiski.items() if c.get("watek") == watek and c.get("czat") == czat), None)


async def _odpowiedz(gateway: Any, zrodlo: Any, tekst: str) -> None:
    """Potwierdzenie tam, skąd przyszła wiadomość (w grupie do tego samego wątku); to grzeczność, nie warunek."""
    adapter = getattr(gateway, "_delivery_adapter_for", lambda _s: None)(zrodlo)
    if adapter is None:
        return
    watek = _watek_grupy(zrodlo)
    try:
        if watek:
            await adapter.send(zrodlo.chat_id, tekst, metadata={"thread_id": watek})
        else:
            await adapter.send(zrodlo.chat_id, tekst)
    except Exception as e:
        logger.warning("jarvo-sesje: potwierdzenie nie wyszło: %s", e)


def _juz_przyjeta(zrodlo: Any, event: Any) -> tuple[tuple[str, str], bool]:
    klucz = (str(getattr(zrodlo, "chat_id", "") or ""), str(getattr(event, "message_id", "") or ""))
    teraz = time.time()
    for k in [k for k, t in _PRZYJETE.items() if teraz - t > _PAMIEC_S]:
        del _PRZYJETE[k]
    if klucz[1] and klucz in _PRZYJETE:
        return klucz, True
    _PRZYJETE[klucz] = teraz
    return klucz, False


async def przechwyc(event: Any = None, gateway: Any = None, **_kw) -> Optional[dict]:
    """Hak `pre_gateway_dispatch`: wiadomość z dopiskiem albo z wątku sesji → skrzynka / karta + potwierdzenie,
    Jarvo jej nie dostaje. W grupie zapisuje też grupę i wątek („start” tylko to). Reszta idzie dalej bez zmian."""
    try:
        if event is None or getattr(event, "internal", False) or not isinstance(getattr(event, "text", None), str):
            return None
        zrodlo = getattr(event, "source", None)
        dopiski = konfiguracja()
        w_grupie = str(getattr(zrodlo, "chat_type", "") or "") in TYPY_GRUP
        z_watku = _cel_watku(dopiski, zrodlo) if dopiski else None
        start = w_grupie and bool(_START.fullmatch(event.text.strip()))
        trafienie = rozpoznaj(event.text, dopiski) if dopiski and not (z_watku or start) else None
        if not (w_grupie or z_watku or trafienie):
            return None
        autoryzacja = getattr(gateway, "_is_user_authorized_for_source", None)
        if zrodlo is None or not callable(autoryzacja) or not autoryzacja(zrodlo):
            return None                       # obcy nadawca idzie zwykłą drogą (parowanie / odmowa Hermesa)
        if w_grupie:
            try:
                zapamietaj_grupe(event)
            except Exception as e:            # wykrycie grupy to dodatek: wiadomość idzie dalej
                logger.warning("jarvo-sesje: zapis grupy Telegrama: %s", e)
        if start:
            _klucz, bylo = _juz_przyjeta(zrodlo, event)
            if not bylo:
                temat = nazwa_tematu(event) or ("General" if _watek_grupy(zrodlo) == WATEK_OGOLNY else "")
                try:
                    zlec_tematy(str(getattr(zrodlo, "chat_id", "") or ""), dopiski)
                except Exception as e:            # zlecenie to dodatek: potwierdzenie idzie i tak
                    logger.warning("jarvo-sesje: zlecenie wątków: %s", e)
                await _odpowiedz(gateway, zrodlo, f"✅ Jarvo HQ: zapisałem ten wątek{f' „{temat}”' if temat else ''}. "
                                 "Wątki agentów zakłada operator, Ty nic nie uruchamiasz.")
            return {"action": "skip", "reason": "start w grupie Jarvo HQ (zapis wątku)"}
        if z_watku and z_watku[1].get("profil"):
            # temat agenta floty (np. JARODEV) to rozmowa: wiadomość idzie dalej do bramy jego profilu, bez karty
            return None
        if z_watku:
            dopisek, cel = z_watku
            wlasny = rozpoznaj(event.text, {dopisek: cel})
            tekst = wlasny[1] if wlasny else event.text.strip()
        elif trafienie:
            dopisek, tekst = trafienie
            cel = dopiski[dopisek]
        else:
            return None
        klucz, bylo = _juz_przyjeta(zrodlo, event)
        if bylo:
            return {"action": "skip", "reason": f"dopisek „{dopisek}” (już przyjęta)"}
        try:
            if cel.get("profil"):
                ident = karta(cel, dopisek, tekst, event, _dane())
                potwierdzenie = f"📥 {cel['nazwa']}: przyjąłem, karta {ident}."
            else:
                skrzynka = Path(os.path.expanduser(cel["skrzynka"]))
                zapisz(skrzynka, dopisek, cel, tekst, event)
                w_kolejce = len(list((skrzynka / "nowe").glob("*.json")))
                potwierdzenie = (f"📥 {cel['nazwa']}: przyjąłem, analizuję"
                                 + (f" (w kolejce: {w_kolejce})" if w_kolejce > 1 else "") + "."
                                 + (f" Odpowiedź w temacie {cel['nazwa'].upper()}."
                                    if cel.get("watek") and not _watek_grupy(zrodlo) else ""))
        except Exception:
            _PRZYJETE.pop(klucz, None)        # ponowienie ma szansę; tę wiadomość dostaje Jarvo
            raise
        await _odpowiedz(gateway, zrodlo, potwierdzenie)
        return {"action": "skip", "reason": f"dopisek „{dopisek}”"}
    except Exception as e:                    # awaria haka nigdy nie gubi wiadomości: idzie do Jarva
        logger.warning("jarvo-sesje: skrzynka sesji: %s", e)
        return None


ZNACZNIK = "_jarvo_sesje"


def owin_zajete(gateway: Any) -> int:
    """Obsługa wiadomości do zajętej rozmowy w każdym adapterze bramy najpierw pyta skrzynki sesji; zwraca liczbę nowo
    owiniętych. Adapter po ponownym połączeniu dostaje od Hermesa świeżą obsługę, więc hak sprawdza to przy każdej
    wiadomości (owinięta obsługa ma ZNACZNIK, drugi raz jej nie owijamy)."""
    nowe = 0
    for adapter in list((getattr(gateway, "adapters", None) or {}).values()):
        ustaw = getattr(adapter, "set_busy_session_handler", None)
        obecna = getattr(adapter, "_busy_session_handler", None)
        if not callable(ustaw) or getattr(obecna, ZNACZNIK, False):
            continue

        async def zajeta(event, session_key, _obecna=obecna):
            wynik = await przechwyc(event=event, gateway=gateway)
            if isinstance(wynik, dict) and wynik.get("action") == "skip":
                return True                    # obsłużona: w skrzynce sesji, Jarvo jej nie dostaje
            return bool(await _obecna(event, session_key)) if _obecna is not None else False

        setattr(zajeta, ZNACZNIK, True)
        ustaw(zajeta)
        nowe += 1
    return nowe


async def hak_bramy(event: Any = None, gateway: Any = None, **kw) -> Optional[dict]:
    """Hak `pre_gateway_dispatch`: najpierw obsługa zajętej rozmowy w adapterach, potem ta wiadomość."""
    try:
        if owin_zajete(gateway):
            logger.info("jarvo-sesje: skrzynki sesji łapią też wiadomości do zajętej rozmowy")
    except Exception as e:                    # bez owinięcia zajęta rozmowa działa jak w Hermesie; wiadomość idzie dalej
        logger.warning("jarvo-sesje: obsługa zajętej rozmowy bez skrzynek sesji: %s", e)
    return await przechwyc(event=event, gateway=gateway, **kw)


def register(ctx) -> None:
    """Zwykła wtyczka hosta bramy: hak rejestrowany przy starcie bramy (stan-jarva sprawdza ten wpis w gateway.log)."""
    ctx.register_hook("pre_gateway_dispatch", hak_bramy)
    try:                                      # zakres menedżera wtyczek: host (<dane>) albo profil (ładowany przy 1. wiadomości)
        from hermes_constants import get_hermes_home
        gdzie = Path(get_hermes_home()).name
    except Exception:
        gdzie = "?"
    logger.info("jarvo-sesje: przekierowanie dopisków aktywne (%s; profil %s)",
                ", ".join(sorted(konfiguracja())) or "brak skrzynek", gdzie)
