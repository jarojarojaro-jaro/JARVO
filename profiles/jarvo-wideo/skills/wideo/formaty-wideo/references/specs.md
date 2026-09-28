# Specyfikacje wideo platform (stan: 2026-09)

Klucz `platforma` = argument `qa_wideo.py --platforma`. Tabela jest zsynchronizowana z `PLATFORMS` w `scripts/qa_wideo.py`
(test `tests/test_wideo.py`).

| platforma | Platforma / miejsce | Format | Rozdzielczość | Maks. długość | Zalecana długość | Uwagi |
|---|---|---|---|---|---|---|
| `tiktok` | TikTok | 9:16 | 1080×1920 | 600 s | 15–60 s | napisy wypalone, hook w 1–2 s |
| `ig-reel` | Instagram Reels | 9:16 | 1080×1920 | 180 s | 15–60 s | okładka w siatce przycinana do 4:5/1:1 |
| `yt-short` | YouTube Shorts | 9:16 | 1080×1920 | 180 s | 15–60 s | pętla na końcu wydłuża oglądanie |
| `fb-reel` | Facebook Reels | 9:16 | 1080×1920 | 90 s | 15–60 s | |
| `ig-story` | Instagram / FB Stories | 9:16 | 1080×1920 | 60 s | 5–15 s | naklejki i link zasłaniają dół |
| `li-video` | LinkedIn wideo | 4:5 | 1080×1350 | 600 s | 30–90 s | napisy wypalone + SRT, ton ekspercki |
| `ig-feed` | Instagram feed wideo | 4:5 | 1080×1350 | 60 s | 15–45 s | |
| `x-video` | X (Twitter) | 16:9 | 1920×1080 | 140 s | 15–45 s | 1:1 też dobrze działa |
| `yt-video` | YouTube (poziomo) | 16:9 | 1920×1080 | 43200 s | 60–900 s | miniatura 1280×720 osobno, rozdziały w opisie |
| `kwadrat` | uniwersalny kwadrat | 1:1 | 1080×1080 | 600 s | 15–60 s | feed FB/LinkedIn/X |
