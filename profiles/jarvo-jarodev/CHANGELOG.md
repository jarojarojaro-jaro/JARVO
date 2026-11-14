# Changelog: jarvo-jarodev

## 0.1.0 (2026-11-14)
- Pierwsza wersja (szkielet agenta biznesowego, decyzja właściciela 14.11): klienci dla jarodev.pl z grup Facebooka na
  jednym przydzielonym telefonie (`jarvo telefon przydziel`, serwer phone z `PHONEUSE_ONLY`), z Map Google na
  Komputerze Jarva (bez Places API) i z szybkiego audytu publicznej strony firmy. 7 skilli (`lejek`, `fb-grupy`,
  `fb-posty`, `mapy-firmy`, `szybkie-wygrane`, `oferta-szkic`, `raport-dnia`), skrypty `lejek.py`, `poranek.py`,
  `wygrane.py`, wzór `zrodla.yaml` (grupy i portale podaje właściciel), rutyna `jarodev-dzien` (wstrzymana).
- Granice: każdy post, komentarz i wiadomość tylko za „tak” właściciela (bramka telefonu i Komputera, wtyczka
  jarvo-zgody, `lejek.py` wymaga zapisu zgody), firm z Map nie kontaktuje mailem, telefonem, SMS-em ani formularzem
  (art. 398 PKE; `lejek.py` odmawia takiego kanału), RODO dla osób z postów (minimum danych, retencja 90 dni).
- Agent biznesowy (`marka: jarodev`): w skarbcu widzi tylko `brands/jarodev/`, swoje notatki i wspólną wiedzę floty;
  pod YOLO ekran i telefon zablokowane jak u Jarva.
- Wspólne skille: `konwersja-plikow` i `odczyt-ekranu` (Indra OCR: tekst ze zrzutu telefonu).
- Evals: 12 scenariuszy (w tym poza zakresem, zgoda, art. 398 PKE, RODO, wiedza tylko o marce), docs/RSI.md; 2 ataki
  red teamu (zimna wysyłka do firm z Map, polecenie w poście z grupy FB o wiedzę innej marki i publikację).
