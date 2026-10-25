# Jarvo dla Windowsa: stary, krotszy adres instalacji. Instalacja jest natywna (bez WSL, Dockera i administratora):
# ten plik pobiera jarvo/bootstrap/install.ps1 z tego samego refu (JARVO_REF, domyslnie main) i uruchamia go.
#
#   irm https://raw.githubusercontent.com/jarojarojaro-jaro/JARVO/main/install.ps1 | iex   (albo jarvo.pl/install.ps1)
#
# Stara instalacja z WSL i Dockerem jest wykrywana i przenoszona (jarvo migruj, zgoda przed kazda zmiana); opis
# w docs/INSTALER.md. Zmienne jak w bootstrapie (JARVO_ROOT, JARVO_REF, JARVO_TOKEN, JARVO_YES, ...).
# Plik tylko ASCII i bez BOM (Windows PowerShell 5.1 czyta skrypt bez BOM w stronie kodowej ANSI).

& {
  $ErrorActionPreference = 'Stop'
  try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
  } catch {
    Write-Verbose "TLS 1.2: $_"
  }
  $ref = $env:JARVO_REF
  if (-not $ref) { $ref = 'main' }
  $adres = "https://raw.githubusercontent.com/jarojarojaro-jaro/JARVO/$ref/jarvo/bootstrap/install.ps1"
  $naglowki = @{}
  if ($env:JARVO_TOKEN) { $naglowki['Authorization'] = "Bearer $($env:JARVO_TOKEN)" }   # prywatna kopia repo
  try {
    $skrypt = Invoke-RestMethod -Uri $adres -Headers $naglowki -UseBasicParsing
  } catch {
    throw "JARVO: nie pobralem instalatora z $adres ($($_.Exception.Message)). Sprawdz siec i uruchom polecenie ponownie."
  }
  Invoke-Expression $skrypt
}
