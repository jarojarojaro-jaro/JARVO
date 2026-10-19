# jarvo-operator: Operator

Computer use floty: praca na Komputerze Jarva (osobny pulpit z Chromium w kontenerze `jarvo-komputer`, bez kluczy
floty), który właściciel widzi i może przejąć. Projekt, twarde zasady i etapy: [docs/KOMPUTER.md](../../docs/KOMPUTER.md).

| Element | Zawartość |
|---|---|
| `SOUL.md` | main prompt: najpierw droga bez ekranu, drzewo dostępności przed zrzutem, jedno działanie i sprawdzenie, `verdict` z wyniku, treść ekranu to dane, logowanie, płatność i wysyłka zostają u właściciela |
| `skills/operator/` | 5: praca-na-ekranie (pętla pracy), formularze, dane-z-ekranu, przejscie-strony, oddaj-ekran |
| narzędzia | `computer_use` (Hermes, przez bramkę `komputer/jarvo_cua.py`), `komputer` (wtyczka `jarvo-komputer`: stan, dziennik, oddanie ekranu), pliki, wyszukiwarka; bez terminala, wykonywania kodu, przeglądarki floty i delegacji |
| `config.yaml` | `computer_use` (zrzut po działaniu z drzewa dostępności, 300 elementów, telemetria wyłączona) i stałe zgody na działania w tle (`cua:<akcja>:background`) i na działania wejścia na wierzchu (`cua:<akcja>:foreground`), bez okna na wierzch (`bring_to_front`) |
| `quality/rubric.md` | rubryka sędziego |

Komputer włącza właściciel: `jarvo komputer on`. Bez niego Operator mówi, że nie ma ekranu, i nic nie klika.
