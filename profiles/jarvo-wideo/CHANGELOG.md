# Changelog: jarvo-wideo

## Niewydane
- Skille zewnętrzne `motion-design` i `video-lessons` z Remocn Studio (MIT, przypięty commit `86f64ee`): reżyseria ruchu (kierunek, inscenizacja, ciągłość, easing, timing, słownik ruchów) i znane usterki renderu; reguła 12 w `film-z-kodu` tłumaczy ich pojęcia na nasze narzędzia. Skan: jedno ustalenie (rada „nie musi udawać demo” wzięta za zmianę tożsamości) opisane jako wyjątek.
- Uwagi z osi edytora HQ: `projekt.py pokaz` wypisuje uwagi właściciela (czas osi, tekst, kadr), `projekt.py uwaga <film> <id> --zrobione|--odrzuc` zamyka je z opisem (edytor pokazuje ✓), `render` ostrzega o otwartych. Prośba z edytora niesie kadry z podglądu (obrazy do `vision_analyze`).
- Skill `demo-strony` i skrypt `demo_strony.py` (metoda za ECC `ui-demo`, MIT): rozpoznanie elementów → próba scenariusza (akcje wykonane, zły selektor = lista widocznych elementów) → nagranie MP4 z płynnym kursorem, pisaniem znak po znaku, pauzami dla człowieka i paskiem napisów kroków (także nad oknem modalnym); SRT i oś kroków do edycji w HQ. Tylko nasz podgląd albo domeny ze scenariusza, hasło konta testowego tylko ze zmiennej środowiskowej.
- Kontrakt zlecenia (wspólny): nie osłabiam kontroli, żeby zaliczyć DoD (za ECC loop-design-check); poprawki po recenzji z pytaniem przy niejasnym punkcie i sprzeciwem z dowodem przy błędnym (za superpowers receiving-code-review); reguła 17: zgoda A2 przypięta do odcisku wersji plików (`scripts/odcisk.py`, za ECC operator-approval-loop).
- Wspólny skill `hooki` (`shared/skills/`, za marketing-os `hooks.md`, MIT): trzy warstwy hooka bez powtórzeń, 18 taktyk, korpus słów klientów, rozbieg, lejek diagnozy. Podpięty w `scenariusz`, `warianty-ab` i master prompcie `clipmaker` (pole `taktyka` w planie; `klipy.py sprawdz` ostrzega, gdy tytuł-hook powtarza pierwsze zdanie mowy).
- Master prompt clipmakera: zasady cięć (nie w środku słowa, zapas 30–200 ms, napisy zawsze na wierzchu).
- Skill `clipmaker` (master prompt: typy momentów, 6 osi oceny, uczciwość; schemat `plan.json`) zastępuje `klipy-z-dlugiego`: rolki są projektami edytora HQ, nie wypalonymi MP4.
- `klipy.py` (clipmaker): długie nagranie → `przygotuj` (mowa, cięcia ujęć, arkusze, transkrypcja), `sprawdz` (plan.json), `zbuduj` (projekty edytora + MP4 + KLIPY.md).
- Napisy karaoke w projekcie montażu: `projekt.py napisy --karaoke [kolor]`, podświetlenie słowa w edytorze HQ i w renderze.
- Kadr klipu w projekcie montażu: punkt skupienia i przybliżenie (`fx`, `fy`, `zoom`; `projekt.py kadr`, suwaki w edytorze HQ).
- Wspólny skill `transkrypcja-filmu`: link (YouTube, TikTok, Instagram…) albo plik → tekst tego, co mówią (napisy platformy albo Parakeet).
- Czat Jarvo HQ (`platform_toolsets.api_server`) ustawiony jawnie: te same narzędzia co na Telegramie (bez `clarify`). Wcześniej Hermes dawał tu swój domyślny zestaw narzędzi.

## 0.1.0 (2026-09-28)
- Pierwsza wersja: wideo wydzielone ze Studia i rozbudowane. 13 workflowów, 7 skryptów: pipeline krótkiego filmu
  z planu (pomysł z MoneyPrinterTurbo, własna implementacja na FFmpeg + Edge TTS), warianty A/B, stock Pexels/Pixabay,
  dobór ujęć okiem, montaż nagrań, klipy z długich nagrań, napisy karaoke z czasu słów, kontrola jakości 0–100.
