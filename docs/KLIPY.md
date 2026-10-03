# Clipmaker Wideografa: długie nagranie → edytowalne rolki (projekt)

> Stan: **zaakceptowany (2026-09-30), w budowie** (§6: kroki 1–4 gotowe). Właściciel: `jarvo-wideo`.
> Format: **9:16 domyślnie** (Reels, Shorts, TikTok), 16:9 na życzenie (`format` w `plan.json`, całość albo rolka).

Ktoś wrzuca długi materiał (podcast, webinar, live, vlog, 5–120 min). Wideograf go transkrybuje, rozumie, w którym
momencie co jest powiedziane, wybiera najlepsze fragmenty według jednego „master promptu” i robi z nich krótkie
rolki 9:16 (Reels, Shorts, TikTok) z napisami karaoke i hookiem. **Każda rolka to projekt edytora HQ**
(`klip-N.edycja.json`), a MP4 jest tylko jego renderem: otwierasz rolkę w edytorze i poprawiasz cięcia, kadr,
napisy, tytuł, muzykę, a eksport robi nową wersję.

---

## 1. Przepływ

```
  Ty: plik (czat HQ 📎 / Telegram) + „zrób rolki z tego”        (link: transkrypcja-filmu pobiera; YouTube z VPS bywa blokowany)
        │
        ▼
  ① klipy.py przygotuj <nagranie>            skrypt, 0 tokenów
       Parakeet → <nagranie>.mowa.json (ten sam plik co zakładka „Mowa” w edytorze: słowa z czasem, pauzy, wtrącenia)
       cięcia ujęć (kadry.py sceny), arkusze klatek co ~30 s, transkrypcja.txt z czasami, akapitami i oknami ~90 s
        │
        ▼
  ② Wideograf czyta transkrypcję według master promptu (skill clipmaker, references/master-prompt.md)
       ocena 0–100 każdego okna → kandydaci z najlepszych okien całego nagrania (2–3× więcej niż rolek)
       → ocena na 6 osiach → wybór N różnych tematów → plan.json → klipy.py sprawdz
       arkusze klatek (vision_analyze): ile osób, plansze; fx/fy tylko tam, gdzie kadr nie ma stać na twarzy
        │
        ▼
  ③ klipy.py zbuduj <nagranie> plan.json     skrypt, 0 tokenów
       dla każdej rolki: projekt 1080×1920 (segmenty ze źródła z granicą dosuniętą ze środka słowa do przerwy,
       kadr na twarzy z twarze.py (YuNet) albo z planu, cięcie pauz > 0,6 s i „yyy”,
       napisy karaoke ze słów, tytuł-hook na pierwsze sekundy, opcjonalnie muzyka) → render tym samym silnikiem
       co „Eksportuj” → klip-N-<slug>.mp4 + klip-N-<slug>.edycja.json
        │
        ▼
  ④ kontrola: qa_wideo.py + klatki kontrolne (kadr, napisy w strefie bezpiecznej) + obraz każdego cięcia
     (krytyka.py ciecia: klatki, fala, słowa; trzask i słowo przecięte) + krytyka według osi
        │
        ▼
  ⑤ oddanie: out/wideo/klipy/ (MP4 + projekty), KLIPY.md (tytuły, opisy, hashtagi, czasy w źródle, oceny)
     Ty: podgląd w HQ → ✎ Edytuj dowolną rolkę → Eksportuj; albo „popraw rolkę 3: krótszy start” do Wideografa
```

Podział pracy jak w reszcie floty: **model decyduje** (co jest ciekawe, gdzie hook, gdzie puenta, jaki kadr),
**skrypty wykonują** (transkrypcja, cięcie, napisy, render), więc tokeny idą tylko na wybór.

## 2. Master prompt: jak wybieramy fragmenty

Plik `skills/wideo/clipmaker/references/master-prompt.md`, czytany zawsze przed wyborem. Zawiera:

- **ocenę okien:** transkrypcja pocięta na okna ~90 s, każde dostaje ocenę 0–100 według testu 2 sekund (czy
  początek najlepszego momentu zatrzyma widza bez kontekstu), z całą skalą; kandydatów szukamy w najlepszych
  oknach całego nagrania, nie tylko z początku (za openshorts),
- **definicję dobrej rolki:** jedna myśl, zrozumiała bez reszty nagrania, 20–60 s (domyślnie 25–45 s),
  hook w pierwszych 1–3 s (teza, liczba, pytanie, kontrowersja, „nikt ci nie mówi, że…”), napięcie lub
  konkret w środku, puenta albo wniosek na końcu (nie urwane w pół zdania),
- **6 osi oceny 1–10:** hook, samodzielność (bez kontekstu), wartość (konkret, rada, liczba), emocja/energia
  mówcy, puenta, potencjał udostępnienia; do rolki tylko średnia ≥ 7 i hook ≥ 7,
- **zakazy:** start od „no i”, „tak jak mówiłem”, „wracając do”; fragmenty zależne od slajdu, którego nie widać
  (samodzielność naprawiamy wcześniejszym początkiem, nigdy ucięciem puenty); tytuł, który pasowałby do każdej
  rolki z nagrania (ma nazywać konkret tej rolki);
  wyrwanie z kontekstu zmieniające sens (reguła uczciwości: KLIPY.md podaje czas w źródle);
- **montaż dozwolony w rolce:** do 3 segmentów z tego samego wątku (np. pytanie z 12:40 + odpowiedź z 14:05),
  wycięte pauzy i wtrącenia; zawsze w kolejności, która nie zmienia sensu,
- **różnorodność:** N rolek = N różnych tematów/emocji, nie 3× ta sama teza; dwie rolki dzielą najwyżej ~20%
  materiału źródła (`klipy.py sprawdz` to liczy),
- **format wyjścia:** `plan.json` (schemat w §4), dla każdej rolki: tytuł-hook na ekran (≤ 6 słów), opis,
  3–5 hashtagów, uzasadnienie wyboru jednym zdaniem.

## 3. Rolka: jak wygląda (domyślny styl, wszystko edytowalne)

| Element | Domyślnie | W projekcie |
|---|---|---|
| format | 1080×1920, 30 fps (9:16); na życzenie 1920×1080 (16:9) | `canvas`; `format` w planie albo rolce |
| kadr | mówca z poziomego nagrania: przycięcie do pionu na twarzy (`twarze.py`, YuNet, 2 próbki/s: twarz na środku, oczy na ~1/3; mały ruch kadr ignoruje, nowa twarz albo duże przesunięcie potwierdzone przez ~1,5 s = nowe ujęcie z cięciem w przerwie między słowami) | klip `fit: cover` + `fx`, `fy` (0–1) i `zoom` (1–2) |
| rytm | wycięte pauzy > 0,6 s i „yyy” (zostaje 0,12 s oddechu); punch-in (zoom 1,15) na mocnym zdaniu | kolejne klipy z tego samego źródła |
| napisy | **karaoke**: 2–4 słowa w linii, aktywne słowo w kolorze akcentu, grube, z obrysem, w dolnej 1/3 poza strefą UI platform | **nowy** typ napisu: `words` + `hl` |
| hook | tytuł na górze przez pierwsze ~3 s | zwykły napis (`texts`) |
| dźwięk | głośność −14 LUFS, opcjonalnie cicha muzyka pod mową | `audio` |

## 4. Co trzeba zbudować

| # | Część | Co | Gdzie |
|---|---|---|---|
| 1 ✅ | **Kadr z punktem skupienia** | `fx`, `fy`, `zoom` w klipie: eksport (`crop` ffmpeg), podgląd i suwaki „Kadr” w edytorze, walidacja | `hq/plugin/edytor.py`, `hq/web/src/45-edytor.js`, `projekt.py` |
| 2 ✅ | **Napisy karaoke** | napis z `words: [[start, end, słowo]]` i `hl` (kolor aktywnego słowa); rysowanie z podświetleniem w `44-napisy.js`; eksport jako **jedna** warstwa (PNG na słowo, sklejone demuxerem concat), więc stała pamięć niezależnie od liczby słów; poprawka tekstu z tą samą liczbą słów (literówka) zachowuje karaoke, inna liczba słów wyłącza je tylko w tej linii | `44-napisy.js`, `45-edytor.js`, `edytor.py`, `plugin_api.py`, `projekt.py` |
| 3 ✅ | **klipy.py** | `przygotuj` (mowa.json, sceny, arkusze, transkrypcja.txt z oknami ~90 s), `zbuduj` (plan.json → granice dosunięte do przerw między słowami → projekty → render), `sprawdz` (walidacja planu: czasy w źródle, długości, hook, słowo przecięte i dokąd pójdzie granica, wspólny materiał rolek, rolki z jednej połowy nagrania) | `profiles/jarvo-wideo/scripts/klipy.py` |
| 4 ✅ | **Skill `clipmaker`** | kroki, master prompt, schemat `plan.json`, styl rolki, DoD, rubryka; zastąpił dawny `klipy-z-dlugiego` (gotowe MP4 z wypalonymi napisami, bez możliwości edycji) | `profiles/jarvo-wideo/skills/wideo/clipmaker/` |
| 5 | **Routing i evals** | „zrób rolki/shorty z tego nagrania” → Wideograf ze skillem `clipmaker`; scenariusze: wybór, wyrwanie z kontekstu, film bez praw | `evals/`, rubryka Wideografa |
| 6 | **Dokumentacja** | HQ.md §2a (kadr, karaoke), FLEET, README profilu, JARVO-CALOSC | |

`plan.json` (pisze Wideograf, sprawdza `klipy.py sprawdz`):
```json
{"zrodlo": "/opt/data/jarvo/inbox/…/podcast.mp4", "format": "9:16",
 "styl": {"napisy": "karaoke", "hl": "#FFE14D", "tytul": true, "tnij_pauzy": 0.6, "muzyka": null},
 "rolki": [{"slug": "3-bledy-cen", "tytul": "3 błędy w cenach", "opis": "…", "hashtagi": ["#biznes"],
            "segmenty": [{"od": 754.2, "do": 781.9, "fx": 0.42, "fy": 0.35, "zoom": 1.0}],
            "oceny": {"hook": 8, "samodzielnosc": 9, "wartosc": 8, "emocja": 7, "puenta": 8, "udostepnienie": 7},
            "dlaczego": "konkretna lista z liczbami, zamyka się puentą"}]}
```

## 5. Ograniczenia i decyzje

- **VPS 8 GB:** transkrypcja 1 h nagrania to ~6–12 min Parakeeta (jedna naraz, ~1,2 GB RAM); render rolki
  30–60 s w ~0,5–1× czasu rzeczywistego. Rolki renderują się jedna po drugiej.
- **Kadr na twarz** (od 2026-10-03, za openshorts): YuNet z OpenCV Zoo (MIT, 230 KB, ONNX na CPU, ~15 ms na
  klatkę) przez `twarze.py`; wynik w `<nagranie>.twarze.json`. Kadr jest stały w obrębie ujęcia (edytor nie ma
  klatek kluczowych), więc zamiast płynnej jazdy kamery jest nowe ujęcie przy zmianie twarzy albo dużym ruchu.
  Przy kilku twarzach kadr trzyma największą (obecna ×3), dopóki inna nie wygra przez ~1,5 s.
- **Rozpoznawanie mówców (kto mówi):** nie w v1; przy kilku osobach w kadrze wygrywa największa twarz.
- **Prawa:** tylko materiał użytkownika albo z jego zgodą (jak w każdym montażu nagrań).
- **Publikacja** rolek na platformy: poza zakresem (A2, osobna decyzja).

## 6. Kolejność budowy (każdy krok: commit, testy, test w kontenerze i w zalogowanym edytorze HQ)

1. ✅ kadr `fx`/`fy`/`zoom` (eksport + podgląd + suwaki, `projekt.py kadr`),
2. ✅ napisy karaoke (rysowanie, edycja, eksport jedną warstwą, `projekt.py napisy --karaoke` i `render`),
3. ✅ `klipy.py przygotuj` + `zbuduj` + `sprawdz`,
4. ✅ skill `clipmaker` z master promptem (`references/master-prompt.md`, `plan.md`), routing, evals, rubryka; `klipy-z-dlugiego` usunięty,
5. próba na prawdziwym nagraniu: 10–20 min → 3–5 rolek, otwarcie i poprawka rolki w edytorze, eksport.
