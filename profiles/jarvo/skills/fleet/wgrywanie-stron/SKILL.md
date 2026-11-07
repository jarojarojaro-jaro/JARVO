---
name: wgrywanie-stron
description: "Wgranie strony na hosting: plan, zgoda na odcisk, cofnięcie."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [fleet, deploy, hosting, ssh, approval]
    related_skills: [decision-queue, sdlc-review, mission-ledger]
  jarvo:
    agent: jarvo
    autonomy: A2
    reviewed: "2026-11-07"
---

# Wgrywanie stron na hosting

Właściciel ma 12 stron na hostingu współdzielonym (SEOHost). Każda strona to prywatne repo
`jarojarojaro-jaro/<domena>`: korzeń repo to dokładnie `public_html` serwera, a gałąź `main` to strona na żywo.
Na serwer wgrywasz **tylko Ty** i **tylko** skryptem `@@PY@@ "$HERMES_HOME/scripts/wgraj.py"`, po wyraźnym „tak”
właściciela dla konkretnego odcisku. Wgranie to akcja A2: zgoda dotyczy jednego planu, nie „wgrywaj od teraz”.

Skrypt potrzebuje narzędzia terminal (sesja CLI i praca na karcie). W czacie bez terminala go nie masz: powiedz
właścicielowi, że plan i wgranie zrobisz w sesji z terminalem, i nie szukaj innej drogi.

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
   plików (każdy usuwany plik wymień, gdy jest ich do 20), adres podglądu. Zapytaj wprost: „Wgrać ten odcisk?”.
5. **Czekaj na „tak” dla tego odcisku.** Brak odpowiedzi, „chyba”, „ok, ale popraw X” = nie wgrywasz. Każda zmiana
   w repo po planie zmienia odcisk: nowy plan i nowe pytanie.
6. **Wgraj:** `wgraj.py wgraj <repo> --wersja <gałąź> --odcisk <odcisk>`. Skrypt sam: czeka na inne wgrywanie (jedno
   naraz w flocie), sprawdza wersję, robi kopię `~/kopie-stron/<domena>/<RRRRMMDD-HHMMSS>.tar.gz`, wgrywa, porównuje sumy
   sha256 każdego pliku, taguje `wgranie-…` i przewija `main` na GitHubie.
7. **Raport:** z JSON-a wyniku: domena, odcisk, liczby, nazwa kopii, czas, tag. Kod 3 = sumy się nie zgadzają: skrypt
   podał gotowe polecenie `cofnij`; pokaż je właścicielowi z listą niezgodnych plików i zapytaj, czy cofnąć.

## Cofnięcie
`wgraj.py cofnij <repo> --do <tag> --odcisk <odcisk tagu>` tworzy na `main` nowy commit „Cofnięcie do <tag>”
z plikami z tagu i wgrywa go jak zwykłe wgranie. To też A2: pokaż tag, jego datę i odcisk, czekaj na „tak”.
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
- Nie wgrywasz bez zgody na dokładnie ten odcisk, także „drobnej poprawki”.
- Nie zmieniasz `.strona.json` bez prośby właściciela.
