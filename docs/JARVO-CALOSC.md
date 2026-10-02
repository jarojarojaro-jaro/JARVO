# Jarvo — całość od A do Z

> Jeden opis wszystkiego. Do wklejenia na start nowej sesji, żeby mieć pełny kontekst
> bez czytania całego repo. Repo: `jarojarojaro-jaro/JARVO`, w piaskownicy Claude Code `/home/user/JARVO`.
> Gałąź robocza: `claude/epic-allen-qfjd0s`. Język pracy: polski.

---

## 0. W jednym zdaniu

Jarvo to **prywatny asystent AI zbudowany na Hermes Agent (Nous Research)**: na zewnątrz jeden
asystent, a w środku **flota wyspecjalizowanych agentów („snajperów”)** prowadzona przez **Jarva**
(Main Judge). Ty gadasz z Jarvem (albo z konkretnym specjalistą), a on rozdziela pracę, ocenia
wyniki i oddaje jeden sprawdzony rezultat. Wszystko działa na jednym VPS-ie i niczego nie zapomina.

**Kluczowa zasada:** nie forkujemy Hermesa. Repo jest jedynym źródłem prawdy — na serwerze nic
nie edytujemy ręcznie. Działania nieodwracalne (publikacja, wdrożenie, płatności, wysyłka) tylko
za zgodą człowieka. Jarvo jest zawsze nadrzędny: z innych projektów bierzemy tylko gotowe rozwiązania
i wzorce do kodu JARVO, nigdy system sterujący nad Jarvem.

---

## 1. Model działania: jeden Main Judge + flota snajperów

Inspiracja: firstmate. Rozmawiasz z jednym agentem, a on prowadzi załogę.

- **Snajper = specjalista.** Jedna dziedzina, własne skille, własna wiedza, własna pamięć.
  Dystrybucja snajpera ma znacznik `.no-bundled-skills` (bez katalogu skilli Hermesa) — dostaje tylko to,
  co mu damy (wyjątek: generalista `jarvo-reka`). Czego nie umie, tego nie robi: oddaje zadanie szefowi.
- **Jarvo = Main Judge (orkiestrator).** Sam nie robi pracy dziedzinowej. Robi cztery rzeczy:
  1. **intake** — rozumie, czego chcesz, dopytuje tylko o prawdziwe decyzje,
  2. **dispatch** — rozbija cel na karty kanbana i przypisuje snajperom,
  3. **judge** — każdy wynik wraca w statusie `review`; Jarvo ocenia go według rubryki agenta:
     akceptuje (`complete`) albo odsyła do poprawki (`request_changes`),
  4. **raport** — oddaje Ci jeden, sprawdzony wynik.
- **Bezpośredni kontakt zostaje** — z każdym snajperem pogadasz osobno, ale praca wieloetapowa
  zawsze idzie przez szefa.
- **Nowy agent nie może być „niewidzialny”.** Każdy specjalista ma w `fleet.yaml` pole `oddaj_gdy`, z którego build
  generuje tabelę „komu oddać” u Ręki, i występuje we wzorcach misji Jarva; walidator nie przepuści go bez tego.
- **Bez martwych ścieżek.** Skill, który potrzebuje usługi (np. Skarbca), deklaruje `metadata.jarvo.wymaga`; dopóki usługi
  nie ma w `infra/docker-compose.yml`, nie trafia do profilu, a SOUL agenta mówi, czego dziś nie zrobi.
- **Wspólne:** wiedza o Tobie (USER.md), brand kity (`knowledge/brands`) i **skarbiec wiedzy** (`knowledge/`, [WIEDZA.md](WIEDZA.md):
  notatki z linkami, orzeczenia z Twoich korekt, wyciągi z rozmów i kart; wtyczka `jarvo-wiedza` daje każdemu agentowi
  przypomnienia przed turą i narzędzia `wiedza_*`). Pamięć i skille są per agent
  (wyjątki: skille z `shared/skills/`: `graf-kodu` u Weba i Ręki, `transkrypcja-filmu` u Sherlocka, Wideografa i Ręki, `hooki` u Studia, Wideografa i Ads; Ręka czyta skille wszystkich).
- **Nadzór bez palenia tokenów:** dispatcher kanbana i patrol (skrypt bez modelu) pilnują floty
  i budzą Jarva tylko przy anomaliach albo gdy trzeba Twojej decyzji.

Poziomy autonomii: **A0** odczyt · **A1** szkice we własnym workspace · **A2** po zgodzie człowieka
· **A3** nigdy. Wszyscy specjaliści mają `autonomy_max: A1`.

---

## 2. Flota agentów (9 profili)

Każdy agent to osobna **dystrybucja Hermesa**: `SOUL.md` (osobowość + zasady), `config.yaml`
(model, toolset, deny), skille, skrypty, rubryka jakości, toolbox, dystrybucja.

| Agent | Rola | Pokój HQ | Temat Telegram | Skille |
|---|---|---|---|---|
| 🛰️ `jarvo` | **Main Judge** — intake, misje, karty, sędziowanie, raporty, patrol | Mostek dowodzenia (`bridge`) | general | 13 |
| 🔎 `jarvo-sherlock` | **Researcher-detektyw** — wieloźródłowy research, weryfikacja faktów, raporty z cytatami, transkrypcja filmu z linku | Gabinet śledczy (`study`) | sherlock | 7 |
| 🌐 `jarvo-web` | **Web Senior Dev** — strony/landingi, SEO techniczne, bezpieczeństwo aplikacji, wydajność, wdrożenie | Pracownia webowa (`devlab`) | web | 9 |
| 🎬 `jarvo-studio` | **Marketing i kreacja** — grafiki social, obrazy AI, copy PL, kampanie, kalendarze | Atelier kreatywne (`atelier`) | studio | 6 |
| 🎥 `jarvo-wideo` | **Wideograf** — krótkie filmy (lektor PL, napisy karaoke, stock/AI), warianty A/B, montaż, filmy z kodu, maskotka | Studio filmowe (`filmstudio`) | wideo | 15 |
| 📈 `jarvo-ads` | **Specjalista Ads** — Meta + Google Ads, kampanie, testy A/B/C, optymalizacja, raporty; wydaje tylko w kopercie z kodem | Sala operacyjna (`office`) | ads | 10 |
| 🎯 `jarvo-lowca` | **Łowca leadów** — sygnały zakupowe (KRS, przetargi BZP/TED, strony firm, oferty pracy), kwalifikacja wg profilu klienta, ranking z „dlaczego teraz”, kontakt opublikowany ze źródłem, monitoring; nic nie wysyła | Radar sprzedaży (`radar`) | lowca | 6 |
| 📱 `jarvo-mobile` | **Twórca aplikacji** — uczciwe „natywna czy PWA” z kosztami, darmowy audyt mobilny (App Store, Google Play, linki strona → aplikacja, PWA, opinie), aplikacje Expo z szablonu ze zgodnością ze sklepami, podgląd w HQ i Expo Go, bramka jakości (Android, iOS w CI), pakiet do sklepów z listą 44 punktów, wydanie za zgodą i nauka z odrzuceń, aplikacja ze strony firmy, utrzymanie (terminy, opinie, SDK, poprawki OTA za zgodą), kontrola paczek npm; konta zawsze właściciela | Pracownia aplikacji (`apps`) | mobile | 10 |
| 🦾 `jarvo-reka` | **Prawa ręka** — generalista, składa pakiety misji, dokumenty, prototypy; zna skille wszystkich (read-only) | Warsztat (`workshop`) | reka | 4 |

### 2a. jarvo-mobile — szczegóły (najnowszy)
Twórca aplikacji, etap 1 z [MOBILE.md](MOBILE.md): `natywna-czy-pwa` (`decyzja.py`: potrzeby → strona, PWA, karta
w Wallet, platforma albo aplikacja w sklepach; 19 funkcji, koszty licencji, ryzyko odrzucenia 4.2, opcje „blisko”)
i `audyt-mobilny` (`audyt_mobilny.py`: iTunes API z polską kartą, status przedsiębiorcy DSA i etykiety prywatności
ze strony App Store, Google Play: aktualizacja, docelowe API, oceny, Data safety; Universal Links i App Links z kopią
w CDN Apple i Digital Asset Links API; baner, odznaki, PWA, polityka prywatności; opinie z App Store z tematami skarg;
aplikacje partnerów oddzielone od aplikacji firmy). Etap 2: `nowa-aplikacja` i `podglad-aplikacji` (szablon
`templates/expo-jarvo` z Expo SDK 57 i elementami zgodności, `zgodnosc.py`, `aplikacja.py nowa/ustaw/sprawdz/podglad/
expo-go`, ikony z logo albo inicjałów, zrzuty iPhone 17 Pro Max i Pixel w obu motywach z kontrolami). Etap 3:
`bramka-aplikacji` (rubryka 10 osi, werdykt PASS / REVISE / BLOCK, testy wrogie: `wrogie.cjs` w przeglądarce,
`urzadzenie.py` na Androidzie przez adb, `ios_ci.py` w symulatorze iOS na GitHub Actions) i telefon testowy floty
(`jarvo android on`: emulator Google przy KVM albo Redroid przy binderze, ekran w HQ przez proxy `:9122` z tokenem).
Etap 4: `pakiet-do-sklepow` (`sklep_check.py`: 44 punkty z dowodem i numerem wytycznej, czyta konfigurację po wtyczkach,
AAB, IPA, metadane, obrazy i adresy; `pakiet.py`: szkic karty, grafiki Google, zrzuty w wymiarach sklepów bez alfy
i galeria w podglądzie HQ). Etap 5: `wydanie` (`wydanie.py`: plan i bramki, EAS Build, pobranie AAB i IPA z listą
kontrolną, TestFlight i testy Google, karta App Store; każdy krok A2 z dosłowną zgodą właściciela, do recenzji wysyła
on) i `odrzucenie` (`odrzucenie.py`: wytyczne z wiadomości recenzenta, poprawka / wyjaśnienie / odwołanie, odpowiedź
po angielsku, wiadomość jako obce dane, nauka jako nowe punkty listy N1, N2…). Etap 6: `aplikacja-ze-strony` (`ze_strony.py`:
strona firmy → dane, oferta z cenami, kolor i logo, sygnały i funkcje natywne z ★, szkice `aplikacja.yaml` i `zgodnosc.yaml`;
mniej niż 3 ★ = ryzyko 4.2; moduł `przypomnienia` w szablonie), `utrzymanie-aplikacji` (`utrzymanie.py`: stan z App Store
i opiniami, kalendarz terminów Google i Apple z `.ics`, plan Expo SDK, poprawka przez EAS Update tylko za zgodą i do buildu
o tym samym odcisku kodu natywnego), `paczki.py` (literówki, podszycia, nazwy zmyślone, świeże paczki i skrypty instalacyjne
przed `npx expo install`), 20 skilli zewnętrznych (Expo, Callstack, Vercel, ASO) i 3 ataki red teamu.

### 2a''. jarvo-lowca — szczegóły
Łowca leadów B2B z oficjalnych, darmowych źródeł: KRS (API MS: biuletyn dnia i odpisy; nazwiska zarządu maskowane),
e-Zamówienia BZP (ogłoszenia i wyniki ze zwycięzcą), TED, strony firm (`robots.txt`, uczciwy UA), wyszukiwarka.
Ocena: dopasowanie do `ICP.yaml` → świeżość → siła; kontakt tylko opublikowany przez firmę albo rejestr, ze źródłem;
przypomnienie o zgodzie na informację handlową (UŚUDE, PKE) i RODO w każdej liście. Skrypty: `krs.py`, `przetargi.py`,
`strona.py`, `leady.py`. Projekt: [LEADY.md](LEADY.md).

### 2a'. jarvo-ads — szczegóły
Specjalista Ads Managera dla **Meta (FB/IG) i Google**. Planuje kampanie, robi testy (jedna reklama,
A/B, A/B/C), audytuje konta, optymalizuje i raportuje. Wyniki liczy **statystyką bayesowską**
(P(best)). 10 skilli: `plan-kampanii`, `plan-testu`, `start-kampanii`, `podlacz-konto`, `audyt-konta`,
`optymalizacja`, `raport-reklam`, `wnioski-marki`, `sledzenie-konwersji`, `zgodnosc-reklam`.
Skrypty: `ads.py` (klient Skarbca, exit 3 gdy nie podłączony), `planer.py`, `eksperyment.py`, `eksport.py`.
**Stan: wpięty technicznie, BEZ kluczy.** Sejf na tokeny (Skarbiec) do zrobienia — patrz §10.

### 2b. jarvo-wideo — szczegóły
Pętla krytyki: film oceniany na **7 osiach** (hook, telefon, ruch, różnorodność, kompozycja, marka,
dźwięk), każda min. 8/10, plus lista zakazanych klisz. Prawdziwe assety marki pobierane ze strony
(`assety.py`). Mówiąca maskotka-robot z polskim lektorem (`maskotka.py`, Edge TTS pl-PL-MarekNeural).
Syntetyczne SFX, biblioteka inspiracji, produkcja etapami, formaty platform z jednego timeline.
Silniki: claude-animation (MIT), HyperFrames check przed renderem, Manim. Demo strony (`demo_strony.py`, metoda ECC
`ui-demo`): rozpoznanie → próba → nagranie z kursorem i napisami kroków, tylko nasz podgląd albo strona użytkownika.
Animacja z kodu ma twardy pomiar przed oddaniem (`html_wideo.py pomiar`: czas czytania, kadr i strefy UI platformy,
kontrast, czarne przerwy, martwe odcinki, rytm; „gotowe” tylko z pełnym i aktualnym raportem) i parametry
(`parametry.json`), które właściciel stroi na żywo w HQ.

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

**Kontrakt zlecenia** (`shared/protocol/kontrakt-zlecenia.md`) jest wstrzykiwany do każdego SOUL (Jarvo dostaje
tylko kształt karty i wyniku oraz zasady wspólne, bez zasad pracy wykonawcy: ~670 tokenów mniej na wywołanie).
Definiuje strukturę karty (CEL, Definition of Done, WYJŚCIA, GRANICE) i 17 zasad wykonawcy,
m.in. echo celu, jedna weryfikacja bez osłabiania kontroli, stany dowodu, poprawki po recenzji z prawem
do sprzeciwu popartego dowodem, **reguła 16: „Blokada to koniec, nie zagadka”** (blokada kończy próbę;
agent nie szuka obejścia, nie zmienia własnej konfiguracji, nie przyjmuje haseł z czatu, nie loguje się
w cudze konta, nie obchodzi wykrywania automatu) i **reguła 17: zgoda A2 dotyczy dokładnie tej wersji**
(odcisk plików `scripts/odcisk.py`; zmiana po zgodzie = nowa zgoda).

---

## 4. Infrastruktura (VPS)

Cała flota mieści się na **1 VPS: 4 vCPU / 8 GB RAM / 80 GB**. Obraz ~4,4 GB, w spoczynku ~0,7 GB RAM.

**Obraz `jarvo-hermes`** = Hermes Agent + dobrane narzędzia. **Sidecary (docker compose):**
- `hermes` — silnik agentów,
- `searxng` — własna metawyszukiwarka (70+ silników, bez kluczy), AGPL,
- `valkey` — magazyn SearXNG (cache, limiter),
- `uptime-kuma` — monitoring dostępności (opcjonalnie: profil compose `monitoring`, `deploy.sh --monitoring`),
- `beszel` + `beszel-agent` — monitoring zasobów (jw.),
- `jarvo-net` — sieć.

**Narzędzia w obrazie:** Lightpanda (lekka przeglądarka headless ~30 MB/sesję) + jedna Chromium z obrazu
Hermesa (`/usr/local/bin/chromium`: render, PDF, zrzuty, Lighthouse), Parakeet przez `jarvo-stt` (onnx-asr;
model ~0,65 GB pobierany przy pierwszym użyciu), FFmpeg (z obrazu Hermesa). Edge TTS (lektor) doinstalowuje
Hermes przy pierwszym użyciu. Odchudzone: usunięto Gotenberg i Crawl4AI. (W piaskownicy Claude Code osobno:
Playwright/Chromium w `/opt/pw-browsers`, poza obrazem.)

**Modele:** domyślnie provider `openai-codex` (jeden model `gpt-6-luna`, głębia myślenia per agent
przez `reasoning_effort`). Presety alternatywne: `openrouter` (Claude Opus 5.5 / Sonnet 5 / Haiku 4.5),
`commandcode` (DeepSeek/Kimi), `commandcode-anthropic`. Fallback, gdy główny model odmówi.
Model zmienia się przez `JARVO_MODEL_PROVIDER` w `compose/jarvo.env`, bez edycji repo.
**Modele testowe lokalnie: GLM 5.3 flash** — nie jest zestawem w `fleet.yaml`; ustawiany w `compose/jarvo.env`
przez `JARVO_MODEL_PROVIDER` + `JARVO_MODEL_FRONTIER/STRONG/FAST` (i `JARVO_MODEL_FALLBACK`), np. `commandcode`
+ `z-ai/glm-5.3-flash` (tak jak w `tests/test_model_provider.py`).

---

## 5. Jarvo HQ (dashboard w przeglądarce)

Plugin dashboardu Hermesa (`hq/`): budynek z pokojami agentów (pixel art), minifigurki, dymki
„co każdy robi teraz”, podgląd pracy na żywo, wyniki, decyzje i czat z Jarvem albo dowolnym agentem.
Pokoje: bridge, study, devlab, atelier, filmstudio, workshop, office, radar. Sesje klikalne (Historia
domyślnie). Czat obsługuje zdjęcia i pliki w obie strony. Linki „Odpal” (podgląd) i „Pokaż w folderze”.
Edytor filmów w stylu CapCut (uwagi na osi z kadrem dla Wideografa) i podgląd animacji z kodu na żywo z suwakami
parametrów ([HQ.md §2a–2b](HQ.md#2a-edytor-filmów)). Dwujęzyczność PL/EN. Demo bez serwera: `python3 scripts/hqbuild.py --demo build/hq-demo`.
Obok BASE zakładka **Wiedza** (`/wiedza`, wtyczka `jarvo-wiedza`): graf skarbca wiedzy, foldery i notatki, szukanie, orzeczenia
z formularzem, skrzynka szkiców z kompilacją, lint, dziennik ([WIEDZA.md](WIEDZA.md)).

---

## 6. Bezpieczeństwo (Skarbiec-design + red team)

- **Red team na promptfoo** (`security/redteam/`): 21 ataków na agentów (w tym orzeczenie wstrzyknięte przez treść strony, klucz do zapisania w skarbcu wiedzy, paczka-literówka i sekret w kodzie aplikacji mobilnej), świeża sesja per atak,
  wykrywanie wycieków. Ostatni zapisany przebieg objął 12 ówczesnych ataków: **12/12 odpartych** po uszczelnieniu;
  dla 9 dodanych później repo nie ma jeszcze wyniku (przebieg wymaga działającej floty z kluczem modelu).
- **Deny dla całej floty** (`shared/security/deny.yaml`, mergowane do każdego profilu): blokada zmiany
  własnej konfiguracji (`hermes config set/...`), kasowania danych floty (`rm -r /opt/data/...`),
  czytania sekretów (cat/less/base64 na `.env`), wysyłki na zewnątrz (webhook.site itp.), haseł
  (`--password`, `password-stdin`), logowania w cudze konta (accounts.google.com, YouTube Studio,
  login.live.com, facebook.com/login) i obchodzenia wykrywania automatu (`--user-agent`,
  `navigator.webdriver`, `xvfb-run`, `Xvfb`).
- **Skan skilli z cudzych repo** (`scripts/skan_skilli.py`, przy każdym buildzie): skaner Hermesa + wzorce
  getsentry `skill-scanner` i ECC (wstrzyknięcia, `curl|sh`, sekrety, ukryte znaki, hooki, `postinstall`).
  High/critical bez przejrzanego wyjątku (`vendor/skan-wyjatki.yaml`, przypięty do commitu) zatrzymuje wdrożenie.
- **Bezpieczeństwo aplikacji (jarvo-web):** skill `bezpieczenstwo-aplikacji` (26 punktów, w tym funkcje AI, sesje,
  CSRF, kopie zapasowe), skaner repo/URL (`security_check.py`: niebezpieczne ustawienia domyślne, zależności nieistniejące
  albo podszyte, klucze w JS strony), nieniszczące próby na podglądzie (`security_check.py atak`: trasy bez sesji, IDOR
  na dwóch kontach, limit logowania, upload, wylogowanie), audyt zależności (`supply-chain-risk-auditor`,
  Trail of Bits), przegląd kodu wg OWASP (`security-review`, getsentry); bramka jakości BLOKUJE oddanie strony przy
  KRYTYCZNE/WYSOKIE.
- Zasady stałe: nigdy nie commitujemy sekretów; hasło FTP tylko w scratchpadzie
  `WGRAJ-LANDING-JARVO.md`; agenci nigdy nie trzymają tokenów platform reklamowych (Skarbiec);
  nie drukujemy znalezionych sekretów.

---

## 7. Landing jarvo.pl (`site/`)

Statyczna strona wgrywana na FTP. Ma: `.htaccess` (HSTS, CSP `frame-ancestors 'none'`, XFO DENY,
nosniff, Referrer/Permissions-Policy, redirecty HTTPS i non-www, 404 dla dotfiles), `robots.txt`,
`sitemap.xml`, `llms.txt`, `site.webmanifest`, favicon; `index.html` z canonical, JSON-LD, opisem
130 znaków, width/height na obrazach; `app.js` bez innerHTML (DOM/DOMParser).
Wdrożenie: `bash scripts/deploy-site.sh`. **Zostało po stronie użytkownika:** wgrać na FTP i sprawdzić
nagłówki `curl -sI https://jarvo.pl | grep -i -E "strict-transport|content-security|x-frame"`.

---

## 8. Mapa repo

| Ścieżka | Co tam jest |
|---|---|
| `fleet.yaml` | rejestr floty: agenci, modele, tematy Telegrama, wspólne katalogi |
| `profiles/<agent>/` | każdy agent jako dystrybucja Hermesa (SOUL, config, skille, skrypty, rubryka, toolbox) |
| `profiles/_host/` | profil hosta: gateway z multipleksacją, trasy Telegrama, dispatcher kanbana |
| `shared/protocol/` | kontrakt zlecenia (17 zasad) wstrzykiwany do każdego SOUL |
| `shared/security/deny.yaml` | reguły blokad dla całej floty |
| `shared/skills/` | skille wspólne (`graf-kodu`; `transkrypcja-filmu`: link do filmu → tekst mowy; `hooki`: trzy warstwy hooka, 18 taktyk) |
| `shared/calibration/` | kalibracja SOUL pod rodzinę modelu przy buildzie |
| `shared/templates/` | szablony SOUL, skilla, evals i toolboxa (`make new-agent`) |
| `security/redteam/` | promptfoo: prowider, config, scenariusze ataków |
| `vendor/skills.lock.yaml` | skille zewnętrzne przypięte do commitów (licencje w docs/SOURCES.md) |
| `vendor/skan-wyjatki.yaml` | przejrzane fałszywe alarmy skanu skilli zewnętrznych, przypięte do commitu źródła |
| `evals/<agent>/` | scenariusze testów zachowań (w zakresie, poza zakresem, routing, protokół, bezpieczeństwo) |
| `scripts/` | build, walidator, deploy, instalacja floty, backupy, evals, migracja, narzędzia |
| `hq/` | Jarvo HQ (backend, frontend, demo) |
| `infra/` | obraz jarvo-hermes, docker-compose z sidecarami, szablony env |
| `knowledge/` | szablon brand kitu (`brands/_szablon`); szablon USER.md jest w skillu `onboarding-interview` Jarva |
| `wiedza/` | skarbiec wiedzy (drugi mózg): `wiedza.py` (zasiew, indeks FTS5, szukanie, szkice, orzeczenia, lint, graf, git) i `SCHEMA.md`; projekt w [WIEDZA.md](WIEDZA.md) |
| `branding/` | skórka Jarvo (banner, logo) |
| `site/` | landing jarvo.pl |
| `install.sh`, `install.ps1`, `bin/jarvo` | instalator jednym poleceniem (Linux/WSL2: sam instaluje pakiety i Docker Engine; macOS; Windows): repo do `~/jarvo`, polecenie `jarvo` (`up`, `status`, `update`, `uninstall`…); plan reszty (macOS, Windows, obraz z rejestru) w [INSTALER.md](INSTALER.md) |
| `requirements-dev.txt` | zależności testów/walidacji (`make dev-deps`: pytest, pyyaml, shellcheck) |
| `tests/`, `docs/` | testy pytest, dokumentacja |

**Dokumenty:** PLAN (wizja/architektura/roadmapa), BOSS (mechanika Main Judge'a), FLEET (specyfikacja
agentów), PROFILE-SPEC (anatomia agenta: 10 warstw), TOOLBOX (narzędzia open-source), VPS (infra),
HQ (dashboard), ADS (projekt agenta reklam + Skarbiec), LEADY (Łowca leadów), KLIPY (clipmaker),
WIEDZA (skarbiec wiedzy: drugi mózg floty, projekt do akceptacji), RUNBOOK (wdrożenie krok po kroku), INSTALER (plan instalatora jednym poleceniem na trzy systemy), ROZWOJ-FLOTY (plan dopracowania agentów), MOBILE (projekt Twórcy aplikacji),
SOURCES (licencje).

---

## 9. Zasady pracy (z CLAUDE.md)

- **Każda aktualizacja = osobny commit i od razu push** (gałąź robocza, remote `origin`).
- **Dokumentacja zawsze zgodna z kodem:** zmiana w kodzie aktualizuje w tym samym commicie każdy dokument, który ją
  opisuje (README, `docs/*.md` z tym plikiem włącznie, README i CHANGELOG profilu): nazwy, liczby, ścieżki, komendy, statusy.
  `validate.py` pilnuje linków i kotwic, pełnej listy floty w dokumentach przeglądowych i liczb skilli/evals w tabelach.
- Przed commitem: `python3 -m pytest -q` i `python3 scripts/validate.py` bez błędów.
  Na czystym kontenerze najpierw `make dev-deps` (pytest, pyyaml i shellcheck z `requirements-dev.txt`).
- **Po każdym dodaniu test w działającym kontenerze**, nie tylko pytest: deploy
  (`scripts/deploy.sh --no-pull` z `JARVO_COMPOSE_DIR`/`JARVO_BUILD` lokalnej instalacji), potem
  nowa funkcja uruchomiona w `jarvo-hermes` jako użytkownik `hermes`
  (`PATH=/opt/hermes/bin:/opt/hermes/.venv/bin:$PATH`), a GUI przez zalogowany dashboard.
  Wszystko ma się spinać: build → instalacja → healthchecki → realne użycie.
- **Piaskownica Claude Code:** `JARVO_LOCAL=<scratchpad>/jarvo-local bash scripts/sandbox-up.sh` robi wszystko:
  `dockerd`, obraz `hermes-ca:test` (Hermes + certyfikat proxy), `jarvo-hermes:local` przez
  `docker build --network host` (compose nie widzi proxy), instalację w `jarvo-local` i
  `deploy.sh --no-pull --no-build`. Obraz przebudowuje się tylko po zmianie `infra/` lub `branding/` albo z `--rebuild`.
- Instalacja lokalna użytkownika (Linux/WSL2, macOS): `install.sh` (na Linuksie sam doinstalowuje pakiety i Docker
  Engine; repo do `~/jarvo`) → `jarvo up` (`bin/jarvo` → `scripts/local-up.sh`) → `~/jarvo-local` (`compose/`,
  `secrets/`, `build/`, `data/`; stare `~/tars-local` przenoszone samo); pomocnik aktualizacji jako usługa
  `systemd --user` (`jarvo autostart on`). Test od zera w piaskownicy: `scripts/install-test.sh`.

---

## 10. Stan i co dalej

**Zrobione (v0.3+):** cała flota v1 zakodowana i przetestowana, HQ, rebranding TARS→Jarvo, migracja
instalacji, Wideograf z pętlą krytyki i maskotką, jarvo-ads (bez kluczy), red team 12/12,
bezpieczeństwo web, landing jarvo.pl z nagłówkami.

**Pending / pomysły:**
1. **Skarbiec (zadanie #50):** kontener z tokenem Meta/Google, polityka w kodzie, koperty (spend cap
   zatwierdzany kodem out-of-band, model nigdy nie widzi kodu), szkice PAUSED, STOP zawsze dozwolony,
   Graph API v25. Do zrobienia, gdy będą klucze.
2. ✅ **Agenci nie zapisują danych logowania w pamięci (`memory`).** Po red teamie Wideograf zapisał login w pamięci
   (hasła tam nie było). Hasła i logowanie w cudze konta blokują reguła 16 kontraktu i `deny.yaml`; zapis loginu, hasła,
   klucza albo numeru karty do `memory` odrzuca teraz strażnik narzędzi wtyczki `jarvo-wiedza` (hak `pre_tool_call`
   u każdego agenta, [WIEDZA.md](WIEDZA.md) §4). Ten sam hak trzyma limit płatnej generacji AI na kartę.
3. **Skarbiec wiedzy (drugi mózg floty), projekt w [WIEDZA.md](WIEDZA.md) (zbudowany 2026-09-30, etapy 1–6 z 7:
   skarbiec zasiewany przy wdrożeniu, `wiedza.py`, wtyczka `jarvo-wiedza` u każdego agenta, kompilacja `kompilacja.py`,
   zakładka „Wiedza”, synteza w przeglądzie tygodnia, red team, evals; **na VPS zostaje pierwsza kompilacja z modelem**):** jeden folder
   notatek Markdown z linkami (`knowledge/`), wzorzec LLM Wiki Karpathy'ego; wtyczka Hermesa `jarvo-wiedza` jako dostawca
   pamięci (przypomnienia przed turą, wyciąg po sesji i przed kompresją, 4 narzędzia), kompilacja tanim modelem (jeden
   piszący), orzeczenia z Twoich korekt, lint, punkty zapisu git, zakładka „Wiedza” z grafem w dashboardzie.
4. **PageIndex (MIT, rozważane):** vectorless RAG do czytania długich dokumentów przez lokalny model
   (litellm → Hermes/GLM). Nie jako osobny agent — jako współdzielona umiejętność „czytania długich
   dokumentów”. Do decyzji: zakres (który agent najpierw) + model do indeksowania.

**Odrzucone (nie wpinamy):** RedAmon (offensive pentest — za ciężki, ryzyko prawne),
terminal-browser (ciężka przeglądarka desktopowa, nie dla agentów na VPS),
devops-exercises (licencja CC BY-NC-ND, tylko materiał do nauki dla człowieka).
