# Reguły PSScriptAnalyzer dla install.ps1 (make dev-pwsh; tests/test_install_ps1.py, CI installer.yml).
@{
  Severity     = @('Error', 'Warning')
  ExcludeRules = @(
    # instalator w konsoli: kolorowe komunikaty dla człowieka, nic nie przechwytuje wyjścia
    'PSAvoidUsingWriteHost',
    # plik bez BOM, bo `irm | iex` w Windows PowerShell 5.1 zostawia BOM w tekście i psuje pierwszą linię;
    # kopię do uruchomienia po restarcie instalator zapisuje z BOM sam
    'PSUseBOMForUnicodeEncodedFile',
    # klucz dostępu na czas restartu: ConvertFrom-SecureString szyfruje go DPAPI dla tego użytkownika Windows
    'PSAvoidUsingConvertToSecureStringWithPlainText'
  )
}
