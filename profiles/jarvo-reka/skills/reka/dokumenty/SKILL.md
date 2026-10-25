---
name: dokumenty
description: "Dokumenty: konwersje MD/DOCX/PDF/HTML, OCR, operacje na PDF."
version: 1.1.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [documents, pdf, docx, ocr, conversion]
    related_skills: [zlozenie-pakietu]
  jarvo:
    agent: jarvo-reka
    autonomy: A1
    reviewed: "2026-10-25"
---

# Dokumenty i konwersje

| Zadanie | Narzędzie | Przykład |
|---|---|---|
| MD → DOCX | pandoc | `pandoc in.md -o out.docx --reference-doc=<szablon.docx opcjonalnie>` |
| MD/HTML → PDF (ładny) | pandoc + Chromium (lokalnie) | `@@PY@@ "$HERMES_HOME/scripts/to_pdf.py" in.md out.pdf` |
| DOCX/ODT → PDF | LibreOffice, a bez niego pandoc + Chromium | `@@PY@@ "$HERMES_HOME/scripts/to_pdf.py" in.docx out.pdf` |
| XLSX/PPTX → PDF | tylko LibreOffice (obraz: dodatek `office`; natywnie LibreOffice z tego komputera) | `@@PY@@ "$HERMES_HOME/scripts/to_pdf.py" in.xlsx out.pdf` |
| PDF/DOCX → Markdown (do analizy) | `read_file` Hermesa, pandoc (DOCX); Docling, jeśli jest | `pandoc in.docx -t gfm -o out.md` |
| skan → tekst | skill `odczyt-ekranu` (Indra OCR, Tesseract) | `@@PY@@ "$HERMES_HOME/skills/pliki/odczyt-ekranu/scripts/ocr.py" skan.pdf --format md` |
| skan → PDF z tekstem | OCRmyPDF (jest w obrazie; w instalacji natywnej jeszcze nie: oddaj tekst z `odczyt-ekranu`) | `ocrmypdf -l pol+eng skan.pdf out.pdf` |
| łączenie/dzielenie/obracanie PDF | qpdf | `qpdf --empty --pages a.pdf b.pdf -- out.pdf` |
| tabele z PDF | Docling (dodatek `docling`); bez niego vision na podglądzie strony | |

## Zasady
- Narzędzia opcjonalne sprawdź przed użyciem: LibreOffice przez
  `@@PY@@ "$HERMES_HOME/skills/pliki/konwersja-plikow/scripts/konwertuj.py" --formaty` (silnik `libreoffice`; natywnie
  LibreOffice zwykle nie jest w PATH, więc `command -v soffice` go nie pokaże), Docling i OCRmyPDF przez
  `command -v docling ocrmypdf`. Brak = użyj zamiennika z tabeli; nie instaluj niczego sam.
- Oryginały zostają nietknięte; wyniki w `out/`.
- Po konwersji **otwórz wynik** (`read_file`, podgląd strony PDF przez vision), bo konwersje gubią tabele i polskie znaki.
- Dokumenty z danymi osobowymi: tylko w workspace, nigdzie nie wysyłasz.
