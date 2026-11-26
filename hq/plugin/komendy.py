"""Komendy po `/` w panelu Jarvo (docs/HQ.md „Komendy”): `/model`, `/effort`, `/fast`, `/new`, `/stop`, `/usage`,
`/context`, `/status`, `/compact` (omp), `/help`, oraz stopka rozmowy (`GET /rozmowy/{id}/licznik` i `…/opcje`).

Brama Hermesa (API server: `/v1/runs`, `/api/sessions`) nie wykonuje komend: `input` przebiegu idzie prosto do
`AIAgent.run_conversation`, a obsługa `/…` żyje tylko w GatewayRunnerze kanałów (Telegram, Discord). Dlatego panel
nigdy nie wysyła `/komendy` agentowi jako tekstu (trasa wiadomości odpowiada 409 `komenda`) i wykonuje je sam, tymi
samymi drogami co Hermes:

- **`/model`** (Hermes): lista i bieżący model z `GET /api/model/options` profilu (ten sam wybór co `/model`
  w Telegramie i strona Modele); wybór dotyczy sesji członka w tej rozmowie (`rozmowy.ustaw_model_czlonka`), a przebieg
  wysyła go w ciele `/v1/runs` jako `model` + `provider` (brama: per-request selection). `--global` zapisuje model
  w config.yaml profilu funkcją dashboardu Hermesa (`_write_profile_model`, jak `PUT /api/profiles/{name}/model`)
  i zdejmuje wybór rozmowy. omp: lista z `omp models --json`, wybór w `<skrzynka>/model.json` (omp_sesje), tura
  skrzynki dostaje `--model`.
- **`/new`** (alias `/reset`, Hermes): zatrzymuje pracę agenta w rozmowie i zaczyna nową sesję członka (rotacja
  w rodowodzie: oś pokazuje dalej starą, agent zaczyna bez historii). Sesja omp jest stała we wpisie sesje.json.
- **`/stop`**: zatrzymuje pracę w rozmowie (jak Esc Esc). **`/usage`**: tokeny przebiegów rozmowy (Hermes, `usage`
  ze stanu przebiegu) albo sesji omp (plik sesji). **`/status`**: agent, zaplecze, sesja, model, zużycie.
  **`/context`** (alias `/ctx`): to, co pokazuje licznik pod kompozytorem, jako tekst.
- **`/compact`** (alias `/compress`) w sesji omp: komenda RPC skrzynki (`omp_sesje.komenda` + `wynik_komendy`), także
  w trakcie tury; wynik w rozmowie od razu, a gdy kompresja trwa dłużej niż `KOMENDA_CZEKAJ_S`, drugi wpis z wynikiem
  po jej końcu. Komendy, które skrzynka zgłasza w `omp_sesje.komendy_omp`, też działają tą drogą. Dla Hermesa
  `/compress` jest niedostępne: brama API nie ma kompresji na żądanie (nie wykonuje komend: `input` idzie do modelu,
  `PATCH /api/sessions/{id}` zmienia tylko pola sesji), a ręczna kompresja żyje tylko w GatewayRunnerze kanałów
  (`gateway/slash_commands_session.py` `_run_manual_compression`: tymczasowy AIAgent z poświadczeniami profilu, blokada
  kompresji, rotacja sesji, zrzut agenta z pamięci bramy). Dashboard nie może tego zrobić bez poświadczeń profilu
  i wyścigu z bramą; trzeba trasy w bramie (np. `POST /api/sessions/{id}/compress` na tym samym rdzeniu).
- **`/help`** (alias `/commands`): komendy tej rozmowy. Pozostałe komendy z rejestru Hermesa
  (`hermes_cli.commands.COMMAND_REGISTRY`, bez `cli_only`) lista pokazuje jako niedostępne w panelu z powodem.
- **`/effort`** (alias `/thinking`, `/reasoning`) i **`/fast`**: wysiłek myślenia i tryb szybki dla tej rozmowy, jak
  `/model`. Hermes: `meta` rozmowy (`przebiegi.opcje_czlonka`), przebieg wysyła je w `model_options.reasoning_effort`
  i `model_options.fast` ciała `/v1/runs` (poziomy `przebiegi.WYSILKI_HERMESA`; tryb szybki tylko dla modeli, które
  Hermes ma za szybkie: `model_supports_fast_mode`). omp: `<skrzynka>/model.json` (`myslenie`, `fast`), skrzynka
  stosuje je w procesie RPC (`set_thinking_level`, `set_fast_mode`) przed turą; poziomy z katalogu `omp models --json`
  (`thinking` modelu i `off`).
- **Licznik** (`Wykonawca.licznik`): model, wysiłek, tryb szybki, kontekst (tokeny i % okna), tokeny wejścia
  i wyjścia, cache, koszt. omp: `omp_sesje.licznik` (skrzynka odświeża go w trakcie tury; bez niej plik sesji czytany
  przyrostowo), okno bez skrzynki z katalogu modeli omp (`katalog_omp`, w tle co 6 h), `koszt_dzis` = koszt odpowiedzi
  z dzisiaj (koszt sesji to równoważnik cen API). Hermes: liczniki i koszt z wierszy `sessions` rodowodu członka
  (`czytnik.zuzycie`, Hermes pisze je w trakcie tury; dolnym progiem jest suma `usage` przebiegów rozmowy), kontekst
  szacowany z rozmiaru aktywnych wierszy najnowszej sesji (znaki / 4, `szacunek`), okno z metadanych modelu Hermesa
  (`okno_modelu`). `Wykonawca.opcje` (stopka po kliknięciu): modele do wyboru, poziomy wysiłku, tryb szybki.

Wynik w rozmowie to wpis systemowy `{typ: "komenda", polecenie, agent, ok, wynik, wynik_en, wybor}` (scalanie nie
daje go do bloku kontekstu agenta), poza rozmową (ekran startu) tylko odpowiedź trasy. Trasy: `GET /komendy`
(katalog dla rozmowy), `POST /komendy` `{tekst, klucz, watek?, agent?}`; ten sam `klucz` w rozmowie = ten sam wpis
bez drugiego wykonania. Testy: tests/test_komendy.py.
"""

from __future__ import annotations

import asyncio
import functools
import json
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from fastapi import Request
from pydantic import Field

KOMENDA_RE = re.compile(r"/([A-Za-z][A-Za-z0-9_-]{0,31})(?:@[\w.-]+)?(?:\s+(.*))?", re.S)
TEKST_MAKS = 2000
MODELE_NA_DOSTAWCE = 8
DOSTAWCY_MAKS = 8
KANDYDACI_MAKS = 12
DO_ZATRZYMANIA = ("wysylanie", "przyjety", "pracuje", "czeka_na_ture", "czeka_na_zgode", "zatrzymywanie")
KOMENDA_CZEKAJ_S = 2.0           # tyle trasa czeka na wynik komendy skrzynki omp (wpis „trwa” widać od razu), potem
                                 # wynik przychodzi drugim wpisem (25.11: przy 20 s kliknięcie nic nie pokazywało)
KOMENDA_MAKS_S = 900.0           # dłużej komenda skrzynki nie może trwać (potem wpis „nie skończyła się”)
OKNO_PAMIEC_S = 600.0            # okno kontekstu modelu pamiętane 10 min (metadane Hermesa mogą pytać sieci)
KATALOG_OMP_S = 6 * 3600.0       # katalog modeli omp (okna, poziomy myślenia) odświeżany co 6 h, w tle
LICZNIK_ZERO = {"model": "", "kontekst": 0, "okno": 0, "procent": 0.0, "wejscie": 0, "wyjscie": 0, "cache_odczyt": 0,
                "cache_zapis": 0, "koszt": 0.0, "koszt_dzis": 0.0, "czas": 0.0}
# dostawcy modeli w wybieraku stopki (23.11 właściciel: „modele mają być podzielone na subskrypcje”): slug →
# (nazwa, rodzaj: subskrypcja = w cenie abonamentu, klucz = płatne za tokeny); nieznany slug: nazwa z bramy,
# rodzaj po końcówce `-api`
DOSTAWCY_OPIS = {
    "anthropic": ("Claude", "subskrypcja"), "anthropic-api": ("Anthropic API", "klucz"),
    "commandcode": ("Command Code", "subskrypcja"), "openai-codex": ("ChatGPT", "subskrypcja"),
    "google-antigravity": ("Antigravity", "subskrypcja"), "google-gemini-cli": ("Gemini CLI", "subskrypcja"),
    "openrouter": ("OpenRouter", "klucz"), "openai": ("OpenAI API", "klucz"), "deepseek": ("DeepSeek API", "klucz"),
    "xai": ("xAI API", "klucz"), "gemini": ("Gemini API", "klucz"),
}
_DATOWANY = re.compile(r"-\d{8}$")


def parsuj(tekst: str) -> tuple[str, str] | None:
    """(nazwa małymi literami, argumenty) albo None, gdy tekst nie jest komendą. `/etc/hosts …` i `//…` to zwykły
    tekst (po nazwie musi być spacja albo koniec), `/model@bot` jak w Telegramie."""
    m = KOMENDA_RE.fullmatch((tekst or "").strip())
    if not m:
        return None
    return m.group(1).lower(), (m.group(2) or "").strip()


# ----------------------------------------------------------------------------------------------- katalog

@dataclass(frozen=True)
class Def:
    nazwa: str
    opis: str
    opis_en: str
    argumenty: str = ""
    aliasy: tuple[str, ...] = ()
    zaplecza: tuple[str, ...] = ("hermes", "omp")     # gdzie panel ją wykonuje
    powody: Mapping[str, tuple[str, str]] = field(default_factory=dict)   # zaplecze → (pl, en): czemu nie


PANEL: tuple[Def, ...] = (
    Def("model", "Pokaż model albo zmień go w tej rozmowie", "Show the model or switch it in this conversation",
        "[model] [--provider nazwa] [--global]"),
    Def("new", "Nowa sesja agenta: zaczyna bez wcześniejszej historii", "New agent session: starts without the earlier history",
        aliasy=("reset",), zaplecza=("hermes",),
        powody={"omp": ("Sesja omp jest stała we wpisie sesje.json; nową zaczyna się w terminalu omp.",
                        "The omp session is fixed in its sesje.json entry; start a new one in the omp terminal.")}),
    Def("stop", "Zatrzymaj trwającą pracę w tej rozmowie", "Stop the work running in this conversation"),
    Def("usage", "Zużycie tokenów w tej rozmowie", "Token usage in this conversation"),
    Def("status", "Sesja, model i zużycie agenta", "Agent session, model and usage"),
    Def("context", "Kontekst: model, tokeny i % okna, cache, koszt", "Context: model, tokens and % of the window, cache, cost",
        aliasy=("ctx",)),
    Def("compact", "Skompresuj kontekst sesji (opcjonalnie: na czym się skupić)",
        "Compact the session context (optionally: what to focus on)", "[instrukcje]", aliasy=("compress",),
        zaplecza=("omp",),
        powody={"hermes": ("Brama Hermesa nie ma kompresji na żądanie dla sesji z panelu (tylko automatyczną przy progu "
                           "kontekstu); ręczne /compress działa w Telegramie i w terminalu. Czysta sesja: /new.",
                           "The Hermes gateway has no on-demand compression for panel sessions (only the automatic one "
                           "at the context threshold); a manual /compress works in Telegram and in the terminal. For a "
                           "clean session: /new.")}),
    Def("effort", "Wysiłek myślenia modelu w tej rozmowie", "Model thinking effort in this conversation", "[poziom]",
        aliasy=("thinking", "reasoning")),
    Def("fast", "Tryb szybki modelu (wyższy priorytet u dostawcy)", "Model fast mode (higher priority at the provider)",
        "[on|off]"),
    Def("help", "Komendy dostępne w tej rozmowie", "Commands available in this conversation", aliasy=("commands",)),
)
_PANEL = {n: d for d in PANEL for n in (d.nazwa, *d.aliasy)}
INNE_HERMES = ("Tej komendy Hermesa panel nie wykonuje (brama nie ma dla niej API). Użyj jej w Telegramie albo "
               "w terminalu (`hermes`).",
               "The panel does not run this Hermes command (the gateway has no API for it). Use it in Telegram or in "
               "the terminal (`hermes`).")


def rejestr_hermesa() -> list[dict]:
    """Komendy kanałów z rejestru Hermesa (bez `cli_only`): {nazwa, aliasy, opis_en, argumenty}. Bez Hermesa
    w procesie (testy) pusta lista."""
    try:
        from hermes_cli.commands import COMMAND_REGISTRY  # noqa: PLC0415
    except Exception:
        return []
    out = []
    for c in COMMAND_REGISTRY:
        if getattr(c, "cli_only", False):
            continue
        out.append({"nazwa": c.name, "aliasy": list(c.aliases or ()), "opis_en": c.description or "",
                    "argumenty": c.args_hint or ""})
    return out


def katalog(zaplecze: str, rejestr: Iterable[Mapping] | None = None, omp: Iterable[Mapping] = ()) -> list[dict]:
    """Komendy rozmowy: najpierw te, które panel wykonuje (w sesji omp także te, które zgłasza skrzynka:
    `omp_sesje.komendy_omp`), potem niedostępne (z powodem), potem reszta rejestru Hermesa (tylko w rozmowie
    z agentem Hermesa)."""
    dzialaja, nie = [], []
    for d in PANEL:
        powod = d.powody.get(zaplecze) or ("", "")
        wpis = {"nazwa": d.nazwa, "aliasy": list(d.aliasy), "opis": d.opis, "opis_en": d.opis_en, "panel": True,
                "argumenty": d.argumenty, "dziala": zaplecze in d.zaplecza, "powod": powod[0], "powod_en": powod[1]}
        (dzialaja if wpis["dziala"] else nie).append(wpis)
    if zaplecze == "omp":
        for c in omp:
            if c.get("nazwa") and c["nazwa"] not in _PANEL:
                dzialaja.append({"nazwa": c["nazwa"], "aliasy": [], "opis": c.get("opis") or "", "opis_en": c.get("opis") or "",
                                 "panel": False, "argumenty": "", "dziala": True, "powod": "", "powod_en": ""})
    if zaplecze == "hermes":
        znane = set(_PANEL)
        for c in rejestr_hermesa() if rejestr is None else rejestr:
            if c["nazwa"] in znane:
                continue
            znane.add(c["nazwa"])
            nie.append({"nazwa": c["nazwa"], "aliasy": list(c.get("aliasy") or []), "opis": c.get("opis_en") or "",
                        "opis_en": c.get("opis_en") or "", "argumenty": c.get("argumenty") or "", "dziala": False,
                        "panel": False, "powod": INNE_HERMES[0], "powod_en": INNE_HERMES[1]})
    return dzialaja + nie


# ----------------------------------------------------------------------------------------------- wynik

class Wynik:
    """Odpowiedź komendy w dwóch językach (Markdown linia po linii) i przyciski wyboru modelu."""

    def __init__(self, ok: bool = True):
        self.ok, self.pl, self.en, self.wybor = ok, [], [], []

    def linia(self, pl: str, en: str | None = None) -> "Wynik":
        self.pl.append(pl)
        self.en.append(pl if en is None else en)
        return self

    def dane(self) -> dict:
        return {"ok": self.ok, "wynik": "\n".join(self.pl).strip(), "wynik_en": "\n".join(self.en).strip(),
                "wybor": self.wybor}


def blad(pl: str, en: str) -> Wynik:
    return Wynik(ok=False).linia(pl, en)


def _kod(s: str) -> str:
    return "`" + str(s).replace("`", "'") + "`"


def _liczba(n: float) -> str:
    return f"{int(n):,}".replace(",", " ")


# ----------------------------------------------------------------------------------------------- argumenty /model

@dataclass
class ArgModelu:
    cel: str = ""
    dostawca: str = ""
    globalnie: bool = False
    odswiez: bool = False
    bledy: list[str] = field(default_factory=list)


def argumenty_modelu(args: str) -> ArgModelu:
    """`[model] [--provider nazwa] [--global|--session] [--refresh]` jak `/model` w Hermesie; `--once`
    i `--reasoning` panel nie obsługuje (błąd zamiast cichego pominięcia)."""
    a, slowa = ArgModelu(), (args or "").split()
    i = 0
    while i < len(slowa):
        s = slowa[i]
        if s in ("--provider", "-p") and i + 1 < len(slowa):
            a.dostawca, i = slowa[i + 1], i + 2
            continue
        if s.startswith("--provider="):
            a.dostawca = s.split("=", 1)[1]
        elif s == "--global":
            a.globalnie = True
        elif s == "--session":
            a.globalnie = False
        elif s == "--refresh":
            a.odswiez = True
        elif s.startswith("-"):
            a.bledy.append(s)
        elif a.cel:
            a.bledy.append(s)
        else:
            a.cel = s
        i += 1
    return a


def _modele_wiersza(w: Mapping) -> list[str]:
    out = []
    for m in w.get("models") or []:
        mid = m.get("id") if isinstance(m, dict) else m
        if isinstance(mid, str) and mid:
            out.append(mid)
    return out


def dostawcy_bramy(opcje: Mapping) -> list[dict]:
    """Wiersze `/api/model/options` z modelami i działającym logowaniem: {slug, nazwa, modele, razem, biezacy}."""
    out = []
    for w in opcje.get("providers") or []:
        if not isinstance(w, dict) or not w.get("slug") or w.get("authenticated") is False:
            continue
        modele = _modele_wiersza(w)
        if not modele and w.get("source") == "canonical":
            continue
        out.append({"slug": str(w["slug"]), "nazwa": str(w.get("name") or w["slug"]), "modele": modele,
                    "razem": int(w.get("total_models") or len(modele)), "biezacy": bool(w.get("is_current"))})
    return out


def znajdz_model(dostawcy: list[dict], cel: str, dostawca: str = "") -> tuple[dict | None, list[dict]]:
    """(wybór {model, provider, nazwa}, kandydaci). Dokładna nazwa (bez wielkości liter) przed fragmentem; przy kilku
    dostawcach z tą samą nazwą wygrywa bieżący; `dostawca/model` też działa. Dostawca bez pełnej listy (np. własny
    endpoint) przyjmuje nazwę spoza listy, gdy podano `--provider`."""
    c = cel.strip().lower()
    wiersze = [d for d in dostawcy if not dostawca or d["slug"].lower() == dostawca.lower()]
    if not dostawca and "/" in c:
        przed, _, po = c.partition("/")
        z_dost = [d for d in dostawcy if d["slug"].lower() == przed]
        if z_dost and any(m.lower() == po for m in z_dost[0]["modele"]):
            wiersze, c = z_dost, po
    wybor = lambda d, m: {"model": m, "provider": d["slug"], "nazwa": d["nazwa"]}  # noqa: E731
    dokladne = [(d, m) for d in wiersze for m in d["modele"] if m.lower() == c]
    if dokladne:
        dokladne.sort(key=lambda x: not x[0]["biezacy"])
        return wybor(*dokladne[0]), []
    if dostawca and wiersze and (not wiersze[0]["modele"] or wiersze[0]["razem"] > len(wiersze[0]["modele"])):
        return wybor(wiersze[0], cel.strip()), []
    fragment = [(d, m) for d in wiersze for m in d["modele"] if c in m.lower()]
    if len(fragment) == 1:
        return wybor(*fragment[0]), []
    return None, [wybor(d, m) for d, m in fragment[:KANDYDACI_MAKS]]


def modele_omp(program: str | None) -> list[dict]:
    """`omp models --json`: [{model: selektor dostawca/id, provider, nazwa, okno (contextWindow), myslenie (poziomy
    thinking)}] (czat; bez sieci poza katalogiem omp)."""
    r = subprocess.run([program or "omp", "models", "--json"], capture_output=True, text=True, timeout=60,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "omp models").strip()[:200])
    d = json.loads(r.stdout or "{}")
    out = []
    for m in d.get("models") or []:
        if isinstance(m, dict) and m.get("id") and m.get("provider") and (m.get("kind") or "chat") == "chat":
            out.append({"model": str(m.get("selector") or f"{m['provider']}/{m['id']}"), "provider": str(m["provider"]),
                        "nazwa": str(m.get("name") or m["id"]), "okno": int(m.get("contextWindow") or 0),
                        "myslenie": [str(x) for x in m.get("thinking") or [] if isinstance(x, str)]})
    return out


def _model_z_argumentow(arg: Iterable[str]) -> str:
    arg = list(arg)
    for i, a in enumerate(arg):
        if a == "--model" and i + 1 < len(arg):
            return arg[i + 1]
        if a.startswith("--model="):
            return a.split("=", 1)[1]
    return ""


# ----------------------------------------------------------------------------------------------- wykonanie

@dataclass
class Kontekst:
    sil: Any
    watek: dict | None
    agent: str
    nazwa: str
    zaplecze: str = "hermes"
    wpis_omp: Any = None
    klucz: str = ""                                  # klucz wpisu komendy (komenda skrzynki omp dostaje ten sam)
    po_czasie: Callable[["Wynik"], None] | None = None    # drugi wpis z wynikiem, gdy komenda skończy się później


def okno_modelu(profil: str, wybrany: Mapping | None = None) -> dict:
    """{model, provider, okno}: model członka (wybór panelu albo z config.yaml profilu) i jego okno kontekstu
    w tokenach z metadanych Hermesa (ta sama funkcja co `GET /api/model/info` dashboardu; nadpisanie
    `model.context_length` z config.yaml dla modelu profilu). Bez Hermesa w procesie: puste i 0."""
    try:
        from hermes_cli.web_routers.models import get_model_info  # noqa: PLC0415
        info = get_model_info(profile=profil) or {}
    except Exception:
        info = {}
    model, provider = str(info.get("model") or ""), str(info.get("provider") or "")
    okno = int(info.get("effective_context_length") or 0)
    if wybrany and (str(wybrany.get("model") or ""), str(wybrany.get("provider") or "")) != (model, provider):
        model, provider = str(wybrany.get("model") or ""), str(wybrany.get("provider") or "")
        try:
            from agent.model_metadata import get_model_context_length  # noqa: PLC0415
            okno = int(get_model_context_length(model=model, base_url="", provider=provider,
                                                config_context_length=None) or 0)
        except Exception:
            okno = 0
    try:
        from hermes_cli.models import model_supports_fast_mode  # noqa: PLC0415
        fast = bool(model and model_supports_fast_mode(model))
    except Exception:
        fast = False
    return {"model": model, "provider": provider, "okno": okno, "fast_dostepny": fast}


class Wykonawca:
    """Wykonanie komend na pętli silnika (`sil.wykonaj`); blokujące rzeczy (omp, pliki, config.yaml) w wątkach."""

    def __init__(self, *, m, zapis_globalny: Callable[[Path, str, str], None] | None = None,
                 lista_omp: Callable[[], list[dict]] | None = None, rejestr: Callable[[], list[dict]] | None = None,
                 okno: Callable[[str, Mapping | None], dict] | None = None, czekaj_s: float = KOMENDA_CZEKAJ_S,
                 maks_s: float = KOMENDA_MAKS_S, odstep_s: float = 0.5):
        self.m = m
        self.zapis_globalny = zapis_globalny or zapisz_model_profilu
        self.lista_omp = lista_omp or (lambda: modele_omp(m.omp_sesje.program_omp()))
        self.rejestr = rejestr or rejestr_hermesa
        self.okno = okno or okno_modelu
        self.czekaj_s, self.maks_s, self.odstep_s = czekaj_s, maks_s, odstep_s
        self._okna: dict[tuple, tuple[float, dict]] = {}
        self._omp_katalog: dict[str, dict] = {}      # selektor modelu omp → {okno, myslenie, nazwa, provider}
        self._omp_katalog_at, self._omp_katalog_trwa = 0.0, False
        self._omp_trwa: set[tuple] = set()          # (sesja omp, komenda) w toku: druga taka sama nie idzie do skrzynki

    def katalog_omp(self) -> dict[str, dict]:
        """Katalog modeli omp z pamięci (okno kontekstu, poziomy myślenia, lista do wyboru); `omp models --json`
        odpowiada ok. 2 s, więc czyta go wątek w tle (pierwsze pytanie po starcie dostaje pusty katalog), co 6 h."""
        teraz = time.monotonic()
        if not self._omp_katalog_trwa and (not self._omp_katalog_at or teraz - self._omp_katalog_at > KATALOG_OMP_S):
            self._omp_katalog_trwa = True
            threading.Thread(target=self._czytaj_katalog_omp, name="omp-katalog", daemon=True).start()
        return self._omp_katalog

    def _czytaj_katalog_omp(self) -> None:
        try:
            self._omp_katalog = {x["model"]: x for x in self.lista_omp() if x.get("model")} or self._omp_katalog
        except Exception:
            pass
        finally:
            self._omp_katalog_at, self._omp_katalog_trwa = time.monotonic(), False

    def model_omp(self, model: str) -> dict:
        """Wpis katalogu dla `dostawca/id` (albo samego id); {} = nie wiadomo."""
        kat = self.katalog_omp()
        if model in kat:
            return kat[model]
        id_ = model.split("/", 1)[-1]
        return next((v for k_, v in kat.items() if k_.split("/", 1)[-1] == id_), {})

    async def wykonaj(self, k: Kontekst, nazwa: str, args: str) -> Wynik:
        d = _PANEL.get(nazwa)
        if d is None:
            if k.zaplecze == "omp" and nazwa in {c["nazwa"] for c in await self._komendy_omp(k)}:
                return await self._omp_komenda(k, nazwa, args)
            znane = {c["nazwa"]: c for c in await asyncio.to_thread(self.rejestr)} if k.zaplecze == "hermes" else {}
            znane.update({a: c for c in list(znane.values()) for a in c.get("aliasy") or []})
            if nazwa in znane:
                return blad(f"{_kod('/' + nazwa)}: {INNE_HERMES[0]}", f"{_kod('/' + nazwa)}: {INNE_HERMES[1]}")
            return blad(f"Nie znam komendy {_kod('/' + nazwa)}. Lista: {_kod('/help')}. Tekst zaczynający się od „//” "
                        "idzie do agenta jak zwykła wiadomość.",
                        f"Unknown command {_kod('/' + nazwa)}. List: {_kod('/help')}. Text starting with “//” goes to "
                        "the agent as a normal message.")
        if k.zaplecze not in d.zaplecza:
            pl, en = d.powody.get(k.zaplecze) or INNE_HERMES
            return blad(f"{_kod('/' + d.nazwa)}: {pl}", f"{_kod('/' + d.nazwa)}: {en}")
        return await getattr(self, f"_{d.nazwa}")(k, args)

    async def _komendy_omp(self, k: Kontekst) -> list[dict]:
        """Komendy, które skrzynka sesji omp umie wykonać (`omp_sesje.komendy_omp`); niedostępna skrzynka: []."""
        if k.zaplecze != "omp" or k.wpis_omp is None or getattr(k.wpis_omp, "blad", ""):
            return []
        try:
            return [c for c in await asyncio.to_thread(self.m.omp_sesje.komendy_omp, k.wpis_omp) if c.get("nazwa")]
        except Exception:
            return []

    # ------------------------------------------------------------------- komendy skrzynki omp (/compact)
    async def _compact(self, k: Kontekst, args: str) -> Wynik:
        return await self._omp_komenda(k, "compact", args)

    async def _omp_komenda(self, k: Kontekst, nazwa: str, args: str) -> Wynik:
        """Komenda RPC skrzynki sesji omp (także w trakcie tury): zapis do skrzynki, potem wynik. Czeka najwyżej
        `czekaj_s`; dłuższa (kompresja potrafi trwać minuty) kończy się drugim wpisem w rozmowie (`po_czasie`)."""
        omp, w = self.m.omp_sesje, k.wpis_omp
        if w is None or getattr(w, "blad", ""):
            return blad("Sesja omp tej rozmowy jest niedostępna.", "This conversation's omp session is unavailable.")
        trwa = (getattr(w, "klucz", "") or id(w), nazwa)
        if trwa in self._omp_trwa:            # druga ta sama komenda w trakcie pierwszej (25.11: dwa /compact naraz)
            return Wynik().linia(f"{_kod('/' + nazwa)} już trwa w sesji omp {k.nazwa}; wynik pojawi się tutaj.",
                                 f"{_kod('/' + nazwa)} is already running in {k.nazwa}'s omp session; the result will "
                                 "appear here.")
        klucz = k.klucz or os.urandom(8).hex()
        try:
            await asyncio.to_thread(omp.komenda, w, nazwa, args, klucz)
        except Exception as exc:
            return blad(f"Skrzynka sesji nie przyjęła {_kod('/' + nazwa)} ({str(exc)[:120] or type(exc).__name__}).",
                        f"The session inbox did not accept {_kod('/' + nazwa)} ({str(exc)[:120] or type(exc).__name__}).")
        self._omp_trwa.add(trwa)
        st = await self._czekaj_na_komende(w, klucz, self.czekaj_s)
        if st is not None:
            self._omp_trwa.discard(trwa)
            return self._wynik_omp(nazwa, st)
        if k.po_czasie is None:
            self._omp_trwa.discard(trwa)
        else:
            k.sil.rejestr.zadanie(self._dokoncz_omp(k, nazwa, klucz, trwa))
        return Wynik().linia(f"{_kod('/' + nazwa)} trwa w sesji omp {k.nazwa}; wynik pojawi się tutaj, gdy się skończy.",
                             f"{_kod('/' + nazwa)} is running in {k.nazwa}'s omp session; the result will appear here "
                             "when it finishes.")

    async def _czekaj_na_komende(self, w, klucz: str, ile_s: float) -> dict | None:
        koniec = time.monotonic() + ile_s
        while True:
            try:
                st = await asyncio.to_thread(self.m.omp_sesje.wynik_komendy, w, klucz)
            except Exception as exc:
                st = {"stan": "blad", "blad": str(exc)[:200] or type(exc).__name__}
            if st.get("stan") in ("gotowe", "blad"):
                return st
            if time.monotonic() >= koniec:
                return None
            await asyncio.sleep(self.odstep_s)

    async def _dokoncz_omp(self, k: Kontekst, nazwa: str, klucz: str, trwa: tuple) -> None:
        try:
            st = await self._czekaj_na_komende(k.wpis_omp, klucz, self.maks_s)
        finally:
            self._omp_trwa.discard(trwa)
        wynik = self._wynik_omp(nazwa, st) if st is not None else blad(
            f"{_kod('/' + nazwa)} nie skończyła się w {int(self.maks_s // 60)} min. Stan sesji: {_kod('/context')}.",
            f"{_kod('/' + nazwa)} did not finish within {int(self.maks_s // 60)} min. Session state: {_kod('/context')}.")
        k.po_czasie(wynik)

    def _wynik_omp(self, nazwa: str, st: Mapping) -> Wynik:
        utajnij = self.m.ochrona.utajnij
        if st.get("stan") == "blad":
            b = utajnij(str(st.get("blad") or "nieznany błąd"))[:300]
            return blad(f"{_kod('/' + nazwa)} się nie udała: {b}", f"{_kod('/' + nazwa)} failed: {b}")
        tekst = utajnij(str(st.get("wynik") or "")).strip()[:2000]
        if nazwa == "compact":
            return Wynik().linia(f"Kontekst sesji skompresowany.{' ' + tekst if tekst else ''}",
                                 f"Session context compacted.{' ' + tekst if tekst else ''}")
        return Wynik().linia(f"{_kod('/' + nazwa)}: {tekst or 'gotowe'}", f"{_kod('/' + nazwa)}: {tekst or 'done'}")

    # ------------------------------------------------------------------- licznik, /context
    async def licznik(self, k: Kontekst) -> dict:
        """Licznik rozmowy (pasek pod kompozytorem, `/context`): kształt `LICZNIK_ZERO` + `zaplecze`, `szacunek`.
        Nigdy wyjątek: czego nie wiadomo, to zero."""
        if k.zaplecze == "omp":
            d: Mapping = {}
            if k.wpis_omp is not None and not getattr(k.wpis_omp, "blad", ""):
                try:
                    d = await asyncio.to_thread(self.m.omp_sesje.licznik, k.wpis_omp) or {}
                except Exception:
                    d = {}
            out = {x: d.get(x) or v for x, v in LICZNIK_ZERO.items()}
            if not out["okno"] and out["model"]:     # bez skrzynki RPC okno zna tylko katalog modeli omp
                out["okno"] = int(self.model_omp(str(out["model"])).get("okno") or 0)
                out["procent"] = round(100.0 * int(out["kontekst"]) / out["okno"], 1) if out["okno"] else 0.0
            return {**out, "wysilek": str(d.get("myslenie") or ""),
                    "fast": d.get("fast") if isinstance(d.get("fast"), bool) else None,
                    "fast_dostepny": True, "zaplecze": "omp", "szacunek": False,
                    "dostawca": str(out["model"] or "").split("/", 1)[0] if "/" in str(out["model"] or "") else "",
                    "kompresja": d.get("kompresja") if isinstance(d.get("kompresja"), dict) else None}
        wid = k.watek["id"] if k.watek else None
        wybrany = k.sil.db.model_czlonka(wid, k.agent) if wid else None
        klucz_okna = (k.agent, (wybrany or {}).get("model"), (wybrany or {}).get("provider"))
        teraz = time.monotonic()
        jest = self._okna.get(klucz_okna)
        if jest is None or teraz - jest[0] > OKNO_PAMIEC_S:
            try:
                jest = (teraz, await asyncio.to_thread(self.okno, k.agent, wybrany))
            except Exception:
                jest = (teraz, {"model": (wybrany or {}).get("model") or "", "okno": 0})
            self._okna[klucz_okna] = jest
        m = jest[1]
        z, u = (await asyncio.to_thread(self._zuzycie_hermes, k)) if wid else (dict(LICZNIK_ZERO), {})
        kontekst = (int(z.get("znaki") or 0) + 3) // 4
        okno = int(m.get("okno") or 0)
        # state.db liczy wszystko, co Hermes rozliczył w sesji (także w trakcie tury), `usage` przebiegów tylko
        # skończone tury panelu: większa z dwóch liczb, żeby licznik nie cofał się, gdy któreś źródło milczy
        o = self.m.przebiegi.opcje_czlonka(k.sil.db, wid, k.agent) if wid else {"wysilek": "", "fast": None}
        return {**LICZNIK_ZERO, "zaplecze": "hermes", "szacunek": True, "model": str(m.get("model") or ""),
                "kontekst": kontekst, "okno": okno, "procent": round(100.0 * kontekst / okno, 1) if okno else 0.0,
                **{x: max(int(z.get(x) or 0), int(u.get(x) or 0)) for x in ("wejscie", "wyjscie", "cache_odczyt", "cache_zapis")},
                "koszt": float(z.get("koszt") or 0), "czas": time.time(), "wysilek": o["wysilek"], "fast": o["fast"],
                "fast_dostepny": bool(m.get("fast_dostepny")), "dostawca": str(m.get("provider") or "")}

    def _zuzycie_hermes(self, k: Kontekst) -> tuple[dict, dict]:
        rodowod = [s["sesja_id"] for s in k.sil.db.sesje_watku(k.watek["id"], agent=k.agent, rola="rozmowa")]
        return k.sil.czytnik.zuzycie(k.agent, rodowod), self._uzycie_hermes(k)["rozmowa"]

    async def _context(self, k: Kontekst, args: str) -> Wynik:
        if not k.watek:
            return blad("Kontekst liczę dla rozmowy: otwórz rozmowę.", "Context is counted per conversation: open one.")
        d = await self.licznik(k)
        ok_ = "≈ " if d["szacunek"] else ""
        okno = f" z {_liczba(d['okno'])} ({d['procent']:.0f}%)" if d["okno"] else ""
        okno_en = f" of {_liczba(d['okno'])} ({d['procent']:.0f}%)" if d["okno"] else ""
        koszt = f" · koszt ${d['koszt']:.2f}" if d["koszt"] else ""
        w = Wynik().linia(f"**{k.nazwa}** · {_kod(d['model'] or '?')}", f"**{k.nazwa}** · {_kod(d['model'] or '?')}")
        w.linia(f"- Kontekst: {ok_}{_liczba(d['kontekst'])} tokenów{okno}",
                f"- Context: {ok_}{_liczba(d['kontekst'])} tokens{okno_en}")
        w.linia(f"- Wejście {_liczba(d['wejscie'])} · wyjście {_liczba(d['wyjscie'])} · cache {_liczba(d['cache_odczyt'])} "
                f"odczyt, {_liczba(d['cache_zapis'])} zapis{koszt}",
                f"- Input {_liczba(d['wejscie'])} · output {_liczba(d['wyjscie'])} · cache {_liczba(d['cache_odczyt'])} "
                f"read, {_liczba(d['cache_zapis'])} write{koszt.replace('koszt', 'cost')}")
        if d["szacunek"]:
            w.linia("Kontekst Hermesa to szacunek z treści sesji (bez promptu systemowego i narzędzi).",
                    "The Hermes context is an estimate from the session content (without the system prompt and tools).")
        return w

    # ------------------------------------------------------------------- /effort, /fast, opcje stopki
    def _poziomy(self, k: Kontekst, model: str) -> list[str]:
        """Poziomy wysiłku: omp z katalogu modelu (`thinking`, plus `off`), Hermes `model_options.reasoning_effort`."""
        if k.zaplecze == "omp":
            m = [x for x in self.model_omp(model).get("myslenie") or [] if x in self.m.omp_sesje.MYSLENIE]
            return ["off"] + [x for x in m if x != "off"] if m else list(self.m.omp_sesje.MYSLENIE)
        return list(self.m.przebiegi.WYSILKI_HERMESA)

    def _ustaw_opcje(self, k: Kontekst, **zmiany) -> str:
        if k.zaplecze == "omp":
            self.m.omp_sesje.ustaw_opcje_skrzynki(k.wpis_omp, **{"myslenie" if x == "wysilek" else x: v
                                                                 for x, v in zmiany.items()})
            return "od następnej tury skrzynki (terminal zostaje przy swoim)"
        self.m.przebiegi.ustaw_opcje_czlonka(k.sil.db, k.watek["id"], k.agent, **zmiany)
        return "od następnej wiadomości"

    def _bez_opcji(self, k: Kontekst) -> Wynik | None:
        if not k.watek:
            return blad("To ustawia się w rozmowie: otwórz rozmowę.", "This is set inside a conversation: open one.")
        if k.zaplecze == "omp" and (k.wpis_omp is None or getattr(k.wpis_omp, "blad", "")):
            return blad("Sesja omp tej rozmowy jest niedostępna.", "This conversation's omp session is unavailable.")
        return None

    async def _effort(self, k: Kontekst, args: str) -> Wynik:
        if (b := self._bez_opcji(k)) is not None:
            return b
        d = await self.licznik(k)
        poziomy = self._poziomy(k, d["model"])
        a = args.strip().lower()
        lista = ", ".join(_kod(p) for p in poziomy)
        if not a:
            return Wynik().linia(
                f"Wysiłek myślenia ({k.nazwa}): **{d['wysilek'] or 'domyślny'}**. Poziomy: {lista}; "
                f"{_kod('/effort domyslny')} wraca do ustawienia agenta.",
                f"Thinking effort ({k.nazwa}): **{d['wysilek'] or 'default'}**. Levels: {lista}; "
                f"{_kod('/effort default')} returns to the agent's setting.")
        if a in ("domyslny", "domyślny", "default", "reset"):
            nowy = ""
        elif a in poziomy:
            nowy = a
        else:
            return blad(f"Nie ma poziomu {_kod(a)} dla {_kod(d['model'] or k.nazwa)}. Poziomy: {lista}.",
                        f"No level {_kod(a)} for {_kod(d['model'] or k.nazwa)}. Levels: {lista}.")
        gdy = await asyncio.to_thread(self._ustaw_opcje, k, wysilek=nowy)
        return Wynik().linia(f"Wysiłek myślenia: **{nowy or 'domyślny'}**, działa {gdy}.",
                             f"Thinking effort: **{nowy or 'default'}**, applies from the next turn.")

    async def _fast(self, k: Kontekst, args: str) -> Wynik:
        if (b := self._bez_opcji(k)) is not None:
            return b
        d = await self.licznik(k)
        a = args.strip().lower()
        if a in ("status", "?"):
            stan = "włączony" if d["fast"] else "wyłączony"
            return Wynik().linia(f"Tryb szybki: **{stan}**.", f"Fast mode: **{'on' if d['fast'] else 'off'}**.")
        if a in ("", "toggle", "przelacz", "przełącz"):
            nowy: bool | None = not bool(d["fast"])
        elif a in ("on", "wl", "wł", "tak", "fast", "1"):
            nowy = True
        elif a in ("off", "wyl", "wył", "nie", "normal", "0"):
            nowy = False
        elif a in ("domyslny", "domyślny", "default", "reset"):
            nowy = None
        else:
            return blad(f"Składnia: {_kod('/fast [on|off|domyslny]')}.", f"Syntax: {_kod('/fast [on|off|default]')}.")
        if nowy and not d["fast_dostepny"]:
            return blad(f"Model {_kod(d['model'] or '?')} nie ma trybu szybkiego w Hermesie (Anthropic Opus, modele "
                        "OpenAI i xAI u bezpośredniego dostawcy).",
                        f"Model {_kod(d['model'] or '?')} has no fast mode in Hermes (Anthropic Opus, OpenAI and xAI "
                        "models at the direct provider).")
        gdy = await asyncio.to_thread(self._ustaw_opcje, k, fast=nowy)
        stan = "domyślny" if nowy is None else "włączony" if nowy else "wyłączony"
        return Wynik().linia(f"Tryb szybki: **{stan}**, działa {gdy}.",
                             f"Fast mode: **{'default' if nowy is None else 'on' if nowy else 'off'}**, applies from the next turn.")

    async def opcje(self, k: Kontekst) -> dict:
        """Stopka rozmowy po kliknięciu (`GET /rozmowy/{id}/opcje`): modele do wyboru (Hermes: dostawcy bramy, omp:
        cały katalog omp), poziomy wysiłku, bieżący wysiłek i tryb szybki. Model niesie `grupa` (slug dostawcy), a
        `grupy` opisują dostawców jako subskrypcje albo klucze API (wybierak modeli dzieli listę na nie). Wybór
        wykonuje panel komendą (`/model`, `/effort`, `/fast`), więc zostaje ślad w rozmowie jak w terminalu."""
        d = await self.licznik(k)
        modele: list[dict] = []
        nazwy: dict[str, str] = {}
        if k.zaplecze == "omp":
            if not self.katalog_omp():
                await asyncio.to_thread(self._czytaj_katalog_omp)
            kat = self.katalog_omp()
            for x in kat.values():
                id_ = x["model"].split("/", 1)[-1]
                if _DATOWANY.search(id_) and f"{x['provider']}/{_DATOWANY.sub('', id_)}" in kat:
                    continue                          # „claude-haiku-4-5-20251001” obok „claude-haiku-4-5”: dubel
                modele.append({"model": x["model"], "provider": "", "grupa": x.get("provider") or "",
                               "nazwa": x.get("nazwa") or x["model"], "okno": int(x.get("okno") or 0),
                               "myslenie": bool(x.get("myslenie")), "biezacy": x["model"] == d["model"]})
            if d["model"] and not any(x["biezacy"] for x in modele):
                m = self.model_omp(d["model"])
                modele.insert(0, {"model": d["model"], "provider": "", "grupa": d["model"].split("/", 1)[0],
                                  "nazwa": m.get("nazwa") or d["model"], "okno": int(m.get("okno") or 0),
                                  "myslenie": bool(m.get("myslenie")), "biezacy": True})
        else:
            try:
                for dost in dostawcy_bramy(await k.sil.brama.opcje_modeli(k.agent))[:DOSTAWCY_MAKS]:
                    nazwy[dost["slug"]] = dost["nazwa"]
                    modele += [{"model": mm, "provider": dost["slug"], "grupa": dost["slug"], "nazwa": mm,
                                "okno": 0, "myslenie": False, "biezacy": mm == d["model"]}
                               for mm in dost["modele"][:MODELE_NA_DOSTAWCE]]
            except self.m.brama.BladBramy:
                pass
        grupy = []
        for slug in dict.fromkeys(x["grupa"] for x in modele):
            nazwa, rodzaj = DOSTAWCY_OPIS.get(slug.lower(), (nazwy.get(slug) or slug, ""))
            if not rodzaj:
                rodzaj = "klucz" if slug.lower().endswith("-api") else "subskrypcja"
            grupy.append({"slug": slug, "nazwa": nazwa, "rodzaj": rodzaj})
        return {"zaplecze": k.zaplecze, "model": d["model"], "modele": modele, "grupy": grupy, "wysilek": d["wysilek"],
                "poziomy": self._poziomy(k, d["model"]), "fast": d["fast"], "fast_dostepny": d["fast_dostepny"]}

    # ------------------------------------------------------------------- /help
    async def _help(self, k: Kontekst, args: str) -> Wynik:
        w = Wynik()
        zap = "omp" if k.zaplecze == "omp" else "Hermes"
        w.linia(f"**Komendy w tej rozmowie** ({k.nazwa} · {zap})", f"**Commands in this conversation** ({k.nazwa} · {zap})")
        for c in katalog(k.zaplecze, [], await self._komendy_omp(k)):
            nazwa = " ".join(x for x in (f"/{c['nazwa']}", c["argumenty"]) if x)
            if c["dziala"]:
                w.linia(f"- {_kod(nazwa)}: {c['opis']}", f"- {_kod(nazwa)}: {c['opis_en']}")
            else:
                w.linia(f"- ~~/{c['nazwa']}~~: {c['powod']}", f"- ~~/{c['nazwa']}~~: {c['powod_en']}")
        if k.zaplecze == "hermes":
            w.linia("", "")
            w.linia("Pozostałe komendy Hermesa działają w Telegramie i w terminalu; panel pokaże je w menu jako "
                    "niedostępne. Tekst od „//” idzie do agenta jak zwykła wiadomość.",
                    "Other Hermes commands work in Telegram and in the terminal; the panel menu shows them as "
                    "unavailable. Text starting with “//” goes to the agent as a normal message.")
        return w

    # ------------------------------------------------------------------- /model
    async def _model(self, k: Kontekst, args: str) -> Wynik:
        a = argumenty_modelu(args)
        if a.bledy:
            return blad(f"Tej opcji panel nie obsługuje: {_kod(' '.join(a.bledy))}. Składnia: "
                        f"{_kod('/model [model] [--provider nazwa] [--global]')}.",
                        f"The panel does not support this option: {_kod(' '.join(a.bledy))}. Syntax: "
                        f"{_kod('/model [model] [--provider name] [--global]')}.")
        if k.zaplecze == "omp":
            return await self._model_omp(k, a)
        brama, bm = k.sil.brama, self.m.brama
        try:
            opcje = await brama.opcje_modeli(k.agent, odswiez=a.odswiez)
        except bm.BladBramy as e:
            return blad(f"Brama Hermesa nie podała listy modeli ({e.kod}). Spróbuj za chwilę.",
                        f"The Hermes gateway did not return the model list ({e.kod}). Try again shortly.")
        dostawcy = dostawcy_bramy(opcje)
        domyslny = {"model": str(opcje.get("model") or ""), "provider": str(opcje.get("provider") or "")}
        wid = k.watek["id"] if k.watek else None
        wybrany = k.sil.db.model_czlonka(wid, k.agent) if wid else None
        nazwy = {d["slug"]: d["nazwa"] for d in dostawcy}
        opis = lambda x: f"**{x['model'] or '?'}** ({nazwy.get(x['provider'], x['provider'] or '?')})"  # noqa: E731
        if not a.cel:
            w = Wynik()
            if wybrany:
                w.linia(f"Model tej rozmowy: {opis(wybrany)}, wybrany w panelu. Domyślny agenta: {opis(domyslny)}.",
                        f"Model of this conversation: {opis(wybrany)}, picked in the panel. Agent default: "
                        f"{opis(domyslny)}.")
            else:
                w.linia(f"Model: {opis(domyslny)}, domyślny agenta {k.nazwa}.",
                        f"Model: {opis(domyslny)}, {k.nazwa}'s default.")
            w.linia("", "")
            biezacy = wybrany or domyslny
            for d in dostawcy[:DOSTAWCY_MAKS]:
                modele = d["modele"][:MODELE_NA_DOSTAWCE]
                reszta = max(0, d["razem"] - len(modele))
                w.linia(f"**{d['nazwa']}** {_kod('--provider ' + d['slug'])}"
                        + (f", jeszcze {reszta}" if reszta else ""),
                        f"**{d['nazwa']}** {_kod('--provider ' + d['slug'])}" + (f", {reszta} more" if reszta else ""))
                for mm in modele:
                    w.wybor.append({"model": mm, "provider": d["slug"], "nazwa": d["nazwa"],
                                    "biezacy": mm == biezacy["model"] and d["slug"] == biezacy["provider"]})
            if not dostawcy:
                w.linia("Brama nie zna żadnego zalogowanego dostawcy: Ustawienia › Model.",
                        "The gateway knows no signed-in provider: Settings › Model.")
            w.linia("", "")
            w.linia(f"{_kod('/model <nazwa>')} zmienia model tej rozmowy, {_kod('--provider <dostawca>')} wybiera "
                    f"dostawcę, {_kod('--global')} zapisuje na stałe dla agenta.",
                    f"{_kod('/model <name>')} switches this conversation's model, {_kod('--provider <provider>')} picks "
                    f"the provider, {_kod('--global')} saves it permanently for the agent.")
            return w
        cel, kandydaci = znajdz_model(dostawcy, a.cel, a.dostawca)
        if cel is None:
            if kandydaci:
                w = blad(f"„{a.cel}” pasuje do kilku modeli, wybierz jeden:", f"“{a.cel}” matches several models, pick one:")
                w.wybor = kandydaci
                return w
            return blad(f"Nie znalazłem modelu „{a.cel}”{' u ' + a.dostawca if a.dostawca else ''} u dostawców agenta "
                        f"{k.nazwa}. Lista: {_kod('/model')}.",
                        f"No model “{a.cel}”{' at ' + a.dostawca if a.dostawca else ''} among {k.nazwa}'s providers. "
                        f"List: {_kod('/model')}.")
        if a.globalnie:
            try:
                await asyncio.to_thread(self.zapis_globalny, Path(k.sil.home) / "profiles" / k.agent, cel["provider"],
                                        cel["model"])
            except Exception as exc:  # walidacja Hermesa (nieznany model, brak klucza) albo zapis config.yaml
                return blad(f"Nie zapisałem modelu na stałe: {str(exc)[:200] or type(exc).__name__}.",
                            f"Could not save the model permanently: {str(exc)[:200] or type(exc).__name__}.")
            if wid:
                k.sil.db.ustaw_model_czlonka(wid, k.agent, None)
            return Wynik().linia(f"Domyślny model agenta {k.nazwa}: {opis(cel)}. Działa od następnej wiadomości "
                                 "we wszystkich rozmowach z nim.",
                                 f"{k.nazwa}'s default model: {opis(cel)}. Applies from the next message in all "
                                 "conversations with the agent.")
        if not wid:
            return blad("Model rozmowy zmienia się w rozmowie: napisz pierwszą wiadomość albo dodaj "
                        f"{_kod('--global')}, żeby zmienić domyślny model agenta.",
                        "A conversation's model is switched inside the conversation: send the first message or add "
                        f"{_kod('--global')} to change the agent's default model.")
        domyslny_wybor = cel["model"] == domyslny["model"] and cel["provider"] == domyslny["provider"]
        k.sil.db.ustaw_model_czlonka(wid, k.agent, None if domyslny_wybor else cel)
        na_stale = _kod("/model {} --provider {} --global".format(cel["model"], cel["provider"]))
        return Wynik().linia(
            f"Model tej rozmowy: {opis(cel)}{' (domyślny agenta)' if domyslny_wybor else ''}. Działa od następnej "
            f"wiadomości. Na stałe: {na_stale}.",
            f"Model of this conversation: {opis(cel)}{' (agent default)' if domyslny_wybor else ''}. Applies from the "
            f"next message. Permanently: {na_stale}.")

    async def _model_omp(self, k: Kontekst, a: ArgModelu) -> Wynik:
        omp, w = self.m.omp_sesje, k.wpis_omp
        if w is None or w.blad:
            return blad("Sesja omp tej rozmowy jest niedostępna.", "This conversation's omp session is unavailable.")
        if a.globalnie:
            return blad("Model na stałe dla sesji omp ustawia się w `omp_arg` jej wpisu w sesje.json.",
                        "An omp session's permanent model is set in `omp_arg` of its sesje.json entry.")
        wybrany = await asyncio.to_thread(omp.model_skrzynki, w)
        sesja = await asyncio.to_thread(omp.podsumowanie_sesji, w)
        ostatni = f"{sesja['dostawca']}/{sesja['model']}" if sesja["model"] else ""
        biezacy = wybrany or _model_z_argumentow(w.omp_arg) or ostatni
        try:
            modele = await asyncio.to_thread(self.lista_omp)
        except Exception as exc:
            return blad(f"omp nie podał listy modeli ({str(exc)[:120] or type(exc).__name__}).",
                        f"omp did not return the model list ({str(exc)[:120] or type(exc).__name__}).")
        if a.dostawca:
            modele = [x for x in modele if x["provider"].lower() == a.dostawca.lower()]
        if not a.cel:
            r = Wynik()
            r.linia(f"Model sesji omp: **{biezacy or 'domyślny omp'}**"
                    + (", wybrany w panelu." if wybrany else ".")
                    + (f" Ostatnia odpowiedź: {_kod(ostatni)}." if ostatni and ostatni != biezacy else ""),
                    f"omp session model: **{biezacy or 'omp default'}**" + (", picked in the panel." if wybrany else ".")
                    + (f" Last reply: {_kod(ostatni)}." if ostatni and ostatni != biezacy else ""))
            grupy: dict[str, list[dict]] = {}
            for x in modele:
                grupy.setdefault(x["provider"], []).append(x)
            for dost, lista in list(grupy.items())[:DOSTAWCY_MAKS]:
                reszta = max(0, len(lista) - MODELE_NA_DOSTAWCE)
                r.linia(f"**{dost}**" + (f", jeszcze {reszta}" if reszta else ""), f"**{dost}**" + (f", {reszta} more" if reszta else ""))
                r.wybor += [{"model": x["model"], "provider": "", "nazwa": x["nazwa"], "biezacy": x["model"] == biezacy}
                            for x in lista[:MODELE_NA_DOSTAWCE]]
            r.linia("", "")
            r.linia(f"{_kod('/model <wzorzec>')} zmienia model kolejnych tur tej sesji ({_kod('dostawca/model')} albo "
                    "fragment nazwy).",
                    f"{_kod('/model <pattern>')} switches the model of the session's next turns ({_kod('provider/model')} "
                    "or part of the name).")
            return r
        c = a.cel.lower()
        dokladne = [x for x in modele if c in (x["model"].lower(), x["model"].split("/", 1)[-1].lower())]
        pasujace = dokladne or [x for x in modele if c in x["model"].lower() or c in x["nazwa"].lower()]
        if len(pasujace) != 1:
            if pasujace:
                r = blad(f"„{a.cel}” pasuje do kilku modeli, wybierz jeden:", f"“{a.cel}” matches several models, pick one:")
                r.wybor = [{"model": x["model"], "provider": "", "nazwa": x["nazwa"]} for x in pasujace[:KANDYDACI_MAKS]]
                return r
            return blad(f"omp nie zna modelu „{a.cel}”. Lista: {_kod('/model')}.",
                        f"omp does not know the model “{a.cel}”. List: {_kod('/model')}.")
        cel = pasujace[0]["model"]
        await asyncio.to_thread(omp.ustaw_model_skrzynki, w, None if cel == _model_z_argumentow(w.omp_arg) else cel)
        return Wynik().linia(f"Model sesji omp: **{cel}**. Działa od następnej tury skrzynki (terminal zostaje przy "
                             "swoim).",
                             f"omp session model: **{cel}**. Applies from the mailbox's next turn (the terminal keeps "
                             "its own).")

    # ------------------------------------------------------------------- /stop
    def _aktywne(self, k: Kontekst, *, agent: str | None = None) -> list[dict]:
        if not k.watek:
            return []
        return [p for p in k.sil.db.przebiegi_watku(k.watek["id"], aktywne=True)
                if p["stan"] in DO_ZATRZYMANIA and (agent is None or p["agent"] == agent)]

    async def _zatrzymaj(self, k: Kontekst, lista: list[dict]) -> int:
        n = 0
        for p in lista:
            try:
                await k.sil.rejestr.stop(p["id"])
                n += 1
            except self.m.przebiegi.Blad:
                pass                                   # skończyła się w międzyczasie
        return n

    async def _stop(self, k: Kontekst, args: str) -> Wynik:
        if not k.watek:
            return blad("Tu nic nie pracuje: zatrzymać można pracę w otwartej rozmowie.",
                        "Nothing runs here: work can be stopped in an open conversation.")
        n = await self._zatrzymaj(k, self._aktywne(k))
        if not n:
            return Wynik().linia("Nic teraz nie pracuje w tej rozmowie.", "Nothing is running in this conversation.")
        return Wynik().linia(f"Zatrzymuję pracę ({n}). Wiadomości w kolejce czekają na „Wyślij teraz”.",
                             f"Stopping work ({n}). Queued messages wait for “Send now”.")

    # ------------------------------------------------------------------- /new
    async def _new(self, k: Kontekst, args: str) -> Wynik:
        if not k.watek:
            return blad("Nowa rozmowa zaczyna się od pierwszej wiadomości: tu sesji jeszcze nie ma.",
                        "A new conversation starts with the first message: there is no session here yet.")
        n = await self._zatrzymaj(k, [p for p in self._aktywne(k, agent=k.agent) if (p.get("rola") or "rozmowa") == "rozmowa"])
        try:
            sid = await k.sil.rejestr.nowa_sesja(k.watek["id"], k.agent)
        except self.m.brama.BladBramy as e:
            return blad(f"Brama Hermesa nie założyła nowej sesji ({e.kod}). Spróbuj za chwilę.",
                        f"The Hermes gateway did not create a new session ({e.kod}). Try again shortly.")
        if sid is None:
            return Wynik().linia(f"{k.nazwa} nie ma jeszcze sesji w tej rozmowie, następna wiadomość i tak zacznie "
                                 "czystą.", f"{k.nazwa} has no session in this conversation yet, the next message starts "
                                 "a clean one anyway.")
        return Wynik().linia(
            ("Zatrzymałem trwającą pracę. " if n else "") + f"Nowa sesja: {k.nazwa} zaczyna od następnej wiadomości bez "
            "wcześniejszej historii (oś rozmowy zostaje).",
            ("Stopped the running work. " if n else "") + f"New session: {k.nazwa} starts from the next message without "
            "the earlier history (the timeline stays).")

    # ------------------------------------------------------------------- /usage, /status
    def _uzycie_hermes(self, k: Kontekst) -> dict:
        czl = k.sil.db.czlonek(k.watek["id"], k.agent) or {}
        tip = czl.get("sesja_tip") or czl.get("sesja_id")
        suma = {"tury": 0, "wejscie": 0, "wyjscie": 0, "razem": 0, "cache_odczyt": 0, "cache_zapis": 0}
        sesja = dict(suma)
        for p in k.sil.db.przebiegi_watku(k.watek["id"]):
            u = p.get("uzycie") if isinstance(p.get("uzycie"), dict) else None
            if p["agent"] != k.agent or (p.get("rola") or "rozmowa") != "rozmowa" or not u:
                continue
            for cel in ((suma, sesja) if tip and p.get("sesja_id") == tip else (suma,)):
                cel["tury"] += 1
                cel["wejscie"] += int(u.get("input_tokens") or 0)
                cel["wyjscie"] += int(u.get("output_tokens") or 0)
                cel["razem"] += int(u.get("total_tokens") or 0) or int(u.get("input_tokens") or 0) + int(u.get("output_tokens") or 0)
                cel["cache_odczyt"] += int(u.get("cache_read_tokens") or 0)
                cel["cache_zapis"] += int(u.get("cache_write_tokens") or 0)
        return {"rozmowa": suma, "sesja": sesja, "tip": tip}

    async def _usage(self, k: Kontekst, args: str) -> Wynik:
        if not k.watek:
            return blad("Zużycie liczę dla rozmowy: otwórz rozmowę.", "Usage is counted per conversation: open one.")
        if k.zaplecze == "omp":
            s = await asyncio.to_thread(self.m.omp_sesje.podsumowanie_sesji, k.wpis_omp)
            return Wynik().linia(
                f"**Sesja omp {k.nazwa}**: {s['odpowiedzi']} odpowiedzi · wejście {_liczba(s['wejscie'])} · wyjście "
                f"{_liczba(s['wyjscie'])} · cache {_liczba(s['cache_odczyt'])} odczyt / {_liczba(s['cache_zapis'])} zapis"
                f" · koszt ${s['koszt']:.2f}. Kontekst ostatniej odpowiedzi: {_liczba(s['kontekst'])} tokenów.",
                f"**omp session {k.nazwa}**: {s['odpowiedzi']} replies · input {_liczba(s['wejscie'])} · output "
                f"{_liczba(s['wyjscie'])} · cache {_liczba(s['cache_odczyt'])} read / {_liczba(s['cache_zapis'])} write"
                f" · cost ${s['koszt']:.2f}. Context of the last reply: {_liczba(s['kontekst'])} tokens.")
        u = await asyncio.to_thread(self._uzycie_hermes, k)
        r, s = u["rozmowa"], u["sesja"]
        w = Wynik().linia(
            f"**{k.nazwa} w tej rozmowie**: {r['tury']} tur · wejście {_liczba(r['wejscie'])} · wyjście "
            f"{_liczba(r['wyjscie'])} · razem {_liczba(r['razem'])} tokenów.",
            f"**{k.nazwa} in this conversation**: {r['tury']} turns · input {_liczba(r['wejscie'])} · output "
            f"{_liczba(r['wyjscie'])} · total {_liczba(r['razem'])} tokens.")
        if s["tury"] != r["tury"]:
            w.linia(f"Bieżąca sesja: {s['tury']} tur · razem {_liczba(s['razem'])} tokenów.",
                    f"Current session: {s['tury']} turns · total {_liczba(s['razem'])} tokens.")
        w.linia("Limity konta dostawcy pokazuje `/usage` w Telegramie albo w terminalu (`hermes`).",
                "Provider account limits: `/usage` in Telegram or in the terminal (`hermes`).")
        return w

    async def _status(self, k: Kontekst, args: str) -> Wynik:
        zap = "omp" if k.zaplecze == "omp" else "Hermes"
        w = Wynik().linia(f"**{k.nazwa}** · {zap}", f"**{k.nazwa}** · {zap}")
        if k.zaplecze == "omp":
            s = await asyncio.to_thread(self.m.omp_sesje.podsumowanie_sesji, k.wpis_omp)
            wybrany = await asyncio.to_thread(self.m.omp_sesje.model_skrzynki, k.wpis_omp)
            model = wybrany or _model_z_argumentow(k.wpis_omp.omp_arg) or (f"{s['dostawca']}/{s['model']}" if s["model"] else "?")
            w.linia(f"- Sesja: {_kod(k.wpis_omp.sesja)}", f"- Session: {_kod(k.wpis_omp.sesja)}")
            w.linia(f"- Model: {_kod(model)}", f"- Model: {_kod(model)}")
            w.linia(f"- Odpowiedzi: {s['odpowiedzi']} · kontekst {_liczba(s['kontekst'])} tokenów",
                    f"- Replies: {s['odpowiedzi']} · context {_liczba(s['kontekst'])} tokens")
        else:
            wybrany = k.sil.db.model_czlonka(k.watek["id"], k.agent) if k.watek else None
            if wybrany:
                model = f"{wybrany['model']} ({wybrany['provider']}) · panel"
            else:
                try:
                    o = await k.sil.brama.opcje_modeli(k.agent)
                    model = f"{o.get('model') or '?'} ({o.get('provider') or '?'})"
                except self.m.brama.BladBramy as e:
                    model = f"? (brama: {e.kod})"
            w.linia(f"- Model: {_kod(model)}", f"- Model: {_kod(model)}")
            if k.watek:
                u = await asyncio.to_thread(self._uzycie_hermes, k)
                w.linia(f"- Sesja: {_kod(u['tip'] or 'brak')}", f"- Session: {_kod(u['tip'] or 'none')}")
                w.linia(f"- Tury w rozmowie: {u['rozmowa']['tury']} · razem {_liczba(u['rozmowa']['razem'])} tokenów",
                        f"- Turns in the conversation: {u['rozmowa']['tury']} · total {_liczba(u['rozmowa']['razem'])} tokens")
        if k.watek:
            n = len(self._aktywne(k))
            w.linia(f"- Praca w toku: {n}" if n else "- Nic teraz nie pracuje", f"- Work running: {n}" if n else "- Nothing running")
        return w


def zapisz_model_profilu(profil: Path, provider: str, model: str) -> None:
    """`/model … --global`: config.yaml profilu agenta przez funkcję dashboardu Hermesa (walidacja wyboru jak
    `PUT /api/profiles/{name}/model` i strona Modele)."""
    from hermes_cli.web_routers.profiles import _write_profile_model  # noqa: PLC0415

    if not (profil / "config.yaml").is_file() and not profil.is_dir():
        raise ValueError("nie ma takiego profilu")
    _write_profile_model(profil, provider, model)


# ----------------------------------------------------------------------------------------------- trasy

def dolacz(router, *, m, trasy, silnik: Callable[[], Any], agenci, hub, log: Callable[[str], None] | None = None,
           wykonawca: Wykonawca | None = None) -> list[str]:
    """`GET /komendy`, `POST /komendy` na routerze wtyczki (ochrona zapisu z `ochrona.Trasa`). `trasy`: moduł
    trasy_rozmow (BladTrasy, blad, czytaj_cialo, _Model, ODCZYT_ZRODLA, SILNIK)."""
    log = log or (lambda _m: None)
    ochrona = m.ochrona
    wyk = wykonawca or Wykonawca(m=m)
    sciezki: list[str] = []
    Blad = trasy.BladTrasy

    def trasa(metoda: str, sciezka: str, **kw):
        sciezki.append(f"{metoda} {sciezka}")
        return router.api_route(sciezka, methods=[metoda], **kw)

    def obsluga(fn):
        @functools.wraps(fn)
        async def owiniete(*a, **kw):
            try:
                return await fn(*a, **kw)
            except trasy.BladTrasy as e:
                return trasy.blad(e.status, e.kod, e.komunikat, e.komunikat_en, **e.dane)
            except m.przebiegi.Blad as e:
                return trasy.blad(e.status, e.kod, e.komunikat, e.komunikat_en, **e.dane)
            except m.silnik.SilnikNiedostepny:
                return trasy.blad(503, "silnik", *trasy.SILNIK)
        return owiniete

    def s():
        sil = silnik()
        if sil is None or not sil.dziala():
            raise Blad(503, "silnik", *trasy.SILNIK)
        return sil

    def kontekst(sil, wid: str | None, agent: str | None, args: str = "") -> tuple[Kontekst, str]:
        """Rozmowa → agent i zaplecze (rozmówca omp: wpis skrzynki; rozmówca Hermesa: jego profil; zwykła rozmowa:
        wybrany adresat, `@uchwyt` na początku argumentów albo koordynator). Zwraca też argumenty bez `@uchwytu`."""
        nazwy = agenci.nazwy_wyswietlane()
        w = None
        if wid:
            if not ochrona.WATEK_RE.fullmatch(wid):
                raise Blad(404, "brak", "Nie ma takiej rozmowy.", "No such conversation.")
            w = sil.db.watek(wid)
            if w is None:
                raise Blad(404, "brak", "Nie ma takiej rozmowy.", "No such conversation.")
        r = sil.db.rozmowca(w["rozmowca"]) if w and w.get("rozmowca") else None
        if r and r["zaplecze"] == "omp":
            wpis = sil.rejestr.omp.wpisy(sil.home).get(r["cel"]) if sil.rejestr.omp is not None else None
            return Kontekst(sil, w, r["klucz"], r.get("nazwa") or r["klucz"], "omp", wpis), args
        if r:
            cel = r["cel"]
        else:
            cel = (agent if agent and agenci.agent(agent) else None) or (w or {}).get("koordynator") or "jarvo"
            slowa = args.split(None, 1)
            if slowa and slowa[0].startswith("@"):
                mapa = m.wzmianki.mapa_aliasow(agenci.lista())
                znany = mapa.get(m.wzmianki.zloz(slowa[0][1:]))
                if znany is None:
                    raise Blad(422, "nieznany_agent", "Nie ma takiego agenta.", "No such agent.")
                cel, args = znany, (slowa[1] if len(slowa) > 1 else "")
        if agenci.agent(cel) is None:
            raise Blad(409, "nieznany_agent", "Agent tej rozmowy nie jest już dostępny.",
                       "This conversation's agent is no longer available.")
        return Kontekst(sil, w, cel, nazwy.get(cel, cel), "hermes"), args

    class KomendaBody(trasy._Model):
        tekst: str = Field(..., min_length=2, max_length=TEKST_MAKS)
        klucz: str = Field(..., pattern=trasy.KLUCZ_WZOR)
        watek: str | None = None
        agent: str | None = Field(None, max_length=64)
        # wybór w stopce (model, wysiłek, tryb szybki): bez wpisu w rozmowie, stan pokazuje sama stopka (23.11 właściciel:
        # „to usuwamy z interfejsu, że się pokazuje zmiana effortu”); odmowa wraca w odpowiedzi trasy
        cicho: bool = False

    w_locie: dict[tuple, asyncio.Future] = {}          # (wątek, klucz) → wykonanie komendy w toku

    def tylko_panel(request: Request) -> None:
        skad = (request.headers.get("sec-fetch-site") or "").strip().lower()
        if skad and skad not in trasy.ODCZYT_ZRODLA:
            raise Blad(403, "csrf", "Odmowa odczytu: żądanie nie przyszło z panelu Jarvo.",
                       "Read refused: the request did not come from the Jarvo dashboard.")

    @trasa("GET", "/komendy")
    @obsluga
    async def lista_komend(request: Request, watek: str = "", agent: str = ""):
        tylko_panel(request)
        sil = s()
        k, _ = await asyncio.to_thread(kontekst, sil, watek or None, agent or None)
        lista = await asyncio.to_thread(katalog, k.zaplecze, None, await wyk._komendy_omp(k))
        return {"zaplecze": k.zaplecze, "agent": k.agent, "nazwa": k.nazwa, "komendy": lista}

    @trasa("GET", "/rozmowy/{wid}/licznik")
    @obsluga
    async def licznik(wid: str, request: Request):
        """Licznik pod kompozytorem: model, kontekst i % okna, tokeny, cache, koszt (panel pyta co 2 s w trakcie pracy
        otwartej rozmowy, rzadziej bez niej)."""
        tylko_panel(request)
        sil = s()
        k, _ = await asyncio.to_thread(kontekst, sil, wid, None)
        return {"licznik": await wyk.licznik(k)}

    @trasa("GET", "/rozmowy/{wid}/opcje")
    @obsluga
    async def opcje_rozmowy(wid: str, request: Request):
        """Stopka po kliknięciu: modele do wyboru, poziomy wysiłku, bieżący wysiłek i tryb szybki."""
        tylko_panel(request)
        sil = s()
        k, _ = await asyncio.to_thread(kontekst, sil, wid, None)
        return {"opcje": await wyk.opcje(k)}

    @trasa("POST", "/komendy")
    @obsluga
    async def komenda(request: Request):
        body = await trasy.czytaj_cialo(request, KomendaBody)
        p = parsuj(body.tekst)
        if p is None:
            raise Blad(422, "nie_komenda", "To nie jest komenda (komenda zaczyna się od „/”).",
                       "This is not a command (a command starts with “/”).")
        sil = s()
        if body.watek:
            jest = await asyncio.to_thread(sil.db.wpis_po_kluczu, body.watek, body.klucz) \
                if ochrona.WATEK_RE.fullmatch(body.watek) else None
            if jest is not None:                   # powtórzone żądanie: ten sam wpis, bez drugiego wykonania
                return {"wynik": {**{k: jest["dane"].get(k) for k in ("ok", "wynik", "wynik_en", "wybor")},
                                  "polecenie": jest["dane"].get("polecenie"), "agent": jest["dane"].get("agent")},
                        "wpis": jest}
        nazwa, args = p
        k, args = await asyncio.to_thread(kontekst, sil, body.watek, body.agent, args)
        if k.watek and k.watek.get("usuniety_at"):
            raise Blad(409, "w_koszu", "Ta rozmowa jest w koszu: przywróć ją, żeby pisać dalej.",
                       "This conversation is in the trash: restore it to keep writing.")
        polecenie = " ".join(body.tekst.split())[:200]
        k.klucz = body.klucz

        def po_czasie(wynik: Wynik) -> None:
            """Wynik komendy, która skończyła się po odpowiedzi trasy (kompresja omp): drugi wpis w rozmowie."""
            wid = k.watek["id"]
            dane = {"typ": "komenda", "polecenie": polecenie, "agent": k.agent, **wynik.dane()}
            w = sil.db.dodaj_wpis(wid, rodzaj="system", tekst=polecenie, dane=dane, klucz=f"{body.klucz[:60]}_w")
            if not w.get("powtorzony"):
                hub.nadaj("watek.wpis", {"watek_id": wid, "wpis": w}, watek_id=wid)
            log(f"jarvo-hq: komenda /{nazwa} {k.agent} ({k.zaplecze}) skończona → {'ok' if wynik.ok else 'odmowa'}")

        k.po_czasie = po_czasie if k.watek else None

        async def _r():
            try:
                wynik = await wyk.wykonaj(k, nazwa, args)
            except m.brama.BladBramy as e:
                wynik = blad(f"Brama Hermesa nie odpowiedziała ({e.kod}).", f"The Hermes gateway did not answer ({e.kod}).")
            dane = {"typ": "komenda", "polecenie": polecenie, "agent": k.agent, **wynik.dane()}
            log(f"jarvo-hq: komenda /{nazwa} {k.agent} ({k.zaplecze}) → {'ok' if wynik.ok else 'odmowa'}")
            cicha = body.cicho and getattr(_PANEL.get(nazwa), "nazwa", "") in ("model", "effort", "fast")
            if not k.watek or cicha:
                return {"wynik": {**wynik.dane(), "polecenie": polecenie, "agent": k.agent}, "wpis": None}
            wid = k.watek["id"]
            w = sil.db.dodaj_wpis(wid, rodzaj="system", tekst=polecenie, dane=dane, klucz=body.klucz)
            if not w.get("powtorzony"):
                hub.nadaj("watek.wpis", {"watek_id": wid, "wpis": w}, watek_id=wid)
            return {"wynik": {**wynik.dane(), "polecenie": polecenie, "agent": k.agent}, "wpis": w}

        async def _raz():
            # ten sam klucz w trakcie wykonania (ponowione żądanie, gdy komenda skrzynki czeka do 2 s): to samo
            # wykonanie, bez drugiej komendy
            if not k.watek:
                return await _r()
            klucz = (k.watek["id"], body.klucz)
            f = w_locie.get(klucz)
            if f is None:
                f = w_locie[klucz] = asyncio.ensure_future(_r())
                f.add_done_callback(lambda _f: w_locie.pop(klucz, None))
            return await asyncio.shield(f)

        return await sil.wykonaj(_raz())

    return sciezki
