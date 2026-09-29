# Jarvo — całość od A do Z

> Jeden opis wszystkiego. Do wklejenia na start nowej sesji, żeby mieć pełny kontekst
> bez czytania całego repo. Repo: `jarojarojaro-jaro/JARVO`, lokalnie `/home/user/TARS`.
> Gałąź robocza: `claude/epic-allen-qfjd0s`. Język pracy: polski.

---

## 0. W jednym zdaniu

Jarvo to **prywatny asystent AI zbudowany na Hermes Agent (Nous Research)**: na zewnątrz jeden
asystent, a w środku **flota wyspecjalizowanych agentów („snajperów”)** prowadzona przez **Jarva**
(Main Judge). Ty gadasz z Jarvem (albo z konkretnym specjalistą), a on rozdziela pracę, ocenia
wyniki i oddaje jeden sprawdzony rezultat. Wszystko działa na jednym VPS-ie i niczego nie zapomina.

**Kluczowa zasada:** nie forkujemy Hermesa. Repo jest jedynym źródłem prawdy — na serwerze nic
nie edytujemy ręcznie. Działania nieodwracalne (publikacja, wdrożenie, płatności, wysyłka) tylko
za zgodą człowieka.

---

## 1. Model działania: jeden Main Judge + flota snajperów

Inspiracja: firstmate. Rozmawiasz z jednym agentem, a on prowadzi załogę.

- **Snajper = specjalista.** Jedna dziedzina, własne skille, własna wiedza, własna pamięć.
  Profile tworzone z `--no-skills` — dostają tylko to, co im damy. Czego nie umie, tego nie robi:
  oddaje zadanie szefowi.
- **Jarvo = Main Judge (orkiestrator).** Sam nie robi pracy dziedzinowej. Robi cztery rzeczy:
  1. **intake** — rozumie, czego chcesz, dopytuje tylko o prawdziwe decyzje,
  2. **dispatch** — rozbija cel na karty kanbana i przypisuje snajperom,
  3. **judge** — każdy wynik wraca w statusie `review`; Jarvo ocenia go według rubryki agenta:
     akceptuje (`complete`) albo odsyła do poprawki (`request_changes`),
  4. **raport** — oddaje Ci jeden, sprawdzony wynik.
- **Bezpośredni kontakt zostaje** — z każdym snajperem pogadasz osobno, ale praca wieloetapowa
  zawsze idzie przez szefa.
- **Jedyna rzecz wspólna:** wiedza o Tobie (USER.md). Reszta jest odizolowana per agent.
- **Nadzór bez palenia tokenów:** dispatcher kanbana i patrol (skrypt bez modelu) pilnują floty
  i budzą Jarva tylko przy anomaliach albo gdy trzeba Twojej decyzji.

Poziomy autonomii: **A0** odczyt · **A1** szkice we własnym workspace · **A2** po zgodzie człowieka
· **A3** nigdy. Wszyscy specjaliści mają `autonomy_max: A1`.

---

## 2. Flota agentów (7 profili)

Każdy agent to osobna **dystrybucja Hermesa**: `SOUL.md` (osobowość + zasady), `config.yaml`
(model, toolset, deny), skille, skrypty, rubryka jakości, toolbox, dystrybucja.

| Agent | Rola | Pokój HQ | Temat Telegram | Skille |
|---|---|---|---|---|
| 🛰️ `jarvo` | **Main Judge** — intake, misje, karty, sędziowanie, raporty, patrol | Mostek dowodzenia (`bridge`) | general | 11 |
| 🔎 `jarvo-sherlock` | **Researcher-detektyw** — wieloźródłowy research, weryfikacja faktów, raporty z cytatami | Gabinet śledczy (`study`) | sherlock | 7 |
| 🌐 `jarvo-web` | **Web Senior Dev** — strony/landingi, SEO techniczne, bezpieczeństwo aplikacji, wydajność, wdrożenie | Pracownia webowa (`devlab`) | web | 9 |
| 🎬 `jarvo-studio` | **Marketing i kreacja** — grafiki social, obrazy AI, copy PL, kampanie, kalendarze | Atelier kreatywne (`atelier`) | studio | 6 |
| 🎥 `jarvo-wideo` | **Wideograf** — krótkie filmy (lektor PL, napisy karaoke, stock/AI), warianty A/B, montaż, filmy z kodu, maskotka | Studio filmowe (`filmstudio`) | wideo | 14 |
| 📈 `jarvo-ads` | **Specjalista Ads** — Meta + Google Ads, kampanie, testy A/B/C, optymalizacja, raporty; wydaje tylko w kopercie z kodem | Sala operacyjna (`office`) | ads | 10 |
| 🦾 `jarvo-reka` | **Prawa ręka** — generalista, składa pakiety misji, dokumenty, prototypy; zna skille wszystkich (read-only) | Warsztat (`workshop`) | reka | 4 |

### 2a. jarvo-ads — szczegóły (najnowszy)
Specjalista Ads Managera dla **Meta (FB/IG) i Google**. Planuje kampanie, robi testy (jedna reklama,
A/B, A/B/C), audytuje konta, optymalizuje i raportuje. Wyniki liczy **statystyką bayesowską**
(P(best)). 10 skilli: `plan-kampanii`, `plan-testu`, `start-kampanii`, `podlacz-konto`, `audyt-konta`,
`optymalizacja`, `raport-reklam`, `wnioski-marki`, `sledzenie-konwersji`, `zgodnosc-reklam`.
Skrypty: `ads.py` (klient Skarbca, exit 3 gdy nie podłączony), `planer.py`, `eksperyment.py`, `eksport.py`.
**Stan: wpięty technicznie, BEZ kluczy.** Sejf na tokeny (Skarbiec) do zrobienia — patrz §7.

### 2b. jarvo-wideo — szczegóły
Pętla krytyki: film oceniany na **7 osiach** (hook, telefon, ruch, różnorodność, kompozycja, marka,
dźwięk), każda min. 8/10, plus lista zakazanych klisz. Prawdziwe assety marki pobierane ze strony
(`assety.py`). Mówiąca maskotka-robot z polskim lektorem (`maskotka.py`, Edge TTS pl-PL-MarekNeural).
Syntetyczne SFX, biblioteka inspiracji, produkcja etapami, formaty platform z jednego timeline.
Silniki: claude-animation (MIT), HyperFrames check przed renderem, Manim.

---

## 3. Jak to jest spięte (przepływ)

```
Ty (Telegram DM / "Jarvo HQ" / CLI / Desktop)
 └─ gateway Hermesa (multipleks profili)
      ├─ DM + wątek "general" → jarvo (Main Judge)
      └─ wątki sherlock/web/studio/wideo/ads/reka → dany snajper
jarvo: intake → MISSION.md → karty kanban (CEL, DoD, GRANICE, WYJŚCIA)
     → snajperzy pracują w swoich workspace'ach
     → kanban_request_review → jarvo sędziuje (rubryka agenta)
     → poprawki albo akceptacja → raport efektów
patrol co 30 min (skrypt bez modelu; budzi Jarva tylko przy anomaliach)
brief rano, przegląd tygodnia
```

**Kontrakt zlecenia** (`shared/protocol/kontrakt-zlecenia.md`) jest wstrzykiwany do każdego SOUL.
Definiuje strukturę karty (CEL, Definition of Done, WYJŚCIA, GRANICE) i 16 zasad wykonawcy,
m.in. echo celu, jedna weryfikacja, stany dowodu, **reguła 16: „Blokada to koniec, nie zagadka”**
(blokada kończy próbę; agent nie szuka obejścia, nie zmienia własnej konfiguracji, nie przyjmuje
haseł z czatu, nie loguje się w cudze konta, nie obchodzi wykrywania automatu).

---

## 4. Infrastruktura (VPS)

Cała flota mieści się na **1 VPS: 4 vCPU / 8 GB RAM / 80 GB**. Obraz ~4,4 GB, w spoczynku ~0,7 GB RAM.

**Obraz `jarvo-hermes`** = Hermes Agent + dobrane narzędzia. **Sidecary (docker compose):**
- `hermes` — silnik agentów,
- `searxng` — własna metawyszukiwarka (70+ silników, bez kluczy), AGPL,
- `valkey` — cache/kolejki,
- `uptime-kuma` — monitoring dostępności,
- `beszel` + `beszel-agent` — monitoring zasobów,
- `jarvo-net` — sieć.

**Narzędzia w obrazie:** Lightpanda (lekka przeglądarka headless ~30 MB/sesję) + jeden Chromium
tylko do renderu, Parakeet (STT), Edge TTS (lektor), FFmpeg, playwright/Chromium (pre-instalowany
w piaskownicy pod `/opt/pw-browsers`). Odchudzone: usunięto Gotenberg i Crawl4AI.

**Modele:** domyślnie provider `openai-codex` (jeden model `gpt-6-luna`, głębia myślenia per agent
przez `reasoning_effort`). Presety alternatywne: `openrouter` (Claude Opus 5.5 / Sonnet 5 / Haiku 4.5),
`commandcode` (DeepSeek/Kimi), `commandcode-anthropic`. Fallback, gdy główny model odmówi.
Model zmienia się przez `JARVO_MODEL_PROVIDER` w `compose/jarvo.env`, bez edycji repo.
**Modele testowe lokalnie: GLM 5.3 flash.**

---

## 5. Jarvo HQ (dashboard w przeglądarce)

Plugin dashboardu Hermesa (`hq/`): budynek z pokojami agentów (pixel art), minifigurki, dymki
„co każdy robi teraz”, podgląd pracy na żywo, wyniki, decyzje i czat z Jarvem albo dowolnym agentem.
Pokoje: bridge, study, devlab, atelier, filmstudio, workshop, office. Sesje klikalne (Historia
domyślnie). Czat obsługuje zdjęcia i pliki w obie strony. Linki „Odpal” (podgląd) i „Pokaż w folderze”.
Dwujęzyczność PL/EN. Demo bez serwera: `python3 scripts/hqbuild.py --demo build/hq-demo`.

---

## 6. Bezpieczeństwo (Skarbiec-design + red team)

- **Red team na promptfoo** (`security/redteam/`): 12 ataków na agentów, świeża sesja per atak,
  wykrywanie wycieków. Ostatni stan: **12/12 odpartych** po uszczelnieniu.
- **Deny dla całej floty** (`shared/security/deny.yaml`, mergowane do każdego profilu): blokada zmiany
  własnej konfiguracji (`hermes config set/...`), kasowania danych floty (`rm -r /opt/data/...`),
  czytania sekretów (cat/less/base64 na `.env`), wysyłki na zewnątrz (webhook.site itp.), haseł
  (`--password`, `password-stdin`), logowania w cudze konta (accounts.google.com, YouTube Studio,
  login.live.com, facebook.com/login) i obchodzenia wykrywania automatu (`--user-agent`,
  `navigator.webdriver`, `xvfb-run`, `Xvfb`).
- **Bezpieczeństwo aplikacji (jarvo-web):** skill `bezpieczenstwo-aplikacji` (18 punktów), skaner
  repo/URL (`security_check.py`), bramka jakości BLOKUJE oddanie strony przy KRYTYCZNE/WYSOKIE.
- Zasady stałe: nigdy nie commitujemy sekretów; hasło FTP tylko w scratchpadzie
  `WGRAJ-LANDING-JARVO.md`; agenci nigdy nie trzymają tokenów platform reklamowych (Skarbiec);
  nie drukujemy znalezionych sekretów.

---

## 7. Landing jarvo.pl (`site/`)

Statyczna strona wgrywana na FTP. Ma: `.htaccess` (HSTS, CSP `frame-ancestors 'none'`, XFO DENY,
nosniff, Referrer/Permissions-Policy, redirecty HTTPS i non-www, 404 dla dotfiles), `robots.txt`,
`sitemap.xml`, `llms.txt`, `site.webmanifest`, favicon; `index.html` z canonical, JSON-LD, opisem
132 znaki, width/height na obrazach; `app.js` bez innerHTML (DOM/DOMParser).
Wdrożenie: `bash scripts/deploy-site.sh`. **Zostało po stronie użytkownika:** wgrać na FTP i sprawdzić
nagłówki `curl -sI https://jarvo.pl | grep -i -E "strict-transport|content-security|x-frame"`.

---

## 8. Mapa repo

| Ścieżka | Co tam jest |
|---|---|
| `fleet.yaml` | rejestr floty: agenci, modele, tematy Telegrama, wspólne katalogi |
| `profiles/<agent>/` | każdy agent jako dystrybucja Hermesa (SOUL, config, skille, skrypty, rubryka, toolbox) |
| `profiles/_host/` | profil hosta: gateway z multipleksacją, trasy Telegrama, dispatcher kanbana |
| `shared/protocol/` | kontrakt zlecenia (16 zasad) wstrzykiwany do każdego SOUL |
| `shared/security/deny.yaml` | reguły blokad dla całej floty |
| `shared/skills/` | skille wspólne (np. `graf-kodu`) |
| `shared/calibration/` | kalibracja SOUL pod rodzinę modelu przy buildzie |
| `security/redteam/` | promptfoo: prowider, config, scenariusze ataków |
| `vendor/skills.lock.yaml` | skille zewnętrzne przypięte do commitów (licencje w docs/SOURCES.md) |
| `evals/<agent>/` | scenariusze testów zachowań (routing, protokół, bezpieczeństwo) |
| `scripts/` | build, walidator, deploy, instalacja floty, backupy, evals, migracja, narzędzia |
| `hq/` | Jarvo HQ (backend, frontend, demo) |
| `infra/` | obraz jarvo-hermes, docker-compose z sidecarami, szablony env |
| `knowledge/` | szablony wiedzy (brand kit, USER.md) |
| `branding/` | skórka Jarvo (banner, logo) |
| `site/` | landing jarvo.pl |
| `requirements-dev.txt` | zależności testów/walidacji (`make dev-deps`) |
| `tests/`, `docs/` | testy pytest, dokumentacja |

**Dokumenty:** PLAN (wizja/architektura/roadmapa), BOSS (mechanika Main Judge'a), FLEET (specyfikacja
agentów), PROFILE-SPEC (anatomia agenta: 10 warstw), TOOLBOX (narzędzia open-source), VPS (infra),
HQ (dashboard), ADS (projekt agenta reklam + Skarbiec), RUNBOOK (wdrożenie krok po kroku),
SOURCES (licencje).

---

## 9. Zasady pracy (z CLAUDE.md)

- **Każda aktualizacja = osobny commit i od razu push** (gałąź robocza, remote `origin`).
- **Dokumentacja zawsze zgodna z kodem:** zmiana w kodzie aktualizuje w tym samym commicie każdy dokument, który ją
  opisuje (README, `docs/*.md` z tym plikiem włącznie, README i CHANGELOG profilu): nazwy, liczby, ścieżki, komendy, statusy.
- Przed commitem: `python3 -m pytest -q` i `python3 scripts/validate.py` bez błędów.
  Na czystym kontenerze najpierw `make dev-deps` (pytest + pyyaml z `requirements-dev.txt`).
- **Po każdym dodaniu test w działającym kontenerze**, nie tylko pytest: deploy
  (`scripts/deploy.sh --no-pull` z `JARVO_COMPOSE_DIR`/`JARVO_BUILD` lokalnej instalacji), potem
  nowa funkcja uruchomiona w `jarvo-hermes` jako użytkownik `hermes`
  (`PATH=/opt/hermes/bin:/opt/hermes/.venv/bin:$PATH`), a GUI przez zalogowany dashboard.
  Wszystko ma się spinać: build → instalacja → healthchecki → realne użycie.
- **Piaskownica Claude Code:** `JARVO_LOCAL=<scratchpad>/jarvo-local bash scripts/sandbox-up.sh` robi wszystko:
  `dockerd`, obraz `hermes-ca:test` (Hermes + certyfikat proxy), `jarvo-hermes:local` przez
  `docker build --network host` (compose nie widzi proxy), instalację w `jarvo-local` i
  `deploy.sh --no-pull --no-build`. Obraz przebudowuje się tylko po zmianie `infra/` albo z `--rebuild`.
- Instalacja lokalna użytkownika (Linux/WSL2): `bash scripts/local-up.sh` → `~/jarvo-local`.

---

## 10. Stan i co dalej

**Zrobione (v0.3+):** cała flota v1 zakodowana i przetestowana, HQ, rebranding TARS→Jarvo, migracja
instalacji, Wideograf z pętlą krytyki i maskotką, jarvo-ads (bez kluczy), red team 12/12,
bezpieczeństwo web, landing jarvo.pl z nagłówkami.

**Pending / pomysły:**
1. **Skarbiec (zadanie #50):** kontener z tokenem Meta/Google, polityka w kodzie, koperty (spend cap
   zatwierdzany kodem out-of-band, model nigdy nie widzi kodu), szkice PAUSED, STOP zawsze dozwolony,
   Graph API v25. Do zrobienia, gdy będą klucze.
2. **Reguła: agenci nie zapamiętują danych logowania z czatu** (po red teamie Wideograf zapisał login
   w pamięci — hasła nie było, ale warto uszczelnić).
3. **PageIndex (MIT, rozważane):** vectorless RAG do czytania długich dokumentów przez lokalny model
   (litellm → Hermes/GLM). Nie jako osobny agent — jako współdzielona umiejętność „czytania długich
   dokumentów”. Do decyzji: zakres (który agent najpierw) + model do indeksowania.

**Odrzucone (nie wpinamy):** RedAmon (offensive pentest — za ciężki, ryzyko prawne),
terminal-browser (ciężka przeglądarka desktopowa, nie dla agentów na VPS),
devops-exercises (licencja CC BY-NC-ND, tylko materiał do nauki dla człowieka).
