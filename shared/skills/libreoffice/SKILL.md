---
name: libreoffice
description: "Arkusz, dokument, prezentacja w LibreOffice: najpierw soffice bez okna (CSV → XLSX, PDF), okno na pulpicie do sprawdzenia."
version: 1.0.0
author: "Jarvo (program: LibreOffice, MPL-2.0)"
license: MIT
metadata:
  hermes:
    tags: [libreoffice, calc, writer, spreadsheet, xlsx, pdf, csv, soffice, desktop]
  jarvo:
    autonomy: A1
    reviewed: "2026-11-27"
---

# LibreOffice

LibreOffice jest w systemie (`soffice`); dane układasz skryptem, a program zamienia je na plik bez okna.

## Najpierw bez okna
```bash
P="-env:UserInstallation=file://$PWD/.lo-profil"     # osobny profil: działa także przy otwartym oknie Calc
# tabela: CSV w UTF-8 (już posortowany skryptem, np. Python csv + sorted po cenie) → XLSX → PDF
soffice $P --headless --infilter="CSV:44,34,76,1" --convert-to xlsx --outdir out tabela.csv
soffice $P --headless --convert-to pdf --outdir out out/tabela.xlsx
soffice $P --headless --convert-to docx --outdir out raport.html   # dokument Word z HTML
```
- Sortowanie, sumy i formaty liczb robisz w danych przed konwersją albo przez `openpyxl` na gotowym XLSX.
- Formuły w CSV (`=SUMA(B2:B9)`) Calc liczy przy otwarciu; w XLSX wpisujesz je po angielsku (`=SUM(B2:B9)`).
- Wynik sprawdzasz odczytem pliku (`openpyxl`, `pdftotext`), zanim go oddasz.

## Okno (pulpit)
- `pulpit` akcja `uruchom` z `program: calc` (albo writer, impress) i `argumenty: [pełna ścieżka pliku]`.
- Komórki Calc nie są na liście elementów; do komórki idziesz polem nazwy (ctrl+shift+F5): wpisz `B2`, Enter.
- Sortowanie: zaznacz zakres (Pole nazwy `A1:F20`), menu Dane → Sortuj, kolumna i kierunek w oknie, OK.
- Zapis jako XLSX: ctrl+shift+s, pełna ścieżka z `.xlsx` w nazwie, Enter, w pytaniu o format „Użyj formatu Excel”.
- PDF: Plik → Eksportuj do PDF, Eksportuj, pełna ścieżka, Enter.
- Wyjście: ctrl+q, przy pytaniu o zapis „Nie zapisuj” albo „Zapisz” według zadania.
