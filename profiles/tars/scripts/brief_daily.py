#!/usr/bin/env python3
"""Wrapper crona: dane do porannego briefu (fleet_report.py --mode daily)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fleet_report  # noqa: E402

sys.exit(fleet_report.main(["--mode", "daily", *sys.argv[1:]]))
