# plan.json: format planu filmu (`film.py`)

Ścieżki względne liczą się od katalogu roboczego karty (albo od katalogu planu). Klucze po polsku, bez ogonków.

```json
{
  "tytul": "Kawa: 3 mity",
  "formaty": ["9:16"],
  "lektor": {"glos": "pl-PL-MarekNeural", "tempo": "+5%"},
  "napisy": {"styl": "karaoke", "akcent": "#FFD400", "font": "Inter", "pozycja": "dol", "wielkie": true},
  "muzyka": {"plik": "losowa", "glosnosc": 0.12},
  "marka": {"nazwa": "ziarno", "logo": "out/wideo/src/logo.png", "pozycja": "gora-prawo"},
  "przejscie": "ciecie",
  "sceny": [
    {"tekst": "Myślisz, że espresso ma najwięcej kofeiny?", "ujecie": {"stock_id": "pexels:3191820"},
     "tekst_ekranowy": "3 mity o kawie"},
    {"tekst": "Kubek przelewu ma jej nawet dwa razy więcej.", "ujecie": {"stock": "pour over coffee", "dopasuj": "rozmyte"}},
    {"tekst": "Ciemne palenie nie znaczy mocniej.", "ujecie": {"plik": "out/wideo/src/ai-palenie.mp4", "od": 1.5}},
    {"tekst": "Zapisz, zanim zapomnisz.", "ujecie": {"kolor": "#1B2A41"}, "tekst_ekranowy": "ZAPISZ"}
  ],
  "warianty": [
    {"nazwa": "B", "lektor": {"glos": "pl-PL-ZofiaNeural"}, "sceny": {"1": {"tekst": "Espresso to bomba kofeinowa? Nie."}}}
  ]
}
```

## Pola
| Pole | Wartości | Domyślnie |
|---|---|---|
| `tytul` / `slug` | nazwa filmu (slug = nazwa plików) | `film` |
| `formaty` | lista z `9:16`, `16:9`, `1:1`, `4:5` | `["9:16"]` |
| `lektor` | `{glos, tempo, glosnosc, wysokosc}`; `{plik: "nagranie.mp3"}` = własny lektor (napisy z transkrypcji); `false` = bez lektora | Marek, `+0%` |
| `napisy.styl` | `karaoke` (aktywne słowo w kolorze akcentu) · `zwykle` · `brak` | `karaoke` |
| `napisy` (reszta) | `font`, `font_plik` (TTF/OTF marki), `kolor`, `akcent`, `obrys`, `pozycja` (`dol`/`srodek`/`gora`), `wielkie`, `rozmiar` (mnożnik) | Inter, biały, #FFD400 |
| `muzyka` | `{plik: ścieżka | "losowa" | "brak", glosnosc: 0–1, katalog}`; „losowa” = biblioteka `@@KNOWLEDGE_DIR@@/wideo/muzyka/` albo `brands/<marka>/muzyka/`, a gdy pusta: podkład CC0 z biblioteki edytora (`projekt.py dzwieki --muzyka`) | brak |
| `marka` | `{nazwa, logo, pozycja: gora-prawo | gora-lewo | dol-prawo | dol-lewo}` | brak logo |
| `przejscie` | `ciecie` · `przenikanie` (0,35 s) | `ciecie` |
| `sceny[].tekst` | zdanie lektora (1–2 zdania, ≤ 22 słowa) | wymagane z lektorem |
| `sceny[].czas` | minimalna długość sceny w s (bez lektora: długość) | z lektora |
| `sceny[].glos` | inny głos tylko w tej scenie (dialog) | głos planu |
| `sceny[].tekst_ekranowy` | duży napis u góry na czas sceny (hook, liczba, CTA) | brak |
| `sceny[].ujecie` | dokładnie jedno: `stock` (zapytanie), `stock_id` (`pexels:ID` / `pixabay:ID`), `plik` (wideo albo zdjęcie), `kolor` (#RRGGBB) | wymagane |
| `ujecie` (opcje) | `typ: "zdjecie"` (stock zdjęć), `od` (start w pliku, s), `ruch` dla zdjęć: `zoom` · `oddal` · `panorama` · `brak`, `dopasuj`: `przytnij` · `rozmyte` (całe ujęcie na rozmytym tle), `koniec` (klip krótszy od sceny): `petla` · `stop` (ostatnia klatka do końca sceny; animacje z `film-z-kodu`) | `zoom`, `przytnij`, `petla` |
| `warianty[]` | `{nazwa, …nadpisania planu}`; `sceny` jako `{"1": {...}}` (numer sceny od 1) albo pełna lista | brak |

## Zasady
- `stock` (zapytanie) wybiera automatycznie najlepszy wynik; do finału wpisuj `stock_id` po obejrzeniu (`dobor-ujec`).
- Zapytania stock po angielsku dają więcej trafień; 2–4 słowa, konkretny obiekt i ujęcie („coffee beans macro”).
- Zdjęcia dostają ruch kamery automatycznie (Ken Burns); statyczna scena > 4 s nuży.
- Nie wpisuj tekstu do obrazu AI: tekst idzie przez `tekst_ekranowy` albo napisy (ostre, poprawne litery).
  Bez emoji w napisach i tekstach ekranowych (renderer napisów pokazuje je jako puste kratki).
- Bez klucza stock: `plik` (AI, własne) i `kolor`; `film.py sprawdz` powie, czego brakuje.

## Polecenia
```bash
python3 $HERMES_HOME/scripts/film.py sprawdz out/wideo/src/plan.json
python3 $HERMES_HOME/scripts/film.py render out/wideo/src/plan.json --szkic
python3 $HERMES_HOME/scripts/film.py render out/wideo/src/plan.json [--format 9:16,16:9] [--wariant B | --wszystkie]
python3 $HERMES_HOME/scripts/film.py lektor "Tekst." -o out/wideo/src/lektor.mp3 --glos pl-PL-ZofiaNeural
python3 $HERMES_HOME/scripts/film.py glosy
python3 $HERMES_HOME/scripts/film.py cache [--starsze-niz 14]
```
