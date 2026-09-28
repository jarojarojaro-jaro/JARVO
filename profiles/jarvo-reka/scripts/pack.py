#!/usr/bin/env python3
"""Składa wyniki kart misji w jeden pakiet.

    python3 pack.py <katalog-misji> --out <katalog-wyjściowy> [--skip zlozenie]

Zbiera <katalog-misji>/<rola>/out/ (każda karta misji ma własny katalog roboczy), kopiuje do
<out>/pakiet/<rola>/, zapisuje MANIFEST.json (pliki, rozmiary, sha256) i tworzy <out>/pakiet.zip.
Nie zmienia treści plików. INDEX.md pisze agent (skill zlozenie-pakietu).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mission_dir")
    ap.add_argument("--out", required=True)
    ap.add_argument("--skip", action="append", default=["zlozenie"], help="role do pominięcia (domyślnie zlozenie)")
    args = ap.parse_args(argv)

    mission = Path(args.mission_dir).resolve()
    out = Path(args.out).resolve()
    pack = out / "pakiet"
    pack.mkdir(parents=True, exist_ok=True)
    manifest = {"mission": mission.name, "roles": {}}
    for role_dir in sorted(p for p in mission.iterdir() if p.is_dir() and not p.name.startswith(".")):
        if role_dir.name in args.skip or role_dir.resolve() == out.parent:
            continue
        src = role_dir / "out"
        if not src.is_dir():
            manifest["roles"][role_dir.name] = {"missing_out": True, "files": []}
            continue
        dest = pack / role_dir.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        files = []
        for f in sorted(dest.rglob("*")):
            if f.is_file():
                files.append({"path": str(f.relative_to(pack)), "bytes": f.stat().st_size, "sha256": sha256(f)})
        manifest["roles"][role_dir.name] = {"missing_out": False, "files": files}

    (pack / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    zip_path = out / "pakiet.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(pack.rglob("*")):
            if f.is_file():
                zf.write(f, f.relative_to(pack.parent))
    total = sum(len(r["files"]) for r in manifest["roles"].values())
    missing = [k for k, v in manifest["roles"].items() if v["missing_out"]]
    print(json.dumps({"pakiet": str(pack), "zip": str(zip_path), "plikow": total, "role": list(manifest["roles"]),
                      "brak_out": missing}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
