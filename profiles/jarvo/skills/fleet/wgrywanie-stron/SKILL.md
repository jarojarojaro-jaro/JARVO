---
name: wgrywanie-stron
description: "Wgranie strony na hosting: plan, odcisk, wgranie, cofnięcie."
version: 1.0.2
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [fleet, deploy, hosting, ssh, approval]
    related_skills: [decision-queue, sdlc-review, mission-ledger]
  jarvo:
    agent: jarvo
    autonomy: A2
    reviewed: "2026-11-14"
---

# Wgrywanie stron na hosting

Właściciel ma 12 stron na hostingu współdzielonym (SEOHost). Każda strona to prywatne repo
`jarojarojaro-jaro/<domena>`: korzeń repo to dokładnie `public_html` serwera, a gałąź `main` to strona na żywo.
Na serwer wgrywasz **tylko Ty** i **tylko** skryptem `@@PY@@ "$HERMES_HOME/scripts/wgraj.py"`, na polecenie
właściciela i bez pytania o „tak”, bo jego polecenie jest zgodą. Każde wgranie dotyczy jednego planu i jego odcisku.

Skrypt potrzebuje narzędzia terminal; masz je w rozmowie (Telegram, czat HQ), w sesji CLI i na karcie. Gdy w tej
sesji terminala nie ma (np. rutyna), powiedz właścicielowi, że plan i wgranie zrobisz w sesji z terminalem, i nie
szukaj innej drogi.

## Kiedy
- Specjalista (zwykle Web) skończył zmianę strony na gałęzi repo strony, sędzia ją przyjął, a właściciel chce ją na żywo.
- Właściciel prosi o cofnięcie strony do wcześniejszego stanu.
- Strona z builda (np. SvelteKit): nowy build trzeba przenieść do repo strony przed planem.
Nie używasz tego skilla do stron spoza tych repo ani do jarvo.pl (osobny `deploy-site.sh`).

## Plik `.strona.json` (w repo strony, nie wgrywany)
`domena`, `katalog_na_serwerze` (np. `domains/<domena>/public_html`, względem katalogu domowego), `chronione` (pliki
serwera, których skrypt nigdy nie wysyła i nigdy nie usuwa: `api/config.php`, `cgi-bin/`, `.well-known/`, bazy, `.env*`),
`kopie_na_serwerze` (ile kopii trzymać), `z_buildu` (wpisy z builda), `zakazane_sciezki`, `zakazane_wzorce`,
`wymagane_teksty`. Na serwer nie trafiają `.git/`, `.github/`, `.gitignore` ani `.strona.json`.

## Procedura
1. **Sprawdź lokalnie:** `wgraj.py sprawdz <repo> --wersja <gałąź>`. Odmowa (niezatwierdzone zmiany, zakazana ścieżka
   albo wzorzec, brak wymaganego tekstu, śledzony sekret z `.gitignore`) wraca do wykonawcy jako poprawka karty;
   sam jej nie obchodzisz. Ostrzeżenie o śledzonym pliku z `chronione` (np. `cgi-bin/.htaccess`) to nie błąd: ten plik
   zostaje na serwerze bez zmian.
2. **Podgląd:** `wgraj.py podglad <repo> --wersja <gałąź>` daje adres podglądu (`JARVO_PODGLAD_URL`).
3. **Plan (jedno połączenie, nic nie zapisuje):** `wgraj.py plan <repo> --wersja <gałąź>`: co dojdzie, co się zmieni,
   co zniknie z serwera, liczby i `odcisk`.
4. **Pokaż właścicielowi** jedną wiadomością: domena, odcisk, liczby (dodane, zmienione, usunięte), lista usuwanych
   plików (każdy usuwany plik wymień, gdy jest ich do 20), adres podglądu.
5. **Wgrywasz ten odcisk bez pytania.** Każda zmiana w repo po planie zmienia odcisk: nowy plan.
6. **Wgraj:** `wgraj.py wgraj <repo> --wersja <gałąź> --odcisk <odcisk>`. Skrypt sam: czeka na inne wgrywanie (jedno
   naraz w flocie), sprawdza wersję, robi kopię `~/kopie-stron/<domena>/<RRRRMMDD-HHMMSS>.tar.gz`, wgrywa, porównuje sumy
   sha256 każdego pliku, taguje `wgranie-…` i przewija `main` na GitHubie.
7. **Raport:** z JSON-a wyniku: domena, odcisk, liczby, nazwa kopii, czas, tag. Kod 3 = sumy się nie zgadzają: skrypt
   podał gotowe polecenie `cofnij`; uruchom je i pokaż właścicielowi listę niezgodnych plików.

## Cofnięcie
`wgraj.py cofnij <repo> --do <tag> --odcisk <odcisk tagu>` tworzy na `main` nowy commit „Cofnięcie do <tag>”
z plikami z tagu i wgrywa go jak zwykłe wgranie. Cofasz na polecenie właściciela; w raporcie podaj tag, jego datę i odcisk.
Tagi: `wgranie-…` (każde udane wgranie) i `zywo-…` (stan początkowy). Kopie na serwerze: `wgraj.py kopie <repo>`.

## Strony z builda
Gdy `z_buildu` nie jest puste: `wgraj.py z-buildu <repo> --build <katalog builda>` podmienia tylko wpisy z `z_buildu`
(np. `_app`, `pl`, `index.html`); `robots.txt`, `api/`, `.htaccess` i pliki analityki zostają. Przejrzyj
`git status`, zatwierdź commit na gałęzi i dopiero wtedy procedura od kroku 1.

## Twarde zasady
- Jedno połączenie SSH na polecenie, bez ponawiania. Błąd połączenia albo logowania = stop i wiadomość do właściciela;
  nigdy druga próba (nieudane logowania banują IP dla wszystkich 12 stron).
- Żadnej innej drogi na hosting: bez ręcznego `ssh`, `scp`, `rsync`, FTP, panelu ani serii zapytań HTTP do sprawdzania
  (limit 429). Nigdy nie uruchamiasz `deploy-ftp.py` z repo KERNEL.
- Nigdy nie commitujesz sekretów (haseł, kluczy, `config.php` z danymi) i nie edytujesz plików z `chronione`.
- Wgrywasz dokładnie odcisk z ostatniego planu, także przy „drobnej poprawce”.
- Nie zmieniasz `.strona.json` bez prośby właściciela.
