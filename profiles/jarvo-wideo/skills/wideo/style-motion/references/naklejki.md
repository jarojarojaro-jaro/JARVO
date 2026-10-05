# Naklejki z grubym obrysem (wzór `19-paperclip`)

Wycięte zdjęcia przedmiotów z grubą białą krawędzią jak naklejki, płaskie ikony i dokładne wykresy leżą na jednym
wielkim płótnie, a kamera jedzie od punktu do punktu. Poznasz go po białym obrysie 10 px, cieniu pod naklejką
i spokojnym szaroniebieskim tle w kropki.
Wzór: okładka `$MGSTYLES/videos/19-paperclip.jpg`, kod `$MGSTYLES/demos/19-paperclip/` (MIT), ocena jury 7,71;
1920×1080, 30 kl./s, 10 s. Wzór nie rusza w Jarvie: jego naklejki (zdjęcia) nie mają źródła i nie są instalowane.
Oglądasz okładkę i kod `index.html`: L54–96 (pomocniki, „klap”, kamera), L209–305 (tablica, licznik, wykres),
L307–359 (mapa i trasy), L392–452 (karta końcowa).

## Do czego
- Explainer B2B „co jest w środku”: producent okien, elektroniki, kosmetyków (skład), 16:9, 15–30 s.
- Sklep internetowy: produkt rozłożony na części z podpisami i ceną, 9:16 albo 1:1, 15 s.
- Liczby roku firmy albo gminy (raport roczny): licznik, słupki, mapa, 16:9, 20–30 s.
- Pochodzenie i dostawy: mapa Polski z trasami (piekarnia: mąka z Kujaw; palarnia: kawa z 3 krajów), 16:9, 15–20 s.
- Wersja „notes”: naklejki klienta na papierze z `plotno.js` dla kawiarni, eventu, młodej marki, 9:16, 10–15 s.

## Nie do
- Emocje, nastrój marki, luksus: `zorza-szklo.md` albo `morph.md`. Same hasła bez liczb i zdjęć: `plaski-wektor.md`.
- Stare zdjęcia, ironia, ręczne cięcie i raster: `kolaz.md`.

## Cechy stylu (sprawdzalne)
- Naklejka: biały obrys 10 px (prompt 8–12), wygładzony; zdjęcie na karcie: biała ramka 9 px, promień rogu 6 px.
- Cień od uniesienia L (0–1): `drop-shadow(0 (6+34L)px (10+34L)px rgba(22,34,46,.26−.08L))`.
- „Klap” w 0,2 s: skala 1 + 0,3·(1 − p²), obrót 6° → 0, potem drganie 4,5 Hz z tłumieniem 10.
- Jedno płótno świata 2400×5900 px (pionowy pas; prompt mówi 6000×3000), jedna kamera. Lot po łuku zoomu
  (`d3.interpolateZoom`, rho 0,85 lot, 1,25 odjazd), krzywe lotu `bez(.62,0,.22,1)`, odjazdu `bez(.5,0,.08,1)`.
- Tło #E9EEF2 z kropkami #C5CFD8 co 48 px. Paleta wzoru (role): tusz #25313D, szary #8C9AA8, karta #F7F9FB,
  tekst #5E6D7B, linia #CDD6DE, jeden akcent #FF5A36; razem 2–3 kolory + akcent.
- Linie odniesienia rosną od zera (`pathLength=1`), etykieta na końcu. Licznik 10 → 70 z easeOutCubic, kafelki
  zapalają się z krzywą 1 − ∛(1 − p); suma kategorii = licznik (23+16+12+11+8 = 70), słupki w skali.
- Mapa: trasy to krzywe kwadratowe z wygięciem min(260, 0,35·L), po 3 paczki na trasę; kraje źródłowe #8C9AA8.
- Karta końcowa: liczba Inter 900, 400 px, z białym obrysem 30 px (`paint-order: stroke`), pod nią mały podpis.
- Nowy element co 0,5–1 s; poza końcem nic nie stoi dłużej niż 1,5 s.

## Technika
- DOM + SVG jak wzór (tekst w DOM `pomiar` czyta sam): świat = jeden `div` przesuwany jedną macierzą CSS.
  Kamera z `demos/19-paperclip/index.html` (`cam`, `projC`, `camFrom`, `worldM`, L74–96) z komentarzem
  `// za mg-styles-15 (MIT), demos/19-paperclip/index.html`; d3 z `/_lib/d3/dist/d3.min.js` (po `instaluj mg`).
- Naklejki tylko ze zdjęć klienta wyciętych z tła (PNG z przezroczystością) albo ze stocku z darmową licencją
  (`material-stock`); bez zdjęć rysowane kształty SVG. Zdjęć wzoru nigdy.
- Obrys w stronie: `rimmed(img, r)` z `demos/06-collage/index.html` (L78–83: 28 przesuniętych kopii + `source-in`)
  z r = 10 i bielą #FFFFFF, raz przed `__ready`. Wcześniej czysta maska bez okruchów i dziur, bo obrys je powieli.
- „Klap”, drganie i cień: `slap`, `wob`, `shadow` (L54–73, czyste funkcje); siła z charakteru marki (`ruch.js`),
  np. `zabawny` amp 0,3, `zaufanie` 0,12. Inne wejścia `ladowanie(t, t0, CH)`.
- Cień wpiecz w canvas naklejki (`shadowBlur` przy rysowaniu): filtr CSS na każdej naklejce i pełnoekranowy filtr
  SVG wzoru robią render bardzo wolnym. Filtr na żywo najwyżej na naklejce, która właśnie leci.
- Rozmycia kamery `camBlur` (L565–581, filtr SVG) nie przenoś. Lot kamery ≥ 0,6 s z łagodną krzywą i nie szybciej
  niż 1,5 szerokości kadru na sekundę (`ruch-i-kompozycja.md`, rozdz. 5). `rozciagniecie(v)` z `ruch.js` tylko
  na tym, co leci samo (część, wielka liczba), zamiast rozmytej liczby z okładki wzoru.
- Tło: kropki CSS `radial-gradient` co 48 px albo canvas w świecie z `papier(g, w, h, { kolor: '#EEF1F4',
  zab: 0.06, chmury: 0.03 })`; wersja „notes”: kremowy `papier` + `winieta(g, W, H, { sila: 0.12 })`.
- Mapa: geometria z licencją (Natural Earth, domena publiczna) wpisana do RAPORT.md; plik mapy wzoru nie ma opisu.
- Kroje: Inter 800–900 z `font-feature-settings: 'tnum'` (liczby), Montserrat albo League Spartan 800 (nagłówki);
  chińskie kroje wzoru odpadają. Pomiary DOM (`offsetWidth`, długość tekstu) raz przed `__ready`, nie w klatce
  (wzór mierzy leniwie i dlatego robi rozgrzewkę `renderAt(7.2)`).

## Rytm (10 s wzoru → film klienta)
| Czas | Co się dzieje |
|---|---|
| 0–0,9 | Hak: naklejka produktu „klap” w 0,16 s, tytuł w 2 wierszach, podkreślenie akcentem 0,62–0,92 |
| 1,25–2,8 | Lot kamery w dół (0,65 s); części wylatują co 0,1 s, linie odniesienia i etykiety |
| 2,9–4,3 | Siatka kafelków (składniki, cennik, oferta); licznik rośnie, kafelki zapalają się kaskadą |
| 4,4–5,6 | Kafelki składają się w wykres słupkowy (ten sam kształt idzie dalej) |
| 5,7–6,45 (64%) | Mapa, naklejki pochodzenia, trasy; 0,2 s wstrzymania kamery, kulminacja: pinezka celu |
| 7,0–7,9 | Odjazd: całe płótno okazuje się ekranem telefonu (albo opakowaniem, kartką notesu) |
| 7,9–10 | Liczba odkleja się i spada (8,14), nagłówek 8,3, źródło danych; kadr stoi od ok. 8,9 s |

- 15–30 s: każdy rozdział (rozkład, liczby, mapa, puenta) dłuższy o 2–4 s, nowy element nadal co 0,5–1 s;
  przy 30 s pasek rozdziałów na dole (01 … 04).
- 9:16: nowy układ świata (sekcje jedna pod drugą) i nowe klucze kamery; ramka telefonu z odjazdu pasuje do pionu
  wprost. Wzór ma świat i środek rzutu (960/540) na sztywno.

## Dźwięk
- Spokojny podkład do explainera ok. 118 BPM (marimba, czyste bębny): `muzyka-pozytywna` albo `muzyka-reklama`.
- „Klap” naklejki: `thump` + `pop` (vol 0,8); odklejenie `kartka`; części `click` co 0,1 s.
- Licznik: `tick` na zapalony kafelek (najwyżej 12 na sekundę); wykres krótki `whoosh`; trasy cichy `chirp`.
- Lot kamery: `whoosh` w chwili największej prędkości; pinezka `chime`; przed odjazdem `riser`, upadek liczby
  `uderzenie-niskie` z biblioteki; całość −14 LUFS.

## Pułapki
- Zdjęcia wzoru (telefon, bateria, płytka, minerały) nie mają źródła: nigdy w filmie, nawet „na chwilę”.
- Obrys na wycięciu z frędzlami albo dziurami daje białą obwódkę wokół każdego okrucha. Najpierw czysta maska.
- Wykres niezgodny z liczbą (słupki nie w skali, suma ≠ licznik) widz zauważy; liczby od klienta, źródło w podpisie.
- Za gęsto: nowy element na każdym bicie, ale w kadrze najwyżej 3 grupy (`ruch-i-kompozycja.md`, rozdz. 3).
- Prompt każe płótno 6000×3000, kod ma 2400×5900: liczy się kolejność punktów i ciągłość lotu, nie rozmiar.

## Kontrola
- `html_wideo.py klatki out/wideo/src/index.html --preset jarvo --czasy 0.3,2,3.5,5,6.45,8.2,9.8
  --arkusz out/wideo/arkusz.jpg`: w każdej klatce jeden bohater i ta sama biel obrysu.
- Obrys 10 px ± 2 na każdej naklejce (zmierz na klatce 1:1), cień miękki, bez ciemnych krawędzi.
- Liczby: licznik = suma kategorii = wysokości słupków; sprawdź w kodzie i na klatce.
- `html_wideo.py pomiar out/wideo/src/index.html --preset jarvo --dlugosc 15`: czas czytania, tekst nie pod UI.
- Ostatnia klatka: liczba i nagłówek czytelne na 360 px szerokości; kadr stoi ≥ 0,8 s.
