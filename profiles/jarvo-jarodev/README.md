# jarvo-jarodev: Jarodev, agent biznesowy jarodev.pl

Pierwszy agent biznesowy floty (`marka: jarodev` we `fleet.yaml`): zdobywa klientów dla jarodev.pl (strony, sklepy,
automatyzacje, aplikacje, wszystko, co da się zakodować) i wie tylko o swojej marce. Opis agentów biznesowych:
[docs/FLEET.md](../../docs/FLEET.md#agenci-biznesowi); granice i prawo: [docs/LEADY.md](../../docs/LEADY.md).

| Element | Zawartość |
|---|---|
| `SOUL.md` | main prompt: nic nie wychodzi bez „tak” właściciela, firm z Map nie kontaktuje mailem, telefonem ani SMS-em (art. 398 PKE), RODO dla osób z postów, ludzkie tempo i limity dnia, wiedza tylko z marki jarodev |
| `skills/jarodev/` | 7: lejek (+ `prawo.md`), fb-grupy, fb-posty, mapy-firmy, szybkie-wygrane, oferta-szkic (+ `oferta.md`), raport-dnia |
| skille zewnętrzne | 2: wspólny `konwersja-plikow`, wspólny `odczyt-ekranu` (tekst ze zrzutu telefonu) (`vendor/skills.lock.yaml`) |
| `scripts/` | `lejek.py` (lejek: dodaj z odsiewem duplikatów, statusy z zapisem zgody i kanału, odmowa maila, telefonu i SMS-a do firm z Map, lista, liczby, retencja RODO, limity dnia; `lejek.json` i `lejek.csv`), `poranek.py` (rutyna poranna bez modelu), `wygrane.py` (3 łatwe wygrane z `seo_check.py` Web i jednego Lighthouse), `zrodla.wzor.yaml` (wzór źródeł: grupy FB, portale, Mapy, limity) |
| `cron/jobs.yaml` | `jarodev-dzien` (pon–sob 8:40, instaluje się wstrzymana): lejek, retencja, karta dnia, wiadomość w wątku agenta |
| `quality/rubric.md` | rubryka sędziego |

**Jak zacząć** (właściciel, raz):
1. Telefon z kontem Facebook: `jarvo telefon on --phoneuse KATALOG`, potem `jarvo telefon przydziel jarvo-jarodev
   <telefon>` (agent widzi tylko ten telefon; [docs/MOBILE.md](../../docs/MOBILE.md)).
2. Mapy: `jarvo komputer on` (Komputer Jarva, ten sam ekran co Jarvo, jedna sesja steruje naraz).
3. Grupy FB, portale i miasta: wpisz w `zrodla.yaml` w katalogu roboczym agenta (`lejek.py init` zakłada wzór).
4. Rutyna: `hermes -p jarvo-jarodev cron resume jarodev-dzien` ([docs/RUNBOOK.md](../../docs/RUNBOOK.md)).

Rozmowa: w wątku Jarodev grupy Jarvo HQ albo w DM z dopiskiem „dev” (karta dla jarvo-jarodev), w aplikacji `@jarodev`.
