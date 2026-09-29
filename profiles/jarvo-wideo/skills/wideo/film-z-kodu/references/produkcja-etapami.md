---
source: "Szablon briefu produkcyjnego: athemeroy/awesome-opus-5-5-videos, docs/production-brief.md (CC-BY 4.0, autor: athemeroy), zaadaptowany; wzorzec bramek z briefów @donaldjewkes i repo JohnHeibel/ClaudeAnimationBase (MIT)"
reviewed: "2026-09-29"
---
# Produkcja etapami (filmy > 30 s, flagowe, z postacią albo historią)

Krótkie rolki robisz jednym przebiegiem z pętlą krytyki. Ten plik jest dla filmów, które na to są za duże: tu viralowe
filmy powstawały nie z jednego promptu, tylko z bramek. **Każda bramka kończy się plikiem i oceną; nie przeskakujesz bramek.**

## Bramki
| # | Bramka | Plik | Przejście |
|---|---|---|---|
| 1 | Film w jednym zdaniu (logline) + co widz ma poczuć na końcu | `docs/BRIEF.md` | zgodne z kartą |
| 2 | Przewodnik stylu z referencji (paleta hex, font, faktura, kamera, jak wchodzi i wychodzi tekst; **gramatyka, nie treść**) | `docs/style_guide.md` | 1–3 klatki stylu obejrzane |
| 3 | Lista ujęć na siatce bitów: czas, stan początkowy → akcja → stan końcowy, kamera, tekst, dźwięk | `docs/shotlist.md` | każde ujęcie ma stan końcowy, na który da się wskazać |
| 4 | Stopklatki każdego ujęcia → arkusz → krytyka | `out/stills.png` | 7 osi ≥ 8 na stopklatkach |
| 5 | Animatic 960×540 z roboczym dźwiękiem | `out/animatic.mp4` | rytm: `krytyka.py martwe` czysto, żadnych dłużyzn |
| 6 | Najtrudniejsze 2–4 s w pełnej jakości (kontakt, zasłanianie, szybki ruch) | `out/probka.mp4` | `krytyka.py pasek` bez wyskoków |
| 7 | Pełny render, szlif, dźwięk, miks −14 LUFS | `out/final.mp4` | `kontrola-wideo` + pętla krytyki |
| 8 | Oddanie: film, plakat (poster), arkusz, źródła z README | `out/` | DoD karty |

## Dziennik krytyki (`docs/review_log.md`)
Po każdej rundzie: data, bramka, 7 osi (1–10), 3 największe problemy z czasem, co poprawione. Minimum 3 rundy na bramce 7.

## Podagenci (film > 60 s)
Najpierw `docs/ANIMATION_GUIDE.md`: jeden styl, biblioteka pomocników (sprężyny, kamera, faktura), konwencje nazw.
Potem jeden podagent na rozdział (`delegate_task`), każdy czyta przewodnik i oddaje rozdział z własnym arkuszem.
Ty skleisz rozdziały i robisz krytykę całości (przejścia między rozdziałami, spójność postaci).

## Brief (skrót do wypełnienia)
```
Tytuł / odbiorca / jedno, co ma zrozumieć albo poczuć:
Gdzie wyjdzie; długość; format; fps; język:
Musi być dokładne (nazwy, liczby, logo, fakty):
Wejścia i prawa: | zasób | plik/URL | licencja | jak wchodzi do filmu |
Kto co robi: model (plan, kod, krytyka) / źródło klatek per ujęcie / dźwięk / człowiek (akceptacje):
Ujęcia: | nr, czas | stan początkowy | akcja | stan końcowy | dokładny tekst/fakt |
Ciągłość (postać, produkt, kamera, światło, szew pętli):
Budżet (czas, płatne API) i co zrobić, gdy się skończy:
```
