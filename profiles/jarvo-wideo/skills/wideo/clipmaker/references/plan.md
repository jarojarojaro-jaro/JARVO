# plan.json: schemat

Czasy w sekundach **źródła** (z `transkrypcja.txt`: `[mm:ss.s–mm:ss.s]`, czyli minuty × 60 + sekundy).
`klipy.py sprawdz` pilnuje pól i zakresów; czego plan nie poda, bierze wartość domyślną.

```json
{
  "zrodlo": "/opt/data/jarvo/inbox/2026-09-30/podcast.mp4",
  "format": "9:16",
  "styl": {
    "napisy": "karaoke",
    "hl": "#FFE14D",
    "tytul": true,
    "tytul_s": 3.0,
    "tnij_pauzy": 0.6,
    "bez_wtracen": true,
    "punch": true,
    "kadr_auto": true,
    "muzyka": null,
    "muzyka_glosnosc": 0.12
  },
  "rolki": [
    {
      "slug": "3-bledy-w-cenach",
      "tytul": "Tracisz marżę?",
      "taktyka": "liczba na start",
      "segmenty": [{"od": 754.2, "do": 781.9}],
      "oceny": {"hook": 8, "samodzielnosc": 9, "wartosc": 8, "emocja": 7, "puenta": 8, "udostepnienie": 7},
      "dlaczego": "konkretna lista z liczbami, zamyka się puentą",
      "opis": "Trzy błędy, przez które zarabiasz mniej niż konkurencja.",
      "hashtagi": ["#biznes", "#ceny", "#sprzedaż"]
    }
  ]
}
```

| Pole | Co | Domyślnie |
|---|---|---|
| `format` | `9:16` (1080×1920) albo `16:9` (1920×1080); także w rolce, gdy jedna ma być inna | `9:16` |
| `styl.napisy` | `karaoke` (aktywne słowo w kolorze `hl`), `zwykle` (bez podświetlenia) albo `null` (bez napisów) | `karaoke` |
| `styl.tytul`, `tytul_s` | tytuł-hook z rolki na górze przez pierwsze sekundy | `true`, 3 s |
| `styl.tnij_pauzy` | wycina pauzy dłuższe niż tyle sekund (zostaje oddech 0,12 s); `null` = bez cięcia | 0,6 |
| `styl.bez_wtracen` | wycina „yyy”, „eee”, „mmm” | `true` |
| `styl.punch` | co drugie ujęcie po cięciu przybliżone ×1,12 (ukrywa skok obrazu) | `true` |
| `styl.kadr_auto` | segment bez `fx`/`fy` kadrowany na twarz (`twarze.py`); `false` = środek kadru | `true` |
| `styl.muzyka` | plik muzyki pod mową (licencja w KLIPY.md), głośność `muzyka_glosnosc` | brak |
| `rolki[].slug` | a-z, 0-9, „-”, do 40 znaków; nazwa pliku `klip-N-<slug>.mp4` | — |
| `rolki[].segmenty` | 1–3 fragmenty źródła: `od`, `do`, kadr `fx`/`fy` (0–1, punkt skupienia; tylko gdy nie twarz), `zoom` (1–3) | kadr na twarz; bez twarzy fx 0,5, fy 0,4 (pion) |
| `rolki[].tytul` | tytuł-hook na ekranie, ≤ 6 słów; nie powtarza pierwszego zdania mowy (`sprawdz` ostrzega) | — |
| `rolki[].taktyka` | taktyka hooka ze skilla `hooki` (np. „pod prąd”, „historia od środka”); trafia do KLIPY.md | — |
| `rolki[].oceny` | 6 osi z master promptu | — |

**Granice segmentów.** `od` albo `do` w środku słowa `zbuduj` dosuwa do przerwy obok (słowo zostaje, gdy jego środek
jest w segmencie; zapas ciszy to połowa przerwy, najwyżej 0,35 s przed i 0,45 s po słowie). Plan zostaje bez zmian,
a czasy po dosunięciu są w projekcie (`clipmaker.granice`) i w KLIPY.md. Skąd kadr segmentu, mówi
`clipmaker.kadr`: `mowiacy` (kilka osób, kadr za tą, która mówi), `twarz`, `plan` (fx/fy z planu), `srodek`. `sprawdz` ostrzega też, gdy dwie rolki
dzielą ponad 20% materiału źródła albo gdy przy nagraniu ≥ 10 min wszystkie (≥ 3) rolki są z jednej połowy.

Poprawka po zbudowaniu: zmień plan i `klipy.py zbuduj plan.json --tylko <slug>`. Rolka zmieniona już w edytorze HQ
→ `projekt.py` na jej projekcie (zbuduj nie nadpisze pracy człowieka bez `--nadpisz`).
