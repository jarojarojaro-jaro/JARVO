# TARS na VPS: infrastruktura

Cel: jedna maszyna, na której cała flota działa 24/7. Jest bezpieczna, ma backupy,
monitoring i przewidywalne wdrożenia. Opiera się na oficjalnym obrazie Docker Hermesa
(`nousresearch/hermes-agent`), który ma wbudowany supervisor s6: jeden kontener obsługuje
wiele profili, a każdy gateway jest pilnowany i restartowany osobno.

---

## 1. Topologia

```
                    Internet
                       │  (brak otwartych portów poza opcjonalnym 443)
        ┌──────────────┴──────────────────────────────────────────────┐
        │ VPS (Ubuntu LTS, Docker)                                     │
        │                                                              │
        │  ┌───────────────────────────────┐    sieć wewnętrzna tars-net│
        │  │ tars-hermes (nasz obraz)      │◄──────────┬──────────┐     │
        │  │  FROM nousresearch/hermes-agent│           │          │     │
        │  │  + toolbox (ffmpeg, lighthouse,│      ┌────┴───┐ ┌────┴───┐ │
        │  │    playwright, yt-dlp, …)     │      │searxng │ │crawl4ai│ │
        │  │  s6: gateway (multipleks)     │      └────────┘ └────────┘ │
        │  │  profile: tars, tars-web,     │      ┌────────┐ ┌────────┐ │
        │  │  tars-sherlock, tars-studio,  │      │ honcho │ │ postiz │ │
        │  │  tars-reka                    │      │+postgres│ │+pg+redis│
        │  └──────────────┬────────────────┘      └────────┘ └────────┘ │
        │        /opt/data (wolumen)              monitoring: beszel,   │
        │                                         uptime-kuma           │
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
  `local` w kontenerze) i nie dostają gniazda Dockera, które dawałoby im władzę nad hostem.
  Do potwierdzenia w fazie 0 (ADR).
- **Telegram nie wymaga otwartych portów:** gateway łączy się wychodząco (long polling).
- **Panele i SSH tylko przez Tailscale.** Z zewnątrz nic nie jest widoczne.

---

## 2. Rozmiar serwera

Bez GPU. Generowanie obrazów i wideo AI idzie przez API (OpenRouter), a lokalnie liczymy tylko
rendering kodu (FFmpeg, HyperFrames, Manim), przeglądarki, transkrypcję i usługi.

| Etap | CPU | RAM | Dysk | Co działa |
|---|---|---|---|---|
| MVP (faza 1) | 4 vCPU | 8 GB | 80 GB NVMe | Hermes + TARS + Sherlock, SearXNG, Crawl4AI |
| Flota v1 | 8 vCPU | 16 GB | 160–240 GB NVMe | + Web (Chromium, Lighthouse), Studio (render wideo), Honcho, Postiz, monitoring |
| Flota v1 + Langfuse | 8 vCPU | 32 GB | 240 GB+ NVMe | + self-hostowany Langfuse (ClickHouse jest pamięciożerny) |

Rekomendacje:
- **x86_64**, nie ARM: część narzędzi medialnych i buildów łatwiej działa na x86,
- **region UE** (Polska/Niemcy): niskie opóźnienia i RODO,
- dysk rośnie głównie przez wideo i workspace’y, więc stare rendery sprzątamy rutyną cron.

---

## 3. Układ katalogów na VPS

```
/srv/tars/
├── repo/                 # klon tego repo (tylko do odczytu dla agentów)
├── compose/              # docker-compose.yml + .env infrastruktury (poza git)
├── data/
│   ├── hermes/           # → /opt/data w kontenerze: wszystkie profile, pamięć, sesje, kanban.db
│   ├── workspaces/       # katalogi robocze agentów (strony, rendery, raporty)
│   ├── knowledge/        # brand kity i wiedza wspólna o Tobie
│   ├── searxng/  honcho-db/  postiz-db/  …
└── backups/              # lokalny staging dumpów przed wysyłką
```

---

## 4. Usługi (docker compose)

| Usługa | Po co | Licencja | Kiedy |
|---|---|---|---|
| `tars-hermes` | agent, gateway, wszystkie profile | MIT | MVP |
| `searxng` (+ valkey) | darmowa metawyszukiwarka dla Sherlocka | AGPL-3.0 | MVP |
| `crawl4ai` | ekstrakcja stron do Markdown (wtyczka Hermesa `crawl4ai`) | Apache-2.0 | MVP |
| `honcho` (+ postgres/pgvector) | wspólna pamięć o Tobie | AGPL-3.0 | faza 3 |
| `postiz` (+ postgres, redis) | kolejka publikacji social media po Twojej akceptacji | AGPL-3.0 | Studio |
| `archivebox` | archiwum dowodów Sherlocka (kopie stron-źródeł) | MIT | opcjonalnie |
| `gotenberg` / `stirling-pdf` | konwersje dokumentów i PDF dla prawej ręki | MIT | opcjonalnie |
| `uptime-kuma` | healthchecki i alerty na Telegram | MIT | faza 2 |
| `beszel` | CPU/RAM/dysk, alerty | MIT | faza 2 |
| `langfuse` | ślady, koszty, oceny sędziego | MIT (core) | faza 6 |
| `caddy` | HTTPS, tylko jeśli coś musi być publiczne (podglądy stron, webhooki) | Apache-2.0 | w razie potrzeby |

Licencje AGPL/GPL są bezpieczne przy **prywatnym self-hostingu** (nie rozpowszechniamy
zmodyfikowanych wersji). Szczegóły: [TOOLBOX.md](TOOLBOX.md#polityka-licencji).

---

## 5. Bezpieczeństwo

**System:**
- Ubuntu LTS, `unattended-upgrades`, strefa czasowa Europe/Warsaw,
- użytkownik `tars` bez roota, logowanie SSH tylko kluczem, `PermitRootLogin no`,
- po postawieniu Tailscale: SSH tylko w sieci Tailscale, a publiczny port 22 zamknięty,
- firewall (UFW): domyślnie blokada ruchu przychodzącego; 80/443 otwarte tylko, gdy działa Caddy,
- CrowdSec (ochrona SSH/Caddy).

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
- backupy szyfrowane (restic szyfruje domyślnie), a hasło do repozytorium backupu trzymasz poza VPS.

---

## 6. Backupy

- **Co:** `data/hermes` (profile, pamięć, sesje, `state.db`, `kanban.db`; spójny zrzut przez
  `hermes backup`), dumpy Postgresa (Honcho, Postiz), `data/knowledge`, `data/workspaces` (bez renderów tymczasowych).
- **Czym:** restic → magazyn S3-kompatybilny poza VPS (inny dostawca albo region).
- **Kiedy:** co noc, retencja 7 dziennych / 4 tygodniowe / 12 miesięcznych.
- **Test odtworzenia:** raz w miesiącu automat odtwarza backup do katalogu tymczasowego
  i raportuje wynik na Telegram. Backup, którego nikt nie odtworzył, nie jest backupem.

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

`scripts/deploy.sh` (idempotentny):
1. `git pull` w `/srv/tars/repo`,
2. walidacja (`tests/`: frontmatter skilli, `distribution.yaml`, spójność `fleet.yaml`, szablony),
3. przebudowa obrazu, jeśli zmienił się któryś `toolbox.yaml` albo wersja Hermesa,
4. `docker compose up -d`,
5. instalacja lub aktualizacja profili (`hermes profile install ./profiles/<x>` przy pierwszym razie, potem aktualizacja),
6. generator floty (`gen-fleet.py`): opisy profili, skill `roster` TARS-a, trasy Telegrama, protokół w SOUL-ach,
7. healthchecki narzędzi z `toolbox.yaml`,
8. smoke evals (kilka szybkich scenariuszy per agent).

**Staging:** osobny projekt compose `tars-staging` na tym samym VPS, z własnym katalogiem danych
i osobnym botem testowym na Telegramie. Każda zmiana SOUL, skilli albo wersji Hermesa idzie najpierw tam.

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

## 10. Checklist postawienia serwera (runbook fazy 0/1)

- [ ] VPS utworzony (x86_64, UE, rozmiar z sekcji 2), klucz SSH dodany
- [ ] hardening systemu (użytkownik, SSH, UFW, unattended-upgrades, CrowdSec)
- [ ] Docker + compose, Tailscale; SSH przełączony na Tailscale
- [ ] `git clone` repo do `/srv/tars/repo`
- [ ] `compose/.env` + `.env` profili z kluczami (OpenRouter per agent, token bota Telegram)
- [ ] `scripts/deploy.sh` przechodzi na czysto
- [ ] Telegram: bot odpowiada tylko Tobie, wątki trafiają do właściwych agentów
- [ ] backup nocny działa + pierwszy test odtworzenia
- [ ] monitoring i alerty na Telegram działają
