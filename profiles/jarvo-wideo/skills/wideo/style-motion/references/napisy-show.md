# Napisy show, kolorowe reakcje nad nagraniem (wzór `18-hanazi`)

Napisy jak z telewizyjnego programu rozrywkowego: grube, kolorowe słowa w kilku obrysach wyskakują litera po literze
nad nagraniem klienta i komentują, co się dzieje, obok naklejki, wybuchy, iskry i krople potu. Poznasz go po białym
i kolorowym obrysie, sprężystym „pyknięciu” liter i obrazie, który drży jak z ręki.
Wzór: okładka `$MGSTYLES/videos/18-hanazi.jpg`, kod `$MGSTYLES/demos/18-hanazi/index.html` (MIT), ocena jury 7,64;
1080×1920 (9:16), 30 kl./s, 10 s. Wzór nie rusza w `html_wideo.py`: jego zdjęcia nie mają podanego źródła i nie są
instalowane. Oglądasz okładkę i kod (napisy wzoru są po chińsku; liczby i budowa warstw się przenoszą).

## Do czego
- Sklep zoologiczny, groomer, weterynarz: rolka z reakcjami zwierzaka, 9:16, 10–20 s.
- Kawiarnia, piekarnia: „reakcja na danie”, kulisy kuchni; salon urody, barber: przed i po; 9:16, 10–15 s.
- Agent nieruchomości, lokalny sklep: wycieczka po mieszkaniu albo zapleczu, 9:16, 15–30 s.
- Stały zestaw napisów do cotygodniowych nagrań klienta (ta sama plakietka, kolory i dźwięki).

## Nie do
- Luksus, B2B, formalna marka (kancelaria, bank): skill `typografia-edit` (spokojne napisy przy mowie).
- Napisy do mowy słowo w słowo: skill `napisy`; rolki z długiego nagrania: `clipmaker`. Słowa mowy w tym wyglądzie
  (obrysy, wyciągnięcie, skok) bez budowania strony: styl `show` w skillu `typografia-edit`.
- Brak nagrania klienta (sama grafika): `naklejki.md`. Film poziomy bez nowego układu: styl jest pionowy z natury.

## Cechy stylu (sprawdzalne)
- Napis od tyłu: 2 kopie wyciągnięcia (przesunięte o `ext` i `ext/2`), obrys kolorowy (szer. 2·(biały + zewnętrzny)),
  obrys biały (2·biały), wypełnienie gradientem pionowym, połysk (biel do 0,46 wysokości), cień grupy (dy 12,
  rozmycie 11, #1a0a28 krycie 0,36). Tytuł wzoru: 172 px, biały 13, zewnętrzny 12 #FF3D7F, wyciągnięcie 16 #A3124F,
  wypełnienie #FFFBD6 → #FFE23A → #FF9A1F, połysk 0,55.
- Pyknięcie: sprężyna ζ 0,517, ω 22, szczyt 1,15 w 5. klatce, ok. 1,01 w 8. (prompt: 0 → 1,15 → 1 w ok. 8 klatek);
  spadek z góry: sprężyna (0,55; 20), obrót do zera: (0,45; 18). Litery co 2 klatki, podpis co 1 klatkę.
- Trzymanie: po 0,22 s kołysanie ±1,8° i 3 px (1,15 Hz), „oddech” ±1,2% (2,3 Hz); zejście 0,17 s: 1 → 1,12 → 0.
- Emocja = forma: szept małym krojem odręcznym jak z maszyny; cisza pionową kolumną pochyloną −7°; zakłopotanie:
  krople potu zjeżdżają 74 px; szok: podwójny poszarpany wybuch (15 kolców, nowy kształt 12 razy na sekundę),
  120 klinów linii prędkości, 20 promieni (14°/s), biała klatka.
- Naklejki: plakietka programu, pasek ostrzeżenia, plakietka z imieniem, miernik (do końca skali w 4 klatki, potem
  drga), pieczątka (2,5 → 1 w 0,13 s, drganie `1 − 0,09·e^(−16w)·cos(44w)`), wycieranie w paski jak cukierek.
- Nagranie żyje: drżenie ±7/2,5 px w poziomie, ±6/2 px w pionie, ±0,32°; powolny najazd na punkt ostrości;
  potrójny najazd (2 klatki outExpo + 3% przestrzelenia).
- Paleta wzoru (role; kolory z marki): róż #FF3D7F, żółć #FFE14D, cyjan #2CCBF2, obrysy granat #1E2A78, tusz
  #1A1030, pomarańcz #FF9A1F, fiolet #B04CFF, zieleń #7BE35A, czerwień #FF2E4D.
- Wzór nie ma emoji ani słów dźwiękonaśladowczych; napis spóźnia się za chwilą tylko czasem (+2–3 klatki).

## Technika
- Kontrakt jarvo, 1080×1920, warstwy DOM: nagranie → winieta → SVG z napisami i naklejkami → błysk; wszystko
  ustawiane w `__seek(t)` od zera. Czasy w `out/wideo/src/cues.json`.
- Nagranie klienta all-intra (`ffmpeg -i in.mp4 -g 1 -an klip.mp4`), blob URL, `currentTime` + `Promise` na
  `seeked` (`kontrakt-html.md`); tylko materiał klienta albo stock (`material-stock`), nigdy zdjęcia wzoru.
- Przenieś z `index.html` (`// za mg-styles-15 (MIT), demos/18-hanazi/index.html`): `HZ` (75–96, warstwy napisu),
  `charXf`, `popOut`, `driveHZ` (97–115), `spring` (51–54), `el`, `grad` (64–72); dekoracje `sparkleD`, `burstD`,
  `focusD`, `raysD`, `DROP_D`, `PAW_D` (117–138); kamera `hand`, `kick`, `addK`, `geom`, `place`, `plate3`
  (58–63, 147–170). `HZ` potrzebuje tylko `<defs>` z filtrem `#soft`: przekaż je parametrem.
- Ikonki zamiast emoji: ścieżki SVG (iskra, kropla potu, łapka, serce, gwiazdka, „!” i „?” w dymku) z obrysem jak
  napisy. Emoji z czcionki systemu wygląda inaczej na każdej maszynie albo wychodzi pustym prostokątem.
- Kroje z `/_lib/kroje/` (wzór ma chińskie): Titan One, Grandstander 900, DynaPuff 700, Baloo 2 800, Nunito 1000;
  szok Bangers albo Sigmar pochylone −8°; szept Patrick Hand albo Caveat. Przed `__ready` dla każdego kroju
  i grubości `await document.fonts.load('900 172px "Grandstander"', 'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ')`: polskie litery są
  w osobnym pliku kroju, bez tego napis z 6. sekundy ma w pierwszych klatkach krój zastępczy.
- Pyknięcie od 0 (0 → 1,15 → 1) to cecha stylu i wyjątek od reguły „skala nigdy od 0”; naklejki, karta i logo
  wchodzą `ladowanie(t, t0, 'zabawny')` z `ruch.js`.
- Rozmycie wzoru (16 rysunków na najazd, 48 kopii plakietki) zastępujesz `duchy(t, rysuj, 3, 1 / 60, 0.5)`
  z `ruch.js` przez 2 klatki najazdu; bez `--subklatki`. Ziarno wzoru (`grain_fine_2048.png`, źródło nieznane)
  zastępujesz `ziarno(g, W, H, klatka, 0.05)` z `plotno.js` na płótnie nad nagraniem albo pomijasz.
- Bez wycinania bohatera ze zdjęcia (wzór: BiRefNet i ręczne punkty), chyba że klient da PNG z przezroczystością.
- Render: zmierz `klatki --preset jarvo --czasy 6` (filtry SVG) i podaj właścicielowi czas, gdy całość > kilka minut.

## Rytm (10 s wzoru → film klienta)
| Czas | Co się dzieje |
|---|---|
| 0–2,5 | Hak: plakietka wlatuje (0–0,33 s), tytuł pyka literami od 0,2 s, skacze na taktach 1,0/1,5/2,0 s |
| 2,5–4,0 | Cięcie ze zgrzytem płyty; „???” skacze w rytm, najazd na detal 3,0 s, „Cisza…” pionowo, pot |
| 4,0–5,8 | Wycieranie w paski; plakietka z imieniem 4,2 s, pasek ostrzeżenia 4,9 s; najazdy 5,25/5,5/5,75 s |
| 5,8–6,0 | Krótka cisza: kadr stoi, muzyka milknie |
| 6,0 (60%) | Kulminacja: biała klatka, promienie, wybuch, „Szok!!” 250 px pochylone −8°; podpis 6,6 s |
| 7,5–8,0 | Stopklatka (szara, 0,27 s), potem nagranie staje się kartą (skala 0,72, −4°, biała ramka) na paskach |
| 8,1–10 | „Petarda!” 8,1 s, pieczątka z logo 8,5 s, „Do zobaczenia!” 8,9 s; karta stoi z kołysaniem napisów |

- 15–30 s: scena 3–5 s z jednym głównym napisem i najwyżej jedną naklejką; kulminacja raz w 60–65%, karta od 80%.
- 16:9: nowy układ (napisy w bocznych trzecich, nagranie w środku); wzór ma 1080×1920 na sztywno (`#stage`, `geom()`).

## Dźwięk
- Skoczny podkład 120 BPM (pizzicato, tuba, dzwonki, klaskanie): `muzyka-pozytywna`, `dzingiel-pizzicato`; `rytm.py`.
- Litera `pop` z `sound.mjs` (`pitch` 0,9–1,3 kolejno), podskok `boing`, cięcie `scratch` albo `zgrzyt-plyty`
  z biblioteki, naklejka `click`, pieczątka `thump`, iskry `sparkle`, wycieranie `whoosh`, karta `migawka`.
- Szok: przed nim `riser`, potem 0,2 s ciszy, na nim `crack`; miernik drga z `buzz`. Całość −14 LUFS.

## Pułapki
- Za dużo naraz zakrywa nagranie: najwyżej 3 grupy w kadrze, twarz i produkt zawsze odsłonięte.
- Wzór ma kilka uderzeń całego kadru (błysk, wstrząs, stopklatka); u nas najwyżej 3, reszta bitów na napisach.
- Napis znika, zanim widz go przeczyta: po pyknięciu stoi ≥ 1 s, dłuższy według czasu czytania z `pomiar`.
- Teksty wzoru nie przekładają się słowo w słowo: piszesz od nowa („Serio?!”, „Cisza…”, „Petarda!”), 1–3 słowa.

## Kontrola
- `html_wideo.py klatki out/wideo/src/index.html --preset jarvo --czasy 0.37,1.5,2.6,4.9,6,6.2,8.6,9.6 --arkusz
  out/wideo/arkusz.jpg`: 0,37 s szczyt pyknięcia 1. litery (5. klatka), 6,0 s biała klatka, 6,2 s „Szok!!”.
- „Zażółć gęślą jaźń” każdym krojem na arkuszu, w powiększeniu: ogonki, kreska ł i kropka ż widoczne pod obrysem.
- `html_wideo.py pomiar out/wideo/src/index.html --preset jarvo --dlugosc 10 --platforma tiktok`: tekst poza UI
  platformy (dół i prawa kolumna), czasy czytania, `uderzenia_kadru` ≤ 3.
- Ostatnia klatka: karta z logo stoi 0,8–1,2 s z kołysaniem napisów; na 360 px napisy czytelne, twarz widoczna.
