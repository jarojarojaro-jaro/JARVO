---
name: zywy-schemat
description: "Żywy schemat: przepływ, który działa; post X, Instagram."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [video, diagram, architecture, infographic, social, live-panel]
    related_skills: [live-panel, film-z-kodu, rodzaje-filmu, kontrola-wideo]
  jarvo:
    agent: jarvo-wideo
    autonomy: A1
    reviewed: "2026-10-04"
---

# Żywy schemat

Schemat, który wygląda jak obrazek, a jest filmem: układ stoi, a system „działa”. Kropki płyną po strzałkach, kroki
podświetlają się po kolei, log się przewija, liczniki rosną. Każda klatka to cały, czytelny schemat. Silnik strony
to skill zewnętrzny `live-panel` (szablon, schemat pliku, gramatyka ruchu); `zywy_schemat.py` dokłada formaty platform,
motywy Jarva, polskie kroje i kontrolę, a `html_wideo.py` (preset `livepanel`) robi klatki, pomiar i film.

## Kiedy
- Post na X, Instagram, LinkedIn: „jak działa nasza flota / usługa”, przepływ zlecenia u klienta, architektura systemu,
  proces sprzedaży, lejek, kto komu co oddaje.
- Statyczna infografika klienta (jego własna, za zgodą) ma „ożyć”: jego układ, słowa i kolory, bez nowych modułów.
- Nie do: wyjaśniania krok po kroku z lektorem (explainer, `rodzaje-filmu`), wykresu z danych (`chart-animation`),
  schematu do rozmowy z właścicielem (Jarvo, skill `schemat`: PNG w kilka sekund).

## Kroki
1. **Treść i źródła.** Ramki, kto do kogo, co jest krokiem, co liczy licznik. Każda liczba ma źródło (link, raport
   klienta, `fleet.yaml`) albo jest poglądowa i ekran to mówi (linia `credit`: „liczby poglądowe”). Nie zmyślamy
   wyników ani pomiarów.
2. **Config JSON.** Start: `references/flota-jarva.json` (motyw jasny, Instagram 4:5, jedna maszyna `cycle` z 8 krokami
   po 3,5 s, która steruje obwódkami, strzałkami i listą) albo konfiguracje z `$HERMES_HOME/skills/video/live-panel/examples/`.
   Pola: `live-panel/references/config-schema.md`. **Przed wyborem maszyn przeczytaj `live-panel/references/motion-grammar.md`.**
   Format `canvas.preset` (`python3 $HERMES_HOME/scripts/zywy_schemat.py formaty`): `x`, `ig`, `pion`, `kwadrat`, `poziom`.
   Motyw `theme.preset`: `jarvo-jasny`, `jarvo-ciemny` albo marka klienta (`colors` z przewodnika marki, krój z zestawu Jarva).
   Pozycje są w pikselach płótna: inny format to osobny config. Współrzędne licz skryptem (pętla po ramkach), nie
   wpisuj ręcznie. Tekst w bezpiecznych marginesach: 6% boków, 8% góry i dołu (pion: strefy UI platformy).
3. **Strona:** `python3 $HERMES_HOME/scripts/zywy_schemat.py strona schemat.json -o out/wideo/<projekt>/schemat.html`
   (uwagi `!` o braku źródeł i krojach spoza zestawu poprawiasz od razu). Strona działa offline w każdej przeglądarce, w pętli.
4. **Kontrola** (wszystko na tej samej stronie):
   - `zywy_schemat.py sprawdz schemat.html`: kod 0 (tekst w ramkach, ramki nie nachodzą na siebie, brak błędów strony);
   - `html_wideo.py klatki schemat.html --preset livepanel --czasy <po jednej chwili na krok> --arkusz arkusz.jpg`
     i `vision_analyze`: czy da się przeczytać na telefonie i czy podświetlona ramka, strzałka i wiersz listy mówią to samo;
   - `html_wideo.py pomiar schemat.html --preset livepanel --dlugosc <canvas.duration>`: 0 błędów (kontrast WCAG,
     marginesy, kroje zastępcze).
5. **Film:** `zywy_schemat.py film schemat.html -o out/wideo/<projekt>/schemat.mp4`: około 2 min na 28 s w 4:5,
   z cichą ścieżką AAC (Telegram i komunikatory nie zamieniają go w GIF). Muzyka: `--bez-audio`, potem `film.py`.
6. **Oddanie:** MP4, strona HTML (na stronę firmy osadza `jarvo-web`), `RAPORT.md` ze źródłami liczb, formatem,
   motywem i wynikami kontroli; post i opis przygotowuje `jarvo-studio`.

## Zasady ruchu (skrót `motion-grammar.md`)
- **Układ się nie rusza:** bez kamery i bez budowania krok po kroku; klatka 0 jest już całym schematem.
- **Trzy tempa naraz:** szybko (kropki na strzałkach, wskaźniki pracy), średnio (log, wskaźniki co 1–3 s),
  wolno (kolejny krok co 3–5 s).
- **Jedna prawda:** jedna maszyna `cycle` mówi, co się teraz dzieje; podświetlenie, strzałki, lista i log biorą stan
  z niej, więc wszystkie miejsca mówią to samo.
- **Akcent tylko dla tego, co teraz pracuje:** czerwień Jarva (`ak`) na aktywnej ramce i strzałce, reszta spokojna.
- **Cudze projekty:** przykłady `codex-agents` i `agent-architecture` z live-panel to cudze projekty (autorzy w ich
  `credit`): uczymy się z nich, nie publikujemy. Przerabiany obrazek klienta: zgoda i autor w `credit`.

## Definition of Done
- [ ] każda liczba ze źródłem albo podpisana jako poglądowa; `credit` na ekranie,
- [ ] `sprawdz` kod 0, `pomiar` bez błędów, arkusz klatek obejrzany (`vision_analyze`),
- [ ] MP4 z cichą ścieżką i strona HTML w `out/wideo/<projekt>/`, `RAPORT.md` z wynikami kontroli.
