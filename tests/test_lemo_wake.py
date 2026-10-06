"""Studio: lemo-wake (lemo_wake.py) – przypięty commit, ścieżki, zgoda na modele, klon bez skilla upload."""

from __future__ import annotations

import json
import os
import subprocess

import yaml

from conftest import REPO, load_script

lw = load_script("profiles/jarvo-studio/scripts/lemo_wake.py")


def test_biblioteka_na_commicie_z_locka_i_skille_w_studiu():
    lock = yaml.safe_load((REPO / "vendor/skills.lock.yaml").read_text(encoding="utf-8"))
    zrodlo = lock["sources"]["lemo-wake"]
    assert zrodlo["rev"] == lw.REV                      # biblioteka = ten sam commit co kopia skilla w profilu
    assert zrodlo["license"] == "CC-BY-NC-4.0"
    wpisy = {e["dest"]: e for e in lock["agents"]["jarvo-studio"] if e["source"] == "lemo-wake"}
    assert set(wpisy) == {"design/lemo-wake", "design/lemo-wake-layers"}    # bez skilla upload
    assert "scripts" in wpisy["design/lemo-wake"]["pomin"]                   # skrypty tylko z biblioteki ($LW)
    assert "/skills/upload/" in lw.POMIN
    zrodla = yaml.safe_load((REPO / "vendor/zrodla.yaml").read_text(encoding="utf-8"))["zrodla"]
    assert zrodla["lemo-wake"]["przejrzane"] == lw.REV and zrodla["lemo-wake"]["status"] == "uzywane"


def test_pakiety_przypiete_i_zwolnione_z_kwarantanny_uv():
    assert all("==" in p for p in lw.PY_PAKIETY)
    nazwy = {p.split("==")[0] for p in lw.PY_PAKIETY}
    assert {"numpy", "pillow", "pillow-heif", "psd-tools", "opencv-python-headless", "onnxruntime"} == nazwy
    zw = lw.uv_zwolnienia(["numpy==2.5.3", "pillow"])
    assert zw == ["--exclude-newer-package", "numpy=false"]


def test_env_sciezki_i_przegladarka_z_obrazu(monkeypatch, tmp_path):
    monkeypatch.setattr(lw, "LIB", tmp_path / "lemo-wake")
    monkeypatch.setattr(lw, "VENV", tmp_path / "lemo-wake" / ".venv")
    monkeypatch.setattr(lw, "DANE", tmp_path / "dane")
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path / "pw"))
    assert "CHROME" not in lw.env()
    for build in ("1200", "1243"):
        shell = tmp_path / "pw" / f"chromium_headless_shell-{build}" / "chrome-headless-shell-linux64" / "chrome-headless-shell"
        shell.parent.mkdir(parents=True)
        shell.write_text("")
    env = lw.env()
    assert env["CHROME"].endswith("chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell")
    assert env["LW"] == str(tmp_path / "lemo-wake" / "skills" / "wake")
    assert env["LW_WARSTWY"] == str(tmp_path / "lemo-wake" / "skills" / "layers")
    assert env["LW_PY"] == str(tmp_path / "lemo-wake" / ".venv" / "bin" / "python")
    assert env["LEMO_WAKE_MODELS"] == str(tmp_path / "dane" / "models")         # modele poza klonem
    assert env["LW_HISTORIA"] == str(tmp_path / "dane" / "history.jsonl")


def test_env_do_eval_w_powloce(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(lw, "LIB", tmp_path / "lemo wake")                      # spacja w ścieżce
    monkeypatch.setattr(lw, "DANE", tmp_path / "dane")
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path / "pw"))
    assert lw.main(["env"]) == 0
    out = capsys.readouterr().out
    wynik = subprocess.run(["bash", "-c", f'eval "$(cat)"; printf %s "$LW"'], input=out, capture_output=True, text=True)
    assert wynik.stdout == str(tmp_path / "lemo wake" / "skills" / "wake")


def test_status_modele_i_zgoda(monkeypatch, tmp_path):
    monkeypatch.setattr(lw, "LIB", tmp_path / "lemo-wake")
    monkeypatch.setattr(lw, "VENV", tmp_path / "lemo-wake" / ".venv")
    monkeypatch.setattr(lw, "SKRYPTY", tmp_path / "lemo-wake" / "skills" / "wake" / "scripts")
    monkeypatch.setattr(lw, "DANE", tmp_path / "dane")
    st = lw.status()
    assert st["biblioteka"] is False and st["python"] is False and st["playwright"] is False
    assert st["zgoda_na_modele"] == "nie-pytano" and not any(st["modele"].values())
    modele = tmp_path / "dane" / "models"
    modele.mkdir(parents=True)
    (modele / "consent.json").write_text(json.dumps({"download": True}))
    (modele / "mobile_sam_image_encoder.onnx").write_text("x")
    st = lw.status()
    assert st["zgoda_na_modele"] == "tak"
    assert st["modele"]["sam"] is False                                          # SAM to dwa pliki
    (modele / "sam_mask_decoder_multi.onnx").write_text("x")
    assert lw.status()["modele"]["sam"] is True
    (modele / "consent.json").write_text(json.dumps({"download": False}))
    assert lw.zgoda() == "nie"
    (modele / "consent.json").write_text("{zepsuty")
    assert lw.zgoda() == "nie-pytano"


def test_znaczniki_instalacji(monkeypatch, tmp_path):
    venv = tmp_path / ".venv"
    skrypty = tmp_path / "scripts"
    monkeypatch.setattr(lw, "VENV", venv)
    monkeypatch.setattr(lw, "SKRYPTY", skrypty)
    (venv / "bin").mkdir(parents=True)
    (venv / "bin" / "python").write_text("")
    assert not lw.python_gotowy()
    lw.znacznik_py().write_text(lw.podpis(*lw.PY_PAKIETY) + "\n")
    assert lw.python_gotowy()
    monkeypatch.setattr(lw, "PY_PAKIETY", [*lw.PY_PAKIETY, "nowy==1.0.0"])     # nowy pin w repo = doinstaluj
    assert not lw.python_gotowy()
    (skrypty / "node_modules").mkdir(parents=True)
    (skrypty / "package-lock.json").write_text('{"v": 1}')
    lw.znacznik_node().write_text(lw.podpis('{"v": 1}'))
    assert lw.node_gotowy()
    (skrypty / "package-lock.json").write_text('{"v": 2}')
    assert not lw.node_gotowy()


def test_klon_bez_uploadu_i_przejscie_na_nowy_commit(tmp_path):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t"}
    up = tmp_path / "up"

    def git(*a, cwd=up):
        return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True, env=env).stdout.strip()

    def commit(files: dict[str, str]) -> str:
        for rel, body in files.items():
            (up / rel).parent.mkdir(parents=True, exist_ok=True)
            (up / rel).write_text(body)
        git("add", "-A")
        git("commit", "-q", "-m", "c")
        return git("rev-parse", "HEAD")

    up.mkdir()
    git("init", "-q", "-b", "main")
    git("config", "uploadpack.allowFilter", "true")
    git("config", "uploadpack.allowAnySHA1InWant", "true")
    a = commit({"skills/wake/SKILL.md": "v1", "skills/layers/SKILL.md": "l", "skills/upload/SKILL.md": "u",
                "README.zh-CN.md": "zh", "LICENSE": "cc"})
    b = commit({"skills/wake/SKILL.md": "v2"})
    dest = tmp_path / "lib"
    lw.klon(f"file://{up}", a, dest)
    assert lw.git_head(dest) == a and (dest / "skills/wake/SKILL.md").read_text() == "v1"
    assert (dest / "LICENSE").exists() and (dest / "skills/layers/SKILL.md").exists()
    assert not (dest / "skills/upload").exists() and not (dest / "README.zh-CN.md").exists()
    lw.klon(f"file://{up}", b, dest)
    assert lw.git_head(dest) == b and (dest / "skills/wake/SKILL.md").read_text() == "v2"
