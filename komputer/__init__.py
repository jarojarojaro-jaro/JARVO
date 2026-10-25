"""Komputer Jarva: bramka sterownika (jarvo_cua.py), wtyczka Operatora (plugin/) i Komputer natywnie (docs/KOMPUTER.md).

Komputer natywnie (docs/NATYWNIE.md, etap E10): osobna przeglądarka Jarva (Chrome for Testing z własnym profilem)
sterowana przez CDP po potoku, z twardymi zasadami wejścia i filtrem ruchu w aplikacji:
  cdp.py               CDP przez --remote-debugging-pipe (bez portu), biblioteka standardowa
  kanal.py             kanały usługi: potoki nazwane z DACL właściciela (Windows), gniazda 0600 (POSIX)
  filtr.py             proxy filtrujące (asyncio): bez sieci lokalnej, metadanych chmury, pętli zwrotnej i portu 25
  przegladarka.py      flagi, preferencje profilu, pobrane pliki i program przeglądarki
  sterownik_cdp.py     sterownik mówiący tym samym MCP co cua-driver (elements, element_token, effect; pasek adresu
                       jako element 0), podgląd dla HQ (Page.startScreencast) i wejście właściciela („Przejmij”)
  zasady_natywne.py    słownik ról CDP dla zasad i zasady z J05 (schowek, okna potwierdzeń, wybór pliku, CAPTCHA,
                       znak po znaku w polu hasła)
  wejscie_natywne.py   wejście z twardymi zasadami: rdzeń z infra/komputer/wejscie.py i zasady.py, kontekst CDP;
                       kanał `ster` z poleceniami właściciela (wznow, klatka, przejmij, wejscie, stop, okno, wyczysc)
  usluga.py            proces usługi Komputera (proxy, przeglądarka, wejście, kanały, samotesty)
Polecenie właściciela: `jarvo komputer` (jarvo/komputer.py).
"""
