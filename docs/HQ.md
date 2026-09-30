# Jarvo HQ: kwatera floty (GUI)

Jarvo HQ to zakładka **BASE** w menu dashboardu Hermesa, nad CHAT (`http://<ip-tailscale>:9119/base`, logowanie jak do dashboardu).
Obok niej jest zakładka **WIEDZA** (`/wiedza`): skarbiec wiedzy floty z grafem notatek, orzeczeniami i skrzynką szkiców
(osobna wtyczka `jarvo-wiedza`, opis w [WIEDZA.md §8](WIEDZA.md#8-zakładka-wiedza-w-dashboardzie-i-obsidian)).
Pokazuje flotę jako budynek z klocków. Na górze jest mostek Jarva, pod nim piętra z pokojami snajperów (po dwa na piętro). Każdy
agent ma swój pokój, swoją minifigurkę i dymek z tym, co robi w tej chwili. Kliknięcie pokoju otwiera panel
z podglądem pracy na żywo, kartami, wynikami i czatem. Na dole jest rozmowa: domyślnie z Jarvem, jednym
kliknięciem z dowolnym agentem.

Tryb demo (symulowana flota, bez serwera): `python3 scripts/hqbuild.py --demo build/hq-demo`, potem otwórz
`build/hq-demo/index.html` przez dowolny serwer statyczny.

---

## 1. Co widać

| Element | Skąd dane | Co pokazuje |
|---|---|---|
| Pasek stanu | kanban | karty w toku, w ocenie, zablokowane, w kolejce, zrobione dziś; liczba decyzji |
| Pokój agenta | kanban + sesja pracownika | stan (pracuje, ocenia, czeka na ocenę, czeka na decyzję, ma kolejkę, wolny) jako animacja i znacznik; dymek z bieżącym narzędziem („szuka: …”, „pisze: out/RAPORT.md”) |
| Mostek Jarva | kanban | ekran „Tablica floty” z prawdziwymi licznikami kolumn; Jarvo-monolit ocenia, gdy w torze review jest karta |
| Panel agenta: Teraz | sesja pracownika w `state.db` profilu | karta, nad którą pracuje, czas, sygnał życia i oś kroków na żywo (narzędzia, wypowiedzi, błędy) |
| Panel agenta: Karty | kanban | karty agenta według stanu (7 dni), klik otwiera kartę z historią i komentarzami |
| Okno karty | kanban + katalog roboczy karty | na wierzchu **cel** (inny kolor), kontekst, **wynik** (pliki z `WYJŚCIA` oznaczone ★) i raport wykonawcy; pełne zlecenie (wejścia, DoD, granice), komentarze i historia zwinięte |
| Panel agenta: Wyniki | katalogi robocze | pliki z `out/`: miniatury grafik, podgląd tekstu, PDF, wideo |
| Czat: zdjęcia i pliki | czat HQ + `/opt/data/jarvo/inbox/` | 📎, wklejanie Ctrl+V (zrzut ekranu) i przeciąganie. Plik trafia do `inbox/<data>/`, agent dostaje jego ścieżkę (linia `📎 …`), zdjęcie także jako obraz (model bez widzenia dostaje opis od Hermesa) |
| Czat: pliki od agenta | odpowiedź agenta | linia `MEDIA:<ścieżka>` i obrazy `data:image` jako miniatury, ścieżki `/opt/data/jarvo/…` i adresy http(s) klikalne; obraz ma „Kopiuj obraz” (np. do Telegrama) |
| Akcje pliku wynikowego | plugin + pomocnik hosta | **▶ Odpal** (strona HTML w nowej karcie, `:9120`), **Pokaż w folderze** (Eksplorator Windows w lokalnej instalacji WSL; gdzie indziej: **Kopiuj ścieżkę**), **Pobierz**, podgląd/kod |
| **✎ Edytuj** (każdy film) | edytor w HQ + ffmpeg w kontenerze | montaż w stylu CapCut: oś czasu z miniaturami, cięcie (S), przycinanie krawędzi, przestawianie klipów, tempo 0,25–4×, głośność i wyciszenie, zdjęcia jako plansze, napisy (styl, krój, kolor, przeciąganie na podglądzie), muzyka z katalogu albo z dysku, format 16:9 / 9:16 / 1:1 / 4:5, cofnij/ponów, skróty klawiszowe. **Eksportuj** zapisuje nową wersję obok oryginału (`film-edycja.mp4`, oryginał zostaje), **Poproś agenta** wysyła Wideografowi prośbę z projektem montażu. Szczegóły: sekcja 2a |
| Panel agenta: Czat | API gatewaya | rozmowa bezpośrednia z agentem (sesja HQ, osobna od Telegrama) |
| Panel agenta: O agencie | fleet.yaml, SOUL, skille | opis, model, autonomia, parametry osobowości, workflowy |
| Centrala: Decyzje | kanban (`blocked` + `needs_input`, karty porzucone po błędach) | pytania agentów; odpowiedź idzie do Jarva, który odblokowuje kartę i zapisuje decyzję. Karta porzucona po błędach ma **Ponów kartę** (wraca do kolejki) albo **Przekaż Jarvowi** |
| Centrala: Misje | `missions/INDEX.md` + kanban | postęp misji (kostki kart w kolorach stanu) |
| Centrala: Na bieżąco | zdarzenia kanbana | kto zaczął, oddał do oceny, skończył, utknął |

Decyzje świadomie idą przez Jarva, a nie bezpośrednio do karty: szef zapisuje je w dzienniku misji i pilnuje
reszty (skill `decision-queue` zna format wiadomości z HQ). Wyjątek: „Ponów kartę” odblokowuje kartę porzuconą
po błędach bezpośrednio (`hermes kanban unblock`), bo tu nie ma czego rozstrzygać.

## 2. Architektura

```
przeglądarka (Tailscale) ── :9119 dashboard Hermesa (logowanie hasłem)
   └─ zakładka „/base” = plugin jarvo-hq (React z SDK dashboardu + htm, bez kroku budowania po stronie serwera)
        ├─ GET  /api/plugins/jarvo-hq/state        co 3 s: agenci, tablica, decyzje, misje, zdarzenia
        ├─ GET  /api/plugins/jarvo-hq/fleet        opis floty (fleet.json)
        ├─ GET  /api/plugins/jarvo-hq/agent/<a>    co 2,5 s przy otwartym panelu: karty, oś kroków, wyniki
        ├─ GET  /api/plugins/jarvo-hq/task/<id>    karta z historią i komentarzami
        ├─ POST /api/plugins/jarvo-hq/task/<id>/retry  „Ponów kartę” porzuconą po błędach (hermes kanban unblock)
        ├─ GET  /api/plugins/jarvo-hq/file?path=   podgląd pliku z katalogów floty
        ├─ POST /api/plugins/jarvo-hq/site        link „Odpal” (token) ─► :9120 serwer podglądu stron w pluginie
        ├─ POST /api/plugins/jarvo-hq/reveal      prośba „Pokaż w folderze” ─► pomocnik hosta (explorer.exe)
        ├─ GET  /api/plugins/jarvo-hq/host        czy działa „Pokaż w folderze” (WSL), ścieżki hosta, port podglądu
        ├─ GET  /api/plugins/jarvo-hq/chat/<a>/history
        ├─ POST /api/plugins/jarvo-hq/chat/<a>/send ─► gateway :8642 /p/<agent>/api/sessions/<id>/chat/stream (SSE)
        ├─ POST /api/plugins/jarvo-hq/chat/<a>/reset
        ├─ POST /api/plugins/jarvo-hq/upload      plik z czatu (📎, Ctrl+V, przeciągnięcie) ─► /opt/data/jarvo/inbox/<data>/
        ├─ GET/POST /api/plugins/jarvo-hq/edit/…  edytor filmów: info, media, save, stamp, srt, speech, proxy,
        │                                          proxy-file, export, job/<id>[/cancel] (sekcja 2a)
        ├─ GET/POST /api/plugins/jarvo-hq/update  stan i prośba o sprawdzenie/aktualizację (pomocnik hosta scripts/updater.py)
        └─ GET  /api/plugins/jarvo-hq/health       klucze API profili i dostępność gatewaya
backend pluginu (plugin_api.py, w procesie dashboardu)
   ├─ hq_core.py: odczyt kanban.db i state.db profili w trybie tylko do odczytu, wyliczenie stanu
   └─ klient API gatewaya z kluczem profilu czytanym z jego .env (przeglądarka nigdy go nie widzi)
```

Pliki w repo:

| Ścieżka | Rola |
|---|---|
| `hq/plugin/manifest.json` | manifest pluginu dashboardu (zakładka BASE w menu, przed CHAT) |
| `hq/plugin/plugin_api.py` | trasy FastAPI, proxy czatu do gatewaya |
| `hq/plugin/hq_core.py` | logika stanu (bez FastAPI, testowana w `tests/test_hq_core.py`) |
| `hq/plugin/edytor.py` | edytor filmów: walidacja projektu, polecenie ffmpeg, ffprobe (testy: `tests/test_edytor.py`) |
| `hq/web/src/*.js` | frontend: podstawy, API, grafika pokoi, budynek, panel, napisy i edytor filmów, czat, HUD, aplikacja, widżet aktualizacji |
| `hq/web/style.css` | styl (tokeny motywu dashboardu, animacje, responsywność) |
| `branding/fonts/` | kroje motywu Fosfor (VT323, IBM Plex Mono, OFL) i `fosfor.css`; te same pliki na stronie logowania |
| `hq/web/vendor/htm.umd.js` | htm 3.1.1 (Apache-2.0): składnia podobna do JSX bez kompilacji |
| `hq/web/demo/` | strona demo i symulator floty |
| `scripts/hqbuild.py` | build pluginu (sklejenie JS, `fleet.json` z fleet.yaml i SOUL) i demo |
| `scripts/share_keys.py` (kopiowany do pluginu) | wspólne klucze floty na żywo: klucz dostawcy z głównego `.env` trafia do `.env` agentów |

Wdrożenie jest częścią zwykłego `deploy.sh`: `build.py` buduje plugin do `build/plugins/jarvo-hq`,
`install-fleet.sh` kopiuje go do `/opt/data/plugins/jarvo-hq`, włącza (Hermes wymaga jawnego włączenia
pluginów użytkownika), generuje brakujące `API_SERVER_KEY` profili i restartuje sam dashboard (s6).

## 2a. Edytor filmów

Bez bibliotek i bez nowych usług: edytor to jeden plik `hq/web/src/45-edytor.js` (~88 KB nieskompresowany, ok. 26 KB po gzip) w tym samym
pakiecie co HQ, a eksport robi ffmpeg, który już jest w kontenerze.

- **Podgląd** gra w przeglądarce z plików pobranych raz (blob), bez serwera w pętli. Dwa elementy `<video>` na zmianę:
  następny klip czeka przewinięty na swój początek, więc przejścia są płynne. Miniatury osi czasu robi przeglądarka
  (jedna kanwa na źródło).
- **Napisy** rysuje jedna funkcja na kanwie: w podglądzie i przy eksporcie (PNG na napis nakładany przez ffmpeg),
  więc plik wygląda jak podgląd, łącznie z krojem.
- **Projekt** zapisuje się sam (co ~1 s) jako `<film>.edycja.json` obok filmu: klipy (`src`, `in`, `out`, `speed`,
  `volume`, `muted`, `fit`), napisy i muzyka. Po ponownym otwarciu edycja jest tam, gdzie była.
- **Eksport** (`POST /edit/export`): serwer sprawdza projekt (ścieżki tylko z katalogów floty, limity długości
  i liczby elementów), składa jeden przebieg ffmpeg (klipy → concat → nakładki → miks z limiterem), H.264 + AAC,
  `+faststart`. Jedno zadanie naraz, postęp z `-progress`, przerwanie zabija proces. Plik powstaje jako `.part`
  i dopiero gotowy dostaje nazwę `film-edycja[-N].mp4`: nic nie jest nadpisywane.
- **Kadr:** klip w trybie „Wypełnij” (np. pion 9:16 z poziomego nagrania) ma w ustawieniach suwaki **Kadr: poziomo**,
  **Kadr: pionowo** i **Przybliżenie** (1–3×, punch-in). Zapisują się w klipie jako `fx`, `fy`, `zoom`; eksport tnie
  ten sam fragment (`crop` z punktem skupienia w ffmpeg), który pokazuje podgląd (CSS `object-position` + `scale`).
- **Napisy:** zakładka „Napisy” (na telefonie przycisk w dolnym pasku) rozpoznaje mowę klipów na serwerze
  (`jarvo-stt`, Parakeet, bez internetu) i wstawia napisy na ścieżkę tekstu, zgrane z cięciami i tempem. Wynik zapisuje
  się obok źródła jako `<nazwa>.auto.srt`, więc drugi raz wczytuje się od razu. Można też wczytać gotowy `.srt`
  z katalogu filmu. Styl, położenie, kolor i rozmiar zmieniają się dla wszystkich napisów naraz; pojedynczy napis
  poprawiasz na osi czasu.
- **Mowa, pauzy i wtrącenia:** zakładka „Mowa” (na telefonie w dolnym pasku). **Wykryj mowę i pauzy** robi dwie rzeczy
  na serwerze: `silencedetect` w ffmpeg wyznacza dokładnie ciszę, a `jarvo-stt --json` podaje czas każdego słowa.
  Na osi pojawia się ścieżka mowy: szare paski z wypowiedziami, **czerwone** znaczniki pauz (dłuższych niż suwak,
  domyślnie 0,6 s) i **pomarańczowe** „yyy”/„eee”. Znacznik klikasz: Wytnij, Zostaw albo Odsłuchaj; albo wycinasz
  wszystkie naraz. Cięcia to zwykłe cięcia klipów (zostaje 0,12 s oddechu), napisy i muzyka przesuwają się razem
  z nimi, całość cofa się jednym Ctrl+Z. Wynik analizy leży obok źródła jako `<nazwa>.mowa.json` (i `.auto.srt`):
  następnym razem wczytuje się sam, widzi go też Wideograf. Bez `jarvo-stt` działa samo wykrywanie pauz.
- **Napisy zgrane ze słowami:** linie układane są ze słów już po cięciach (nowa linia po pauzie, końcu zdania albo
  32 znakach), bez wtrąceń.
- **Karaoke:** napisy ze słów (automatyczne, nie z pliku `.srt`) pamiętają czas każdego słowa (`words`, liczony od
  początku napisu, więc przesunięty napis zabiera go ze sobą). Pole **Karaoke** w zakładce „Napisy” podświetla słowo
  wypowiadane w danej chwili wybranym kolorem (`hl`, domyślnie żółty). Poprawka literówki (ta sama liczba słów) zostawia
  karaoke, inna liczba słów wyłącza je tylko w tej linii. Eksport: obraz PNG na każde słowo, a wszystkie napisy karaoke
  idą do ffmpeg jako **jedna** warstwa (demuxer `concat`), więc pamięć nie rośnie z długością filmu.
- **Każda przeglądarka:** gdy przeglądarka nie odtwarza kodeka filmu (np. Chromium bez H.264, ProRes), edytor sam
  prosi serwer o kopię podglądową WebM (VP9, do 540 p, klatka kluczowa co 0,5 s dla szybkiego przewijania; raz na
  plik, w `state/edytor/proxy/`, sprząta się po 7 dniach). Eksport zawsze bierze oryginał w pełnej jakości.
- **Wspólny projekt z Wideografem:** „Poproś agenta” każe Wideografowi pracować na tym samym `*.edycja.json`
  poleceniem `projekt.py` (`pokaz`, `dodaj-audio`, `dodaj-tekst`, `dodaj-klip`, `kadr`, `napisy`, `usun`, `sprawdz`,
  `render`). `render` używa tego samego silnika co „Eksportuj” (`edytor.py` kopiowany przy buildzie obok skryptu),
  a napisy rysuje ta sama funkcja (`hq/web/src/44-napisy.js`) w przeglądarce bez okna, więc plik od agenta wygląda
  jak eksport z edytora. Edytor co 3 s sprawdza, czy projekt zmienił się z zewnątrz: bez Twoich niezapisanych zmian
  wczytuje wersję agenta sam (jako zwykły krok, ↶ ją cofa), a przy kolizji pyta: „Wczytaj jego wersję” albo
  „Zostaw moją”. Zapis nigdy nie nadpisuje po cichu cudzej zmiany (serwer odrzuca go jako nieaktualny).
- **Telefon (do 860 px):** układ jak w CapCut: podgląd na górze, pod nim czas, odtwarzanie i cofnij/ponów, oś czasu
  przewijana palcem pod stałym wskaźnikiem na środku (dwa palce: przybliżenie), a na dole pasek **Edytuj · Audio ·
  Tekst · Napisy · Format**. Narzędzie otwiera panel od dołu; dotknięcie klipu, napisu albo muzyki na osi otwiera
  jego ustawienia, uchwyty do przycinania pojawiają się na zaznaczonym elemencie.
- Logika serwera: `hq/plugin/edytor.py` (bez FastAPI), testy: `tests/test_edytor.py` (także prawdziwy eksport ffmpeg).

## 3. Bezpieczeństwo

- Wszystkie trasy pluginu są za logowaniem dashboardu (bez sesji: `401 unauthenticated`).
- Dashboard nasłuchuje tylko na IP Tailscale (`JARVO_BIND_IP`), hasło generuje bootstrap.
- Klucze API profili zostają na serwerze. Backend pluginu czyta je z `.env` profilu przy każdym wywołaniu.
- Podgląd plików tylko z `/opt/data/jarvo/{workspaces,missions,knowledge,inbox}` (inbox: pliki wysłane w czacie HQ),
  po rozwiązaniu symlinków.
  Pliki wysyłane z nagłówkiem `Content-Security-Policy: sandbox` i `nosniff`, HTML jako zwykły tekst:
  strona wygenerowana przez agenta nie wykona skryptu w sesji dashboardu.
- **▶ Odpal**: strona agenta idzie z osobnego portu 9120 (ten sam `JARVO_BIND_IP`), tylko pod adresem z losowym
  tokenem, który wydaje zalogowany dashboard albo agent (`scripts/jarvo_link.py`; wspólny plik
  `state/preview-links.json`, ważny 7 dni, przetrwa restart). Wykonawca karty działa z `HERMES_HOME` swojego profilu
  (`/opt/data/profiles/<agent>`), więc `hq_core` wylicza z niego korzeń danych (`/opt/data/jarvo`). Nagłówek `CSP: sandbox` bez
  `allow-same-origin` daje stronie nieprzezroczyste pochodzenie: jej skrypty działają, ale nie czytają ciasteczek
  i nie wyślą ich do dashboardu. Nowa karta nie ma `window.opener`. Pliki ukryte, `..` i symlinki na zewnątrz: 404.
- **Pokaż w folderze**: dashboard zapisuje tylko prośbę ze ścieżką (`state/reveal-request`); `scripts/updater.py`
  na hoście sprawdza ją ponownie (tylko `jarvo/{workspaces,missions,knowledge,inbox}`) i woła `explorer.exe /select,…`.
- Odczyt kanbana i transkrypcji w trybie SQLite `mode=ro`. HQ zapisuje tylko: mapę sesji czatu
  (`/opt/data/jarvo/state/hq-sessions.json`), pliki z czatu (`inbox/<data>/`), linki podglądu
  (`state/preview-links.json`, `state/preview.json`), prośby do pomocnika hosta (`state/reveal-request`,
  `state/update-request`), pliki edytora filmów (projekt `*.edycja.json`, analiza `*.mowa.json` i `*.auto.srt`,
  nowe wersje filmu obok oryginału, pliki tymczasowe w `state/edytor/`) i blok wspólnych kluczy w `.env` agentów
  (`share_keys.py`). Na tablicy HQ może tylko ponowić kartę porzuconą po błędach (`hermes kanban unblock`);
  resztę zmian robią agenci przez swoje narzędzia.
- Edytor: każda ścieżka z projektu przechodzi przez to samo sprawdzenie co podgląd plików; ffmpeg dostaje argumenty
  listą (bez powłoki), napisy tylko jako poprawne PNG do 12 MB.

## 4. Wieża Jarvo (wygląd)

Tytuł „Jarvo HQ”, stan połączenia, liczniki tablicy (w toku, ocena, blokady, kolejka, zrobione dziś) i
przycisk „Decyzje” siedzą w górnym pasku dashboardu Hermesa (kontekst strony wczytany z modułu dashboardu);
gdy go nie ma (np. tryb demo), HQ pokazuje własny pasek nad wieżą. Scena dopasowuje się do wysokości
okna: cała wieża mieści się nad czatem, a nadmiar szerokości wypełnia miasto po bokach.

Scena to **przekrój bazy-wieżowca w pixel arcie**, nocą, jak model z klocków przecięty na pół: płaskie
cięcie konstrukcji, a pokoje mają głębię (tylna ściana, podłoga w perspektywie, meble). Rysunek powstaje
w kodzie (`hq/web/src/20-art.js`) na siatce 400 pikseli logicznych i skaluje się w SVG bez rozmycia.

- **Dach:** neon „Jarvo”, antena z migającym światłem, talerz, zbiornik na wodę.
- **Mostek dowodzenia** (`bridge`): **Jarvo jako szef w garniturze** (postać 2× większa od załogi) za
  pulpitem dowodzenia, fotel dyrektorski, okno na miasto, ekran „Tablica floty” (liczniki kanbana na żywo),
  panel „Załoga” z lampką statusu każdego agenta, robot-monolit Jarvo (pracuje, gdy flota pracuje).
- **Piętra załogi:** po dwa pokoje na piętro wokół szybu windy; winda jeździ, gdy ktoś pracuje. Przy
  nieparzystej liczbie agentów wolne miejsce zajmuje magazyn. Nowi agenci dokładają piętra.
- **Maszynownia** (piwnica pod ulicą): szafy serwerowe i rdzeń zasilania; zielony „GATEWAY ONLINE”,
  czerwony, gdy HQ traci połączenie z flotą.

Pokój przypisuje `hq_room` w `fleet.yaml`, a krótką nazwę na szyldzie `hq_short`:

| `hq_room` | Wystrój | Postać |
|---|---|---|
| `bridge` | jak wyżej | szef Jarvo: czarny garnitur, biała koszula, czerwony krawat |
| `study` | regał z książkami, tablica dowodów z czerwonymi nitkami, zegar, globus, biurko z lampą bankierską | detektyw w kaszkiecie i szaliku (lupa przy pracy) |
| `devlab` | szafa serwerowa z diodami, tablica z makietą, neon `</>`, dwa monitory z kodem, kubek z parą | programista w bluzie i słuchawkach, tyłem przy monitorach |
| `atelier` | turkusowe tło fotograficzne, softbox, kamera z lampką REC, sztaluga z obrazem, plakat, klaps | artystka w berecie i koszulce w paski (paleta przy pracy) |
| `filmstudio` | zielone tło z softboxem, kamera na statywie z lampką REC, stół montażowy z monitorem 9:16 i osią czasu (głowica jedzie przy pracy), klaps, szpula i napis REC na ścianie | wideograf w czerwonej czapce z daszkiem i kamizelce (kamera przy pracy) |
| `workshop` | tablica z narzędziami, stół z imadłem i ramieniem robota, skrzynie (liczba = kolejka kart), beczka | mechanik w kasku i ogrodniczkach, tyłem przy stole |
| `office` | Sala operacyjna (Ads), też pokój domyślny dla nowych agentów: ściana ekranów z wynikami kampanii (słupki wariantów, linia wydatków pod czerwoną linią koperty, tablica ROAS), biurko z dwoma monitorami, czerwony STOP, roślinka | postać w koszuli i niebieskim krawacie, tyłem przy monitorach |
| `radar` | Radar sprzedaży (Łowca leadów): ekran radaru z pierścieniami (wiązka i migające cele przy pracy), mapa Polski z pinezkami firm, neon LEADY, biurko z listą leadów i słupkami oceny, stos kart (kolejka), telefon, roślinka | łowca w pomarańczowej czapce i kamizelce, ze słuchawkami, tyłem przy monitorach |

Stan agenta zmienia pokój: światło (pokój przygasa, gdy agent jest wolny), pozę (praca, trzymana karta
przy ocenie, uniesiona ręka i „!” przy blokadzie, „Z z z”, gdy śpi) i rekwizyty (monitory, lampa, ramię
robota, nagrywanie, hologram na pulpicie szefa). Animacje są skokowe jak w grach (kilka klatek) i
wyłączają się przy `prefers-reduced-motion`. Na wąskim ekranie wieżę przesuwa się w bok palcem.

**Nowy pokój:** dodaj klucz w `ROOMS` i funkcję wnętrza (`ROOM_DRAW`) w `hq/web/src/20-art.js`, wygląd
postaci w `LOOKS`, wpisz klucz do `HQ_ROOMS` w `scripts/fleetlib.py` (walidator pilnuje zgodności)
i ustaw `hq_room` agenta.

## 5. Motyw „Fosfor” (wygląd całego dashboardu)

Cały dashboard (menu, górny pasek, czat, Jarvo HQ) wygląda jak terminal CRT z 1982: czcionki VT323 i IBM Plex
Mono, linie skanowania, numerowane menu, podświetlenie w negatywie. Wieża zostaje w swoich kolorach.

- **Jeden kolor → cały wygląd.** `scripts/install_themes.py` liczy z niego odcienie, tło, ramki i poświatę,
  a z `branding/fosfor/theme.css` składa motywy Hermesa w `<HERMES_HOME>/dashboard-themes/`. Motyw dwukolorowy
  podaje dodatkowo `frame`, `fill`, `bg`, `muted`, `line` (i opcjonalnie `accent`).
- **Zmiana koloru:** przełącznik motywów w lewym dolnym rogu: domyślny **Jarvo · biało-czerwony** (dwukolorowy)
  oraz Fosfor: błękit, bursztyn, zieleń, biel. Własny kolor: dopisz linię w `branding/fosfor/palettes.yaml`
  i wdroż. Wybór zrobiony w dashboardzie przetrwa wdrożenia.
- Kolory terminala czatu idą z motywu (łatka w `branding/patch_dashboard.py`), skórka TUI jest biało-czerwona
  (`branding/skin-jarvo.yaml`).
- **Strona logowania** (`/login`, przed dashboardem) ma markę Jarvo: logo, biel i czerwień, VT323 / IBM Plex Mono,
  linie CRT i polskie napisy (łatka `patch_login` w `branding/patch_dashboard.py`). Fonty kopiuje do publicznego
  `/fonts/` dashboardu, bo pliki pluginu HQ są za logowaniem. Stopka menu: „Jarvo · Hermes Agent”.

## 6. Język: polski i angielski

Dashboard ma pełny polski (tłumaczenie `branding/i18n/pl.json`, ~750 tekstów i całe menu) i jest domyślnie po
polsku. Język zmienia przełącznik w lewym dolnym rogu (**POLSKI** / **EN** / …). Jarvo HQ idzie za nim: po polsku
albo po angielsku (każdy inny język = angielskie HQ); nazwy pokoi, role i opisy agentów po angielsku są w
`fleet.yaml` (`en:`). Tłumaczenie wstrzykuje `branding/patch_dashboard.py` przy budowie obrazu (brakujący klucz =
tekst angielski), więc zmiana `branding/` przebudowuje tylko ostatnią warstwę obrazu (sekundy, ta sama wersja
Hermesa). Etykiety wpisane w kod po angielsku na stronie Sesje (liczniki, „Import sessions”) tłumaczy łatka
(`patch_sessions`, klucze `sessions.*` w `pl.json`); inne takie etykiety Hermesa zostają po angielsku.

Agenci rozmawiają po polsku niezależnie od języka panelu (SOUL).

## 7. Rozwiązywanie problemów

| Objaw | Przyczyna i naprawa |
|---|---|
| brak zakładki BASE albo WIEDZA w menu | plugin nie jest włączony albo dashboard nie wstał po instalacji: `docker exec -u hermes jarvo-hermes /command/s6-svc -r /run/service/dashboard` |
| czat: „Profil … nie ma API_SERVER_KEY” | uruchom deploy ponownie (instalator generuje klucze) |
| czat: „Gateway odrzucił klucz” | klucz w `.env` profilu zmieniony bez restartu gatewaya: `hermes gateway restart` |
| czat: „No LLM provider configured” | profil nie ma `OPENROUTER_API_KEY` w `/srv/jarvo/secrets/<agent>.env` |
| pokój „Pracuje”, ale dymek „cisza…” | pracownik nie wysłał sygnału od 3 min; szczegóły w panelu, patrol zgłosi problem sam |
| agent podaje `localhost:8000` albo inny port z kontenera | taki adres nie działa w Twojej przeglądarce. Agenci mają to w zasadach; link do wyniku daje `python3 /opt/jarvo/repo/scripts/jarvo_link.py <plik>` (serwer podglądu :9120, 7 dni) |
| „▶ Odpal” otwiera pustą kartę / „nie można połączyć” | port 9120 nieopublikowany: kontener sprzed tej wersji, `bash scripts/local-up.sh` (lokalnie) albo `deploy.sh` go odtworzy |
| brak „Pokaż w folderze”, jest „Kopiuj ścieżkę” | pomocnik hosta nie działa albo to nie WSL: `bash scripts/local-up.sh` (uruchamia `scripts/updater.py`) |
| `/api/plugins/jarvo-hq/health` | pokazuje, czy każdy profil ma klucz i czy gateway odpowiada na `/p/<agent>` |
