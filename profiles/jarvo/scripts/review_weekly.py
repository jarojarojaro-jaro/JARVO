#!/usr/bin/env python3
"""Wrapper crona: dane do przeglądu tygodnia (fleet_report.py --mode weekly)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fleet_report  # noqa: E402

sys.exit(fleet_report.main(["--mode", "weekly", *sys.argv[1:]]))
