"""Obraz z narzędzi MCP do modelu głównego jako obraz (middleware `tool_execution` wtyczki jarvo-zgody).

Hermes zamienia blok obrazu z wyniku narzędzia MCP (np. `shot` telefonu z PhoneUse) na tekst `MEDIA:<ścieżka>`
(`tools/mcp_tool_content.py`), więc model widział tylko ścieżkę i oglądał piksele dopiero osobnym `vision_analyze`.
Ten moduł oddaje taki wynik jako koperta `_multimodal` (tekst wyniku bez zmian + JPEG o dłuższym boku najwyżej
DLUZSZY_BOK), czyli tym samym mechanizmem co `capture` z `computer_use` i `pulpit`. Decyzję, czy model główny
przyjmuje obraz, bierze ta sama bramka co `computer_use` (`_should_route_through_aux_vision`; wpisy modeli
w `jarvo/flota.py` MODELE_Z_OBRAZEM). Gdy w turze pracuje model bez obrazu (zapas), Hermes sam zamienia kopertę na
`text_summary` (`_tool_result_content_for_active_model`), a stare obrazy w kontekście przycina sam
(`evict_stale_outbound_tool_images`, `_retire_stale_tool_result_images`). Każdy błąd oddaje wynik bez zmian.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import re
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

PREFIKS_MCP = "mcp__"
DLUZSZY_BOK = 1280          # px: zrzut telefonu (720x1600) i ekranu czytelny dla modelu, ~1,5 tys. tokenów
JAKOSC_JPEG = 80
MAKS_OBRAZOW = 2            # obrazów z jednego wyniku narzędzia
MAKS_BAJTOW = 8 * 1024 * 1024
_MEDIA = re.compile(r"^MEDIA:(\S[^\n]*?\.(?:jpe?g|png|webp))[ \t]*$", re.IGNORECASE | re.MULTILINE)


def obraz_natywny() -> bool:
    """Ta sama bramka co zrzut `computer_use` (False = model główny dostaje opis z modelu pomocniczego)."""
    try:
        from tools.computer_use.tool import _should_route_through_aux_vision
        return not _should_route_through_aux_vision()
    except Exception as e:  # noqa: BLE001 - bez Hermesa (testy) albo po zmianie jego API: zostaje tekst
        logger.debug("jarvo-zgody: bramka obrazu niedostępna: %s", e)
        return False


def jpeg_data_url(sciezka: Path, dluzszy_bok: int = DLUZSZY_BOK) -> str | None:
    """Plik obrazu jako `data:image/jpeg;base64,…` (dłuższy bok najwyżej `dluzszy_bok`); None, gdy się nie da."""
    try:
        if not sciezka.is_file() or sciezka.stat().st_size > MAKS_BAJTOW:
            return None
        surowe = sciezka.read_bytes()
        from PIL import Image
        with Image.open(io.BytesIO(surowe)) as img:
            img.load()
            if img.format == "JPEG" and max(img.size) <= dluzszy_bok:
                dane = surowe                       # zrzut telefonu (JPEG 360x800) idzie bez przekodowania
            else:
                obraz = img.convert("RGB")
                if max(obraz.size) > dluzszy_bok:
                    obraz.thumbnail((dluzszy_bok, dluzszy_bok), Image.LANCZOS)
                bufor = io.BytesIO()
                obraz.save(bufor, format="JPEG", quality=JAKOSC_JPEG, optimize=True)
                dane = bufor.getvalue()
        return "data:image/jpeg;base64," + base64.b64encode(dane).decode("ascii")
    except Exception as e:  # noqa: BLE001 - uszkodzony albo nieznany plik: zostaje ścieżka w tekście
        logger.debug("jarvo-zgody: obraz %s nieczytelny: %s", sciezka, e)
        return None


def koperta(wynik: Any) -> dict | None:
    """Wynik narzędzia MCP (JSON `{"result": "...MEDIA:<plik>..."}`) jako koperta `_multimodal`; None bez obrazu."""
    if not isinstance(wynik, str) or "MEDIA:" not in wynik:
        return None
    try:
        dane = json.loads(wynik)
    except ValueError:
        return None
    tekst = dane.get("result") if isinstance(dane, dict) else None
    if not isinstance(tekst, str):
        return None
    obrazy = [u for u in (jpeg_data_url(Path(m.group(1).strip())) for m in _MEDIA.finditer(tekst)) if u]
    if not obrazy:
        return None
    obrazy = obrazy[:MAKS_OBRAZOW]
    tresc = [{"type": "text", "text": tekst}] + [{"type": "image_url", "image_url": {"url": u}} for u in obrazy]
    return {"_multimodal": True, "content": tresc, "text_summary": wynik,
            "meta": {"jarvo_obraz": len(obrazy), "native_vision": True}}


def obraz_mcp(*, tool_name: str = "", args: Any = None, next_call: Callable[..., Any], **_: Any) -> Any:
    """Middleware `tool_execution`: wynik narzędzia MCP z obrazem → koperta `_multimodal` dla modelu z obrazem."""
    wynik = next_call(args)
    if not str(tool_name).startswith(PREFIKS_MCP) or not isinstance(wynik, str) or "MEDIA:" not in wynik:
        return wynik
    if not obraz_natywny():
        return wynik
    return koperta(wynik) or wynik


def zarejestruj(ctx) -> None:
    """Rejestracja w register() wtyczki; błąd nie przerywa ładowania strażnika zgód."""
    try:
        ctx.register_middleware("tool_execution", obraz_mcp)
    except Exception as e:  # noqa: BLE001 - starszy Hermes bez middleware: zostaje tekst MEDIA:
        logger.warning("jarvo-zgody: obraz z narzędzi MCP bez middleware (%s)", e)
