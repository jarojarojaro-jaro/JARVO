# Instalator Jarvo dla Windowsa (PowerShell, zwykły użytkownik). Jedno polecenie ze strony:
#
#   irm https://raw.githubusercontent.com/jarojarojaro-jaro/JARVO/main/install.ps1 | iex   (albo jarvo.pl/install.ps1)
#   (jarvo.pl/install.ps1 przekierowuje na ten adres, gdy strona jest wgrana: site/.htaccess)
#
# Jarvo działa w Linuksie (WSL2) z Dockerem w środku. Skrypt robi wszystko sam, każdy krok pomija, gdy jest już
# zrobiony (drugie uruchomienie = aktualizacja):
#   1. sprawdza Windowsa (10 w wersji 2004+ albo 11), procesor (x64, ARM64), RAM i dysk;
#   2. WSL2: brak → `wsl --install --no-distribution` (jedno okno zgody administratora), restart komputera,
#      a po zalogowaniu instalator sam rusza dalej (wpis RunOnce);
#   3. osobna dystrybucja „Jarvo”: oficjalny obraz Ubuntu 24.04 dla WSL (suma SHA256 sprawdzana) wgrany przez
#      `wsl --import`, użytkownik jarvo z sudo bez hasła (Windows i tak wchodzi do WSL jako root, więc hasło
#      Linuksa nic nie chroni, a ludzie go zapominają) i systemd. Bez Microsoft Store, bez Docker Desktop,
#      bez pytań o hasło. Gdy Jarvo stoi już w innej dystrybucji (np. Ubuntu z Docker Desktop), aktualizuje tamtą;
#   4. w środku ten sam instalator co na Linuksie (install.sh): Docker Engine, repo, gotowy obraz floty, flota;
#   5. autostart: po zalogowaniu do Windowsa ukryty proces trzyma dystrybucję przy życiu (systemd → Docker → flota);
#   6. otwiera dashboard.
#
# Zmienne (opcjonalne): JARVO_TOKEN (klucz dostępu do prywatnej kopii repo; publiczne go nie potrzebuje), JARVO_PROVIDER, JARVO_KEY, JARVO_YES=1,
# JARVO_BRANCH, JARVO_FORCE=1, JARVO_DISTRO (nazwa dystrybucji, domyślnie Jarvo), JARVO_INSTALL_BASE (skąd pobrać
# install.sh), JARVO_UNINSTALL=1 (usuń dystrybucję Jarvo i autostart), JARVO_DRY_RUN=1 (tylko pokaż kroki).
# Opis i decyzje: docs/INSTALER.md.

# `irm | iex` działa w sesji użytkownika: jej ustawienia przywracamy na końcu
$JarvoPrefs = @($ErrorActionPreference, $ProgressPreference)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # pasek postępu spowalnia Invoke-WebRequest kilkukrotnie
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch { Write-Verbose "TLS 1.2: $_" }

function EnvOr([string]$Name, [string]$Default) {
  $v = [Environment]::GetEnvironmentVariable($Name)
  if ($v) { return $v } else { return $Default }
}

$Base = EnvOr "JARVO_INSTALL_BASE" "https://raw.githubusercontent.com/jarojarojaro-jaro/JARVO/main"
$Distro = EnvOr "JARVO_DISTRO" "Jarvo"
$Dry = (EnvOr "JARVO_DRY_RUN" "0") -eq "1"
$Yes = (EnvOr "JARVO_YES" "0") -eq "1"
$Force = (EnvOr "JARVO_FORCE" "0") -eq "1"
$JarvoDir = Join-Path (EnvOr "LOCALAPPDATA" (EnvOr "HOME" ".")) "Jarvo"
$RootfsBase = "https://cloud-images.ubuntu.com/wsl/releases/24.04/current"
$Url = "http://localhost:9119/jarvo"
$Ram = 0
$RunOnceKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce"
$env:WSL_UTF8 = "1"   # nowsze wsl.exe piszą wtedy UTF-8 zamiast UTF-16

function Say([string]$t) { Write-Host "▌ " -ForegroundColor Red -NoNewline; Write-Host $t }
function Warn([string]$t) { Write-Host "! $t" -ForegroundColor Yellow }
function Die([string]$t) { throw [System.Exception]::new("JARVO: $t") }
function Show([string]$t) { Write-Host "  $ $t" -ForegroundColor DarkGray }

# Programy spoza PowerShella (wsl.exe, curl.exe) uruchamiamy z ErrorActionPreference=Continue: w Windows PowerShell 5.1
# każda linia na stderr przy przekierowaniu staje się błędem, a przy Stop przerywa instalację
function Native([scriptblock]$Block) {
  $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
  try { & $Block } finally { $ErrorActionPreference = $old }
}
# wsl.exe z limitem czasu (aktualizacja WSL, sprawdzanie innych dystrybucji): -1, gdy nie skończył w porę (proces ubity)
function WslTimed([string]$ArgLine, [int]$Seconds) {
  $p = Start-Process wsl.exe -ArgumentList $ArgLine -WindowStyle Hidden -PassThru
  $null = $p.Handle   # bez tego ExitCode bywa pusty po WaitForExit(ms)
  if (-not $p.WaitForExit($Seconds * 1000)) { try { $p.Kill() } catch { $null = $_ }; return -1 }
  return $p.ExitCode
}
# wsl.exe przez jedną funkcję: na sucho tylko pokazujemy polecenie
function Wsl {
  if ($Dry) { Show ("wsl.exe " + ($args -join " ")); $global:LASTEXITCODE = 0; return }
  $a = $args
  Native { & wsl.exe @a }
}
function WslOut {   # wyjście wsl.exe jako tekst (stare wsl.exe piszą UTF-16: zera wycinamy)
  if ($Dry) { return "" }
  $a = $args
  $o = Native { & wsl.exe @a 2>$null | Out-String }
  return ([string]$o -replace "`0", "").Trim()
}

function Ask([string]$Question) {   # tak/nie; JARVO_YES=1 i próba na sucho odpowiadają „tak”
  if ($Yes -or $Dry) { return $true }
  $a = Read-Host "$Question [T/n]"
  return -not ($a -match '^[nN]')
}

function WriteText([string]$Path, [string]$Text, [bool]$Bom) {   # LF dla Linuksa, BOM dla PowerShella 5.1
  if ($Dry) { Show "zapis $Path"; return }
  New-Item -ItemType Directory -Force -Path (Split-Path $Path) | Out-Null
  [IO.File]::WriteAllText($Path, $Text, (New-Object Text.UTF8Encoding $Bom))
}

# ---------------------------------------------------------------- klucz dostępu (prywatne repo)
$Token = EnvOr "JARVO_TOKEN" ""
$TokenFile = Join-Path $JarvoDir "token.dat"
function LoadToken {   # po restarcie: klucz zaszyfrowany dla tego użytkownika Windows (DPAPI)
  if ($Token -or -not (Test-Path $TokenFile)) { return }
  try {
    $s = Get-Content $TokenFile | ConvertTo-SecureString
    $script:Token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))
  } catch { Warn "Nie odczytałem zapisanego klucza dostępu: zapytam o niego, jeśli będzie potrzebny." }
}
function SaveToken {
  if (-not $Token -or $Dry) { return }
  New-Item -ItemType Directory -Force -Path $JarvoDir | Out-Null
  ConvertTo-SecureString $Token -AsPlainText -Force | ConvertFrom-SecureString | Set-Content $TokenFile
}
function AskToken {
  if ($Token -or $Dry -or $Yes) { return $false }
  Warn "Nie mogę pobrać Jarvo anonimowo (prywatna kopia repo albo brak dostępu)."
  $s = Read-Host "Wklej klucz dostępu od właściciela (token GitHub; nie będzie widoczny)" -AsSecureString
  $script:Token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))
  return [bool]$Token
}

function Download([string]$Src, [string]$Dest) {   # klucz idzie tylko do GitHuba, nigdy na inne adresy
  if ($Dry) { Show "pobierz $Src → $Dest"; return }
  New-Item -ItemType Directory -Force -Path (Split-Path $Dest) | Out-Null
  $h = @{}
  if ($Token -and ([Uri]$Src).Host -match '(^|\.)github(usercontent)?\.com$') { $h["Authorization"] = "token $Token" }
  Invoke-WebRequest -UseBasicParsing -Headers $h -Uri $Src -OutFile $Dest -ErrorAction Stop
}

function GetInstallFile([string]$Name, [string]$As = "") {   # install.sh / install.ps1 z $Base (z kluczem, gdy repo prywatne)
  $dest = Join-Path $JarvoDir $(if ($As) { $As } else { $Name })
  try { Download "$Base/$Name" $dest }
  catch {
    if (-not (AskToken)) { Die "Nie udało się pobrać $Base/$Name ($($_.Exception.Message)). Sprawdź internet albo klucz dostępu (JARVO_TOKEN)." }
    try { Download "$Base/$Name" $dest } catch { Die "Klucz dostępu nie działa ($($_.Exception.Message))." }
  }
  return $dest
}

# ---------------------------------------------------------------- system
function CheckSystem {
  $isWin = [Environment]::OSVersion.Platform -eq "Win32NT"
  if (-not $isWin -and -not $Dry) { Die "To polecenie jest dla Windowsa. Na Linuksie i macOS: curl -fsSL $Base/install.sh | bash" }
  $build = [int](EnvOr "JARVO_FAKE_BUILD" ([string][Environment]::OSVersion.Version.Build))
  if ($build -lt 19041) { Die "Potrzebny Windows 10 w wersji 2004 (kompilacja 19041) albo nowszy, albo Windows 11. Masz kompilację ${build}: zaktualizuj Windowsa (Ustawienia → Windows Update)." }
  $a = EnvOr "JARVO_FAKE_ARCH" (EnvOr "PROCESSOR_ARCHITECTURE" "AMD64")
  switch ($a) {
    "AMD64" { $script:Arch = "amd64" }
    "ARM64" { $script:Arch = "arm64" }
    default { Die "Nieobsługiwany procesor: $a (potrzebny x64 albo ARM64)." }
  }
  $ram = [int](EnvOr "JARVO_FAKE_RAM_GB" "0")
  if (-not $ram) { try { $ram = [int]((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB) } catch { $ram = 0 } }
  $disk = [int](EnvOr "JARVO_FAKE_DISK_GB" "0")
  if (-not $disk) { try { $disk = [int]((Get-PSDrive ($env:LOCALAPPDATA.Substring(0, 1))).Free / 1GB) } catch { $disk = 0 } }
  $script:Ram = $ram
  Say "System: Windows (kompilacja $build, $Arch), RAM $ram GB, wolne miejsce $disk GB"
  if ($ram -gt 0 -and $ram -lt 4 -and -not $Force) { Die "Za mało RAM ($ram GB): flota potrzebuje 8 GB (minimum 4). JARVO_FORCE=1 wymusza." }
  if ($ram -gt 0 -and $ram -lt 8) { Warn "Polecamy 8 GB RAM (masz $ram GB): agenci mogą działać wolniej." }
  # aktualizacja: Linux, obraz i dane już są na dysku (dysk dystrybucji Jarvo albo autostart z poprzedniej instalacji),
  # nowa wersja obrazu dokłada najwyżej kilka GB
  $installed = (Test-Path (Join-Path $JarvoDir "wsl\ext4.vhdx")) -or (Test-Path (StartupVbs))
  if ($Dry) { $installed = (EnvOr "JARVO_FAKE_INSTALLED" "0") -eq "1" }
  if ($installed) {
    if ($disk -gt 0 -and $disk -lt 5 -and -not $Force) { Die "Za mało miejsca na aktualizację ($disk GB): nowa wersja obrazu floty potrzebuje do ~5 GB. Zwolnij miejsce na dysku C: albo JARVO_FORCE=1 wymusza." }
    if ($disk -gt 0 -and $disk -lt 10) { Warn "Masz $disk GB wolnego miejsca: na aktualizację wystarczy, ale na projekty i filmy zostanie mało." }
    return
  }
  if ($disk -gt 0 -and $disk -lt 20 -and -not $Force) { Die "Za mało miejsca ($disk GB): Linux, obraz i dane floty potrzebują ~30 GB (minimum 20). JARVO_FORCE=1 wymusza." }
  if ($disk -gt 0 -and $disk -lt 30) { Warn "Masz $disk GB wolnego miejsca: wystarczy, Jarvo zajmie ok. 15 GB (Linux, obraz floty ok. 7 GB po rozpakowaniu, Komputer Jarva 1,6 GB). 30 GB polecamy jako zapas na projekty, filmy i aktualizacje." }
}

# ---------------------------------------------------------------- WSL
function WslReady {
  if ($Dry) { return (EnvOr "JARVO_FAKE_WSL" "jest") -eq "jest" }
  if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { return $false }
  Native { & wsl.exe --status *> $null }
  return ($LASTEXITCODE -eq 0)
}

function SaveSelfForResume {   # po restarcie RunOnce uruchamia zapisaną kopię instalatora
  $self = Join-Path $JarvoDir "install.ps1"
  try {
    $tmp = GetInstallFile "install.ps1" "install.ps1.new"
    if (-not $Dry) { WriteText $self (Get-Content -Raw -Encoding UTF8 $tmp) $true; Remove-Item $tmp -Force }
  } catch { Warn "Nie zapisałem kopii instalatora: po restarcie wklej polecenie instalacji jeszcze raz." ; return $null }
  return $self
}

function InstallWsl {
  Say "Instaluję WSL (podsystem Linuksa w Windowsie). Windows poprosi o zgodę administratora."
  $self = SaveSelfForResume
  SaveToken
  # WSL bierze domyślnie połowę RAM: przy 8–15 GB to za mało na flotę (limit kontenera 5 GB). Świeży WSL nie ma
  # innych dystrybucji, więc własny ~/.wslconfig nikomu nie przeszkadza; istniejącego nie ruszamy.
  $cfg = Join-Path (EnvOr "USERPROFILE" (EnvOr "HOME" ".")) ".wslconfig"
  if ($Ram -ge 8 -and $Ram -lt 16 -and -not (Test-Path $cfg)) {
    WriteText $cfg "# Jarvo (install.ps1): pamięć maszyny WSL dla floty; bez tego pliku WSL wraca do domyślnej połowy RAM`r`n[wsl2]`r`nmemory=$($Ram - 3)GB`r`n" $false
    Say "WSL dostanie $($Ram - 3) GB RAM ($cfg)."
  }
  if ($Dry) { Show "Start-Process wsl.exe --install --no-distribution -Verb RunAs"; $code = 0 }
  else {
    try { $p = Start-Process wsl.exe -ArgumentList "--install", "--no-distribution" -Verb RunAs -Wait -PassThru; $code = $p.ExitCode }
    catch { Die "Bez zgody administratora nie zainstaluję WSL. Uruchom polecenie jeszcze raz i kliknij Tak." }
  }
  if ($code -ne 0) {
    # starszy Windows 10 nie zna --no-distribution: włączamy składniki systemu bezpośrednio
    Warn "wsl --install zwrócił ${code}: włączam składniki WSL i Platformy maszyny wirtualnej przez DISM."
    $cmd = "dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart; " +
           "dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart"
    if ($Dry) { Show "Start-Process powershell -Verb RunAs: $cmd" }
    else { Start-Process powershell.exe -ArgumentList "-NoProfile", "-Command", $cmd -Verb RunAs -Wait | Out-Null }
  }
  if (-not $Dry) { New-Item -ItemType Directory -Force -Path $JarvoDir | Out-Null; Set-Content (Join-Path $JarvoDir "po-restarcie") "1" }
  if ($self) {
    $run = "powershell.exe -NoExit -ExecutionPolicy Bypass -File `"$self`""
    if ($Dry) { Show "RunOnce JarvoInstall = $run" } else { Set-ItemProperty -Path $RunOnceKey -Name "JarvoInstall" -Value $run }
  }
  Say "WSL zainstalowany. Potrzebny restart komputera; po zalogowaniu instalacja Jarvo ruszy sama."
  if (Ask "Uruchomić ponownie teraz?") {
    if ($Dry) { Show "Restart-Computer" } else { Restart-Computer -Force }
  } else { Say "Uruchom ponownie komputer, kiedy zechcesz." }
}

function Distros {
  if ($Dry) { return @((EnvOr "JARVO_FAKE_DISTROS" "") -split "," | Where-Object { $_ }) }
  return @((WslOut -l -q) -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -and $_ -notmatch '^docker-desktop' })
}

function ExistingInstall([string[]]$List) {   # Jarvo już stoi w innej dystrybucji (np. Ubuntu z Docker Desktop)?
  if ($Dry) { return (EnvOr "JARVO_FAKE_EXISTING" "") }
  $others = @($List | Where-Object { $_ -ne $Distro })
  if ($others.Count -gt 0) { Say "Szukam wcześniejszej instalacji Jarvo w innych dystrybucjach WSL ($($others.Count))…" }
  foreach ($d in $others) {
    # jeden wiersz poleceń dla wsl.exe; $HOME rozwija sh w Linuksie. Zawieszona dystrybucja nie blokuje instalacji.
    $code = WslTimed ('-d "' + $d + '" -e sh -c "test -f $HOME/jarvo-local/compose/.env"') 60
    if ($code -eq -1) { Warn "Dystrybucja $d nie odpowiada od minuty: pomijam ją." }
    if ($code -eq 0) { return $d }
  }
  return ""
}

function ToWslPath([string]$p) {   # C:\Users\x\… → /mnt/c/Users/x/…
  $full = [IO.Path]::GetFullPath($p)
  if ($full -match '^([A-Za-z]):\\(.*)$') { return "/mnt/" + $Matches[1].ToLower() + "/" + ($Matches[2] -replace '\\', '/') }
  return ($full -replace '\\', '/')
}

function ImportDistro {
  $file = "ubuntu-noble-wsl-$Arch-wsl.rootfs.tar.gz"
  $dest = Join-Path $JarvoDir $file
  Say "Pobieram Ubuntu 24.04 dla WSL (~340 MB, oficjalny obraz Canonical)…"
  Download "$RootfsBase/SHA256SUMS" (Join-Path $JarvoDir "SHA256SUMS")
  if (-not $Dry) {
    $want = (Get-Content (Join-Path $JarvoDir "SHA256SUMS") | Where-Object { $_ -match " \*?$([regex]::Escape($file))$" } | Select-Object -First 1) -split '\s+' | Select-Object -First 1
    if (-not $want) { Die "Brak sumy kontrolnej dla $file w $RootfsBase/SHA256SUMS." }
    $ok = (Test-Path $dest) -and ((Get-FileHash -Algorithm SHA256 $dest).Hash -eq $want.ToUpper())
    if (-not $ok) {
      if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
        Native { & curl.exe -fL --retry 3 -o $dest "$RootfsBase/$file" }
        if ($LASTEXITCODE -ne 0) { Die "Nie udało się pobrać $RootfsBase/$file." }
      } else { Download "$RootfsBase/$file" $dest }
      if ((Get-FileHash -Algorithm SHA256 $dest).Hash -ne $want.ToUpper()) { Remove-Item $dest -Force; Die "Pobrany obraz Ubuntu ma złą sumę kontrolną (przerwane pobieranie?). Uruchom polecenie jeszcze raz." }
    }
  } else { Show "pobierz $RootfsBase/$file → $dest (sprawdzenie SHA256)" }
  Say "Tworzę dystrybucję $Distro (Linux dla Jarvo, osobno od innych)…"
  $out = Join-Path $JarvoDir "wsl"
  if (-not $Dry) { New-Item -ItemType Directory -Force -Path $out | Out-Null }
  $msg = ""
  if ($Dry) { Wsl --import $Distro $out $dest --version 2 }
  else { $msg = [string](Native { & wsl.exe --import $Distro $out $dest --version 2 2>&1 | Out-String }) -replace "`0", "" }
  if ($LASTEXITCODE -ne 0) {
    if ($msg -match '0x80370102|HCS_E_HYPERV|virtualization|wirtualizac|BIOS') {
      Die "Komputer ma wyłączoną wirtualizację. Włącz ją w BIOS/UEFI (Intel VT-x albo AMD SVM; często w zakładce Advanced/CPU), uruchom Windowsa i wklej polecenie jeszcze raz."
    }
    Die "wsl --import się nie udał: $msg"
  }
  if (-not $Dry) { Remove-Item $dest -Force -ErrorAction SilentlyContinue }
}

function ConfigureDistro {   # użytkownik jarvo z sudo bez hasła, systemd, domyślny użytkownik (idempotentne)
  $sh = @'
set -e
id -u jarvo >/dev/null 2>&1 || useradd -m -s /bin/bash -G sudo jarvo
printf 'jarvo ALL=(ALL) NOPASSWD:ALL\n' > /etc/sudoers.d/jarvo && chmod 440 /etc/sudoers.d/jarvo
cat > /etc/wsl.conf <<'EOF'
# Dystrybucja Jarvo (install.ps1): systemd uruchamia Dockera i pomocnika aktualizacji
[boot]
systemd=true
[user]
default=jarvo
[interop]
enabled=true
appendWindowsPath=true
EOF
'@
  $f = Join-Path $JarvoDir "przygotuj.sh"
  WriteText $f ($sh -replace "`r`n", "`n") $false
  Wsl -d $Distro -u root -e bash (ToWslPath $f)
  if ($LASTEXITCODE -ne 0) { Die "Nie udało się przygotować dystrybucji $Distro." }
  Wsl --terminate $Distro   # nowa konfiguracja (systemd, użytkownik) działa od następnego startu
}

# ---------------------------------------------------------------- autostart
function StartupVbs {   # folder Autostart użytkownika (shell:startup)
  $startup = EnvOr "JARVO_FAKE_STARTUP" ""
  if (-not $startup) { $startup = [Environment]::GetFolderPath("Startup") }
  return (Join-Path $startup "Jarvo.vbs")
}

function Autostart([string]$Target) {   # ukryty proces po zalogowaniu trzyma dystrybucję (i flotę) przy życiu
  $vbs = StartupVbs
  $text = "' Jarvo: po zalogowaniu uruchamia Linuksa z flotą (install.ps1). Usunięcie pliku wyłącza autostart.`r`n" +
          "CreateObject(""WScript.Shell"").Run ""wsl.exe -d $Target -u root -e sleep infinity"", 0, False`r`n"
  WriteText $vbs $text $false
  if ($Dry) { Show "wscript.exe $vbs" } else { Start-Process wscript.exe -ArgumentList "`"$vbs`"" }
  Say "Autostart: $vbs"
}

# polecenie jarvo w PowerShellu i cmd: %LOCALAPPDATA%\Jarvo\bin\jarvo.cmd przekazuje wszystko do jarvo w Linuksie
$CmdDir = Join-Path $JarvoDir "bin"
$EnvKey = "HKCU:\Environment"
function UserPath {   # surowa wartość (bez rozwijania %USERPROFILE%), żeby zapis nie zepsuł cudzych wpisów
  if ($Dry) { return (EnvOr "JARVO_FAKE_USER_PATH" "") }
  return (Get-Item $EnvKey).GetValue("Path", "", [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
}
function SetUserPath([string]$Value) {
  if ($Dry) { Show "PATH użytkownika = $Value"; return }
  New-ItemProperty -Path $EnvKey -Name Path -Value $Value -PropertyType ExpandString -Force | Out-Null
  # zapis do rejestru nie ogłasza zmiany: zapis zmiennej przez .NET ją ogłasza (nowe okna widzą nowy PATH)
  [Environment]::SetEnvironmentVariable("JarvoPathTick", "1", "User")
  [Environment]::SetEnvironmentVariable("JarvoPathTick", $null, "User")
}
function WindowsCommand([string]$Target, [string]$User) {
  $cmd = Join-Path $CmdDir "jarvo.cmd"
  $run = ('wsl.exe -d @D@ -u @U@ --cd ~ -e bash -c "export PATH=${PATH}:${HOME}/.local/bin:${HOME}/jarvo/bin; exec jarvo \"$@\"" jarvo %*' -replace "@D@", $Target) -replace "@U@", $User
  if ($Dry) { Show "jarvo.cmd: $run" }
  WriteText $cmd ("@echo off`r`nrem Jarvo (install.ps1): jarvo in Windows runs jarvo in Linux ($Target).`r`n" + $run + "`r`n") $false
  $now = UserPath
  if (-not (@($now -split ";") -contains $CmdDir)) { SetUserPath ((@($now, $CmdDir) | Where-Object { $_ }) -join ";") }
  if (-not (@($env:Path -split ";") -contains $CmdDir)) { $env:Path = "$env:Path;$CmdDir" }   # to okno też
  Say "Polecenie jarvo w PowerShellu: $cmd"
}

function Uninstall {
  Say "Usuwam dystrybucję $Distro (flota, dane i klucze w niej) i autostart."
  if (-not (Ask "Na pewno?")) { return }
  Wsl --unregister $Distro
  $vbs = StartupVbs
  if ($Dry) { Show "Remove-Item $vbs, $JarvoDir" } else { Remove-Item $vbs, $JarvoDir -Recurse -Force -ErrorAction SilentlyContinue }
  $now = UserPath
  if (@($now -split ";") -contains $CmdDir) { SetUserPath ((@($now -split ";") | Where-Object { $_ -and $_ -ne $CmdDir }) -join ";") }
  Say "Gotowe. Inne dystrybucje WSL zostały bez zmian."
}

# ---------------------------------------------------------------- główny przebieg
function Main {
  Write-Host ""
  Write-Host "  ██████  J A R V O" -ForegroundColor White
  Write-Host "  ██████  from idea to reality." -ForegroundColor Red
  Write-Host ""
  if ($Dry) { Warn "Na sucho (JARVO_DRY_RUN=1): tylko pokazuję, co bym zrobił." }
  if ((EnvOr "JARVO_UNINSTALL" "0") -eq "1") { Uninstall; return }
  CheckSystem
  LoadToken
  $resumed = Test-Path (Join-Path $JarvoDir "po-restarcie")
  if (-not (WslReady) -and $resumed -and -not $Dry) {
    # po restarcie WSL nadal nie działa (np. starszy Windows 10 bez jądra WSL2): aktualizacja WSL, bez kolejnego restartu
    Say "Dokładam aktualizację WSL ( Windows może poprosić o zgodę administratora)…"
    try { Start-Process wsl.exe -ArgumentList "--update" -Verb RunAs -Wait | Out-Null } catch { Warn "Bez zgody administratora nie zaktualizuję WSL." }
    if (-not (WslReady)) { Die "WSL nadal nie działa po restarcie. Otwórz PowerShell jako administrator, wpisz: wsl --install --no-distribution, uruchom ponownie komputer i wklej polecenie instalacji jeszcze raz." }
  }
  if (-not (WslReady)) { InstallWsl; return }
  if (-not $Dry) { Remove-Item (Join-Path $JarvoDir "po-restarcie") -Force -ErrorAction SilentlyContinue }
  Say "WSL: jest"
  if (-not $Dry) {   # nowszy WSL (systemd, sieć); bez internetu nic się nie dzieje
    Say "Sprawdzam aktualizację WSL (zwykle kilka sekund, najwyżej 3 minuty)…"
    if ((WslTimed "--update" 180) -eq -1) { Warn "Aktualizacja WSL trwa za długo: pomijam ją, instalacja idzie dalej." }
  }

  $list = Distros
  $target = ExistingInstall $list
  $temp = $false
  if ($target) {
    Say "Jarvo jest już w dystrybucji ${target}: aktualizuję ją."
    $user = WslOut -d $target -e sh -c "id -un"
    if ($Dry) { $user = "uzytkownik" }
  } else {
    $target = $Distro
    if ($list -notcontains $Distro) { ImportDistro } else { Say "Dystrybucja ${Distro}: jest" }
    ConfigureDistro
    $user = "jarvo"
  }

  # hasło Linuksa w starej dystrybucji to NIE hasło Windowsa: na czas instalacji sudo bez hasła, potem zabieramy
  $drop = "/etc/sudoers.d/zz-jarvo-install"
  if ($target -ne $Distro -and $user -and $user -ne "root") {
    Wsl -d $target -u root -e sh -c "printf '%s ALL=(ALL) NOPASSWD: ALL\n' '$user' > $drop.tmp && chmod 440 $drop.tmp && visudo -cf $drop.tmp >/dev/null && mv $drop.tmp $drop"
    $temp = ($LASTEXITCODE -eq 0)
  }

  $sh = GetInstallFile "install.sh"
  SaveToken
  # zmienne instalatora przechodzą do Linuksa przez WSLENV (klucze nie trafiają do wiersza poleceń)
  $env:JARVO_NO_OPEN = "1"
  if ($Token) { $env:JARVO_TOKEN = $Token }
  $pass = "JARVO_TOKEN/u:JARVO_PROVIDER/u:JARVO_KEY/u:JARVO_YES/u:JARVO_BRANCH/u:JARVO_FORCE/u:JARVO_NO_OPEN/u"
  $env:WSLENV = if ($env:WSLENV) { "$($env:WSLENV):$pass" } else { $pass }
  Say "Uruchamiam instalator w Linuksie ($target, użytkownik $user)…"
  $code = 0
  try {
    Wsl -d $target -u $user --cd "~" -e bash (ToWslPath $sh)
    $code = $LASTEXITCODE
  } finally {
    if ($temp) { Wsl -d $target -u root -e rm -f $drop "$drop.tmp" }
    if (-not $Dry) { Remove-Item $TokenFile, $sh -Force -ErrorAction SilentlyContinue }
  }
  if ($code -ne 0) { Die "Instalacja w Linuksie się nie udała (log wyżej; pełny: ~/jarvo-local/install.log w dystrybucji $target, otwórz: wsl -d $target)." }

  Autostart $target
  WindowsCommand $target $user
  # przeglądarka od razu zalogowana: klucz jednorazowy z floty (jarvo link, 15 min); bez niego zwykła strona logowania
  $open = $Url
  $link = WslOut -d $target -u $user --cd "~" -e bash -c 'jarvo link 2>/dev/null || ~/jarvo/bin/jarvo link'
  if ($link -match '(?m)^(http://localhost:\d+/jarvo#klucz=JRV(-[0-9A-Z]{4}){3})$') { $open = $Matches[1] }
  if ($Dry) { Show "Start-Process $Url" } else { Start-Process $open }
  Write-Host ""
  Say "Gotowe. Dashboard: $Url   (polecenia: jarvo help, w PowerShellu albo w Linuksie: wsl -d $target)"
}

$JarvoFailed = $false
try { Main }
catch {
  $JarvoFailed = $true
  Write-Host ""
  Write-Host ("✗ " + ($_.Exception.Message -replace '^JARVO: ', '')) -ForegroundColor Red
}
finally { $ErrorActionPreference, $ProgressPreference = $JarvoPrefs }
# kod wyjścia tylko przy uruchomieniu z pliku (RunOnce, testy); przy `irm | iex` exit zamknąłby okno PowerShella
if ($JarvoFailed -and $PSCommandPath) { exit 1 }
