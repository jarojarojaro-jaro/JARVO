---
name: krotki-film
description: "Krótki film z tematu: plan, ujęcia, lektor, napisy, montaż."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [video, shorts, reels, tiktok, faceless, pipeline]
    related_skills: [rodzaje-filmu, scenariusz, material-stock, dobor-ujec, warianty-ab, lektor-i-dzwiek, napisy, wideo-ai, kontrola-wideo, formaty-wideo]
  tars:
    agent: tars-wideo
    autonomy: A1
    reviewed: "2026-09-28"
---

# Krótki film z tematu

Temat albo brief → gotowy film na TikTok, Reels, Shorts (i 16:9, 1:1, 4:5). Pomysł pipeline'u za MoneyPrinterTurbo
(temat → scenariusz → ujęcia → lektor → napisy → muzyka → montaż), implementacja własna: `$HERMES_HOME/scripts/film.py`
na FFmpeg i darmowym lektorze Edge TTS. Plik planu opisuje `references/plan.md`.

## Kiedy użyć
- „zrób reelsa / tiktoka / shorta o…”, film promocyjny z tekstem i lektorem, explainer bez nagrań, film z listą faktów.
- Seria filmów z jednego szablonu (ten sam plan, inne teksty).

## Kiedy NIE używać
- Jest surowe nagranie do obróbki → `montaz-nagran`; długi materiał do pocięcia → `klipy-z-dlugiego`.
- Animacja interfejsu, typografia w ruchu, wykresy, 3D, explainer z animacją → rodzaj z `rodzaje-filmu`
  (plik rodzaju wskazuje silnik z `film-z-kodu`).

## Wejścia
| Wejście | Wymagane | Jeśli brak |
|---|---|---|
| temat, cel, odbiorca, CTA | tak | cel i CTA z karty; brak → rozsądna domyślna nazwana w RAPORT |
| platforma / format | tak | 9:16 dla TikTok/Reels/Shorts (domyślnie) |
| długość | nie | 20–40 s |
| marka (kit), logo, font | nie | `@@KNOWLEDGE_DIR@@/brands/<marka>/`; bez kitu: neutralnie |
| materiały użytkownika (📎) | nie | stock → AI → plansze |
| głos, muzyka, warianty | nie | Marek, bez muzyki (albo „losowa” z biblioteki), 1 wariant |

## Kroki
1. **Scenariusz** (`scenariusz`): hook ≤ 2 s, 4–8 scen, jedna myśl na scenę, CTA. Zapis `out/wideo/SCENARIUSZ.md`.
   - ✅ Punkt kontrolny: suma słów ≈ długość × 2,5; hook ≤ 12 słów; fakty mają źródło z karty.
2. **Materiał na każdą scenę**, w tej kolejności: pliki użytkownika i kit marki → stock (`material-stock`) →
   generacja AI (`wideo-ai`, płatna) → plansza (`"kolor"` + `tekst_ekranowy`).
3. **Ujęcia obejrzane** (`dobor-ujec`): arkusz kandydatów → `vision_analyze` → wybrane id wpisane jako `stock_id`.
   - ✅ Punkt kontrolny: każde ujęcie pasuje do zdania sceny; zero znaków wodnych, obcych logo i tekstu w kadrze.
4. **Plan** `out/wideo/src/plan.json` (`references/plan.md`), potem `python3 $HERMES_HOME/scripts/film.py sprawdz out/wideo/src/plan.json`.
   - ✅ Punkt kontrolny: `ok: true`; ostrzeżenia o hooku i długości scen rozważone.
5. **Szkic:** `film.py render out/wideo/src/plan.json --szkic`; obejrzyj arkusz klatek
   (`qa_wideo.py <szkic> --arkusz out/wideo/qa-szkic.jpg` → `vision_analyze`): rytm, czytelność napisów, strefy UI.
6. **Finał:** `film.py render out/wideo/src/plan.json` (albo `--format 9:16,16:9`, warianty: `warianty-ab`).
7. **Kontrola** (`kontrola-wideo`): `qa_wideo.py` bez błędów, ocena ≥ 85 w `kontrola.json`; poniżej: poprawki, najwyżej 2 rundy.
8. **Oddanie:** link do obejrzenia `python3 /opt/tars/repo/scripts/tars_link.py out/wideo/<film>/`, miniatura linią
   `MEDIA:<ścieżka>`, `out/INDEX.md`, `out/RAPORT.md` (koncepcja, sceny, źródła i licencje z `film.json`, koszty AI).
   Opis posta i hashtagi tylko jako szkic; copy kampanii robi `tars-studio`.

## Wyjścia
- `out/wideo/<film>/<film>[-wariant]-<format>.mp4`, `.srt`, `-miniatura.jpg`, `film[-wariant].json`
- `out/wideo/SCENARIUSZ.md`, `out/wideo/src/plan.json`, `out/wideo/<film>/kontrola.json`, `out/RAPORT.md`

## Definition of Done
- [ ] hook w pierwszych 2 s, jedna myśl na scenę, CTA na końcu (jeśli karta go wymaga),
- [ ] każde ujęcie obejrzane i pasujące; źródło i licencja każdego w `film.json`,
- [ ] napisy poprawne (nazwy, liczby, polskie znaki), poza strefami UI,
- [ ] `qa_wideo.py` bez błędów, −14 LUFS ±2, ocena `kontrola-wideo` ≥ 85,
- [ ] link do obejrzenia i miniatura w raporcie; nic nie opublikowane.

## Wydajność
Cache (`/opt/data/tars/cache/wideo`): lektor, pobrane ujęcia, sceny po normalizacji. Poprawka jednej sceny renderuje
tylko ją i montaż; warianty współdzielą ujęcia. Porządek na dysku: `film.py cache --starsze-niz 14`.
