# Landing JARVO

Statyczna strona (bez buildu, bez CDN): `index.html`, `style.css`, `app.js`, `assets/`, a do SEO i bezpieczeństwa
`.htaccess` (nagłówki, HTTPS, bez www), `robots.txt`, `sitemap.xml`, `llms.txt`, `site.webmanifest`, `favicon.ico`
(pilnuje `tests/test_site.py`). `tools/` to generatory grafiki, nie idą na serwer.
Podgląd: `python3 -m http.server -d site 8080` → http://localhost:8080.
Wdrożenie: `JARVO_FTP_PASS='…' bash scripts/deploy-site.sh` (FTPS na jarvo.pl; zmienne `JARVO_FTP_HOST`,
`JARVO_FTP_USER`, `JARVO_FTP_DIR`, serwer bez FTPS: `JARVO_FTP_PLAIN=1`). Wysyła stronę, pliki SEO/bezpieczeństwa
i `assets/` (bez `*.json`), bez `tools/` i README.

- **Układ 1:1 z makietą** `JARVO-landing-page-koncepcja.png` (1536×1024): na desktopie plansza skaluje się do
  szerokości okna, zawsze mieści się na jednym ekranie (szerokość i wysokość). Telefon (≤ 820 px): też jeden ekran, zamiast sceny przy biurku robot z karty postaci (`tools/robot.mjs`: poza FRONT bez tła). Stoi spokojnie i mruga, nad nim dymek z powitaniem „Hi, I'm JARVO”; tapnięcie = krótki podskok i kolejny tekst. Czysty kontur (krawędź wycinka zjedzona do konturu, równy obrys w CSS).
- **Robot się rusza:** oczy idą za kursorem i mrugają, dłonie stukają, gdy terminal pisze, panele pływają
  z paralaksą, antena i ekran laptopa świecą, z kubka leci para, po panelach przewijają się dane, a czerwonymi kablami płynie energia. Przy `prefers-reduced-motion` wszystko stoi.
- **Warstwy ilustracji** generuje `tools/art.mjs` z grafiki z pakietu marki (tło bez ruchomych elementów
  i osobne sprite'y). Pozycje w `style.css` muszą zgadzać się z `assets/art.json` (pilnuje test).
  Nagłówek „FROM IDEA TO REALITY.” to wektor obrysowany z tej samej grafiki.
- **Kontakt:** stała `CONTACT` na górze `app.js` (e-mail albo adres strony; pusto = zgłoszenia na GitHubie).
- **„Start building”** pyta o system (macOS / Linux / Windows, wykrywa go sam) i daje polecenie:
  `curl … | bash` (macOS, Linux, WSL) albo `irm … | iex` (PowerShell). Instalatory to `install.sh`
  i `install.ps1` w katalogu głównym repo. Adres instalatorów to `BASE` na górze `app.js` (dziś GitHub raw).
  Żeby serwować je z domeny, zmień tę linię i dopisz `install.sh`, `install.ps1` do listy w `scripts/deploy-site.sh`
  (dziś ich nie wysyła).
- Czcionki: DM Sans i JetBrains Mono (SIL OFL 1.1), serwowane lokalnie.
