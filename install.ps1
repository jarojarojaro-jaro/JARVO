# Instalator Jarvo dla Windowsa (PowerShell). Jedno polecenie ze strony:
#
#   irm https://raw.githubusercontent.com/jarojarojaro-jaro/JARVO/HEAD/install.ps1 | iex
#
# Jarvo działa w Dockerze przez WSL2. Skrypt sprawdza WSL i Docker Desktop, a potem uruchamia
# ten sam instalator co na Linuksie (install.sh) wewnątrz domyślnej dystrybucji WSL.
$ErrorActionPreference = "Stop"
$Base = if ($env:JARVO_INSTALL_BASE) { $env:JARVO_INSTALL_BASE } else { "https://raw.githubusercontent.com/jarojarojaro-jaro/JARVO/HEAD" }

function Say($t) { Write-Host "▌ " -ForegroundColor Red -NoNewline; Write-Host $t }
function Die($t) { Write-Host "✗ $t" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "  ██████  J A R V O" -ForegroundColor White
Write-Host "  ██████  from idea to reality." -ForegroundColor Red
Write-Host ""

# 1. WSL2 z dystrybucją Linuksa
$wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
$distros = if ($wsl) { (wsl.exe -l -q 2>$null) -replace "`0", "" | Where-Object { $_.Trim() } } else { @() }
if (-not $distros) {
  Say "Brak WSL z Linuksem. Instaluję WSL + Ubuntu (potrzebne uprawnienia administratora)."
  Start-Process wsl.exe -ArgumentList "--install -d Ubuntu" -Verb RunAs -Wait
  Die "Po instalacji uruchom ponownie komputer, otwórz raz Ubuntu (ustaw użytkownika) i wklej to polecenie jeszcze raz."
}
Say "WSL: $($distros[0].Trim())"

# 2. Docker Desktop z integracją WSL
if (-not (Get-Command docker.exe -ErrorAction SilentlyContinue)) {
  Die "Brak Docker Desktop. Zainstaluj: https://www.docker.com/products/docker-desktop/ (w Settings → Resources → WSL integration włącz swoją dystrybucję), potem uruchom polecenie ponownie."
}
wsl.exe -e sh -c "docker info >/dev/null 2>&1"
if ($LASTEXITCODE -ne 0) {
  Die "Docker nie odpowiada w WSL. Uruchom Docker Desktop i włącz Settings → Resources → WSL integration dla swojej dystrybucji."
}

# 3. Ten sam instalator co na Linuksie, w WSL (pytania o dostawcę modeli pojawią się tutaj)
Say "Uruchamiam instalator w WSL…"
wsl.exe -e bash -lc "curl -fsSL '$Base/install.sh' | bash"
if ($LASTEXITCODE -ne 0) { Die "Instalacja się nie udała (log powyżej)." }
Start-Process "http://localhost:9119/base"
