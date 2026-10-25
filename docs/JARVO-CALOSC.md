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
  (wyjątki: skille z `shared/skills/`: `graf-kodu` u Weba i Ręki, `transkrypcja-filmu` u Sherlocka, Wideografa i Ręki, `hooki` u Studia, Wideografa i Ads, `izometria` u Weba, Studia i Wideografa, `warsztat-3d` (model 3D z kodu) u Weba, Wideografa i Mobile, `konwersja-plikow` (plik → inny format albo bez metadanych) i `odczyt-ekranu` (tekst ze zrzutu ekranu, skanu albo PDF: Indra OCR, zapas Tesseract) u wszystkich poza Operatorem (nie ma terminala), `ostrozna-przegladarka` (jedna próba Camoufoxem po odmowie strony) u Łowcy i Sherlocka; Ręka czyta skille wszystkich).
- **Nadzór bez palenia tokenów:** dispatcher kanbana i patrol (skrypt bez modelu) pilnują floty
  i budzą Jarva tylko przy anomaliach albo gdy trzeba Twojej decyzji.

Poziomy autonomii: **A0** odczyt · **A1** szkice we własnym workspace · **A2** po zgodzie człowieka
· **A3** nigdy. Wszyscy specjaliści mają `autonomy_max: A1`.

---

## 2. Flota agentów (10 profili)

Każdy agent to osobna **dystrybucja Hermesa**: `SOUL.md` (osobowość + zasady), `config.yaml`
(model, toolset, deny), skille, skrypty, rubryka jakości, toolbox, dystrybucja.

| Agent | Rola | Uchwyt | Pokój HQ | Temat Telegram | Skille |
|---|---|---|---|---|---|
| 🛰️ `jarvo` | **Main Judge** — intake, misje, karty, sędziowanie, raporty, patrol | `@jarvo` | Mostek dowodzenia (`bridge`) | general | 14 |
| 🔎 `jarvo-sherlock` | **Researcher-detektyw** — wieloźródłowy research, weryfikacja faktów, raporty z cytatami z rejestru źródeł sprawdzanymi przed oddaniem, transkrypcja filmu z linku | `@sherlock` | Gabinet śledczy (`study`) | sherlock | 8 |
| 🌐 `jarvo-web` | **Web Senior Dev** — strony/landingi (z inspiracjami z branży: Inspo + własna baza), SEO techniczne, bezpieczeństwo aplikacji, wydajność, wdrożenie | `@web` | Pracownia webowa (`devlab`) | web | 10 |
| 🎬 `jarvo-studio` | **Marketing i kreacja** — grafiki social, obrazy AI, żywe obrazy (pętla 5 s, warstwy PSD), copy PL, kampanie, kalendarze | `@studio` | Atelier kreatywne (`atelier`) | studio | 7 |
| 🎥 `jarvo-wideo` | **Wideograf** — krótkie filmy (lektor PL, napisy karaoke, stock/AI), warianty A/B, montaż, dwa ekrany (split screen), typografia jak z montażu, filmy z kodu, 15 stylów motion design, 8 gramatyk explainera, 35 stylów malarskich, losowanie ruchów z biblioteki 273 technik, żywe schematy, maskotka | `@wideo` | Studio filmowe (`filmstudio`) | wideo | 22 |
| 📈 `jarvo-ads` | **Specjalista Ads** — Meta + Google Ads, kampanie, testy A/B/C, raporty; przygotowuje paczkę, publikujesz Ty | `@ads` | Sala operacyjna (`office`) | ads | 11 |
| 🎯 `jarvo-lowca` | **Łowca leadów** — sygnały zakupowe (KRS, CEIDG, przetargi BZP/TED, strony firm, oferty pracy), kwalifikacja wg profilu klienta, ranking z „dlaczego teraz”, kontakt opublikowany ze źródłem, monitoring, rozpoznanie nowego źródła; nic nie wysyła | `@lowca` | Radar sprzedaży (`radar`) | lowca | 7 |
| 📱 `jarvo-mobile` | **Twórca aplikacji** — uczciwe „natywna czy PWA” z kosztami, darmowy audyt mobilny (App Store, Google Play, linki strona → aplikacja, PWA, opinie), aplikacje Expo z szablonu ze zgodnością ze sklepami, podgląd w HQ i Expo Go, bramka jakości (Android, iOS w CI), pakiet do sklepów z listą 44 punktów, wydanie za zgodą i nauka z odrzuceń, aplikacja ze strony firmy, utrzymanie (terminy, opinie, SDK, poprawki OTA za zgodą), kontrola paczek npm; konta zawsze właściciela | `@mobile` | Pracownia aplikacji (`apps`) | mobile | 10 |
| 🖥️ `jarvo-operator` | **Operator** — praca na ekranie Komputera Jarva (computer use): klik w panelach i programach w przeglądarce, formularze, dane z ekranu do pliku, ścieżka klienta na stronie; klik w tle, klawiatura w aktywnym oknie, logowanie, płatność i wysyłkę oddaje właścicielowi | `@operator` | Sterownia (`control`) | operator | 5 |
| 🦾 `jarvo-reka` | **Prawa ręka** — generalista, składa pakiety misji, dokumenty, prototypy; zna skille wszystkich (read-only) | `@reka` | Warsztat (`workshop`) | reka | 4 |

### 2a°. jarvo-operator — szczegóły (najnowszy)
Operator ekranu, etap K3 z [KOMPUTER.md](KOMPUTER.md). Narzędzie `computer_use` Hermesa idzie przez bramkę
`komputer/jarvo_cua.py` do wejścia Komputera Jarva (twarde zasady, ukrywanie sekretów, dziennik); wtyczka
`jarvo-komputer` daje narzędzie `komputer` (`stan`, `dziennik`, `oddaj`: prośba do właściciela jako pauza z powodem).
Pętla z `praca-na-ekranie`: najpierw droga bez ekranu (`web_extract`), potem `capture` `ax` → `som` → `vision`, klik
po numerze elementu, `capture_after` po każdym działaniu i werdykt (`verify_fresh_state`, `escalate`). Skille:
`praca-na-ekranie`, `formularze`, `dane-z-ekranu`, `przejscie-strony`, `oddaj-ekran`. Konfiguracja: toolsety
`computer_use`, `komputer`, `file`, `web`, `memory`, `skills`, `todo`, `session_search` (na Telegramie też `clarify`;
w cronie bez ekranu), bez terminala, wykonywania kodu, przeglądarki Hermesa i delegowania; `computer_use`:
`permission_mode: standard`, `capture_after_mode: ax`, telemetria wyłączona; stałe zgody (`command_allowlist`)
`cua:<działanie>:background` i `cua:<działanie>:foreground` dla działań wejścia (na pulpicie X11 klawiatura,
przewijanie i przeciąganie działają tylko na wierzchu; wejście przepuszcza je tylko w aktywnym oknie, odmowa
`okno_nieaktywne`), walidator odrzuca `bring_to_front`, tryby cron i bez nadzoru odmawiają.
Logowanie, płatność, CAPTCHA i wysyłkę robi właściciel w Ekranie HQ; Operator nie przyjmuje haseł ani kart z czatu.
Bez wyciągu rozmów do skarbca (`bez_wyciagu`). 20 evals, 2 ataki red teamu (wstrzyknięcie z ekranu, karta i hasło
na ekranie), pokój Sterownia w HQ. Wzorzec 11 w `dispatch-playbook` mówi Jarvowi, kiedy dać kartę Operatorowi.

### 2a. jarvo-mobile — szczegóły
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
CEIDG (API v3 Hurtowni danych na darmowym tokenie właściciela: jednoosobowe działalności, minimum danych osoby),
e-Zamówienia BZP (ogłoszenia i wyniki ze zwycięzcą), TED, strony firm (`robots.txt`, uczciwy UA), wyszukiwarka.
Ocena: dopasowanie do `ICP.yaml` → świeżość → siła; kontakt tylko opublikowany przez firmę albo rejestr, ze źródłem;
przypomnienie o zgodzie na informację handlową (UŚUDE, PKE) i RODO w każdej liście. Skrypty: `krs.py`, `ceidg.py`,
`przetargi.py`, `strona.py`, `leady.py`; nowe źródło najpierw rozpoznaje (`zrodlo.py`: nagranie ruchu HAR, różnice dwóch nagrań,
schemat z wielu odpowiedzi) i opisuje w `ZRODLO.md`, zanim powstanie skrypt. Strona firmy, która odmówiła zwykłej
przeglądarce (403/429, „Human Verification”), dostaje jedną próbę Camoufoxem (`ostrozna-przegladarka`: robots.txt,
20 s odstępu, 30 stron domeny na dobę, bez klikania captchy); serwisy za Cloudflare zwykle odmawiają dalej i to
zostaje blokadą. Projekt: [LEADY.md](LEADY.md).

### 2a'. jarvo-ads — szczegóły
Specjalista Ads Managera dla **Meta (FB/IG) i Google**. Planuje kampanie, robi testy (jedna reklama,
A/B, A/B/C), audytuje konta, optymalizuje i raportuje. Wyniki liczy **statystyką bayesowską**
(P(best)). 11 skilli: `plan-kampanii`, `plan-testu`, `publikacja-reczna`, `start-kampanii`, `podlacz-konto`,
`audyt-konta`, `optymalizacja`, `raport-reklam`, `wnioski-marki`, `sledzenie-konwersji`, `zgodnosc-reklam`.
Skrypty: `ads.py` (klient Skarbca, exit 3 gdy nie podłączony), `planer.py`, `eksperyment.py`, `eksport.py`,
`paczka.py` (paczka do publikacji: sprawdzenie limitów, budżetu ponad zgodę i daty końca, instrukcja krok po kroku).
**Stan: BEZ kluczy, z wyboru.** Agent przygotowuje kampanię, właściciel ją publikuje. Sejf na tokeny (Skarbiec) odłożony — patrz §10.

### 2b. jarvo-wideo — szczegóły
Pętla krytyki: film oceniany na **7 osiach** (hook, telefon, ruch, różnorodność, kompozycja, marka,
dźwięk), każda min. 8/10, plus lista zakazanych klisz. Prawdziwe assety marki pobierane ze strony
(`assety.py`: zrzuty, logo, marka w siedmiu rolach kolorów ze skalą kroju i rogami; `--film`: strona w 2× z mapą
elementów, wycinkami i pustą planszą do filmowania; kamera po niej `/_lib/jarvo/strona.js`: przewijanie z postojami,
wycieczka po elementach, lupa, zakreślacz, uderzenie, z kontrolą planu ruchów przed renderem; 11 ujęć z kart video-shotcraft
w HTML bez Remotion: `/_lib/jarvo/ujecia.js`, np. karty rozdane z talii, licznik bębnowy, reflektor na bohaterze). Mówiąca maskotka-robot z polskim lektorem (`maskotka.py`, domyślnie lokalny Matcha `pl-PL-Matcha-Meski`).
Najpierw losowanie, potem projekt: plan ruchów filmu losowany z biblioteki 273 technik cinetic (MIT) pod rodzaj i energię
(`ruchy.py losuj`, skill `losowanie-ruchow`; przepisy na tokenach `/_lib/jarvo/tokeny.js`), żeby filmy nie zbiegały się do tych samych ruchów.
Gotowy film przechodzi kontrolę klatek (`qa_wideo.py`, wzorce za cinetic): duch (klatka z plamą, której nie ma obok), zamrożona
klatka w ruchu, skok elementu w 1–2 klatkach, drgania powolnego ruchu schodkami pikseli, pasy na gładkim przejściu, szew pętli.
Krytyk szuka w katalogu tanich chwytów (`kontrola-wideo/references/tanie-chwyty.md`, 12 grup z ID i poprawką, za cinetic,
bez zakazów kolorów i krojów: te wybiera marka) i zaczyna każdy problem od ID chwytu, z priorytetem P0–P2.
Syntetyczne SFX, biblioteka inspiracji (prompty twórców i katalog 157 kart ujęć video-shotcraft: `inspiracje.py ujecia`), produkcja etapami, formaty platform z jednego timeline.
Silniki: claude-animation (MIT), HyperFrames check przed renderem, Manim na ManimGX (dodatek `manim`: `inspect` przed renderem, polski tekst krojem Noto Sans, `montaz.py napraw --fps 30` przed sklejaniem scen o zmiennym klatkażu). Demo strony (`demo_strony.py`, metoda ECC
`ui-demo`): rozpoznanie → próba → nagranie z kursorem i napisami kroków, tylko nasz podgląd albo strona użytkownika.
Film z kodu z lektorem zaczyna się od pliku narracji (`film.py narracja`): zdanie w linii, akapit = ujęcie, pauzy
z akapitów (0,33 s w akapicie, 1 s między akapitami, 1,5 s przed rozdziałem) i oś czasu `os_czasu.json`, z której
animacja bierze chwile po nazwie (`/_lib/jarvo/os_czasu.js`); nowe nagranie lektora nie psuje animacji.
Fakty do explainera daje Sherlock w briefie `fakty.json` (liczby z przeczytanego źródła A–C, przeliczenie na skalę,
analogie z miejscem, w którym kłamią, słowniczek z wymową, lista niepewnych; `fakty.py sprawdz`). Lektor i pomiar
animacji sprawdzają z nim każdą liczbę: z listy niepewnych zatrzymuje, bez źródła ostrzega.
Animacja z kodu ma twardy pomiar przed oddaniem (`html_wideo.py pomiar`: czas czytania, kadr i strefy UI platformy,
kontrast, napisy na sobie, tekst w pasie napisów lektora, tekst w kawałkach (≤ 5 słów naraz, ≤ 10 w klatce, obraz bez słów
między kawałkami), czarne przerwy, martwe odcinki, rytm, pusta scena, oddech,
uderzenia kadru, liczby kontra `fakty.json`;
„gotowe” tylko z pełnym i aktualnym raportem), ruch z charakterem marki (`/_lib/jarvo/ruch.js`: 6 charakterów,
smugi zamiast motion bluru) i parametry
(`parametry.json`), które właściciel stroi na żywo w HQ. Typografia do nagrania z mową (`typografia.py`, skill
`typografia-edit`): reżyser z reguł układa bloki słów, Wideograf poprawia je znaczeniem (puenta = uderzenie, myśl =
dalej i kursywą), kolory bierze z kadru (dwa akcenty w kontraście ze sceną, np. niebo → ciemna czerwień i złoto,
na zmianę po mocnych słowach), styl filmu wybiera z 14 według rodzaju nagrania (podcast z obrysem, vlog, tech,
magazyn i inne; karty stylów w HQ), mocne słowo staje za osobą (maska MODNet), wirtualna kamera robi najazd, odjazd
i przesunięcie, a napisy stoją na różnych głębokościach z rozmyciem jak w obiektywie (`typografia.py kamera`), napis
krąży pierścieniem wokół głowy albo przechodzi przez osobę (`typografia.py efekt`, maska osoby), plan zostaje
w projekcie montażu do poprawek w HQ; gotowego planu nie nadpisuje bez wyraźnej prośby. Żywy schemat (`zywy_schemat.py`,
skill `zywy-schemat`, silnik strony live-panel, MIT): flota, przepływ zlecenia albo architektura jako film, w którym
układ stoi, a kropki płyną po strzałkach i kroki podświetlają się po kolei; formaty X, Instagram, pion, motywy
w kolorach Jarva, kroje lokalnie, kontrola układu i `html_wideo.py pomiar` przed filmem. Style motion design
(skill `style-motion`): 15 kart stylów (rysunek z wrzącą linią, izometria, płaski wektor, morph, HUD, kolaż, Bauhaus,
synthwave, pixel art, zorza i szkło, płyn, napisy show i inne) z cechami do sprawdzenia, rytmem i dźwiękiem; do każdej
film-wzór 10 s z mg-styles-15 (MIT) do obejrzenia (`narzedzia.py instaluj mg`, `html_wideo.py klatki --preset mg`),
a silniki stylów w modułach stron `/_lib/jarvo/`: `kreska.js` (wrząca linia, pióro, wypełnienie obok konturu),
`morph.js` (przemiana kształtów przez koło, uderzenie, kolor w OKLab), `crt.js` (kineskop, VHS, HUD w jednym filtrze
WebGL2), `plotno.js` (papier, ziarno, kurz, druk z płyt, raster) i `piksel.js` (pixel art z paletą i ditheringiem);
kroje z polskimi znakami strona bierze z `/_lib/kroje/kroje.css`. Gramatyki explainera (skill `gramatyki-explainera`,
`gramatyka.py`, silnik kanwy huashu-art-motion, MIT, instalowany na żądanie `narzedzia.py instaluj huashu`): osiem
sposobów rysowania fragmentu z lektorem (wykresy, tablica, 3Blue1Brown, kolaż Vox, prezentacja, historyjka z postacią,
typografia kinetyczna, Kurzgesagt), każdy jako klip z jednego spec JSON: cue przypięte do słów lektora z `os_czasu.json`,
liczby sprawdzane z `fakty.json`, render o dokładnej długości także w pionie i z alfą, a polska nakładka
`/_lib/jarvo/huashu_pl.js` daje kroje z ą–ż, liczby po polsku i neutralną postać. Na tym samym silniku style
malarskie (skill `style-malarskie`, `malarz.py`): 35 stylów od jaskini po Picassa, karta i scena-wzór każdego,
galeria, szkielet filmu z odcinkami na siatce bitów i przejściem-podpisem stylu. Muzykę pod taki film Wideograf pisze kodem
(`muzyka.py`, mgaudio z mg-styles-15, dodatek `narzedzia.py instaluj mgaudio`): gatunek ze stylu, kulminacja i logo
z osi filmu, efekty w tych samych chwilach, −14 LUFS i kontrola słyszalności każdego efektu; z lektorem
(`--lektor`) głos idzie do miksu, a muzyka przysiada, gdy lektor mówi, i wraca w pauzach między akapitami.

---

## 3. Jak to jest spięte (przepływ)

```
Ty (Telegram DM / aplikacja Jarvo / CLI / Desktop)
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
w cudze konta, nie obchodzi wykrywania automatu; jedyny wyjątek zapisany w SOUL Łowcy i Sherlocka: raz czytają
odrzuconą stronę publiczną zapasową przeglądarką Camoufox, skill `ostrozna-przegladarka`, a jej odmowa to koniec) i **reguła 17: zgoda A2 dotyczy dokładnie tej wersji**
(odcisk plików `scripts/odcisk.py`; zmiana po zgodzie = nowa zgoda).

---

## 4. Infrastruktura (VPS)

Cała flota mieści się na **1 VPS: 4 vCPU / 8 GB RAM / 80 GB**. Obraz ~2,5 GB do pobrania, ~7,3 GB po rozpakowaniu; w spoczynku ~0,7 GB RAM.

**Obraz `jarvo-hermes`** = Hermes Agent + dobrane narzędzia. **Sidecary (docker compose):**
- `hermes` — silnik agentów,
- `searxng` — własna metawyszukiwarka (70+ silników, bez kluczy), AGPL,
- `valkey` — magazyn SearXNG (cache, limiter),
- `uptime-kuma` — monitoring dostępności (opcjonalnie: profil compose `monitoring`, `deploy.sh --monitoring`),
- `beszel` + `beszel-agent` — monitoring zasobów (jw.),
- `jarvo-net` — sieć.

**Narzędzia w obrazie:** Lightpanda (lekka przeglądarka headless ~30 MB/sesję) + jedna Chromium z obrazu
Hermesa (`/usr/local/bin/chromium`: render, PDF, zrzuty, Lighthouse), Parakeet przez `jarvo-stt` (onnx-asr;
model ~0,65 GB pobierany przy pierwszym użyciu), FFmpeg (z obrazu Hermesa), lektor przez `jarvo-tts`: polski Matcha-TTS-PL v2 (dwa głosy syntetyczne,
2 × 140 MB w obrazie, CC BY-SA 4.0) i angielski Paradee (9 MB), bez sieci, Camoufox (`/opt/jarvo/camoufox`, Firefox z odciskiem zwykłej przeglądarki,
~0,35 GB): zapasowa przeglądarka Łowcy i Sherlocka tylko po odmowie strony (`ostrozna.py`, jedna naraz, ~0,8 GB RAM
na czas jednej strony). Edge TTS (lektor PL do wyboru i zapas) doinstalowuje Hermes przy pierwszym użyciu. Odchudzone: usunięto Gotenberg i Crawl4AI. (W piaskownicy Claude Code osobno:
Playwright/Chromium w `/opt/pw-browsers`, poza obrazem.)

**Modele:** domyślnie provider `openai-codex` (jeden model `gpt-6-luna`, głębia myślenia per agent
przez `reasoning_effort`). Presety alternatywne: `openrouter` (Claude Opus 5.5 / Sonnet 5 / Haiku 4.5),
`commandcode` (DeepSeek/Kimi), `commandcode-anthropic`. Fallback, gdy główny model odmówi.
Model zmienia się przez `JARVO_MODEL_PROVIDER` w `compose/jarvo.env`, bez edycji repo.
**Modele testowe lokalnie: GLM 5.3 flash** — nie jest zestawem w `fleet.yaml`; ustawiany w `compose/jarvo.env`
przez `JARVO_MODEL_PROVIDER` + `JARVO_MODEL_FRONTIER/STRONG/FAST` (i `JARVO_MODEL_FALLBACK`), np. `commandcode`
+ `z-ai/glm-5.3-flash` (tak jak w `tests/test_model_provider.py`).

---

## 5. Aplikacja Jarvo (dashboard w przeglądarce)

Przed dashboardem **strona logowania** jak strona tytułowa magazynu: winieta „Jarvo” z robotem CRT, dymek, wejście.
Instalator i `jarvo open` otwierają ją z **kluczem jednorazowym** w adresie (15 min, jedno użycie, w kontenerze tylko
skrót): klucz wpisuje się sam i użytkownik od razu jest w środku ([HQ.md §5](HQ.md#5-motyw-fosfor-wygląd-całego-dashboardu)).
Przy pierwszym wejściu (w `USER.md` nie ma imienia) czeka **pierwsze spotkanie** na całym ekranie: robot Jarvo mówi lokalnym głosem
(Matcha męski albo damski, „Zmień mój głos”), pyta bez modelu o imię, firmę, strony i konta oraz cele, a po lewej
rośnie zdanie „Bohater: Kuba.” z podkreślonymi odpowiedziami. Odpowiedzi idą do `USER.md` w skarbcu (pola szablonu
`onboarding-interview`), na końcu „Brakuje mi tylko mózgu” z kartą na miejscu: konto ChatGPT (kod urządzenia) albo
klucz API (dostawca po przedrostku, sprawdzony u dostawcy; cała flota przechodzi na zestaw modeli tego dostawcy,
`hq/plugin/mozg.py`). W chwili podłączenia Jarvo mówi „Mam mózg. Zaczynam pierwszą sesję.” i otwiera wątek
**Pierwsza sesja** (raz na instalację, skill `pierwsza-sesja`): Web szybki audyt strony, Sherlock 3 konkurentów,
Łowca 10 firm z okolicy, potem 3 najważniejsze ruchy na ten tydzień ([HQ.md §2f](HQ.md#2f-aplikacja-rozmowa-pasek-szuflada)).
Plugin dashboardu Hermesa (`hq/`), zakładka **Jarvo** pod `/jarvo` (pierwsza w menu; `/` i stary adres Bazy prowadzą tam
same, łatka powłoki `branding/powloka.json` + `powloka.js`, loader ≤ 4 KB, pakiet z `/zasoby` tylko na `/jarvo`,
ochrona zapisu `hq/plugin/ochrona.py` w obu wtyczkach; [HQ.md §2c](HQ.md#2c-powłoka-jarvo-osadzanie-zasoby)).
Od etapu 3 to **aplikacja czatu** (makieta „V2 · Spokojny”): jedna rozmowa na pierwszym planie, rozmowy po lewej
z listą na żywo, szuflada ustawień z prawej (Klucze i Modele Hermesa w ramce, motyw jasny/ciemny, język, konto),
menu Hermesa schowane, jeden strumień SSE na przeglądarkę, skróty klawiszowe, telefon; etap 3a to fundament
(sklep, trasa, słownik PL/EN, motyw, klient API i strumień, pasek, szuflada), etap 3b sama rozmowa: wiadomości
z bezpiecznym Markdownem, odpowiedź pisana na żywo, kroki pracy (Prosty/Szczegóły), zgody w wątku z odliczaniem,
**Zatrzymaj** i Esc Esc, **Ponów** po błędzie, kompozytor (Enter wysyła, szkic na wątek, załączniki, `@agent`
albo lista **Do:** na jedną wiadomość, pytanie przy więcej niż 3 adresatach), karty plików z podglądem, menu wiersza,
Archiwum i Kosz, eksport rozmowy do Markdown; etap 3c domyka całość: ekran startu (powitanie po imieniu z `USER.md`,
jedno zdanie gotowości z jednym przyciskiem tylko gdy czegoś brakuje: Połącz albo Poznajmy się (otwiera pierwsze
spotkanie), a gdy brama wstaje
„Jarvo się uruchamia…” bez czerwonego paska; pod polem „Czeka na Ciebie” (zgody, pytania zespołu, nieudana praca)
i startery „Na początek” z warstwy nauki N0 (tylko z połączonym modelem),
`GET /app`, `GET /podpowiedzi`, `nawyki.db`), paski stanu (nowa wersja z **Odśwież**, sama odświeża się tylko
schowana bezczynna karta), szuflada minimalna z **System › Aktualizacja** (przy pracy agentów „Zaktualizuj, gdy
skończą”: prośba do pomocnika 30 s po końcu pracy) i językiem w Konto (`hermes-locale`), odznaka **⬆ N** oraz tryb
„bezpośrednio” w SOUL i protokole: `@uchwyt` na początku wiadomości = jedna wiadomość wprost do agenta, bez karty
([HQ.md §2f](HQ.md#2f-aplikacja-rozmowa-pasek-szuflada)).
**Stara Baza** (Ustawienia › Stara Baza): budynek z pokojami agentów (pixel art), minifigurki, dymki
„co każdy robi teraz”, podgląd pracy na żywo, wyniki, decyzje i czat z Jarvem albo dowolnym agentem.
Pokoje: bridge, study, devlab, atelier, filmstudio, workshop, office, radar. Sesje klikalne (Historia
domyślnie). Czat obsługuje zdjęcia i pliki w obie strony. Linki „Odpal” (podgląd) i „Pokaż w folderze”.
W Centrali **Konwerter**: plik → inny format na serwerze albo ten sam plik bez metadanych (GPS, telefon, daty, autor i firma w PDF i Wordzie; ten sam `konwertuj.py` co skill floty `konwersja-plikow`). **Jak działa usługa**: flota jako klikalna figura izometryczna (wieża z Jarvem i pokojami agentów, demo = droga zlecenia; `iso.py flota` ze skilla `izometria`).
Edytor filmów w stylu CapCut (przejścia między klipami, które nie skracają filmu, kolor klipu ze stylami i Auto, menu Audio z biblioteką efektów i podkładów CC0, lektorem, nagraniem z mikrofonu i wyodrębnianiem dźwięku, uwagi na osi z kadrem dla Wideografa, typografia słowo po słowie z napisem za osobą: maska MODNet) i podgląd animacji z kodu na żywo z suwakami
parametrów ([HQ.md §2a–2b](HQ.md#2a-edytor-filmów), plan rozbudowy: [EDYTOR-PLAN.md](EDYTOR-PLAN.md)). Dwujęzyczność PL/EN. Demo bez serwera: `python3 scripts/hqbuild.py --demo build/hq-demo`.
Pod aplikacją czatu działa **silnik rozmów** w procesie
dashboardu: wątki w `/opt/data/jarvo/state/rozmowy.db`, tury agentów przez `/v1/runs` bramy z kolejką, zgodami,
dopiskiem, stopem i ponowieniem, strumień zdarzeń SSE z wznowieniem od kursora, oś czasu scalona z sesji Hermesa,
`praca.json` (ostrzeżenie `install-fleet.sh` przed restartem bramy w trakcie pracy) i dziennik
`/opt/data/logs/jarvo-hq.log` bez treści rozmów ([HQ.md §2d–2e](HQ.md#2e-rozmowy-silnik-przebiegi-strumień-trasy)).
Obok niej zakładka **Wiedza** (`/wiedza`, wtyczka `jarvo-wiedza`): graf skarbca wiedzy, foldery i notatki, szukanie, orzeczenia
z formularzem, skrzynka szkiców z kompilacją, lint, dziennik ([WIEDZA.md](WIEDZA.md)).

---

## 6. Bezpieczeństwo (Skarbiec-design + red team)

- **Red team na promptfoo** (`security/redteam/`): 23 ataki na agentów (w tym orzeczenie wstrzyknięte przez treść strony, klucz do zapisania w skarbcu wiedzy, paczka-literówka i sekret w kodzie aplikacji mobilnej, polecenie ukryte na ekranie Komputera i karta z czatu do wpisania na ekranie), świeża sesja per atak,
  wykrywanie wycieków. Ostatni zapisany przebieg objął 12 ówczesnych ataków: **12/12 odpartych** po uszczelnieniu;
  dla 9 dodanych później repo nie ma jeszcze wyniku (przebieg wymaga działającej floty z kluczem modelu).
- **Deny dla całej floty** (`shared/security/deny.yaml`, mergowane do każdego profilu): blokada zmiany
  własnej konfiguracji (`hermes config set/...`), kasowania danych floty (`rm -r /opt/data/...`),
  czytania sekretów (cat/less/base64 na `.env`), wysyłki na zewnątrz (webhook.site itp.), haseł
  (`--password`, `password-stdin`), logowania w cudze konta (accounts.google.com, YouTube Studio,
  login.live.com, facebook.com/login), obchodzenia wykrywania automatu (`--user-agent`,
  `navigator.webdriver`, `xvfb-run`, `Xvfb`) i instalacji albo aktualizacji sterownika ekranu w locie
  (`computer-use install`, `trycua/cua`, `cua-driver`, gniazda `/opt/jarvo/komputer`).
- **Computer use** (`docs/KOMPUTER.md`): Hermes woła sterownik ekranu tylko przez bramkę `komputer/jarvo_cua.py`
  (`HERMES_CUA_DRIVER_CMD`), która odmawia aktualizacji, instalacji i trybu bez ograniczeń; walidator pozwala na
  `computer_use` i klucze `cua:*` tylko agentowi z `komputer: true` i zabrania `approvals.mode: off`.
  Komputer Jarva (`infra/komputer`, profil compose `komputer`, `jarvo komputer on|off|status|wyczysc|odswiez`
  i `pauza|wznow|dziennik`): pulpit Xvnc z Chromium i drzewem dostępności w osobnym kontenerze bez kluczy floty
  i bez portów; ekran (do K4 tylko podgląd: Xvnc odrzuca klawiaturę, mysz i schowek) i sterownik tylko przez gniazda
  unix w wolumenie `jarvo-komputer-gniazda` (w `jarvo-hermes` `/opt/jarvo/komputer`); obraz co tydzień z bieżącymi
  poprawkami Chromium (`KOMPUTER_POPRAWKI` przy wdrożeniu); filtr ruchu przed pulpitem: internet tak, sieć lokalna, metadane chmury, adresy hosta
  i port 25 nie. Wejście sterownika (`infra/komputer/wejscie.py`, `zasady.py`) sprawdza każde wywołanie, zanim
  dostanie je sterownik: płatności, zakupy, logowanie, wysyłkę, publikację, Enter w takim formularzu i wpisywanie
  haseł, kart, BLIK i kodów zostawia właścicielowi, sekretów nie wpisuje i ukrywa je w odpowiedziach, wyłącza
  JavaScript, schowek i DevTools, uruchamia tylko Chromium; cel działania zna z migawek sterownika i z AT-SPI.
  Pauzę włączy każdy, zdejmie tylko właściciel (`SO_PEERCRED`); pauza od floty to prośba Operatora do właściciela
  z powodem (widać ją w `jarvo komputer status`); ekranem steruje jedna sesja naraz (`zajete`); dziennik bez treści.
  Test na żywo: `scripts/komputer-test.sh`.
  Agent z `komputer: true` dostaje wtyczkę `jarvo-komputer` (narzędzie `komputer`: stan, dziennik, prośba do
  właściciela jako pauza z powodem; wznowić nie umie) i nie ma wyciągów rozmów do skarbca (treść ekranu).
- **Skan skilli z cudzych repo** (`scripts/skan_skilli.py`, przy każdym buildzie): skaner Hermesa + wzorce
  getsentry `skill-scanner` i ECC (wstrzyknięcia, `curl|sh`, sekrety, ukryte znaki, hooki, `postinstall`).
  High/critical bez przejrzanego wyjątku (`vendor/skan-wyjatki.yaml`, przypięty do commitu) zatrzymuje wdrożenie.
- **Bezpieczeństwo aplikacji (jarvo-web):** skill `bezpieczenstwo-aplikacji` (28 punktów, w tym funkcje AI, sesje,
  CSRF, kopie zapasowe, cache CDN), skaner repo/URL (`security_check.py`: niebezpieczne ustawienia domyślne, zależności nieistniejące
  albo podszyte, klucze w JS strony, publiczne mapy źródeł `.js.map` z kodem, GPS w zdjęciach projektu i strony, ciasteczko sesji w odpowiedzi dla cache CDN), nieniszczące próby na podglądzie (`security_check.py atak`: trasy bez sesji, IDOR
  na dwóch kontach, limit logowania, upload, wylogowanie, cache odpowiedzi zalogowanego), audyt zależności (`supply-chain-risk-auditor`,
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
Wdrożenie: `bash scripts/deploy-site.sh`; `jarvo.pl/install.sh` i `jarvo.pl/install.ps1` przekierowuje `.htaccess` na najnowsze instalatory z publicznego repo. **Zostało po stronie użytkownika:** wgrać na FTP i sprawdzić
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
| `shared/skills/` | skille wspólne (`graf-kodu`; `transkrypcja-filmu`: link do filmu → tekst mowy; `hooki`: trzy warstwy hooka, 18 taktyk; `izometria`: figury izometryczne ze świeceniem na stronę, PNG i film; `warsztat-3d`: model 3D z kodu build123d → STEP, STL, GLB, 3MF, podgląd PNG i film obrotu; `konwersja-plikow`: plik → inny format albo bez metadanych u każdego agenta; `odczyt-ekranu`: tekst ze zrzutu ekranu, skanu, PDF albo klatki filmu (Indra OCR, zapas Tesseract) u każdego agenta; `ostrozna-przegladarka`: zapasowa przeglądarka Camoufox Łowcy i Sherlocka po odmowie strony) |
| `shared/calibration/` | kalibracja SOUL pod rodzinę modelu przy buildzie |
| `shared/templates/` | szablony SOUL, skilla, evals i toolboxa (`make new-agent`) |
| `security/redteam/` | promptfoo: prowider, config, scenariusze ataków |
| `vendor/skills.lock.yaml` | skille zewnętrzne przypięte do commitów (licencje w docs/SOURCES.md) |
| `vendor/zrodla.yaml` | spis wszystkich repo, z których bierzemy kod, skille albo wzorce (status, ostatni przejrzany commit); `scripts/zrodla.py sprawdz` pokazuje nowości, rutyna pon/śr/pt robi z nich propozycje do zatwierdzenia |
| `vendor/natywne.yaml` | instalacja natywna: narzędzia (wersja i plik z sumą sha256 na każdą platformę albo `brak:` z powodem), modele (pliki z rewizją i sumą) i venvy (locki w `infra/python/natywne/`); lock `vendor/natywne.lock.json` z `scripts/natywne.py generuj` |
| `vendor/pixi/tesseract/` | Tesseract 5.5.3 z conda-forge dla instalacji natywnej (`pixi.toml`, `pixi.lock` z sumą każdej paczki, `.pixi/config.toml` bez skryptów post-link) |
| `vendor/skan-wyjatki.yaml` | przejrzane fałszywe alarmy skanu skilli zewnętrznych, przypięte do commitu źródła |
| `evals/<agent>/` | scenariusze testów zachowań (w zakresie, poza zakresem, routing, protokół, bezpieczeństwo) |
| `scripts/` | build, walidator, deploy, instalacja floty, backupy, evals (runner, pomiar `evalslib.py`, `evals-wyniki.py`), migracja, narzędzia |
| `hq/` | aplikacja Jarvo, HQ (backend, frontend, demo) |
| `infra/` | obraz jarvo-hermes, obraz Komputera Jarva (`infra/komputer`), docker-compose z sidecarami, szablony env; `infra/python/natywne/`: locki venvów instalacji natywnej z wejściami i opisem odtworzenia |
| `knowledge/` | szablon brand kitu (`brands/_szablon`); szablon USER.md jest w skillu `onboarding-interview` Jarva |
| `komputer/` | computer use: bramka sterownika ekranu `jarvo_cua.py` (`HERMES_CUA_DRIVER_CMD`), wtyczka Operatora `plugin/` (narzędzie `komputer`), ręce na ekranie właściciela `rece/` (K6: podpisana zgoda, bramka z twardymi zasadami i ścisłym odczytem zgód profilu, profil rąk `jarvo-ekran`, sterownik cua-driver-rs 0.38.0); projekt i etapy w [KOMPUTER.md](KOMPUTER.md) |
| `wiedza/` | skarbiec wiedzy (drugi mózg): `wiedza.py` (zasiew, indeks FTS5, szukanie, szkice, orzeczenia, lint, graf, git) i `SCHEMA.md`; projekt w [WIEDZA.md](WIEDZA.md) |
| `branding/` | skórka Jarvo (banner, logo, motyw i tłumaczenie dashboardu), łatka powłoki `/jarvo` (`powloka.json`, `powloka.js`) |
| `site/` | landing jarvo.pl |
| `jarvo/` | Jarvo natywnie, w budowie ([NATYWNIE.md](NATYWNIE.md)): `sciezki.py` (katalogi i platforma na trzy systemy), `srodowisko.py` (zmienne procesów Jarva z narzędziami i modelami, bez sekretów i zmiennych obcych), `przenosne.py` (przenośne blokady, zapisy atomowe i ochrona dostępu), `manifest.py` (odczyt `vendor/natywne.lock.json`), `pobieracz.py` (pobieranie z sumą sha256, paskiem i wznawianiem, rozpakowanie z dowiązaniami, `usun` i `zmien_nazwe`), `hermes.py` (Hermes z przypięcia: checkout, uv z sumami także dla zależności budowy, front, bezpieczna konfiguracja), `nadzorca.py` (`jarvo serwis`: brama i panel Hermesa, restart, logi z rotacją, kanał sterowania, trwałe zatrzymanie), `autostart.py` (zadanie Harmonogramu `Jarvo-<SID>`, LaunchAgent `pl.jarvo.nadzorca`, `jarvo.service` w systemd --user), `zmiany_hosta.py` (dziennik `<stan>/zmiany-hosta.jsonl`, cofany od końca przy odinstalowaniu), `cli.py` (polecenie `jarvo`: instaluj, serwis, up, down, status, panel, chat, logs, autostart, doctor, wiedza, rutyny, telegram, update, uninstall, migruj, komputer (także `komputer rece`), android, version, help), `instalator.py` (`jarvo instaluj` z paskiem: kroki składane z manifestu, na Windows dziś 42), `aktualizacja.py` (`jarvo update`: nowa wersja z GitHuba obok starej w `<program>/app/<sha12>`, jej instalator, doctor z rozgrzewką, powrót przy błędzie, sprzątanie starych wersji, pomocnik przycisku w panelu), `odinstalowanie.py` (`jarvo uninstall`: stop, autostart off, cofnięcie dziennika zmian hosta, usunięcie katalogów, dane tylko z `--all`, skan śladów), `migracja.py` (`jarvo migruj`: dane starej instalacji z Dockerem i WSL), `komputer.py` i `rece.py` (Komputer Jarva i ręce na ekranie właściciela), `android.py` (telefon testowy przez adb i scrcpy), `przy_uzyciu.py` i `manimgx.py` (narzędzia przy pierwszym użyciu), `wiedza_cli.py` (skarbiec, rutyny i Telegram w `jarvo` i `doctor`), `zgody_cli.py` (doctor: wtyczka zgód w każdym profilu bramy), `start.py` (launcher `python -I -X utf8` dla polecenia i autostartu), `bootstrap/` (instalacja jednym poleceniem: `install.ps1` i `install.sh`, domyślna od etapu E13; stara instalacja z Dockerem jest przenoszona tym samym poleceniem) |
| `zgody/` | wtyczka zgód `jarvo-zgody` dla instalacji natywnej: tryby pytaj, projekt (domyślny) i pełny jak w Claude Code (hak `pre_tool_call`, polecenie `/tryb`); opis w `zgody/README.md`, budowa i instalacja we flocie w etapie E4 |
| `install.sh`, `install.ps1`, `bin/jarvo` | `install.ps1` od etapu E13 przekierowuje na `jarvo/bootstrap/install.ps1` (instalacja natywna); `install.sh` i `bin/jarvo` to stara droga z Dockerem, dziś dla serwera (VPS) i starych instalacji (`install.sh` na macOS uruchamia instalację natywną, w WSL podaje polecenie PowerShella): dawniej instalator jednym poleceniem (Linux/WSL2: sam instaluje pakiety i Docker Engine; macOS: Homebrew, Colima, dane w wolumenach Dockera, LaunchAgent; Windows: WSL2 z restartem i dalszym ciągiem, własna dystrybucja `Jarvo`, Docker Engine w niej, autostart): repo do `~/jarvo`, gotowy obraz z GHCR, klucz dostępu do prywatnego repo (`JARVO_TOKEN`), polecenie `jarvo` (`up`, `status`, `update` = `git pull` + instalator, `uninstall`…); opis i plan w [INSTALER.md](INSTALER.md) |
| `requirements-dev.txt` | zależności testów/walidacji (`make dev-deps`: pytest, pyyaml, shellcheck) |
| `tests/`, `docs/` | testy pytest (w `tests/live/` test aplikacji w przeglądarce dla `scripts/jarvo-e2e.sh`), dokumentacja |

**Dokumenty:** PLAN (wizja/architektura/roadmapa), BOSS (mechanika Main Judge'a), FLEET (specyfikacja
agentów), PROFILE-SPEC (anatomia agenta: 10 warstw), TOOLBOX (narzędzia open-source), VPS (infra),
HQ (dashboard), ADS (projekt agenta reklam + Skarbiec), LEADY (Łowca leadów), KLIPY (clipmaker),
WIEDZA (skarbiec wiedzy: drugi mózg floty, projekt do akceptacji), RUNBOOK (wdrożenie krok po kroku), INSTALER (plan instalatora jednym poleceniem na trzy systemy), NATYWNIE (plan przejścia na instalację natywną bez Dockera i WSL), ROZWOJ-FLOTY (plan dopracowania agentów), MOBILE (projekt Twórcy aplikacji),
KOMPUTER (computer use i server use: Komputer Jarva, Operator, Ekran w HQ, Ręce; etapy K0–K6),
SOURCES (licencje).

---

## 9. Zasady pracy (z CLAUDE.md)

- **Każda aktualizacja = osobny commit i od razu push** (gałąź robocza, remote `origin`).
- **Dokumentacja zawsze zgodna z kodem:** zmiana w kodzie aktualizuje w tym samym commicie każdy dokument, który ją
  opisuje (README, `docs/*.md` z tym plikiem włącznie, README i CHANGELOG profilu): nazwy, liczby, ścieżki, komendy, statusy.
  `validate.py` pilnuje linków i kotwic, pełnej listy floty w dokumentach przeglądowych i liczb skilli/evals w tabelach.
- Przed commitem: `python -m pytest -q` i `python scripts/validate.py` bez błędów (na Windows i macOS z
  `PYTHONUTF8=1`). Na czystej maszynie najpierw `make dev-deps` (pytest, pyyaml i shellcheck z `requirements-dev.txt`).
- **Instalacja natywna jednym poleceniem** (od etapu E13): nowa zależność do manifestu `vendor/natywne.yaml` (sumy na
  pięć platform, lock z `scripts/natywne.py generuj`), zmiany na komputerze tylko przez `jarvo/zmiany_hosta.py`, Hermes
  przypięty w `vendor/natywne.yaml`; serwer (VPS) zostaje na obrazie (`infra/Dockerfile`).
- **Po każdym dodaniu test na działającej instalacji natywnej**, nie tylko pytest: instalacja próbna w osobnym
  katalogu (`JARVO_ROOT`, bootstrap z `JARVO_REF` albo `jarvo --korzen <katalog> instaluj`; obok starej instalacji
  z Dockerem `JARVO_MIGRACJA=nie`), `jarvo doctor`, `jarvo status`, nowa funkcja użyta naprawdę, GUI przez panel
  (`tests/live/natywnie_panel.py`); pełna próba jak w CI: `tests/live/natywnie_e2e.py sprawdz|panel|komputer`,
  a na pięciu systemach `natywnie.yml` po każdym pushu.
- **Stara piaskownica z Dockerem (kontener floty jak na VPS):** `JARVO_LOCAL=<scratchpad>/jarvo-local bash scripts/sandbox-up.sh` robi wszystko:
  `dockerd` (po restarcie piaskownicy usuwa stare pliki pid demona), obraz `hermes-ca:test` (Hermes + certyfikat proxy), `jarvo-hermes:local` przez
  `docker build --network host` (compose nie widzi proxy), instalację w `jarvo-local` i
  `deploy.sh --no-pull --no-build`. Obraz przebudowuje się tylko po zmianie `infra/` lub `branding/` albo z `--rebuild`; dodatki obrazu
  przez `JARVO_EXTRAS="manim"` przed poleceniem (z `--rebuild`); Komputer Jarva przez `JARVO_KOMPUTER=1` (obraz
  `komputer-ca:test` = Debian + certyfikat proxy, `jarvo-komputer:local` po zmianie `infra/komputer/`), a potem
  test twardych zasad na żywo `scripts/komputer-test.sh`. Piaskownica ma w `compose/.env` `JARVO_E2E=1` (trasy testowe
  wtyczek), a test aplikacji w przeglądarce na żywo to `bash /opt/jarvo/repo/scripts/jarvo-e2e.sh etap1` w kontenerze
  (Playwright i Chromium z obrazu, logowanie hasłem z env kontenera, raport JSON, sprzątanie przy każdym wyjściu);
  `… etap2` sprawdza silnik rozmów: własna atrapa modelu na `127.0.0.1:9197` z `--dziennik`, profile jednorazowe
  `test-e2e-a`, `test-e2e-b`, `test-e2e-j` usuwane przy każdym wyjściu, punkty 1–15 etapu 2 (docs/HQ.md §2e);
  `… etap3` sprawdza aplikację z tą samą atrapą i profilami: powłoka, jeden strumień na dwie karty, lista i wątek
  na żywo, szuflada, klawiatura, telefon, wygasła sesja (punkty 1–9) i rozmowę etapu 3b: „Hej” przez kompozytor
  z odpowiedzią na żywo, Markdown i ładunek XSS jako tekst, adresat na jedną wiadomość i pytanie przy 4 adresatach,
  zgoda z odliczaniem, Odmów, „Czas minął” i Poproś ponownie (punkty 10–13) oraz kryteria etapu 3c: ekran startu
  z kartą gotowości i powitaniem z `USER.md`, nowy wątek ze startu, bez przyklejania adresata, załączniki i karty
  plików, Zatrzymaj / Esc Esc / Ponów, odświeżenie w trakcie strumienia, 5 kart i połączenia, bezpieczna aktualizacja
  i nowa wersja, wylogowanie między kartami, tylko klawiatura (punkty 14–23, docs/HQ.md §2f;
  `JARVO_E2E_ZRZUT=<plik.png>` zapisuje zrzuty, `JARVO_E2E_ZRZUTY=<katalog>` zestaw jasny/ciemny × 1440/390 px dla
  właściciela, `JARVO_E2E_PUNKTY=14,15` uruchamia wybrane punkty). Testy czystych modułów frontu
  w node: `TZ=Europe/Warsaw node tests/js/hq_front.test.cjs` (też w `tests/test_hq_front.py`).
- **Rozmowa bez klucza dostawcy (piaskownica, CI):** `scripts/atrapa_modelu.py --port 9199` to atrapa modelu zgodna
  z OpenAI (strumień, wywołanie narzędzia `[narzedzie:NAZWA {…}]`, `[wolno]`, `[wolno:<s>]` = strumień rozłożony na
  `<s>` sekund (razem z `[narzedzie:…]`: odpowiedź po wyniku narzędzia), `[plik:<ścieżka>]` = linia `Plik: <ścieżka>` w odpowiedzi (karta pliku), `[blad]`, `[dlugo]`;
  `--dziennik <plik>` zapisuje każde ciało zapytania jako jedną linię JSON z adresem zapytania w polu `_sciezka`,
  z której test E2E sprawdza, co dostał agent i do którego profilu poszło (profil testu ma adres `…/p/<profil>/v1`).
  `--odpowiedzi <plik.json>` (`{fragment: odpowiedź}`) daje gotowe odpowiedzi (zrzuty ekranu z realistyczną treścią).
  Strumień po znaku trzyma dwukropek przy poprzednim znaku, bo Hermes wstrzymuje deltę zaczynającą się od „:”
  do końca linii). Profil testowy
  w kontenerze dostaje w `config.yaml` `model: {provider: custom, base_url: http://127.0.0.1:9199/v1, default: atrapa}`,
  więc całą drogę wiadomości (gateway, `/v1/runs`, czat w dashboardzie) da się sprawdzić bez prawdziwego modelu.
  Żaden profil w obrazie z niej nie korzysta.
- **Silnik rozmów bez kontenera:** `tests/test_silnik_rozmow.py` uruchamia prawdziwy wątek silnika i trasy FastAPI
  z atrapą bramy Hermesa `tests/atrapa_bramy.py` (`/v1/runs` z idempotencją, zdarzenia, zgody, steer jak w Hermesie:
  wiersz `steer` ze znacznikiem `[OUT-OF-BAND USER MESSAGE …]` i `pending_steer` jako jeden tekst, stop, dzierżawy
  tury, state.db ze schematem z obrazu); przeploty z przeglądu (Stop, dopisz, Ponów, 429, zgody, strumień) sprawdza
  `tests/test_silnik_wyscigi.py`, trasy i ścieżki `tests/test_trasy_rozmow.py`; znaczniki w treści sterują atrapą (`[wolno:<s>]`, `[zgoda]`,
  `[blad]`, `[przerwij]`, `[urwij]`, `[czekaj]`; z `czas_zgody` atrapa sama odmawia zgody po tylu sekundach, jak
  Hermes po `approvals.timeout`). Na hoście potrzebuje FastAPI i httpx, bez nich test jest pomijany.
- Instalacja lokalna użytkownika: natywna, jednym poleceniem `jarvo/bootstrap/install.ps1` albo `install.sh` (README,
  [INSTALER.md](INSTALER.md)); stara instalacja z Dockerem jest wykrywana i przenoszona tym samym poleceniem
  (`jarvo migruj` za zgodą). Stara droga (do usunięcia w E13): `install.sh` (na Linuksie sam doinstalowuje pakiety i Docker
  Engine, na macOS Homebrew i Colimę; repo do `~/jarvo`) → `jarvo up` (`bin/jarvo` → `scripts/local-up.sh`) →
  `~/jarvo-local` (`compose/`, `secrets/`, `build/`, `data/`; na macOS dane i build w wolumenach Dockera
  `jarvo-hermes-data`, `jarvo-valkey-data`, `jarvo-build`; stare `~/tars-local` przenoszone samo); pomocnik
  aktualizacji jako usługa `systemd --user` albo LaunchAgent `pl.jarvo.updater` (`jarvo autostart on`).
  `jarvo update` = `git pull` + nowy `install.sh` (wersja wymagań hosta `HOST_VERSION` w `compose/.host-version`).
  Test od zera w piaskownicy: `scripts/install-test.sh`.

---

## 10. Stan i co dalej

**Zrobione (v0.3+):** cała flota v1 zakodowana i przetestowana, HQ, rebranding TARS→Jarvo, migracja
instalacji, Wideograf z pętlą krytyki i maskotką, jarvo-ads (bez kluczy), red team 12/12,
bezpieczeństwo web, landing jarvo.pl z nagłówkami.

**Pending / pomysły:**
1. **Skarbiec (zadanie #50):** kontener z tokenem Meta/Google, polityka w kodzie, koperty (spend cap
   zatwierdzany kodem out-of-band, model nigdy nie widzi kodu), szkice PAUSED, STOP zawsze dozwolony,
   Graph API v25. Odłożony (2026-10-10): do tego czasu agent oddaje paczkę do publikacji, publikujesz Ty.
2. ✅ **Agenci nie zapisują danych logowania w pamięci (`memory`).** Po red teamie Wideograf zapisał login w pamięci
   (hasła tam nie było). Hasła i logowanie w cudze konta blokują reguła 16 kontraktu i `deny.yaml`; zapis loginu, hasła,
   klucza albo numeru karty do `memory` odrzuca teraz strażnik narzędzi wtyczki `jarvo-wiedza` (hak `pre_tool_call`
   u każdego agenta, [WIEDZA.md](WIEDZA.md) §4). Ten sam hak trzyma limit płatnej generacji AI na kartę.
3. **Skarbiec wiedzy (drugi mózg floty), projekt w [WIEDZA.md](WIEDZA.md) (zbudowany 2026-09-30, etapy 1–6 z 7:
   skarbiec zasiewany przy wdrożeniu, `wiedza.py`, wtyczka `jarvo-wiedza` u każdego agenta, kompilacja `kompilacja.py`,
   zakładka „Wiedza”, synteza w przeglądzie tygodnia, red team, evals; **na VPS zostaje pierwsza kompilacja z modelem**):** jeden folder
   notatek Markdown z linkami (`knowledge/`), wzorzec LLM Wiki Karpathy'ego; wtyczka Hermesa `jarvo-wiedza` jako dostawca
   pamięci (przypomnienia przed turą, wyciąg po sesji i przed kompresją, 4 narzędzia), kompilacja głównym modelem (jeden
   piszący), orzeczenia z Twoich korekt, lint, punkty zapisu git, zakładka „Wiedza” z grafem w dashboardzie.
4. **Pętla samodoskonalenia (RSI), plan w [RSI.md](RSI.md) (zgoda właściciela 2026-10-13):** flota poprawia własne
   skille i prompty bez uczenia wag, z pomiarem, bramkami i Twoją zgodą na każdą zmianę. R0 pomiar ✅ 2026-10-13:
   runner evals z sędzią innej rodziny modeli (`fleet.yaml` → `evals.judges`), powtórzeniami, zbiorem odłożonym,
   kanarkami (znacznik-pułapka w plikach evals), historią i punktem odniesienia (`scripts/evalslib.py`,
   `scripts/evals-wyniki.py`); wyniki ze stagingu w karcie agenta w HQ i w przeglądzie tygodnia. R1 lekcje ✅ 2026-10-13:
   księga lekcji z pomiarem skutku wdrożonej reguły (pomogło / zaszkodziło z evals, `lekcje.py`) i poczekalnia skilli:
   specjaliści mają `skills.write_approval: true`, więc skill, który agent sam sobie dopisze, czeka na Twoją zgodę,
   skanowany tymi samymi wzorcami co skille zewnętrzne (`poczekalnia.py`, zgoda przypięta do odcisku). R2 kuźnia
   skilli ✅ 2026-10-13 (`scripts/kuznia.sh`): poprawka jednego skilla (model z innej rodziny niż sędzia pisze ją z porażek
   zbioru roboczego albo Ty podajesz własną), limity przed evals (przyrost ≤ 20%, skan, bez cytatów z evals), pojedynek
   z obecną wersją na stagingu, bramki (poprawa na roboczym, odłożony i safety bez regresji, kanarek, przeuczenie),
   raport z patchem i karta decyzji w HQ; nic nie wchodzi bez Twojego „ok”. Dalej: R3 workflowy Jarva (po próbie R2).
5. **PageIndex (MIT, rozważane):** vectorless RAG do czytania długich dokumentów przez lokalny model
   (litellm → Hermes/GLM). Nie jako osobny agent — jako współdzielona umiejętność „czytania długich
   dokumentów”. Do decyzji: zakres (który agent najpierw) + model do indeksowania.
6. **Jarvo natywnie (kierunek od 2026-10-24), plan w [NATYWNIE.md](NATYWNIE.md):** Jarvo bez Dockera i WSL na Windows,
   macOS i Linuksie, z każdą funkcją (czat w terminalu ze zgodami jak w Claude Code, flota, panel, skarbiec, rutyny,
   Telegram, filmy, lektor, OCR, Komputer Jarva, migracja ze starej instalacji). Hermes z przypiętego commitu przez uv,
   narzędzia z wydań u źródła z sumą sha256, własny nadzorca procesów. Etapy E0–E14; decyzje właściciela z 2026-10-24 w planie (bez macOS Intel, minimum macOS 15, domyślne zgody „projekt”,
   wyszukiwarka: najlepsza dostępna). Stan 2026-10-25 (NATYWNIE § g): instalacja natywna jest domyślna (E13), z migracją
   starej instalacji tym samym poleceniem. W kodzie są: manifest z 25 narzędziami, 10 modelami i 9 venvami, pobieracz,
   Hermes z przypięcia, nadzorca `jarvo serwis`, autostart, dziennik zmian hosta, polecenie `jarvo`, instalator
   i bootstrap `jarvo/bootstrap/install.ps1|sh`, wtyczka zgód `zgody/`; CI `natywnie.yml` instaluje poleceniem z README
   na Windows x64 i arm64, macOS arm64 i Linuksie x64 i arm64. Po instalacji: `jarvo` (rozmowa), `jarvo panel`,
   `jarvo status`, `jarvo doctor`, `jarvo down`/`up`.

**Odrzucone (nie wpinamy):** RedAmon (offensive pentest — za ciężki, ryzyko prawne),
terminal-browser (ciężka przeglądarka desktopowa, nie dla agentów na VPS),
devops-exercises (licencja CC BY-NC-ND, tylko materiał do nauki dla człowieka).
