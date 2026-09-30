# Jarvo na VPS: infrastruktura

Cel: jedna maszyna, na której cała flota działa 24/7. Jest bezpieczna, ma backupy,
monitoring i przewidywalne wdrożenia. Opiera się na oficjalnym obrazie Docker Hermesa
(`nousresearch/hermes-agent`), który ma wbudowany supervisor s6: jeden kontener obsługuje
wszystkie profile przez jeden multipleksowany gateway, a s6 pilnuje i restartuje gateway i dashboard.

---

## 1. Topologia

```
                    Internet
                       │  (brak otwartych portów; SSH tylko do czasu Tailscale)
        ┌──────────────┴──────────────────────────────────────────────┐
        │ VPS (Ubuntu LTS, Docker)                                     │
        │                                                              │
        │  ┌───────────────────────────────┐    sieć wewnętrzna jarvo-net│
        │  │ jarvo-hermes (nasz obraz)      │◄──────────┐                │
        │  │  FROM nousresearch/hermes-agent│           │                │
        │  │  + toolbox (lighthouse, sharp, │      ┌────┴───┐            │
        │  │    pandoc, ocr, parakeet, …)  │      │searxng │            │
        │  │  przeglądarki: Lightpanda +   │      │+valkey │            │
        │  │    1× Chromium (render/PDF)   │      └────────┘            │
        │  │  s6: gateway (multipleks)     │                            │
        │  │  profile: jarvo, jarvo-web,   │                            │
        │  │  jarvo-sherlock, jarvo-studio,│                            │
        │  │  jarvo-wideo, jarvo-ads,      │                            │
        │  │  jarvo-reka                   │                            │
        │  └──────────────┬────────────────┘   później: honcho, postiz  │
        │        /opt/data (wolumen)           monitoring (opcja):      │
        │                                      uptime-kuma, beszel      │
        │  Tailscale ◄── Ty: SSH, dashboard Hermesa, desktop app       │
        └──────────────────────────────────────────────────────────────┘
                       │
      Telegram (long polling, wychodzące) ── Ty na telefonie
```

Kluczowe decyzje:
- **Jeden kontener Hermesa, wiele profili.** Tak rekomenduje dokumentacja Hermesa: wspólny cache,
  jeden katalog do backupu, jeden gateway (`gateway.multiplex_profiles`) pod nadzorem s6.
- **Nasz obraz pochodny:** `FROM nousresearch/hermes-agent:<wersja>` + narzędzia z `toolbox.yaml`
  wszystkich agentów. Budowany przez `infra/Dockerfile` z `HERMES_IMAGE` z `compose/.env` (domyślnie
  `:latest`; po pierwszym wdrożeniu `scripts/pin-images.sh` przypina go do digestu).
- **Sidecar tylko wtedy, gdy musi być usługą** (SearXNG). Ekstrakcja stron i PDF działają w obrazie
  na żądanie (trafilatura, Lightpanda, pandoc + Chromium): proces żyje tylko na czas zadania, więc
  w spoczynku nie zajmuje RAM-u. Tak cała flota mieści się na VPS z 8 GB.
- **Kontener Hermesa jest sandboxem.** Agenci wykonują komendy wewnątrz kontenera (backend
  `local` w kontenerze) i nie dostają gniazda Dockera, które dawałoby im władzę nad hostem
  (`infra/docker-compose.yml` go nie montuje).
- **Telegram nie wymaga otwartych portów:** gateway łączy się wychodząco (long polling).
- **Panele i SSH tylko przez Tailscale.** Z zewnątrz nic nie jest widoczne.

---

## 2. Rozmiar serwera

Bez GPU. Generowanie obrazów i wideo AI idzie przez API (OpenRouter), a lokalnie liczymy tylko
rendering kodu (FFmpeg, HyperFrames), przeglądarki, transkrypcję i usługi.

**Cel: VPS 4 vCPU / 8 GB RAM / 80 GB NVMe dla całej floty (7 agentów).**

| | Zmierzone (Docker, Hermes 0.21.5) |
|---|---|
| obraz `jarvo-hermes` | **4,4 GB** (z tego 2,7 GB to sam obraz Hermesa) + SearXNG 0,26 GB + Valkey 0,04 GB |
| dysk na start | ok. **6 GB**: obrazy + model mowy 0,65 GB (pobierany przy pierwszej wiadomości głosowej) |
| RAM w spoczynku | **ok. 0,7 GB**: gateway 350 MB, dashboard 185 MB, SearXNG 130 MB, Valkey 6 MB |

RAM narzędzi zmierzony w kontenerze (szczyt, proces żyje tylko na czas zadania):

| Zadanie | RAM | Czas |
|---|---|---|
| przeglądanie przez Lightpandę (agent-browser, strona z ciężkim JS) | ~35 MB | 0,4 s |
| to samo w Chromium (zrzuty ekranu, trudne strony) | ~100–250 MB | 0,9 s |
| Lighthouse, 1 strona mobile | ~340 MB | 11 s |
| transkrypcja Parakeet (36 s wideo → tekst/SRT, 2 wątki CPU) | ~1,1–1,3 GB | 10–12 s |
| dembrandt (tokeny marki ze strony) | ~170 MB | 9 s |
| Markdown → PDF (pandoc + Chromium) | ~70 MB | 0,4 s |
| pracownik kanbana (proces Hermesa z agentem) | ~250–350 MB (szac.) | cały czas trwania karty |

**Budżet 8 GB (najgorszy realny przypadek naraz):** spoczynek 0,7 + 3 pracowników 1,0 + przeglądarki 0,4 +
Lighthouse 0,35 + transkrypcja 1,2 ≈ **3,7 GB**. Sufity w compose: Hermes 5 GB, SearXNG 384 MB, Valkey 96 MB.
Bezpieczniki: `kanban.max_in_progress: 3` (bez tego Hermes liczy 8 pracowników z RAM hosta),
`max_in_progress_per_profile: 2`, `delegation.max_concurrent_children` 2–3, jedna transkrypcja naraz
(blokada w `jarvo-stt`), swap 4 GB (`bootstrap-vps.sh`, swappiness 10).

| Etap | CPU | RAM | Dysk | Co działa |
|---|---|---|---|---|
| Flota v1 (cała) | 4 vCPU | **8 GB** | 80 GB NVMe | 7 agentów, SearXNG, Lighthouse, PDF, transkrypcja, render wideo (FFmpeg, chwilowo 0,5–0,65 GB); monitoring (+0,2 GB) |
| + dodatki obrazu | 4 vCPU | 8 GB | 80 GB | `JARVO_EXTRAS` (niżej): zwiększa dysk, nie RAM w spoczynku |
| + Langfuse / Honcho | 8 vCPU | 16 GB | 160 GB+ | self-hostowane ślady i pamięć (ClickHouse i Postgres są pamięciożerne) |

**Dodatki obrazu** (`JARVO_EXTRAS` w `compose/.env`, potem `deploy.sh --rebuild`), domyślnie wyłączone:

| Dodatek | Co daje | Dysk |
|---|---|---|
| `rembg` | wycinanie tła ze zdjęć (Studio) | ~0,5 GB + model 170 MB |
| `media` | auto-editor: automatyczne cięcie ciszy w nagraniach | ~0,2 GB |
| `office` | LibreOffice: XLSX/PPTX/DOC → PDF | ~0,5 GB |
| `docling` | PDF/DOCX → Markdown z modelami ML (tabele, układ) | ~1–2 GB |
| `manim` | animacje matematyczne (+ LaTeX) | ~1 GB |
| `lemo` | Wideograf: sample instrumentów i głos Kokoro (EN/ZH) dla lemo-opuscar; bez przebudowy obrazu: `narzedzia.py instaluj lemo` w działającym kontenerze | ~1,7 GB w `/opt/data` |

Co zmieniliśmy względem pierwszej wersji (9,5 GB obrazu, sidecary 5 GB, limit 10 GB RAM):
- **Gotenberg** (LibreOffice + Chromium w osobnym kontenerze, 1,7 GB) → `to_pdf.py`: pandoc + Chromium z obrazu;
  LibreOffice tylko jako dodatek `office`.
- **Crawl4AI** (drugi Chromium + Python, ~3 GB obrazu, do 3 GB RAM) → trafilatura (`extract.py`), `web_extract`
  Hermesa i Lightpanda (`lightpanda fetch --dump markdown <url>`).
- **faster-whisper** → **Parakeet TDT 0.6B v3** (int8, ONNX, 25 języków z polskim): lepszy polski,
  uruchamiany na żądanie jako komenda STT Hermesa, 0 MB w spoczynku.
- **Chromium dla agentów → Lightpanda** (przeglądarka w Zig: ~30 MB na sesję, 3–5× mniej niż Chromium);
  Chromium zostaje jeden, z obrazu Hermesa, do zrzutów, PDF i Lighthouse. Wyleciały dwie dodatkowe kopie
  Chromium (dembrandt) i pakiety z własną przeglądarką (Unlighthouse, critical).
- Obraz: bez cache instalatorów w warstwach (1,9 GB), bez `chmod -R` (duplikował 2,7 GB), bez bibliotek ML
  dembrandta dla nieużywanej flagi `--ai` (0,5 GB).

Rekomendacje:
- **x86_64**, nie ARM: część narzędzi medialnych i buildów łatwiej działa na x86,
- **region UE** (Polska/Niemcy): niskie opóźnienia i RODO,
- dysk rośnie głównie przez wideo i workspace’y, więc stare rendery sprzątamy rutyną cron;
  `deploy.sh --rebuild` usuwa poprzedni obraz i stary cache budowania.

---

## 3. Układ katalogów na VPS

```
/srv/jarvo/
├── repo/                 # klon tego repo → /opt/jarvo/repo (tylko do odczytu w kontenerze)
├── compose/              # .env compose (obrazy, sekrety usług, JARVO_BIND_IP) + jarvo.env (ID Telegrama, dostawca modeli)
├── secrets/              # host.env i <agent>.env (klucze) → /opt/jarvo/secrets (ro), grupa 10000, 2750/640
├── restic.env            # dane dostępowe backupu (root, 600), poza kontenerem
├── build/                # wynik scripts/build.py → /opt/jarvo/build (ro): dystrybucje profili, config hosta
├── data/
│   ├── hermes/           # → /opt/data: profile, pamięć, sesje, kanban.db, cron
│   │   └── jarvo/         # missions/ (dziennik misji), workspaces/<agent>/, knowledge/ (brand kity, USER.md), state/
│   ├── valkey/  uptime-kuma/  beszel/
├── staging/              # izolowane dane do evals (scripts/evals-staging.sh)
└── backups/              # staging kopii SQLite, logi backupu i testu odtworzenia
```

---

## 4. Usługi (docker compose)

| Usługa | Po co | Licencja | Stan |
|---|---|---|---|
| `jarvo-hermes` | agent, gateway, wszystkie profile, dashboard (hasło) | MIT | ✅ w compose |
| `searxng` (+ `valkey`) | darmowa metawyszukiwarka (JSON) dla Sherlocka i Jarva | AGPL-3.0 | ✅ w compose |
| ~~`crawl4ai`~~ | zastąpiony: trafilatura + Lightpanda w obrazie (bez stałego kontenera) | | ❌ usunięty (RAM) |
| ~~`gotenberg`~~ | zastąpiony: `to_pdf.py` (pandoc + Chromium, LibreOffice jako dodatek) | | ❌ usunięty (RAM) |
| `uptime-kuma` | healthchecki i alerty | MIT | ✅ profil `monitoring` |
| `beszel` (+ agent) | CPU/RAM/dysk, alerty | MIT | ✅ profil `monitoring` |
| `honcho` (+ postgres/pgvector) | wspólna pamięć o Tobie | AGPL-3.0 | ⬜ faza 3, jeśli MVP pamięci nie wystarczy |
| `postiz` (+ postgres, redis) | kolejka publikacji social media po Twojej akceptacji | AGPL-3.0 | ⬜ gdy Studio zacznie publikować |
| `langfuse` | ślady, koszty, oceny sędziego | MIT (core) | ⬜ faza 6 |
| `caddy` | HTTPS, tylko jeśli coś musi być publiczne (podglądy stron, webhooki) | Apache-2.0 | ⬜ w razie potrzeby |

Licencje AGPL/GPL są bezpieczne przy **prywatnym self-hostingu** (nie rozpowszechniamy
zmodyfikowanych wersji). Szczegóły: [TOOLBOX.md](TOOLBOX.md#polityka-licencji).

---

## 5. Bezpieczeństwo

**System:**
- Ubuntu LTS, `unattended-upgrades`, strefa czasowa Europe/Warsaw,
- użytkownik `jarvo` bez roota, logowanie SSH tylko kluczem, `PermitRootLogin no`,
- po postawieniu Tailscale: SSH tylko w sieci Tailscale, a publiczny port 22 zamknięty,
- firewall (UFW): domyślnie blokada ruchu przychodzącego; 80/443 otwarte tylko, gdy działa Caddy,
- fail2ban na SSH (bootstrap); CrowdSec, jeśli kiedyś wystawimy Caddy.

**Agenci:**
- zatwierdzanie ryzykownych komend w Hermesie **włączone**,
- **poziomy autonomii** z [PROFILE-SPEC.md](PROFILE-SPEC.md#9-granice-autonomia-uprawnienia-sandbox):
  wdrożenia, publikacje i wydatki wymagają Twojej zgody,
- **treści z internetu to niezaufane dane.** Sherlock i Web czytają obce strony (ryzyko prompt injection),
  dlatego żaden agent czytający sieć nie wykonuje akcji A2 bez zgody człowieka,
- Telegram: bot odpowiada tylko Tobie (allowlista ID użytkownika w Hermesie),
- workspace’y agentów rozdzielone, repo montowane tylko do odczytu,
- **skille z cudzych repo** przechodzą przy każdym buildzie skan bezpieczeństwa (skaner Hermesa + wzorce getsentry
  i ECC); nowa wersja źródła w locku = przegląd ustaleń od nowa ([SOURCES.md](SOURCES.md#2-skille-dołączane-do-agentów-vendoring)).

**Sekrety:**
- tylko w `.env` profili (uprawnienia `0600`), nigdy w git,
- **osobny klucz OpenRouter dla każdego agenta z limitem kredytów** (obrazy i wideo AI, a przy zestawie
  `openrouter` także modele). Widać koszt per agent, a wyciek jednego klucza ma ograniczony zasięg.
  Agent bez własnego klucza dostaje klucz hosta (`scripts/share_keys.py`, blok „klucze wspólne”),
- backupy szyfrowane (restic szyfruje domyślnie), a hasło do repozytorium backupu trzymasz poza VPS,
- **granica zaufania:** wszyscy agenci działają w jednym kontenerze jako ten sam użytkownik (`hermes`),
  więc agent z terminalem technicznie może przeczytać klucze innych agentów. Łagodzą to limity na kluczach,
  zgody na ryzykowne komendy i to, że dane dostępowe backupu (`/srv/jarvo/restic.env`) w ogóle nie trafiają
  do kontenera, a `compose/.env` nie jest w nim montowany (trafiają z niego tylko login, hasło i sekret sesji
  dashboardu jako zmienne `HERMES_DASHBOARD_BASIC_AUTH_*`). Pełna izolacja kluczy wymagałaby osobnych kontenerów per agent.

---

## 6. Backupy

- **Co:** `data/hermes` (profile, pamięć, sesje, misje, wiedza, workspace’y bez cache i `node_modules`),
  bazy SQLite (`state.db`, `kanban.db`…) jako spójne kopie online (`sqlite3 .backup`), `compose/` i `secrets/`.
  Dumpy Postgresa dojdą razem z Honcho/Postiz. Skrypt: `scripts/backup.sh`.
- **Czym:** restic → magazyn S3-kompatybilny poza VPS (inny dostawca albo region).
- **Kiedy:** co noc, retencja 7 dziennych / 4 tygodniowe / 12 miesięcznych.
- **Test odtworzenia:** raz w miesiącu `scripts/restore-test.sh` odtwarza ostatni snapshot do katalogu
  tymczasowego i sprawdza kluczowe pliki (wynik w logu). Backup, którego nikt nie odtworzył, nie jest backupem.

---

## 7. Monitoring i koszty

- **Beszel:** zasoby serwera, alert przy dysku > 80% i RAM > 90%,
- **Uptime Kuma:** monitory dashboardu (9119) i SearXNG; „heartbeat” z crona Hermesa (brak sygnału = alert) jeszcze nie jest zbudowany,
- **Hermes:** `hermes doctor`, `hermes logs --follow`, `/usage`, `/insights`,
- **koszty:** plan ChatGPT (domyślne modele `openai-codex`), limity na kluczach OpenRouter (obrazy, wideo, zestaw
  `openrouter`) + tygodniowy raport kosztów per agent od Jarva,
- **Langfuse (faza 6):** każdy przebieg agenta, koszt, czas, oceny sędziego i regresje jakości.

---

## 8. Wdrożenia i aktualizacje

```
laptop / sesja dev ──git push──► GitHub ──git pull──► VPS: scripts/deploy.sh
```

`scripts/deploy.sh` (idempotentny; szczegóły w [RUNBOOK.md](RUNBOOK.md)):
1. `git pull --ff-only` w `/srv/jarvo/repo`,
2. przebudowa obrazu, gdy zmienił się `infra/Dockerfile`, `infra/node/`, `infra/python/` albo `infra/bin/` (wtedy też
   z pobraniem nowego obrazu bazowego) lub `branding/` (albo `--rebuild`),
3. `docker compose up -d`,
4. walidacja repo w kontenerze (`scripts/validate.py`); błąd zatrzymuje wdrożenie przed zmianą floty,
5. build dystrybucji (`scripts/build.py`): SOUL z protokołem, tokeny modeli, roster, rubryki, skille zewnętrzne, cron,
   config hosta z trasami Telegrama; skan skilli zewnętrznych (`scripts/skan_skilli.py`) zatrzymuje wdrożenie
   przy ustaleniu high/critical bez wyjątku w `vendor/skan-wyjatki.yaml`,
6. `install-fleet.sh` w kontenerze: config i sekrety hosta, `hermes profile install/update` każdego agenta,
   usunięcie skilli wycofanych z repo, sekrety agentów, tablica kanban, restart gatewaya (przez s6),
7. healthchecki narzędzi z `toolbox.yaml`.

**Staging:** `scripts/evals-staging.sh` uruchamia jednorazowy kontener z tym samym obrazem i buildem, ale na
osobnym katalogu danych (`/srv/jarvo/staging`) i bez gatewaya, więc scenariusze evals nie ruszają produkcyjnej
tablicy ani Telegrama. Osobny bot testowy dojdzie, gdy będziemy testować routing Telegrama przed zmianą tras.

**Wersje:** Hermes przypięty do digestu obrazu (`HERMES_IMAGE` w `compose/.env`, zapisuje go `scripts/pin-images.sh`;
bez tego `:latest`). Aktualizacja Hermesa to świadoma decyzja (np. raz w miesiącu): najpierw staging, potem produkcja.
Rollback: poprzedni tag repo + `deploy.sh --no-pull --rebuild` na przypiętym `HERMES_IMAGE` (poprzedni obraz
`jarvo-hermes` przebudowa usuwa).

---

## 9. Dostęp dla Ciebie

| Kanał | Jak |
|---|---|
| Telegram | grupa „Jarvo HQ” z wątkami per agent (routing `profile_routes`), plus DM z Jarvem |
| Terminal | SSH przez Tailscale → `docker exec -it -u hermes jarvo-hermes hermes -p jarvo-web chat` (alias `jarvo-web`) |
| Desktop | aplikacja Hermes Desktop połączona ze zdalnym backendem przez Tailscale: Bot Mode, czat grupowy floty |
| Dashboard | panel web Hermesa (profile, skille, cron, kanban) tylko przez Tailscale |

---

## 10. Postawienie serwera

Krok po kroku, z komendami: [RUNBOOK.md](RUNBOOK.md).
