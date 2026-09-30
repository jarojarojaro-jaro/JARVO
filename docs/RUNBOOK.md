# RUNBOOK: stawiamy Jarva na VPS

Instrukcja krok po kroku: od pustego serwera do floty odpowiadającej na Telegramie, plus codzienna
obsługa. Architektura i uzasadnienia są w [VPS.md](VPS.md) i [BOSS.md](BOSS.md), tu są same kroki.

Czas: ok. 1,5 h przy pierwszym razie (z czego ~20 min to budowa obrazu).

---

## 0. Co przygotować przed startem

| Co | Po co | Uwagi |
|---|---|---|
| VPS x86_64, Ubuntu 24.04 (albo Debian 12), region UE | wszystko działa tutaj | cała flota: **4 vCPU / 8 GB / 80 GB** (obraz `jarvo-hermes` 4,4 GB, na start ok. 6 GB dysku; RAM w spoczynku ok. 0,7 GB, w szczycie ok. 3,7 GB; szczegóły: [VPS.md §2](VPS.md#2-rozmiar-serwera)) |
| Darmowe konto Docker Hub | `docker login` na serwerze | anonimowe pobieranie obrazów ma limit, który na współdzielonych IP VPS-ów łatwo wyczerpać |
| Klucz SSH (ed25519) | logowanie na serwer | hasła będą wyłączone |
| Konto [Tailscale](https://tailscale.com) (darmowe) | prywatny dostęp do serwera i paneli | nic nie wystawiamy publicznie |
| Konto ChatGPT (z dostępem do Codex) | domyślne modele floty (`openai-codex`, gpt-6-luna) | logowanie OAuth w dashboardzie: Models → Login przy profilu „default” |
| Konto [OpenRouter](https://openrouter.ai) z kredytami | obrazy i wideo AI (modele tylko przy zestawie `openrouter`) | **8 kluczy**: host + 7 agentów, każdy z limitem kredytów |
| Klucz [Pexels](https://www.pexels.com/api/) albo [Pixabay](https://pixabay.com/api/docs/) (darmowy) | ujęcia stock dla Wideografa | `PEXELS_API_KEY` / `PIXABAY_API_KEY` w Keys (profil główny) |
| Konto Telegram | główny kanał | bot + supergrupa „Jarvo HQ” z tematami |
| Miejsce na backup (Backblaze B2, S3 albo SFTP) | nocne kopie restic | poza serwerem |

Limity kluczy OpenRouter na start (miesięcznie, do korekty po 2 tygodniach): `jarvo` 30 $, `jarvo-sherlock` 20 $,
`jarvo-web` 20 $, `jarvo-studio` 20 $ (obrazy), `jarvo-wideo` 30 $ (wideo AI), `jarvo-ads` 15 $, `jarvo-reka` 15 $, host 5 $. Klucz z limitem to bezpiecznik:
zapętlony agent nie wyczyści konta.

Przed wdrożeniem sprawdź, czy modele z `fleet.yaml` nadal istnieją (lokalnie albo na serwerze). Przy domyślnym
`openai-codex` skrypt nic nie sprawdza (dostawca nie ma publicznej listy modeli); ma sens dla zestawów
`openrouter`, `commandcode` i `commandcode-anthropic`:

```bash
JARVO_MODEL_PROVIDER=openrouter python3 scripts/check-models.py
```

---

## 1. Bootstrap serwera (root, jednorazowo)

```bash
ssh root@<IP-VPS>
curl -fsSL https://raw.githubusercontent.com/jarojarojaro-jaro/JARVO/<gałąź>/scripts/bootstrap-vps.sh -o bootstrap-vps.sh
bash bootstrap-vps.sh --user jarvo --ssh-key "ssh-ed25519 AAAA… ty@laptop"
passwd jarvo                 # hasło tylko do sudo (logowanie SSH i tak wyłącznie kluczem)
```

Skrypt: aktualizacje i automatyczne łatki, swap 4 GB (swappiness 10), użytkownik `jarvo` (sudo, docker; bez hasła,
dlatego `passwd`), SSH tylko z kluczy i bez roota, UFW (tylko SSH), fail2ban, Docker + compose, Tailscale (bez
logowania), katalogi `/srv/jarvo/*`, usługa `jarvo-updater` (włączona, uruchamiasz ją po pierwszym wdrożeniu).

**Repo prywatne:** `raw.githubusercontent.com` nie wyda pliku bez tokenu, więc skrypt skopiuj z laptopa
(`scp scripts/bootstrap-vps.sh root@<IP-VPS>:`). Potem klucz tylko do odczytu (deploy key), klon i drugi przebieg
bootstrapu (jest idempotentny, a za drugim razem skopiuje szablony konfiguracji):

```bash
ssh jarvo@<IP-VPS>
ssh-keygen -t ed25519 -f ~/.ssh/jarvo_deploy -N "" && cat ~/.ssh/jarvo_deploy.pub
#   → GitHub: repo → Settings → Deploy keys → Add (bez "Allow write access")
cat >> ~/.ssh/config <<'EOF'
Host github.com
  IdentityFile ~/.ssh/jarvo_deploy
  IdentitiesOnly yes
EOF
git clone --branch <gałąź> git@github.com:jarojarojaro-jaro/JARVO.git /srv/jarvo/repo
sudo bash /srv/jarvo/repo/scripts/bootstrap-vps.sh --user jarvo
```

(Repo publiczne: wystarczy od razu `--repo https://github.com/jarojarojaro-jaro/JARVO.git --branch <gałąź>`.)

`<gałąź>`: `main` po scaleniu, do tego czasu gałąź robocza (`claude/epic-allen-qfjd0s`).

## 2. Tailscale

```bash
sudo tailscale up            # otwórz link i zaloguj serwer do swojej sieci
tailscale ip -4              # np. 100.101.102.103 → to będzie JARVO_BIND_IP
```

Zainstaluj Tailscale też na laptopie i telefonie. Od teraz łącz się przez `ssh jarvo@<ip-tailscale>`.

---

## 3. Telegram: bot i „Jarvo HQ”

1. **Bot:** w [@BotFather](https://t.me/BotFather) → `/newbot` → nazwa (np. „Jarvo”) → zapisz **token**.
2. **Prywatność:** `/setprivacy` → wybierz bota → **Disable**. Bez tego bot w grupie widzi tylko komendy i @wzmianki.
3. **Twoje ID:** napisz do [@userinfobot](https://t.me/userinfobot) → liczba `Id` = `TELEGRAM_OWNER_ID`.
4. **Supergrupa:** nowa grupa „Jarvo HQ” → Ustawienia → **Tematy (Topics): włącz**. Dodaj bota
   (**po** zmianie prywatności; jeśli był dodany wcześniej: usuń i dodaj ponownie) i nadaj mu admina.
5. **Tematy:** utwórz `Sherlock`, `Web`, `Studio`, `Wideo`, `Ads`, `Ręka`. Wątek „General” należy do Jarva.
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

**`/srv/jarvo/compose/.env`** (docker compose):
```ini
JARVO_BIND_IP=100.101.102.103      # IP Tailscale: dashboard i panele tylko w Twojej sieci
SEARXNG_SECRET=…                  # wygenerowany przez bootstrap, zostaw
DASHBOARD_PASSWORD=…              # hasło do dashboardu (użytkownik: jarvo), wygenerowane przez bootstrap
HERMES_MEM_LIMIT=5g               # sufit RAM kontenera Hermesa (VPS 8 GB); przy 16 GB można 10g
HERMES_CPUS=4
JARVO_EXTRAS=                      # opcjonalnie: rembg media office docling manim (więcej dysku, nie RAM)
```

**`/srv/jarvo/compose/jarvo.env`** (ID Telegrama i dostawca modeli, nie sekrety):
```ini
TELEGRAM_OWNER_ID=123456789
TELEGRAM_HQ_CHAT_ID=-1001234567890
TELEGRAM_TOPIC_SHERLOCK=2
TELEGRAM_TOPIC_WEB=3
TELEGRAM_TOPIC_STUDIO=4
TELEGRAM_TOPIC_REKA=5
TELEGRAM_TOPIC_WIDEO=6
TELEGRAM_TOPIC_ADS=7
JARVO_MODEL_PROVIDER=              # puste = openai-codex (niżej: „Dostawca modeli”)
```

**`/srv/jarvo/secrets/host.env`** (gateway):
```ini
TELEGRAM_BOT_TOKEN=…
TELEGRAM_ALLOWED_USERS=123456789
TELEGRAM_GROUP_ALLOWED_USERS=123456789
TELEGRAM_REQUIRE_MENTION=false
OPENROUTER_API_KEY=sk-or-v1-…     # klucz "host" (niski limit)
```

**`/srv/jarvo/secrets/<agent>.env`** dla `jarvo`, `jarvo-sherlock`, `jarvo-web`, `jarvo-studio`, `jarvo-wideo`, `jarvo-ads`, `jarvo-reka`:
```ini
OPENROUTER_API_KEY=sk-or-v1-…     # osobny klucz na agenta
```
Opcjonalne klucze (wdrożenia stron, Postiz) są opisane w komentarzach szablonów. Agent bez własnego klucza
dostaje klucz hosta (blok „klucze wspólne”, `scripts/share_keys.py`), czyli jego niski limit; `install-fleet.sh`
ostrzega tylko, gdy brakuje całego pliku `secrets/<agent>.env`.

---

### Dostawca modeli (OpenAI, OpenRouter, CommandCode…)

Domyślnie agenci używają OpenAI przez logowanie ChatGPT (`openai-codex`, model gpt-6-luna; zaloguj się
w dashboardzie: Models → Login przy profilu „default”). OpenRouter służy wtedy do obrazów i wideo AI.
Inny dostawca dla całej floty: w `compose/jarvo.env` ustaw `JARVO_MODEL_PROVIDER` na nazwę zestawu
z `fleet.yaml` → `models.presets` (`openrouter`: Claude przez OpenRouter, `commandcode-anthropic`: Claude
przez CommandCode, `commandcode`: DeepSeek/Kimi przez CommandCode) i wdroż. Pojedyncze modele:
`JARVO_MODEL_FRONTIER` / `_STRONG` / `_FAST`, model zapasowy `JARVO_MODEL_FALLBACK` (albo `off`;
domyślne zapasowe: `fleet.yaml` → `models.fallback`). Lokalnie jednym poleceniem:
`JARVO_MODEL_PROVIDER=commandcode bash scripts/local-up.sh`. Host (zadania pomocnicze
kanbana) dostaje najszybszy model zestawu, chyba że wybrano mu model ręcznie przez `/model`.
`make models` sprawdza, czy modele wybranego zestawu istnieją u dostawcy (przy `openai-codex` nic nie sprawdza).

### Klucze dostawców i logowanie (OAuth)

Każdy agent floty to osobny profil Hermesa z własnym `.env`, a Hermes celowo ich nie miesza (izolacja kluczy
przy multipleksowaniu). Żeby nie wpisywać klucza siedem razy:

- **Klucze API** (CommandCode, OpenRouter, OpenCode, Exa…) dodawaj w dashboardzie **Keys przy profilu
  „default”**. Jarvo HQ w ciągu kilku sekund kopiuje je do wszystkich agentów (`scripts/share_keys.py`, blok
  „klucze wspólne” na końcu `.env` agenta). Dzielone są tylko klucze dostawców i narzędzi; tokeny
  komunikatorów (Telegram, Discord…) zostają tam, gdzie je wpisano.
- **Inny klucz dla jednego agenta:** wybierz go w lewym górnym rogu i ustaw klucz w Keys. Ma pierwszeństwo
  przed wspólnym i synchronizacja go nie nadpisze.
- **Logowanie OAuth** (ChatGPT/Codex, Nous Portal, Copilot…): zaloguj się raz, przy profilu „default”.
  Agenci korzystają z niego sami (Hermes czyta główny `auth.json` jako zapas dla profili).
  Nie loguj się na to samo konto osobno w agentach.

## 5. Pierwsze wdrożenie

```bash
cd /srv/jarvo/repo
bash scripts/deploy.sh --first-run
```

Co się dzieje (i co powinieneś zobaczyć):

| Krok | Oczekiwany wynik |
|---|---|
| budowa obrazu `jarvo-hermes:local` | kilkanaście minut za pierwszym razem |
| start usług | `hermes`, `searxng`, `valkey` w stanie `running` |
| walidacja repo | `Walidacja: 0 błędów` |
| build dystrybucji | `✓ jarvo: … skilli, 4 rutyn cron`, `✓ jarvo-sherlock: …` itd., `✓ skan skilli: … (… znanych wyjątków, … ostrzeżeń)`; brak linii `!` o Telegramie i o wyjątkach skanu |
| instalacja floty | `Instalacja profilu …` ×7, `✅ Flota zainstalowana` |
| healthchecki | `✓` przy narzędziach, `○` przy opcjonalnych (dodatki `JARVO_EXTRAS`, narzędzia Wideografa z `narzedzia.py`, klucze Pexels/Pixabay, postiz, skarbiec); każdy `✗` sprawdź w sekcji 10 |

Przed pierwszym wdrożeniem zaloguj się do Docker Hub (`docker login`), żeby nie trafić na limit pobrań.

Po udanym wdrożeniu przypnij obrazy do digestów (powtarzalne wdrożenia):

```bash
bash scripts/pin-images.sh      # zapisuje digesty w /srv/jarvo/compose/.env (repo bez zmian)
```

Uruchom też pomocnika aktualizacji (przycisk „Aktualizuj” w dashboardzie; bootstrap tylko go włączył):

```bash
sudo systemctl start jarvo-updater
```

## 6. Test dymny (smoke test)

1. **DM z botem:** „Cześć, kim jesteś i kogo masz w zespole?” → odpowiada Jarvo, wymienia 5 snajperów i Prawą rękę.
2. **Temat Sherlock:** „Jaka jest aktualna stawka VAT na usługi IT w Polsce? Podaj źródło.” → odpowiada Sherlock.
3. **Misja przez Jarva (DM):** „Sprawdź 3 konkurentów kawiarni specialty w Krakowie i przygotuj szkic landing page’a.”
   Jarvo powinien potwierdzić zlecenie efektami, a na tablicy pojawić się karty:
   ```bash
   docker exec -u hermes jarvo-hermes hermes kanban list
   ```
   Po kilku–kilkunastu minutach: recenzja Jarva (status `review` → `done` albo prośba o poprawki) i raport w DM.
4. **Jarvo HQ:** `http://<ip-tailscale>:9119/base` (zakładka **BASE** nad CHAT), login `jarvo` + `DASHBOARD_PASSWORD`
   z `compose/.env`. To budynek floty: pokoje agentów z podglądem pracy, decyzje, misje i czat ([HQ.md](HQ.md)).
   Pozostałe zakładki dashboardu Hermesa (sesje, cron, logi, konfiguracja) zostają w menu.
   Kontrola: `/api/plugins/jarvo-hq/health` po zalogowaniu pokazuje klucze API profili i dostępność gatewaya.

## 7. Włączenie rutyn i onboarding

Rutyny Jarva (patrol co 30 min, poranny brief, przegląd tygodnia, świeżość wiedzy) instalują się wstrzymane.
Po udanym teście Telegrama:

```bash
bash scripts/deploy.sh --no-pull --resume-cron
docker exec -u hermes jarvo-hermes hermes -p jarvo cron list
```

Potem napisz do Jarva: **„Zróbmy onboarding.”** Wywiad (15–20 min) wypełnia `knowledge/user/USER.md` i pamięć
o Tobie, z której korzystają wszyscy agenci. Brand kity dodajesz poleceniem: „Naucz się marki z https://…”.

## 8. Backupy, monitoring, zamknięcie SSH

**Backup (restic):** dane dostępowe trzymamy w `/srv/jarvo/restic.env` (root, 600), celowo **poza**
`/srv/jarvo/secrets`, bo ten katalog jest widoczny w kontenerze agentów.
```bash
sudo install -m 600 /dev/null /srv/jarvo/restic.env
sudo nano /srv/jarvo/restic.env
#   RESTIC_REPOSITORY=b2:jarvo-backup:/vps
#   RESTIC_PASSWORD=…            # zapisz TAKŻE poza serwerem (menedżer haseł)
#   B2_ACCOUNT_ID=…
#   B2_ACCOUNT_KEY=…
sudo bash /srv/jarvo/repo/scripts/backup.sh          # pierwszy przebieg ręcznie
sudo crontab -e
# 15 3 * * * /srv/jarvo/repo/scripts/backup.sh >> /srv/jarvo/backups/backup.log 2>&1
# 40 4 1 * * /srv/jarvo/repo/scripts/restore-test.sh >> /srv/jarvo/backups/restore-test.log 2>&1
```

**Monitoring (opcjonalnie):** `bash scripts/deploy.sh --no-pull --monitoring`, potem Uptime Kuma
`http://<ip-tailscale>:3001` (monitory: dashboard 9119, SearXNG) i Beszel `http://<ip-tailscale>:8090`
(klucz agenta z panelu → `BESZEL_AGENT_KEY` w `compose/.env` → ponownie `--monitoring`).

**SSH tylko przez Tailscale** (gdy `ssh jarvo@<ip-tailscale>` działa):
```bash
sudo bash /srv/jarvo/repo/scripts/bootstrap-vps.sh --lock-ssh
```

---

## 9. Codzienna obsługa

| Zadanie | Komenda |
|---|---|
| wdrożenie zmian z repo | `bash scripts/deploy.sh` (pull → walidacja → build → aktualizacja profili → restart gatewaya) |
| przebudowa obrazu (nowe narzędzia) | `bash scripts/deploy.sh --rebuild` (automatycznie, gdy zmienił się `infra/Dockerfile`, `infra/node/`, `infra/python/`, `infra/bin/` albo `branding/`) |
| aktualizacja Hermesa | zmień `HERMES_IMAGE` w `compose/.env` → `deploy.sh --rebuild` (tag ruchomy, np. `latest`: `--rebuild --pull-base`) → `pin-images.sh` |
| evals (staging, izolowane dane) | `bash scripts/evals-staging.sh --agent jarvo` (koszt: klucze agentów + sędzia) |
| red team (ataki promptfoo, tylko środowisko testowe) | `bash scripts/redteam.sh` albo `bash scripts/redteam.sh --filtr ads` (koszt: tokeny modeli) |
| skille, które agenci zmienili sami | `bash scripts/harvest-skills.sh > harvest.md`, przegląd, przeniesienie do repo |
| nowy agent | lokalnie `make new-agent NAME=jarvo-x TITLE="…"`, uzupełnienie, `make validate`, status `active`, deploy |
| stan floty | `docker exec -u hermes jarvo-hermes hermes kanban stats`, `… hermes gateway status` |
| logi | `docker logs -f jarvo-hermes`, `/srv/jarvo/data/hermes/logs/` |
| wycofanie zmiany | `git checkout <tag-albo-commit> && bash scripts/deploy.sh --no-pull` (z `--rebuild`, gdy różni się `infra/` albo `branding/`) |
| koszty | modele `openai-codex`: plan ChatGPT; OpenRouter → Activity (obrazy, wideo, zestaw `openrouter`; per klucz = per agent), dashboard Hermesa |

Zasada: **na serwerze nic nie edytujemy ręcznie** (poza plikami env). Zmiana = commit w repo + `deploy.sh`.
Wyjątek to skille tworzone przez agentów: zbiera je `harvest-skills.sh`.

### Aktualizacje z panelu

Gdy na GitHubie jest nowsza wersja, w menu bocznym dashboardu pojawia się **„⬆ Aktualizacja (n)”**:
klik pokazuje listę zmian, **„Aktualizuj teraz”** robi `git pull` i wdrożenie (z przebudową obrazu, gdy
trzeba), a na koniec strona sama się odświeża. Pomocnik sprawdza GitHuba co minutę; z `JARVO_AUTO_UPDATE=1`
(lokalnie: `JARVO_AUTO_UPDATE=1 bash scripts/local-up.sh`) instaluje nowe wersje sam, bez klikania. Robi to pomocnik na hoście
(`scripts/updater.py`), bo kontener celowo nie ma dostępu do Dockera: panel może tylko poprosić o
sprawdzenie albo aktualizację tej samej gałęzi. Na VPS działa jako usługa `jarvo-updater` (start: §5;
`sudo systemctl status jarvo-updater`, log: `journalctl -u jarvo-updater`; `JARVO_AUTO_UPDATE=1` przez
`sudo systemctl edit jarvo-updater` → `[Service]` `Environment=JARVO_AUTO_UPDATE=1`); lokalnie uruchamia go
`scripts/local-up.sh` (log: `~/jarvo-local/updater.log`). Gdy nie działa, pozycja w menu się nie pojawia.

### Wyniki agentów w przeglądarce
Flota działa w kontenerze, więc serwer uruchomiony przez agenta (`localhost:8000`, `npm run dev`) jest dla
przeglądarki nieosiągalny. Wyniki otwiera **▶ Odpal** w Jarvo HQ albo link, który agent robi poleceniem
`python3 /opt/jarvo/repo/scripts/jarvo_link.py <plik albo katalog>` (serwer podglądu na porcie 9120, ten sam
`JARVO_BIND_IP` co dashboard; link ważny 7 dni). Pliki wysłane w czacie HQ leżą w `/opt/data/jarvo/inbox/<data>/`.

## 10. Rozwiązywanie problemów

| Objaw | Przyczyna i naprawa |
|---|---|
| bot milczy w grupie, w DM odpowiada | prywatność bota włączona albo bot dodany przed jej wyłączeniem → `/setprivacy` Disable, usuń i dodaj bota |
| w temacie odpowiada Jarvo zamiast snajpera | złe `TELEGRAM_TOPIC_*` → popraw `jarvo.env`, `deploy.sh --no-pull`; build wypisuje `!` przy brakach |
| karty wiszą w `ready` | nie działa dispatcher: `hermes gateway status`; patrol zgłosi to sam po 20 min |
| karta w `blocked` `capability` | brak narzędzia albo klucza: Jarvo pyta w kolejce decyzji; dopisz klucz do `secrets/<agent>.env`, `deploy.sh --no-pull` |
| agent odpowiada błędem 401/402 | `openai-codex`: wygasłe logowanie ChatGPT → ponów Models → Login przy profilu „default”; zestaw `openrouter`: zły klucz OpenRouter albo wyczerpany limit kredytów tego klucza |
| `✗` w healthchecku narzędzia | `docker exec -u hermes jarvo-hermes bash -c '<komenda z toolbox.yaml>'` (nie `bash -lc`: powłoka logowania zeruje `PATH` obrazu) i przebudowa obrazu, jeśli brakuje pakietu |
| build: „Skan skilli: N ustaleń high/critical bez wyjątku” | nowa wersja źródła w locku albo nowy skill ma podejrzany fragment. Przeczytaj każde ustalenie w kontekście (`python3 scripts/skan_skilli.py <katalog skilla>`): fałszywy alarm → wpis w `vendor/skan-wyjatki.yaml` z powodem i rev; prawdziwy problem → nie bierzemy tej wersji (cofnij `rev`) |
| walidacja przy deployu nie przechodzi | deploy zatrzymuje się przed zmianą floty; popraw błąd w repo (lokalnie `make validate`) |
| `install-fleet.sh`: „nieczytelny” przy sekretach | złe uprawnienia `secrets/` → `sudo chgrp -R 10000 /srv/jarvo/secrets && sudo chmod 2750 /srv/jarvo/secrets && sudo chmod 640 /srv/jarvo/secrets/*.env` |
| `toomanyrequests: You have reached your unauthenticated pull rate limit` | limit Docker Hub → `docker login` (darmowe konto) i ponów `deploy.sh` |
| brak miejsca na dysku | `docker system prune`, stare rendery w `/srv/jarvo/data/hermes/jarvo/workspaces/*/` |
| mało RAM-u, OOM w `docker logs` / `dmesg` | `docker stats`; zmniejsz `kanban.max_in_progress` w `profiles/_host/config.yaml` (domyślnie 3) i `deploy.sh --no-pull`; sprawdź swap (`swapon --show`) |
| pierwsza wiadomość głosowa długo się przetwarza | pobiera się model Parakeet (0,65 GB) do `/srv/jarvo/data/hermes/jarvo/models`; raz. Z góry: `docker exec -u hermes jarvo-hermes jarvo-stt --prefetch` |
| przeglądarka agenta nie widzi strony (pusta treść) | Lightpanda nie obsługuje wszystkiego; Hermes sam przełącza na Chromium przy zrzutach i błędach. Gdy strona uparcie nie działa: `browser.engine: chrome` w `profiles/<agent>/config.yaml` |
