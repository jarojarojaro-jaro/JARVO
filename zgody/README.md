# Wtyczka zgód Jarva (jarvo-zgody)

Tryby zgód jak w Claude Code dla natywnego Jarva. Bez kontenera terminal agenta działa z prawami właściciela, więc
zgody są główną ochroną. To kontrola, nie izolacja: polecenie terminala może przeczytać wszystko, co właściciel.
Plan i uzasadnienie: [docs/NATYWNIE.md, sekcja (d)](../docs/NATYWNIE.md#d-pozwolenia-jak-w-claude-code) i decyzja I08
(domyślny tryb „projekt”, tryb pełny tylko na jedną sesję).

Wtyczka Hermesa (`plugin/`: `__init__.py`, `plugin.yaml`) ma hak `pre_tool_call` i polecenie `/tryb`. Hak zwraca
`approve` (prośba trafia do bramki zgód Hermesa: raz, sesja, zawsze, odmowa; w CLI, TUI, Telegramie i w HQ przez
`/v1/runs`), `block` albo nic.

| Tryb | Co robi hak |
|---|---|
| **pytaj** | pyta o `write_file`, `patch` (także łatki V4A), `execute_code`, `process_manage` i `cronjob_manage` (działania zmieniające) oraz o terminal spoza listy poleceń tylko do odczytu |
| **projekt** | jak pytaj, ale bez pytania zapisy i proste polecenia plikowe (`mkdir`, `touch`, `cp`, `mv`, `rm`, `rmdir`, `sed -i`, `tee`, `>` i `>>`), gdy rzeczywista ścieżka leży w folderze projektu, w katalogu roboczym karty, w skarbcu (`JARVO_KNOWLEDGE_DIR`) albo w misjach (`JARVO_MISSIONS_DIR`, dziennik Jarva) |
| **auto** (domyślny, decyzja właściciela 14.11) | bez pytania polecenia terminala, zapisy, `execute_code`, procesy i rutyny; pyta tylko o chronione miejsca (niżej) i o `confirm` na telefonie, gdy cel wygląda na płatność albo usunięcie konta; masowe kasowanie i zapis `config.yaml` blokuje jak w każdym trybie. Z człowiekiem; na karcie i w rutynie zasady bez zmian (niżej) |
| **pełny** | tylko na sesję: `jarvo chat --tryb pelny` (czyli `--yolo`) albo `/yolo`; Hermes zatwierdza prośby sam; wtyczka nigdy nie włącza go sama, a w profilu `jarvo` blokuje pod nim narzędzia ekranu i telefonu (`computer_use`, `komputer`, `mcp__phone__*`) |

Zawsze, w każdym trybie:
- zapis `config.yaml` Hermesa (profilu i katalogu danych) = blokada;
- zgoda na `AGENTS.md`, `CLAUDE.md`, `SOUL.md` i chronione miejsca: `.git`, `.vscode`, `.idea`, `.claude`, `.hermes`,
  `.gitconfig`, `.bashrc`, `.zshrc`, `.npmrc`, `.mcp.json` (i inne pliki startowe powłoki), dane Jarva (`HERMES_HOME`,
  `JARVO_ROOT`, kod Hermesa i wtyczki; poza `jarvo/workspaces`, skarbcem, misjami i katalogami roboczymi Hermesa
  w każdym profilu: `cache` (brudnopis `cache/scratch`), `home`, `workspace`, `plans`, `sandboxes`, `audio_cache`, `image_cache`). W trybie pełnym o te miejsca nie
  da się zapytać, więc są blokowane;
- o polecenia, które Hermes sam uzna za niebezpieczne, pyta tylko Hermes (bez drugiego pytania). Pliki instrukcji
  przez `write_file` i `patch` też pyta sam Hermes (zawsze, także pod YOLO). Wyjątek: masowe kasowanie blokuje
  strażnik kasowania (niżej), zanim Hermes o nie zapyta;
- telefon (serwer MCP `phone` z PHONEUSE po `jarvo telefon on`, [docs/MOBILE.md](../docs/MOBILE.md)):
  `mcp__phone__act` i `mcp__phone__batch` z `confirm: true` (na wierzchu, w `args` albo w kroku `batch`) omijają
  bramkę `needs_confirm` telefonu, więc z człowiekiem to prośba z treścią akcji (zgoda = „tak” dla tej jednej akcji;
  „zawsze” niczego nie zapamiętuje), na karcie kanbana z linią `ZGODA WŁAŚCICIELA` w treści karty przepuszczenie, a bez
  człowieka i w trybie pełnym blokada (na karcie bez tej linii z poradą `kanban_block(kind="needs_input")`). Pozostałe
  narzędzia telefonu wtyczka zostawia Hermesowi. Pod YOLO
  `jarvo` ma zablokowany telefon tak jak `computer_use` i `komputer`.

Folder projektu to katalog startu czatu: `JARVO_FOLDER_PROJEKTU` albo `TERMINAL_CWD` (u pracownika karty: katalog
karty). Katalog domowy i korzeń dysku nie są folderem projektu: wtedy tryb projekt pyta o każdy zapis. Ścieżki Git Bash
`/c/...` znaczą `C:\...`; na Windows i macOS porównanie jest bez wielkości liter; dowiązania, junction i `..` liczą się
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
