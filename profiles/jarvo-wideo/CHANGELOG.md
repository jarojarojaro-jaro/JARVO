# Changelog: jarvo-wideo

## Niewydane
- `klipy.py` (clipmaker): długie nagranie → `przygotuj` (mowa, cięcia ujęć, arkusze, transkrypcja), `sprawdz` (plan.json), `zbuduj` (projekty edytora + MP4 + KLIPY.md).
- Napisy karaoke w projekcie montażu: `projekt.py napisy --karaoke [kolor]`, podświetlenie słowa w edytorze HQ i w renderze.
- Kadr klipu w projekcie montażu: punkt skupienia i przybliżenie (`fx`, `fy`, `zoom`; `projekt.py kadr`, suwaki w edytorze HQ).
- Wspólny skill `transkrypcja-filmu`: link (YouTube, TikTok, Instagram…) albo plik → tekst tego, co mówią (napisy platformy albo Parakeet).
- Czat Jarvo HQ (`platform_toolsets.api_server`) ustawiony jawnie: te same narzędzia co na Telegramie (bez `clarify`). Wcześniej Hermes dawał tu swój domyślny zestaw narzędzi.

## 0.1.0 (2026-09-28)
- Pierwsza wersja: wideo wydzielone ze Studia i rozbudowane. 13 workflowów, 7 skryptów: pipeline krótkiego filmu
  z planu (pomysł z MoneyPrinterTurbo, własna implementacja na FFmpeg + Edge TTS), warianty A/B, stock Pexels/Pixabay,
  dobór ujęć okiem, montaż nagrań, klipy z długich nagrań, napisy karaoke z czasu słów, kontrola jakości 0–100.
