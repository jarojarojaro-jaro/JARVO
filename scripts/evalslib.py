"""Pomiar evals floty Jarvo: zbiory (robocze i odłożone), kanarki, powtórzenia, historia, punkt odniesienia,
porównanie dwóch przebiegów i wybór sędziego z innej rodziny modeli niż oceniany agent.

Używają go scripts/run-evals.py (zapis wyników), scripts/evals-wyniki.py (historia, odniesienie, porównanie)
i kuźnia skilli (docs/RSI.md). Bez zależności poza biblioteką standardową i pyyaml (przez fleetlib).

Zasady (docs/RSI.md §R0):
- zbiór odłożony (~1/4 scenariuszy, stały skrót id albo pole `zbior`) służy tylko jako bramka: kuźnia nie pokazuje
  go modelowi, który proponuje zmiany,
- kanarek: losowy znacznik w pliku scenariuszy agenta; pojawienie się go w odpowiedzi albo w wywołaniach narzędzi
  znaczy, że agent przeczytał evals (alarm, przebieg niezaliczony),
- scenariusz z powtórzeniami jest zaliczony, gdy przeszła większość przebiegów; wynik to średnia ocen,
- twarde sprawdzenia (`check`, kanarek) mają pierwszeństwo przed sędzią LLM.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

ZBIORY = ("roboczy", "odlozony")
ODLOZONY_CO = 4                      # co czwarty scenariusz (wg skrótu id) trafia do zbioru odłożonego
KANAREK_RE = re.compile(r"^JARVO-KANAREK-[0-9a-f]{12}$")
REMIS = 0.05                         # różnica wyniku scenariusza poniżej tego progu = remis w teście znaków


# ---------- scenariusze ----------

def zbior(scn: dict) -> str:
    """`roboczy` albo `odlozony`: jawne pole `zbior` wygrywa, inaczej stały skrót id (ten sam na każdej maszynie)."""
    jawny = scn.get("zbior")
    if jawny in ZBIORY:
        return jawny
    h = int(hashlib.sha256(str(scn.get("id", "")).encode()).hexdigest(), 16)
    return "odlozony" if h % ODLOZONY_CO == 0 else "roboczy"


def wczytaj(repo: Path, agent: str) -> dict:
    import fleetlib as fl
    return fl.load_yaml(repo / "evals" / agent / "scenarios.yaml") or {}


def kanarki(repo: Path) -> dict[str, str]:
    """{agent: znacznik} ze wszystkich plików evals/*/scenarios.yaml."""
    import fleetlib as fl
    out = {}
    for path in sorted((repo / "evals").glob("*/scenarios.yaml")):
        tok = (fl.load_yaml(path) or {}).get("kanarek")
        if isinstance(tok, str):
            out[path.parent.name] = tok
    return out


def wykryj_kanarek(final: str, events: list, tokeny) -> list[str]:
    """Znaczniki kanarków obecne w odpowiedzi albo w zdarzeniach (wywołania narzędzi, wyniki)."""
    tekst = final + "\n" + json.dumps(events, ensure_ascii=False)
    return sorted({t for t in tokeny if t and t in tekst})


# ---------- ocena ----------

def ocena_przebiegu(det: list[str], verdict: dict) -> tuple[bool | None, float | None]:
    """(zaliczony, wynik 0..1). Twarde niezaliczenie = (False, 0) niezależnie od sędziego; błąd sędziego =
    (False, None); sędzia pominięty (brak klucza) = (None, None), czyli NIEOCENIONY: bez sędziego nie wiemy,
    czy agent zrobił, co trzeba (nigdy cichy sukces)."""
    if det:
        return False, 0.0
    if verdict.get("blad"):
        return False, None
    p = verdict.get("pass")
    if p is None:
        return None, None
    score = verdict.get("score")
    try:
        score = max(0.0, min(1.0, float(score)))
    except (TypeError, ValueError):
        score = 1.0 if p else 0.0
    return bool(p), score


def scal(runs: list[dict]) -> dict:
    """Scenariusz z N przebiegów: zaliczony = większość zaliczonych; żaden przebieg nieoceniony → pass None."""
    n = len(runs)
    ok = sum(1 for r in runs if r.get("pass") is True)
    ocenione = [r for r in runs if r.get("pass") is not None]
    scores = [r["score"] for r in runs if r.get("score") is not None]
    return {
        "przebiegi": n,
        "zaliczone": ok,
        "pass_rate": round(ok / n, 4) if n else 0.0,
        "score": round(sum(scores) / len(scores), 4) if scores else None,
        "pass": (n > 0 and ok * 2 > n) if ocenione else None,
        "kanarek": sorted({t for r in runs for t in r.get("kanarek") or []}),
        "bledy_sedziego": sum(1 for r in runs if (r.get("judge") or {}).get("blad")),
        "bez_sedziego": sum(1 for r in runs if (r.get("judge") or {}).get("pominiety")),
    }


def podsumuj(rekordy: list[dict]) -> dict:
    """Podsumowanie jednego agenta: razem, per zbiór i per typ (średni wynik ocenionych, zaliczone, nieocenione)."""
    def blok(rs):
        sc = [r["score"] for r in rs if r.get("score") is not None]
        return {"n": len(rs), "zaliczone": sum(1 for r in rs if r.get("pass") is True),
                "nieocenione": sum(1 for r in rs if r.get("pass") is None),
                "score": round(sum(sc) / len(sc), 4) if sc else None}
    out = {"razem": blok(rekordy), "zbiory": {}, "typy": {}}
    for z in ZBIORY:
        out["zbiory"][z] = blok([r for r in rekordy if r.get("zbior") == z])
    for t in sorted({r.get("type") for r in rekordy if r.get("type")}):
        out["typy"][t] = blok([r for r in rekordy if r.get("type") == t])
    out["kanarek"] = sorted({t for r in rekordy for t in r.get("kanarek") or []})
    out["bledy_sedziego"] = sum(r.get("bledy_sedziego", 0) for r in rekordy)
    out["bez_sedziego"] = sum(r.get("bez_sedziego", 0) for r in rekordy)
    return out


# ---------- historia i punkt odniesienia ----------

def wczytaj_przebieg(path: Path) -> list[dict]:
    """Rekordy scenariuszy z pliku <agent>.jsonl."""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def dopisz_historie(wyniki: Path, wpis: dict) -> None:
    wyniki.mkdir(parents=True, exist_ok=True)
    with (wyniki / "historia.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(wpis, ensure_ascii=False) + "\n")


def historia(wyniki: Path, agent: str | None = None) -> list[dict]:
    path = wyniki / "historia.jsonl"
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            w = json.loads(line)
        except json.JSONDecodeError:
            continue
        if agent is None or w.get("agent") == agent:
            out.append(w)
    return out


def odniesienie_path(wyniki: Path, agent: str) -> Path:
    return wyniki / "odniesienie" / f"{agent}.jsonl"


def ustaw_odniesienie(wyniki: Path, agent: str, przebieg: Path) -> Path:
    """Kopiuje <przebieg>/<agent>.jsonl jako punkt odniesienia agenta."""
    src = przebieg / f"{agent}.jsonl"
    if not src.is_file():
        raise FileNotFoundError(src)
    dst = odniesienie_path(wyniki, agent)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".tmp")
    tmp.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    tmp.replace(dst)
    meta = dst.with_suffix(".json")
    meta.write_text(json.dumps({"agent": agent, "przebieg": przebieg.name}, ensure_ascii=False), encoding="utf-8")
    return dst


def p_znakow(wygrane: int, przegrane: int) -> float:
    """Jednostronny test znaków: szansa co najmniej tylu wygranych, gdyby zmiana nic nie dawała."""
    n = wygrane + przegrane
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(wygrane, n + 1)) / 2 ** n


def porownaj(stare: list[dict], nowe: list[dict]) -> dict:
    """Porównanie po scenariuszach ocenionych w obu przebiegach (para: ten sam id; bez wyniku → `nieocenione`).

    regresje: scenariusz zaliczony wcześniej, a teraz nie; bezpieczenstwo: regresje scenariuszy typu safety;
    delta: średnia zmiana wyniku; p: test znaków dla poprawy (mniejsze = pewniejsza poprawa)."""
    a = {r["id"]: r for r in stare}
    b = {r["id"]: r for r in nowe}
    wspolne = [i for i in a if i in b and a[i].get("score") is not None and b[i].get("score") is not None]
    nieocenione = sorted(i for i in a if i in b and i not in wspolne)
    wygrane, przegrane, remisy, regresje, poprawy, bezp = [], [], [], [], [], []
    delty = []
    for i in wspolne:
        d = b[i]["score"] - a[i]["score"]
        delty.append(d)
        if d > REMIS:
            wygrane.append(i)
        elif d < -REMIS:
            przegrane.append(i)
        else:
            remisy.append(i)
        if a[i]["pass"] is True and b[i]["pass"] is False:
            regresje.append(i)
            if b[i].get("type") == "safety" or a[i].get("type") == "safety":
                bezp.append(i)
        if b[i]["pass"] is True and a[i]["pass"] is False:
            poprawy.append(i)
    return {
        "wspolne": len(wspolne),
        "delta": round(sum(delty) / len(delty), 4) if delty else 0.0,
        "wygrane": wygrane, "przegrane": przegrane, "remisy": len(remisy),
        "regresje": regresje, "poprawy": poprawy, "bezpieczenstwo": bezp,
        "p": round(p_znakow(len(wygrane), len(przegrane)), 4),
        "tylko_stare": sorted(set(a) - set(b)), "tylko_nowe": sorted(set(b) - set(a)), "nieocenione": nieocenione,
    }


def trend(wyniki: Path, agent: str, n: int = 8) -> list[dict]:
    """Ostatnie n pełnych przebiegów agenta (data, commit, wynik razem i w zbiorze odłożonym); częściowe pomija."""
    out = []
    for w in [w for w in historia(wyniki, agent) if not w.get("czesciowy")][-n:]:
        s = w.get("podsumowanie") or {}
        out.append({
            "data": w.get("data"), "commit": (w.get("commit") or "")[:7], "powtorzenia": w.get("powtorzenia"),
            "score": (s.get("razem") or {}).get("score"),
            "zaliczone": (s.get("razem") or {}).get("zaliczone"), "n": (s.get("razem") or {}).get("n"),
            "nieocenione": (s.get("razem") or {}).get("nieocenione", 0),
            "odlozony": ((s.get("zbiory") or {}).get("odlozony") or {}).get("score"),
            "kanarek": bool(s.get("kanarek")),
        })
    return out


# ---------- sędzia ----------

def rodzina(model: str) -> str:
    """Rodzina modelu (anthropic, openai, google, deepseek, moonshot, …) z identyfikatora dostawcy."""
    m = (model or "").lower()
    for klucz, nazwa in (("claude", "anthropic"), ("anthropic", "anthropic"), ("gpt", "openai"), ("openai", "openai"),
                         ("gemini", "google"), ("google", "google"), ("deepseek", "deepseek"),
                         ("kimi", "moonshot"), ("moonshot", "moonshot"), ("qwen", "qwen"), ("grok", "xai")):
        if klucz in m:
            return nazwa
    return m.split("/", 1)[0] if "/" in m else m


def wybierz_sedziego(sedziowie: list[str], model_agenta: str, wymuszony: str | None = None) -> str:
    """Pierwszy sędzia z listy z innej rodziny niż model agenta (sędzia nie ocenia „swoich”)."""
    if wymuszony:
        return wymuszony
    for s in sedziowie:
        if rodzina(s) != rodzina(model_agenta):
            return s
    if not sedziowie:
        raise ValueError("fleet.yaml: brak evals.judges")
    return sedziowie[0]
