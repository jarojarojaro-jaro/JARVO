# Landing JARVO

Statyczna strona (bez buildu, bez CDN): `index.html`, `style.css`, `app.js`, `assets/`.
Podgląd: `python3 -m http.server -d site 8080` → http://localhost:8080.

- **Układ 1:1 z makietą** `JARVO-landing-page-koncepcja.png` (1536×1024): na desktopie plansza skaluje się do
  szerokości okna, zawsze mieści się na jednym ekranie (szerokość i wysokość). Telefon (≤ 820 px): też jeden ekran, zamiast sceny przy biurku sam robot z karty postaci (`tools/robot.mjs`), który oddycha, mruga i w dymku prowadzi tę samą rozmowę co terminal.
- **Robot się rusza:** oczy idą za kursorem i mrugają, dłonie stukają, gdy terminal pisze, panele pływają
  z paralaksą, antena i ekran laptopa świecą, z kubka leci para, po panelach przewijają się dane, a czerwonymi kablami płynie energia. Przy `prefers-reduced-motion` wszystko stoi.
- **Warstwy ilustracji** generuje `tools/art.mjs` z grafiki z pakietu marki (tło bez ruchomych elementów
  i osobne sprite'y). Pozycje w `style.css` muszą zgadzać się z `assets/art.json` (pilnuje test).
  Nagłówek „FROM IDEA TO REALITY.” to wektor obrysowany z tej samej grafiki.
- **Kontakt:** stała `CONTACT` na górze `app.js` (e-mail albo adres strony; pusto = zgłoszenia na GitHubie).
- **„Start building”** pyta o system (macOS / Linux / Windows, wykrywa go sam) i daje polecenie:
  `curl … | bash` (macOS, Linux, WSL) albo `irm … | iex` (PowerShell). Instalatory to `install.sh`
  i `install.ps1` w katalogu głównym repo. Adres instalatorów to `BASE` na górze `app.js`: po podpięciu
  domeny zmieniasz jedną linię.
- Czcionki: DM Sans i JetBrains Mono (SIL OFL 1.1), serwowane lokalnie.
