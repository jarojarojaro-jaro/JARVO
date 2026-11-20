---
name: komentarze-na-x
description: "Komentarz na X z telefonów floty, krótko i po ludzku."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [x, twitter, komentarze, telefony, pisanie]
    related_skills: [skrzynka-linkow]
  jarvo:
    agent: jarvo
    autonomy: A2
    reviewed: "2026-11-20"
---

# Komentarze na X z telefonów floty

Skill napisał Jarvo 18.11 po korektach właściciela (zapis `skill_manage` w zainstalowanym profilu); 20.11 przeniesiony
do repo, żeby aktualizacja go nie zgubiła.

## When to Use

**Tylko gdy właściciel wyraźnie każe skomentować** („napisz coś pod tym”, „skomentuj”, „odpowiedz z telefonów”). Sam link wysłany bez słowa to **zlecenie analizy, nie komentowania**: wtedy skill `skrzynka-linkow` (pobierz, oceń, zapisz) i ani jednego wpisu na X. Wysłanie komentarza bez polecenia to błąd, który właściciel nazwał wprost „CO TY ODPIERDALASZ”.

Właściciel chce odpowiedź pod wpisem na X z telefonów (`first`, `second`, `third`). Cel: wpis ma wyglądać jak od człowieka, nie od automatu.

## Jak pisać (najważniejsze)

Test: czy tak napisałby to zwykły użytkownik, który właśnie zobaczył wpis? Jeśli nie, pisz od nowa.

- **Jedno zdanie, może dwa.** Długość nie jest celem samym w sobie: „Id love to test” jest dobre, ale „been waiting for something like this, might actually try it” też jest dobre. Złe są trzy zdania gadaniny, które nic nie wnoszą.
- **Nic o Enigmie, nic o flocie, nic o agentach, nic o własnym serwerze.** Zero self-promo i zero tłumaczenia się, kim jesteś. To komentarz pod cudzym wpisem, nie wizytówka.
- **Zero marketingu:** bez nazw własnych produktu, bez „300k VM minutes”, bez liczb, bez „at real scale”, bez „would love a month of X”.
- **Bez wyliczanek i bez myślników** (— i –). Bez emoji, bez hasztagów.
- **Po ludzku, nie gramatycznie idealnie**: „Id love to test” jest lepsze niż „I'd love to test”. Małe potknięcia są w porządku, sztuczna poprawność nie.
- **Bez powtarzania tej samej treści na kilku kontach.** Ten sam sens, inne słowa: jedno zachwyt („wow would love to try capy”), drugie sucho („gonna try this”).
- Język wpisu rządzi: wpis po angielsku = odpowiedź po angielsku.

Zły przykład (odrzucony przez właściciela): „Building an agent fleet on our own inference engine (Enigma, 14 agents on a home server) — this is the first pricing that makes swarms affordable...”. To AI slop: długie, reklamowe, z liczbami, o sobie.

## Jak wysłać (PhoneUse)

1. `mcp__phone__ping` na każdym telefonie. Offline = jeden telefon mniej, nie powtarzaj w pętli.
2. `act` `open` z URL wpisu (bez parametrów `?s=`, `?a=`: wystarczy `/status/<id>`).
3. `wait` na tekst „Odpowiedz” (25 s), potem `tap` w „Odpowiedz / N”.
4. `act` `type` z `index` pola EditText (zwykle 8 lub 13 po otwarciu arkusza; sprawdź `screen`, indeksy przesuwają się).
5. `tap` w przycisk „Odpowiedz” na górze arkusza.
6. Paragon: linia „Odpowiedź została wysłana” + profil `x.com/<uchwyt>/with_replies` pokazuje wpis z „· 5 s”.

## Jak usunąć własny wpis

Menu „Opcje wpisu” (trzy kropki) → „Usuń wpis” → potwierdzenie „Usuń”. Telefon wymaga `confirm: true` przy obu krokach; bez tego zwraca `needs_confirm` i nic nie robi. Po usunięciu sprawdź, że w miejscu wpisu jest „Ten wpis został usunięty”.

## Pułapki

- **Po skończonej pracy wygaś każdy telefon**: `act` `global` z `action: "lock_screen"` na każdym, którego użyłeś (także tym, co był tylko otwarty na wpisie). Telefon zostawiony z włączonym ekranem żre baterię, a przy niskiej baterii wypada z Tailscale i przestaje być dostępny. Nie ma osobnego „sleep”: `lock_screen` to jedyna droga przez PhoneUse.
- Tap w zakładkę „Odpowiedzi” na profilu nie zawsze przełącza widok; po `tap` czytaj `screen`, zamiast powtarzać tap.
- Profil z zakładką „Odpowiedzi” pokazuje najpierw cudze wpisy z osi; własną odpowiedź znajdziesz po `scroll down`.
- Pola tekstowe mają różne indeksy w arkuszu odpowiedzi zależnie od tego, czy klawiatura jest otwarta; zawsze `type` po `index` z ostatniego `screen`.
- Telefony realme rozłączają Tailscale przy niskiej baterii (od ~15%, gdy Tailscale nie jest na białej liście). Telefon z baterią <10% traktuj jak niedostępny.
