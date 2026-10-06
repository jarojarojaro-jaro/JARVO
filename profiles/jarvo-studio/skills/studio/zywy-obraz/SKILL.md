---
name: zywy-obraz
description: "Zdjęcie lub grafika → pętla 5 s (GIF/MP4), warstwy PSD."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [animation, loop, gif, photo, layers, psd]
    related_skills: [lemo-wake, lemo-wake-layers, grafika-social, formaty-platform, publikacja]
  jarvo:
    agent: jarvo-studio
    autonomy: A1
    reviewed: "2026-10-06"
---

# Żywy obraz (lemo-wake)

Jedno zdjęcie, plakat, logo, wykres albo gotowa grafika z `grafika-social` zamienia się w pętlę około 5 sekund.
Rzeczy z obrazu naprawdę się ruszają: modele wycinają je z tła, kod składa je na nowo, a koniec łączy się
z początkiem. Bez generowania obrazów i bez kluczy API: materiał tylko z obrazu, kodu i lokalnych modeli.
Robi to lemo-wake (skill `lemo-wake`; rozbicie na warstwy: `lemo-wake-layers`) w przypiętej wersji.

## Licencja: najpierw to
lemo-wake ma licencję CC BY-NC 4.0, czyli wolno go używać tylko niekomercyjnie.
**Zgoda autora na użycie komercyjne: brak** (stan 2026-10-06; gdy właściciel ją dostanie, zmieniamy ten wiersz).
- **Komercyjne** = praca dla klienta, reklama, post promujący ofertę albo sprzedaż, grafika na stronę lub do sklepu firmy.
  Takiej karty tym skillem nie robisz. W RAPORT piszesz, że potrzebna jest zgoda autora (github.com/lemomo-ai),
  i proponujesz zamiennik: ruch kodem w `grafika-social` albo film u Wideografa.
- **Niekomercyjne** (prywatne zdjęcie właściciela, test, materiał bez celu zarobkowego): robisz.
- W RAPORT zawsze dopisek: „zrobione narzędziem lemo-wake (Lemomo), CC BY-NC 4.0”.

## Kiedy użyć
- „ożyw to zdjęcie”, „zrób z tego GIF / animację”, „ruchomy plakat”, „żywe logo”, „niech ta grafika się rusza”.
- „rozbij na warstwy”, „daj PSD”, „oddziel ludzi od tła”: `lemo-wake-layers`.

## Kiedy NIE używać
- Film z kilkoma ujęciami, lektorem albo muzyką → brief do Wideografa (`pakiet-kampanii`, `out/teksty/BRIEF-WIDEO.md`).
- Nowy obraz → `generacja-ai`; sam kadr albo zmiana rozmiaru → `formaty-platform`; samo usunięcie tła → `grafika-social` (rembg).
- Karta komercyjna bez zgody autora (wyżej).

## Wejścia
| Wejście | Wymagane | Jeśli brak |
|---|---|---|
| obraz (plik w workspace) | tak | zapytaj; nie bierz obrazów z internetu bez licencji |
| cel i platforma | tak | z karty; brak = post na social |
| rozmiar | nie | rozmiar źródła; social według `formaty-platform` (Reels/Stories `--out 1080x1920`, post IG `--out 1080x1350`) |
| formaty | nie | MP4 + GIF; WebP na stronę |

## Start (każde polecenie)
```bash
python3 $HERMES_HOME/scripts/lemo_wake.py sprawdz        # JSON: biblioteka, python, playwright, przeglądarka, modele, zgoda
python3 $HERMES_HOME/scripts/lemo_wake.py instaluj       # raz (ok. 350 MB, ok. minuty); też gdy "biblioteka": false
eval "$(python3 $HERMES_HOME/scripts/lemo_wake.py env)"  # na początku KAŻDEGO polecenia: zmienne nie przeżywają między poleceniami
```

## Różnice wobec instrukcji lemo-wake
Instrukcja `$LW/SKILL.md` (ten sam tekst co skill `lemo-wake`) zakłada laptopa z Claude Code. U nas:

| W instrukcji | U nas |
|---|---|
| `$S` (folder skilla) | `$LW`; przy warstwach `$L` = `$LW_WARSTWY`, `$W` = `$LW/scripts` |
| `$S/scripts/x.py …` (przez `uv run`) | `$LW_PY $LW/scripts/x.py …`: pakiety przypięte; nigdy `uv run`, nic nie doinstalowujesz |
| `node $S/scripts/doctor.mjs --fix` | bez `--fix` (pobiera przeglądarkę); stan z `lemo_wake.py sprawdz`, przeglądarka z obrazu (`CHROME`) |
| `LEMO_WAKE_MODELS=…`, `${CLAUDE_PLUGIN_DATA}` | ustawia `env` (modele poza biblioteką, przeżywają aktualizację) |
| `history.jsonl` | `$LW_HISTORIA` |
| projekt w bieżącym katalogu | `mkdir -p out/zywe && cd out/zywe` w workspace karty, potem `new_project.py` |
| pytanie o rozmiar i formaty | z karty (tabela wejść); pytasz tylko, gdy karta nic nie mówi, a cel jest niejasny |
| Live Photo (`livephoto.py`), naklejka WeChat | pomijasz (macOS, chińskie komunikatory) |
| `/lemo-wake:upload`, galeria autora | nigdy; publikacja tylko przez `publikacja`, za zgodą |
| język rozmowy | do właściciela po polsku; instrukcje skilla są po angielsku |

## Modele
Pięć modeli ONNX, razem ok. 600 MB z Hugging Face: głębia, wycięcie głównego obiektu, wycięcie osoby z włosami,
wybór elementu (SAM) i wypełnienie dziury (LaMa). Model, który jest już na dysku, działa bez pytania.
- **Kod 10:** zapytaj właściciela raz, jedną wiadomością: które modele, po co, ile MB, skąd, gdzie leżą
  (`/opt/data/jarvo/narzedzia/lemo-wake-dane/models`) i co stracisz bez nich. Odpowiedź zapisz:
  `$LW_PY $LW/scripts/models.py consent yes` (albo `no`), potem uruchom krok jeszcze raz. Drugi raz nie pytasz.
- **Kod 11 (odmowa):** nie pytasz ponownie, robisz obejście kodem: maski po kolorze, `inpaint.py --engine opencv`,
  paralaksa warstwami zamiast głębi.
- **Kod 12 (pobieranie nie wyszło):** jedna powtórka, potem obejście i wpis w RAPORT.

## Kroki
1. **Licencja i brief:** sprawdź licencję (wyżej), potem cel, platformę, rozmiar i formaty.
   - ✅ Punkt kontrolny: karta niekomercyjna albo jest zgoda autora; obraz leży w workspace.
2. **Przed planem przeczytaj `$LW/references/taste.md`** i typ obrazu z `$LW/types/` (photo, poster, logo, chart…).
3. **Budowa według `$LW/SKILL.md`, kroki 2–8:** projekt (`new_project.py`), rozbiór na części modelami, plan w `DIRECTOR.md`
   (jedna akcja, która należy tylko do tego obrazu), `index.html`, kadry kontrolne (`render.mjs … stills`, `sheet.py`),
   pełny render, pętla, kodowanie (`encode.py`) i `qa.py`.
4. **Marka:** dodatki (napis, CTA, kolor tła przy innym formacie) z brand kitu `@@KNOWLEDGE_DIR@@/brands/<marka>/`.
5. **Kontrola:** `qa.py` bez FAIL, `python3 $HERMES_HOME/scripts/check_media.py out/zywe/<slug>-alive/<slug>.mp4 --auto`
   (sam plik: katalog projektu ma też setki klatek), obejrzyj
   `qa_sheet.jpg` (ostatni kafel to pierwsza klatka: szew pętli) i pierwszą klatkę, bo to okładka w wielu aplikacjach.
6. **Warstwy (PSD), gdy ktoś o nie prosi:** instrukcja `$LW_WARSTWY/SKILL.md` z podstawieniami z tabeli wyżej.

## Wyjścia
- w projekcie `out/zywe/<slug>-alive/`: `<slug>.mp4`, `<slug>.gif` (+ `<slug>.webp` na stronę), `DIRECTOR.md`,
  `src/qa_sheet.jpg`; klatki (`src/frames*`) usuwasz po oddaniu;
- warstwy: `layers.psd`, PNG warstw, `layers.json`;
- wpis w `out/INDEX.md` i w `$LW_HISTORIA`.

## Definition of Done
- [ ] licencja sprawdzona (niekomercyjnie albo zgoda autora), dopisek w RAPORT
- [ ] w obrazie naprawdę coś się rusza (samo światło albo kolor to za mało), pętla bez skoku, `qa.py` bez FAIL
- [ ] wymiary i waga pasują do platformy (`check_media.py`)
- [ ] pierwsza klatka wygląda dobrze

## Typowe błędy
- Skrypt bez `$LW_PY` albo przez `uv run` → inne wersje pakietów pobierane od nowa.
- `doctor.mjs --fix` → zbędne 190 MB przeglądarki w profilu.
- Brak `eval "$(… env)"` w poleceniu → modele szukane w złym miejscu i drugie pytanie o zgodę.
- Karta komercyjna zrobiona bez zgody autora.

## Format raportu
```
Żywy obraz: <slug> (<typ obrazu>), <szer>×<wys>, <s> s
Akcja: <jedno zdanie>; pętla: <jak się zamyka>
Pliki: out/zywe/<slug>-alive/<slug>.mp4 (<MB>), .gif (<MB>)[, .webp]
QA: <PASS / WARN z opisem>; modele: <użyte / obejście>
Licencja: lemo-wake (Lemomo), CC BY-NC 4.0; użycie: niekomercyjne | zgoda autora z <data>
```
