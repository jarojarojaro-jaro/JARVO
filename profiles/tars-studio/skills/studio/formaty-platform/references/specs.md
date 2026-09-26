# Specyfikacje platform

<!-- reviewed: 2026-09-26. Wartości zalecane do produkcji. Limity platform zmieniają się:
     przy rozbieżności z dokumentacją platformy aktualizuj ten plik w repo (profiles/tars-studio/…). -->

Klucze `spec` w pierwszej kolumnie są używane przez `check_media.py`.

| spec | Platforma / typ | Wymiary (px) | Proporcje | Długość wideo | Uwagi |
|---|---|---|---|---|---|
| `ig-post` | Instagram post (pion) | 1080×1350 | 4:5 | — | najlepsza widoczność w feedzie |
| `ig-square` | Instagram post (kwadrat) | 1080×1080 | 1:1 | — | karuzela: wszystkie slajdy w tym samym formacie |
| `ig-story` | Instagram Stories | 1080×1920 | 9:16 | ≤ 60 s na klatkę | bezpieczna strefa: ~250 px góra/dół |
| `ig-reel` | Instagram Reels | 1080×1920 | 9:16 | rek. 15–60 s | okładka widoczna w siatce jako 4:5/1:1 |
| `tiktok` | TikTok | 1080×1920 | 9:16 | rek. 15–60 s | napisy wypalone, hook w 1–2 s |
| `yt-short` | YouTube Shorts | 1080×1920 | 9:16 | rek. ≤ 60 s | |
| `yt-thumb` | YouTube miniatura | 1280×720 | 16:9 | — | < 2 MB, czytelna w małym rozmiarze |
| `yt-video` | YouTube wideo | 1920×1080 | 16:9 | — | |
| `li-post` | LinkedIn obraz | 1200×627 | 1.91:1 | — | alternatywnie 1080×1080 / 1080×1350 |
| `li-video` | LinkedIn wideo | 1080×1350 / 1920×1080 | 4:5 / 16:9 | rek. 30–90 s | napisy wypalone |
| `x-post` | X (Twitter) obraz | 1600×900 | 16:9 | — | |
| `fb-post` | Facebook post | 1080×1350 | 4:5 | — | link preview: 1200×630 |
| `og` | Open Graph / podgląd linku | 1200×630 | 1.91:1 | — | < 1 MB, kluczowy tekst w centrum |
| `email-hero` | nagłówek e-maila | 1200×600 | 2:1 | — | retina: eksport 2× szerokości kontenera |

## Limity tekstu (orientacyjne)
| Platforma | Limit | Widoczne przed „więcej” |
|---|---|---|
| LinkedIn post | 3000 znaków | ~210 znaków (hook tutaj) |
| Instagram opis | 2200 znaków, do 30 hashtagów | ~125 znaków |
| X post | 280 znaków (konta bez subskrypcji) | całość |
| Facebook post | długi; rek. < 250 znaków | ~125 znaków |
| TikTok opis | 4000 znaków | krótko: 1–2 zdania |
| Meta title / description | 60 / 160 znaków | — |
