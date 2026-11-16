---
typ: blad
tagi: [przegladarka, camoufox, narzedzia]
utworzono: 2026-11-17
zmieniono: 2026-11-17
status: aktualna
zrodlo: "porównanie przeglądarki opencode 16.11 (Jarvo); JARVO cdcf6cd2"
agent: jarvo
sygnatury: [camoufox fetch, poproś właściciela o instalację, "/camoufox.{0,60}(not found|nie znaleziono|niedostępn)/"]
wystapienia: 1
---
# Zapasowa przeglądarka pobiera się sama, bez camoufox fetch

**Zapasową przeglądarkę (Camoufox, skill `ostrozna-przegladarka`) pobiera sam skrypt przy pierwszej stronie, z wersji i sumy z manifestu; agent nie woła `camoufox fetch` i nie prosi właściciela o instalację.**

**Objaw:** 16.11 skrypt zapasowej przeglądarki szukał jej w ścieżce z obrazu i pisał „poproś właściciela o instalację”; Jarvo, żeby zrobić test, użył `camoufox fetch`, które pobrało niepilnowaną wersję (2,5 GB) poza manifestem i bez sumy.

**Przyczyna:** dodatek „przy pierwszym użyciu” nie miał w kodzie drogi pobrania, a rada „poproś właściciela” pchnęła agenta do obejścia.

**Jak poprawnie:** stronę przez zapasową przeglądarkę otwierasz zwykłym poleceniem skilla `ostrozna-przegladarka`: przy pierwszej stronie sam pobierze wpis `camoufox` z manifestu Jarva (wersja i suma). `--sprawdz` mówi, czy jest gotowa. Gdy pobranie się nie uda, zgłaszasz błąd z jego komunikatem (zlecenie w `DLA-CLAUDE.md`), a nie pobierasz innej wersji ręcznie i nie prosisz właściciela.

## Powiązane
- hub: [[bledy/_hub-bledy|Księga błędów]]
- [[bledy/ocena narzędzia z linku zaczyna się od wykluczeń|Ocena narzędzia od wykluczeń]]
- [[bledy/ekran komputera zajęty przez inną kartę|Ekran Komputera zajęty]]
- [[fleet/lekcje|Księga lekcji floty]]
