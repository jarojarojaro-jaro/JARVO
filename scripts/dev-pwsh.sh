#!/usr/bin/env bash
# PowerShell 7 i PSScriptAnalyzer do testów install.ps1 na Linuksie (make dev-pwsh), bez roota i bez apt:
# paczki przypięte wersją i sumą SHA256, rozpakowane do .tools/ w repo (poza gitem).
#
#   bash scripts/dev-pwsh.sh          # .tools/pwsh/pwsh i .tools/psmodules/PSScriptAnalyzer
#
# tests/test_install_ps1.py szuka pwsh najpierw w .tools/pwsh, potem na PATH; bez niego testy są pomijane.
# Wersje: PowerShell z repozytorium Microsoftu dla Ubuntu 24.04 (suma z jego indeksu Packages),
# PSScriptAnalyzer z PowerShell Gallery (suma SHA512 z API galerii zgodna z SHA256 poniżej).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
T="$ROOT/.tools"
PWSH_VER=7.5.5-1
PWSH_URL="https://packages.microsoft.com/ubuntu/24.04/prod/pool/main/p/powershell/powershell_${PWSH_VER}.deb_amd64.deb"
PWSH_SHA=a8bc51c83316d93ec38d14c5877fa4749ca3a843864985c408d6c0a104069093
PSA_VER=1.24.0
PSA_URL="https://www.powershellgallery.com/api/v2/package/PSScriptAnalyzer/$PSA_VER"
PSA_SHA=e86c97d44bb1bc8a1de35e753b85ea1d938f6f9f881639a181507e079bca4556

[[ "$(uname -s)-$(uname -m)" == Linux-x86_64 ]] || { echo "dev-pwsh: tylko Linux x86_64 (gdzie indziej: pwsh z systemu)"; exit 0; }

get() {   # get <url> <sha256> <plik>
  if [[ -f "$3" ]] && echo "$2  $3" | sha256sum -c --quiet 2>/dev/null; then return; fi
  curl -fsSL --retry 3 -o "$3.part" "$1"
  echo "$2  $3.part" | sha256sum -c --quiet || { rm -f "$3.part"; echo "dev-pwsh: zła suma $1" >&2; exit 1; }
  mv "$3.part" "$3"
}

mkdir -p "$T/pobrane"
# shellcheck disable=SC2016  # $PSVersionTable to kod PowerShella, nie basha
if [[ ! -x "$T/pwsh/pwsh" ]] || ! "$T/pwsh/pwsh" -NoLogo -NoProfile -Command '$PSVersionTable.PSVersion.ToString()' | grep -qx "${PWSH_VER%-*}"; then
  get "$PWSH_URL" "$PWSH_SHA" "$T/pobrane/powershell.deb"
  d="$(mktemp -d)"
  (cd "$d" && ar x "$T/pobrane/powershell.deb" && tar -xf data.tar.*)
  rm -rf "$T/pwsh" && mv "$d/opt/microsoft/powershell/7" "$T/pwsh" && rm -rf "$d"
  chmod +x "$T/pwsh/pwsh"
fi
if [[ ! -f "$T/psmodules/PSScriptAnalyzer/$PSA_VER/PSScriptAnalyzer.psd1" ]]; then
  get "$PSA_URL" "$PSA_SHA" "$T/pobrane/psscriptanalyzer.nupkg"
  rm -rf "$T/psmodules/PSScriptAnalyzer" && mkdir -p "$T/psmodules/PSScriptAnalyzer/$PSA_VER"
  python3 -I -c 'import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])' \
    "$T/pobrane/psscriptanalyzer.nupkg" "$T/psmodules/PSScriptAnalyzer/$PSA_VER"
fi
# shellcheck disable=SC2016
echo "✓ $("$T/pwsh/pwsh" -NoLogo -NoProfile -Command '"PowerShell $($PSVersionTable.PSVersion)"'), PSScriptAnalyzer $PSA_VER w $T"
