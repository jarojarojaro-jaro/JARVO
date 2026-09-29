# Changelog: jarvo-wideo

## Niewydane
- Wspólny skill `transkrypcja-filmu`: link (YouTube, TikTok, Instagram…) albo plik → tekst tego, co mówią (napisy platformy albo Parakeet).
- Czat Jarvo HQ (`platform_toolsets.api_server`) ustawiony jawnie: te same narzędzia co na Telegramie (bez `clarify`). Wcześniej Hermes dawał tu swój domyślny zestaw narzędzi.

## 0.1.0 (2026-09-28)
- Pierwsza wersja: wideo wydzielone ze Studia i rozbudowane. 13 workflowów, 7 skryptów: pipeline krótkiego filmu
  z planu (pomysł z MoneyPrinterTurbo, własna implementacja na FFmpeg + Edge TTS), warianty A/B, stock Pexels/Pixabay,
  dobór ujęć okiem, montaż nagrań, klipy z długich nagrań, napisy karaoke z czasu słów, kontrola jakości 0–100.
