# RUNBOOK: stawiamy TARS-a na VPS

Instrukcja krok po kroku: od pustego serwera do floty odpowiadającej na Telegramie, plus codzienna
obsługa. Architektura i uzasadnienia są w [VPS.md](VPS.md) i [BOSS.md](BOSS.md), tu są same kroki.

Czas: ok. 1,5 h przy pierwszym razie (z czego ~20 min to budowa obrazu).

---

## 0. Co przygotować przed startem

| Co | Po co | Uwagi |
|---|---|---|
| VPS x86_64, Ubuntu 24.04 (albo Debian 12), region UE | wszystko działa tutaj | start: **4 vCPU / 8 GB / 80 GB**, cała flota wygodnie: **8 vCPU / 16 GB / 160 GB** (sam obraz `tars-hermes` ma ok. 9–10 GB, sidecary ok. 5 GB) |
| Darmowe konto Docker Hub | `docker login` na serwerze | anonimowe pobieranie obrazów ma limit, który na współdzielonych IP VPS-ów łatwo wyczerpać |
| Klucz SSH (ed25519) | logowanie na serwer | hasła będą wyłączone |
| Konto [Tailscale](https://tailscale.com) (darmowe) | prywatny dostęp do serwera i paneli | nic nie wystawiamy publicznie |
| Konto [OpenRouter](https://openrouter.ai) z kredytami | modele, obrazy, wideo | **6 kluczy**: host + 5 agentów, każdy z limitem kredytów |
| Konto Telegram | główny kanał | bot + supergrupa „TARS HQ” z tematami |
| Miejsce na backup (Backblaze B2, S3 albo SFTP) | nocne kopie restic | poza serwerem |

Limity kluczy OpenRouter na start (miesięcznie, do korekty po 2 tygodniach): `tars` 30 $, `tars-sherlock` 20 $,
`tars-web` 20 $, `tars-studio` 30 $ (obrazy/wideo), `tars-reka` 15 $, host 5 $. Klucz z limitem to bezpiecznik:
zapętlony agent nie wyczyści konta.

Przed wdrożeniem sprawdź, czy modele z `fleet.yaml` nadal istnieją (lokalnie albo na serwerze):

```bash
python3 scripts/check-models.py
```

---

## 1. Bootstrap serwera (root, jednorazowo)

```bash
ssh root@<IP-VPS>
curl -fsSL https://raw.githubusercontent.com/jarojarojaro-jaro/TARS/<gałąź>/scripts/bootstrap-vps.sh -o bootstrap-vps.sh
bash bootstrap-vps.sh --user tars --ssh-key "ssh-ed25519 AAAA… ty@laptop"
```

Skrypt: aktualizacje i automatyczne łatki, użytkownik `tars` (sudo, docker), SSH tylko z kluczy i bez roota,
UFW (tylko SSH), fail2ban, Docker + compose, Tailscale (bez logowania), katalogi `/srv/tars/*`.

**Repo prywatne:** najpierw klucz tylko do odczytu (deploy key), potem klon i drugi przebieg bootstrapu
(jest idempotentny, a za drugim razem skopiuje szablony konfiguracji):

```bash
ssh tars@<IP-VPS>
ssh-keygen -t ed25519 -f ~/.ssh/tars_deploy -N "" && cat ~/.ssh/tars_deploy.pub
#   → GitHub: repo → Settings → Deploy keys → Add (bez "Allow write access")
cat >> ~/.ssh/config <<'EOF'
Host github.com
  IdentityFile ~/.ssh/tars_deploy
  IdentitiesOnly yes
EOF
git clone --branch <gałąź> git@github.com:jarojarojaro-jaro/TARS.git /srv/tars/repo
sudo bash /srv/tars/repo/scripts/bootstrap-vps.sh --user tars
```

(Repo publiczne: wystarczy od razu `--repo https://github.com/jarojarojaro-jaro/TARS.git --branch <gałąź>`.)

`<gałąź>`: `main` po scaleniu, do tego czasu gałąź robocza (`claude/epic-allen-qfjd0s`).

## 2. Tailscale

```bash
sudo tailscale up            # otwórz link i zaloguj serwer do swojej sieci
tailscale ip -4              # np. 100.101.102.103 → to będzie TARS_BIND_IP
```

Zainstaluj Tailscale też na laptopie i telefonie. Od teraz łącz się przez `ssh tars@<ip-tailscale>`.

---

## 3. Telegram: bot i „TARS HQ”

1. **Bot:** w [@BotFather](https://t.me/BotFather) → `/newbot` → nazwa (np. „TARS”) → zapisz **token**.
2. **Prywatność:** `/setprivacy` → wybierz bota → **Disable**. Bez tego bot w grupie widzi tylko komendy i @wzmianki.
3. **Twoje ID:** napisz do [@userinfobot](https://t.me/userinfobot) → liczba `Id` = `TELEGRAM_OWNER_ID`.
4. **Supergrupa:** nowa grupa „TARS HQ” → Ustawienia → **Tematy (Topics): włącz**. Dodaj bota
   (**po** zmianie prywatności; jeśli był dodany wcześniej: usuń i dodaj ponownie) i nadaj mu admina.
5. **Tematy:** utwórz `Sherlock`, `Web`, `Studio`, `Ręka`. Wątek „General” należy do TARS-a.
6. **ID grupy i wątków** (zanim uruchomisz flotę, bo gateway przejmie odbieranie wiadomości):
   napisz po jednej wiadomości w każdym temacie, potem:
   ```bash
   curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates" | jq '.result[].message | {chat: .chat.id, thread: .message_thread_id, text}'
   ```
   `chat` (zaczyna się od `-100`) → `TELEGRAM_HQ_CHAT_ID`, `thread` dla każdego tematu → `TELEGRAM_TOPIC_*`.
   Alternatywa: w aplikacji „Kopiuj link” do tematu → `https://t.me/c/<grupa>/<ID-wątku>`.

---

## 4. Konfiguracja na serwerze

Wszystkie pliki mają już szablony (utworzył je bootstrap). `compose/.env` ma tryb 600. Pliki w `secrets/`
mają tryb 640 i grupę `10000` (użytkownik `hermes` w kontenerze), bo instalator floty czyta je z kontenera.
Nowe pliki w tym katalogu dziedziczą grupę (setgid), a przy ręcznym kopiowaniu użyj
`sudo chgrp 10000 plik && chmod 640 plik`.

**`/srv/tars/compose/.env`** (docker compose):
```ini
TARS_BIND_IP=100.101.102.103      # IP Tailscale: dashboard i panele tylko w Twojej sieci
SEARXNG_SECRET=…                  # wygenerowany przez bootstrap, zostaw
DASHBOARD_PASSWORD=…              # hasło do dashboardu (użytkownik: tars), wygenerowane przez bootstrap
HERMES_MEM_LIMIT=10g              # przy 8 GB RAM: 5g
HERMES_CPUS=6                     # przy 4 vCPU: 3
```

**`/srv/tars/compose/tars.env`** (ID Telegrama, nie sekrety):
```ini
TELEGRAM_OWNER_ID=123456789
TELEGRAM_HQ_CHAT_ID=-1001234567890
TELEGRAM_TOPIC_SHERLOCK=2
TELEGRAM_TOPIC_WEB=3
TELEGRAM_TOPIC_STUDIO=4
TELEGRAM_TOPIC_REKA=5
```

**`/srv/tars/secrets/host.env`** (gateway):
```ini
TELEGRAM_BOT_TOKEN=…
TELEGRAM_ALLOWED_USERS=123456789
TELEGRAM_GROUP_ALLOWED_USERS=123456789
TELEGRAM_REQUIRE_MENTION=false
OPENROUTER_API_KEY=sk-or-v1-…     # klucz "host" (niski limit)
```

**`/srv/tars/secrets/<agent>.env`** dla `tars`, `tars-sherlock`, `tars-web`, `tars-studio`, `tars-reka`:
```ini
OPENROUTER_API_KEY=sk-or-v1-…     # osobny klucz na agenta
```
Opcjonalne klucze (wdrożenia stron, Postiz) są opisane w komentarzach szablonów. Agent bez klucza nie
zadziała; `install-fleet.sh` wypisze ostrzeżenie.

---

## 5. Pierwsze wdrożenie

```bash
cd /srv/tars/repo
bash scripts/deploy.sh --first-run
```

Co się dzieje (i co powinieneś zobaczyć):

| Krok | Oczekiwany wynik |
|---|---|
| budowa obrazu `tars-hermes:local` | kilkanaście minut za pierwszym razem |
| start usług | `hermes`, `searxng`, `valkey`, `crawl4ai`, `gotenberg` w stanie `running` |
| walidacja repo | `Walidacja: 0 błędów` |
| build dystrybucji | `✓ tars: … skilli, 4 rutyn cron`, `✓ tars-sherlock: …` itd.; brak linii `!` o Telegramie |
| instalacja floty | `Instalacja profilu …` ×5, `✅ Flota zainstalowana` |
| healthchecki | `✓` przy narzędziach, `○` przy opcjonalnych (docling, manim, postiz); każdy `✗` sprawdź w sekcji 10 |

Przed pierwszym wdrożeniem zaloguj się do Docker Hub (`docker login`), żeby nie trafić na limit pobrań.

Po udanym wdrożeniu przypnij obrazy do digestów (powtarzalne wdrożenia):

```bash
bash scripts/pin-images.sh      # zapisuje digesty w /srv/tars/compose/.env (repo bez zmian)
```

## 6. Test dymny (smoke test)

1. **DM z botem:** „Cześć, kim jesteś i kogo masz w zespole?” → odpowiada TARS, wymienia 4 snajperów.
2. **Temat Sherlock:** „Jaka jest aktualna stawka VAT na usługi IT w Polsce? Podaj źródło.” → odpowiada Sherlock.
3. **Misja przez TARS-a (DM):** „Sprawdź 3 konkurentów kawiarni specialty w Krakowie i przygotuj szkic landing page’a.”
   TARS powinien potwierdzić zlecenie efektami, a na tablicy pojawić się karty:
   ```bash
   docker exec -u hermes tars-hermes hermes kanban list
   ```
   Po kilku–kilkunastu minutach: recenzja TARS-a (status `review` → `done` albo prośba o poprawki) i raport w DM.
4. **Dashboard:** `http://<ip-tailscale>:9119`, login `tars` + `DASHBOARD_PASSWORD` z `compose/.env`
   (tablica kanban, sesje, koszty). Bez hasła Hermes nie uruchomi dashboardu poza localhostem.

## 7. Włączenie rutyn i onboarding

Rutyny TARS-a (patrol co 30 min, poranny brief, przegląd tygodnia, świeżość wiedzy) instalują się wstrzymane.
Po udanym teście Telegrama:

```bash
bash scripts/deploy.sh --no-pull --resume-cron
docker exec -u hermes tars-hermes hermes -p tars cron list
```

Potem napisz do TARS-a: **„Zróbmy onboarding.”** Wywiad (15–20 min) wypełnia `knowledge/user/USER.md` i pamięć
o Tobie, z której korzystają wszyscy agenci. Brand kity dodajesz poleceniem: „Naucz się marki z https://…”.

## 8. Backupy, monitoring, zamknięcie SSH

**Backup (restic):** dane dostępowe trzymamy w `/srv/tars/restic.env` (root, 600), celowo **poza**
`/srv/tars/secrets`, bo ten katalog jest widoczny w kontenerze agentów.
```bash
sudo install -m 600 /dev/null /srv/tars/restic.env
sudo nano /srv/tars/restic.env
#   RESTIC_REPOSITORY=b2:tars-backup:/vps
#   RESTIC_PASSWORD=…            # zapisz TAKŻE poza serwerem (menedżer haseł)
#   B2_ACCOUNT_ID=…
#   B2_ACCOUNT_KEY=…
sudo bash /srv/tars/repo/scripts/backup.sh          # pierwszy przebieg ręcznie
sudo crontab -e
# 15 3 * * * /srv/tars/repo/scripts/backup.sh >> /srv/tars/backups/backup.log 2>&1
# 40 4 1 * * /srv/tars/repo/scripts/restore-test.sh >> /srv/tars/backups/restore-test.log 2>&1
```

**Monitoring (opcjonalnie):** `bash scripts/deploy.sh --no-pull --monitoring`, potem Uptime Kuma
`http://<ip-tailscale>:3001` (monitory: dashboard 9119, SearXNG, Gotenberg) i Beszel `http://<ip-tailscale>:8090`
(klucz agenta z panelu → `BESZEL_AGENT_KEY` w `compose/.env` → ponownie `--monitoring`).

**SSH tylko przez Tailscale** (gdy `ssh tars@<ip-tailscale>` działa):
```bash
sudo bash /srv/tars/repo/scripts/bootstrap-vps.sh --lock-ssh
```

---

## 9. Codzienna obsługa

| Zadanie | Komenda |
|---|---|
| wdrożenie zmian z repo | `bash scripts/deploy.sh` (pull → walidacja → build → aktualizacja profili → restart gatewaya) |
| przebudowa obrazu (nowe narzędzia) | `bash scripts/deploy.sh --rebuild` (automatycznie, gdy zmienił się `infra/Dockerfile`, `infra/node/`, `infra/python/`) |
| aktualizacja Hermesa | zmień `HERMES_IMAGE` w `compose/.env` → `deploy.sh --rebuild` → `pin-images.sh` |
| evals (staging, izolowane dane) | `bash scripts/evals-staging.sh --agent tars` (koszt: klucze agentów + sędzia) |
| skille, które agenci zmienili sami | `bash scripts/harvest-skills.sh > harvest.md`, przegląd, przeniesienie do repo |
| nowy agent | lokalnie `make new-agent NAME=tars-x TITLE="…"`, uzupełnienie, `make validate`, status `active`, deploy |
| stan floty | `docker exec -u hermes tars-hermes hermes kanban stats`, `… hermes gateway status` |
| logi | `docker logs -f tars-hermes`, `/srv/tars/data/hermes/logs/` |
| wycofanie zmiany | `git checkout <tag-albo-commit> && bash scripts/deploy.sh --no-pull` |
| koszty | OpenRouter → Activity (per klucz = per agent), dashboard Hermesa |

Zasada: **na serwerze nic nie edytujemy ręcznie** (poza plikami env). Zmiana = commit w repo + `deploy.sh`.
Wyjątek to skille tworzone przez agentów: zbiera je `harvest-skills.sh`.

## 10. Rozwiązywanie problemów

| Objaw | Przyczyna i naprawa |
|---|---|
| bot milczy w grupie, w DM odpowiada | prywatność bota włączona albo bot dodany przed jej wyłączeniem → `/setprivacy` Disable, usuń i dodaj bota |
| w temacie odpowiada TARS zamiast snajpera | złe `TELEGRAM_TOPIC_*` → popraw `tars.env`, `deploy.sh --no-pull`; build wypisuje `!` przy brakach |
| karty wiszą w `ready` | nie działa dispatcher: `hermes gateway status`; patrol zgłosi to sam po 20 min |
| karta w `blocked` `capability` | brak narzędzia albo klucza: TARS pyta w kolejce decyzji; dopisz klucz do `secrets/<agent>.env`, `deploy.sh --no-pull` |
| agent odpowiada błędem 401/402 | zły klucz OpenRouter albo wyczerpany limit kredytów tego klucza |
| `✗` w healthchecku narzędzia | `docker exec -u hermes tars-hermes bash -lc '<komenda z toolbox.yaml>'` i przebudowa obrazu, jeśli brakuje pakietu |
| walidacja przy deployu nie przechodzi | deploy zatrzymuje się przed zmianą floty; popraw błąd w repo (lokalnie `make validate`) |
| `install-fleet.sh`: „nieczytelny” przy sekretach | złe uprawnienia `secrets/` → `sudo chgrp -R 10000 /srv/tars/secrets && sudo chmod 2750 /srv/tars/secrets && sudo chmod 640 /srv/tars/secrets/*.env` |
| `toomanyrequests: You have reached your unauthenticated pull rate limit` | limit Docker Hub → `docker login` (darmowe konto) i ponów `deploy.sh` |
| brak miejsca na dysku | `docker system prune`, stare rendery w `/srv/tars/data/hermes/tars/workspaces/*/` |
