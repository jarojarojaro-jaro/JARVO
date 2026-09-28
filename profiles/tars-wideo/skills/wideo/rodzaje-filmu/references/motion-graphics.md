# Motion graphics

Ruch jest treścią: showreel, abstrakcja, przejścia, pętla, brand motion, infinite zoom, „pokaż, co potrafisz”.
Nie to: coś ma zostać wyjaśnione → `explainer.md`; hasło jest treścią → `typografia.md`; logo → `logo-intro.md`.

## Wynik
- 8–20 s (pętla do feedu) albo 30 s (showreel); 9:16 lub 1:1 na social, 16:9 na stronę; 30 albo 60 fps.
- Muzyka z licencją albo syntezowana (`anidoodle` music); pętla bez szwu, gdy karta mówi „loop”.

## Silnik
| Styl | Silnik |
|---|---|
| geometria, cząstki, shadery, kolaż, infinite zoom | własny HTML Canvas/WebGL (`kontrakt-html.md`) |
| szybko z szablonów, tekst + kształty | HyperFrames `motion-graphics` |
| rysowany, organiczny | `anidoodle` |
| opener z wyglądem marki | `bang-motion` |
| 39 stylów kina (akwarela, anime, pixel, papier…) | `lemo-opuscar` |

## Struktura
| 15 s | Rytm |
|---|---|
| 0–1 | **Hak ruchem:** coś już leci, rośnie albo pęka od klatki 0 |
| 1–12 | **Łańcuch przemian** co 1–2 s: każda wynika z poprzedniej (match cut, morph, maska, zoom w detal) |
| 12–15 | **Kulminacja** i powrót do klatki 0 (pętla) albo logo |

## Rzemiosło
- Jeden język formalny na film (np. tylko koła i linie, tylko papier, tylko neon) i paleta 3–4 kolorów.
- Nic nie pojawia się znikąd: przejścia wynikają z kształtów (maska, powiększenie, rozpad na cząstki).
- Easing zawsze (ease-out wejście, ease-in wyjście), overlapping action: elementy startują z przesunięciem 2–4 klatek.
- Cięcia i akcenty na taktach muzyki; cisza i bezruch też są rytmem (0,3 s zatrzymania przed dropem).
- Infinite zoom: skala rośnie wykładniczo przy stałej prędkości (czas segmentu ∝ log(przybliżenia));
  następny świat siedzi w „portalu” poprzedniego i przejmuje kadr, gdy go wypełni.
- Motion blur z podklatek (`html_wideo.py … --subklatki 4`) przy szybkim ruchu; ziarno i winieta z umiarem.
- Pętla idealna: stan w `t = DUR` równy stanowi w `t = 0` (sprawdź klatkę pierwszą i ostatnią obok siebie).

## Brief (`out/wideo/src/BRIEF.md`)
```
Cel i emocja (jedno słowo):                     Język formalny i paleta:
Łańcuch przemian (czas → co przechodzi w co):
Muzyka (BPM, takty, licencja):                  Pętla tak/nie, długość, formaty, fps:
```

## Pułapki
- Przypadkowy zbiór efektów bez łańcucha; pięć stylów w 15 s; ruch liniowy (bez easingu).
- Szum i blur, które na telefonie zamieniają się w breję; drobne detale poniżej 1% kadru.
- Losowość bez ziarna (każdy render inny) albo animacja z zegara (klatki gubione przy renderze).

## Kontrola
- Arkusz co 0,5 s + pasek klatek co 0,1 s na przejściach: czy każde przejście wynika z poprzedniego kształtu.
- Klatka pierwsza obok ostatniej (pętla); czytelność na 360 px szerokości (zmniejsz arkusz i obejrzyj).

## Inspiracje
`python3 $HERMES_HOME/scripts/inspiracje.py motion-graphics --ile 3` (albo `--szukaj "infinite zoom"`, `--tag shader`).
