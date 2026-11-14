---
name: lejek
description: "Lejek jarodev: dodaj, status, lista, liczby, retencja."
version: 0.1.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [sales, pipeline, leads, gdpr]
    related_skills: [fb-grupy, mapy-firmy, oferta-szkic, raport-dnia]
  jarvo:
    agent: jarvo-jarodev
    autonomy: A1
    reviewed: "2026-11-14"
---

# Lejek jarodev

Jedno miejsce prawdy o tym, z kim rozmawiamy i na jakim etapie. Każdy wpis z grup FB, Map, audytu albo portalu idzie
przez `lejek.py`: skrypt pilnuje duplikatów, statusów, zgody, kanału i retencji, więc tego nie robisz w głowie.

```bash
L="$HERMES_HOME/scripts/lejek.py"; K="@@WORKSPACES_DIR@@/jarvo-jarodev/lejek"
@@PY@@ "$L" --katalog "$K" init
```

## Kiedy użyć
- nowa osoba albo firma z sygnałem (prośba o stronę, firma bez strony, słaba strona),
- zmiana etapu (szkic gotowy, „tak” właściciela, wysłane, odpowiedź, klient, odpada), liczby do raportu.

## Kiedy NIE używać
- leady B2B z rejestrów (KRS, CEIDG, przetargi) → to `jarvo-lowca` przez Jarva.

## Wejścia
| Wejście | Wymagane | Jeśli brak |
|---|---|---|
| źródło (`fb-grupa`, `fb-post`, `mapy`, `audyt`, `portal`, `polecenie`, `inne`) | tak | ustal z kontekstu |
| link do posta, wizytówki w Mapach albo strony | dla osoby tak | firma bez linku: nazwa + `--miasto` |
| potrzeba (czego szuka / co poprawić) | tak | nie dodawaj wpisu bez powodu |

## Kroki
1. Dodaj: `@@PY@@ "$L" --katalog "$K" dodaj --zrodlo fb-grupa --rodzaj osoba --nazwa "<wyświetlana nazwa>"
   --link <link do posta> --potrzeba "<czego szuka, jej słowami>" --data <dzień posta>`.
   Firma: `--rodzaj firma --miasto <miasto>` i link wizytówki albo strony. Odpowiedź `duplikat` = wpis już jest.
   - ✅ Osoba z posta: tylko link, wyświetlana nazwa, potrzeba i data. Telefon albo e-mail w polach = kod 2 (RODO).
2. Status: `@@PY@@ "$L" --katalog "$K" status L-0007 szkic --uwaga "szkic w out/szkice/L-0007.md"`.
   - `zaakceptowany` tylko z `--zgoda "„tak” właściciela w rozmowie 14.11 o 10:20"` albo z linią karty
     `ZGODA WŁAŚCICIELA`; bez tego skrypt odmawia (kod 3).
   - `wyslany` z `--kanal`: osoba z FB `fb-komentarz` albo `fb-wiadomosc`; firma z Map albo audytu tylko
     `list`, `osobiscie` albo `odpowiedz` (sama się odezwała). Mail, telefon, SMS, formularz do takiej firmy = kod 3
     (art. 398 PKE, `references/prawo.md`).
3. Lista i liczby: `lista --status szkic`, `stats --json` (czeka na zgodę, do wysłania, konwersja).
4. Retencja (codziennie robi ją `poranek.py`): `retencja --dni 90` pokazuje, `--wykonaj` usuwa osoby bez kontaktu.
5. Limity dnia: przed każdą grupą, komentarzem, postem, firmą z Map i audytem `licz <rodzaj> --limit <z zrodla.yaml>`;
   kod 3 = limit wyczerpany, koniec tej czynności na dziś.

## Wyjścia
- `lejek/lejek.json` (źródło prawdy), `lejek/lejek.csv` (eksport), `lejek/limity.json` (liczniki dnia).

## Definition of Done
- [ ] każdy nowy wpis ma źródło, datę i potrzebę; zero duplikatów,
- [ ] każda zmiana na `zaakceptowany` ma zapis zgody, każda wysyłka kanał,
- [ ] raport podaje liczby z `stats`, nie z pamięci.

## Typowe błędy
- Wpis „na zapas” bez potrzeby → nie dodawaj; lejek to ludzie i firmy z sygnałem, nie książka telefoniczna.
- Zmiana statusu ręcznie w pliku → nigdy; tylko `lejek.py` (historia i zgody).

## Wiedza
- `references/prawo.md`: art. 398 PKE, RODO dla danych z postów, retencja, czego nie wolno.
