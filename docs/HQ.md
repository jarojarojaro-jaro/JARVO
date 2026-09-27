# TARS HQ: kwatera floty (GUI)

TARS HQ to zakładka **BASE** w menu dashboardu Hermesa, nad CHAT (`http://<ip-tailscale>:9119/base`, logowanie jak do dashboardu).
Pokazuje flotę jako budynek z klocków. Na piętrze jest mostek TARS-a, na parterze pokoje snajperów. Każdy
agent ma swój pokój, swoją minifigurkę i dymek z tym, co robi w tej chwili. Kliknięcie pokoju otwiera panel
z podglądem pracy na żywo, kartami, wynikami i czatem. Na dole jest rozmowa: domyślnie z TARS-em, jednym
kliknięciem z dowolnym agentem.

Tryb demo (symulowana flota, bez serwera): `python3 scripts/hqbuild.py --demo build/hq-demo`, potem otwórz
`build/hq-demo/index.html` przez dowolny serwer statyczny.

---

## 1. Co widać

| Element | Skąd dane | Co pokazuje |
|---|---|---|
| Pasek stanu | kanban | karty w toku, w ocenie, zablokowane, w kolejce, zrobione dziś; liczba decyzji |
| Pokój agenta | kanban + sesja pracownika | stan (pracuje, ocenia, czeka na ocenę, czeka na decyzję, ma kolejkę, wolny) jako animacja i znacznik; dymek z bieżącym narzędziem („szuka: …”, „pisze: out/RAPORT.md”) |
| Mostek TARS-a | kanban | ekran „Tablica floty” z prawdziwymi licznikami kolumn; TARS-monolit ocenia, gdy w torze review jest karta |
| Panel agenta: Teraz | sesja pracownika w `state.db` profilu | karta, nad którą pracuje, czas, sygnał życia i oś kroków na żywo (narzędzia, wypowiedzi, błędy) |
| Panel agenta: Karty | kanban | karty agenta według stanu (7 dni), klik otwiera kartę z historią i komentarzami |
| Okno karty | kanban + katalog roboczy karty | na wierzchu **cel** (inny kolor), kontekst, **wynik** (pliki z `WYJŚCIA` oznaczone ★) i raport wykonawcy; pełne zlecenie (wejścia, DoD, granice), komentarze i historia zwinięte |
| Panel agenta: Wyniki | katalogi robocze | pliki z `out/`: miniatury grafik, podgląd tekstu, PDF, wideo |
| Akcje pliku wynikowego | plugin + pomocnik hosta | **▶ Odpal** (strona HTML w nowej karcie, `:9120`), **Pokaż w folderze** (Eksplorator Windows w lokalnej instalacji WSL; gdzie indziej: **Kopiuj ścieżkę**), **Pobierz**, podgląd/kod |
| Panel agenta: Czat | API gatewaya | rozmowa bezpośrednia z agentem (sesja HQ, osobna od Telegrama) |
| Panel agenta: O agencie | fleet.yaml, SOUL, skille | opis, model, autonomia, parametry osobowości, workflowy |
| Centrala: Decyzje | kanban (`blocked` + `needs_input`) | pytania agentów; odpowiedź idzie do TARS-a, który odblokowuje kartę i zapisuje decyzję |
| Centrala: Misje | `missions/INDEX.md` + kanban | postęp misji (kostki kart w kolorach stanu) |
| Centrala: Na bieżąco | zdarzenia kanbana | kto zaczął, oddał do oceny, skończył, utknął |

Decyzje świadomie idą przez TARS-a, a nie bezpośrednio do karty: szef zapisuje je w dzienniku misji i pilnuje
reszty (skill `decision-queue` zna format wiadomości z HQ).

## 2. Architektura

```
przeglądarka (Tailscale) ── :9119 dashboard Hermesa (logowanie hasłem)
   └─ zakładka „/” = plugin tars-hq (React z SDK dashboardu + htm, bez kroku budowania po stronie serwera)
        ├─ GET  /api/plugins/tars-hq/state        co 3 s: agenci, tablica, decyzje, misje, zdarzenia
        ├─ GET  /api/plugins/tars-hq/agent/<a>    co 2,5 s przy otwartym panelu: karty, oś kroków, wyniki
        ├─ GET  /api/plugins/tars-hq/task/<id>    karta z historią i komentarzami
        ├─ GET  /api/plugins/tars-hq/file?path=   podgląd pliku z katalogów floty
        ├─ POST /api/plugins/tars-hq/site        link „Odpal” (token) ─► :9120 serwer podglądu stron w pluginie
        ├─ POST /api/plugins/tars-hq/reveal      prośba „Pokaż w folderze” ─► pomocnik hosta (explorer.exe)
        ├─ GET  /api/plugins/tars-hq/chat/<a>/history
        ├─ POST /api/plugins/tars-hq/chat/<a>/send ─► gateway :8642 /p/<agent>/api/sessions/<id>/chat/stream (SSE)
        ├─ POST /api/plugins/tars-hq/chat/<a>/reset
        └─ GET  /api/plugins/tars-hq/health       klucze API profili i dostępność gatewaya
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
| `hq/web/src/*.js` | frontend: podstawy, API, grafika pokoi, budynek, panel, czat, HUD, aplikacja |
| `hq/web/style.css` | styl (tokeny motywu dashboardu, animacje, responsywność) |
| `hq/web/vendor/htm.umd.js` | htm 3.1.1 (Apache-2.0): składnia podobna do JSX bez kompilacji |
| `hq/web/demo/` | strona demo i symulator floty |
| `scripts/hqbuild.py` | build pluginu (sklejenie JS, `fleet.json` z fleet.yaml i SOUL) i demo |

Wdrożenie jest częścią zwykłego `deploy.sh`: `build.py` buduje plugin do `build/plugins/tars-hq`,
`install-fleet.sh` kopiuje go do `/opt/data/plugins/tars-hq`, włącza (Hermes wymaga jawnego włączenia
pluginów użytkownika), generuje brakujące `API_SERVER_KEY` profili i restartuje sam dashboard (s6).

## 3. Bezpieczeństwo

- Wszystkie trasy pluginu są za logowaniem dashboardu (bez sesji: `401 unauthenticated`).
- Dashboard nasłuchuje tylko na IP Tailscale (`TARS_BIND_IP`), hasło generuje bootstrap.
- Klucze API profili zostają na serwerze. Backend pluginu czyta je z `.env` profilu przy każdym wywołaniu.
- Podgląd plików tylko z `/opt/data/tars/{workspaces,missions,knowledge}`, po rozwiązaniu symlinków.
  Pliki wysyłane z nagłówkiem `Content-Security-Policy: sandbox` i `nosniff`, HTML jako zwykły tekst:
  strona wygenerowana przez agenta nie wykona skryptu w sesji dashboardu.
- **▶ Odpal**: strona agenta idzie z osobnego portu 9120 (ten sam `TARS_BIND_IP`), tylko pod adresem z losowym
  tokenem, który wydaje zalogowany dashboard (ważny 12 h, znika przy restarcie). Nagłówek `CSP: sandbox` bez
  `allow-same-origin` daje stronie nieprzezroczyste pochodzenie: jej skrypty działają, ale nie czytają ciasteczek
  i nie wyślą ich do dashboardu. Nowa karta nie ma `window.opener`. Pliki ukryte, `..` i symlinki na zewnątrz: 404.
- **Pokaż w folderze**: dashboard zapisuje tylko prośbę ze ścieżką (`state/reveal-request`); `scripts/updater.py`
  na hoście sprawdza ją ponownie (tylko `tars/{workspaces,missions,knowledge}`) i woła `explorer.exe /select,…`.
- Odczyt kanbana i transkrypcji w trybie SQLite `mode=ro`. HQ niczego nie zapisuje poza mapą sesji czatu
  (`/opt/data/tars/state/hq-sessions.json`); zmiany na tablicy robią agenci przez swoje narzędzia.

## 4. Wieża TARS (wygląd)

Tytuł „TARS HQ”, stan połączenia, liczniki tablicy (w toku, ocena, blokady, kolejka, zrobione dziś) i
przycisk „Decyzje” siedzą w górnym pasku dashboardu Hermesa (kontekst strony wczytany z modułu dashboardu);
gdy go nie ma (np. tryb demo), HQ pokazuje własny pasek nad wieżą. Scena dopasowuje się do wysokości
okna: cała wieża mieści się nad czatem, a nadmiar szerokości wypełnia miasto po bokach.

Scena to **przekrój bazy-wieżowca w pixel arcie**, nocą, jak model z klocków przecięty na pół: płaskie
cięcie konstrukcji, a pokoje mają głębię (tylna ściana, podłoga w perspektywie, meble). Rysunek powstaje
w kodzie (`hq/web/src/20-art.js`) na siatce 400 pikseli logicznych i skaluje się w SVG bez rozmycia.

- **Dach:** neon „TARS”, antena z migającym światłem, talerz, zbiornik na wodę.
- **Mostek dowodzenia** (`bridge`): **TARS jako szef w garniturze** (postać 2× większa od załogi) za
  pulpitem dowodzenia, fotel dyrektorski, okno na miasto, ekran „Tablica floty” (liczniki kanbana na żywo),
  panel „Załoga” z lampką statusu każdego agenta, robot-monolit TARS (pracuje, gdy flota pracuje).
- **Piętra załogi:** po dwa pokoje na piętro wokół szybu windy; winda jeździ, gdy ktoś pracuje. Przy
  nieparzystej liczbie agentów wolne miejsce zajmuje magazyn. Nowi agenci dokładają piętra.
- **Maszynownia** (piwnica pod ulicą): szafy serwerowe i rdzeń zasilania; zielony „GATEWAY ONLINE”,
  czerwony, gdy HQ traci połączenie z flotą.

Pokój przypisuje `hq_room` w `fleet.yaml`, a krótką nazwę na szyldzie `hq_short`:

| `hq_room` | Wystrój | Postać |
|---|---|---|
| `bridge` | jak wyżej | szef TARS: czarny garnitur, biała koszula, czerwony krawat |
| `study` | regał z książkami, tablica dowodów z czerwonymi nitkami, zegar, globus, biurko z lampą bankierską | detektyw w kaszkiecie i szaliku (lupa przy pracy) |
| `devlab` | szafa serwerowa z diodami, tablica z makietą, neon `</>`, dwa monitory z kodem, kubek z parą | programista w bluzie i słuchawkach, tyłem przy monitorach |
| `atelier` | turkusowe tło fotograficzne, softbox, kamera z lampką REC, sztaluga z obrazem, plakat, klaps | artystka w berecie i koszulce w paski (paleta przy pracy) |
| `workshop` | tablica z narzędziami, stół z imadłem i ramieniem robota, skrzynie (liczba = kolejka kart), beczka | mechanik w kasku i ogrodniczkach, tyłem przy stole |
| `office` | domyślny pokój dla nowych agentów: biurko, monitor, szafka, zegar | postać w krawacie |

Stan agenta zmienia pokój: światło (pokój przygasa, gdy agent jest wolny), pozę (praca, trzymana karta
przy ocenie, uniesiona ręka i „!” przy blokadzie, „Z z z”, gdy śpi) i rekwizyty (monitory, lampa, ramię
robota, nagrywanie, hologram na pulpicie szefa). Animacje są skokowe jak w grach (kilka klatek) i
wyłączają się przy `prefers-reduced-motion`. Na wąskim ekranie wieżę przesuwa się w bok palcem.

**Nowy pokój:** dodaj klucz w `ROOMS` i funkcję wnętrza (`ROOM_DRAW`) w `hq/web/src/20-art.js`, wygląd
postaci w `LOOKS`, wpisz klucz do `HQ_ROOMS` w `scripts/fleetlib.py` (walidator pilnuje zgodności)
i ustaw `hq_room` agenta.

## 5. Motyw „Fosfor” (wygląd całego dashboardu)

Cały dashboard (menu, górny pasek, czat, TARS HQ) wygląda jak terminal CRT z 1982: czcionki VT323 i IBM Plex
Mono, linie skanowania, numerowane menu, podświetlenie w negatywie. Wieża zostaje w swoich kolorach.

- **Jeden kolor → cały wygląd.** `scripts/install_themes.py` liczy z niego odcienie, tło, ramki i poświatę,
  a z `branding/fosfor/theme.css` składa motywy Hermesa w `<HERMES_HOME>/dashboard-themes/`.
- **Zmiana koloru:** przełącznik motywów w lewym dolnym rogu (błękit, bursztyn, zieleń, biel). Własny kolor:
  dopisz linię w `branding/fosfor/palettes.yaml` i wdroż. Wybór zrobiony w dashboardzie przetrwa wdrożenia.
- Kolory terminala czatu idą z motywu (łatka w `branding/patch_dashboard.py`), skórka TUI jest w błękicie.

## 6. Rozwiązywanie problemów

| Objaw | Przyczyna i naprawa |
|---|---|
| brak zakładki BASE w menu | plugin nie jest włączony albo dashboard nie wstał po instalacji: `docker exec -u hermes tars-hermes /command/s6-svc -r /run/service/dashboard` |
| czat: „Profil … nie ma API_SERVER_KEY” | uruchom deploy ponownie (instalator generuje klucze) |
| czat: „Gateway odrzucił klucz” | klucz w `.env` profilu zmieniony bez restartu gatewaya: `hermes gateway restart` |
| czat: „No LLM provider configured” | profil nie ma `OPENROUTER_API_KEY` w `/srv/tars/secrets/<agent>.env` |
| pokój „Pracuje”, ale dymek „cisza…” | pracownik nie wysłał sygnału od 3 min; szczegóły w panelu, patrol zgłosi problem sam |
| „▶ Odpal” otwiera pustą kartę / „nie można połączyć” | port 9120 nieopublikowany: kontener sprzed tej wersji, `bash scripts/local-up.sh` (lokalnie) albo `deploy.sh` go odtworzy |
| brak „Pokaż w folderze”, jest „Kopiuj ścieżkę” | pomocnik hosta nie działa albo to nie WSL: `bash scripts/local-up.sh` (uruchamia `scripts/updater.py`) |
| `/api/plugins/tars-hq/health` | pokazuje, czy każdy profil ma klucz i czy gateway odpowiada na `/p/<agent>` |
