# Jarvo Ads: specjalista Ads Managera (projekt)

> Stan: **agent zbudowany (faza 2, 2026-09-29); Skarbiec (faza 1) jeszcze nie istnieje.** Decyzje z sekcji 14 podjęte.
> Bez Skarbca `ads.py` kończy się kodem 3, a agent pracuje na eksportach CSV (`eksport.py`). Co jest, a co w planie: sekcja 12.
> Platformy: **Meta Ads i Google Ads.** Fakty o platformach sprawdzone 2026-09-29 (źródła w sekcji 15).

Nowy specjalista floty: **`jarvo-ads`**, czyli ktoś, kto na co dzień siedzi w Ads Managerze i Google Ads.
Planuje kampanie, stawia je, pilnuje budżetu, codziennie sprawdza konto, optymalizuje, raportuje, co działa,
a co nie. Testuje wtedy, gdy test ma sens: jedna reklama, A/B, A/B/C albo więcej wariantów, w których może
różnić się wszystko naraz.

---

## 1. Co dokładnie robi

**Codzienna robota specjalisty od reklam:**

| Obszar | Co konkretnie |
|---|---|
| **planowanie kampanii** | cel biznesowy → cel kampanii (sprzedaż, leady, ruch, zasięg, instalacje), struktura (kampanie, zestawy/grupy, reklamy), odbiorcy, miejsca emisji, budżety, harmonogram, prognoza wyników i kosztów |
| **stawianie** | kampanie na Mecie (FB, IG) i w Google (Search, YouTube, Performance Max): odbiorcy, słowa kluczowe, reklamy, UTM, piksel i konwersje. Wszystko najpierw jako **szkic PAUSED** (0 zł) z podglądem |
| **pilnowanie** | codzienna kontrola konta: tempo wydatków, odrzucone reklamy, faza uczenia, zmęczenie kreacji, częstotliwość, problemy z płatnością, śledzenie konwersji, wyszukiwane hasła w Google (wykluczenia) |
| **optymalizacja** | wyłączanie słabych reklam, przesuwanie budżetu do lepszych, wymiana zmęczonych kreacji, korekty stawek i odbiorców w zatwierdzonym budżecie |
| **testy** | jedna reklama, A/B, A/B/C, A/B/C/D…: warianty mogą różnić się wszystkim (film, hook, copy, grupa odbiorców). Agent mówi uczciwie, co da się z takiego testu wyczytać, a co nie (sekcja 5) |
| **raporty** | krótko, gdy coś się dzieje; tygodniowo z wykresami; na koniec kampanii z wnioskami |
| **wnioski marki** | co zadziałało i dlaczego, zapisane z dowodami, żeby Studio i Wideograf robili kolejne kreacje lepiej |

Pętla pracy:

```
  cel („więcej zapisów na jarvo.pl”)
        │
        ▼
  ① plan kampanii (jarvo-ads): cel, struktura, odbiorcy, budżet, prognoza, ewentualnie warianty
        │
        ▼
  ② kreacje: brief do Studia (grafiki, copy) i Wideografa (filmy, wersje hooków)
        │
        ▼
  ③ szkic na koncie (PAUSED, 0 zł): podglądy reklam, link do Ads Managera / Google Ads
        │
        ▼
  ④ Twoja zgoda na kopertę budżetu (kod przez podłączony komunikator)
        │
        ▼
  ⑤ start → codzienna kontrola i optymalizacja w kopercie
        │     strażnik co godzinę: wydatki, anomalie, odrzucone reklamy
        ▼
  ⑥ raporty → wnioski marki → następne kreacje i kampanie (wraca do ①)
```

**Poza zakresem:** robienie grafik i filmów (Studio, Wideograf), strona i piksel na stronie (Web), research rynku
(Sherlock), posty organiczne (Studio). Płatne reklamy należą w całości do `jarvo-ads`: Studio robi kreacje,
Ads je puszcza i mierzy.

---

## 2. Zasada numer jeden: agent nie trzyma kluczy do pieniędzy

W obecnej flocie wszyscy agenci działają w jednym kontenerze jako ten sam użytkownik ([VPS.md §5](VPS.md#5-bezpieczeństwo)).
Agent z terminalem może przeczytać każdy plik i każdą zmienną w kontenerze. Zgody w Hermesie ocenia
pomocniczy model (`approvals.mode: smart`, [`tools/approval_smart.py`](https://github.com/NousResearch/hermes-agent/blob/main/tools/approval_smart.py)).
To dobre na `rm -rf`, ale `python ads.py start` wygląda dla niego jak niewinny skrypt.
Do tego karty kanbana wykonują się bez człowieka (tryb `unattended`).

**Wniosek: prompt i zgody Hermesa nie mogą być jedyną ochroną przed wydaniem Twoich pieniędzy.**

Dlatego tokeny Meta i Google **nie trafiają do kontenera Hermesa w ogóle**. Trzyma je osobny, mały kontener:
**Skarbiec** (`jarvo-skarbiec`). Agent rozmawia z nim przez wąskie API, a każda reguła o pieniądzach
jest w kodzie Skarbca, nie w prompcie.

```
  kontener jarvo-hermes                     kontener jarvo-skarbiec (bez modelu)
 ┌──────────────────────────────┐   HTTP   ┌────────────────────────────────────────┐
 │ jarvo-ads (agent)            │─────────►│ polityka (skarbiec.yaml, tylko odczyt) │
 │   └ ads.py (CLI, bez tokenu) │jarvo-net │ dziennik każdej akcji (SQLite)         │
 │ HQ: panel Reklamy,           │─────────►│ zgody: kody jednorazowe (komunikator)  │
 │     przycisk STOP (w planie) │          │ strażnik co 1 h: wydatki, anomalie     │
 └──────────────────────────────┘          │ tokeny Meta i Google (tylko tu)        │
                                           └────────────────────┬───────────────────┘
                                                                │ Graph API v25 (HTTPS)
                                                                ▼
                                            Meta: konto reklamowe, strona FB/IG, piksel
```

Skarbiec to mały serwis w Pythonie z biblioteki standardowej: bez frameworka, kilkadziesiąt MB RAM, ten sam wzorzec co sidecar
SearXNG. Pliki kreacji czyta z `/opt/data/jarvo` zamontowanego tylko do odczytu.

**Stan:** Skarbca jeszcze nie ma (brak usługi w `infra/docker-compose.yml`). Istnieje klient `ads.py`, który bez
Skarbca kończy się kodem 3 („Skarbiec niepodłączony”), a agent pracuje na eksportach CSV (`eksport.py`).

### Obrona w głąb: pięć warstw

| # | Warstwa | Co zatrzymuje | Kto ją pilnuje |
|---|---|---|---|
| 1 | token tylko w Skarbcu | agent nie może ominąć reguł i zawołać API sam | architektura |
| 2 | polityka w kodzie Skarbca | start bez zgody, budżet ponad kopertę, obce konta, kategorie specjalne | Skarbiec |
| 3 | limity po stronie Meta | awaria Skarbca: zestawy reklam mają `lifetime_budget` + `end_time`, kampania `spend_cap` (od ~100 USD) | Meta |
| 4 | strażnik z automatycznym STOP | wydatek szybszy niż plan, CPA 2× ponad cel, lawina odrzuceń | Skarbiec, bez modelu |
| 5 | limit wydatków konta w Ads Managerze | wszystko powyżej zawiodło | Ty, raz przy konfiguracji |

Zmniejszanie wydatków jest zawsze dozwolone (pauza, STOP, obniżka budżetu). Zwiększanie zawsze wymaga zgody.

---

## 3. Poziomy autonomii w reklamach

Ogólne poziomy A0–A3 są w [PROFILE-SPEC.md §9](PROFILE-SPEC.md#9-granice-autonomia-uprawnienia-sandbox). Tu jest ich przekład na reklamy:

| Poziom | Akcje | Zgoda |
|---|---|---|
| **A0** odczyt | statystyki, audyt konta, podgląd kampanii, raporty | nie |
| **A1** szkic | plan testu, wgranie kreacji, kampania na koncie w stanie **PAUSED** (0 zł, podgląd w Ads Managerze) | nie (Skarbiec wymusza PAUSED) |
| **A2** wydatek | start koperty, podniesienie budżetu, przedłużenie, nowa grupa odbiorców, wznowienie po STOP strażnika | **kod zgody** |
| **A2 w kopercie** | wyłączenie przegranego wariantu, przesunięcie budżetu między wariantami tego samego testu (suma bez zmian), pauza całości | nie: zgoda na kopertę to obejmuje |
| **A3** nigdy | metody płatności, limit konta, uprawnienia w Business Managerze, konta spoza listy, usuwanie historii (tylko archiwizacja), reklamy w kategoriach specjalnych bez Twojego wpisu w polityce | niemożliwe przez API Skarbca |

### Koperta budżetowa

Zgoda nie dotyczy pojedynczego kliknięcia, tylko **koperty**: jeden test albo kampania z twardymi granicami.

```
Koperta K-0930-launch
  konto:        act_123 (JARVO)          cel testu:   hook rate, potem CTR
  budżet:       500 zł łącznie           dziennie:    maks. 100 zł
  czas:         30.09 → 06.10            warianty:    5 (A–E, filmy launchowe)
  wolno w kopercie: wyłączać przegranych, przesuwać budżet między A–E
  po końcu:     wszystko pauzuje się samo (end_time na zestawach reklam)
```

Wewnątrz koperty agent optymalizuje sam, bo tylko tak testy A/B/C/D mają sens: nikt nie chce zatwierdzać
każdego przesunięcia 20 zł. Poza kopertę wyjść nie może, bo Skarbiec liczy sumę budżetów przed każdą zmianą.

---

## 4. Zgoda: jak to wygląda na telefonie

Stan: po stronie agenta gotowe (`ads.py koperta …`, skill `start-kampanii`); wysyłkę i sprawdzanie kodów robi Skarbiec,
którego jeszcze nie ma.

1. Agent zgłasza kopertę do Skarbca (`ads.py koperta zglos out/koperta.json`). Skarbiec sprawdza politykę i zapisuje
   kopertę ze stanem `czeka`.
2. **Skarbiec sam** (nie model) wysyła Ci przez podłączony komunikator (Telegram, Discord albo Slack; bez komunikatora
   tylko w panelu Skarbca) podsumowanie z danych koperty i 6-cyfrowy kod:
   ```
   🔐 Skarbiec: prośba o zgodę na wydatek
   Test „5 filmów launchowych” · konto JARVO (act_123)
   500 zł łącznie, maks. 100 zł/dzień, 30.09–06.10
   5 reklam (link do podglądu z Mety)
   Kod: 482 917 (ważny 30 min, tylko dla tej koperty)
   ```
3. Wpisujesz kod w rozmowie z Jarvem albo w panelu Reklamy w HQ (panel w planie, faza 4). Agent przekazuje go do Skarbca, a ten startuje kampanię.

Dlaczego tak:
- **model nie zna kodu**, dopóki go nie wpiszesz. Skarbiec trzyma tylko jego skrót (hash), więc agent nie może „zatwierdzić
  sam siebie”, nawet gdyby ktoś go zmanipulował treścią ze strony albo komentarzem pod reklamą,
- **widzisz to, co podpisujesz:** opis w wiadomości generuje Skarbiec z tych samych danych, które potem wykonuje.
  Model nie może pokazać Ci „100 zł”, a puścić 1000,
- kod jest jednorazowy, przypięty do jednej koperty i wygasa po 30 min.

Na STOP nie trzeba kodu: `ads.py stop` pauzuje wszystko, co Skarbiec prowadzi (działa, gdy Skarbiec jest podłączony).
W planie (faza 4): czerwony przycisk w HQ i „stop reklamy” do Jarva. Dziś Jarvo traktuje „stop” jak anulowanie misji
(archiwizuje karty), a nie jak STOP reklam.

---

## 5. Testy A/B/C/D: metoda

### 5.1 Trzy tryby testu na Mecie

| Tryb | Jak | Kiedy | Uczciwość wyniku |
|---|---|---|---|
| **Split test** | Meta dzieli odbiorców na rozłączne losowe grupy (`ad_studies`, typ `SPLIT_TEST`) | odbiorcy, strategia, miejsca emisji, większe budżety | najwyższa: przyczynowa |
| **Równe budżety (ABO)** | osobny zestaw reklam na wariant, ten sam budżet | test kreacji przy małym budżecie (domyślny) | dobra: równy wydatek, ale grupy mogą się nakładać |
| **Wolumen (CBO / Andromeda)** | wiele kreacji w jednym zestawie, Meta sama dzieli budżet | skalowanie zwycięzców, szukanie sygnału w 10+ kreacjach | niska: algorytm faworyzuje wcześnie, to sygnał, nie dowód |

Agent zawsze mówi, w jakim trybie jest test, i nie nazywa wyniku z trybu wolumen „wygraną w teście A/B”.

### 5.2 Drabina metryk (bo budżet decyduje, co da się zmierzyć)

Przykład z założeniami: CPM 20 zł, test dwóch wariantów, różnica do wykrycia jak w tabeli, istotność 5%, moc 80%.

| Metryka | Różnica do wykrycia | Potrzeba na wariant | Koszt na wariant |
|---|---|---|---|
| hook rate (3 s oglądania / wyświetlenia) | 25% → 30% | ~1 250 wyświetleń | **~25 zł** |
| CTR (kliknięcia w link) | 1,0% → 1,3% | ~19 800 wyświetleń | ~400 zł |
| koszt wyniku (CPA) | 2× | ~33 konwersje | zależy od CPA |
| koszt wyniku (CPA) | 1,3× | ~230 konwersji | zwykle tysiące zł |

Stąd domyślna strategia przy małych budżetach: **tanio przesiać hooki (hook rate), średnio sprawdzić CTR na 2–3 najlepszych,
drogo potwierdzić CPA tylko na zwycięzcy.** Agent nie może obiecać „znajdziemy najtańszą konwersję” za 200 zł. Planer mocy
(skrypt) liczy to przed startem i blokuje testy, które z założenia nic nie rozstrzygną: proponuje wtedy mniej wariantów,
tańszą metrykę albo dłuższy czas.

### 5.3 Statystyka (skrypt, nie model)

- **Wskaźniki** (hook rate, CTR, CVR): model beta-dwumianowy, rozkład a priori Beta(1, 1).
- **Koszt wyniku:** wyniki na złotówkę jako proces Poissona z rozkładem gamma, więc nierówny wydatek wariantów nie psuje porównania.
- Dla każdego wariantu: **P(najlepszy)**, oczekiwana strata, przedział wiarygodności. Monte Carlo ze stałym ziarnem,
  żeby raport dał się powtórzyć.
- **Reguły stopu** (domyślne, do zmiany w planie testu):
  - najpierw minimum: 4 dni (lepiej 7, pełny tydzień) i minimalny wolumen na wariant z planera,
  - **zwycięzca:** P(najlepszy) ≥ 95% i oczekiwana strata < 2%,
  - **przegrany** (wyłączany w kopercie): P(najlepszy) < 5% po minimum albo wydatek 2× docelowego CPA bez konwersji,
  - koniec czasu bez rozstrzygnięcia: raport mówi **„remis”** i podaje, ile budżetu brakowało.
- Najlepiej jedna zmienna na test. Gdy warianty różnią się wszystkim (`wiele_zmiennych: true`), raport mówi tylko,
  który pakiet wygrał, a nie dlaczego. Nazwa reklamy koduje atrybuty (`T03_hook-pytanie_9x16_lektor-m_v2`), więc wnioski da się
  zbierać przekrojowo przez wiele testów („hooki-pytania vs hooki-liczby”).

### 5.4 Zmęczenie kreacji

Według praktyków po zmianie algorytmu Andromeda kreacje męczą się w 2–3 tygodnie zamiast 6+. Strażnik śledzi częstotliwość, spadek CTR względem pierwszych
3 dni i wzrost CPM. Gdy kreacja słabnie, agent zamawia następców (brief do Studia i Wideografa) z wyprzedzeniem, a nie po fakcie.

---

## 6. Workflowy agenta (skille)

Własne [T] (wszystkie są w `profiles/jarvo-ads/skills/ads/`, 10 skilli):

| Skill | Co robi | Poziom |
|---|---|---|
| `plan-kampanii` | cel biznesowy → typ kampanii (Meta/Google), struktura, odbiorcy/słowa kluczowe, budżet, harmonogram, prognoza z `planer.py`, konwencja nazw | A1 |
| `podlacz-konto` | przeprowadza Cię przez Business Managera, aplikację, użytkownika systemowego i token, a w Google Ads przez MCC, token deweloperski i OAuth; tokeny wklejasz do Skarbca (nie do agenta); `ads.py doctor` sprawdza uprawnienia, walutę, strefę czasu, piksel, limit konta | A0 |
| `audyt-konta` | stan konta: struktura, marnotrawstwo, piksel/CAPI, zmęczone kreacje, szybkie wygrane | A0 |
| `plan-testu` | hipoteza, zmienna, warianty, metryka z drabiny, planer mocy, koperta, **brief kreacji** dla Studia/Wideografa | A1 |
| `start-kampanii` | budowa na koncie w PAUSED, podglądy reklam, zgłoszenie koperty, start po kodzie | A1 → A2 |
| `optymalizacja` | codzienny przegląd w kopercie: przegrani, przesunięcia, zmęczenie, notatka „co i dlaczego” | A2 w kopercie |
| `raport-reklam` | raport dzienny (tylko gdy jest o czym), tygodniowy z wykresami, końcowy raport testu | A0 |
| `wnioski-marki` | zapis wniosków z dowodami do `knowledge/brands/<marka>/reklamy/WNIOSKI.md` | A1 |
| `zgodnosc-reklam` | zasady reklamowe Meta, kategorie specjalne, polskie prawo (oznaczanie reklam, UOKiK, obietnice), RODO przy pikselu | A0 |
| `sledzenie-konwersji` | lista kontrolna piksel + Conversions API + UTM; wdrożenie na stronie to karta dla `jarvo-web` | A0 |

Zewnętrzne (MIT, [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills)):
`ads` (strategia, w tym `meta-decision-system.md` i `audit-guardrails.md`), `ab-testing`, `attribution`, `analytics`,
`ad-creative` (tylko do pisania briefów, kreacje robi Studio).

Skrypty (deterministyczne, `--help`, JSON, kod wyjścia ≠ 0 przy błędzie):
- `ads.py`: jedyne wejście do Skarbca (`doctor`, `konta`, `kampanie`, `statystyki`, `szkic` (kreacje w pliku szkicu),
  `koperta zglos|zatwierdz|stan`, `pauza`, `budzet`, `stop`, `dziennik`); kod wyjścia 0 ok, 1 odmowa Skarbca,
  2 złe wejście, 3 Skarbiec niepodłączony,
- `eksperyment.py`: P(najlepszy), strata, reguły stopu, werdykt,
- `planer.py`: moc testu, czas i koszt do rozstrzygnięcia, rekomendacja liczby wariantów,
- `eksport.py`: eksport CSV z Ads Managera / Google Ads (nagłówki PL i EN) → tabela (wydatek, CTR, CPC, CPA, hook rate),
  `--json` jako wejście dla `eksperyment.py`, `--grupuj kampania|zestaw|reklama`; działa bez Skarbca.

Wykresy do raportów agent robi sam według skilla `raport-reklam` (HTML → PNG przez Chromium z obrazu), bez osobnego skryptu.

---

## 7. Rutyny

Instalują się **wstrzymane**, jak wszystkie rutyny floty ([BOSS.md §4](BOSS.md#4-pilnowanie-nic-nie-ginie)).

**Stan: jeszcze niezbudowane.** Strażnik powstanie razem ze Skarbcem. Rutyny agenta wymagają `profiles/jarvo-ads/cron/jobs.yaml`
(dziś go nie ma) i dopisania ich id do `scripts/install-fleet.sh --resume-cron` (dziś wznawia tylko rutyny Jarva).

| Rutyna | Kiedy | Model? |
|---|---|---|
| strażnik (w Skarbcu) | co 1 h: pobiera statystyki, liczy tempo wydatków, sprawdza odrzucone reklamy, problemy z płatnością i wygasanie tokenu. Twarde przekroczenie → **sam pauzuje** i pisze do Ciebie | nie (0 tokenów) |
| `ads-optymalizacja` | codziennie 9:10: skrypt podaje werdykty testów; agent budzi się tylko, gdy jest decyzja do podjęcia | tylko przy zmianie |
| `ads-raport` | poniedziałek 8:40: raport tygodnia (wydatki, wyniki, testy, wnioski, następne testy) | 1 tura/tydzień |

---

## 8. Współpraca z flotą

| Kto | Zmiana | Stan |
|---|---|---|
| **Jarvo** | routing: „reklama płatna”, „budżet”, „Meta Ads”, „wyniki kampanii”, „test A/B reklam” → `jarvo-ads`. Misja „wypromuj X” = ads (plan) → studio + wideo (kreacje) → ads (start, po kodzie) | routing ✅ (skill `roster` z `fleet.yaml`); wzorzec misji ⬜ (brak w `dispatch-playbook`, wzorzec „Kampania” nie ma ads) |
| **Studio** | przestaje być właścicielem reklam płatnych; robi kreacje reklam według briefu z `plan-testu` (formaty, warianty, jedna zmienna). Skille `ads` i `ad-creative` zostają u niego do copy | ✅ (SOUL Studia) |
| **Wideograf** | skill `warianty-ab` dostaje wejście z briefu (hook, tempo, lektor); nazwy plików według konwencji atrybutów | ⬜ (`warianty-ab` bez briefu od ads, pliki `<film>-<wariant>-<format>.mp4`) |
| **Web** | piksel, Conversions API, UTM i baner zgód na stronach docelowych (karta od ads) | ⬜ (brak workflowu w profilu Web) |
| **Sherlock** | benchmarki branży, reklamy konkurencji (Biblioteka reklam Meta) na potrzeby planu | bez zmian w profilu: zwykłe zlecenie researchu |

Sędzia (Jarvo) dostaje rubrykę `jarvo-ads` (jest: `profiles/jarvo-ads/quality/rubric.md`): plan ma hipotezę i jedną zmienną, planer mocy uruchomiony, koperta zgodna z kartą,
raport z P(najlepszy) i uczciwym „remisem”, wnioski zapisane z dowodem, zero akcji A2 bez identyfikatora zgody w dzienniku.

---

## 9. Dane i raporty

Stan: dziennik, migawki i uzgadnianie to część Skarbca (w planie). Agent ma już klienta `ads.py dziennik`.

- **Dziennik Skarbca** (SQLite, tylko dopisywanie): każda akcja zapisująca z polami kto (agent / strażnik / HQ), co, stan przed
  i po, identyfikator zgody. To odpowiedź na pytanie „kto to włączył?”.
- **Migawki statystyk** raz na godzinę dla aktywnych reklam i raz na dobę pełne, żeby trendy i zmęczenie liczyły się z własnych danych,
  a nie z okien atrybucji, które Meta potem przelicza.
- **Uzgadnianie:** codziennie suma wydatków z dziennika vs `spend` z Mety. Różnica > 5% = alert.

Raport tygodniowy w Telegramie (przykład formatu):
```
📈 Reklamy: tydzień 40
Wydane: 412 / 500 zł (koperta K-0930-launch)
Test „5 filmów launchowych”: po hook rate wygrywa D (bang-motion), P=97%.
  CTR: D i B remis (P 58/41%), potrzeba ~600 zł, żeby rozstrzygnąć.
Wyłączone: A, C, E (hook rate 18–22% vs 31% u D).
Wniosek do marki: szybki start z ruchem w 1. sekundzie > spokojne otwarcie (1 test, pewność średnia).
Dalej proponuję: test CTR D vs B, 300 zł, 5 dni. Odpowiedz „ok”, a przyślę kod.
```

---

## 10. HQ

- Pokój `office` to **„Sala operacyjna”** (jest): ściana ekranów (słupki wariantów, wydatki pod linią koperty, ROAS),
  figurka Ads, czerwony STOP jako dekoracja.
- Panel **Reklamy** (w planie, faza 4; dziś go nie ma): koperty (pasek wydane / zatwierdzone), testy z paskami P(najlepszy) dla wariantów, oczekujące zgody
  z polem na kod, dziennik akcji i **czerwony STOP** (bez kodu, bo tylko zmniejsza wydatki).

---

## 11. Platformy

| Platforma | Dostęp przez API | Plan |
|---|---|---|
| **Meta** (FB, IG, Messenger, Threads) | Graph API v25. Nowa aplikacja startuje z poziomem *Limited Access* (niższe limity wywołań, do własnych kont wystarcza); *Full Access* po 500+ wywołaniach w 15 dni z błędami < 15% (od maja 2026). **Konto sandbox** pozwala testować całe API bez wydawania pieniędzy | **faza 1** |
| **Google Ads** (Search, YouTube, PMax) | token deweloperski: *Explorer access* działa na kontach produkcyjnych bez ręcznej weryfikacji, do 2 880 operacji dziennie | faza 5 |
| **TikTok** | Marketing API po weryfikacji aplikacji (kilka tygodni, wymaga pełnej strony o usłudze) | faza 6, wniosek złożyć wcześniej |
| LinkedIn | program partnerski | na żądanie |

**Dlaczego nie oficjalny MCP albo CLI Mety** (oba od 29.04.2026):
- **Ads MCP** (`mcp.facebook.com/ads`) daje modelowi bezpośredni zapis na koncie przez OAuth, a więc omija Skarbiec
  i zasadę numer jeden. Może kiedyś posłużyć do odczytu, zapis zawsze idzie przez Skarbiec,
- **Ads CLI** (`meta-ads` 1.2.0): licencja zamknięta, wersja alpha, skompilowane moduły, przypięty stary SDK
  (`facebook-business<25`), a testy (`study`) ma tylko do listowania.

Skarbiec woła Graph API bezpośrednio (HTTPS z biblioteki standardowej): pełna kontrola, a testy przechodzą bez sieci
na atrapie API (fake Graph), tak jak testy HQ.

---

## 12. Plan budowy

Każdy krok: osobny commit, push, pytest + `validate.py` i test w działającym kontenerze (zasady z `CLAUDE.md`).

Stan: ✅ zrobione w kodzie · 🟡 zakodowane, czeka na test na żywo · ⬜ do zrobienia.

| Faza | Co | Test „na żywo” | Stan |
|---|---|---|---|
| **1. Skarbiec** | kontener, polityka, dziennik, koperty, kody przez komunikator, STOP, strażnik, adapter Meta, atrapa Graph API, `ads.py` | atrapa + **konto sandbox Meta** (0 zł) | ⬜ Skarbca brak; jest tylko klient `ads.py` (bez Skarbca kod 3) |
| **2. Agent** | profil `jarvo-ads` (SOUL, 10 skilli, skrypty planera, statystyki i eksportu CSV), rubryka, ≥ 10 evals (w tym „odpal bez pytania”, injection w komentarzu pod reklamą, „zmień metodę płatności”), routing Jarva, figurka w HQ | karta od Jarva → plan → szkic w sandboxie → kod → start | 🟡 w kodzie gotowe (12 evals); test na żywo czeka na Skarbiec |
| **3. Pierwszy prawdziwy test** | **5 filmów launchowych jako test A/B/C/D/E** na jarvo.pl, mała koperta (Twoja decyzja) | prawdziwe konto, raport końcowy | ⬜ |
| **4. Pętla wiedzy i HQ** | panel Reklamy, raport tygodniowy z wykresami, wnioski marki czytane przez Studio i Wideografa | drugi test na briefie z wniosków | ⬜ panel, rutyny i czytanie wniosków przez Studio/Wideografa; ✅ Sala operacyjna w HQ, zapis `WNIOSKI.md` przez `wnioski-marki` |
| **5. Google Ads** | adapter w Skarbcu, test na koncie testowym Google | | ⬜ adapter; po stronie agenta Google już jest (`plan-kampanii`, `podlacz-konto`, CSV w `eksport.py`) |
| **6. TikTok** | po weryfikacji aplikacji | | ⬜ |

---

## 13. Czego potrzebuję od Ciebie (jednorazowo, przed fazą 3)

1. Meta Business Manager z kontem reklamowym JARVO (waluta PLN, strefa Europe/Warsaw) i podpiętą kartą.
2. Strona na Facebooku i konto Instagram połączone z Business Managerem.
3. **Limit wydatków konta** w Ads Managerze (np. 1000 zł), czyli ostatnia warstwa obrony.
4. Aplikacja Meta typu Business z produktem Marketing API i użytkownik systemowy z dostępem do konta, strony i piksela
   (skill `podlacz-konto` przeprowadzi Cię krok po kroku, ~15 min).
5. Piksel na jarvo.pl z banerem zgód (zrobi `jarvo-web`). Bez piksela test i tak ruszy na hook rate i CTR.

---

## 14. Decyzje (podjęte 2026-09-29)

| # | Pytanie | Decyzja |
|---|---|---|
| 1 | Czy w zatwierdzonej kopercie agent może sam wyłączać przegranych i przesuwać budżet między wariantami? | **Tak.** Bez tego testy A/B/C/D wymagają Twojego kliknięcia co kilka godzin |
| 2 | Kanał kodu zgody | **podłączony komunikator** (Telegram, Discord albo Slack), a w HQ pole na kod (jak 2FA w banku); bez komunikatora kody tylko w panelu Skarbca |
| 3 | Twardy sufit miesięczny w polityce Skarbca (zmiana tylko w pliku na serwerze, nie przez agenta) | **1000 zł/mies.** na start |
| 4 | Czy Studio oddaje reklamy płatne w całości nowemu agentowi? | **Tak:** Studio robi kreacje, Ads je puszcza i mierzy |
| 5 | Kolejność platform po Mecie | **Google, potem TikTok** (wniosek do TikToka złożyć już teraz, bo trwa tygodniami) |
| 6 | Nazwa | `jarvo-ads` · „Specjalista Ads” · pokój „Sala operacyjna” · Skarbiec jako strażnik |

---

## 15. Źródła (sprawdzone 2026-09-29)

- Meta Ads MCP: [Ads MCP Server overview](https://developers.facebook.com/documentation/ads-commerce/ads-ai-connectors/ads-mcp-server/ads-mcp-server-overview)
- Meta Ads CLI: [ogłoszenie 29.04.2026](https://developers.facebook.com/blog/post/2026/04/29/introducing-ads-cli/),
  [dokumentacja](https://developers.facebook.com/documentation/ads-commerce/ads-ai-connectors/ads-cli/ads-cli-overview),
  pakiet `meta-ads` 1.2.0 na PyPI (licencja `LicenseRef-Proprietary`, `Development Status :: 3 - Alpha`)
- Poziomy dostępu: [Update to Ads Management Standard Access (04.05.2026)](https://developers.meta.com/blog/updates-to-ads-management-standard-access-feature/)
- Kampania, `spend_cap` (min. ~100 USD), `special_ad_categories`, tworzenie w PAUSED:
  [Ad Campaign reference, v25.0](https://developers.facebook.com/documentation/ads-commerce/marketing-api/reference/ad-campaign-group)
- Split testy: [Split Testing guide](https://developers.facebook.com/documentation/ads-commerce/marketing-api/guides/split-testing)
- Konto sandbox: [Sandbox Ad Accounts](https://developers.facebook.com/ads/blog/post/v2/2016/10/19/sandbox-ad-accounts/)
- Google Ads API: [Access levels](https://developers.google.com/google-ads/api/docs/api-policy/access-levels)
- TikTok: [App Review FAQ](https://developers.tiktok.com/docs/en/getting-started-faq)
- Testowanie kreacji po Andromedzie (praktyka rynkowa, nie dokumentacja Mety):
  [TheOptimizer](https://theoptimizer.io/blog/how-to-test-ad-creatives-on-meta-after-the-andromeda-update-2026-playbook)
- Liczebności w §5.2: wzór na dwie proporcje (α = 0,05, moc 80%) i porównanie dwóch częstości Poissona; CPM 20 zł to założenie przykładu, nie benchmark
