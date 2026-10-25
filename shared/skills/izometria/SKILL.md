---
name: izometria
description: "Figury izometryczne ze świeceniem: strona, PNG, film."
version: 1.1.0
author: "Jarvo (szablon i kernel: iso-glow, April Zhu, na iso-figure, Tolga Cohce; MIT)"
license: MIT
metadata:
  hermes:
    tags: [isometric, svg, illustration, icons, glow, interactive, html, animation]
  jarvo:
    autonomy: A0
    reviewed: "2026-10-07"
---

# Izometria: figury ze świeceniem

Klikalna figura izometryczna w jednym pliku HTML: cienka kreska na ciemnym (albo jasnym) panelu, a świeci w kolorze
akcentu tylko to, co żyje (wciśnięty przycisk, zapalony ekran, piętro z włączonym światłem, impuls na kablu).
Czysty SVG bez bibliotek: strona z jedną figurą waży ~40 KB (z krojem ~115 KB) i działa z dysku, bez sieci.

## Kiedy użyć
- **Web:** ilustracja na stronie klienta (nagłówek, „jak to działa”): klikalna kasa, ekspres, maszyna, budynek.
- **Studio:** grafika na social media (PNG), spójna seria ikon izometrycznych dla marki (jedna paleta, `--wszystkie`).
- **Wideograf:** figura z `demo()` nagrana na film: intro, explainer, rolka (styl świecenia pasuje do Fosforu).
- **Schemat usługi:** „jak działa usługa” jako budynek albo urządzenie, w którym zapalają się kolejne etapy.
- **Flota Jarva:** `iso.py flota` sam robi figurę z `fleet.yaml`: wieża z mostkiem Jarva i pokojami agentów, a demo
  to droga zlecenia (Ty → Jarvo → karty dla agentów → ocena → raport). Na nasze materiały: post, strona, film.
  Tę samą figurę właściciel ogląda w HQ (Centrala → Jak działa usługa).

## Kiedy NIE używać
- zdjęcie produktu, realistyczny render, logo i znaki towarowe (nigdy nie rysujesz prawdziwych logo ani sylwetek
  markowych produktów: wymyślone napisy i znaki),
- wykres z danymi (to praca na wykres), długi tekst (figura ma krótkie etykiety),
- pastelowy świat 2.5D z kafelkami i kamerą na film (Three.js): to styl `izometria` w `style-motion` Wideografa
  (wzór `03-isometric`); ten skill to cienka kreska na panelu, świecenie i klik.

## Kroki
```bash
I="$HERMES_HOME/skills/design/izometria/scripts/iso.py"
@@PY@@ "$I" zbuduj fig.js -o out/iso/ekspres.html --tytul "Ekspres"            # nasze materiały (stopka zostaje)
@@PY@@ "$I" zbuduj fig.js -o public/iso/kasa.html --kadr --bez-stopki --akcent "#E4572E" --demo   # strona klienta
@@PY@@ "$I" sprawdz out/iso/ekspres.html --przegladarka                         # zawsze przed oddaniem
@@PY@@ "$I" png out/iso/ekspres.html -o out/iso/ekspres.png --czas 1.6 --rozmiar 1080x1350 --podpis
@@PY@@ "$I" png out/iso/seria.html -o out/iso/ikony.png --wszystkie --przezroczyste --rozmiar 800x800
@@PY@@ "$I" wideo out/iso/ekspres.html -o out/wideo/ekspres.mp4 --dlugosc 6 --rozmiar 1080x1920   # Wideograf
@@PY@@ "$I" flota -o out/iso/flota.html --podpis                               # flota z fleet.yaml (bez fig.js)
@@PY@@ "$I" png out/iso/flota.html -o out/iso/flota.png --czas 7 --rozmiar 1200x1200 --podpis
```
1. **Nazwij wynik figury, zanim narysujesz:** co daje naciśnięcie (napis, liczba, światło, ruch). Figura, na którą
   można tylko patrzeć, to dekoracja: wybierz inny przedmiot albo dodaj działanie.
2. Napisz `fig.js` według `references/kontrakt-figury.md` (kontrakt, kernel, klasy świecenia, czas z api).
   Wzór: `assets/przyklady/ekspres.js` (nasz, po polsku), `assets/iso-glow/assets/examples/` (biurko, wieżowiec).
   Etykiety, podpowiedź (`hint`), odczyt i `aria` po polsku.
3. `zbuduj` (kontrola kodu w środku: kolor wpisany na sztywno, zewnętrzny adres, sieć = błąd), potem
   `sprawdz --przegladarka`: każda figura w Chromium z demo, błędy JS, pusta figura, tekst poza kadrem, za mały
   tekst, nic nie świeci po demo. Popraw każdy błąd i uwagę, zanim oddasz.
4. Obejrzyj PNG (`vision_analyze`): świecenie ma być wyraźne w miniaturze, napisy czytelne, nic nie wystaje.
5. Oddaj: plik linią `MEDIA:<ścieżka>` (HTML, PNG, film), dużo plików linkiem
   `@@PY@@ "@@REPO_DIR@@/scripts/jarvo_link.py" <katalog>`. Powiedz, co kliknąć albo nacisnąć.

## Opcje
- `--paleta ember` (ciepłe, przedmioty) | `city` (miasto, budynki); `--akcent` = kolor marki klienta (z tokenów marki
  albo strony); skrypt rozjaśnia go na ciemnym panelu i przyciemnia na jasnym, gdy inaczej by zginął (kontrast ≥ 3:1).
  Kilka `--akcent "Nazwa=#hex"` = kilka kolorów do wyboru w przełączniku.
- `--motyw auto|ciemny|jasny` (strona; `auto` = jak system widza), PNG i film domyślnie `ciemny`.
- `--kadr`: sama figura na całej stronie (bez paska, listy i stopki) do `<iframe>` na stronie klienta;
  `--podpis` dokłada „Rys. N · nazwa” i odczyt; `--demo`: strona otwiera się zapalona.
- Parametry adresu nadpisują ustawienia: `?kadr`, `?podpis`, `?motyw=jasny`, `?akcent=cyan`, `?tlo=0`, `?figura=id`, `?demo`.
- `png --czas S`: stan w sekundzie S demo (0 = stan startowy); `--skala 2` ostrzej; rozmiary: 1080x1080 post,
  1080x1350 IG, 1080x1920 story, 1200x630 OG.
- `flota`: `-o plik.js` = sama figura (do strony z innymi figurami), `-o plik.html` = od razu strona (opcje jak
  w `zbuduj`, domyślnie paleta `city`); `--przyklad sherlock,web,studio` = kto pracuje w demo (domyślnie pierwszych
  trzech z rejestru); demo trwa ~6,5 s, więc PNG z `--czas 7`, film `--dlugosc 8`.
- `wideo` woła `html_wideo.py` Wideografa (`--preset jarvo`, render klatka po klatce w kilku przeglądarkach).
  Inny agent zleca film Wideografowi kartą (WEJŚCIA: strona .html, id figury, długość, format).

## Na stronie klienta (Web)
```html
<iframe src="/iso/kasa.html" title="Kasa: kliknij przyciski" loading="lazy"
        style="width:100%;aspect-ratio:4/3;border:0;background:transparent"></iframe>
```
Zbuduj z `--kadr --bez-stopki --akcent <kolor marki>`; tło przezroczyste: `src="/iso/kasa.html?tlo=0"`. Dodaj PNG
z `png` jako obraz zastępczy (OG, `<noscript>`), a figurę przepuść przez listę kontrolną strony (lighthouse).

## Zasady
- Kolory tylko przez tokeny (`var(--accent)`, `var(--line)`…): inaczej paleta marki i jasny motyw się sypią.
- Czas tylko z api (`api.after`, `api.every`, `api.loop(ts)`, `api.now()`), nigdy `setTimeout` ani `Date.now`
  wprost: tylko wtedy PNG w chwili t i film wychodzą zawsze tak samo.
- Stopka „Made with ISO-GLOW ↗”: zostaje na naszych materiałach (Jarvo, HQ, nasze social); na pracach dla klientów
  `--bez-stopki` (licencję MIT i autorów podajemy w `docs/SOURCES.md`, plik `LICENSE` jedzie ze skillem). Nigdy
  „Made by …”: praca należy do właściciela albo klienta.
- Bez zewnętrznych skryptów, fontów i adresów (kontrola to blokuje); krój JetBrains Mono (OFL) jest w pliku.

## Definition of Done
- [ ] `sprawdz --przegladarka` bez błędów i uwag (albo uwaga uzasadniona w odpowiedzi),
- [ ] PNG obejrzany: świecenie wyraźne, polskie znaki i napisy czytelne,
- [ ] wynik oddany (`MEDIA:` albo link) z jednym zdaniem: co to jest i co kliknąć; dla klienta bez stopki.
