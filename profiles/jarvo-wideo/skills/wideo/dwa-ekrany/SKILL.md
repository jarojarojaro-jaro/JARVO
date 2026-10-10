---
name: dwa-ekrany
description: "Split screen: dwa nagrania w kadrze, przed/po, telefony."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [video, split-screen, comparison, before-after, ffmpeg]
    related_skills: [montaz-nagran, napisy, kontrola-wideo, formaty-wideo, warianty-ab]
  jarvo:
    agent: jarvo-wideo
    autonomy: A1
    reviewed: "2026-10-10"
---

# Dwa ekrany (split screen)

Dwie rzeczy naraz w jednym kadrze: porównanie, przed/po, reakcja, „ja vs kolega”, stara i nowa strona, dwa
ujęcia tej samej chwili. Narzędzie: `$HERMES_HOME/scripts/dwa_ekrany.py` (FFmpeg, ramki i podpisy rysowane kodem,
bez cudzych zdjęć i bez sieci). Sposób pracy za skillem `duo` (HeyGen hyperframes-community-skills, Apache-2.0):
dwa okna, jedna oś czasu, w każdej chwili coś się rusza; samego `duo` nie używamy (cudze zdjęcie bez licencji,
tylko poziom 4:3).

## Kiedy użyć
- „Pokaż obok siebie”, „przed i po”, „porównaj A i B”, „split screen”, „reakcja na nagranie”, „dwa telefony”.

## Kiedy NIE używać
- Jedno nagranie w innym formacie → `montaz-nagran` (`kadr`).
- Więcej niż dwa okna albo animowana plansza porównania → `film-z-kodu`.

## Układy
| Układ | Kiedy | Uwaga |
|---|---|---|
| `gora-dol` | pion 9:16 (TikTok, Reels, Shorts), domyślny dla pionu | każde okno prawie kwadrat: twarz w `--kadr-* x,0.35–0.45` |
| `obok` | poziom 16:9 i kwadrat, domyślny dla nich | w pionie okna są wąskie paski, unikaj |
| `przed-po` | zdjęcia albo nagrania z tego samego miejsca (remont, retusz, strona przed i po) | A = przed z lewej, B = po z prawej, kreska jedzie |
| `telefony` | dwie aplikacje, dwa czaty, dwie wersje strony na telefonie | treść pionowa (nagranie ekranu telefonu), tło `--tlo` |

## Kroki
1. **Plan na piśmie przed renderem:** co robi okno A i okno B w każdej sekundzie. Test pauzy: w każdej chwili
   w co najmniej jednym oknie coś się dzieje (nagranie gra, strona się przewija, kreska jedzie). Dwa stojące
   zrzuty to nie film: zdjęcia tylko w `przed-po` (tam rusza się kreska) albo jako krótki przerywnik.
2. **Materiał:** pliki od właściciela z `/opt/data/jarvo/inbox/`, nagrania ekranu (`demo-strony`), własne filmy.
   Cudzych postów, kont i liczników nie pobieramy ani nie wymyślamy: treść jest właściciela, klienta albo z
   licencją (`material-stock`). Nagranie z ręki → najpierw `montaz.py stabilizuj`, za długie → `montaz.py wytnij`.
3. **Złożenie:**
   ```bash
   python3 $HERMES_HOME/scripts/dwa_ekrany.py A.mp4 B.mp4 -o out/wideo/<temat>/dwa.mp4 \
     --format 9:16 --podpisy "Przed" "Po" [--uklad gora-dol|obok|przed-po|telefony] \
     [--dzwiek auto|a|b|oba|brak] [--sek 12] [--kadr-a 0.5,0.4] [--kadr-b 0.5,0.4] \
     [--kreska "0=0,2=0.5,5=0.5,7=1"] [--tlo "#0e0f13"] [--kolor "#ffffff"]
   ```
   Treść wypełnia okno przyciętą (nigdy rozciągniętą); kadr przesuwasz `--kadr-a/-b`, nie zmieniasz okien.
   Podpisy: 1–3 słowa, w strefie bezpiecznej platformy (skrypt pilnuje sam). Dźwięk z jednego okna (domyślnie
   A); `oba` tylko gdy obie ścieżki mają sens razem (np. reakcja na nagranie).
   Długość: dłuższe nagranie; krótsze trzyma ostatnią klatkę, więc tnij do podobnej długości.
4. **Kontrola:** skrypt wypisuje JSON z `uwagi`: test pauzy (chwile, gdy nic się nie rusza w żadnym oknie)
   → popraw materiał albo skróć. Potem `kadry.py arkusz <wynik> --klatek 6` → `vision_analyze`: twarze i ważne
   rzeczy w oknach (nie ucięte kreską ani ramką), podpisy czytelne, kreska widoczna; `qa_wideo.py <wynik>`.
5. Dalej jak zwykły film: `napisy` (pas napisów nachodzi na dolne okno: w `gora-dol` napisy lektora krótkie),
   `montaz.py glosnosc`, raport z plikiem.

## Zasady
- Nie zmieniaj okien, żeby „zmieściła się” treść: dopasuj treść (kadr, skala w nagraniu ekranu).
- Jedna rzecz porównywana naraz: ten sam kadr, to samo światło, ta sama długość; inaczej widz porównuje szum.
- Kreska podziału zostaje cienka i jednolita; bez drgania, pulsowania i ozdobnych ramek.
- Telefony to rysunek ramki, nie zdjęcie konkretnego modelu: bez logo i nazw producentów.
