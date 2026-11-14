# Prawo i granice przy pozyskiwaniu klientów jarodev

source: ustawa z 12 lipca 2024 r. Prawo komunikacji elektronicznej (Dz.U. 2024 poz. 1221), art. 398; RODO
(rozporządzenie UE 2016/679) art. 5, 6, 14, 21; regulamin Facebooka (Meta, warunki korzystania i zasady automatycznego
zbierania danych); decyzje właściciela z 14.11.2026
reviewed: 2026-11-14

To checklista do pracy, nie porada prawna. W sprawie wątpliwej: szkic + pytanie do właściciela, nie działanie.

## Art. 398 PKE (od 10.11.2024, zastąpił art. 172 Prawa telekomunikacyjnego i art. 10 ustawy o świadczeniu usług drogą elektroniczną)
- Marketing bezpośredni, w tym niezamówiona informacja handlowa, przez telekomunikacyjne urządzenia końcowe
  (e-mail, telefon, SMS, komunikator) i automatyczne systemy wywołujące jest zakazany **bez wcześniejszej zgody**
  odbiorcy. Dotyczy także firm, nie tylko konsumentów.
- Zgody nie daje: opublikowany adres e-mail lub telefon firmy, wpis w Mapach Google, rejestr CEIDG albo KRS.
- Dlatego: firm z Map i z audytu **nie kontaktujemy** mailem, telefonem, SMS-em, formularzem kontaktowym ani wiadomością
  na Facebooku. Szkic oferty tak; kanał wybiera właściciel (list, spotkanie, odpowiedź, gdy firma sama napisała).
- Osoba, która publicznie prosi o oferty („szukam kogoś do zrobienia strony, piszcie”), sama zaprasza do kontaktu:
  odpowiedź w wątku albo wiadomość z odpowiedzią na jej prośbę jest zamówiona. Tylko w temacie jej prośby, jedna
  wiadomość, bez dopisywania do list i bez ponawiania bez odpowiedzi.

## RODO przy danych z postów
- Podstawa: prawnie uzasadniony interes (art. 6 ust. 1 lit. f), bo osoba sama opublikowała prośbę o ofertę.
- Minimum danych (art. 5 ust. 1 lit. c): link do posta, wyświetlana nazwa, potrzeba, data. Bez telefonu, maila,
  zdjęć, miejsca pracy, profilu prywatnego, znajomych. `lejek.py` odrzuca e-mail i telefon w polach osoby.
- Ograniczenie przechowywania (art. 5 ust. 1 lit. e): bez kontaktu po 90 dniach wpis znika (`lejek.py retencja`,
  codziennie w `poranek.py`).
- Obowiązek informacyjny (art. 14) i sprzeciw (art. 21): pierwsza wiadomość do osoby mówi, skąd mamy kontakt
  („z Pana posta w grupie …”), a „nie, dziękuję” = status `odpada` i koniec kontaktu.

## Facebook i serwisy
- Regulamin Facebooka zabrania automatycznego zbierania danych bez zgody Meta: czytamy grupy jak człowiek na telefonie
  (przewijanie, czytanie), bez skrobaków, eksportów, automatycznego klikania serii i bez obchodzenia blokad.
- Limity dnia z `zrodla.yaml` (grupy, komentarze, posty). Ostrzeżenie Facebooka („robisz to za szybko”, blokada
  funkcji, weryfikacja) = stop na dziś i raport do właściciela.
- Nie dołączamy do grup, nie zapraszamy znajomych i nie zmieniamy ustawień konta bez polecenia właściciela.

## Mapy Google
- Bez Places API i bez narzędzi do masowego pobierania wizytówek (decyzja właściciela i warunki Google). Przeglądamy
  wyniki w przeglądarce Komputera Jarva w ludzkim tempie, w limicie `mapy` z `zrodla.yaml`.
- Z wizytówki bierzemy: nazwę firmy, miasto, branżę, link wizytówki, czy jest strona (i jej adres), ocenę i liczbę
  opinii. Opinie klientów i dane osób z opinii nie trafiają do lejka.
