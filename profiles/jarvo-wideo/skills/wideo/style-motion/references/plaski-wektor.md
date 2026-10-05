# Płaski wektor (wzór `01-flat-vector`)

Klasyczny explainer: płaskie plamy koloru bez gradientów, geometryczne postacie, sprężyste wejścia i jedno ujęcie
bez cięć, w którym kropka przechodzi z kształtu w kształt. Widz poznaje styl po nasyconych kolorach i ściskaniu.
Wzór: okładka `$MGSTYLES/videos/01-flat-vector.jpg`, kod `$MGSTYLES/demos/01-flat-vector/` (MIT), ocena jury 7,64;
1920×1080, 30 kl./s, 10 s (300 klatek), jedno SVG i jeden skrypt, bez bibliotek; ok. 0,2 s na klatkę na CPU:
```
python3 $HERMES_HOME/scripts/html_wideo.py klatki $MGSTYLES/demos/01-flat-vector/index.html --preset mg \
  --czasy 0.5,1.4,3,3.5,5.1,6,8.5,9.5 --arkusz out/wideo/wzor-01-flat-vector.jpg
```

## Do czego
- Aplikacja, SaaS, fintech: „jak to działa” w 3 krokach albo onboarding, 16:9 i 9:16, 10–30 s.
- Biuro rachunkowe, broker ubezpieczeń, kancelaria podatkowa: prosta oferta bez zdjęć, 1:1 i 9:16, 15–20 s.
- Rekrutacja w sklepie albo zakładzie produkcyjnym: „dołącz do nas”, 9:16, 15 s.
- Gmina, szkoła: komunikat (zapisy, segregacja, nowy przystanek), 16:9 i 1:1, 20–30 s.

## Nie do
- Luksus, premium, spokój: `rysunek-linia.md`. Rękodzieło i ciepło „zrobione ręcznie”: `kreska.md`.
- Produkt do „poczucia” (kosmetyk, jedzenie): `3d.md` albo zdjęcia klienta (`promo-produktu.md`, `rodzaje-filmu`).
- Trudne tematy (choroba, żałoba, windykacja): sprężystość brzmi lekceważąco; wybierz `rysunek-linia.md`.

## Cechy stylu (sprawdzalne)
- Ściśle płasko: zero `<linearGradient>`, `<radialGradient>` i filtrów; cień to płaski ciemniejszy pas 14% szerokości.
- Paleta wzoru (role): tło ultramaryna `#2B2BFF`, bohater koral `#FF5A4E`, akcent słonecznik `#FFC62B`, mięta
  `#2EE6A8`, krem `#FFF6E9`, tusz `#151433`; każdy kolor ma ciemniejszy i jaśniejszy ton (`#1F1FCC`, `#4D4DFF`).
- Wejścia sprężyną w zamkniętej postaci: 2,3–5 Hz, tłumienie ζ 0,38–0,65, ściśnięcie 10–25% z prędkości sprężyny,
  po 0,9 s wartość przypięta do 1. Krzywa z promptu `(.34, 1.56, .64, 1)` jest w kodzie, ale nieużywana.
- Kolejność: 9 budynków co 3 klatki, litery logo co 1 klatkę; naraz rusza się jeden bohater. Bez motion bluru.
- Ściśnięcie: pierwsze uderzenie piłki sy 0,6 / sx 1,36 (40%), drugie 20%, przysiad 30%, w locie do 42% wzdłuż
  prędkości; logo i słońce ok. 10%.
- Jeden bohater przez cały film: koralowa kropka (piłka → słońce → bańka powiadomienia → zalew koła → kropka siatki
  → moneta → szczyt słupka → kropka nad „ı” w logo).
- Przejścia kształtem: przelot przez okno 64×36 px z przybliżeniem 30× w skali log (błysk w klatce 105); zalewy
  koło (kl. 150) → kapsuła mięty (154) → kremowe półkole (158) → uderzenie (164); siatka 2×2 rośnie w pole logo.
- Piłka: g = 2040 px/s², wstrząs 2 klatki (112–113), najazd końcowy 4,5%; ikony na takty 6,0 / 6,5 / 7,0 / 7,5 s.

## Technika
- SVG w DOM (jak wzór) albo Canvas 2D w kontrakcie jarvo (`kontrakt-html.md`, skill `rodzaje-filmu`): `__seek(t)`
  ustawia `transform` każdej grupy. Tekst w SVG `pomiar` czyta sam.
- Ruch z `ruch.js`: charakter `zabawny` (0,9 s, krzywa `0.34, 1.56, 0.64, 1`, przestrzelenie 1,08, ściśnięcie 0,18),
  dla poważniejszej firmy `przyjazny`; `ladowanie(t, t0, CH)` → `skala`, `sx`, `sy`. Przelot kropki:
  `rozciagniecie(v, 0.00025, 0.42)` (wzór dochodzi do 42%).
- Z `morph.js` (`morph.md`): drganie po kontakcie `uderzenie(t, t0, {A: 0.2})` (start 2 klatki przed kontaktem),
  ściśnięcie bez zmiany pola `macierzScisku(phi, k)`, kształt w kształt (bańka → kapsuła, słupek → litera)
  `para(A, B)` + `przemiana(p, u)`, kolory `mieszajKolor` (OKLab), smuga kropki `smugaKropki(g, pA, pB, r, kolor)`.
- Z kodu wzoru (komentarz `// za mg-styles-15 (MIT), demos/01-flat-vector/index.html`): `spring`, `springV`, `pop`
  (wiersze 31–58), kamera przez okno `camera` (250–266: `s = exp(lerp(log sB, log S1, p))`), `ballA` (409–430:
  grawitacja, ściśnięcie, łuk Béziera), `burstLine` i `ring` (400–407: promienie i fale uderzenia).
- Kroje z `/_lib/kroje/kroje.css`, zaokrąglone jak Fredoka wzoru: Nunito 800–900, Baloo 2 800, Rubik 700, DynaPuff;
  podpisy Outfit albo Poppins 500. Metrykę kroju (np. kropka nad literą) licz po `await document.fonts.load(
  '800 120px "Nunito"', 'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ')` dla każdego kroju (polskie litery są w osobnym pliku).
- Logo z SVG klienta; kropka kończy w logo tylko, gdy ma ono okrągły element (kropka, „o”), inaczej ląduje obok.
- Szybki ruch: 3–6 kresek prędkości przez 0,1–0,2 s albo `smuga`/`duchy` z `ruch.js` (nigdy na tekście); prompt
  chciał motion bluru z 4 próbek, wzór go nie ma. Bez ziarna, papieru i winiety: styl jest czysto płaski.

## Rytm (10 s wzoru → film klienta)
| Czas | Co się dzieje |
|---|---|
| 0–1,33 | Hak: piłka już spada; uderzenia 0,5 i 0,8 s, przysiad, wybicie po łuku w słońce (12 promieni) |
| 1,33–2,8 | Ziemia wjeżdża, 9 budynków od 1,47 s, chmury, ptaki, drzewa, okna |
| 2,8–4,5 | Roleta w oknie w górę, przelot przez okno (3,0–3,73), postać przy biurku, telefon dzwoni 4,0 s |
| 5,0–5,5 | Bańka powiadomienia zalewa kadr: koło → kapsuła → półkole → uderzenie |
| 6,0–7,8 | Kulminacja: 4 ćwiartki na takty, kropka skacze między nimi |
| 7,8–9,2 | Kropki zbiegają się w słupek, słupek → litera, kropka ląduje nad nią (8,5), hasło 8,6–9,2 |
| 9,2–10 | Logo stoi, dwa drgnięcia na bity (9,0 / 9,5), powolny najazd 4,5% |
- 20 s (3 kroki): hak 0–2, świat 2–5, problem 5–8, 3 korzyści po 2 s (8–14; pierwsza ok. 12 s = 60%, przed nią
  0,3 s ciszy), przejście w logo 14–16, logo i hasło od 16 s, koniec stoi 1 s z jednym drgnięciem na bit.
- 9:16: nowy układ: siatka 2×2 w kwadracie środka albo 4 pasy jeden pod drugim, miasto węższe i wyższe (5 budynków),
  linia ziemi liczona z wysokości kadru, logo na ok. 80% szerokości.

## Dźwięk
- Pop / future bass 120 BPM: motyw 4 nut marimby (we wzorze F5–A5–C6–A5) na dzwonek telefonu i na drop, stopa 808;
  podkład z `projekt.py dzwieki --muzyka` (np. „Pozytywnie”, „Reklama”), bity z `rytm.py`.
- Każde wejście ma dźwięk: `pop` na budynki (`pitch` 0,9 → 1,3), `boing` na odbicie, `whoosh` 0,15 s przed przelotem
  przez okno, `klawiatura` i `powiadomienie` z biblioteki przy biurku, `sparkle` na logo.
- Drop: 0,25 s ciszy, potem akcent na każdą ćwiartkę (`click` + `pop`). Całość −14 LUFS.

## Pułapki
- Gradient „na chwilę”, rozmyty cień, obrys 1 px: styl przestaje być płaski.
- Kilka rzeczy rusza się naraz: zostaje jeden bohater, tło rusza się mniej i 2–4 klatki później.
- Układ zależny od metryki kroju: krój zastępczy przesuwa logo i kropkę bez żadnego błędu.
- Współrzędne wzoru na 1920×1080 (`GY = 820`, budynki, siatka 960×540): pion to nowy układ.
- Jedna krzywa na wszystko: przestrzelenie wszędzie takie samo. Wzór stroi sprężyny 2,3–5 Hz; duże rzeczy wolniej.
- Przelot przez okno w skali liniowej: najpierw stoi, potem skacze. Zoom tylko w skali log.

## Kontrola
- `python3 $HERMES_HOME/scripts/html_wideo.py klatki out/wideo/src/index.html --preset jarvo
  --czasy 0.5,0.8,2,4,11.9,12,16.5,19.5 --arkusz out/wideo/arkusz.jpg`: w każdej klatce jeden bohater; w kodzie
  strony zero `Gradient`, `filter` i `blur`.
- `krytyka.py pasek out/wideo/film.mp4 --t 0.5 --klatek 12`: ściśnięcie w 1–2 klatkach kontaktu, kształt wraca
  bez drgania; to samo przy przelocie przez okno (płynny zoom, bez skoku).
- `… pomiar out/wideo/src/index.html --preset jarvo --dlugosc 20 --platforma tiktok` bez błędów (9:16), hasło ≥ 5%
  wysokości; `… wideo … --preset jarvo --dlugosc 20 --fps 30 -o out/wideo/film.mp4` (ok. 0,2 s na klatkę).
- Ostatni kadr: logo i hasło stoją ≥ 0,8 s; `krytyka.py telefon out/wideo/film.mp4` czytelny na 360 px.
