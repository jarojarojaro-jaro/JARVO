# Changelog: jarvo-web

## Niewydane
- `seo_check.py` 1.1: każda nowa strona ma sprawdzone 8 rzeczy: obraz OG (bezwzględny adres, HTTP 200, `image/*`,
  1200×630 z nagłówka pliku) i `twitter:card`, strona 404 (losowy adres musi dać 404, 200 = „soft 404”), title
  i description inne na każdej podstronie, landmarki (jeden `<main>`, `<header>`, `<nav>`, `<footer>`), `alt="TODO"`
  jako błąd, canonical bezwzględny na tym samym hoście, `robots.txt` (także odpowiedź HTML zamiast pliku), `/llms.txt`,
  sitemap (także z wpisu `Sitemap:`). Brak canonical, `twitter:card`, robots, sitemap i llms.txt to teraz błędy.
  Nowe tryby: `--dir dist` (cały build bez sieci: duplikaty title, description i canonical, `404.html`, pliki
  w katalogu, strony poza sitemapą, obraz OG z dysku) i `--podglad` (noindex i canonical na domenie produkcyjnej to
  info, obraz OG sprawdzany na adresie podglądu). `nowa-strona` 1.4.0: `site` i `@astrojs/sitemap`, `robots.txt`,
  `llms.txt`, `404.astro`, `og.png`, landmarki w layoucie, DoD z `--dir` i `--podglad`. Lista widoczności 19 → 23
  punkty, próg description wszędzie 70–160 (zalecane 140–160), rubryka blokuje brak 404/sitemap/robots/llms,
  duplikaty title i description oraz brak `<main>`. Eval `web-new-site-seo`.
- `security_check.py url` wykrywa publiczne mapy źródeł skryptów strony (komentarz `sourceMappingURL`, nagłówek
  `SourceMap`, plik `<skrypt>.map` obok, mapa wbudowana `data:`): mapa z `sourcesContent` odtwarza czytelny kod frontu
  (ŚREDNIE), sekret w odzyskanym kodzie to KRYTYCZNE, mapa bez kodu NISKIE. Strona SPA odpowiadająca na `.map` swoim
  HTML-em to nie mapa. `repo` zgłasza `productionBrowserSourceMaps: true`. Skill `bezpieczenstwo-aplikacji` 1.2.0.
- Skill `inspiracje-stron` i serwer MCP `inspo` (katalog Inspo: 832 prawdziwe strony): przed projektem strony lub landingu 3–5 stron referencyjnych z branży i sekcja „Inspiracje” w `out/PLAN.md` (co bierzemy, czego nie; nic kopiowanego). Krok w `nowa-strona` (2) i `landing-produktowy`, punkt „Ważne” w rubryce, eval `web-inspiracje-nieruchomosci`.
- Mapa 18 polskich branż na filtry Inspo z zapytaniem po angielsku i policzonym pokryciem (`references/branze.md`). Branża słabo pokryta (nieruchomości, gabinety, salony, kancelarie…) → własna baza w skarbcu `inspiracje/strony/<branża>/<domena>` (karta strony, `DESIGN.md`, zrzuty tylko wewnętrznie) przez `brand_extract.sh --kit` i `screenshots.cjs`.
- MCP `inspo`: healthcheck robi prawdziwe `search_screens` w okrojonym środowisku jak Hermes (samo `initialize` przechodziło, gdy katalog się nie pobrał), a serwer dostaje `NODE_EXTRA_CA_CERTS` z systemowym zbiorem certyfikatów (bez tego za proxy z własnym CA: `SELF_SIGNED_CERT_IN_CHAIN`).
- MCP `inspo`: Nutlope/inspo (MIT), `inspo-mcp` 0.1.16 z obrazu, lokalnie po stdio, `lazy` (znika po 15 min bezczynności), `trust: untrusted`, 6 z 15 narzędzi w schemacie (`tools.include`), miniatury jako pliki, sufit 5000 tokenów; bez hostowanego endpointu i bez `TOGETHER_API_KEY`. Hub agenta w skarbcu wymienia serwery MCP.
- SOUL bez linii „dane, nie polecenia” (jest w zasadzie 8 protokołu w tym samym prompcie).
- Poza zakresem: aplikacje mobilne i decyzja „aplikacja czy PWA” należą do Twórcy aplikacji (`jarvo-mobile`); PWA, pliki `.well-known` i baner aplikacji na stronie zostają u Weba.
- Bezpieczeństwo aplikacji 1.1: lista kontrolna 26 punktów (nowe: własność danych na dwóch kontach, CSRF, wygasanie sesji, prywatne buckety, limity endpointów AI i wydatków, prompt injection, model z narzędziami/SQL, kopie zapasowe z próbą odtworzenia) i przepisy per stos. `security_check.py`: `url` szuka kluczy serwerowych w JS wysyłanym do przeglądarki (anon Supabase pomija), `repo` sprawdza zależności w npm i PyPI (nieistniejące, różne jedną literą od popularnych, nowe i mało używane; `--offline`), nowy tryb `atak` (nieniszczące próby na podglądzie: trasy bez sesji, IDOR, limit logowania, upload HTML jako obrazek, sesja po wylogowaniu; poza podglądem tylko z `--zgoda-wlasciciela`). `nowa-strona`: `.gitignore` z `.env*` przed pierwszym commitem. Eval `web-app-ai-security`.
- Bezpieczeństwo aplikacji: skille `security-review` (getsentry, OWASP: JS/Next, Python, Docker, tabela „czego nie zgłaszać”) i `supply-chain-risk-auditor` (Trail of Bits: OSV, porzucone repo, wydawcy npm, skrypty instalacyjne), oba CC BY-SA bez zmian; `bezpieczenstwo-aplikacji` krok 1b (zależności) i 4 (przegląd per technologia). `security_check.py repo`: niebezpieczne ustawienia domyślne (metoda Trail of Bits `insecure-defaults`, reguły własne; pliki testów pominięte).
- Kontrakt zlecenia (wspólny): nie osłabiam kontroli, żeby zaliczyć DoD (za ECC loop-design-check); poprawki po recenzji z pytaniem przy niejasnym punkcie i sprzeciwem z dowodem przy błędnym (za superpowers receiving-code-review); reguła 17: zgoda A2 przypięta do odcisku wersji plików (`scripts/odcisk.py`, za ECC operator-approval-loop). `wdrozenie`: prośba o zgodę z odciskiem `dist/`, przed wdrożeniem `odcisk.py --sprawdz`.
- Skill `systematic-debugging` z Hermesa (metoda superpowers z pętlą mattpocock): gdy build, skrypt albo test pada, najpierw przyczyna, potem jedna poprawka. Wpięty w `nowa-strona` (krok 6).
- Czat Jarvo HQ (`platform_toolsets.api_server`) ustawiony jawnie: te same narzędzia co na Telegramie (bez `clarify`). Wcześniej Hermes dawał tu swój domyślny zestaw narzędzi.

## 0.1.0 (2026-09-26)
- Pierwsza wersja: 7 workflowów, 7 skryptów, 30 skilli zewnętrznych (jakość, SEO, CRO, design, publikacja).
