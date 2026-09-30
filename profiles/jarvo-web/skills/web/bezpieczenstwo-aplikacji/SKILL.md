---
name: bezpieczenstwo-aplikacji
description: "Bezpieczeństwo aplikacji: skan, 18 punktów, przegląd kodu."
version: 1.0.0
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
**dla każdej strony z backendem, logowaniem, formularzem, bazą, płatnościami albo uploadem**. Czysty statyczny landing:
tylko krok 2 (nagłówki i wycieki).

## Kiedy użyć
- nowa aplikacja lub funkcja z logowaniem, bazą, API, formularzem, plikami, płatnościami, webhookami,
- przed każdym wdrożeniem takiej aplikacji (skill `wdrozenie`) i w `bramka-jakosci`,
- „zrób audyt bezpieczeństwa”, „czy moja strona jest bezpieczna”, przejęty projekt „vibe-coded”.

## Kroki
1. **Skan kodu:** `python3 $HERMES_HOME/scripts/security_check.py repo <projekt> --json > out/bezpieczenstwo/repo.json`
   (sekrety w plikach i w **historii gita**, `.env` w repo, `npm audit`, wzorce ryzyka: token w localStorage,
   SQL sklejany z danych, eval, HTML bez oczyszczenia, sekret w zmiennej publicznej frontu, CORS *, debug; niebezpieczne
   ustawienia domyślne: sekret z wartością zapasową, zabezpieczenie wyłączone przy braku konfiguracji, TLS bez weryfikacji,
   JWT bez podpisu, domyślne hasło, stos błędu w odpowiedzi, introspekcja GraphQL, uprawnienia 777/public-read).
   KRYTYCZNE (sekret) → najpierw **unieważnij klucz** u dostawcy, potem usuń z kodu i historii. Samo usunięcie nie wystarcza.
1b. **Zależności** (jest `package.json`, `pyproject.toml`, `requirements*.txt` albo `go.mod`): skill
   `supply-chain-risk-auditor`, skrypty bez `uv` i poza badanym repo:
   `D=$HERMES_HOME/skills/bezpieczenstwo/supply-chain-risk-auditor/scripts`,
   `python3 $D/collect.py <projekt> --json out/bezpieczenstwo/zaleznosci.json` →
   `python3 $D/render.py out/bezpieczenstwo/zaleznosci.json --out out/bezpieczenstwo/zaleznosci.md`.
   Podatności z lockfile'a (OSV), porzucone repo, jeden wydawca pakietu npm, skrypty instalacyjne. Brak danych
   (np. limit GitHuba bez tokenu) to „nie oceniono”, nigdy „czysto”; kod ≠ 0 z `collect.py` przekazujesz dosłownie.
2. **Skan działającej strony** (podgląd albo produkcja): `python3 $HERMES_HOME/scripts/security_check.py url <URL>`
   (HTTPS, HSTS, CSP, clickjacking, nosniff, Referrer/Permissions-Policy, flagi ciasteczek sesji, CORS z obcej domeny,
   ślady błędów, publiczne `/.env`, `/.git`, kopie zapasowe).
3. **Lista kontrolna** `references/lista-kontrolna.md`: 18 punktów + nagłówki. Każdy punkt: ✓ z dowodem (plik:linia,
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
   wynik skanów przed i po, lista kontrolna, co musi zrobić człowiek (unieważnić klucz, włączyć 2FA u dostawcy).

## Zasady
- **Nigdy nie wypisujesz znalezionego sekretu** w raporcie ani w czacie: tylko rodzaj i miejsce (`plik:linia`).
- Nie testujesz cudzych stron bez zgody właściciela: `url` tylko dla stron użytkownika albo naszego podglądu.
- Bez ataków niszczących (DoS, masowe żądania, łamanie haseł). To audyt, nie pentest.
- Poprawki zabezpieczeń na produkcji = wdrożenie (A2, skill `wdrozenie`).

## Definition of Done
- [ ] oba skany uruchomione, wynik w `out/bezpieczenstwo/` (przed i po poprawkach),
- [ ] zero KRYTYCZNYCH i WYSOKICH (albo nazwane z decyzją człowieka),
- [ ] lista kontrolna wypełniona z dowodami; n/d z powodem,
- [ ] żaden sekret nie pojawił się w raporcie, logu ani odpowiedzi.
