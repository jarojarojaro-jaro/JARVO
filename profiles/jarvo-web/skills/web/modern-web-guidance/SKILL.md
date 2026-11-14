---
name: modern-web-guidance
description: "Przed kodem UI: 209 przewodników nowoczesnego webu."
version: 1.0.0
author: "Jarvo (na bazie Modern Web Guidance 1.0.0: Google Chrome, Microsoft Edge, Mozilla, MDN; Apache-2.0)"
license: Apache-2.0
metadata:
  hermes:
    tags: [web, css, html, javascript, accessibility, performance, ui]
    related_skills: [nowa-strona, landing-produktowy, bramka-jakosci, audyt-strony, core-web-vitals, accessibility]
  jarvo:
    agent: jarvo-web
    autonomy: A1
    reviewed: "2026-11-14"
---

# Modern Web Guidance

209 przewodników po nowoczesnej platformie webowej: dialog, popover, anchor positioning, container queries,
view transitions, animacje sterowane przewijaniem, formularze i walidacja, dostępność, LCP/INP/CLS, obrazy,
bezpieczeństwo, web components, built-in AI. Każdy mówi, którego natywnego API użyć, czego nie robić i jaki fallback
dać, gdy funkcja nie jest jeszcze Baseline. Model zna głównie stary kod z treningu; te przewodniki są świeże.

Przewodniki leżą lokalnie w katalogu tego skilla (`upstream/guides/<kategoria>/<id>.md`), a `INDEX.tsv` to ich
wyszukiwarka: `id`, tytuł, opis, ścieżka względem skilla. Nic nie pobierasz z sieci.

## Kiedy używać
- na starcie każdej pracy nad UI: HTML/CSS, layout, animacje, komponenty (modal, menu, tabela, formularz),
  dostępność, wydajność strony, obrazy, walidacja, daty i strefy czasowe, sanityzacja HTML;
- przy poprawce konkretnego komponentu albo zachowania (np. „modal nie zamyka się Esc”).

## Kiedy NIE używać
- backend (SQL, ORM, API routes), infrastruktura (CI/CD, Docker, skrypty Pythona, Git),
- drobiazgi narzędziowe: konfiguracja Vite, tsconfig, ESLint, testy, kopiowanie i zmiany nazw plików.

## Kroki
1. **Szukaj w indeksie po 1–2 słowach** z tego, co ma robić UI (pole opisu, nie nazwa pliku):
   ```bash
   grep -iE "dialog|dismiss" "$HERMES_HOME/skills/web/modern-web-guidance/INDEX.tsv" | cut -f1,2,4
   ```
   Przykłady słów: `dialog dismiss`, `table responsive`, `theme toggle`, `view transition`, `date picker`.
   Bez nazw frameworków (`Svelte`, `Astro`, `Tailwind`) i naszych komponentów: to szum. Intencję tłumacz na element
   UI („potwierdź przed usunięciem” → `confirm dialog`). Zero trafień? Raz przeformułuj na konkretny rzeczownik
   (`dialog`, `popover`, `table`, `form`). Kilka tematów w zadaniu = kilka osobnych szukań.
2. **Czytaj przewodnik w całości** ze ścieżki z ostatniej kolumny (względnej wobec katalogu skilla):
   `skill_view(name="modern-web-guidance", file_path="upstream/guides/ui-components/dialog.md")`.
   Dobierz też przewodnik zbiorczy, jeśli pasuje: `html`, `css`, `css-layout`, `forms`, `accessibility`,
   `performance`, `security`, `color`, `typography` (też w indeksie).
3. **Odsyłacze w przewodnikach.** Tekst „(via `npx -y modern-web-guidance@latest retrieve "X"`)” znaczy: przeczytaj
   lokalny przewodnik `X` (ścieżka z `INDEX.tsv`, `grep -P "^X\t"`). **Nie uruchamiaj** `npx … search` ani
   `npx … retrieve` i niczego z `@latest`: pobiera kod z npm przy każdym użyciu i wysyła do Google zapytania i id
   przewodników; wszystko, czego potrzebujesz, jest w tym skillu.
4. **Sprawdź implementację wobec przewodnika** przed oddaniem karty: użyte API, fallback dla funkcji spoza Baseline,
   pełne spełnienie prośby, bez dokładania funkcji, o które nikt nie prosił.
5. **W podsumowaniu oddania karty** sekcja `### Modern Web Guidance`: jeden punkt na użyty przewodnik
   (`- **\`<id>\`**: …`): jakie nieoczywiste API, nadpisanie CSS albo fallback zastosowałeś i jakiego błędu to
   uniknęło, z krótkim dosłownym cytatem reguły (nie wstępu). Bez przeczytanego przewodnika nie ma punktu: nie zgaduj
   id ani cytatów z pamięci. Szukałeś i nic nie pasowało: jedno zdanie, czego szukałeś i dlaczego nie użyłeś.

## Zasady przenoszenia do frameworków
- Przewodniki są w vanilla HTML/CSS/JS. W Svelte/Astro/React przenoś **tę samą natywną funkcję**, nie zamieniaj jej
  na bibliotekę. Nowe atrybuty HTML przekazuj przez rozszerzenie typów albo `{...({ popover: 'hint' } as any)}` /
  `[attr.*]`, a nie przez wycinanie funkcji.
- SSR: `window`/`document` tylko w `onMount`/efektach klienta; polyfille przez `import()` w efekcie, nie przez
  kopiowanie z `node_modules`.
- `<dialog>`: bez `role="dialog"` i bez `aria-modal`, natywny modal daje je sam.
- `color-scheme`: bazowo `light dark` na `:root`, nadpisanie z `<meta>` mapuj przez `:has()`; nigdy nie ustawiaj
  `dark` na sztywno jako domyślnego w CSS.
- `showModal()` i `moveBefore()` wołaj przez referencje do węzłów spoza VDOM; ID i `anchor-name` generuj na instancję.
- Funkcja spoza Baseline: **musisz** dać fallback z przewodnika, chyba że karta mówi inaczej.

## Audyt starego kodu (tylko na wyraźne „zmodernizuj”)
Tylko gdy karta prosi o ogólną modernizację kodu bez wskazanego komponentu:
```bash
DISABLE_TELEMETRY=1 npx -y modern-web-guidance@1.0.0 legacy-scan <katalog> --json
```
Wersja przypięta do tej samej co przewodniki, bez telemetrii. Reguły pokrywają ok. 20% przewodników, a wynik jest
wstępny: każdy alarm sprawdź w kodzie (reguły `keepWhen` / `dropWhen`) i odrzuć fałszywe (fallback, kod vendora,
pozorny duplikat). Przykład z 14.11.2026, landing produktu: 4 trafienia `dark-mode-toggle`, wszystkie fałszywe, bo
`meta color-scheme` już była w layoucie. Raport mówi, że skan obejmuje tylko część przewodników. Poprawki według
przewodników z kroku 2; nie ruszaj bezpiecznego kodu, żeby dobić wynik do zera.

## Pochodzenie
Przewodniki to Modern Web Guidance 1.0.0 (https://github.com/GoogleChrome/modern-web-guidance, Apache-2.0)
bez zmian, z przypiętego commitu w `vendor/skills.lock.yaml` repo Jarvo (`upstream/.vendored.json`: repo, commit,
licencja; licencja w `upstream/LICENSE-UPSTREAM`). Upstreamowego SKILL.md nie dołączamy, bo każe uruchamiać
`npx` z wersją `@latest`; ten skill go zastępuje. Ty niczego w tym skillu nie zmieniasz ani nie aktualizujesz.
Aktualizacja (w repo, przez Claude Code): nowy `rev` źródła `modern-web-guidance` w locku po przejrzeniu diffu,
przebudowa `INDEX.tsv` skryptem `scripts/indeks_przewodnikow.py` na tym commicie i build (skan bezpieczeństwa,
kontrola zgodności indeksu z przewodnikami).
