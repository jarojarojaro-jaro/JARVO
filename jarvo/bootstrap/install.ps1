# Jarvo natywnie: instalacja jednym poleceniem na Windows 10/11 (docs/NATYWNIE.md, L01 i c3).
#
#   irm https://raw.githubusercontent.com/jarojarojaro-jaro/JARVO/main/jarvo/bootstrap/install.ps1 | iex
#
# Bez administratora, bez WSL, bez Dockera i bez restartu. Skrypt zna tylko dwa pliki dla architektury komputera:
# uv i Pythona 3.13 (python-build-standalone). Adresy i sumy sha256 sa wpisane ponizej, te same co
# w vendor/natywne.lock.json (tests/test_natywne_cli.py pilnuje zgodnosci). Kroki:
#   1. korzen: $env:JARVO_ROOT albo %LOCALAPPDATA%\Jarvo; katalog programu ma sciezke ASCII (przy polskich znakach
#      krotka nazwa 8.3 korzenia, jak jarvo/sciezki.py); stara instalacja z WSL w tym miejscu = odmowa (migracja E12),
#   2. uv i Python do <root>\program\narzedzia\<nazwa>\<wersja>: suma przed rozpakowaniem (Get-FileHash), tar.exe
#      dla tar.gz, Expand-Archive dla zip; znacznik .jarvo-suma jak w jarvo/pobieracz.py, wiec instalator
#      w Pythonie niczego nie pobiera drugi raz,
#   3. kod Jarva: ref ($env:JARVO_REF albo main) -> SHA przez API GitHuba, archiwum tego commitu do
#      <root>\program\app\<sha12> (nowa wersja obok starej),
#   4. python -I -X utf8 <app>\jarvo\start.py instaluj: dalej instalator w Pythonie (jarvo/instalator.py).
# Drugie uruchomienie niczego nie psuje: sprawdzone pliki zostaja, gotowe kroki sa pomijane.
#
# Zmienne (opcjonalne): JARVO_ROOT, JARVO_REF (galaz, tag albo pelny SHA), JARVO_TOKEN (klucz do prywatnej kopii
# repo: idzie tylko w naglowku do api.github.com, nigdy na ekran), JARVO_NO_AUTOSTART=1, JARVO_WEB_LOKALNIE=1,
# JARVO_BEZ_PATH=1 (polecenie jarvo tylko w <root>\bin, PATH uzytkownika bez zmian: proby),
# JARVO_DRY_RUN=1 (tylko plan, bez pobierania i zapisu; JARVO_FAKE_ARCH udaje wtedy architekture).
# Do etapu E13 to osobny adres: domyslny zostaje stary install.ps1 z katalogu glownego repo.
#
# Plik tylko ASCII i bez BOM: Windows PowerShell 5.1 czyta skrypt bez BOM w stronie kodowej ANSI, a `irm | iex`
# zostawia BOM w tekscie. Calosc dziala w bloku `& { }`: funkcje i ustawienia (ErrorActionPreference) nie zostaja
# w sesji uzytkownika po `irm | iex`.

& {
  $ErrorActionPreference = 'Stop'
  $ProgressPreference = 'SilentlyContinue'      # pasek Invoke-WebRequest spowalnia pobieranie kilkukrotnie
  try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
  } catch {
    Write-Verbose "TLS 1.2: $_"
  }

  $JarvoRepo = 'jarojarojaro-jaro/JARVO'
  $JarvoNaSucho = $env:JARVO_DRY_RUN -eq '1'
  # vendor/natywne.lock.json: uv 0.12.13 i python313 3.13.17+20261021. Windows ARM64: uv natywny, Python x64
  # w emulacji (decyzja I27: cryptography 50 nie ma kola win_arm64).
  $JarvoPliki = @(
    @{ platforma = 'windows-x64'; nazwa = 'uv'; katalog = '0.12.13'; format = 'zip'; poziom = 0; rozmiar = 17612025
       url = 'https://github.com/astral-sh/uv/releases/download/0.12.13/uv-x86_64-pc-windows-msvc.zip'
       sha256 = 'a86c9dc7bad9b03f388583b7187c05fe9951c2e0d392217e8fd43d97787f6ec2' }
    @{ platforma = 'windows-x64'; nazwa = 'python313'; katalog = '3.13.17'; format = 'tar.gz'; poziom = 1; rozmiar = 21986637
       url = 'https://github.com/astral-sh/python-build-standalone/releases/download/20261021/cpython-3.13.17%2B20261021-x86_64-pc-windows-msvc-install_only_stripped.tar.gz'
       sha256 = '56cde3b1a1dcc36576753cb408ee0c3568d211baafa0eee40423adc147c480f2' }
    @{ platforma = 'windows-arm64'; nazwa = 'uv'; katalog = '0.12.13'; format = 'zip'; poziom = 0; rozmiar = 18817671
       url = 'https://github.com/astral-sh/uv/releases/download/0.12.13/uv-aarch64-pc-windows-msvc.zip'
       sha256 = '1efb2654b06e7063d4ac1fc9d49a9bda9a6704d82f035b589a2751a592f14151' }
    @{ platforma = 'windows-arm64'; nazwa = 'python313'; katalog = '3.13.17'; format = 'tar.gz'; poziom = 1; rozmiar = 21986637
       url = 'https://github.com/astral-sh/python-build-standalone/releases/download/20261021/cpython-3.13.17%2B20261021-x86_64-pc-windows-msvc-install_only_stripped.tar.gz'
       sha256 = '56cde3b1a1dcc36576753cb408ee0c3568d211baafa0eee40423adc147c480f2' }
  )

  function JarvoKrok([string]$Tekst) { Write-Host "[jarvo] $Tekst" }
  function JarvoPlan([string]$Tekst) { Write-Host "  (na sucho) $Tekst" -ForegroundColor DarkGray }
  function JarvoBlad([string]$Tekst) { throw "JARVO: $Tekst" }

  # Program spoza PowerShella. W Windows PowerShell 5.1 wiersz na stderr przy przekierowaniu staje sie bledem,
  # a przy ErrorActionPreference=Stop przerywa skrypt (curl.exe pisze tam pasek postepu): decyduje kod wyjscia.
  # Wywolanie bez przechwycenia, wiec program pisze wprost do konsoli (pasek, kolory, polskie znaki).
  function JarvoProgram([string]$Plik, [string[]]$Argumenty, [string]$Blad) {
    $stary = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
      & $Plik @Argumenty
      $kod = $LASTEXITCODE
    } finally {
      $ErrorActionPreference = $stary
    }
    if ($kod -ne 0) { JarvoBlad "$Blad (kod $kod)" }
  }

  function JarvoSuma([string]$Plik) {
    return (Get-FileHash -LiteralPath $Plik -Algorithm SHA256).Hash.ToLowerInvariant()
  }

  function JarvoArchitektura {
    if ($JarvoNaSucho -and $env:JARVO_FAKE_ARCH) { return [string]$env:JARVO_FAKE_ARCH }
    try {
      # wartosc systemowa = architektura procesora, takze z procesu x64 w emulacji na ARM64
      $klucz = 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment'
      $a = (Get-ItemProperty -LiteralPath $klucz -Name PROCESSOR_ARCHITECTURE -ErrorAction Stop).PROCESSOR_ARCHITECTURE
      if ($a) { return [string]$a }
    } catch {
      Write-Verbose "architektura z rejestru: $_"
    }
    if ($env:PROCESSOR_ARCHITEW6432) { return [string]$env:PROCESSOR_ARCHITEW6432 }
    return [string]$env:PROCESSOR_ARCHITECTURE
  }

  function JarvoPlatforma([string]$Architektura) {
    switch ($Architektura.ToUpperInvariant()) {
      'AMD64' { return 'windows-x64' }
      'ARM64' { return 'windows-arm64' }
    }
    JarvoBlad "Jarvo potrzebuje 64-bitowego Windowsa 10 albo 11 (x64 albo ARM64), a ten komputer ma architekture '$Architektura'."
  }

  function JarvoKorzen {
    $r = $env:JARVO_ROOT
    if (-not $r) {
      if (-not $env:LOCALAPPDATA) { JarvoBlad 'brak zmiennej LOCALAPPDATA: ustaw JARVO_ROOT na katalog instalacji.' }
      $r = Join-Path $env:LOCALAPPDATA 'Jarvo'
    }
    return [IO.Path]::GetFullPath($r)
  }

  # <program> jak w jarvo/sciezki.py: sciezka ASCII (espeak-ng, OpenCV i Tesseract maja waskie API sciezek)
  function JarvoKatalogProgramu([string]$Korzen) {
    $p = Join-Path $Korzen 'program'
    if ($p -notmatch '[^\x00-\x7F]') { return $p }
    if ($JarvoNaSucho) { return $p }
    New-Item -ItemType Directory -Force -Path $Korzen | Out-Null
    $krotki = (New-Object -ComObject Scripting.FileSystemObject).GetFolder($Korzen).ShortPath
    $p = Join-Path $krotki 'program'
    if ($p -match '[^\x00-\x7F]') {
      JarvoBlad "sciezka $Korzen ma znaki spoza ASCII, a system nie podal krotkiej nazwy. Ustaw JARVO_ROOT na katalog z samymi literami ASCII (np. C:\Jarvo) i uruchom polecenie ponownie."
    }
    return $p
  }

  function JarvoStaraInstalacja([string]$Korzen) {
    $cmd = Join-Path $Korzen 'bin\jarvo.cmd'
    $stara = Test-Path -LiteralPath (Join-Path $Korzen 'wsl')
    if (-not $stara -and (Test-Path -LiteralPath $cmd)) {
      $stara = -not ((Get-Content -LiteralPath $cmd -Raw) -match 'Jarvo natywnie')
    }
    if ($stara) {
      JarvoBlad ("w $Korzen jest stara instalacja Jarvo (WSL i Docker). Migracja (jarvo migruj) przyjdzie w etapie E12; " +
                 "do tego czasu zainstaluj Jarvo natywnie w osobnym katalogu, np.: `$env:JARVO_ROOT = 'D:\Jarvo'; " +
                 "irm https://raw.githubusercontent.com/$JarvoRepo/main/jarvo/bootstrap/install.ps1 | iex")
    }
  }

  # Pobranie z suma sprawdzana przed uzyciem; plik juz obecny z dobra suma = bez sieci
  function JarvoPobierz([string]$Url, [string]$Cel, [string]$Sha256) {
    if ((Test-Path -LiteralPath $Cel) -and ((JarvoSuma $Cel) -eq $Sha256)) { return }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Cel) | Out-Null
    $czesc = "$Cel.czesc"
    Remove-Item -LiteralPath $czesc -Force -ErrorAction SilentlyContinue
    JarvoSciagnij $Url $czesc
    $suma = JarvoSuma $czesc
    if ($suma -ne $Sha256) {
      Remove-Item -LiteralPath $czesc -Force
      JarvoBlad ("suma sha256 pliku $Url sie nie zgadza (jest $($suma.Substring(0, 12))..., ma byc " +
                 "$($Sha256.Substring(0, 12))...). Plik usuniety, niczego nie uruchomilem.")
    }
    Move-Item -LiteralPath $czesc -Destination $Cel -Force
  }

  # curl.exe (Windows 10 1803+) z paskiem postepu; bez niego Invoke-WebRequest
  function JarvoSciagnij([string]$Url, [string]$Cel) {
    $curl = Join-Path $env:SystemRoot 'System32\curl.exe'
    if (Test-Path -LiteralPath $curl) {
      JarvoProgram $curl @('-fL', '--retry', '3', '--retry-delay', '2', '--progress-bar', '-o', $Cel, $Url) "nie udalo sie pobrac $Url (siec?). Uruchom polecenie ponownie"
    } else {
      Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $Cel
    }
  }

  function JarvoKatalogNarzedzia([string]$Program, $Wpis) {
    return Join-Path $Program ("narzedzia\{0}\{1}" -f $Wpis.nazwa, $Wpis.katalog)
  }

  # Narzedzie do <program>\narzedzia\<nazwa>\<wersja>: rozpakowanie do <wersja>.new, znacznik z suma, zmiana nazwy
  function JarvoNarzedzie($Wpis, [string]$Cel, [string]$Pobrane) {
    $znacznik = Join-Path $Cel '.jarvo-suma'
    if ((Test-Path -LiteralPath $znacznik) -and ((Get-Content -LiteralPath $znacznik -Raw).Trim() -eq $Wpis.sha256)) {
      JarvoKrok "$($Wpis.nazwa) $($Wpis.katalog): juz jest"
      return
    }
    $plik = $Wpis.url.Substring($Wpis.url.LastIndexOf('/') + 1)
    $archiwum = Join-Path $Pobrane ('{0}-{1}' -f $Wpis.sha256.Substring(0, 16), $plik)
    if ($JarvoNaSucho) {
      JarvoPlan "pobierz $($Wpis.url)"
      JarvoPlan "  sha256 $($Wpis.sha256) -> $archiwum"
      JarvoPlan "  rozpakuj ($($Wpis.format), poziom $($Wpis.poziom)) -> $Cel"
      return
    }
    JarvoKrok "pobieram $($Wpis.nazwa) $($Wpis.katalog) ($([math]::Round($Wpis.rozmiar / 1MB)) MB)"
    JarvoPobierz $Wpis.url $archiwum $Wpis.sha256
    $nowy = "$Cel.new"
    if (Test-Path -LiteralPath $nowy) { Remove-Item -LiteralPath $nowy -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $nowy | Out-Null
    if ($Wpis.format -eq 'zip') {
      Expand-Archive -LiteralPath $archiwum -DestinationPath $nowy -Force
    } else {
      $tar = Join-Path $env:SystemRoot 'System32\tar.exe'
      JarvoProgram $tar @('-xzf', $archiwum, '-C', $nowy, "--strip-components=$($Wpis.poziom)") "nie udalo sie rozpakowac $archiwum"
    }
    [IO.File]::WriteAllText((Join-Path $nowy '.jarvo-suma'), "$($Wpis.sha256)`n")
    if (Test-Path -LiteralPath $Cel) { Remove-Item -LiteralPath $Cel -Recurse -Force }
    Move-Item -LiteralPath $nowy -Destination $Cel
    JarvoKrok "$($Wpis.nazwa) $($Wpis.katalog): $Cel"
  }

  function JarvoNaglowki {
    $h = @{ 'User-Agent' = 'jarvo-instalator' }
    if ($env:JARVO_TOKEN) { $h['Authorization'] = 'Bearer ' + $env:JARVO_TOKEN }
    return $h
  }

  # ref -> pelny SHA (Accept: application/vnd.github.sha zwraca sam SHA, bez JSON)
  function JarvoWersja([string]$Ref) {
    if ($Ref -match '^[0-9a-fA-F]{40}$') { return $Ref.ToLowerInvariant() }
    $adres = "https://api.github.com/repos/$JarvoRepo/commits/$Ref"
    if ($JarvoNaSucho) {
      JarvoPlan ("GET $adres" + $(if ($env:JARVO_TOKEN) { ' (Authorization: Bearer <ukryty>)' } else { '' }))
      return $null
    }
    $h = JarvoNaglowki
    $h['Accept'] = 'application/vnd.github.sha'
    try {
      $odp = Invoke-WebRequest -UseBasicParsing -Uri $adres -Headers $h
    } catch {
      JarvoBlad "nie znalazlem wersji '$Ref' w $JarvoRepo ($($_.Exception.Message)). Prywatna kopia repo: ustaw JARVO_TOKEN."
    }
    $tresc = $odp.Content
    if ($tresc -is [byte[]]) { $tresc = [Text.Encoding]::ASCII.GetString($tresc) }
    $sha = ([string]$tresc).Trim().ToLowerInvariant()
    if ($sha -notmatch '^[0-9a-f]{40}$') { JarvoBlad "API GitHuba nie podalo SHA dla '$Ref'." }
    return $sha
  }

  # Archiwum kodu z commitu $Sha. Prywatna kopia: API przekierowuje na jednorazowy adres codeload, a .NET nie
  # przenosi naglowka Authorization na inny adres po przekierowaniu, wiec klucz trafia tylko do api.github.com.
  function JarvoAdresKodu([string]$Sha) {
    if ($env:JARVO_TOKEN) { return "https://api.github.com/repos/$JarvoRepo/tarball/$Sha" }
    return "https://codeload.github.com/$JarvoRepo/tar.gz/$Sha"
  }

  # Kod Jarva z commitu $Sha do $Cel (bez .git); .jarvo-wersja = pelny SHA dla instalatora i `jarvo --wersja`
  function JarvoKod([string]$Sha, [string]$Cel, [string]$Pobrane) {
    $archiwum = Join-Path $Pobrane "jarvo-$Sha.tar.gz"
    $adres = JarvoAdresKodu $Sha
    if ($JarvoNaSucho) {
      JarvoPlan ("pobierz $adres" + $(if ($env:JARVO_TOKEN) { ' (Authorization: Bearer <ukryty>)' } else { '' }))
      JarvoPlan "  rozpakuj (tar.gz, poziom 1) -> $Cel"
      return
    }
    if (Test-Path -LiteralPath (Join-Path $Cel 'jarvo\start.py')) {
      JarvoKrok "kod Jarva $($Sha.Substring(0, 12)): juz jest"
      return
    }
    JarvoKrok "pobieram kod Jarva $($Sha.Substring(0, 12))"
    New-Item -ItemType Directory -Force -Path $Pobrane | Out-Null
    Remove-Item -LiteralPath $archiwum -Force -ErrorAction SilentlyContinue
    if ($env:JARVO_TOKEN) {
      Invoke-WebRequest -UseBasicParsing -Uri $adres -Headers (JarvoNaglowki) -OutFile $archiwum
    } else {
      JarvoSciagnij $adres $archiwum
    }
    $nowy = "$Cel.new"
    if (Test-Path -LiteralPath $nowy) { Remove-Item -LiteralPath $nowy -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $nowy | Out-Null
    $tar = Join-Path $env:SystemRoot 'System32\tar.exe'
    JarvoProgram $tar @('-xzf', $archiwum, '-C', $nowy, '--strip-components=1') "nie udalo sie rozpakowac kodu Jarva"
    if (-not (Test-Path -LiteralPath (Join-Path $nowy 'jarvo\start.py'))) {
      JarvoBlad "archiwum $adres nie ma jarvo\start.py (zly ref? ustaw JARVO_REF)."
    }
    [IO.File]::WriteAllText((Join-Path $nowy '.jarvo-wersja'), "$Sha`n")
    # niepelny katalog po przerwanej probie (bez jarvo\start.py): Move-Item wsunalby nowy do srodka
    if (Test-Path -LiteralPath $Cel) { Remove-Item -LiteralPath $Cel -Recurse -Force }
    Move-Item -LiteralPath $nowy -Destination $Cel
    Remove-Item -LiteralPath $archiwum -Force -ErrorAction SilentlyContinue
  }

  function JarvoInstaluj {
    JarvoKrok 'Jarvo natywnie: instalacja bez WSL i bez Dockera'
    $platforma = JarvoPlatforma (JarvoArchitektura)
    $korzen = JarvoKorzen
    $program = JarvoKatalogProgramu $korzen
    $pobrane = Join-Path $korzen 'cache\pobrane'
    JarvoKrok "platforma $platforma, katalog $korzen"
    JarvoStaraInstalacja $korzen
    $python = $null
    foreach ($wpis in @($JarvoPliki | Where-Object { $_.platforma -eq $platforma })) {
      $cel = JarvoKatalogNarzedzia $program $wpis
      JarvoNarzedzie $wpis $cel $pobrane
      if ($wpis.nazwa -eq 'python313') { $python = Join-Path $cel 'python.exe' }
    }
    $ref = $env:JARVO_REF
    if (-not $ref) { $ref = 'main' }
    $sha = JarvoWersja $ref
    if (-not $sha) { $sha = 'SHA-z-' + ($ref -replace '[^\w.-]', '_') }     # tylko na sucho: SHA zna dopiero API
    $app = Join-Path $program ('app\' + $sha.Substring(0, [math]::Min(12, $sha.Length)))
    JarvoKod $sha $app $pobrane
    $argumenty = @('-I', '-X', 'utf8', (Join-Path $app 'jarvo\start.py'), 'instaluj')
    if ($env:JARVO_NO_AUTOSTART -eq '1') { $argumenty += '--bez-autostartu' }
    if ($env:JARVO_WEB_LOKALNIE -eq '1') { $argumenty += '--web-lokalnie' }
    if ($env:JARVO_BEZ_PATH -eq '1') { $argumenty += '--bez-path' }
    if ($JarvoNaSucho) {
      JarvoPlan ("$python " + ($argumenty -join ' '))
      return
    }
    JarvoProgram $python $argumenty 'instalator Jarva zakonczyl sie bledem (opis wyzej)'
    $bin = Join-Path $korzen 'bin'
    if ($env:JARVO_BEZ_PATH -eq '1') {
      JarvoKrok "Gotowe. Polecenie: $bin\jarvo.cmd (PATH bez zmian: JARVO_BEZ_PATH=1)."
      return
    }
    if (-not (@($env:Path -split ';') -contains $bin)) { $env:Path = "$env:Path;$bin" }   # to okno tez
    JarvoKrok 'Gotowe. Polecenie jarvo dziala w tym oknie i w kazdym nowym (jarvo chat, jarvo panel, jarvo status).'
  }

  JarvoInstaluj
}
