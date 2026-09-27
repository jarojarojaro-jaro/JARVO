# TARS HQ: kwatera floty (GUI)

TARS HQ to strona główna dashboardu Hermesa (`http://<ip-tailscale>:9119`, logowanie jak do dashboardu).
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
| Panel agenta: Wyniki | katalogi robocze | pliki z `out/`: miniatury grafik, podgląd tekstu, PDF, wideo |
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
| `hq/plugin/manifest.json` | manifest pluginu dashboardu (zakładka zastępuje stronę główną) |
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
- Odczyt kanbana i transkrypcji w trybie SQLite `mode=ro`. HQ niczego nie zapisuje poza mapą sesji czatu
  (`/opt/data/tars/state/hq-sessions.json`); zmiany na tablicy robią agenci przez swoje narzędzia.

## 4. Wieża TARS (wygląd)

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

## 5. Rozwiązywanie problemów

| Objaw | Przyczyna i naprawa |
|---|---|
| strona główna dashboardu nie pokazuje HQ | plugin nie jest włączony albo dashboard nie wstał po instalacji: `docker exec -u hermes tars-hermes /command/s6-svc -r /run/service/dashboard` |
| czat: „Profil … nie ma API_SERVER_KEY” | uruchom deploy ponownie (instalator generuje klucze) |
| czat: „Gateway odrzucił klucz” | klucz w `.env` profilu zmieniony bez restartu gatewaya: `hermes gateway restart` |
| czat: „No LLM provider configured” | profil nie ma `OPENROUTER_API_KEY` w `/srv/tars/secrets/<agent>.env` |
| pokój „Pracuje”, ale dymek „cisza…” | pracownik nie wysłał sygnału od 3 min; szczegóły w panelu, patrol zgłosi problem sam |
| `/api/plugins/tars-hq/health` | pokazuje, czy każdy profil ma klucz i czy gateway odpowiada na `/p/<agent>` |
