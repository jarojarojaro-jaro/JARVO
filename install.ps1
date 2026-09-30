# Instalator Jarvo dla Windowsa (PowerShell). Jedno polecenie ze strony:
#
#   irm https://raw.githubusercontent.com/jarojarojaro-jaro/JARVO/main/install.ps1 | iex
#
# Jarvo działa w Dockerze przez WSL2. Skrypt sprawdza WSL i Docker Desktop, a potem uruchamia
# ten sam instalator co na Linuksie (install.sh) wewnątrz domyślnej dystrybucji WSL. Hasła Linuksa nie trzeba:
# na czas instalacji użytkownik WSL dostaje sudo bez hasła (przez wsl -u root), zabierane zaraz po niej.
$ErrorActionPreference = "Stop"
$Base = if ($env:JARVO_INSTALL_BASE) { $env:JARVO_INSTALL_BASE } else { "https://raw.githubusercontent.com/jarojarojaro-jaro/JARVO/main" }

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

# 3. Ten sam instalator co na Linuksie, w WSL (pytania o dostawcę modeli pojawią się tutaj).
# Hasło Linuksa w WSL to NIE hasło Windowsa i ludzie go nie pamiętają. Windows i tak wchodzi do WSL jako root
# bez hasła (wsl -u root), więc na czas instalacji dajemy użytkownikowi sudo bez hasła i zabieramy je na końcu.
$User = ((wsl.exe -e sh -c "id -un") | Out-String).Trim()
$Drop = "/etc/sudoers.d/zz-jarvo-install"
$DropTmp = "/etc/sudoers.d/.zz-jarvo-install.tmp"
$Granted = $false
if ($User -and $User -ne "root") {
  wsl.exe -u root -e sh -c "printf '%s ALL=(ALL) NOPASSWD: ALL\n' '$User' > $DropTmp && chmod 440 $DropTmp && visudo -cf $DropTmp >/dev/null && mv $DropTmp $Drop"
  if ($LASTEXITCODE -eq 0) { $Granted = $true }
  else { Say "Nie udało się dać tymczasowych uprawnień: instalator zapyta o hasło Linuksa w WSL (nie Windowsa)." }
}
Say "Uruchamiam instalator w WSL…"
$Code = 1
try {
  wsl.exe -e bash -lc "curl -fsSL '$Base/install.sh' | bash"
  $Code = $LASTEXITCODE
} finally {
  if ($Granted) { wsl.exe -u root -e rm -f $Drop $DropTmp }
}
if ($Code -ne 0) { Die "Instalacja się nie udała (log powyżej; pełny: ~/jarvo-local/install.log w WSL)." }
# dashboard otwiera już install.sh (jarvo open w WSL): tu nie otwieramy drugiej karty
