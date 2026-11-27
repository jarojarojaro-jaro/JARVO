# Wtyczka zgód Jarva (jarvo-zgody)

Tryby zgód jak w Claude Code dla natywnego Jarva. Bez kontenera terminal agenta działa z prawami właściciela, więc
zgody są główną ochroną. To kontrola, nie izolacja: polecenie terminala może przeczytać wszystko, co właściciel.
Plan i uzasadnienie: [docs/NATYWNIE.md, sekcja (d)](../docs/NATYWNIE.md#d-pozwolenia-jak-w-claude-code) i decyzja I08
(domyślny tryb „projekt”, tryb pełny tylko na jedną sesję).

Wtyczka Hermesa (`plugin/`: `__init__.py`, `obraz.py`, `plugin.yaml`) ma hak `pre_tool_call`, polecenie `/tryb`
i middleware `tool_execution` z `obraz.py`. Hak zwraca `approve` (prośba trafia do bramki zgód Hermesa: raz, sesja,
zawsze, odmowa; w CLI, TUI, Telegramie i w HQ przez `/v1/runs`), `block` albo nic. Middleware oddaje wynik narzędzia
MCP z obrazem (np. `shot` telefonu, który Hermes zamienia na tekst `MEDIA:<plik>`) jako obraz dla modelu głównego
(koperta `_multimodal`, JPEG o dłuższym boku do 1280 px, tekst wyniku bez zmian), gdy model przyjmuje obraz według
tej samej bramki co zrzut `computer_use` (wpisy modeli w `jarvo/flota.py`, `MODELE_Z_OBRAZEM`).

| Tryb | Co robi hak |
|---|---|
| **pytaj** | pyta o `write_file`, `patch` (także łatki V4A), `execute_code`, `process_manage` i `cronjob_manage` (działania zmieniające) oraz o terminal spoza listy poleceń tylko do odczytu |
| **projekt** | jak pytaj, ale bez pytania zapisy i proste polecenia plikowe (`mkdir`, `touch`, `cp`, `mv`, `rm`, `rmdir`, `sed -i`, `tee`, `>` i `>>`), gdy rzeczywista ścieżka leży w folderze projektu, w katalogu roboczym karty, w skarbcu (`JARVO_KNOWLEDGE_DIR`) albo w misjach (`JARVO_MISSIONS_DIR`, dziennik Jarva) |
| **auto** (domyślny, decyzja właściciela 14.11) | bez pytania polecenia terminala, zapisy, `execute_code`, procesy i rutyny; pyta tylko o chronione miejsca (niżej) i o `confirm` na telefonie, gdy cel wygląda na płatność albo usunięcie konta; masowe kasowanie i zapis `config.yaml` blokuje jak w każdym trybie. Z człowiekiem; na karcie i w rutynie zasady bez zmian (niżej) |
| **pełny** | tylko na sesję: `jarvo chat --tryb pelny` (czyli `--yolo`) albo `/yolo`; Hermes zatwierdza prośby sam; wtyczka nigdy nie włącza go sama, a w każdym profilu blokuje pod nim narzędzia ekranu i telefonu (`computer_use`, `komputer`, `mcp__phone__*`; ekran i telefon mają Jarvo i agent biznesowy z przydziałem) |

Zawsze, w każdym trybie:
- zapis `config.yaml` Hermesa (profilu i katalogu danych) = blokada;
- zapis w kodzie floty = blokada z radą, bez pytania (z człowiekiem, bez niego i pod YOLO): `skills`, `plugins`,
  `hooks`, `scripts`, `SOUL.md` i `mcp.json` każdego profilu i hosta, `<JARVO_ROOT>/program` i `build`, kod Hermesa
  (`HERMES_SRC`), Jarva (`JARVO_REPO`) i tej wtyczki. Rada dla agenta: zmiana floty (nowy albo zmieniony skill,
  wtyczka, config agenta) to zlecenie dla Claude Code w `<misje>/DLA-CLAUDE.md` (repo JARVO, skan skilli, wdrożenie);
  zapis w zainstalowanym profilu znika przy aktualizacji i omija skan. 14.11 Jarvo wgrał tak ręcznie skill do
  `jarvo-web`, a właściciel osiem razy klikał „Always”;
- zgoda na `AGENTS.md`, `CLAUDE.md`, `SOUL.md` i chronione miejsca: `.git`, `.vscode`, `.idea`, `.claude`, `.hermes`,
  `.gitconfig`, `.bashrc`, `.zshrc`, `.npmrc`, `.mcp.json` (i inne pliki startowe powłoki), reszta danych Jarva
  (`HERMES_HOME`, `JARVO_ROOT`: sekrety, stan zgód, pamięć, bazy; poza `jarvo/workspaces`, skarbcem, misjami
  i katalogami roboczymi Hermesa w każdym profilu: `cache` (brudnopis `cache/scratch`), `home`, `workspace`, `plans`,
  `sandboxes`, `audio_cache`, `image_cache`). Hermes nie pozwala wtyczce ukryć przycisku „Always”, a klucz reguły
  obejmuje ten sam plik albo to samo polecenie, więc treść takiej prośby kończy się zdaniem „Stała zgoda tu nie
  działa: …”. W trybie pełnym o te miejsca nie da się zapytać, więc są blokowane;
- o polecenia, które Hermes sam uzna za niebezpieczne, pyta tylko Hermes (bez drugiego pytania). Pliki instrukcji
  przez `write_file` i `patch` też pyta sam Hermes (zawsze, także pod YOLO). Wyjątek: masowe kasowanie blokuje
  strażnik kasowania (niżej), zanim Hermes o nie zapyta;
- `kill`, `pkill` i `killall` pracownika karty kanbana albo Hermesa = blokada z radą `kanban_block` / `kanban_complete`
  ([strażnik pracowników kart](#strażnik-pracowników-kart));
- decyzja przypisana właścicielowi bez jego cytatu i czasu (tekst narzędzi kanbana, zapis w misjach i skarbcu) =
  blokada z radą ([decyzja właściciela tylko z cytatem](#decyzja-właściciela-tylko-z-cytatem));
- telefon (serwer MCP `phone` z PHONEUSE po `jarvo telefon on`, [docs/MOBILE.md](../docs/MOBILE.md)):
  `mcp__phone__act` i `mcp__phone__batch` z `confirm: true` (na wierzchu, w `args` albo w kroku `batch`) omijają
  bramkę `needs_confirm` telefonu, więc z człowiekiem to prośba z treścią akcji (zgoda = „tak” dla tej jednej akcji;
  „zawsze” niczego nie zapamiętuje), na karcie kanbana z linią `ZGODA WŁAŚCICIELA` w treści karty przepuszczenie, a bez
  człowieka i w trybie pełnym blokada (na karcie bez tej linii z poradą `kanban_block(kind="needs_input")`). Pozostałe
  narzędzia telefonu wtyczka zostawia Hermesowi. Pod YOLO
  każdy profil ma zablokowany telefon tak jak `computer_use` i `komputer` (od 14.11; wcześniej tylko `jarvo`).

Folder projektu to katalog startu czatu: `JARVO_FOLDER_PROJEKTU` albo `TERMINAL_CWD` (u pracownika karty: katalog
karty). Katalog domowy i korzeń dysku nie są folderem projektu: wtedy tryb projekt pyta o każdy zapis. Ścieżki Git Bash
`/c/...` znaczą `C:\...`, a `$HOME` i `~` w poleceniu mają na Windows postać `/c/Users/...` jak w Git Bash (także
w `sh -c "…"` i `eval`); na Windows i macOS porównanie jest bez wielkości liter; dowiązania, junction i `..` liczą się
po rozwiązaniu.

Bez człowieka (karta kanbana, rutyna, `-q`, podagent `delegate_task`, webhook i każda sesja, w której nikt nie
odpowie na prośbę) hak nigdy nie zwraca `approve`. Przechodzą zapisy w katalogu karty (`HERMES_KANBAN_WORKSPACE`),
w skarbcu (`JARVO_KNOWLEDGE_DIR`), w misjach (`JARVO_MISSIONS_DIR`) i to, co tryb przepuszcza bez pytania w folderze
projektu. Reszta zapisów to blokada z poradą (na karcie: `kanban_block(kind="needs_input")`), tak samo `execute_code`
i zmiany rutyn. Polecenia, których celów nie da się ustalić, zostają polityce Hermesa (`approvals.cron_mode`,
`single_query_mode`), poza kasowaniem rekurencyjnym albo wymuszonym (strażnik kasowania). Błąd wtyczki też kończy się
blokadą.

Wybór trybu: `/tryb` w sesji, potem `JARVO_TRYB_ZGOD` (`auto`, `projekt`, `pytaj`, `pelny`; ustawia `jarvo chat --tryb`),
potem plik profilu `<HERMES_HOME>/plugin-data/jarvo-zgody/stan.json` (zapisuje go `/tryb auto`, `/tryb pytaj` i `/tryb projekt`),
na końcu „auto”. Trybu nie trzymamy w `approvals.mode`, bo wdrożenie nadpisuje `approvals`. Odpowiedź „zawsze”
zapisuje w `command_allowlist` wąski klucz `plugin_rule:jarvo-zgody:<narzędzie>:<odcisk folderu>:<skrót treści>`.

Testy: `tests/test_zgody.py` (atrapa kontekstu wtyczki, bez Hermesa). Budowa i instalacja wtyczki we flocie
(`scripts/build.py`, instalator, `jarvo chat --tryb`) to etap E4.

## Strażnik kasowania

Agent nigdy nie skasuje hurtem ani nie zniszczy danych właściciela. Strażnik działa przed resztą oceny, w każdym trybie:
z człowiekiem (pytaj, projekt), bez człowieka (karta, rutyna, `-q`, podagent) i pod YOLO. Zwraca `block`, nie
`approve`, więc nie omija go ani zgoda „zawsze”, ani `command_allowlist`, ani strażnik `approvals.mode: smart`.
Blokada trafia do logu (`jarvo-zgody: zablokowane kasowanie (…)`) i mówi agentowi, co zrobić zamiast: skasować
konkretne pliki po jawnej ścieżce, a całość zostawić właścicielowi (na karcie `kanban_block(kind="needs_input")`).

| Chronione | Czego nie wolno |
|---|---|
| katalog domowy, `~/dev`, `~/strony`, `~/jarvo-testy`, każde repozytorium git (katalog z `.git`; poza katalogami tymczasowymi i katalogami kart), skarbiec, misje, katalogi robocze kart | skasować miejsca w całości, jego zawartości (`rm -rf ~/dev/*`, `rsync --delete` do niego) ani katalogu nad nim; skasować `.git` repozytorium |
| `~/.ssh`, `~/.config`, `~/.phoneuse` | skasować cokolwiek w środku, także pojedynczy plik, ani opróżnić pliku |
| dane i kod Jarva (`~/.local/share/jarvo`, `HERMES_HOME`, `JARVO_ROOT`, kod Hermesa; poza skarbcem, misjami, katalogami kart i HOME terminala) | skasować drzewo w środku ani nadpisać pliku |
| pliki startowe powłoki (`.bashrc`, `.gitconfig`…), pliki w `.git`, `config.yaml` Hermesa; pliki instrukcji (`AGENTS.md`, `SOUL.md`…) | usunąć (startowe) albo opróżnić (`> plik`, `truncate`, `dd of=`, `cp /dev/null`, `tee`, `write_file` z pustą treścią, `patch` usuwający całą treść, V4A `*** Delete File`) |

Rozpoznawane formy: `rm -r`/`-R`/`--recursive` i `-f` w każdej kolejności (także po celach), pod `sudo`, `env`,
`nice`, `timeout`, `command`, `xargs` i ze ścieżką programu (`/bin/rm`, `\rm`); `find … -delete` i `-exec rm` (bez
zawężenia nazwą, czasem albo rozmiarem; `-name '*'` to brak zawężenia); `shutil.rmtree`, `os.removedirs`,
`os.system` i `subprocess` w `python -c`, heredocu, here-stringu i `execute_code`; `fs.rmSync`, `rimraf`, `rmtree`
w `node`/`perl`/`ruby -e`; `bash -c`, `eval`, `$(…)`; `rsync --delete*`; `git clean -f`, `git reset --hard`,
`git push --force`/`-f`/`--mirror`/`+gałąź` w chronionym repozytorium (także `git -C`); `truncate`, `dd of=`, `mkfs`,
`wipefs`; wejście procesu w tle (`process_manage`). Kasowanie rekurencyjne albo wymuszone, którego celów nie da się
ustalić (zmienna, `$(…)`, pętla, `xargs`), też jest blokowane, z powodem w komunikacie.

Wolno: sprzątać katalog karty i katalogi tymczasowe (także klony repozytoriów w nich), kasować wyniki budowania
w projekcie (`node_modules`, `dist`, `.svelte-kit`, `__pycache__`), podkatalogi i pojedyncze pliki w drzewie roboczym,
używać zawężonego `find` (np. `find . -name '*.pyc' -delete`), dopisywać (`>>`), kasować samo dowiązanie (`rm link`).
Repozytorium zagnieżdżone w kasowanym katalogu strażnik szuka do 4 poziomów w głąb i w najwyżej 3000 katalogach.

## Strażnik pracowników kart

16.11 wtyczka odmówiła rozmowie `kanban_block` na karcie w pracy, więc Jarvo zabił jej pracownika poleceniem `kill`.
Dyspozytor kanbana uznaje zabitego pracownika za awarię („protocol violation”) i uruchamia kartę od nowa: trzy razy
z rzędu. Teraz, w każdym trybie (z człowiekiem, na karcie, w rutynie i pod YOLO), blokada bez pytania dla `kill`,
`pkill` i `killall`, które trafiają w:

- pracownika karty kanbana: linia poleceń `… chat -q "work kanban task <karta>"` (tak uruchamia go Hermes) albo
  `HERMES_KANBAN_TASK` w otoczeniu procesu Hermesa (Linux: `/proc`, macOS: `ps`; Windows: tylko treść polecenia);
- proces Hermesa, w którym działa wtyczka (rozmowa, brama, sam pracownik karty);
- wszystkie procesy (`kill -1`) albo grupę procesów z pracownikiem (`kill -- -PGID`);
- cel albo wzorzec, w którym widać `kanban`, `hermes`, numer karty (`t_` + 8 znaków) albo `$PPID` (`kill $(pgrep -f
  'work kanban task')`, `pgrep -f kanban | xargs kill`, `pkill -f hermes_cli`).

`pkill` i `killall` sprawdzamy na żywej tablicy procesów jak one same (nazwa albo z `-f` cała linia, `-x`, `-i`,
`-v`, `-P`, `-g`; `killall -r`, `-I`). Formy jak u strażnika kasowania: owijki (`sudo`, `nice`, `env`), `bash -c`,
`$(…)`, `xargs`, `python -c` i `execute_code` z `os.kill`/`os.killpg`, wejście procesu w tle.

Rada w blokadzie: na karcie `kanban_block(kind="needs_input", reason="…")` albo `kanban_complete(summary="…")`;
w rozmowie `kanban_block(task_id="<karta>", reason="…")`, po którym pracownika zamyka sam dyspozytor
(`reap_terminal_workers`). Dlatego rozmowa może zrobić `kanban_block` na karcie `running` (zatrzymanie, nie ocena;
komentarz z rozmowy nie dociera do pracownika karty tego samego profilu). Werdykty na kartach w toku dalej wydaje
tylko pracownik. Własne procesy (nagrywanie, serwer, `kill %1`, `kill -0`) wolno zatrzymać jak dotąd.

## Decyzja właściciela tylko z cytatem

16.11 Jarvo napisał w komentarzu karty „Decyzja Jarva: zaznaczyć NDA”, a 27 minut później w raporcie misji „decyzja
właściciela z 23:15”, choć właściciel nic wtedy nie napisał. Teraz, w każdym trybie, blokada z radą, gdy tekst
przypisuje decyzję właścicielowi („decyzja / zgoda / polecenie / wybór właściciela” albo „użytkownika”, „właściciel
zdecydował / zgodził się / zatwierdził / wybrał / kazał / polecił / zlecił / potwierdził / pozwolił”, „owner decided”)
bez jego słów w cudzysłowie („…”) i godziny albo daty w tym samym akapicie (do 300 znaków od przypisania):

- tekst narzędzi kanbana: `kanban_comment` (body), `kanban_block` i `kanban_request_changes` (reason),
  `kanban_complete` (summary, result), `kanban_request_review` (summary), `kanban_create` (title, body),
  `kanban_heartbeat` (note);
- nowe linie `write_file` i `patch` w misjach (`MISSION.md`, `DLA-CLAUDE.md`, raporty) i w skarbcu; linia, która już
  była w pliku, nie blokuje poprawki obok niej.

Przechodzi: `decyzja właściciela (16.11 23:15): „tak, zaznacz NDA”`, linia `ZGODA WŁAŚCICIELA` z cytatem i datą,
„decyzja Jarva: …”, prośba o decyzję, pytanie i przeczenie („potrzebna decyzja właściciela”, „czekam na decyzję
właściciela”, „czy właściciel zatwierdził”, „bez zgody właściciela”). Rada w blokadzie: cytat z czasem albo „decyzja
Jarva: …”, a gdy potrzebne jest „tak” właściciela, pytanie (na karcie `kanban_block(kind="needs_input")`).

## Strażnik nagrywania ekranu

Surowe nagrywanie ekranu (`ffmpeg`/`avconv` z `-f x11grab`, `gdigrab`, `avfoundation`, `kmsgrab`, `fbdev`, a także
`ddagrab`, `ximagesrc`, `wf-recorder`, `recordmydesktop`, `byzanz-record`, `simplescreenrecorder`, `vokoscreen`, `kazam`)
w terminalu, procesie w tle i `execute_code` to `block` w każdym trybie, z człowiekiem, bez niego i pod YOLO.
Komunikat kieruje do `nagraj.py` ze skilla `praca-na-ekranie` (`start "<krok>"`, `stop`, `film`): krótkie odcinki
udanych kroków, koniec nagrywania przy pierwszej odmowie Komputera albo bez ruchu na ekranie. Powód: 16.11 Jarvo
nagrywał pulpit surowym `ffmpeg -f x11grab` przez ~20 min, w kółko tę samą nieudaną weryfikację, choć sam pracował już
na telefonie. Blokada trafia do logu (`jarvo-zgody: zablokowane surowe nagrywanie ekranu (…)`).
