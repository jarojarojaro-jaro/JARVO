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
| **projekt** (domyślny) | jak pytaj, ale bez pytania zapisy i proste polecenia plikowe (`mkdir`, `touch`, `cp`, `mv`, `rm`, `rmdir`, `sed -i`, `tee`, `>` i `>>`), gdy rzeczywista ścieżka leży w folderze projektu albo w katalogu roboczym karty |
| **pełny** | tylko na sesję: `jarvo chat --tryb pelny` (czyli `--yolo`) albo `/yolo`; Hermes zatwierdza prośby sam; wtyczka nigdy nie włącza go sama i blokuje go w `jarvo-operator` |

Zawsze, w każdym trybie:
- zapis `config.yaml` Hermesa (profilu i katalogu danych) = blokada;
- zgoda na `AGENTS.md`, `CLAUDE.md`, `SOUL.md` i chronione miejsca: `.git`, `.vscode`, `.idea`, `.claude`, `.hermes`,
  `.gitconfig`, `.bashrc`, `.zshrc`, `.npmrc`, `.mcp.json` (i inne pliki startowe powłoki), dane Jarva (`HERMES_HOME`,
  `JARVO_ROOT`, kod Hermesa i wtyczki; poza `jarvo/workspaces`, skarbcem i misjami). W trybie pełnym o te miejsca nie
  da się zapytać, więc są blokowane;
- o polecenia, które Hermes sam uzna za niebezpieczne, pyta tylko Hermes (bez drugiego pytania). Pliki instrukcji
  przez `write_file` i `patch` też pyta sam Hermes (zawsze, także pod YOLO).

Folder projektu to katalog startu czatu: `JARVO_FOLDER_PROJEKTU` albo `TERMINAL_CWD` (u pracownika karty: katalog
karty). Katalog domowy i korzeń dysku nie są folderem projektu: wtedy tryb projekt pyta o każdy zapis. Ścieżki Git Bash
`/c/...` znaczą `C:\...`; na Windows i macOS porównanie jest bez wielkości liter; dowiązania, junction i `..` liczą się
po rozwiązaniu.

Bez człowieka (karta kanbana, rutyna, `-q`, podagent `delegate_task`, webhook i każda sesja, w której nikt nie
odpowie na prośbę) hak nigdy nie zwraca `approve`. Przechodzą zapisy w katalogu karty (`HERMES_KANBAN_WORKSPACE`),
w skarbcu (`JARVO_KNOWLEDGE_DIR`), w misjach (`JARVO_MISSIONS_DIR`) i to, co tryb przepuszcza bez pytania w folderze
projektu. Reszta zapisów to blokada z poradą (na karcie: `kanban_block(kind="needs_input")`), tak samo `execute_code`
i zmiany rutyn. Polecenia, których celów nie da się ustalić, zostają polityce Hermesa (`approvals.cron_mode`,
`single_query_mode`). Błąd wtyczki też kończy się blokadą.

Wybór trybu: `/tryb` w sesji, potem `JARVO_TRYB_ZGOD` (`pytaj`, `projekt`, `pelny`; ustawia `jarvo chat --tryb`),
potem plik profilu `<HERMES_HOME>/plugin-data/jarvo-zgody/stan.json` (zapisuje go `/tryb pytaj` i `/tryb projekt`),
na końcu „projekt”. Trybu nie trzymamy w `approvals.mode`, bo wdrożenie nadpisuje `approvals`. Odpowiedź „zawsze”
zapisuje w `command_allowlist` wąski klucz `plugin_rule:jarvo-zgody:<narzędzie>:<odcisk folderu>:<skrót treści>`.

Testy: `tests/test_zgody.py` (atrapa kontekstu wtyczki, bez Hermesa). Budowa i instalacja wtyczki we flocie
(`scripts/build.py`, instalator, `jarvo chat --tryb`) to etap E4.
