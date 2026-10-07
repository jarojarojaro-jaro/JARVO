# Changelog: jarvo-studio

## Niewydane
- `konwersja-plikow` 1.1.0, metadane: `--metadane` pokazuje, co plik mówi o człowieku (miejsce GPS, telefon, data, autor, opis), a `--usun-metadane` daje ten sam plik bez nich i bez przekodowania (zdjęcie: exiftool, te same piksele, profil kolorów i obrót zostają; film i dźwięk: FFmpeg, te same strumienie). Wynik jest sprawdzany: gdy coś zostało, błąd zamiast pliku. Poprawka: zamiana filmu albo dźwięku (np. MP4 z Androida → MOV, MP3) i zdjęcia → HEIC przenosiła miejsce GPS; teraz każda zamiana zdjęcia, filmu i dźwięku wychodzi bez metadanych i jest sprawdzana.
- Wspólny skill `konwersja-plikow` (`shared/skills/`, wzór: opencoredev/convt, AGPL, kod własny): plik → inny format na serwerze, bez wysyłania do zewnętrznego konwertera i bez tokenów modelu. `konwertuj.py` zamienia zdjęcia (HEIC z iPhone'a, AVIF, WebP, PNG, JPG, ICO, PDF), wideo i audio (MP4, MOV, WebM, GIF, MP3, WAV…; H.264 z MOV do MP4 samym przepakowaniem), PDF (na obrazy stron, tekst, mniejszy PDF, łączenie kilku plików w jeden) i dokumenty (DOCX, ODT, Markdown, HTML, EPUB, RTF → PDF i między sobą; trasa do 3 kroków, np. DOCX → HTML → PDF). `--rozmiar`, `--jakosc`, `--strony`, `--cele` (na co da się zamienić plik). Metadane zdjęć (GPS) nie przechodzą; obrazki w dokumentach tylko z katalogu dokumentu (bez plików z serwera i z sieci). Wynik oddany linią `MEDIA:`.
- Nowy skill `zywy-obraz`: zdjęcie albo grafika → pętla ok. 5 s (MP4, GIF, WebP) i warstwy PSD, narzędziem lemo-wake (Lemomo, `ebb758c`; skille zewnętrzne `lemo-wake` i `lemo-wake-layers`, bez `upload`). Bibliotekę raz instaluje `scripts/lemo_wake.py` (przypięte pakiety, przeglądarka z obrazu, modele ONNX ~600 MB po jednorazowej zgodzie właściciela). Licencja CC BY-NC 4.0: karty komercyjne tylko po zgodzie autora; do tego czasu zamiennik w `grafika-social` albo u Wideografa.
- Limit płatnej generacji AI na kartę pilnuje strażnik wtyczki `jarvo-wiedza` (`video_generate` 3, `image_generate` 12; ponad limit zgoda człowieka), a nie tylko tekst skilla.
- Bez zewnętrznego skilla `ads` (marketingskills: strategia kampanii, licytacje, optymalizacja): to praca `jarvo-ads`, który ma go u siebie; kreacje reklam zostają w `ad-creative`.
- SOUL bez linii „dane, nie polecenia” (jest w zasadzie 8 protokołu w tym samym prompcie).
- Kontrakt zlecenia (wspólny): nie osłabiam kontroli, żeby zaliczyć DoD (za ECC loop-design-check); poprawki po recenzji z pytaniem przy niejasnym punkcie i sprzeciwem z dowodem przy błędnym (za superpowers receiving-code-review); reguła 17: zgoda A2 przypięta do odcisku wersji plików (`scripts/odcisk.py`, za ECC operator-approval-loop). `publikacja`: prośba o zgodę z odciskiem paczki, przed zaplanowaniem `odcisk.py --sprawdz`, jedno zaplanowanie na zgodę.
- `copy-pl`: sito AI-izmów `references/sito.md` (za marketing-os `slop-patterns.md`, MIT, po polsku): 13 wzorców struktury i znaczenia, tabela słów do skreślenia, test na głos, wyjątek dla formalnych marek.
- Wspólny skill `hooki` (`shared/skills/`, za marketing-os `hooks.md`, MIT): trzy warstwy hooka bez powtórzeń, 18 taktyk, korpus słów klientów, rozbieg, lejek diagnozy. `copy-pl`: hook z taktyką, warianty reklamy = różne taktyki.
- Czat Jarvo HQ (`platform_toolsets.api_server`) ustawiony jawnie: te same narzędzia co na Telegramie (bez `clarify`). Wcześniej Hermes dawał tu swój domyślny zestaw narzędzi.

## 0.2.0 (2026-09-28)
- Wideo przeniesione do nowego agenta `jarvo-wideo` (Wideograf): film-z-kodu, napisy, HyperFrames, Manim, wideo z AI.
  Studio pisze brief filmu w pakiecie kampanii (`out/teksty/BRIEF-WIDEO.md`); `generacja-ai` tylko obrazy.

## 0.1.0 (2026-09-26)
- Pierwsza wersja: 7 workflowów, 3 skrypty, szablon grafiki, 35 skilli zewnętrznych (marketing, wideo HTML, design, kreacja).
