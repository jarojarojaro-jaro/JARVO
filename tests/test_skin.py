"""Skórka terminala: czat w dashboardzie (ui-tui, banner.ts) robi z każdego znacznika koloru osobną linię,
więc w banerze każda linijka może mieć najwyżej jeden kolor."""
import re
from pathlib import Path

import yaml

SKIN = Path(__file__).resolve().parents[1] / "branding" / "skin-jarvo.yaml"


def test_banner_one_color_per_line():
    skin = yaml.safe_load(SKIN.read_text(encoding="utf-8"))
    for key in ("banner_logo", "banner_hero"):
        for line in skin[key].splitlines():
            assert len(re.findall(r"\[(?:bold\s+)?(?:dim\s+)?#[0-9a-fA-F]{3,8}\]", line)) <= 1, (key, line)
