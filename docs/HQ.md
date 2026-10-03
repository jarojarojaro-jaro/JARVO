# Jarvo HQ: kwatera floty (GUI)

Jarvo HQ to zakładka **BASE** w menu dashboardu Hermesa, nad CHAT (`http://<ip-tailscale>:9119/base`, logowanie jak do dashboardu).
Obok niej jest zakładka **WIEDZA** (`/wiedza`): skarbiec wiedzy floty z grafem notatek, orzeczeniami i skrzynką szkiców
(osobna wtyczka `jarvo-wiedza`, opis w [WIEDZA.md §8](WIEDZA.md#8-zakładka-wiedza-w-dashboardzie-i-obsidian)).
Pokazuje flotę jako budynek z klocków. Na górze jest mostek Jarva, pod nim piętra z pokojami snajperów (po dwa na piętro). Każdy
agent ma swój pokój, swoją minifigurkę i dymek z tym, co robi w tej chwili. Kliknięcie pokoju otwiera panel
z podglądem pracy na żywo, kartami, wynikami i czatem. Na dole jest rozmowa: domyślnie z Jarvem, jednym
kliknięciem z dowolnym agentem.

Tryb demo (symulowana flota, bez serwera): `python3 scripts/hqbuild.py --demo build/hq-demo`, potem otwórz
`build/hq-demo/index.html` przez dowolny serwer statyczny.

---

## 1. Co widać

| Element | Skąd dane | Co pokazuje |
|---|---|---|
| Pasek stanu | kanban | karty w toku, w ocenie, zablokowane, w kolejce, zrobione dziś; liczba decyzji |
| Pokój agenta | kanban + sesja pracownika | stan (pracuje, ocenia, czeka na ocenę, czeka na decyzję, ma kolejkę, wolny) jako animacja i znacznik; dymek z bieżącym narzędziem („szuka: …”, „pisze: out/RAPORT.md”) |
| Mostek Jarva | kanban | ekran „Tablica floty” z prawdziwymi licznikami kolumn; Jarvo-monolit ocenia, gdy w torze review jest karta |
| Panel agenta: Teraz | sesja pracownika w `state.db` profilu | karta, nad którą pracuje, czas, sygnał życia i oś kroków na żywo (narzędzia, wypowiedzi, błędy) |
| Panel agenta: Karty | kanban | karty agenta według stanu (7 dni), klik otwiera kartę z historią i komentarzami |
| Okno karty | kanban + katalog roboczy karty | na wierzchu **cel** (inny kolor), kontekst, **wynik** (pliki z `WYJŚCIA` oznaczone ★) i raport wykonawcy; pełne zlecenie (wejścia, DoD, granice), komentarze i historia zwinięte |
| Panel agenta: Wyniki | katalogi robocze | pliki z `out/`: miniatury grafik, podgląd tekstu, PDF, wideo (bez katalogów roboczych: `node_modules`, `.git`, sylwetki `<film>.maska/`) |
| Czat: zdjęcia i pliki | czat HQ + `/opt/data/jarvo/inbox/` | 📎, wklejanie Ctrl+V (zrzut ekranu) i przeciąganie. Plik trafia do `inbox/<data>/`, agent dostaje jego ścieżkę (linia `📎 …`), zdjęcie także jako obraz (model bez widzenia dostaje opis od Hermesa) |
| Czat: pliki od agenta | odpowiedź agenta | linia `MEDIA:<ścieżka>` i obrazy `data:image` jako miniatury, ścieżki `/opt/data/jarvo/…` i adresy http(s) klikalne; obraz ma „Kopiuj obraz” (np. do Telegrama) |
| Akcje pliku wynikowego | plugin + pomocnik hosta | **▶ Odpal** (strona HTML w nowej karcie, `:9120`), **Pokaż w folderze** (Eksplorator Windows w lokalnej instalacji WSL; gdzie indziej: **Kopiuj ścieżkę**), **Pobierz**, podgląd/kod |
| **✎ Edytuj** (każdy film) | edytor w HQ + ffmpeg w kontenerze | montaż w stylu CapCut: oś czasu z miniaturami, cięcie (S), przycinanie krawędzi, przestawianie klipów, tempo 0,25–4×, głośność i wyciszenie, zdjęcia jako plansze, napisy (styl, krój, kolor, przeciąganie na podglądzie), muzyka z katalogu albo z dysku, format 16:9 / 9:16 / 1:1 / 4:5, cofnij/ponów, skróty klawiszowe, uwagi przypięte do osi i kadr z podglądu dla Wideografa. **Eksportuj** zapisuje nową wersję obok oryginału (`film-edycja.mp4`, oryginał zostaje), **Poproś agenta** wysyła Wideografowi prośbę z projektem montażu. Szczegóły: sekcja 2a |
| **◐ Animacja** (animacja HTML Wideografa) | serwer podglądu `:9120` + `parametry.json` + `pomiar.json` obok strony | animacja z kodu bez renderowania MP4: przewijanie, odtwarzanie, klatka po klatce, suwaki, kolory, teksty, przełączniki i krzywe ruchu z `parametry.json` widoczne od razu, **Zapisz parametry**, lista ustaleń pomiaru (klik przewija do chwili) i **Poproś Wideografa**. Szczegóły: sekcja 2b |
| Panel agenta: Czat | API gatewaya | rozmowa bezpośrednia z agentem (sesja HQ, osobna od Telegrama) |
| **📱 Ekran telefonu** (panel Twórcy aplikacji) | telefon testowy floty (`jarvo android on`) + proxy `:9122` | ekran Androida w nowej karcie (ws-scrcpy: podgląd na żywo, klikanie, pisanie), link z tokenem ważny 12 h; przycisk widać tylko, gdy telefon działa |
| Panel agenta: O agencie | fleet.yaml, SOUL, skille | opis, model, autonomia, parametry osobowości, workflowy |
| Centrala: Decyzje | kanban (`blocked` + `needs_input`, karty porzucone po błędach) | pytania agentów; odpowiedź idzie do Jarva, który odblokowuje kartę i zapisuje decyzję. Karta porzucona po błędach ma **Ponów kartę** (wraca do kolejki) albo **Przekaż Jarvowi** |
| Centrala: Misje | `missions/INDEX.md` + kanban | postęp misji (kostki kart w kolorach stanu) |
| Centrala: Na bieżąco | zdarzenia kanbana | kto zaczął, oddał do oceny, skończył, utknął |

Decyzje świadomie idą przez Jarva, a nie bezpośrednio do karty: szef zapisuje je w dzienniku misji i pilnuje
reszty (skill `decision-queue` zna format wiadomości z HQ). Wyjątek: „Ponów kartę” odblokowuje kartę porzuconą
po błędach bezpośrednio (`hermes kanban unblock`), bo tu nie ma czego rozstrzygać.

## 2. Architektura

```
przeglądarka (Tailscale) ── :9119 dashboard Hermesa (logowanie hasłem)
   └─ zakładka „/base” = plugin jarvo-hq (React z SDK dashboardu + htm, bez kroku budowania po stronie serwera)
        ├─ GET  /api/plugins/jarvo-hq/state        co 3 s (ukryta karta: co 12 s): agenci, tablica, decyzje, misje, zdarzenia
        ├─ GET  /api/plugins/jarvo-hq/fleet        opis floty (fleet.json)
        ├─ GET  /api/plugins/jarvo-hq/agent/<a>    co 2,5 s przy otwartym panelu: karty, oś kroków, wyniki (pliki co 10 s)
        ├─ GET  /api/plugins/jarvo-hq/task/<id>    karta z historią i komentarzami
        ├─ POST /api/plugins/jarvo-hq/task/<id>/retry  „Ponów kartę” porzuconą po błędach (hermes kanban unblock)
        ├─ GET  /api/plugins/jarvo-hq/file?path=   podgląd pliku z katalogów floty
        ├─ POST /api/plugins/jarvo-hq/site        link „Odpal” (token) ─► :9120 serwer podglądu stron w pluginie
        ├─ POST /api/plugins/jarvo-hq/reveal      prośba „Pokaż w folderze” ─► pomocnik hosta (explorer.exe)
        ├─ POST /api/plugins/jarvo-hq/android     link „📱 Ekran telefonu” (token) ─► :9122 proxy ekranu w pluginie
        │                                          ─► jarvo-android-ekran:8000 (ws-scrcpy, HTTP i WebSocket)
        ├─ GET  /api/plugins/jarvo-hq/host        czy działa „Pokaż w folderze” (WSL), ścieżki hosta, port podglądu,
        │                                          czy działa telefon testowy
        ├─ GET  /api/plugins/jarvo-hq/chat/<a>/history
        ├─ POST /api/plugins/jarvo-hq/chat/<a>/send ─► gateway :8642 /p/<agent>/api/sessions/<id>/chat/stream (SSE)
        ├─ POST /api/plugins/jarvo-hq/chat/<a>/reset
        ├─ POST /api/plugins/jarvo-hq/upload      plik z czatu (📎, Ctrl+V, przeciągnięcie) ─► /opt/data/jarvo/inbox/<data>/
        ├─ GET/POST /api/plugins/jarvo-hq/edit/…  edytor filmów: info, media, save, stamp, srt, speech, proxy,
        │                                          proxy-file, maska, export, job/<id>[/cancel] (sekcja 2a)
        ├─ GET  /api/plugins/jarvo-hq/anim/check  czy plik HTML to animacja z kontraktem (przycisk „◐ Animacja”)
        ├─ GET  /api/plugins/jarvo-hq/anim/info   link podglądu z mostkiem ─► :9120, parametry, stan pomiaru (sekcja 2b)
        ├─ POST /api/plugins/jarvo-hq/anim/params nowe wartości ─► parametry.json obok strony
        ├─ GET/POST /api/plugins/jarvo-hq/update  stan i prośba o sprawdzenie/aktualizację (pomocnik hosta scripts/updater.py)
        └─ GET  /api/plugins/jarvo-hq/health       klucze API profili i dostępność gatewaya
backend pluginu (plugin_api.py, w procesie dashboardu)
   ├─ hq_core.py: odczyt kanban.db i state.db profili w trybie tylko do odczytu, wyliczenie stanu
   └─ klient API gatewaya z kluczem profilu czytanym z jego .env (przeglądarka nigdy go nie widzi)
```

Pliki w repo:

| Ścieżka | Rola |
|---|---|
| `hq/plugin/manifest.json` | manifest pluginu dashboardu (zakładka BASE w menu, przed CHAT) |
| `hq/plugin/plugin_api.py` | trasy FastAPI, proxy czatu do gatewaya |
| `hq/plugin/hq_core.py` | logika stanu (bez FastAPI, testowana w `tests/test_hq_core.py`) |
| `hq/plugin/edytor.py` | edytor filmów: walidacja projektu i planu typografii, polecenie ffmpeg, ffprobe (testy: `tests/test_edytor.py`, `tests/test_typografia.py`) |
| `hq/plugin/animacja.py` | animacja HTML: schemat i zapis `parametry.json`, stan pomiaru, mostek podglądu (testy: `tests/test_animacja.py`); build dokłada do pluginu `pomiar.py` Wideografa (odcisk i aktualność raportu) |
| `hq/web/src/*.js` | frontend: podstawy, API, grafika pokoi, budynek, panel, napisy, typografia (`48-typografia.js`), edytor filmów i jego uwagi z kadrami, podgląd animacji z parametrami, czat, HUD, aplikacja, widżet aktualizacji |
| `hq/web/style.css` | styl (tokeny motywu dashboardu, animacje, responsywność; edytor i okno animacji z własnymi tokenami) |
| `hq/web/fonts/` | Inter (OFL, `LICENSE-Inter.txt`): krój zapasowy edytora, gdy system nie ma SF Pro, Segoe UI ani Roboto; `kroje/`: kroje napisów i typografii (OFL, `scripts/kroje.py`) |
| `branding/fonts/` | kroje motywu Fosfor (VT323, IBM Plex Mono, OFL) i `fosfor.css`; te same pliki na stronie logowania |
| `hq/web/vendor/htm.umd.js` | htm 3.1.1 (Apache-2.0): składnia podobna do JSX bez kompilacji |
| `hq/web/demo/` | strona demo i symulator floty |
| `scripts/hqbuild.py` | build pluginu (sklejenie JS, `fleet.json` z fleet.yaml i SOUL) i demo |
| `scripts/share_keys.py` (kopiowany do pluginu) | wspólne klucze floty na żywo: klucz dostawcy z głównego `.env` trafia do `.env` agentów |

Wdrożenie jest częścią zwykłego `deploy.sh`: `build.py` buduje plugin do `build/plugins/jarvo-hq`,
`install-fleet.sh` kopiuje go do `/opt/data/plugins/jarvo-hq`, włącza (Hermes wymaga jawnego włączenia
pluginów użytkownika), generuje brakujące `API_SERVER_KEY` profili i restartuje sam dashboard (s6). Dashboard czyta
listę wtyczek tylko przy starcie, więc restart następuje, gdy odcisk treści `jarvo-hq` i `jarvo-wiedza` różni się od
odcisku z ostatniego restartu (`/opt/data/plugins/.odcisk-panelu`). Dzięki temu wtyczka skopiowana przez przerwaną
instalację pojawi się przy następnej, a wdrożenie bez zmian nie rozłącza otwartego panelu.

## 2a. Edytor filmów

Bez bibliotek i bez nowych usług: edytor to plik `hq/web/src/45-edytor.js` (~146 KB nieskompresowany, ok. 44 KB po gzip, plus `46-uwagi.js`) w tym samym
pakiecie co HQ, a eksport robi ffmpeg, który już jest w kontenerze.

- **Oś magnetyczna (jak w CapCut):** każda zmiana klipów (usunięcie, wstawienie, przycięcie krawędzi, tempo, długość
  obrazu, przestawienie) przelicza resztę osi: napisy, uwagi i bloki typografii (z czasami słów) idą za materiałem,
  z którego pochodzą (czas źródła klipu),
  a muzyka i lektor przesuwają się o wycięty albo wstawiony czas; przy przestawieniu napis jedzie z klipem, a audio stoi.
  Ta sama reguła działa u Wideografa (`edytor.remap_times` w `projekt.py usun` i `dodaj-klip --pozycja`), więc edycje
  człowieka i agenta nie rozjeżdżają napisów. Testy: `tests/test_edytor_os.py` (te same przypadki w przeglądarce i w Pythonie).
- **Strefy platform (tylko podgląd):** w kadrze pionowym podgląd zaznacza na czerwono miejsca, które zasłania
  interfejs TikToka, Reels albo Shorts (góra: zakładki i nazwa konta, dół: opis, konto i dźwięk, boki: przyciski);
  platformę albo **Wył.** wybierasz w **Format** (zapamiętane w tej przeglądarce). Tekst, który w nie wchodzi, ma
  czerwoną ramkę, a panel tekstu i napisów mówi, pod co wchodzi. Strefy nie trafiają do eksportu ani do kadru dla
  agenta. Liczby (ułamki kadru 1080×1920, przegląd 2026): TikTok 130/484/44/140 px (góra/dół/lewo/prawo), Shorts
  180/390/60/120 px, Reels według zalecenia Meta 14% / 35% / 6%; te same liczby ma kontrola Wideografa
  (`wideo_lib.STREFY_UI`: arkusz `qa_wideo.py`, `pomiar.py`). Nowy tekst i napisy w kadrze pionowym startują
  na wysokości 0,68 i z szerokością 74% (nad opisem, obok przycisków), tak samo u Wideografa (`projekt.py dodaj-tekst` i `napisy`). Test: `tests/test_edytor_strefy.py`.
- **Podgląd** gra w przeglądarce z plików pobranych raz (blob), bez serwera w pętli. Dwa elementy `<video>` na zmianę:
  następny klip czeka przewinięty na swój początek, więc przejścia są płynne. Miniatury osi czasu robi przeglądarka
  (jedna kanwa na źródło), a muzyka na osi ma falę dźwięku w skali dB (szczyty liczone raz na plik, dekodowanie
  w 8 kHz; −48 dBFS = cisza, bez wyrównania do najgłośniejszego miejsca, więc cichy fragment wygląda cicho).
- **Linia głośności (pomysł z OpenCut):** żółta linia na klipie wideo i na muzyce; przeciągnięcie w górę albo w dół
  zmienia głośność (góra +6 dB, 0 dB na 5/6 wysokości, przyciąga do 0 dB, sam dół = cisza), cały gest to jeden krok
  cofania. Na telefonie linię przeciąga się po zaznaczeniu klipu. W projekcie głośność zostaje liniowa (0–2), jak
  w eksporcie (`volume=`); etykieta na osi i panel pokazują ją w dB. Test: `tests/test_edytor_glosnosc.py`.
- **Wygląd jak w CapCut:** grafitowe tło, jeden akcent (cyjan: **Eksportuj**, aktywne narzędzie, zaznaczenie), krój
  systemowy (SF Pro na iPhonie i Macu, Segoe UI na Windows, Roboto na Androidzie) z Inter jako zapasem
  (`hq/web/fonts/`, OFL), ikony SVG jednym stylem linii zamiast emoji, czas `00:05.20`. Na osi: miniatury klipu w
  zaokrąglonym pasku z białą ramką zaznaczenia, fala dźwięku na morskim tle, tekst pomarańczowy, napisy ciemniejszy
  pomarańcz, cienki biały wskaźnik. Komunikaty to pływająca „pigułka” pod paskiem, bez przesuwania układu. Edytor
  i okno **◐ Animacja** nie biorą wyglądu z motywu dashboardu: „tarcza” w `style.css` cofa to, co motyw Fosfor
  wymusza (`!important` na zaokrągleniach i tle pól, poświata tekstu, wyłączone animacje).
- **Napisy** rysuje jedna funkcja na kanwie: w podglądzie i przy eksporcie (PNG na napis nakładany przez ffmpeg),
  więc plik wygląda jak podgląd, łącznie z krojem. **Kroje** napisów i typografii: 68 rodzin OFL (lista w
  `scripts/kroje.py`, m.in. Montserrat, Poppins, Inter, Kanit, Anton, Bebas Neue, Teko, Titan One, Nunito, Playfair
  Display, Bodoni Moda, Lobster, Dancing Script, Bangers, Bungee, Monoton, Press Start 2P, Rubik Bubbles, Space Mono;
  latin + latin-ext, a test czyta mapę znaków każdego pliku i sprawdza „ąćęłńóśźż”; kroje bez polskich znaków albo
  bez licencji OFL odpadają przy dodawaniu) leżą lokalnie w `hq/web/fonts/kroje/` (`kroje.css`, sumy SHA-256
  w `sumy.json`, wersje w `scripts/kroje.py`; `kroje.py sprawdz` w testach). Każdy jest do wyboru w panelu tekstu
  (`ED_FONTS` w `44-napisy.js`: 70 pozycji z dwoma systemowymi) i w panelu słowa typografii (`TYPO_KROJE`), w obu
  przewijanym polem z nagłówkami grup (systemowe, mocne, wąskie, okrągłe, szeryfowe, odręczne, ozdobne, techniczne)
  i nazwą pisaną danym krojem; pole samo przewija się do wybranego kroju. Lista napisów zna grubości plików
  (pogrubiony i zwykły), więc krój z jedną grubością nie jest sztucznie pogrubiany. Krój wczytuje się razem
  z tekstem napisu (`fontLoad`), więc polskie znaki nie spadają na krój zastępczy; render agenta wstawia te same
  pliki jako data: URL (`edytor.kroje_css`), tylko kroje użyte w projekcie (`projekt.strona` liczy je funkcją
  rysującą; wszystkie to kilka MB i sekunda dłuższy start), bez Google Fonts.
- **Typografia** jak z montażu (słowo po słowie: różne wielkości, kroje, kolory, głębia, skos, perspektywa 3D): plan
  w projekcie (`typo`: motyw, akcent, paleta i bloki z układem, kotwicą, obrotem, perspektywą, warstwą, wejściem i wyjściem;
  słowa z czasem, wagą 0–3, linią, głębią, krojem, kolorem, stylem i znacznikiem płytki) rysuje jeden renderer
  `hq/web/src/48-typografia.js` w podglądzie, przy eksporcie i w renderze Wideografa. Trzynaście stylów filmu (motywów:
  `czysty` domyślny, `kino`, `ulica`, `energia`, `elegancki`, `podcast`, `vlog`, `komiks`, `magazyn`, `tech`,
  `nowoczesny`, `retro`, `neon`); styl to kroje, styl słów i uderzenia (`wypelnij`, `kontur`, `3d`, `blask`, `tlo`
  albo `obrys`: gruby obrys pod literą, czarny przy jasnym słowie, biały przy ciemnym), wejście, wyjście i skos.
  Kolory mocnych słów to **paleta z kadru** (`typo.paleta`, dwa akcenty, które `typografia.py` dobiera
  z kontrastu z barwami sceny, np. niebieskie niebo → ciemna czerwień i złoto); akcentem bez palety jest kolor
  motywu, a kolor marki (`akcent`) wygrywa z obydwoma. Słowo w stylu `tlo` ma płytkę w swoim kolorze z czarnym albo
  białym napisem (kontrast); słowo ze znacznikiem `plyta` (kolor słabo odcina się od tła) dostaje ją samo, chyba że
  styl filmu daje mu obrys. Styl `blask` ciemnego koloru ma jasny rdzeń (neon nie gaśnie). Blok wypełnia część swojej szerokości zależnie od najmocniejszego słowa. Plan układa Wideograf (`typografia.py plan`, reżyser z reguł: mowa, głośność słów, pauzy,
  interpunkcja, cięcia ujęć) i poprawia według znaczenia (`typografia.py popraw`); serwer sprawdza go
  (`edytor.normalize_typo`). Przy eksporcie przeglądarka rysuje klatkę tylko tam, gdzie obraz warstwy się zmienia
  (`typoOdcinki`), wysyła je jako WebP (PNG, gdy przeglądarka nie zna WebP) razem z pustą klatką w tym samym formacie
  (demuxer `concat` dekoduje całą listę kodekiem pierwszego pliku, więc serwer odrzuca mieszankę PNG i WebP), a ffmpeg
  nakłada dwie warstwy pod zwykłymi napisami: „za osobą” (`tyl`) i przednią.
- **Edycja typografii:** pas **Typografia** nad osią (blok przed osobą niebieski, za osobą fioletowy, słowa pogrubione
  według wagi). Klik w blok na osi albo na podglądzie otwiera panel (na telefonie arkusz): słowa jako żetony
  (tekst, waga, kolor z powrotem do motywu, krój z siatki albo „Auto” z motywu, styl, głębia, wielkie litery, skala,
  linia) i blok (układ; „Za osobą” przestawia blok na warstwę `tyl`, rozmiar, szerokość, obrót, perspektywa 3D,
  wejście słów, wyjście). Blok `tyl` bez policzonej sylwetki ma ostrzeżenie i przycisk prośby do Wideografa
  (`typografia.py sylwetki`; `typografia.py plan` nie nadpisuje planu poprawionego w edytorze bez `--nowy`).
  Na podglądzie blok przeciąga się z przyciąganiem do środka kadru; na osi zmienia się jego czas (lewa krawędź
  zostawia słowa przy ich czasie w filmie). **Tnij** dzieli blok na słowie pod wskaźnikiem, jest też **Połącz
  z następnym**, **Duplikuj** i **Usuń**; wszystko to jeden krok cofania. Panel **Napisy** ma sekcję typografii:
  **Styl filmu** (karty 13 stylów: blok tego filmu z uderzeniem narysowany tym samym rendererem na pasie bieżącej
  klatki podglądu; klik zmienia motyw, układ, kolory i poprawki zostają; `TypoStyle` w `45-edytor.js`),
  **paleta z filmu** (zmiana koloru palety przenosi na nowy kolor wszystkie słowa w starym, tak jak
  `typografia.py popraw` z `"paleta"`), akcent, nowy blok, usunięcie planu albo prośba do Wideografa o plan.
  Kolory palety stoją też pierwsze przy kolorze słowa. Przycięcie, usunięcie, tempo
  i przestawienie klipów przesuwają bloki i czasy słów razem z materiałem (`typoNaOsi` w `remapTimes`
  i `edytor.remap_times`; test: `tests/test_edytor_os.py`).
- **Napis za osobą** (głębia jak z montażu: osoba przed słowem): Wideograf liczy maską MODNet (`maska.py`) sylwetkę
  osoby klatka po klatce dla bloków warstwy `tyl` i zapisuje ją obok filmu (`<film>.maska/`: PNG z kanałem alfa
  i `indeks.json` z kluczem osi). Podgląd pobiera indeks (`GET /edit/maska`) i rysuje: warstwa `tyl` → osoba z bieżącej
  klatki filmu wycięta sylwetką → warstwa przednia; eksport robi to samo w ffmpeg (`edytor.maska_concat`, `alphamerge`).
  Po przewinięciu podgląd rysuje osobę jeszcze raz z nowej klatki (zdarzenie `seeked`), a w strefach platformy
  przyciemnia ją jak resztę wideo.
  Klucz osi (klipy, przycięcie, tempo, kadr; `edytor.maska_klucz` = `maskaKlucz` w `48-typografia.js`) pilnuje, żeby
  po zmianie klipów nie użyć starych sylwetek: wtedy napis jest po prostu widoczny w całości.
- **Projekt** zapisuje się sam (co ~1 s) jako `<film>.edycja.json` obok filmu: klipy (`src`, `in`, `out`, `speed`,
  `volume`, `muted`, `fit`, `transition`), napisy, muzyka i typografia (`typo`). Po ponownym otwarciu edycja jest tam, gdzie była.
- **Eksport** (`POST /edit/export`): serwer sprawdza projekt (ścieżki tylko z katalogów floty, limity długości
  i liczby elementów), składa jeden przebieg ffmpeg (klipy → concat albo xfade przy przejściach → nakładki → miks
  z limiterem), H.264 + AAC,
  `+faststart`. Jedno zadanie naraz, postęp z `-progress`, przerwanie zabija proces. Plik powstaje jako `.part`
  i dopiero gotowy dostaje nazwę `film-edycja[-N].mp4`: nic nie jest nadpisywane.
  Kadr ma krótszy bok najwyżej 1080 px przy proporcjach źródła (nagranie 4K z iPhone'a 2160×3840 → 1080×1920;
  `edytor.kadr_eksportu` = `edKadr` w `45-edytor.js`, tak samo `projekt.py`): platformy i tak pokazują najwyżej 1080p,
  a 4K z warstwami typografii i maską nie mieściło się w pamięci kontenera. Warstwy z klatek (typografia, maska,
  karaoke) zmieniają format przed filtrem `fps`, nie po nim, bo `fps` powtarza długą klatkę od razu wiele razy
  i każda powtórka po konwersji to nowa pełna klatka w pamięci (pomiar 1080×1920 60 kl/s, 10 s, 3 warstwy: 1,1 GB stałe
  zamiast rosnących do OOM).
- **Klip o innych proporcjach niż kadr** (np. poziome nagranie w pionie 9:16) ma trzy tryby: **Pasy** (całe ujęcie,
  czarne pasy), **Rozmyte tło** (całe ujęcie na rozmytym, przyciemnionym tle z niego samego; `fit: "blur"`) i
  **Wypełnij** (przycięcie). Wybór jest w ustawieniach klipu, a w **Format** dla wszystkich takich klipów naraz.
  Zmiana formatu na inny niż materiał daje klipom domyślnie rozmyte tło (pasy wybrane wcześniej zostają), tak samo nowy
  klip o innych proporcjach. Film ma zostać poziomy? Format **16:9** albo **Oryginał**: wtedy poziomy klip wypełnia
  kadr bez tła i pasów, a panel Format mówi to wprost. Podgląd rysuje tło na małej kanwie pod wideo (rozmycie w CSS),
  eksport tym samym przepisem co `film.py --tryb rozmyte` (`edytor.blur_filter`: `boxblur` + `eq`), Wideograf:
  `projekt.py dodaj-klip|kadr --rozmyte|--dopasuj|--wypelnij`.
- **Szybkie cięcie** (jak w CapCut): w ustawieniach klipu **Usuń z lewej** (od początku klipu do wskaźnika,
  klawisz Q) i **Usuń z prawej** (od wskaźnika do końca klipu, W), a **Podziel na równe części** tnie klip na 2, 3
  albo 4 kawałki (np. 7,5 s → 3 × 2,5 s), więc środek wycinasz jednym usunięciem. Reszta osi się dosuwa razem
  z napisami, typografią, uwagami i muzyką (`remapTimes`), przejście zostaje na tym samym cięciu (ostatnia część).
  Logika bez Reacta: `hq/web/src/47-ciecie.js` (testy w node: `tests/test_edytor_ciecie.py`). Wideograf:
  `projekt.py tnij <film> <id> --w S|--czesci N` i `projekt.py wytnij <film> --od S --do S` (odcinek osi przez klipy).
- **Przejścia między klipami** (jak w CapCut): na każdym cięciu osi jest mały kwadrat; klik otwiera panel z 16
  przejściami (Przenikanie, Przez czerń, Przez biel, Rozmycie, Przybliżenie, Piksele, Przesuń w lewo/prawo/górę/dół,
  Najazd z prawej/lewej, Zasłona w lewo/prawo, Miękka zasłona, Koło), każde z animowaną miniaturą, suwakiem długości
  (0,1–3 s), **Podgląd** (odtwarza samo cięcie) i **Do wszystkich cięć**. Przejście leży na środku cięcia i **nie skraca
  filmu**: klip A gra dalej za cięciem (materiał za przycięciem, a gdy go brak, ostatnia klatka), klip B zaczyna przed
  cięciem, więc napisy, muzyka i uwagi zostają na miejscu. Długość to parzysta liczba klatek, najwyżej tyle, ile trwa
  krótszy z dwóch klipów (`przejsciaOsi` w `49-przejscia.js` = `edytor.przejscia_osi`); okno przejścia widać na osi jako
  paski. Zapis: `transition: {type, dur}` w klipie przed cięciem; Tnij zostawia przejście na prawej części, wycinanie
  pauz na ostatnim kawałku. Eksport: `xfade` i `acrossfade` w ffmpeg na wydłużonych odcinkach (dźwięk przenika się
  razem z obrazem), „Rozmycie” to przenikanie z rozmyciem Gaussa rosnącym do cięcia (`sendcmd` + `gblur`).
  Podgląd ma dwie warstwy (klip i następny) stylowane przez `przejscieStyl` tymi samymi wzorami co `xfade`
  (krycie, przesunięcie, maska, rozmycie, piksele na kanwie), a test porównuje kolory podglądu z klatkami z ffmpeg
  (`tests/test_edytor_przejscia.py`). Wideograf: `projekt.py przejscie <film> <id>|--wszystkie [--typ] [--dlugosc] [--usun]`.
- **Kadr:** klip w trybie „Wypełnij” (np. pion 9:16 z poziomego nagrania) ma w ustawieniach suwaki **Kadr: poziomo**,
  **Kadr: pionowo** i **Przybliżenie** (1–3×, punch-in). Zapisują się w klipie jako `fx`, `fy`, `zoom`; eksport tnie
  ten sam fragment (`crop` z punktem skupienia w ffmpeg), który pokazuje podgląd (CSS `object-position` + `scale`).
- **Napisy:** zakładka „Napisy” (na telefonie przycisk w dolnym pasku) rozpoznaje mowę klipów na serwerze
  (`jarvo-stt`, Parakeet, bez internetu) i wstawia napisy na ścieżkę tekstu, zgrane z cięciami i tempem. Wynik zapisuje
  się obok źródła jako `<nazwa>.auto.srt`, więc drugi raz wczytuje się od razu. Można też wczytać gotowy `.srt`
  z katalogu filmu. Styl, położenie, kolor i rozmiar zmieniają się dla wszystkich napisów naraz; pojedynczy napis
  poprawiasz na osi czasu.
- **Mowa, pauzy i wtrącenia:** zakładka „Mowa” (na telefonie w dolnym pasku). **Wykryj mowę i pauzy** robi dwie rzeczy
  na serwerze: `silencedetect` w ffmpeg wyznacza dokładnie ciszę, a `jarvo-stt --json` podaje czas każdego słowa.
  Na osi pojawia się ścieżka mowy: szare paski z wypowiedziami, **czerwone** znaczniki pauz (dłuższych niż suwak,
  domyślnie 0,6 s) i **pomarańczowe** „yyy”/„eee”. Znacznik klikasz: Wytnij, Zostaw albo Odsłuchaj; albo wycinasz
  wszystkie naraz. Cięcia to zwykłe cięcia klipów (zostaje 0,12 s oddechu), napisy i muzyka przesuwają się razem
  z nimi, całość cofa się jednym Ctrl+Z. Wynik analizy leży obok źródła jako `<nazwa>.mowa.json` (i `.auto.srt`):
  następnym razem wczytuje się sam, widzi go też Wideograf. Bez `jarvo-stt` działa samo wykrywanie pauz.
- **Napisy zgrane ze słowami:** linie układane są ze słów już po cięciach (nowa linia po pauzie, końcu zdania albo
  32 znakach), bez wtrąceń.
- **Karaoke:** napisy ze słów (automatyczne, nie z pliku `.srt`) pamiętają czas każdego słowa (`words`, liczony od
  początku napisu, więc przesunięty napis zabiera go ze sobą). Pole **Karaoke** w zakładce „Napisy” podświetla słowo
  wypowiadane w danej chwili wybranym kolorem (`hl`, domyślnie żółty). Poprawka literówki (ta sama liczba słów) zostawia
  karaoke, inna liczba słów wyłącza je tylko w tej linii. Eksport: obraz PNG na każde słowo, a wszystkie napisy karaoke
  idą do ffmpeg jako **jedna** warstwa (demuxer `concat`), więc pamięć nie rośnie z długością filmu.
- **Każda przeglądarka:** gdy przeglądarka nie odtwarza kodeka filmu (np. Chromium bez H.264, ProRes), edytor sam
  prosi serwer o kopię podglądową WebM (VP9, do 540 p, klatka kluczowa co 0,5 s dla szybkiego przewijania; raz na
  plik, w `state/edytor/proxy/`, sprząta się po 7 dniach). Eksport zawsze bierze oryginał w pełnej jakości.
- **Wspólny projekt z Wideografem:** „Poproś agenta” każe Wideografowi pracować na tym samym `*.edycja.json`
  poleceniem `projekt.py` (`pokaz`, `dodaj-audio`, `dodaj-tekst`, `dodaj-klip`, `kadr`, `napisy`, `przejscie`, `tnij`, `wytnij`, `usun`, `uwaga`,
  `sprawdz`, `render`). `render` używa tego samego silnika co „Eksportuj” (`edytor.py` kopiowany przy buildzie obok skryptu),
  a napisy i typografię rysują te same funkcje (`hq/web/src/44-napisy.js`, `48-typografia.js`) w przeglądarce bez
  okna, więc plik od agenta wygląda jak eksport z edytora. Typografię na tym samym projekcie układa `typografia.py`
  (`plan`, `pokaz`, `popraw`, `arkusz`, `usun`). Edytor co 3 s (gdy karta jest widoczna) sprawdza, czy projekt zmienił się z zewnątrz: bez Twoich niezapisanych zmian
  wczytuje wersję agenta sam (jako zwykły krok, ↶ ją cofa), a przy kolizji pyta: „Wczytaj jego wersję” albo
  „Zostaw moją”. Zapis nigdy nie nadpisuje po cichu cudzej zmiany (serwer odrzuca go jako nieaktualny).
- **Uwagi na osi i kadr do Wideografa** (pomysł z Remocn Studio, MIT): w panelu „Poproś agenta” **📌 Uwaga w 0:04.2**
  przypina prośbę do chwili filmu (żółta pinezka na ścieżce „Uwagi” nad osią; klik przewija do tego miejsca), a
  **📷 Kadr** pozwala zaznaczyć prostokąt na podglądzie (klik = cały kadr). Kadr składa się jak podgląd: klatka w tym
  samym kadrze (`fitBox` = `applyFit`) i napisy tą samą funkcją `drawText`; JPEG do 1280 px trafia do inboxu, a uwaga
  albo prośba ma do niego ścieżkę. **Wyślij** wysyła prośbę i wszystkie otwarte uwagi naraz, z czasem osi i kadrami
  (pierwsze 4 jako obrazy dla modelu, reszta jako ścieżki do `vision_analyze`). Uwagi są w projekcie (`notes`), więc
  przetrwają zamknięcie edytora i przesuwają się razem z treścią przy wycinaniu pauz. Wideograf zamyka każdą
  `projekt.py uwaga <film> <id> --zrobione "co zmienił"` albo `--odrzuc "dlaczego"`: pinezka zmienia się w zielone ✓
  z jego opisem, a `render` ostrzega o otwartych. Logika bez Reacta: `hq/web/src/46-uwagi.js` (testy w node).
- **Telefon (do 860 px):** układ jak w CapCut: podgląd na górze, pod nim czas, odtwarzanie i cofnij/ponów, oś czasu
  przewijana palcem pod stałym wskaźnikiem na środku (dwa palce: przybliżenie), a na dole pasek **Edytuj · Audio ·
  Tekst · Napisy · Format**. Narzędzie otwiera panel od dołu; dotknięcie klipu, napisu albo muzyki na osi otwiera
  jego ustawienia, uchwyty do przycinania pojawiają się na zaznaczonym elemencie.
- Plan dalszej rozbudowy (szybkie cięcie, audio, naklejki, animacje klipów) i stan kroków: [EDYTOR-PLAN.md](EDYTOR-PLAN.md).
- Logika serwera: `hq/plugin/edytor.py` (bez FastAPI), testy: `tests/test_edytor.py` (także prawdziwy eksport ffmpeg)
  i `tests/test_edytor_przejscia.py` (przejścia: oś, eksport, podgląd = film).

## 2b. Animacja HTML: podgląd na żywo i parametry

Animację z kodu (kontrakt HTML Wideografa: `window.__seek(t)`, `__ready`, `__W/__H/__DUR`) da się obejrzeć i stroić
bez renderowania MP4 (pomysł z Remocn Studio, MIT: panel właściwości i podgląd na żywo). Przycisk **◐ Animacja** jest
przy każdym pliku HTML, który ma obok `parametry.json` albo `__seek` w kodzie (wyniki agenta i linki w czacie).

- **Podgląd** to ta sama strona z serwera `:9120` (link z tokenem na katalog animacji, jak **▶ Odpal**), ale z
  `?render=1&jarvo-podglad=1`: strona nie gra sama, a serwer dokleja do niej mostek `/_jarvo/most.js`. Strona ma
  nieprzezroczyste pochodzenie (CSP sandbox), więc HQ rozmawia z nią tylko przez `postMessage`: wysyła czas i wartości
  parametrów, mostek ustawia je (`window.__setParams(wartości)`, jeśli strona go ma, inaczej `Object.assign(window.__params, …)`),
  woła `__seek(t)` i odpowiada „klatka gotowa”. Przewijanie łączy żądania (najwyżej jedno w drodze, potem ostatnie
  czekające), więc suwak nie zatyka strony. Ramka ma natywny rozmiar animacji (`__W×__H`) przeskalowany do okna.
- **Sterowanie:** ▶/❚❚ i Spacja (pętla), suwak czasu, ←/→ klatka (1/30 s), Shift+←/→ sekunda, pole długości
  (z raportu pomiaru albo `__DUR` strony), Esc zamyka. Biblioteki z `/_lib/` (three, gsap) serwer `:9120` podaje z tego samego katalogu
  narzędzi co `html_wideo.py`, więc podgląd wygląda jak render.
- **Parametry** (kontrakt HTML, reguła 7): `parametry.json` obok strony ma listę `pola` z typami `liczba` (suwak
  min/max/krok), `kolor` (#RRGGBB), `tekst` (do 400 znaków), `przelacznik`, `wybor` (opcje) i `krzywa`
  (cubic-bezier z uchwytami do przeciągania i gotowymi krzywymi). Zmiana jest widoczna od razu w bieżącej klatce;
  zmienione pole ma ↺ z zapisaną wartością. **Zapisz parametry** zapisuje tylko wartości pól ze schematu (typy
  i zakresy sprawdza serwer, zapis atomowy); kod strony i reszta pliku zostają. Strona bez `window.__params`
  dostaje ostrzeżenie, że zmiany nie będą widoczne na żywo.
- **Pomiar:** okno czyta `pomiar.json` (`html_wideo.py pomiar`) i liczy jego aktualność tym samym odciskiem co
  Wideograf (`pomiar.py` w pluginie). Lista ustaleń (błędy, ostrzeżenia, wyjątki z powodem) przewija do chwili
  problemu. Zapis parametrów zmienia odcisk, więc raport od razu staje się nieaktualny: „gotowe” wymaga nowego pomiaru.
- **Poproś Wideografa** wysyła prośbę ze ścieżką strony, kursorem czasu i niezapisanymi zmianami („tempo: 1 → 1.25”)
  oraz poleceniem pomiaru i renderu. Odpowiedź widać w oknie.
- Logika serwera: `hq/plugin/animacja.py` (bez FastAPI), frontend: `hq/web/src/47-animacja.js`, testy:
  `tests/test_animacja.py`.

## 3. Bezpieczeństwo

- Wszystkie trasy pluginu są za logowaniem dashboardu (bez sesji: `401 unauthenticated`).
- Dashboard nasłuchuje tylko na IP Tailscale (`JARVO_BIND_IP`), hasło generuje bootstrap.
- Klucze API profili zostają na serwerze. Backend pluginu czyta je z `.env` profilu przy każdym wywołaniu.
- Podgląd plików tylko z `/opt/data/jarvo/{workspaces,missions,knowledge,inbox}` (inbox: pliki wysłane w czacie HQ),
  po rozwiązaniu symlinków.
  Pliki wysyłane z nagłówkiem `Content-Security-Policy: sandbox` i `nosniff`, HTML jako zwykły tekst:
  strona wygenerowana przez agenta nie wykona skryptu w sesji dashboardu.
- **▶ Odpal**: strona agenta idzie z osobnego portu 9120 (ten sam `JARVO_BIND_IP`), tylko pod adresem z losowym
  tokenem, który wydaje zalogowany dashboard albo agent (`scripts/jarvo_link.py`; wspólny plik
  `state/preview-links.json`, ważny 7 dni, przetrwa restart). Wykonawca karty działa z `HERMES_HOME` swojego profilu
  (`/opt/data/profiles/<agent>`), więc `hq_core` wylicza z niego korzeń danych (`/opt/data/jarvo`). Nagłówek `CSP: sandbox` bez
  `allow-same-origin` daje stronie nieprzezroczyste pochodzenie: jej skrypty działają, ale nie czytają ciasteczek
  i nie wyślą ich do dashboardu. Nowa karta nie ma `window.opener`. Pliki ukryte, `..` i symlinki na zewnątrz: 404.
  Bez tokenu serwer podaje tylko mostek `/_jarvo/most.js` i biblioteki `/_lib/…` (otwarte pakiety npm z
  `narzedzia/node/node_modules`, bez plików ukrytych i symlinków na zewnątrz). Mostek trafia do strony tylko z
  `?jarvo-podglad=1` (okno **◐ Animacja**) i przyjmuje wiadomości wyłącznie od okna nadrzędnego.
- **📱 Ekran telefonu**: ws-scrcpy nie ma logowania, więc działa tylko w sieci floty (bez portów); jedyne wejście to
  proxy w pluginie na porcie 9122 (ten sam `JARVO_BIND_IP`). Link `/<token>/` wydaje zalogowany dashboard albo agent
  (`scripts/jarvo_link.py --android`; ten sam plik linków, znacznik `@android-ekran`, ważny 12 h). Wejście z tokenem
  zamienia go na ciasteczko `HttpOnly` (`SameSite=Lax`) i przekierowuje na `/`; każde żądanie bez ważnego ciasteczka
  dostaje 403. Zwykłe żądania idą do ws-scrcpy z `Connection: close`, więc każde następne przechodzi kontrolę od nowa;
  WebSocket po kontroli to czysty strumień. Ciasteczka przeglądarki (także dashboardu, bo ciasteczka nie znają portów)
  nie idą dalej. Token ekranu nie otwiera niczego na `:9120` i odwrotnie.
- **Pokaż w folderze**: dashboard zapisuje tylko prośbę ze ścieżką (`state/reveal-request`); `scripts/updater.py`
  na hoście sprawdza ją ponownie (tylko `jarvo/{workspaces,missions,knowledge,inbox}`) i woła `explorer.exe /select,…`.
  Prośby odbiera co 2 s, gdy jest Eksplorator (WSL); bez niego (VPS, Linux) co 6 s, bo czekają tylko „sprawdź” i „aktualizuj”.
- Odczyt kanbana i transkrypcji w trybie SQLite `mode=ro`. HQ zapisuje tylko: mapę sesji czatu
  (`/opt/data/jarvo/state/hq-sessions.json`), pliki z czatu (`inbox/<data>/`), linki podglądu
  (`state/preview-links.json`, `state/preview.json`), prośby do pomocnika hosta (`state/reveal-request`,
  `state/update-request`), pliki edytora filmów (projekt `*.edycja.json`, analiza `*.mowa.json` i `*.auto.srt`,
  nowe wersje filmu obok oryginału, pliki tymczasowe w `state/edytor/`), wartości pól w `parametry.json` animacji
  (**◐ Animacja**) i blok wspólnych kluczy w `.env` agentów
  (`share_keys.py`). Na tablicy HQ może tylko ponowić kartę porzuconą po błędach (`hermes kanban unblock`);
  resztę zmian robią agenci przez swoje narzędzia.
- Edytor: każda ścieżka z projektu przechodzi przez to samo sprawdzenie co podgląd plików; ffmpeg dostaje argumenty
  listą (bez powłoki), napisy tylko jako poprawne PNG do 12 MB.

## 4. Wieża Jarvo (wygląd)

Tytuł „Jarvo HQ”, stan połączenia, liczniki tablicy (w toku, ocena, blokady, kolejka, zrobione dziś) i
przycisk „Decyzje” siedzą w górnym pasku dashboardu Hermesa (kontekst strony wczytany z modułu dashboardu);
gdy go nie ma (np. tryb demo), HQ pokazuje własny pasek nad wieżą. Scena dopasowuje się do wysokości
okna: cała wieża mieści się nad czatem, a nadmiar szerokości wypełnia miasto po bokach.

Scena to **przekrój bazy-wieżowca w pixel arcie**, nocą, jak model z klocków przecięty na pół: płaskie
cięcie konstrukcji, a pokoje mają głębię (tylna ściana, podłoga w perspektywie, meble). Rysunek powstaje
w kodzie (`hq/web/src/20-art.js`) na siatce 400 pikseli logicznych i skaluje się w SVG bez rozmycia.

- **Dach:** neon „Jarvo”, antena z migającym światłem, talerz, zbiornik na wodę.
- **Mostek dowodzenia** (`bridge`): **Jarvo jako szef w garniturze** (postać 2× większa od załogi) za
  pulpitem dowodzenia, fotel dyrektorski, okno na miasto, ekran „Tablica floty” (liczniki kanbana na żywo),
  panel „Załoga” z lampką statusu każdego agenta, robot-monolit Jarvo (pracuje, gdy flota pracuje).
- **Piętra załogi:** po dwa pokoje na piętro wokół szybu windy; winda jeździ, gdy ktoś pracuje. Przy
  nieparzystej liczbie agentów wolne miejsce zajmuje magazyn. Nowi agenci dokładają piętra.
- **Maszynownia** (piwnica pod ulicą): szafy serwerowe i rdzeń zasilania; zielony „GATEWAY ONLINE”,
  czerwony, gdy HQ traci połączenie z flotą.

Pokój przypisuje `hq_room` w `fleet.yaml`, a krótką nazwę na szyldzie `hq_short`:

| `hq_room` | Wystrój | Postać |
|---|---|---|
| `bridge` | jak wyżej | szef Jarvo: czarny garnitur, biała koszula, czerwony krawat |
| `study` | regał z książkami, tablica dowodów z czerwonymi nitkami, zegar, globus, biurko z lampą bankierską | detektyw w kaszkiecie i szaliku (lupa przy pracy) |
| `devlab` | szafa serwerowa z diodami, tablica z makietą, neon `</>`, dwa monitory z kodem, kubek z parą | programista w bluzie i słuchawkach, tyłem przy monitorach |
| `atelier` | turkusowe tło fotograficzne, softbox, kamera z lampką REC, sztaluga z obrazem, plakat, klaps | artystka w berecie i koszulce w paski (paleta przy pracy) |
| `filmstudio` | zielone tło z softboxem, kamera na statywie z lampką REC, stół montażowy z monitorem 9:16 i osią czasu (głowica jedzie przy pracy), klaps, szpula i napis REC na ścianie | wideograf w czerwonej czapce z daszkiem i kamizelce (kamera przy pracy) |
| `workshop` | tablica z narzędziami, stół z imadłem i ramieniem robota, skrzynie (liczba = kolejka kart), beczka | mechanik w kasku i ogrodniczkach, tyłem przy stole |
| `office` | Sala operacyjna (Ads), też pokój domyślny dla nowych agentów: ściana ekranów z wynikami kampanii (słupki wariantów, linia wydatków pod czerwoną linią koperty, tablica ROAS), biurko z dwoma monitorami, czerwony STOP, roślinka | postać w koszuli i niebieskim krawacie, tyłem przy monitorach |
| `radar` | Radar sprzedaży (Łowca leadów): ekran radaru z pierścieniami (wiązka i migające cele przy pracy), mapa Polski z pinezkami firm, neon LEADY, biurko z listą leadów i słupkami oceny, stos kart (kolejka), telefon, roślinka | łowca w pomarańczowej czapce i kamizelce, ze słuchawkami, tyłem przy monitorach |
| `apps` | Pracownia aplikacji (Twórca aplikacji): tablica z makietami trzech ekranów (przy pracy ekrany się zmieniają), neon APP z pięcioma gwiazdkami ocen, regał z telefonami testowymi (lampki ładowania), biurko z monitorem z kodem, telefon na statywie z kodem QR do podglądu (zielona linia skanu przy pracy), stos kart (kolejka), roślinka | twórca w fioletowej bluzie i słuchawkach, tyłem przy biurku |

Stan agenta zmienia pokój: światło (pokój przygasa, gdy agent jest wolny), pozę (praca, trzymana karta
przy ocenie, uniesiona ręka i „!” przy blokadzie, „Z z z”, gdy śpi) i rekwizyty (monitory, lampa, ramię
robota, nagrywanie, hologram na pulpicie szefa). Animacje są skokowe jak w grach (kilka klatek) i
wyłączają się przy `prefers-reduced-motion`. Na wąskim ekranie wieżę przesuwa się w bok palcem.

**Nowy pokój:** dodaj klucz w `ROOMS` i funkcję wnętrza (`ROOM_DRAW`) w `hq/web/src/20-art.js`, wygląd
postaci w `LOOKS`, wpisz klucz do `HQ_ROOMS` w `scripts/fleetlib.py` (walidator pilnuje zgodności)
i ustaw `hq_room` agenta.

## 5. Motyw „Fosfor” (wygląd całego dashboardu)

Cały dashboard (menu, górny pasek, czat, Jarvo HQ) wygląda jak terminal CRT z 1982: czcionki VT323 i IBM Plex
Mono, linie skanowania, numerowane menu, podświetlenie w negatywie. Wieża zostaje w swoich kolorach.

- **Jeden kolor → cały wygląd.** `scripts/install_themes.py` liczy z niego odcienie, tło, ramki i poświatę,
  a z `branding/fosfor/theme.css` składa motywy Hermesa w `<HERMES_HOME>/dashboard-themes/`. Motyw dwukolorowy
  podaje dodatkowo `frame`, `fill`, `bg`, `muted`, `line` (i opcjonalnie `accent`).
- **Zmiana koloru:** przełącznik motywów w lewym dolnym rogu: domyślny **Jarvo · biało-czerwony** (dwukolorowy)
  oraz Fosfor: błękit, bursztyn, zieleń, biel. Własny kolor: dopisz linię w `branding/fosfor/palettes.yaml`
  i wdroż. Wybór zrobiony w dashboardzie przetrwa wdrożenia.
- Kolory terminala czatu idą z motywu (łatka w `branding/patch_dashboard.py`), skórka TUI jest biało-czerwona
  (`branding/skin-jarvo.yaml`).
- **Strona logowania** (`/login`, przed dashboardem) ma markę Jarvo: logo, biel i czerwień, VT323 / IBM Plex Mono,
  linie CRT i polskie napisy (łatka `patch_login` w `branding/patch_dashboard.py`). Fonty kopiuje do publicznego
  `/fonts/` dashboardu, bo pliki pluginu HQ są za logowaniem. Stopka menu: „Jarvo · Hermes Agent”.

## 6. Język: polski i angielski

Dashboard ma pełny polski (tłumaczenie `branding/i18n/pl.json`, ~750 tekstów i całe menu) i jest domyślnie po
polsku. Język zmienia przełącznik w lewym dolnym rogu (**POLSKI** / **EN** / …). Jarvo HQ idzie za nim: po polsku
albo po angielsku (każdy inny język = angielskie HQ); nazwy pokoi, role i opisy agentów po angielsku są w
`fleet.yaml` (`en:`). Tłumaczenie wstrzykuje `branding/patch_dashboard.py` przy budowie obrazu (brakujący klucz =
tekst angielski), więc zmiana `branding/` przebudowuje tylko ostatnią warstwę obrazu (sekundy, ta sama wersja
Hermesa). Etykiety wpisane w kod po angielsku na stronie Sesje (liczniki, „Import sessions”) tłumaczy łatka
(`patch_sessions`, klucze `sessions.*` w `pl.json`); inne takie etykiety Hermesa zostają po angielsku.

Agenci rozmawiają po polsku niezależnie od języka panelu (SOUL).

## 7. Rozwiązywanie problemów

| Objaw | Przyczyna i naprawa |
|---|---|
| brak zakładki BASE albo WIEDZA w menu | plugin nie jest włączony albo dashboard nie wstał po instalacji: `docker exec -u hermes jarvo-hermes /command/s6-svc -r /run/service/dashboard` |
| czat: „Profil … nie ma API_SERVER_KEY” | uruchom deploy ponownie (instalator generuje klucze) |
| czat: „Gateway odrzucił klucz” | klucz w `.env` profilu zmieniony bez restartu gatewaya: `hermes gateway restart` |
| czat: „No LLM provider configured” | profil nie ma `OPENROUTER_API_KEY` w `/srv/jarvo/secrets/<agent>.env` |
| pokój „Pracuje”, ale dymek „cisza…” | pracownik nie wysłał sygnału od 3 min; szczegóły w panelu, patrol zgłosi problem sam |
| agent podaje `localhost:8000` albo inny port z kontenera | taki adres nie działa w Twojej przeglądarce. Agenci mają to w zasadach; link do wyniku daje `python3 /opt/jarvo/repo/scripts/jarvo_link.py <plik>` (serwer podglądu :9120, 7 dni) |
| „▶ Odpal” otwiera pustą kartę / „nie można połączyć” | port 9120 nieopublikowany: kontener sprzed tej wersji, `bash scripts/local-up.sh` (lokalnie) albo `deploy.sh` go odtworzy |
| brak przycisku „📱 Ekran telefonu” | telefon testowy wyłączony: `jarvo android status`, włączenie `jarvo android on` (docs/MOBILE.md §5) |
| ekran telefonu: „Telefon testowy jest wyłączony” (503) | kontener `jarvo-android-ekran` nie działa: `jarvo android on`; pusta lista urządzeń w ws-scrcpy = Android jeszcze startuje (do 4 min) |
| brak „Pokaż w folderze”, jest „Kopiuj ścieżkę” | pomocnik hosta nie działa albo to nie WSL: `bash scripts/local-up.sh` (uruchamia `scripts/updater.py`) |
| `/api/plugins/jarvo-hq/health` | pokazuje, czy każdy profil ma klucz i czy gateway odpowiada na `/p/<agent>` |
