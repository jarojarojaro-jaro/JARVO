"""Kalibracja pod rodzinę modelu: rozpoznanie rodziny i wybór sekcji roli (shared/calibration/)."""

from conftest import load_script

fl = load_script("scripts/fleetlib.py", "fleetlib_calib_test")


def test_model_family():
    cases = {
        "gpt-6-luna": "gpt", "openai/gpt-5.6-sol": "gpt", "anthropic/claude-opus-5.5": "claude",
        "claude-haiku-4-5-20251001": "claude", "deepseek/deepseek-v4-pro": "deepseek",
        "moonshotai/Kimi-K2.6": "kimi", "glm-5.3": "generic", "": "generic", None: "generic",
    }
    for model, family in cases.items():
        assert fl.model_family(model) == family, model


def test_role_sections():
    orch = fl.calibration_block("gpt-6-luna", True)
    work = fl.calibration_block("gpt-6-luna", False)
    assert orch.startswith("## Jak pracuję na tym modelu (gpt-6-luna)")
    assert "deleguję kartą" in orch and "deleguję kartą" not in work        # GPT: deleguje za rzadko
    assert "tyle, ile wymaga DoD" in work and "tyle, ile wymaga DoD" not in orch
    shared = "Kryterium sprawdzone i spełnione"
    assert shared in orch and shared in work
    assert "<!--" not in orch                                              # komentarze z pliku nie trafiają do SOUL


def test_every_family_has_both_roles():
    for fam in ("gpt-x", "claude-x", "deepseek-x", "kimi-x", "zzz"):
        for orch in (True, False):
            block = fl.calibration_block(fam, orch)
            assert block.count("\n- ") >= 2, (fam, orch)


def test_recalibrate_keeps_role_and_rest():
    soul = "A\n" + fl.calibration_section("gpt-6-luna", True) + "\nB"
    new = fl.recalibrate_soul(soul, "deepseek/deepseek-v4-pro")
    assert new.startswith("A\n<!-- Jarvo:CALIBRATION orkiestrator -->") and new.endswith("\nB")
    assert "dokładne dopasowanie tekstu" in new and "(gpt-6-luna)" not in new
    assert fl.recalibrate_soul("bez znaczników", "x") is None
