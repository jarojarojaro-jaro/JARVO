---
name: wideo-ai
description: "Ujęcia z AI: obraz→wideo, prompt ruchu, spójność, koszt."
version: 1.0.0
author: TARS
license: MIT
metadata:
  hermes:
    tags: [video, ai, video-generation, image-to-video, openrouter]
    related_skills: [krotki-film, dobor-ujec, material-stock, ai-presenter-video]
  tars:
    agent: tars-wideo
    autonomy: A1
    reviewed: "2026-09-28"
---

# Ujęcia z AI

Narzędzia Hermesa: `video_generate` (wideo z tekstu albo z obrazu; katalog modeli OpenRouter na żywo)
i `image_generate` (klatka startowa). Generacje kosztują: limit z karty (domyślnie 3 klipy wideo, 8 obrazów).

## Kiedy użyć
- Scena, której nie ma w stocku (konkretny styl marki, fantazja, produkt w nietypowej scenie), a użytkownik nie ma materiału.
- Ożywienie zdjęcia produktu albo ilustracji marki (obraz → wideo).

## Kiedy NIE używać
- Stock ma dobre ujęcie (darmowe, szybsze): najpierw `material-stock`.
- Tekst, logo, cena, interfejs: AI zniekształca litery → tekst przez `tekst_ekranowy`/napisy, animacje UI przez `film-z-kodu`.
- Realna osoba, głos realnej osoby, cudza marka: nigdy. Prezenter AI tylko z autoryzowanego obrazu (`ai-presenter-video`).

## Kroki
1. **Obraz startowy najpierw** (tańszy i sterowalny): `image_generate` z promptem
   `[obiekt] + [kadr] + [światło] + [styl] + [paleta marki] + [proporcje formatu], bez tekstu, bez logo`.
   Oceń (vision): kompozycja pod 9:16, brak artefaktów. Zapis: `out/wideo/src/ai-<scena>.png`.
2. **Ruch:** `video_generate` z obrazem startowym i promptem ruchu: jeden ruch kamery + jeden ruch obiektu,
   np. „slow dolly in, steam rising from the cup, soft morning light, no text”. Czas: 4–6 s na scenę;
   dłuższe sceny składaj z 2 ujęć albo `"ruch": "zoom"` na samym obrazie (darmowe).
3. **Spójność serii:** ten sam opis stylu i palety w każdym prompcie (`out/wideo/src/STYL-AI.md`), ta sama proporcja,
   referencja z poprzedniej sceny, jeśli model ją przyjmuje.
4. **Kontrola** (`dobor-ujec`): `kadry.py arkusz` → vision: deformacje (dłonie, twarze, fizyka), migotanie, tekst-krzaki.
   Wadliwe odrzucasz; nie „ratujesz” napisem.
5. **Do planu:** `"ujecie": {"plik": "out/wideo/src/ai-<scena>.mp4"}` (film.py dopasuje kadr i długość, pętli nie ukryje:
   klip krótszy niż scena = skróć scenę albo dodaj drugie ujęcie).
6. **Rejestr** `out/wideo/src/generacje.jsonl`: scena, narzędzie, model, prompt, koszt/liczba, wynik (użyte/odrzucone).
   W RAPORT: które sceny są z AI (część platform wymaga oznaczenia treści AI).

## Wyjścia
- klipy i obrazy w `out/wideo/src/`, `generacje.jsonl`, `STYL-AI.md`, oznaczenie scen AI w RAPORT.md.

## Definition of Done
- [ ] limit generacji z karty zachowany; każda generacja w rejestrze z modelem i promptem,
- [ ] zero deformacji i tekstu-krzaków w użytych ujęciach (arkusz obejrzany),
- [ ] sceny AI spójne stylem; oznaczone w raporcie.
