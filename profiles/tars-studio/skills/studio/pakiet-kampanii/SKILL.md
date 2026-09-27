---
name: pakiet-kampanii
description: "Kampania: koncepcja, posty, grafiki, wideo, kalendarz."
version: 1.0.0
author: TARS
license: MIT
metadata:
  hermes:
    tags: [marketing, campaign, launch, content-calendar]
    related_skills: [launch, content-strategy, social, social-media-content-calendar, grafika-social, film-z-kodu, copy-pl]
  tars:
    agent: tars-studio
    autonomy: A1
    reviewed: "2026-09-26"
---

# Pakiet kampanii

## Kroki
1. **Kontekst:** brand kit + `product-marketing.md` → `.agents/product-marketing.md` w workspace; raport Sherlocka
   (odbiorcy, konkurencja, głos klienta), jeśli jest.
2. **Koncepcja** (`out/KONCEPCJA.md`, zasady z `launch` i `content-strategy`): cel kampanii (miara), odbiorca, jedna
   główna obietnica, 3 filary treści, kanały, oś czasu. 2 warianty koncepcji z rekomendacją, jeśli karta tego nie przesądza.
3. **Treści:** posty (`copy-pl`, `social`), grafiki (`grafika-social`), wideo (`film-z-kodu`), opcjonalnie e-mail (`emails`)
   i reklamy (`ad-creative`), zgodnie z listą z karty.
4. **Kalendarz** (`social-media-content-calendar`): `out/kalendarz.csv` (data, godzina, platforma, typ, plik, tekst, CTA, status=szkic).
5. **Kontrola:** `check_media.py out/ --auto`, limity tekstów, spójność wizualna (obejrzyj całość obok siebie).
6. **INDEX i RAPORT:** `out/INDEX.md` (każdy plik: do czego i gdzie), `out/RAPORT.md` (koncepcja w 5 zdaniach, samokontrola DoD,
   koszty generacji AI, co wymaga decyzji: np. publikacja, budżet reklam).

## DoD (domyślne)
- [ ] koncepcja z celem i miarą,
- [ ] wszystkie elementy z karty w formatach platform,
- [ ] kalendarz ze statusem „szkic” (nic nie zaplanowane w narzędziu publikacji bez zgody),
- [ ] zgodność z marką, zero obietnic bez dowodu.
