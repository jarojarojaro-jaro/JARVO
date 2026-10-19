"""Komputer Jarva, etap K1 (docs/KOMPUTER.md): obraz infra/komputer, usługa compose, filtr ruchu, polecenie jarvo."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys

import pytest
import yaml

from conftest import REPO

KOMP = REPO / "infra" / "komputer"
sys.path.insert(0, str(REPO / "komputer"))
import jarvo_cua  # noqa: E402


def _compose() -> dict:
    return yaml.safe_load((REPO / "infra" / "docker-compose.yml").read_text(encoding="utf-8"))


def _tekst(nazwa: str) -> str:
    return (KOMP / nazwa).read_text(encoding="utf-8")


def test_usluga_bez_portow_kluczy_i_sieci_floty():
    c = _compose()
    k = c["services"]["komputer"]
    assert k["profiles"] == ["komputer"]
    assert k["image"] == "jarvo-komputer:local" and k["build"]["context"] == "./komputer"
    assert "ports" not in k and "expose" not in k and "network_mode" not in k
    assert k["networks"] == ["jarvo-komputer-net"]
    assert "jarvo-komputer-net" in c["networks"]
    assert not k.get("privileged") and "devices" not in k and "env_file" not in k
    # tylko gniazda i stan pulpitu: bez repo, sekretów, danych floty i gniazda Dockera
    assert k["volumes"] == ["komputer-gniazda:/run/jarvo-komputer", "komputer-dom:/home"]
    assert set(k["environment"]) == {"TZ", "KOMPUTER_EKRAN", "KOMPUTER_BLOKADA"}
    assert k["cap_drop"] == ["ALL"]
    assert set(k["cap_add"]) == {"CHOWN", "DAC_OVERRIDE", "FOWNER", "KILL", "NET_ADMIN", "SETGID", "SETPCAP", "SETUID"}
    assert k["security_opt"] == ["no-new-privileges:true"]
    limity = k["deploy"]["resources"]["limits"]
    assert limity["memory"] == "${KOMPUTER_MEM_LIMIT:-2g}" and limity["pids"] == 2048
    assert c["volumes"]["komputer-gniazda"] == {"name": "jarvo-komputer-gniazda"}
    assert c["volumes"]["komputer-dom"] == {"name": "jarvo-komputer-dom"}


def test_hermes_widzi_gniazda_tam_gdzie_szuka_bramka():
    h = _compose()["services"]["hermes"]
    assert "komputer-gniazda:/opt/jarvo/komputer" in h["volumes"]
    assert "komputer" not in h.get("profiles", [])
    assert jarvo_cua.GNIAZDO == "/opt/jarvo/komputer/cua.sock"


def test_obraz_przypiety_i_sterownik_sprawdzany_suma():
    d = _tekst("Dockerfile")
    assert re.search(r"^ARG DEBIAN_IMAGE=debian:trixie-slim@sha256:[0-9a-f]{64}$", d, re.M)
    assert f"ARG CUA_DRIVER_VERSION={jarvo_cua.WERSJA_STEROWNIKA}" in d
    sumy = dict(re.findall(r"^ARG CUA_DRIVER_SHA256_(AMD64|ARM64)=([0-9a-f]{64})$", d, re.M))
    assert set(sumy) == {"AMD64", "ARM64"}
    assert "sha256sum -c" in d and not re.search(r"\| *(ba)?sh\b", d)
    # sumy i wersja zapisane w spisie źródeł
    zr = yaml.safe_load((REPO / "vendor" / "zrodla.yaml").read_text(encoding="utf-8"))["zrodla"]["cua"]
    assert jarvo_cua.WERSJA_STEROWNIKA in zr["notatka"]
    assert sumy["AMD64"] in zr["notatka"] and sumy["ARM64"] in zr["notatka"]
    assert (KOMP / "LICENSE-cua-driver.md").read_text(encoding="utf-8").startswith("MIT License")
    assert 'ENTRYPOINT ["/usr/bin/tini"' in d and "HEALTHCHECK" in d
    assert "CUA_DRIVER_RS_TELEMETRY_ENABLED=0" in d and "CUA_DRIVER_RS_UPDATE_CHECK=false" in d


def test_ekran_tylko_na_gniezdzie_z_ciasteczkiem():
    s = _tekst("start.sh")
    xvnc = s[s.index("jako_pulpit Xvnc"):]
    xvnc = xvnc[:xvnc.index("XVNC=$!")]
    for flaga in ("-rfbport -1", "-rfbunixpath", "-rfbunixmode 0660", "-nolisten tcp", "-nolisten local", "-auth"):
        assert flaga in xvnc
    assert "--force-renderer-accessibility" in s and "--remote-debugging" not in s
    # drzewo dostępności: szyna AT-SPI włączona, zanim wystartuje Chromium (inaczej sterownik widzi samo okno)
    assert s.index("ScreenReaderEnabled") < s.index("przegladarka &")
    # wszystko na ekranie jako pulpit, bez nowych uprawnień
    assert "--no-new-privs" in s and "--bounding-set=-all" in s


def test_filtr_ruchu_przed_pulpitem_i_bez_powrotu():
    s = _tekst("start.sh")
    for zakres in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16", "100.64.0.0/10", "127.0.0.0/8"):
        assert zakres in s
    assert "--dport 25" in s
    assert 'die "iptables nie działa' in s and "filtr nie zadziałał" in s
    # filtr ustawiany przed pulpitem, potem NET_ADMIN znika ze zbioru uprawnień
    assert s.index("\n  filtr\n") < s.index("jako_pulpit Xvnc")
    assert "--bounding-set=-net_admin,-net_raw" in s


def test_polityka_chromium():
    p = json.loads(_tekst("chromium.json"))
    assert p["PasswordManagerEnabled"] is False and p["AutofillCreditCardEnabled"] is False
    assert p["SyncDisabled"] is True and p["BrowserSignin"] == 0
    assert p["ExtensionInstallBlocklist"] == ["*"]
    assert "file://*" in p["URLBlocklist"]
    assert p["DownloadDirectory"].startswith("/home/pulpit/")


def test_polecenie_jarvo_komputer():
    j = (REPO / "bin" / "jarvo").read_text(encoding="utf-8")
    assert "#   jarvo komputer on|off|status|wyczysc|odswiez" in j
    assert "komputer|computer) cmd_komputer" in j
    for czesc in ("on)", "off)", "wyczysc|clean)", "odswiez|refresh)", "status)"):
        assert czesc in j[j.index("cmd_komputer() {"):]
    assert "jarvo-komputer-dom" in j[j.index("cmd_uninstall() {"):]


def test_deploy_i_piaskownica_buduja_komputer():
    d = (REPO / "scripts" / "deploy.sh").read_text(encoding="utf-8")
    assert "KOMPUTER_CPUS=2" in d and ".komputer-tree" in d and "build komputer" in d
    assert "KOMPUTER_BLOKADA" in d and "zdrowie.sh" in d
    s = (REPO / "scripts" / "sandbox-up.sh").read_text(encoding="utf-8")
    assert "JARVO_KOMPUTER" in s and "komputer-ca:test" in s and ".komputer-tree" in s


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="brak shellcheck (make dev-deps)")
def test_shellcheck_skryptow_komputera():
    res = subprocess.run(["shellcheck", "-S", "warning", str(KOMP / "start.sh"), str(KOMP / "zdrowie.sh")],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stdout
