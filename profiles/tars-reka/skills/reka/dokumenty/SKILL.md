---
name: dokumenty
description: "Dokumenty: konwersje MD/DOCX/PDF/HTML, OCR, operacje na PDF."
version: 1.0.0
author: TARS
license: MIT
metadata:
  hermes:
    tags: [documents, pdf, docx, ocr, conversion]
    related_skills: [zlozenie-pakietu]
  tars:
    agent: tars-reka
    autonomy: A1
    reviewed: 2026-09-26
---

# Dokumenty i konwersje

| Zadanie | Narzędzie | Przykład |
|---|---|---|
| MD → DOCX | pandoc | `pandoc in.md -o out.docx --reference-doc=<szablon.docx opcjonalnie>` |
| MD/HTML → PDF (ładny) | Gotenberg (sidecar) | `python3 $HERMES_HOME/scripts/to_pdf.py in.md out.pdf` |
| DOCX/XLSX/PPTX → PDF | Gotenberg (LibreOffice) | `python3 $HERMES_HOME/scripts/to_pdf.py in.docx out.pdf` |
| PDF/DOCX → Markdown (do analizy) | Docling / `read_file` Hermesa | `docling in.pdf --to md --output out/` |
| skan → PDF z tekstem | OCRmyPDF | `ocrmypdf -l pol+eng skan.pdf out.pdf` |
| łączenie/dzielenie/obracanie PDF | qpdf | `qpdf --empty --pages a.pdf b.pdf -- out.pdf` |
| tabele z PDF | Docling (tabele → CSV/MD) | |

## Zasady
- Oryginały zostają nietknięte; wyniki w `out/`.
- Po konwersji **otwórz wynik** (`read_file`, podgląd strony PDF przez vision), bo konwersje gubią tabele i polskie znaki.
- Dokumenty z danymi osobowymi: tylko w workspace, nigdzie nie wysyłasz.
