"""Zakładka „Wiedza”: trasy backendu wtyczki dashboardu Hermesa (montowane pod /api/plugins/jarvo-wiedza/).

Działa w procesie dashboardu (za jego logowaniem). Logika w panel.py (bez FastAPI), skarbiec przez wiedza.py obok.
Odczyt: overview, tree, note, graph, search, inbox, log, lint, rulings. Zapis tylko: POST rulings (orzeczenie od człowieka),
POST remark (uwaga do notatki = szkic), POST compile (kompilacja jako osobny proces), POST reindex.
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

_HERE = Path(__file__).resolve().parent


def _load(name: str, plik: str):
    mod = sys.modules.get(name)
    if mod is not None:
        return mod
    spec = importlib.util.spec_from_file_location(name, _HERE / plik)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


panel_mod = _load("jarvo_wiedza_panel", "panel.py")
HOME = panel_mod.korzen_danych(os.environ.get("HERMES_HOME", "/opt/data"))
JARVO_DIR = Path(os.environ.get("JARVO_DATA_DIR", str(HOME / "jarvo")))
PANEL = panel_mod.Panel(os.environ.get("JARVO_KNOWLEDGE_DIR") or JARVO_DIR / "knowledge",
                        os.environ.get("JARVO_STATE_DIR") or JARVO_DIR / "state",
                        os.environ.get("JARVO_REPO_DIR", "/opt/jarvo/repo"))
router = APIRouter()


def _blad(e: Exception) -> HTTPException:
    if isinstance(e, (ValueError, FileNotFoundError)):
        return HTTPException(400 if isinstance(e, ValueError) else 404, str(e))
    return HTTPException(500, f"błąd skarbca: {e}")


async def _w(fn, *args):
    try:
        return await asyncio.to_thread(fn, *args)
    except HTTPException:
        raise
    except Exception as e:
        raise _blad(e)


@router.get("/overview")
async def overview():
    return await _w(PANEL.overview)


@router.get("/tree")
async def tree():
    return await _w(PANEL.tree)


@router.get("/note")
async def note(path: str):
    return await _w(PANEL.note, path)


@router.get("/graph")
async def graph():
    return await _w(PANEL.graph)


@router.get("/search")
async def search(q: str, folder: str = "", limit: int = 12):
    return {"wyniki": await _w(PANEL.search, q, folder or None, limit)}


@router.get("/inbox")
async def inbox():
    return await _w(PANEL.inbox)


@router.get("/log")
async def log(n: int = 40):
    return {"wpisy": await _w(PANEL.log, max(1, min(n, 200)))}


@router.get("/lint")
async def lint(refresh: int = 0):
    return await _w(PANEL.lint, bool(refresh))


@router.get("/rulings")
async def rulings():
    return {"pliki": await _w(PANEL.rulings)}


@router.post("/rulings")
async def add_ruling(request: Request):
    body = await request.json()
    return await _w(PANEL.add_ruling, str(body.get("kogo") or "wszyscy"), str(body.get("tresc") or ""), str(body.get("zrodlo") or ""))


@router.post("/remark")
async def add_remark(request: Request):
    body = await request.json()
    return await _w(PANEL.add_remark, str(body.get("path") or ""), str(body.get("uwaga") or ""))


@router.post("/compile")
async def compile_start():
    return await _w(PANEL.compile_start)


@router.get("/compile")
async def compile_status():
    return await _w(PANEL.compile_status)


@router.post("/reindex")
async def reindex():
    return await _w(PANEL.reindex)
