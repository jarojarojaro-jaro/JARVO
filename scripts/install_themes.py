#!/usr/bin/env python3
"""Instaluje motywy „Fosfor” dashboardu (branding/fosfor/) w <HERMES_HOME>/dashboard-themes/.

    python install_themes.py <repo> <hermes_home>

Każda pozycja z palettes.yaml staje się jednym motywem Hermesa (YAML: paleta, czcionki, customCSS).
Wszystkie odcienie liczą się z jednego koloru. Gdy dashboard ma jeszcze motyw domyślny Hermesa,
ustawia `dashboard.theme` na `default` z palettes.yaml; wybór zrobiony w dashboardzie zostaje.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

FONT_URL = "/dashboard-plugins/tars-hq/dist/fonts/fosfor.css"
HERMES_DEFAULT_THEMES = {"", "default", None}


def rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError(f"zły kolor: {hex_color!r} (oczekiwany #rrggbb)")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def shade(c: tuple[int, int, int], k: float) -> str:
    return "#" + "".join(f"{round(v * k):02x}" for v in c)


AMBER, BLUE = "#ffb000", "#89cff0"


def tokens(color: str, accent: str | None = None) -> dict[str, str]:
    """Odcienie fosforu z jednego koloru + drugi kolor (--fos-alt) do wyróżnień, np. celu karty.
    Bez `accent`: bursztyn, a dla ciepłego fosforu (czerwony > niebieski) błękit."""
    c = rgb(color)
    alt = accent or (BLUE if c[0] > c[2] + 40 else AMBER)
    return {
        "fos": shade(c, 1.0), "fos-mid": shade(c, 0.82), "fos-lo": shade(c, 0.45),
        "fos-bg": shade(c, 0.05), "fos-bg2": shade(c, 0.08),
        "fos-glow": f"rgba({c[0]}, {c[1]}, {c[2]}, 0.45)",
        "fos-alt": shade(rgb(alt), 1.0),
    }


def icon_svg(rows: list[str]) -> str:
    """Siatka pikseli ("#" = zapalony) → SVG (prostokąty scalone w wierszach)."""
    d = []
    for y, row in enumerate(rows):
        x = 0
        while x < len(row):
            if row[x] == "#":
                start = x
                while x < len(row) and row[x] == "#":
                    x += 1
                d.append(f"M{start} {y}h{x - start}v1h-{x - start}z")
            else:
                x += 1
    w, h = max(map(len, rows)), len(rows)
    return (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {w} {h}' shape-rendering='crispEdges'>"
            f"<path d='{''.join(d)}'/></svg>")


def icons_css(text: str) -> str:
    """icons.txt → reguły CSS: każda pozycja menu dostaje swoją ikonkę jako zmienną --fos-ic."""
    icons: dict[str, list[str]] = {}
    key = None
    for line in text.splitlines():
        if line.startswith("#") and not set(line.strip()) <= {"#", "."}:
            continue
        if line.startswith("= "):
            key = line[2:].strip()
            icons[key] = []
        elif key and line.strip():
            icons[key].append(line.strip())
    out = []
    for href, rows in icons.items():
        url = "url(\"data:image/svg+xml," + icon_svg(rows).replace("<", "%3C").replace(">", "%3E") + "\")"
        sel = "aside.fixed nav a" if href == "default" else f'aside.fixed nav a[href$="{href}"]'
        out.append(f"{sel} {{ --fos-ic: {url}; }}")
    return "\n".join(out) + "\n"


def theme(entry: dict, css: str) -> dict:
    t = tokens(entry["color"], entry.get("accent"))
    root = ":root { " + " ".join(f"--{k}: {v};" for k, v in t.items()) + " }\n"
    return {
        "name": entry["name"],
        "label": entry.get("label") or entry["name"],
        "description": "TARS: terminal CRT, jeden kolor fosforu",
        "palette": {
            "background": t["fos-bg"],
            "midground": t["fos"],
            "foreground": {"hex": t["fos"], "alpha": 0.0},
            "warmGlow": t["fos-glow"],
            "noiseOpacity": 0,
        },
        "typography": {
            "fontSans": '"IBM Plex Mono", ui-monospace, monospace',
            "fontMono": '"IBM Plex Mono", ui-monospace, monospace',
            "fontDisplay": 'VT323, "IBM Plex Mono", monospace',
            "fontUrl": FONT_URL,
            "baseSize": "14px",
            "letterSpacing": "0.01em",
        },
        "layout": {"radius": "0", "density": "comfortable"},
        "colorOverrides": {
            "card": t["fos-bg2"], "popover": t["fos-bg2"], "border": t["fos-lo"], "input": t["fos-lo"],
            "ring": t["fos"], "primary": t["fos"], "primaryForeground": t["fos-bg"],
            "mutedForeground": t["fos-mid"], "accent": t["fos-lo"], "accentForeground": t["fos"],
        },
        "terminalBackground": t["fos-bg"],
        "terminalForeground": t["fos"],
        "customCSS": root + css,
    }


def set_default_theme(config: Path, name: str) -> bool:
    if not config.exists():
        return False
    try:
        from ruamel.yaml import YAML
        y = YAML()
        y.preserve_quotes = True
        data = y.load(config.read_text(encoding="utf-8")) or {}
        dump = lambda d: y.dump(d, config.open("w", encoding="utf-8"))  # noqa: E731
    except ImportError:  # pragma: no cover
        data = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
        dump = lambda d: config.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")  # noqa: E731
    dash = data.get("dashboard")
    if not isinstance(dash, dict):
        dash = {}
        data["dashboard"] = dash
    if dash.get("theme") not in HERMES_DEFAULT_THEMES:
        return False
    dash["theme"] = name
    dump(data)
    return True


def main(argv: list[str]) -> int:
    repo, home = Path(argv[0]), Path(argv[1])
    src = repo / "branding" / "fosfor"
    spec = yaml.safe_load((src / "palettes.yaml").read_text(encoding="utf-8"))
    css = (src / "theme.css").read_text(encoding="utf-8")
    if (src / "icons.txt").is_file():
        css += "\n/* ikonki menu (z icons.txt) */\n" + icons_css((src / "icons.txt").read_text(encoding="utf-8"))
    out = home / "dashboard-themes"
    out.mkdir(parents=True, exist_ok=True)
    for entry in spec["themes"]:
        body = yaml.safe_dump(theme(entry, css), allow_unicode=True, sort_keys=False, width=1000)
        (out / f"{entry['name']}.yaml").write_text(body, encoding="utf-8")
    changed = set_default_theme(home / "config.yaml", spec["default"])
    print(f"motywy Fosfor: {len(spec['themes'])}" + (f", domyślny: {spec['default']}" if changed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
