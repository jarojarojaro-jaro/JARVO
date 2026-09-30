---
name: bezpieczenstwo-aplikacji
description: "Bezpieczeństwo aplikacji: skan, próby, 26 punktów."
version: 1.1.0
author: "Jarvo (metodyka przeglądu wg anthropics/claude-code-security-review, MIT)"
license: MIT
metadata:
  hermes:
    tags: [security, web, owasp, headers, auth, secrets]
    related_skills: [security-review, supply-chain-risk-auditor, bramka-jakosci, audyt-strony, wdrozenie, nowa-strona]
  jarvo:
    agent: jarvo-web
    autonomy: A1
    reviewed: "2026-09-30"
---

# Bezpieczeństwo aplikacji

Strona „zrobiona z AI” najczęściej wycieka nie przez wyrafinowany atak, tylko przez klucz w repo, token
w `localStorage` albo panel admina bez sprawdzenia uprawnień na serwerze. Ten skill to obowiązkowa bramka
**dla każdej strony z backendem, logowaniem, formularzem, bazą, płatnościami, uploadem albo funkcją AI**. Czysty
statyczny landing: tylko krok 2 (nagłówki, wycieki, klucze w JS). Skany i próby trwają minuty; najdłużej trwa krok 4.

## Kiedy użyć
- nowa aplikacja lub funkcja z logowaniem, bazą, API, formularzem, plikami, płatnościami, webhookami, czatem/AI,
- przed każdym wdrożeniem takiej aplikacji (skill `wdrozenie`) i w `bramka-jakosci`,
- „zrób audyt bezpieczeństwa”, „czy moja strona jest bezpieczna”, przejęty projekt „vibe-coded”.

## Kroki
1. **Skan kodu:** `python3 $HERMES_HOME/scripts/security_check.py repo <projekt> --json > out/bezpieczenstwo/repo.json`
   (sekrety w plikach i w **historii gita**, `.env` w repo, `npm audit`, wzorce ryzyka: token w localStorage,
   SQL sklejany z danych, eval, HTML bez oczyszczenia, sekret w zmiennej publicznej frontu, CORS *, debug; niebezpieczne
   ustawienia domyślne: sekret z wartością zapasową, zabezpieczenie wyłączone przy braku konfiguracji, TLS bez weryfikacji,
   JWT bez podpisu, domyślne hasło, stos błędu w odpowiedzi, introspekcja GraphQL, uprawnienia 777/public-read) oraz
   **zależności z rejestru** (npm, PyPI): nieistniejąca nazwa (zmyślona przez model), różna jedną literą od popularnej,
   nowa i mało używana. `nie_ocenione` w wyniku to „nie sprawdzono”, nigdy „czysto”.
   KRYTYCZNE (sekret) → najpierw **unieważnij klucz** u dostawcy, potem usuń z kodu i historii. Samo usunięcie nie wystarcza.
   Nowa zależność w trakcie pracy: przed `npm install` sprawdź ją w rejestrze (istnieje, wiek, pobrania, repozytorium).
1b. **Zależności** (jest `package.json`, `pyproject.toml`, `requirements*.txt` albo `go.mod`): skill
   `supply-chain-risk-auditor`, skrypty bez `uv` i poza badanym repo:
   `D=$HERMES_HOME/skills/bezpieczenstwo/supply-chain-risk-auditor/scripts`,
   `python3 $D/collect.py <projekt> --json out/bezpieczenstwo/zaleznosci.json` →
   `python3 $D/render.py out/bezpieczenstwo/zaleznosci.json --out out/bezpieczenstwo/zaleznosci.md`.
   Podatności z lockfile'a (OSV), porzucone repo, jeden wydawca pakietu npm, skrypty instalacyjne. Brak danych
   (np. limit GitHuba bez tokenu) to „nie oceniono”, nigdy „czysto”; kod ≠ 0 z `collect.py` przekazujesz dosłownie.
2. **Skan działającej strony** (podgląd albo produkcja): `python3 $HERMES_HOME/scripts/security_check.py url <URL>`
   (HTTPS, HSTS, CSP, clickjacking, nosniff, Referrer/Permissions-Policy, flagi ciasteczek sesji, CORS z obcej domeny,
   ślady błędów, publiczne `/.env`, `/.git`, kopie zapasowe, **klucze serwerowe w JS wysyłanym do przeglądarki**;
   klucz `anon` Supabase i klucze Google Maps/Firebase są publiczne z założenia, liczy się ich ograniczenie).
2b. **Próby na działającej aplikacji** (podgląd z backendem): dwa konta testowe (A i B) zakładasz sam na podglądzie,
   ich nagłówki sesji bierzesz z odpowiedzi logowania, potem:
   ```bash
   python3 $HERMES_HOME/scripts/security_check.py atak http://localhost:4321 --json \
     --chronione /api/admin /api/orders --sesja-a "Cookie: sid=…" --sesja-b "Cookie: sid=…" --zasob-a /api/orders/<id A> \
     --logowanie /api/login --upload /api/upload:file --wyloguj /api/logout > out/bezpieczenstwo/atak.json
   ```
   Sprawdza: trasy bez sesji, cudzy zasób sesją konta B (IDOR), limit prób logowania (12 prób, oczekiwane 429), plik
   HTML udający obrazek w uploadzie, sesję po wylogowaniu; `--limit <trasa>` dla innych tras. `sprawdzone` to dowody do
   listy kontrolnej. Endpointu AI z prawdziwym modelem nie odpytujesz seryjnie (kosztuje): limit z przeglądu kodu.
3. **Lista kontrolna** `references/lista-kontrolna.md`: 26 punktów + nagłówki (23–25 tylko przy funkcji AI). Każdy punkt: ✓ z dowodem (plik:linia,
   wynik polecenia) albo ✗ z poprawką, albo „n/d” z powodem (np. brak uploadu). Przepisy per stos: `references/przepisy.md`.
4. **Przegląd kodu jak security engineer** (`references/przeglad-kodu.md`): kontekst → porównanie z wzorcami
   projektu → śledzenie danych od wejścia do operacji wrażliwych. Tylko ustalenia z pewnością ≥ 0,8 i realnym scenariuszem
   ataku; bez teorii i stylu. Szczegóły per technologia: skill `security-review` (OWASP): `languages/javascript.md`
   (Express, React, Next, Vue), `languages/python.md`, `infrastructure/docker.md` i `references/<temat>.md` (xss, csrf,
   ssrf, authorization…) oraz jego tabela „czego nie zgłaszać” (wartości z konfiguracji serwera, auto-escaping frameworka).
   Przewodników go/rust/java i k8s/terraform, do których odsyła, w tej wersji nie ma.
5. **Poprawki:** KRYTYCZNE i WYSOKIE naprawiasz przed oddaniem; ŚREDNIE naprawiasz albo opisujesz z uzasadnieniem;
   potem ponownie kroki 1–2 (dowód, że znikło).
6. **Raport** `out/bezpieczenstwo/RAPORT.md`: tabela ustaleń (waga, co, gdzie, scenariusz ataku, poprawka, stan),
   wynik skanów i prób przed i po, lista kontrolna, co musi zrobić człowiek (unieważnić klucz, włączyć 2FA u dostawcy,
   **twarde limity wydatków** u dostawców AI i w chmurze, kopie zapasowe bazy z próbą odtworzenia).

## Zasady
- **Nigdy nie wypisujesz znalezionego sekretu** w raporcie ani w czacie: tylko rodzaj i miejsce (`plik:linia`).
- Nie testujesz cudzych stron bez zgody właściciela: `url` tylko dla stron użytkownika albo naszego podglądu.
  `atak` sam odmawia poza podglądem (localhost, adres prywatny); na produkcji użytkownika tylko po jego wyraźnej zgodzie
  (`--zgoda-wlasciciela`), na kontach testowych, nigdy na kontach prawdziwych klientów.
- Bez ataków niszczących (DoS, masowe żądania, łamanie haseł). Próby `atak` to kilkanaście żądań na trasę. To audyt, nie pentest.
- Poprawki zabezpieczeń na produkcji = wdrożenie (A2, skill `wdrozenie`).

## Definition of Done
- [ ] oba skany uruchomione, wynik w `out/bezpieczenstwo/` (przed i po poprawkach); aplikacja z kontami: także `atak`,
- [ ] zero KRYTYCZNYCH i WYSOKICH (albo nazwane z decyzją człowieka),
- [ ] lista kontrolna wypełniona z dowodami; n/d z powodem,
- [ ] żaden sekret nie pojawił się w raporcie, logu ani odpowiedzi.
