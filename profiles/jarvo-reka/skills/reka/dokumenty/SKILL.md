---
name: dokumenty
description: "Dokumenty: konwersje MD/DOCX/PDF/HTML, OCR, operacje na PDF."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [documents, pdf, docx, ocr, conversion]
    related_skills: [zlozenie-pakietu]
  jarvo:
    agent: jarvo-reka
    autonomy: A1
    reviewed: "2026-09-26"
---

# Dokumenty i konwersje

| Zadanie | Narzędzie | Przykład |
|---|---|---|
| MD → DOCX | pandoc | `pandoc in.md -o out.docx --reference-doc=<szablon.docx opcjonalnie>` |
| MD/HTML → PDF (ładny) | pandoc + Chromium (lokalnie) | `python3 $HERMES_HOME/scripts/to_pdf.py in.md out.pdf` |
| DOCX/ODT → PDF | LibreOffice, a bez niego pandoc + Chromium | `python3 $HERMES_HOME/scripts/to_pdf.py in.docx out.pdf` |
| XLSX/PPTX → PDF | tylko LibreOffice (dodatek `office`) | `python3 $HERMES_HOME/scripts/to_pdf.py in.xlsx out.pdf` |
| PDF/DOCX → Markdown (do analizy) | `read_file` Hermesa, pandoc (DOCX); Docling, jeśli jest | `pandoc in.docx -t gfm -o out.md` |
| skan → PDF z tekstem | OCRmyPDF | `ocrmypdf -l pol+eng skan.pdf out.pdf` |
| łączenie/dzielenie/obracanie PDF | qpdf | `qpdf --empty --pages a.pdf b.pdf -- out.pdf` |
| tabele z PDF | Docling (dodatek `docling`); bez niego vision na podglądzie strony | |

## Zasady
- Narzędzia opcjonalne (Docling, LibreOffice) sprawdź przed użyciem (`command -v docling soffice`). Brak = użyj
  zamiennika z tabeli; nie instaluj niczego sam.
- Oryginały zostają nietknięte; wyniki w `out/`.
- Po konwersji **otwórz wynik** (`read_file`, podgląd strony PDF przez vision), bo konwersje gubią tabele i polskie znaki.
- Dokumenty z danymi osobowymi: tylko w workspace, nigdzie nie wysyłasz.
