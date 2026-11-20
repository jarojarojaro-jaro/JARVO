"""Komendy po `/` w panelu Jarvo (docs/HQ.md „Komendy”): `/model`, `/new`, `/stop`, `/usage`, `/status`, `/help`.

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
- **`/help`** (alias `/commands`): komendy tej rozmowy. Pozostałe komendy z rejestru Hermesa
  (`hermes_cli.commands.COMMAND_REGISTRY`, bez `cli_only`) lista pokazuje jako niedostępne w panelu z powodem;
  `/compress` też: kompresji na żądanie brama nie udostępnia (sesja API kompresuje się sama przy progu kontekstu).

Wynik w rozmowie to wpis systemowy `{typ: "komenda", polecenie, agent, ok, wynik, wynik_en, wybor}` (scalanie nie
daje go do bloku kontekstu agenta), poza rozmową (ekran startu) tylko odpowiedź trasy. Trasy: `GET /komendy`
(katalog dla rozmowy), `POST /komendy` `{tekst, klucz, watek?, agent?}`; ten sam `klucz` w rozmowie = ten sam wpis
bez drugiego wykonania. Testy: tests/test_komendy.py.
"""

from __future__ import annotations

import asyncio
import functools
import json
import re
import subprocess
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
    Def("compress", "Skompresuj kontekst rozmowy", "Compress the conversation context", aliasy=("compact",), zaplecza=(),
        powody={"hermes": ("Brama Hermesa nie ma kompresji na żądanie dla sesji z panelu (tylko automatyczną przy progu "
                           "kontekstu). Czysta sesja: /new.",
                           "The Hermes gateway has no on-demand compression for panel sessions (only the automatic one "
                           "at the context threshold). For a clean session: /new."),
                "omp": ("Sesja omp kompresuje się sama; ręczne /compact działa w terminalu omp.",
                        "The omp session compacts itself; a manual /compact works in the omp terminal.")}),
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


def katalog(zaplecze: str, rejestr: Iterable[Mapping] | None = None) -> list[dict]:
    """Komendy rozmowy: najpierw te, które panel wykonuje, potem niedostępne (z powodem), potem reszta rejestru
    Hermesa (tylko w rozmowie z agentem Hermesa)."""
    dzialaja, nie = [], []
    for d in PANEL:
        powod = d.powody.get(zaplecze) or ("", "")
        wpis = {"nazwa": d.nazwa, "aliasy": list(d.aliasy), "opis": d.opis, "opis_en": d.opis_en, "panel": True,
                "argumenty": d.argumenty, "dziala": zaplecze in d.zaplecza, "powod": powod[0], "powod_en": powod[1]}
        (dzialaja if wpis["dziala"] else nie).append(wpis)
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
    """`omp models --json`: [{model: selektor dostawca/id, provider, nazwa}] (czat; bez sieci poza katalogiem omp)."""
    r = subprocess.run([program or "omp", "models", "--json"], capture_output=True, text=True, timeout=60,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "omp models").strip()[:200])
    d = json.loads(r.stdout or "{}")
    out = []
    for m in d.get("models") or []:
        if isinstance(m, dict) and m.get("id") and m.get("provider") and (m.get("kind") or "chat") == "chat":
            out.append({"model": str(m.get("selector") or f"{m['provider']}/{m['id']}"), "provider": str(m["provider"]),
                        "nazwa": str(m.get("name") or m["id"])})
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


class Wykonawca:
    """Wykonanie komend na pętli silnika (`sil.wykonaj`); blokujące rzeczy (omp, pliki, config.yaml) w wątkach."""

    def __init__(self, *, m, zapis_globalny: Callable[[Path, str, str], None] | None = None,
                 lista_omp: Callable[[], list[dict]] | None = None, rejestr: Callable[[], list[dict]] | None = None):
        self.m = m
        self.zapis_globalny = zapis_globalny or zapisz_model_profilu
        self.lista_omp = lista_omp or (lambda: modele_omp(m.omp_sesje.program_omp()))
        self.rejestr = rejestr or rejestr_hermesa

    async def wykonaj(self, k: Kontekst, nazwa: str, args: str) -> Wynik:
        d = _PANEL.get(nazwa)
        if d is None:
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

    # ------------------------------------------------------------------- /help
    async def _help(self, k: Kontekst, args: str) -> Wynik:
        w = Wynik()
        zap = "omp" if k.zaplecze == "omp" else "Hermes"
        w.linia(f"**Komendy w tej rozmowie** ({k.nazwa} · {zap})", f"**Commands in this conversation** ({k.nazwa} · {zap})")
        for c in katalog(k.zaplecze, []):
            nazwa = " ".join(x for x in (f"/{c['nazwa']}", c["argumenty"]) if x)
            if c["dziala"]:
                w.linia(f"- {_kod(nazwa)} — {c['opis']}", f"- {_kod(nazwa)} — {c['opis_en']}")
            else:
                w.linia(f"- ~~/{c['nazwa']}~~ — {c['powod']}", f"- ~~/{c['nazwa']}~~ — {c['powod_en']}")
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
                w.linia(f"Model tej rozmowy: {opis(wybrany)} — wybrany w panelu. Domyślny agenta: {opis(domyslny)}.",
                        f"Model of this conversation: {opis(wybrany)} — picked in the panel. Agent default: "
                        f"{opis(domyslny)}.")
            else:
                w.linia(f"Model: {opis(domyslny)} — domyślny agenta {k.nazwa}.",
                        f"Model: {opis(domyslny)} — {k.nazwa}'s default.")
            w.linia("", "")
            biezacy = wybrany or domyslny
            for d in dostawcy[:DOSTAWCY_MAKS]:
                modele = d["modele"][:MODELE_NA_DOSTAWCE]
                reszta = max(0, d["razem"] - len(modele))
                w.linia(f"**{d['nazwa']}** {_kod('--provider ' + d['slug'])}"
                        + (f" — jeszcze {reszta}" if reszta else ""),
                        f"**{d['nazwa']}** {_kod('--provider ' + d['slug'])}" + (f" — {reszta} more" if reszta else ""))
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
                w = blad(f"„{a.cel}” pasuje do kilku modeli — wybierz jeden:", f"“{a.cel}” matches several models — pick one:")
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
            return blad("Model rozmowy zmienia się w rozmowie — napisz pierwszą wiadomość albo dodaj "
                        f"{_kod('--global')}, żeby zmienić domyślny model agenta.",
                        "A conversation's model is switched inside the conversation — send the first message or add "
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
                    + (" — wybrany w panelu." if wybrany else ".")
                    + (f" Ostatnia odpowiedź: {_kod(ostatni)}." if ostatni and ostatni != biezacy else ""),
                    f"omp session model: **{biezacy or 'omp default'}**" + (" — picked in the panel." if wybrany else ".")
                    + (f" Last reply: {_kod(ostatni)}." if ostatni and ostatni != biezacy else ""))
            grupy: dict[str, list[dict]] = {}
            for x in modele:
                grupy.setdefault(x["provider"], []).append(x)
            for dost, lista in list(grupy.items())[:DOSTAWCY_MAKS]:
                reszta = max(0, len(lista) - MODELE_NA_DOSTAWCE)
                r.linia(f"**{dost}**" + (f" — jeszcze {reszta}" if reszta else ""), f"**{dost}**" + (f" — {reszta} more" if reszta else ""))
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
                r = blad(f"„{a.cel}” pasuje do kilku modeli — wybierz jeden:", f"“{a.cel}” matches several models — pick one:")
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
            return blad("Nowa rozmowa zaczyna się od pierwszej wiadomości — tu sesji jeszcze nie ma.",
                        "A new conversation starts with the first message — there is no session here yet.")
        n = await self._zatrzymaj(k, [p for p in self._aktywne(k, agent=k.agent) if (p.get("rola") or "rozmowa") == "rozmowa"])
        try:
            sid = await k.sil.rejestr.nowa_sesja(k.watek["id"], k.agent)
        except self.m.brama.BladBramy as e:
            return blad(f"Brama Hermesa nie założyła nowej sesji ({e.kod}). Spróbuj za chwilę.",
                        f"The Hermes gateway did not create a new session ({e.kod}). Try again shortly.")
        if sid is None:
            return Wynik().linia(f"{k.nazwa} nie ma jeszcze sesji w tej rozmowie — następna wiadomość i tak zacznie "
                                 "czystą.", f"{k.nazwa} has no session in this conversation yet — the next message starts "
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
        suma = {"tury": 0, "wejscie": 0, "wyjscie": 0, "razem": 0}
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
        return {"rozmowa": suma, "sesja": sesja, "tip": tip}

    async def _usage(self, k: Kontekst, args: str) -> Wynik:
        if not k.watek:
            return blad("Zużycie liczę dla rozmowy — otwórz rozmowę.", "Usage is counted per conversation — open one.")
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
                w.linia(f"- Sesja: {_kod(u['tip'] or '—')}", f"- Session: {_kod(u['tip'] or '—')}")
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

    @trasa("GET", "/komendy")
    @obsluga
    async def lista_komend(request: Request, watek: str = "", agent: str = ""):
        skad = (request.headers.get("sec-fetch-site") or "").strip().lower()
        if skad and skad not in trasy.ODCZYT_ZRODLA:
            raise Blad(403, "csrf", "Odmowa odczytu: żądanie nie przyszło z panelu Jarvo.",
                       "Read refused: the request did not come from the Jarvo dashboard.")
        sil = s()
        k, _ = await asyncio.to_thread(kontekst, sil, watek or None, agent or None)
        lista = await asyncio.to_thread(katalog, k.zaplecze, None)
        return {"zaplecze": k.zaplecze, "agent": k.agent, "nazwa": k.nazwa, "komendy": lista}

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
            raise Blad(409, "w_koszu", "Ta rozmowa jest w koszu — przywróć ją, żeby pisać dalej.",
                       "This conversation is in the trash — restore it to keep writing.")
        polecenie = " ".join(body.tekst.split())[:200]

        async def _r():
            try:
                wynik = await wyk.wykonaj(k, nazwa, args)
            except m.brama.BladBramy as e:
                wynik = blad(f"Brama Hermesa nie odpowiedziała ({e.kod}).", f"The Hermes gateway did not answer ({e.kod}).")
            dane = {"typ": "komenda", "polecenie": polecenie, "agent": k.agent, **wynik.dane()}
            log(f"jarvo-hq: komenda /{nazwa} {k.agent} ({k.zaplecze}) → {'ok' if wynik.ok else 'odmowa'}")
            if not k.watek:
                return {"wynik": {**wynik.dane(), "polecenie": polecenie, "agent": k.agent}, "wpis": None}
            wid = k.watek["id"]
            w = sil.db.dodaj_wpis(wid, rodzaj="system", tekst=polecenie, dane=dane, klucz=body.klucz)
            if not w.get("powtorzony"):
                hub.nadaj("watek.wpis", {"watek_id": wid, "wpis": w}, watek_id=wid)
            return {"wynik": {**wynik.dane(), "polecenie": polecenie, "agent": k.agent}, "wpis": w}

        return await sil.wykonaj(_r())

    return sciezki
