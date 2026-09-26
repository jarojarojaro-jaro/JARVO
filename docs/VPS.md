# TARS na VPS: infrastruktura

Cel: jedna maszyna, na której cała flota działa 24/7. Jest bezpieczna, ma backupy,
monitoring i przewidywalne wdrożenia. Opiera się na oficjalnym obrazie Docker Hermesa
(`nousresearch/hermes-agent`), który ma wbudowany supervisor s6: jeden kontener obsługuje
wiele profili, a każdy gateway jest pilnowany i restartowany osobno.

---

## 1. Topologia

```
                    Internet
                       │  (brak otwartych portów; SSH tylko do czasu Tailscale)
        ┌──────────────┴──────────────────────────────────────────────┐
        │ VPS (Ubuntu LTS, Docker)                                     │
        │                                                              │
        │  ┌───────────────────────────────┐    sieć wewnętrzna tars-net│
        │  │ tars-hermes (nasz obraz)      │◄──────────┬──────────┐     │
        │  │  FROM nousresearch/hermes-agent│           │          │     │
        │  │  + toolbox (lighthouse, sharp, │      ┌────┴───┐ ┌────┴───┐ │
        │  │    pandoc, ocr, whisper, …)   │      │searxng │ │crawl4ai│ │
        │  │  s6: gateway (multipleks)     │      │+valkey │ └────────┘ │
        │  │  profile: tars, tars-web,     │      └────────┘ ┌────────┐ │
        │  │  tars-sherlock, tars-studio,  │                 │gotenberg│ │
        │  │  tars-reka                    │                 └────────┘ │
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
  jeden katalog do backupu, s6 restartuje każdy gateway osobno.
- **Nasz obraz pochodny:** `FROM nousresearch/hermes-agent:<wersja>` + narzędzia z `toolbox.yaml`
  wszystkich agentów. Budowany przez `infra/Dockerfile`, przypięty do konkretnej wersji Hermesa.
- **Ciężkie usługi jako sidecary** (osobne kontenery w sieci `tars-net`), a Hermes łączy się z nimi po nazwie.
- **Kontener Hermesa jest sandboxem.** Agenci wykonują komendy wewnątrz kontenera (backend
  `local` w kontenerze) i nie dostają gniazda Dockera, które dawałoby im władzę nad hostem
  (`infra/docker-compose.yml` go nie montuje).
- **Telegram nie wymaga otwartych portów:** gateway łączy się wychodząco (long polling).
- **Panele i SSH tylko przez Tailscale.** Z zewnątrz nic nie jest widoczne.

---

## 2. Rozmiar serwera

Bez GPU. Generowanie obrazów i wideo AI idzie przez API (OpenRouter), a lokalnie liczymy tylko
rendering kodu (FFmpeg, HyperFrames, Manim), przeglądarki, transkrypcję i usługi.

| Etap | CPU | RAM | Dysk | Co działa |
|---|---|---|---|---|
| MVP (faza 1) | 4 vCPU | 8 GB | 80 GB NVMe | Hermes + TARS + Sherlock, SearXNG, Crawl4AI |
| Flota v1 | 8 vCPU | 16 GB | 160–240 GB NVMe | + Web (Chromium, Lighthouse), Studio (render wideo), monitoring; później Honcho, Postiz |
| Flota v1 + Langfuse | 8 vCPU | 32 GB | 240 GB+ NVMe | + self-hostowany Langfuse (ClickHouse jest pamięciożerny) |

Rekomendacje:
- **x86_64**, nie ARM: część narzędzi medialnych i buildów łatwiej działa na x86,
- **region UE** (Polska/Niemcy): niskie opóźnienia i RODO,
- dysk rośnie głównie przez wideo i workspace’y, więc stare rendery sprzątamy rutyną cron.

---

## 3. Układ katalogów na VPS

```
/srv/tars/
├── repo/                 # klon tego repo → /opt/tars/repo (tylko do odczytu w kontenerze)
├── compose/              # .env compose (obrazy, sekrety usług, TARS_BIND_IP) + tars.env (ID Telegrama)
├── secrets/              # host.env i <agent>.env (klucze) → /opt/tars/secrets (ro), grupa 10000, 2750/640
├── restic.env            # dane dostępowe backupu (root, 600), poza kontenerem
├── build/                # wynik scripts/build.py → /opt/tars/build (ro): dystrybucje profili, config hosta
├── data/
│   ├── hermes/           # → /opt/data: profile, pamięć, sesje, kanban.db, cron
│   │   └── tars/         # missions/ (dziennik misji), workspaces/<agent>/, knowledge/ (brand kity, USER.md), state/
│   ├── valkey/  uptime-kuma/  beszel/
├── staging/              # izolowane dane do evals (scripts/evals-staging.sh)
└── backups/              # staging kopii SQLite, logi backupu i testu odtworzenia
```

---

## 4. Usługi (docker compose)

| Usługa | Po co | Licencja | Stan |
|---|---|---|---|
| `tars-hermes` | agent, gateway, wszystkie profile, dashboard (hasło) | MIT | ✅ w compose |
| `searxng` (+ `valkey`) | darmowa metawyszukiwarka (JSON) dla Sherlocka i TARS-a | AGPL-3.0 | ✅ w compose |
| `crawl4ai` | ekstrakcja stron do Markdown | Apache-2.0 | ✅ w compose |
| `gotenberg` | HTML/Markdown/Office → PDF dla prawej ręki | MIT | ✅ w compose |
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
- użytkownik `tars` bez roota, logowanie SSH tylko kluczem, `PermitRootLogin no`,
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
- workspace’y agentów rozdzielone, repo montowane tylko do odczytu.

**Sekrety:**
- tylko w `.env` profili (uprawnienia `0600`), nigdy w git,
- **osobny klucz OpenRouter dla każdego agenta z limitem kredytów.** Widać koszt per agent,
  a wyciek jednego klucza ma ograniczony zasięg,
- backupy szyfrowane (restic szyfruje domyślnie), a hasło do repozytorium backupu trzymasz poza VPS,
- **granica zaufania:** wszyscy agenci działają w jednym kontenerze jako ten sam użytkownik (`hermes`),
  więc agent z terminalem technicznie może przeczytać klucze innych agentów. Łagodzą to limity na kluczach,
  zgody na ryzykowne komendy i to, że dane dostępowe backupu (`/srv/tars/restic.env`) oraz `compose/.env`
  w ogóle nie trafiają do kontenera. Pełna izolacja kluczy wymagałaby osobnych kontenerów per agent.

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
- **Uptime Kuma:** healthchecki sidecarów + „heartbeat” z crona Hermesa (brak sygnału = alert),
- **Hermes:** `hermes doctor`, `hermes logs --follow`, `/usage`, `/insights`,
- **koszty:** limity na kluczach OpenRouter + tygodniowy raport kosztów per agent od TARS-a,
- **Langfuse (faza 6):** każdy przebieg agenta, koszt, czas, oceny sędziego i regresje jakości.

---

## 8. Wdrożenia i aktualizacje

```
laptop / sesja dev ──git push──► GitHub ──git pull──► VPS: scripts/deploy.sh
```

`scripts/deploy.sh` (idempotentny; szczegóły w [RUNBOOK.md](RUNBOOK.md)):
1. `git pull --ff-only` w `/srv/tars/repo`,
2. przebudowa obrazu, gdy zmienił się `infra/Dockerfile`, `infra/node/` albo `infra/python/` (albo `--rebuild`),
3. `docker compose up -d`,
4. walidacja repo w kontenerze (`scripts/validate.py`); błąd zatrzymuje wdrożenie przed zmianą floty,
5. build dystrybucji (`scripts/build.py`): SOUL z protokołem, tokeny modeli, roster, rubryki, skille zewnętrzne, cron,
   config hosta z trasami Telegrama,
6. `install-fleet.sh` w kontenerze: config i sekrety hosta, `hermes profile install/update` każdego agenta,
   usunięcie skilli wycofanych z repo, sekrety agentów, tablica kanban, restart gatewaya (przez s6),
7. healthchecki narzędzi z `toolbox.yaml`.

**Staging:** `scripts/evals-staging.sh` uruchamia jednorazowy kontener z tym samym obrazem i buildem, ale na
osobnym katalogu danych (`/srv/tars/staging`) i bez gatewaya, więc scenariusze evals nie ruszają produkcyjnej
tablicy ani Telegrama. Osobny bot testowy dojdzie, gdy będziemy testować routing Telegrama przed zmianą tras.

**Wersje:** Hermes przypięty do wersji albo digestu obrazu. Aktualizacja Hermesa to świadoma decyzja
(np. raz w miesiącu): najpierw staging, potem produkcja. Rollback: poprzedni tag repo i poprzedni obraz.

---

## 9. Dostęp dla Ciebie

| Kanał | Jak |
|---|---|
| Telegram | grupa „TARS HQ” z wątkami per agent (routing `profile_routes`), plus DM z TARS-em |
| Terminal | SSH przez Tailscale → `docker exec -it tars-hermes hermes -p tars-web chat` (alias `tars-web`) |
| Desktop | aplikacja Hermes Desktop połączona ze zdalnym backendem przez Tailscale: Bot Mode, czat grupowy floty |
| Dashboard | panel web Hermesa (profile, skille, cron, kanban) tylko przez Tailscale |

---

## 10. Postawienie serwera

Krok po kroku, z komendami: [RUNBOOK.md](RUNBOOK.md).
