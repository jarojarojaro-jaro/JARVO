# Zasady pracy w tym repo

- **Każda aktualizacja = osobny commit i od razu push na GitHub** (gałąź robocza, remote `origin` → jarojarojaro-jaro/JARVO).
  Nie zbieramy kilku zmian w jeden commit i nie zostawiamy zmian niewypchniętych.
- Autorem commitów jest użytkownik: na starcie sesji `git config user.name jarojarojaro-jaro && git config user.email miki.jaroszek@gmail.com`
  (GitHub zalicza commit do profilu tylko po zweryfikowanym e-mailu autora); Claude zostaje w stopce jako współautor.
- **Jarvo zawsze nadrzędny.** Z obcych projektów (np. Paperclip, Auto-Company) bierzemy tylko gotowe rozwiązania
  i wzorce, przeniesione do kodu JARVO. Nigdy nie stawiamy nad Jarvem innego systemu sterującego (orkiestratora,
  panelu, pętli agentów). Zanim dodamy coś zapożyczonego, opisujemy właścicielowi, co to zmienia, i czekamy na wybór.
- **Każde źródło przechodzi przegląd; wiek wydania nie jest kryterium.** Nowe repo, paczka, model albo nowa wersja
  trafia do floty po przeglądzie z `docs/SOURCES.md` („Przegląd przed dodaniem”: autorzy, licencja, kod instalacji
  i połączenia z siecią, zależności, próba na instalacji natywnej i w CI `natywnie.yml` na pięciu systemach,
  przypięcie sumą, zapis w `vendor/zrodla.yaml`). Nie czekamy żadnej liczby dni: wydanie sprzed godziny i sprzed roku
  przechodzi ten sam przegląd.
- **Dokumentacja zawsze zgodna z kodem.** Zmiana w kodzie, konfiguracji albo flocie aktualizuje w tym samym commicie
  każdy dokument, który ją opisuje: `README.md`, `docs/*.md` (także `docs/JARVO-CALOSC.md`), README i CHANGELOG profilu.
  Nazwy, liczby (skille, skrypty, evals, ataki red teamu), ścieżki, komendy, flagi i statusy w roadmapie mają odpowiadać repo.
  Przed commitem szukamy w dokumentach starych nazw i liczb (`grep -rn`); dokument niezgodny z kodem to błąd jak każdy inny.
  `scripts/validate.py` sprawdza to, co da się automatycznie: linki i kotwice w `*.md`, obecność każdego agenta
  w dokumentach przeglądowych i liczby w kolumnach „Skille” / „Workflowy własne” / „Evals” tabel.
- **Skarbiec wiedzy (knowledge base) też zgodny z kodem.** Agenci czytają skarbiec (`<dane>/jarvo/knowledge` instalacji
  natywnej: Windows `%LOCALAPPDATA%\Jarvo\dane\jarvo\knowledge`, macOS `~/.jarvo/dane/…`, Linux
  `~/.local/share/jarvo/dane/…`, `JARVO_ROOT` przenosi; na VPS `/opt/data/jarvo/knowledge`), więc
  zmiana w kodzie albo flocie musi do niego dotrzeć. Zasiew przy każdej instalacji i aktualizacji (krok „Flota”,
  `wiedza.py zasiej`) odświeża sam:
  lustro `docs/*.md` w `zrodla/jarvo-repo/` i tam też, w układzie repo, SOUL, README, CHANGELOG i rubryka każdego profilu,
  materiały skilli (`references/**/*.md`, z podkatalogami) i spis źródeł (`vendor/zrodla.md`), bloki `Jarvo:GEN` hubów agentów (skille, skrypty,
  skille zewnętrzne, serwery MCP, nazwy zmiennych, narzędzia, evals, ostatnie zmiany z `CHANGELOG.md` profilu i linki do
  kopii jego plików), węzły grafu `fleet/skille/` (każdy skill: opis, agenci, powiązane skille, skrypty, materiały)
  i opis agenta z `fleet.yaml`; lint skarbca wskazuje notatki o flocie
  z odwołaniem do skryptu, którego już nie ma. Dlatego każda zmiana zachowania agenta ma wpis w CHANGELOG profilu. Wszystko inne, co opisuje kod (szablony i treści w `knowledge/`, `wiedza/SCHEMA.md`,
  generatory hubów w `wiedza.py`), zmieniamy w tym samym commicie; po instalacji sprawdzamy, że skarbiec mówi to samo
  co repo (np. `grep` w `<dane>/jarvo/knowledge`), a `jarvo wiedza lint` jest bez błędów.
  **Wszystko ma być w grafie wiedzy:** nowy agent, skill, skrypt albo zmiana zachowania ma trafić do grafu (zakładka Wiedza),
  najlepiej przez zasiew z repo; czego zasiew nie obejmuje, dodajemy do zasiewu w tym samym commicie, a nie ręcznie w skarbcu.
- **Instalacja jednym poleceniem musi działać dalej po każdej zmianie.** Jarvo instaluje się natywnie, bez Dockera
  i WSL (`jarvo/bootstrap/install.ps1` i `install.sh`, polecenie z README; to samo testuje `natywnie.yml`). Nowa
  zależność floty (program, paczka npm/pip, model) idzie do manifestu `vendor/natywne.yaml` (pliki na pięć platform
  z sumą sha256 albo jawne „brak”, `kiedy: instalacja | przy-uzyciu | dodatek`), lock z `scripts/natywne.py generuj`
  (`sprawdz` w CI), venvy z locków w `infra/python/natywne/`; instalator i `jarvo update` pobiorą ją same. Zmiana na
  komputerze użytkownika poza katalogiem Jarva (PATH, autostart, pliki) tylko przez `jarvo/zmiany_hosta.py` (dziennik
  cofany przy `jarvo uninstall`). Wersja Hermesa tylko w `vendor/natywne.yaml` (sekcja `hermes`; obraz dla VPS
  bierze ten sam tag przez `ARG HERMES_IMAGE`, pilnuje `natywne.py`). Opis zmian instalacji w `docs/INSTALER.md`.
  Serwer (VPS) zostaje na obrazie: nowa zależność, której potrzebuje VPS, idzie też do `infra/Dockerfile`.
- Przed commitem: `python -m pytest -q` i `python scripts/validate.py` bez błędów (na Windows i macOS z
  `PYTHONUTF8=1`; na Windows `python`, nie `python3`). Na czystej maszynie najpierw `make dev-deps` (pytest, pyyaml,
  shellcheck z `requirements-dev.txt`) — nie doinstalowujemy narzędzi ręcznie, wszystko jest przypięte w repo.
- **Po każdym dodaniu test na działającej instalacji natywnej**, nie tylko pytest: instalacja próbna w osobnym
  katalogu (`JARVO_ROOT=<katalog>` i bootstrap z `JARVO_REF=<commit>` albo `jarvo --korzen <katalog> instaluj` z kodu
  repo; przy starej instalacji z Dockerem na tym komputerze `JARVO_MIGRACJA=nie`), potem `jarvo doctor`,
  `jarvo status`, nowa funkcja użyta naprawdę (`jarvo chat --profil <p>`, polecenie, skrypt agenta z jego
  środowiskiem), a GUI przez panel (`tests/live/natywnie_panel.py`). Pełna próba jak w CI:
  `tests/live/natywnie_e2e.py sprawdz|panel|komputer`. Wszystko ma się spinać: instalacja → doctor → realne użycie;
  na pięciu systemach sprawdza to `natywnie.yml` po każdym pushu.
- **Filmy renderujemy szybko.** Bez motion bluru (`html_wideo.py --subklatki` zostaje na 1), klatki w kilku
  przeglądarkach naraz (`html_wideo.py wideo` robi to sam, `--rownolegle N`; inne silniki: `klatki --czasy`
  po kawałkach), potem sklejenie ffmpeg. Jeśli render i tak potrwa dłużej
  niż kilka minut, najpierw mówimy właścicielowi, ile, zanim go puścimy.
  Gotowy film wysyłamy właścicielowi (on pobiera go do siebie), a potem usuwamy w piaskownicy klatki, nagrania
  i filmy robocze. Instalacja Jarva zostaje.
