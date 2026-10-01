---
name: nowa-aplikacja
description: "Nowa aplikacja Expo: plan, zgodność, szablon, ekrany."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [mobile, expo, react-native, app, prototype, app-store, google-play]
    related_skills: [natywna-czy-pwa, podglad-aplikacji, audyt-mobilny]
  jarvo:
    agent: jarvo-mobile
    autonomy: A1
    reviewed: "2026-10-01"
---

# Nowa aplikacja

Od briefu do działającej aplikacji Expo (SDK 57, TypeScript, expo-router), którą właściciel widzi w HQ i na telefonie.
Zasady sklepów wchodzą do planu pierwszego dnia (profil zgodności), a szablon JARVO od początku ma to, o co
najczęściej odbijają się małe aplikacje: prywatność, kontakt, usuwanie konta, stany ekranów, brak sieci.

## Kiedy użyć
- decyzja z `natywna-czy-pwa` wskazała aplikację (albo właściciel jej chce mimo ryzyk opisanych w rekomendacji),
- karta „zrób aplikację / prototyp aplikacji” z planem albo briefem.

## Kiedy NIE używać
- nie było decyzji „natywna czy PWA” → najpierw `natywna-czy-pwa` (chyba że karta zawiera jej wynik),
- zmiana w istniejącej aplikacji → praca w jej katalogu (`aplikacja.py sprawdz` + `podglad` po zmianie),
- PWA albo strona → `jarvo-web`.

## Wejścia
Cel aplikacji, odbiorcy, funkcje „musi” (z `decyzja.json`), brand kit (`@@KNOWLEDGE_DIR@@/brands/<marka>/`: kolor główny,
logo), dane firmy (nazwa, adres, e-mail, telefon, strona, adres polityki prywatności). Brakuje domeny albo danych
firmy → `kanban_block(kind="needs_input")` z propozycją; identyfikatora aplikacji nie zgadujesz z nazwy.

## Kroki
1. **Plan** `out/PLAN.md` (szablon: `references/plan.md`): cel, użytkownik, mapa ekranów (najwyżej 5 zakładek),
   na każdym ekranie dane i stany, **funkcje ponad stronę** (Apple 4.2: powiadomienia, offline, aparat, karta),
   dane i backend, konta, płatności, powiadomienia (kiedy i po co), miary sukcesu. Teksty roboczo z `[SZKIC]`.
2. **Profil zgodności** `out/zgodnosc.yaml` (`python3 $HERMES_HOME/scripts/zgodnosc.py szablon`): logowanie, płatności,
   treści użytkowników, AI, uprawnienia z polskim powodem (≥ 40 znaków, z przykładem użycia), reklamy, dzieci, tablet,
   branża, konto Google. `zgodnosc.py sprawdz out/zgodnosc.yaml --md out/ZGODNOSC.md` bez błędów, zanim powstanie kod.
3. **Konfiguracja** `out/aplikacja.yaml` (`python3 $HERMES_HOME/scripts/aplikacja.py konfiguracja`): `bundle` z odwróconej
   domeny firmy (`salonola.pl` → `pl.salonola.app`; nie do zmiany po pierwszym wgraniu), kolor z brand kitu, dane
   firmy, `usuwanie_konta_url`, gdy są konta (stronę robi Web).
4. **Aplikacja z szablonu:** `python3 $HERMES_HOME/scripts/aplikacja.py nowa <projekt>/app --aplikacja out/aplikacja.yaml
   --zgodnosc out/zgodnosc.yaml [--logo <brand>/logo/logo.svg]` (ok. 1 min: szablon, paleta WCAG, ikony, moduły
   uprawnień przez `expo install`). Przeczytaj `app/AGENTS.md`.
5. **Ekrany z planu** (zasady: `references/ekrany.md`): komponenty z `src/components/`, kolory z `useKolory()`, na
   każdym ekranie z danymi stany ładowania, pustki i błędu, formularze z typem klawiatury i autouzupełnianiem, prośba
   o uprawnienie w momencie użycia z ekranem wyjaśnienia przed oknem systemowym, nic za logowaniem bez potrzeby.
   Paczki tylko `npx expo install <paczka>`; w prototypie trzymaj się modułów dostępnych w Expo Go (podgląd na
   telefonie bez builda). Backend: Supabase z kluczem `anon` (nigdy `service_role` w aplikacji).
6. **Pętla po każdej większej zmianie:**
   - `python3 $HERMES_HOME/scripts/aplikacja.py sprawdz <projekt>/app`: typy, lint, wersje SDK, expo-doctor, zasady
     JARVO (pliki zgodności, uprawnienia ↔ moduły, sekrety). Wszystko ✓; `J-TODO` dozwolone tylko z listą w ryzykach,
   - `python3 $HERMES_HOME/scripts/aplikacja.py podglad <projekt>/app --trasy / /wiecej …`: link w HQ i zrzuty iPhone
     i Pixel w jasnym i ciemnym motywie z kontrolami (konsola, przewijanie, cele dotyku, axe). **Obejrzyj zrzuty**
     (vision): każdy ekran z planu, oba motywy; popraw, zanim pójdziesz dalej.
   Kontrola pada → najpierw przyczyna (komunikat, odtworzenie), potem jedna poprawka; nie osłabiasz kontroli.
7. **Raport** `out/RAPORT.md`: link HQ, 4–6 najlepszych zrzutów, co działa, co `[SZKIC]`, lista `JARVO-TODO`, co
   niesprawdzone na urządzeniu (powiadomienia, aparat, płatności, logowanie Google), następny krok: `podglad-aplikacji`
   (Expo Go na telefonie właściciela), potem bramka jakości i pakiet do sklepów.

## Wyjścia
`out/PLAN.md`, `out/zgodnosc.yaml`, `out/ZGODNOSC.md`, `out/aplikacja.yaml`, `<projekt>/app/` (repo git),
`<projekt>/app/out/jakosc/sprawdz.json`, `<projekt>/app/out/zrzuty/`, `out/RAPORT.md`.

## Definition of Done
- [ ] plan z mapą ekranów i funkcjami ponad stronę; profil zgodności bez błędów,
- [ ] `aplikacja.py sprawdz` wszystko ✓ (poza `J-TODO` opisanym w ryzykach),
- [ ] `aplikacja.py podglad`: 0 błędów konsoli, bez poziomego przewijania, 0 poważnych błędów axe, zrzuty obejrzane,
- [ ] każdy ekran z planu istnieje i ma stany; elementy zgodności z szablonu nietknięte,
- [ ] zero sekretów w kodzie i `app.config.ts`; raport z linkiem i listą niesprawdzonego na urządzeniu.

## Typowe błędy
- Zakładanie konta przed pokazaniem czegokolwiek (Apple 5.1.1(v) i utrata klientów).
- Ogólnikowy opis uprawnienia („aplikacja potrzebuje dostępu do aparatu”): odrzucenie 5.1.1(ii).
- Logowanie Google bez Apple (4.8): profil zgodności dodaje je sam, ale ekran logowania trzeba zrobić.
- Moduł spoza Expo Go w prototypie: podgląd na telefonie przestaje działać, potrzebny build.
