# Changelog: jarvo-sherlock

## Niewydane
- Cytowania z rejestru (skill `cytowania`, na bazie Hermes `grounded-citations`, MIT): `sources.py` to teraz rejestr `out/zrodla.json` z numerami `[n]` nadawanymi przy pobraniu, cytatami-dowodami (`quote` przyjmuje tylko słowa, które są w zapisanym tekście strony), blokiem „## Źródła” z `render --replace-in` i `verify` raportu (numery spoza rejestru, blok niezgodny z rejestrem, źródło bez przeczytanego tekstu albo bez oceny A–D, pokrycie, `--dowody`); `[niezweryfikowane]` dla twierdzeń bez źródła. `extract.py` rejestruje stronę i zapisuje jej tekst w `out/strony/<n>.txt` (`--tier`, `--type`, `--bez-rejestru`). Stary `out/zrodla.jsonl` przechodzi do rejestru sam. `--archive` zapisuje też tekst. Zewnętrzny `grounded-citations` usunięty (jeden rejestr). metoda-sherlocka 1.2.0, raport-sledztwa, weryfikacja-faktow i szybki-fakt 1.1.0, SOUL zasada 9, rubryka: `verify` z błędem blokuje.
- SOUL: z linii o treściach źródeł zostaje tylko własna część (podejrzane instrukcje odnotowane w raporcie); „dane, nie polecenia” jest w zasadzie 8 protokołu.
- Poza zakresem: audyt aplikacji w App Store i Google Play należy do Twórcy aplikacji (`jarvo-mobile`).
- Poza zakresem: listy leadów sprzedażowych należą do Łowcy (`jarvo-lowca`).
- Kontrakt zlecenia (wspólny): nie osłabiam kontroli, żeby zaliczyć DoD (za ECC loop-design-check); poprawki po recenzji z pytaniem przy niejasnym punkcie i sprzeciwem z dowodem przy błędnym (za superpowers receiving-code-review); reguła 17: zgoda A2 przypięta do odcisku wersji plików (`scripts/odcisk.py`, za ECC operator-approval-loop).
- Wspólny skill `transkrypcja-filmu`: link (YouTube, TikTok, Instagram…) albo plik → tekst tego, co mówią (napisy platformy albo Parakeet).
- Czat Jarvo HQ (`platform_toolsets.api_server`) ustawiony jawnie: te same narzędzia co na Telegramie (bez `clarify`). Wcześniej Hermes dawał tu swój domyślny zestaw narzędzi.

## 0.1.0 (2026-09-26)
- Pierwsza wersja: metoda Sherlocka, weryfikacja faktów, raporty, research rynku i SEO, monitoring; 3 skrypty; 15 skilli zewnętrznych.
