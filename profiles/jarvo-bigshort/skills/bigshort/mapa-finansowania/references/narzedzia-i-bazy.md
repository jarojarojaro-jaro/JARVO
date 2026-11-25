---
source: "research floty Jarva 2026-11-25 (strony programów i regulaminy, linki przy wpisach)"
reviewed: "2026-11-25"
---

# Narzędzia, bazy inwestorów i API do researchu finansowania

Data badania: 2026-11-25. Autor: agent badawczy (web research, bez rejestracji, bez wysyłania formularzy).

## Legenda

- **Dostęp**: Darmowe (bez konta lub z darmowym kontem), Freemium (darmowy poziom z limitami), Płatne (subskrypcja lub wycena indywidualna).
- **ToS/scraping**: co mówi regulamin lub robots.txt o automatycznym pobieraniu. „Zakaz” oznacza, że agent nie powinien sam pobierać danych, tylko przygotowywać pracę dla człowieka.
- **Zweryfikowano**: data, w której sprawdziłem informację. „U źródła” znaczy na oficjalnej stronie lub żywym wywołaniem API. „Pośrednio” znaczy z porównania lub artykułu strony trzeciej (podana), czyli traktować jako niepewne.
- **[NIEZWERYFIKOWANE]**: informacja z drugiej ręki albo wniosek, którego nie potwierdziłem u źródła.
- **[WNIOSEK]**: moja interpretacja, nie fakt ze strony.


---

## 1. Bazy inwestorów i platformy fundraisingowe

### 1. Crunchbase
- URL: https://www.crunchbase.com , dokumentacja API: https://data.crunchbase.com/docs/api-essentials
- Dane: firmy, rundy finansowania, inwestorzy, przejęcia, ludzie; „likely investors”, prognozy, MCP.
- Dostęp/koszt: darmowe konto z bardzo ograniczoną liczbą profili. Pro ok. 49 USD/mies. rocznie (promocja na 1. rok, cena katalogowa 79) lub 99 USD miesięcznie; Business od 199 USD/mies. (pośrednio, 12inf.ai, sprawdzone przez nich 2026-10-11). **Darmowe Basic API zostało wycofane**: istniejących kluczy nie można regenerować, nowych się nie wydaje. API Enterprise tylko przez dział sprzedaży, limit 200 wywołań/min i 3 równoległe na klucz, zakaz redystrybucji, wymagane atrybucje z linkiem dofollow (pośrednio, frontal.so, 2026-11-20). Serwer MCP (mcp.crunchbase.com) to osobny zakup per użytkownik.
- ToS/scraping: regulamin wprost zabrania „crawls, scrapes or spiders” jakiejkolwiek części serwisu (about.crunchbase.com/terms-of-service, sprawdzone 2026-11-25). robots.txt wpuszcza boty działające na żądanie użytkownika (ChatGPT-User, Claude-User, PerplexityBot), a blokuje boty treningowe (GPTBot, ClaudeBot, CCBot). Uwaga: robots.txt nie znosi zakazu z regulaminu.
- Dopasowanie: dobra baza „kto finansował podobne firmy”, słabsza dla aniołów pre-seed i Europy Środkowej.
- Zweryfikowano: 2026-11-25 (ToS i robots u źródła; cennik i API pośrednio).

### 2. PitchBook (oraz PitchBook for Startups)
- URL: https://pitchbook.com/pricing , https://pitchbook.com/pitchbook-for-startups
- Dane: najgłębsze dane o rundach VC/PE, funduszach, LP, ludziach, analizy.
- Dostęp/koszt: cena na zapytanie; strony trzecie podają ok. 7,5 do 10,5 tys. USD za seat rocznie wg zamówień rządowych USA lub 20 do 40 tys. USD+ (pośrednio, crustdata.com, provaapi.com). **Nowość z 2026-11-10: PitchBook for Startups, darmowy dostęp** dla firm przed pierwszą rundą instytucjonalną: pre-seed lub bootstrapped bez rundy wycenionej (priced round), niezależna firma (nie spółka zależna), brak umowy z PitchBook w ostatnich 12 mies. Program globalny. Weryfikacja przez służbowy e-mail, stronę lub LinkedIn oraz działające demo, prototyp lub makietę. W zamian firma co kwartał aktualizuje swoje dane (finanse, zespół, kamienie milowe), które zasilają nowe narzędzie dla inwestorów PitchBook Origin.
- ToS/scraping: platforma za loginem, strona chroniona Cloudflare (odczyt komunikatu prasowego zwrócił 403). Automatyzacja [NIEZWERYFIKOWANE], zakładać zakaz.
- Dopasowanie: **bardzo wysokie** dla obu projektów, jeśli nie było rundy wycenionej. Koszt to udostępnienie danych inwestorom (to też kanał bycia znalezionym).
- Zweryfikowano: 2026-11-25 pośrednio (strona programu i komunikat prasowy cytowane w wynikach wyszukiwania: pitchbook.com, finance.yahoo.com, geekwire.com); strona PitchBook zablokowała bezpośredni odczyt.

### 3. Dealroom
- URL: https://dealroom.co/pricing/ , API: https://dealroom.co/api/ , https://developers.dealroom.co
- Dane: 3,2 mln+ firm, w tym 500 tys.+ europejskich startupów, rundy, inwestorzy, sygnały; najlepsze pokrycie Europy.
- Dostęp/koszt: Premium 250 EUR/seat/mies., Premium Plus 325 EUR (z MCP dla Claude/Cursor), minimum 3 seaty, rozliczenie roczne (czyli min. ok. 9 000 EUR/rok). API jako płatny dodatek wg wolumenu. 3-dniowy trial bez karty (50 kredytów eksportu). Zniżki dla „kwalifikujących się startupów” po kontakcie ze sprzedażą.
- ToS/scraping: dane licencjonowane, MCP „zwraca tylko dane dozwolone licencją”. Zakładać zakaz scrapingu [NIEZWERYFIKOWANE w ToS].
- Jak agent może użyć: realnie tylko w trialu (3 dni) lub po zakupie. Ewentualnie zapytać o cenę startupową.
- Dopasowanie: merytorycznie świetne dla UE, finansowo za drogie na pre-seed.
- Zweryfikowano: 2026-11-25, u źródła (cennik).

### 4. Tracxn
- URL: https://tracxn.com/pricing , API: https://w.tracxn.com/api-developers-page
- Dane: 8,4 mln+ firm, 292 tys.+ inwestorów, 2 mln+ rund, 229 tys.+ przejęć.
- Dostęp/koszt: **Lite za darmo** (bez karty, „ścisłe limity użycia”, eksporty, raporty, alerty w ograniczonym zakresie). Premium na wycenę. API i zrzuty danych jako „Data Solutions packs” na wycenę; trial PoC 5 do 7 dni z limitem kredytów (help.tracxn.com).
- ToS/scraping: zakaz współdzielenia kont; licencje wewnętrzne vs redystrybucyjne. Automatyzacja poza API [NIEZWERYFIKOWANE], zakładać zakaz.
- Dopasowanie: średnie, dobra darmowa furtka do danych o rundach.
- Zweryfikowano: 2026-11-25, u źródła.

### 5. Harmonic
- URL: https://harmonic.ai/pricing , API: https://console.harmonic.ai/docs/api-reference/introduction
- Dane: 70 mln firm, 210 mln osób, 250 tys. inwestorów; wykrywa firmy bardzo wcześnie (rejestracje, zatrudnienia); asystent Scout; MCP.
- Dostęp/koszt: tylko wycena („Get pricing”), API i dane o finansowaniu jako dodatki. Strona „For founders / get discovered” pozwala zgłosić startup.
- ToS/scraping: płatna licencja; brak darmowego dostępu.
- Jak agent może użyć: praktycznie nie, poza zgłoszeniem firmy (harmonic.ai/submit), żeby VC używający Harmonic ją widzieli.
- Dopasowanie: niskie jako narzędzie, średnie jako kanał widoczności.
- Zweryfikowano: 2026-11-25, u źródła.

### 6. OpenVC
- URL: https://www.openvc.app , cennik: https://docs.openvc.app/en/articles/13262685-how-much-does-openvc-cost
- Dane: 16 do 20 tys.+ inwestorów (VC, aniołowie, akceleratory), filtry etap/sektor/kraj/czek, przycisk „Submit deck” u wielu funduszy, CRM, śledzenie decka, AI do e-maili.
- Dostęp/koszt: 90% funkcji darmowe na zawsze. Premium 99 USD/mies. lub 299 USD/rok (300 pitchy/mies.), Ultra 299 USD/mies. lub 899 USD/rok (1000 pitchy/mies.). Bez prowizji i equity. Filtr „verified”, wielkość czeku i lead są w Premium (pośrednio, 12inf.ai).
- ToS/scraping: **wyraźny zakaz** scrapingu, automatycznej ekstrakcji, tworzenia baz pochodnych, masowej wysyłki i trenowania AI na danych OpenVC (openvc.app/legal, cytowane w wynikach wyszukiwania). Strona za Cloudflare.
- Dopasowanie: **wysokie** dla obu projektów (globalnie i w UE, pre-seed).
- Zweryfikowano: 2026-11-25 (cennik u źródła; ToS pośrednio).

### 7. Signal by NFX
- URL: https://signal.nfx.com , FAQ: https://signal.nfx.com/faq , rankingi: https://signal.nfx.com/investor-lists
- Dane: profile inwestorów crowdsourcowane przez founderów i asystentów VC (ponad 1 mln edycji); rankingi „Top investors by sector & stage”; zakres czeku, „sweet spot”, współinwestorzy. Strona list pokazuje 32 823 dodanych inwestorów.
- Dostęp/koszt: **100% za darmo**, „nigdy nie będziemy pobierać opłat”. OAuth Gmaila odczytuje tylko nagłówki (nadawca, odbiorca, data), by pokazać istniejące relacje z inwestorami.
- ToS/scraping: regulamin zakazuje botów, crawlerów i „manual or automated means to extract and/or compile content” (signal.nfx.com/terms, sprawdzone 2026-11-25). robots.txt: Crawl-delay 8, zakaz m.in. /investors$.
- Zweryfikowano: 2026-11-25, u źródła.

### 8. VC Sheet
- URL: https://www.vcsheet.com , https://www.vcsheet.com/investors , https://www.vcsheet.com/funds
- Dane: „największa otwarta lista aktywnych inwestorów”, filtry etap/branża/geografia; kuratorowane „sheets” (np. „Investors Focused on AI”, 64 inwestorów; „VCs Leading Seeds”, 85), filmy z inwestorami, poradniki.
- Dostęp/koszt: przeglądanie za darmo bez konta.
- ToS/scraping: robots.txt zawiera tylko mapę strony (brak zakazów); strony regulaminu nie znalazłem (/terms nie zwróciło treści) [NIEZWERYFIKOWANE].
- Jak agent może użyć: odczyt publicznych stron z umiarkowaną częstotliwością (np. kuratorowane listy AI i pre-seed), z cache i atrybucją; przed automatyzacją potwierdzić regulamin.
- Dopasowanie: średnio-wysokie, mocny akcent na USA.
- Zweryfikowano: 2026-11-25, u źródła (strona, robots).

### 9. Visible Connect
- URL: https://connect.visible.vc , https://visible.vc/connect
- Dane: darmowa baza inwestorów (ok. 19 tys.+ rekordów, 800+ zweryfikowanych wg 12inf.ai), filtry etap/sektor/czek/geografia; źródła: sami inwestorzy, newsletter Axios Pro Rata, dane publiczne.
- Dostęp/koszt: przeglądanie za darmo; zaawansowane filtry po założeniu darmowego konta Visible. Płatne plany Visible od 59 USD/mies. rocznie (pośrednio, 12inf.ai) dotyczą głównie investor updates i data roomów.
- ToS/scraping: robots.txt bez zakazów (User-agent: *); regulamin [NIEZWERYFIKOWANE].
- Jak agent może użyć: odczyt publicznych profili po nazwie funduszu (wzbogacenie: czek, etapy, fokus), nie masowe pobieranie.
- Dopasowanie: średnie.
- Zweryfikowano: 2026-11-25 (robots u źródła, liczby pośrednio).

### 10. Landscape.vc
- URL: https://landscape.vc
- Dane: historycznie platforma z opiniami founderów o VC i akceleratorach (opis w Tracxn); obecnie strona opisuje się jako „Discover & Analyse Startups with AI” dla VC i aniołów, trial 30 dni za 30 USD (landscape.ventures).
- Dostęp/koszt: płatne dla inwestorów; dla founderów niejasne.
- ToS/scraping: [NIEZWERYFIKOWANE]. Strona zwróciła błąd HTTP 522 w dniu badania.
- Jak agent może użyć: ewentualnie odczyt publicznych recenzji funduszy (np. /investors/forward-partners), jeśli nadal są dostępne.
- Dopasowanie: niskie, status produktu niepewny.
- Zweryfikowano: 2026-11-25, częściowo (strona niedostępna).

### 11. F6S
- URL: https://www.f6s.com/programs , https://www.f6s.com/accelerators
- Dane: „16 tys. akceleratorów, grantów i okazji finansowania”, programy, wyzwania, zniżki na oprogramowanie. Wiele europejskich „open calls” z kaskadowego finansowania UE jest zbieranych przez F6S [WNIOSEK z obserwacji rynku, do potwierdzenia].
- Dostęp/koszt: darmowe dla founderów (konto).
- ToS/scraping: robots.txt wpuszcza tylko wymienione boty wyszukiwarek, a dla reszty (User-agent: *) ma `Disallow: /`. Agent nie powinien crawlować.
- Dopasowanie: wysokie dla programów UE i akceleratorów.
- Zweryfikowano: 2026-11-25, u źródła (robots).

### 12. Gust
- URL: https://gust.com , https://gust.com/pricing/
- Dane: platforma, przez którą grupy aniołów (np. Gust Angel Collective, do 150 tys. USD w pre-seed/seed) przyjmują zgłoszenia; Gust Launch to inkorporacja w Delaware, cap table, SAFE.
- Dostęp/koszt: Gust Launch 450 do 3 500 USD/rok; profil startupu i aplikowanie do grup [NIEZWERYFIKOWANE czy bezpłatne w 2026].
- ToS/scraping: [NIEZWERYFIKOWANE].
- Dopasowanie: niskie dla firmy z PL (silny akcent na USA i Delaware).
- Zweryfikowano: 2026-11-25, pośrednio (wyniki wyszukiwania, roundfunded.com).

### 13. AngelList i Wellfound
- URL: https://www.angellist.com/startups/ruv , https://wellfound.com
- Dane: AngelList to dziś infrastruktura VC (syndykaty, fundusze, Roll Up Vehicles: do 250 inwestorów jako jedna pozycja w cap table). Wellfound (dawniej AngelList Talent) wydzielono w 2023 r. jako serwis rekrutacyjny; nie jest już wyszukiwarką inwestorów.
- Dostęp/koszt: RUV płatne [NIEZWERYFIKOWANE kwoty]; struktury oparte na prawie Delaware.
- ToS/scraping: robots Wellfound blokuje ścieżki ofert pracy; dla inwestorów nie dotyczy.
- Jak agent może użyć: jako narzędzie do zebrania wielu małych czeków od aniołów (RUV) po znalezieniu ich gdzie indziej; nie do wyszukiwania.
- Dopasowanie: niskie na etapie szukania, średnie przy zamykaniu rundy od aniołów.
- Zweryfikowano: 2026-11-25, u źródła (strona RUV) i pośrednio (historia Wellfound).

### 14. EU-Startups (baza inwestorów i startupów)
- URL: https://www.eu-startups.com
- Dane: magazyn o europejskich startupach, baza inwestorów (typ, fokus, ticket, etapy) i startupów, cotygodniowy przegląd rund.
- Dostęp/koszt: członkostwo ok. 114 EUR/rok za pełny dostęp do bazy [NIEZWERYFIKOWANE, źródło pośrednie: everythingxiaomi.com/apps/eu-startups/pricing].
- ToS/scraping: robots.txt bez zakazów (`Disallow:` puste); regulamin nie odczytany. Istnieją nieoficjalne API stron trzecich (NeuralVerge, Parse.bot) oparte na scrapingu, co niesie ryzyko prawne.
- Dopasowanie: wysokie dla UE, tani dostęp.
- Zweryfikowano: 2026-11-25 (robots u źródła, cena pośrednio).

### 15. Foundersuite
- URL: https://foundersuite.com/pricing , https://foundersuite.com/features/investor_database
- Dane: 216 tys. inwestorów (VC, family office, CVC, PE, pożyczkodawcy) plus 150 tys. aniołów/HNW; CRM, kampanie e-mail, AI do szkiców, data room, warm intro z LinkedIn/poczty/kalendarza.
- Dostęp/koszt: Basic za darmo (75 inwestorów na pipeline, pośrednio 12inf.ai); Silver 745 USD/rok (200), Gold 1 069 USD/rok (1000), Platinum 1 609 USD/rok (1500), miesięcznie ok. 10% drożej.
- ToS/scraping: dane zamknięte za kontem [NIEZWERYFIKOWANE regulamin].
- Dopasowanie: średnie (narzędzie procesowe, nie dobór).
- Zweryfikowano: 2026-11-25, u źródła (cennik).

### 16. AngelMatch
- URL: https://angelmatch.io/pricing
- Dane: 125 tys.+ aniołów, VC i PE z e-mailami i telefonami, masowa wysyłka, CRM.
- Dostęp/koszt: Basic 59, Growth 99, Premium od 349 USD/mies.; trial 3 dni (pośrednio, 12inf.ai, 2026-10-11).
- ToS/scraping: [NIEZWERYFIKOWANE].
- Jak agent może użyć: nie rekomenduję. Masowa wysyłka do osób z UE rodzi ryzyko RODO i przepisów o niezamówionej informacji handlowej (patrz sekcja 9).
- Dopasowanie: niskie.
- Zweryfikowano: pośrednio.

---

## 2. Publiczne dane i API (bez płatnych licencji)

### 17. EU Funding & Tenders Portal: Search API (SEDIA)
- URL: oficjalna strona API: https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/support/apis ; endpoint: `https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA`
- Dane: wszystkie konkursy i tematy (Horizon Europe z EIC, Digital Europe, CEF, LIFE, EU4Health itd.), terminy, budżety, statusy; indeks `SEDIA_NONH2020_PROD` dla przyznanych projektów; endpointy `/search`, `/facet`, `/document/{ref}`. Stara lista usług obejmuje też Partner Search (szukanie partnerów do konsorcjów).
- Dostęp/koszt: **darmowe, bez rejestracji**, publiczny klucz `SEDIA`. Zapytanie: POST multipart/form-data z częściami `query` (JSON, bool query w stylu Elasticsearch), `languages`, opcjonalnie `displayLanguage`. Kod Polski w API: `20000986`.
- Test na żywo (2026-11-25): `text=artificial intelligence`, typy 1/2/8 zwróciło 234 wyniki, m.in. HORIZON-CL3-2027-02-CS-ECCC-01 (termin 2027-09-15) i HORIZON-HLTH-2027-03-TOOL-08 (2027-09-16). Mój filtr statusu nie odfiltrował zamkniętego tematu z 2024, więc kody statusu (w nieoficjalnej dokumentacji 31094501 forthcoming, 31094502 open) trzeba potwierdzić facetem `/facet`.
- ToS/scraping: dane publiczne Komisji, zasady ponownego wykorzystania dokumentów KE (decyzja 2011/833/UE) [WNIOSEK, nie sprawdzałem warunków samego API]. Używać rozsądnego tempa i cache.
- Jak agent może użyć: codzienny skaner nowych tematów (wzorzec W1), filtrowanie po słowach kluczowych (LLM inference, edge AI, agents, SME), alert o terminach.
- Zweryfikowano: 2026-11-25, u źródła (żywe wywołanie).

### 18. CORDIS: otwarte dane o projektach UE
- URL: https://cordis.europa.eu/projects , zbiory: https://data.europa.eu/data/datasets/cordis-eu-research-projects-under-horizon-europe-2021-2027
- Dane: wszystkie projekty Horizon Europe i H2020: beneficjenci, kwoty, tematy, deliverables, publikacje, sieć współpracy organizacji; pliki CSV/JSON/XML/XLSX.
- Dostęp/koszt: darmowe, pobieranie hurtowe.
- ToS/scraping: otwarte dane UE [WNIOSEK: licencja CC BY 4.0 typowa dla data.europa.eu, do potwierdzenia na stronie zbioru].
- Jak agent może użyć: znaleźć firmy, które dostały EIC Accelerator lub granty Horizon w podobnej technologii (inferencja, kompresja modeli, edge AI), jakie kwoty, kto był partnerem; to wzorce dla wniosku i kandydaci na partnerów konsorcjum.
- Zweryfikowano: 2026-11-25, pośrednio (opis zbioru w wynikach wyszukiwania).

### 19. SEC EDGAR: Full-Text Search i API submissions
- URL: https://www.sec.gov/search-filings/edgar-application-programming-interfaces , https://data.sec.gov , zasady: https://www.sec.gov/os/accessing-edgar-data
- Dane: wszystkie zgłoszenia SEC, w tym Form D (oferty prywatne startupów i nowe fundusze VC w USA), pełnotekstowo od 2001.
- Dostęp/koszt: darmowe, bez klucza. Zasady fair access: nagłówek User-Agent z nazwą i e-mailem, maks. 10 zapytań/s.
- Test na żywo (2026-11-25): `efts.sec.gov/LATEST/search-index?q="artificial intelligence"&forms=D&startdt=2026-11-01&enddt=2026-11-24` zwrócił 2 zgłoszenia nowych funduszy AI (Brookfield Artificial Intelligence Infrastructure Fund, 360 ONE Multi Stage Artificial Intelligence Fund).
- ToS/scraping: dozwolone w granicach fair access.
- Dopasowanie: średnie (głównie rynek USA).
- Zweryfikowano: 2026-11-25, u źródła (żywe wywołanie).

### 20. SEC Form D Data Sets (zrzuty kwartalne)
- URL: https://www.sec.gov/data-research/sec-markets-data/form-d-data-sets
- Dane: ustrukturyzowane dane ze wszystkich Form D (Rule 504, 506(b), 506(c)), spłaszczone tabele, od 2008 do 2026 Q3 (plik 2026q3_d.zip, 3,48 MB), aktualizacja kwartalna.
- Dostęp/koszt: darmowe ZIP-y.
- ToS/scraping: dane publiczne; SEC zastrzega brak gwarancji poprawności.
- Jak agent może użyć: kwartalny import do SQLite, zapytania „pooled investment fund” + słowa kluczowe, lista nowych funduszy i ich zarządzających; łączenie z bazą inwestorów.
- Dopasowanie: średnie.
- Zweryfikowano: 2026-11-25, u źródła.

### 21. Grants.gov API (search2) i Simpler.Grants.gov API
- URL: https://www.grants.gov/api/common/search2 , https://wiki.simpler.grants.gov/product/api , OpenAPI: https://api.simpler.grants.gov/docs
- Dane: federalne granty USA (otwarte, prognozowane), terminy, agencje, kwalifikowalność.
- Dostęp/koszt: `POST https://api.grants.gov/v1/api/search2` działa **bez klucza** (test 2026-11-25: „artificial intelligence”, statusy forecasted|posted, 149 wyników). Simpler.Grants.gov wymaga klucza `X-API-Key` (konto przez Login.gov), ma endpoint extracts do pobrania całości, page_size 1 do 100.
- ToS/scraping: dane publiczne, limity zapytań (429 przy przekroczeniu).
- Dopasowanie: niskie teraz.
- Zweryfikowano: 2026-11-25, u źródła (żywe wywołanie, wiki).

### 22. YC OSS API (firmy Y Combinator jako JSON)
- URL: https://github.com/yc-oss/api , https://yc-oss.github.io/api/meta.json
- Dane: wszystkie publicznie ogłoszone firmy YC (6 408 wg meta.json z 2026-11-24), podział na batche, branże, tagi (np. open-source), firmy zatrudniające. Aktualizacja codzienna przez GitHub Actions z indeksu Algolia YC.
- Dostęp/koszt: darmowe, statyczne pliki JSON.
- ToS/scraping: projekt społecznościowy, nie scrapuje strony YC, tylko indeks Algolia [licencja repo do sprawdzenia].
- Dopasowanie: wysokie (aplikacja do YC, mapa konkurencji).
- Zweryfikowano: 2026-11-25, u źródła (żywe wywołanie).

### 23. Hacker News Search API (Algolia)
- URL: https://hn.algolia.com/api
- Dane: pełna historia HN: posty, komentarze, „Show HN”, „Launch HN” (firmy YC), ogłoszenia funduszy.
- Dostęp/koszt: darmowe, bez klucza; `/search`, `/search_by_date`, `/items/:id`, tagi story/show_hn/ask_hn.
- Test na żywo (2026-11-25): zapytanie `"pre-seed" fund` zwróciło 131 trafień, m.in. „Show HN: I built a tool that matches Founders to VCs based on their pitch deck”.
- ToS/scraping: publiczne API.
- Zweryfikowano: 2026-11-25, u źródła.

### 24. Seedlist (katalog inwestorów badany przez LLM, Eric Ries)
- URL: https://seedlist.com , https://seedlist.com/llms.txt , repo: https://github.com/ericries/seedlist
- Dane: 892 inwestorów, 434 firm VC, 2 242 startupów (llms.txt, 2026-11-25); tezy wywnioskowane z faktycznego portfela, nie z deklaracji; każde źródło cytowane i datowane.
- Dostęp/koszt: **pliki JSON bez logowania i klucza**: `enrichment-index.json` (fokus, czek, lokalizacja, ostatnia inwestycja, tldr), `investor-lookup.json`, `startup-investor-map.json` (kto w co zainwestował, runda, rok), `investor-graph.json` (koinwestycje), `rounds-feed.json` (500 ostatnich rund). Serwer MCP `https://seedlist.com/mcp` (logowanie Google) z dopasowaniem i prośbą o intro od Erica Riesa. Brak opublikowanego cennika.
- ToS/scraping: dane wystawione celowo dla agentów; repo bez licencji (stan 2026-11-25), więc redystrybucja niejasna [NIEZWERYFIKOWANE].
- Dopasowanie: **wysokie** (agent-native), ale katalog mały i raczej USA [WNIOSEK].
- Zweryfikowano: 2026-11-25, u źródła.

### 25. Portal Funduszy Europejskich, harmonogramy naborów i Mapa Dotacji
- URL: https://www.funduszeeuropejskie.gov.pl/wyszukiwarka/ , https://funduszeeuropejskie.gov.pl/nabory-wnioskow/harmonogramy-naborow-fe/ , https://mapadotacji.gov.pl
- Dane: wyszukiwarka dotacji w Polsce; harmonogramy naborów na 12 mies. dla FENG, FERC, programów regionalnych (np. plik XLSX FE dla Mazowsza z 04.11.2026); Mapa Dotacji: projekty od 2004 r.
- Dostęp/koszt: darmowe. Udokumentowanego API wyszukiwarki nie znalazłem [NIEZWERYFIKOWANE].
- ToS/scraping: dane publiczne administracji [WNIOSEK].
- Jak agent może użyć: raz w tygodniu pobierać pliki XLSX harmonogramów, wyciągać nabory dla MŚP i innowacji cyfrowych, porównywać z poprzednią wersją.
- Zweryfikowano: 2026-11-25, pośrednio (wyniki wyszukiwania).

### 26. grantledger.eu (open source, 99 oficjalnych źródeł)
- URL: https://grantledger.eu , metodologia: https://grantledger.eu/methodology
- Dane: 25 288 otwartych naborów i 1 429 nadchodzących z 99 oficjalnych źródeł w 32+ krajach (Polska: 71 naborów); granty, pożyczki, gwarancje, ulgi; odświeżanie co noc; każdy rekord linkuje do oficjalnego ogłoszenia.
- Dostęp/koszt: przeglądanie za darmo; Pro to jednorazowa opłata (screening profilu, cotygodniowe dopasowania, serwer MCP dla ChatGPT/Claude). Bez prowizji od sukcesu.
- ToS/scraping: projekt deklaruje się jako open source (Aitek Labs); licencje źródeł opisane w metodologii [NIEZWERYFIKOWANE szczegóły].
- Jak agent może użyć: przeglądanie filtrów (kraj PL/UE, beneficjent SME), a po zakupie Pro przez MCP; kod źródłowy jako wzór adapterów do krajowych źródeł.
- Dopasowanie: wysokie dla obu projektów.
- Zweryfikowano: 2026-11-25, u źródła.

### 27. Awesome AI Market Maps (Joy Larkin)
- URL: https://github.com/joylarkin/Awesome-AI-Market-Maps
- Dane: 500+ map rynku AI publikowanych przez VC i analityków, plik CSV, zbiór na Hugging Face, kanał RSS, serwer MCP przez gitmcp.io. 356 gwiazdek, aktualizacja 2026-11-16.
- Dostęp/koszt: darmowe.
- ToS/scraping: repozytorium publiczne.
- Jak agent może użyć: znaleźć fundusze, które publikują mapy „AI inference”, „agents”, „on-device AI”, bo mają tezę w tym obszarze; to gotowa lista celów.
- Dopasowanie: wysokie dla obu.
- Zweryfikowano: 2026-11-25, u źródła.

---

## 3. Agregatory grantów, kredytów i programów

### 28. GrantsFinder.eu
- URL: https://www.grantsfinder.eu/ai-grant-finder
- Dane: dopasowanie opisu projektu do aktualnych konkursów UE (Horizon, Digital Europe, Erasmus+, EU4Health), tłumaczenie ogłoszeń na prosty język.
- Dostęp/koszt: „Get started free”; cennik nie odczytany (strona JS) [NIEZWERYFIKOWANE].
- ToS/scraping: [NIEZWERYFIKOWANE].
- Dopasowanie: średnie.
- Zweryfikowano: 2026-11-25, częściowo.

### 29. AllGrants.eu i grants.dealflow.eu (Grant Compass)
- URL: https://allgrants.eu , https://grants.dealflow.eu
- Dane: 1 414 do 1 943 otwartych naborów UE i krajowych, ok. 16,4 mld EUR dostępnych; analiza dopasowania na podstawie strony firmy.
- Dostęp/koszt: wyszukiwanie i odczyt dopasowania za darmo; usługi pisania wniosków płatne [NIEZWERYFIKOWANE model, możliwa prowizja].
- ToS/scraping: [NIEZWERYFIKOWANE].
- Dopasowanie: średnie.
- Zweryfikowano: 2026-11-25, u źródła (strona główna).

### 30. findfunding.eu
- URL: https://findfunding.eu/en
- Dane: dopasowanie AI do programów UE, federalnych i krajowych (silny akcent na Niemcy).
- Dostęp/koszt: subskrypcja od 99 EUR/mies. (5 analiz) lub od 29 EUR za analizę.
- ToS/scraping: płatne.
- Jak agent może użyć: raczej nie; za mało pokrycia Polski [WNIOSEK].
- Dopasowanie: niskie.
- Zweryfikowano: 2026-11-25, u źródła.

### 31. Spinbase.eu
- URL: https://spinbase.eu
- Dane: semantyczne wyszukiwanie konkursów UE, projektów i partnerów na podstawie opisu tekstowego.
- Dostęp/koszt: [NIEZWERYFIKOWANE].
- Jak agent może użyć: wyszukiwanie partnerów konsorcjum dla Horizon (alternatywa dla Partner Search i CORDIS).
- Zweryfikowano: 2026-11-25, częściowo.

### 32. Instrumentl
- URL: https://www.instrumentl.com/pricing
- Dane: baza grantów i fundacji (głównie USA, organizacje non-profit), tracking, pisanie wniosków.
- Dostęp/koszt: 299, 499, 999 USD/mies. rocznie (349, 579, 1 159 USD miesięcznie), trial 14 dni (pośrednio, grantcue.com).
- Dopasowanie: niskie (USA, non-profit).
- Zweryfikowano: pośrednio.

### 33. aifree.dev i lista awesome-free-ai-credits
- URL: http://aifree.dev/startup-ai-credits , https://github.com/aifree-dev/awesome-free-ai-credits
- Dane: 91 programów kredytów AI dla startupów (łącznie do 350 tys. USD), 195 ofert w repo, każda ręcznie zweryfikowana z datą i „haczykiem”; RSS zmian.
- Dostęp/koszt: darmowe.
- Jak agent może użyć: subskrypcja RSS, filtr „bez wymogu VC”, przypomnienia o wygasaniu kredytów.
- Zweryfikowano: 2026-11-25, pośrednio (wyniki wyszukiwania).

### 34. TheGrantIndex
- URL: https://thegrantindex.com/guides/free-ai-credits-for-startups , https://thegrantindex.com/guides/non-dilutive-funding-open-source
- Dane: przewodniki po kredytach AI i finansowaniu bezudziałowym dla open source, liczby sprawdzane z oficjalnymi stronami (aktualizacja 2026-11-04 i 2026-11-11).
- Dostęp/koszt: darmowe.
- Dopasowanie: średnie.
- Zweryfikowano: pośrednio.

---

## 4. Listy na GitHubie (awesome-*)

### 35. awesome-oss-investors
- URL: https://github.com/jonathimer/awesome-oss-investors
- Dane: VC inwestujące w komercyjny open source (warunek: min. 3 inwestycje w startupy oparte na projekcie OSS i nadal aktywne), z etapem, ticketem, siedzibą i przykładami. Europejskie przykłady: Angel Invest (DE, 0,1 mln USD), Crane (UK, 1 do 6 mln), Elaia (FR), Serena Capital (UE), Firstminute (UK), Fly Ventures (DE).
- Dostęp/koszt: darmowe; 479 gwiazdek, ostatni push 2025-07-25 (rok stary, weryfikować aktywność funduszy).
- Zweryfikowano: 2026-11-25, u źródła.

### 36. yueyueL/awesome-grants
- URL: https://github.com/yueyueL/awesome-grants , strona: https://yueyuel.github.io/awesome-grants
- Dane: 252+ zweryfikowanych okazji: stypendia, granty badawcze, darmowe moce obliczeniowe, dla OSS i indie developerów. CC0, 49 gwiazdek, aktualizacja 2026-11-23.
- Jak agent może użyć: parsowanie README (CC0, wolno przetwarzać), filtr „indie/OSS/compute”.
- Zweryfikowano: 2026-11-25, u źródła.

### 37. pleasedodisturb/awesome-ai-dev-funding
- URL: https://github.com/pleasedodisturb/awesome-ai-dev-funding
- Dane: 278 programów dla **solo developerów AI** w 7 kategoriach (kredyty laboratoriów AI, granty frameworków OSS, chmura, akceleratory, granty rządowe i fundacji, Web3, ścieżki przychodowe); flaga „Solo OK” i status; 116 otwartych i realnie dostępnych dla solo. Weryfikacja 2026-07-19, push 2026-11-22.
- Jak agent może użyć: najlepsza gotowa lista „free money” dla solo foundera; agent filtruje „Solo OK + Open” i sprawdza każdy program na oficjalnej stronie.
- Dopasowanie: **wysokie dla obu**.
- Zweryfikowano: 2026-11-25, u źródła.

### 38. doanbactam/awesome-builder-programs
- URL: https://github.com/doanbactam/awesome-builder-programs
- Dane: programy z kredytami, grantami i narzędziami dla studentów, startupów, OSS; tylko oficjalne strony programów; sekcja programów wstrzymanych. 165 gwiazdek, push 2026-11-10.
- Dopasowanie: średnie.
- Zweryfikowano: 2026-11-25, u źródła.

### 39. aidenixai/bootstrapped-credits
- URL: https://github.com/aidenixai/bootstrapped-credits
- Dane: kredyty dostępne **bez VC** (wystarczy zarejestrowana firma, strona, e-mail w domenie), ile, na jak długo, kiedy sprawdzone. 41 gwiazdek, push 2026-11-16.
- Zweryfikowano: 2026-11-25, u źródła.

### 40. Awesome-llms-labs/awesome-startup-credits
- URL: https://github.com/Awesome-llms-labs/awesome-startup-credits
- Dane: kredyty chmurowe, AI/API, narzędzia, granty gotówkowe z flagą verified/unverified (np. Akamai Cloud Rise do 120 tys. USD w 1. roku). MIT.
- Dopasowanie: średnie.
- Zweryfikowano: 2026-11-25, u źródła (metadane).

### 41. evalyze-ai/awesome-startup-fundraising
- URL: https://github.com/evalyze-ai/awesome-startup-fundraising
- Dane: narzędzia do decków, dopasowania inwestorów, darmowe listy inwestorów, CRM, data roomy, outreach, akceleratory, finansowanie bezudziałowe, skille Claude, „najaktywniejsze VC 2026”. Uwaga: prowadzi ją dostawca (Evalyze), możliwa stronniczość.
- Dopasowanie: średnie (dobry spis do przejrzenia raz).
- Zweryfikowano: 2026-11-25, u źródła.

### 42. maximally0/open-source-vc
- URL: https://github.com/maximally0/open-source-vc
- Dane: 226 projektów open source, zbiorów danych i standardów, na których działa VC (deal sourcing, CRM, wyceny); CC0.
- Dopasowanie: średnie.
- Zweryfikowano: 2026-11-25, u źródła (metadane).

### 43. isanthoshgandhi/awesome-vc-opensource i thesurenk/awesome-venture-capital
- URL: https://github.com/isanthoshgandhi/awesome-vc-opensource , https://github.com/thesurenk/awesome-venture-capital
- Dane: pierwsza: narzędzia OSS dla VC (sourcing, due diligence, wycena, cap table), push 2026-03; druga: ogólne zasoby VC, **nieaktualizowana od 2020-10** (niska wartość).
- Dopasowanie: niskie.
- Zweryfikowano: 2026-11-25, u źródła (metadane).

---

## 5. Open source: agenci i narzędzia AI

### 44. oncesylvia/fundraising-skills (Claude Code skills)
- URL: https://github.com/oncesylvia/fundraising-skills
- Co robi: lejek pitch-narrative → investor-targeting/investor-research → warm-path-finder → warm-intro / cold-email / cold-call → pipeline-tracker. Badanie inwestorów **na żywo z darmowych źródeł publicznych**, odmawia zmyślonych list i masowej wysyłki. Warm paths z własnego eksportu CSV z LinkedIn.
- Dostęp: darmowe (12 gwiazdek, push 2026-07-05); licencja do sprawdzenia.
- Jak użyć: wzorzec architektury skilli Bigshort, szczególnie reguła „brak źródła = brak inwestora na liście”.
- Dopasowanie: wysokie.
- Zweryfikowano: 2026-11-25, u źródła (README).

### 45. shawnpang/startup-founder-skills
- URL: https://github.com/shawnpang/startup-founder-skills
- Co robi: 50 zadań foundera jako skille (fundraising, sprzedaż, rekrutacja, prawo); wszystkie czytają wspólny `startup-context`; skill `investor-research` (kwalifikacja wg etapu, sektora, czeku, portfela). 396 gwiazdek.
- Dopasowanie: wysokie.
- Zweryfikowano: 2026-11-25, u źródła (README).

### 46. openprose/grant-finder
- URL: https://github.com/openprose/grant-finder
- Co robi: CLI w Go, bez kluczy API; buduje lokalny „ledger” z Grants.gov, Federal Register, RSS agencji; zwraca „Research Packet” JSON z dowodami, pochodzeniem, pewnością terminu, nakładem pracy i **negatywnymi dowodami** („brak pasujących programów ARPA-E”). Komendy research, explain, status, doctor.
- Dostęp: darmowe; zakres USA.
- Jak użyć: skopiować format Research Packet i ideę ledgera, podmienić źródła na EU F&T, CORDIS, PL harmonogramy.
- Dopasowanie: wysokie jako architektura.
- Zweryfikowano: 2026-11-25, u źródła (README).

### 47. darylalim/grant-writer-agent
- URL: https://github.com/darylalim/grant-writer-agent
- Co robi: LangChain Deep Agents + Claude; `discover` (grants.gov + web, ocena dopasowania z cytatem dla każdej oceny) i `draft` (wymagania z ogłoszenia, research grantodawcy, szkic i audyt sekcji). Nieznane fakty oznacza `[NEEDS INPUT: pytanie]` zamiast zmyślać. Nie wysyła wniosków. MIT, push 2026-11-04; wymaga kluczy Anthropic i Tavily.
- Jak użyć: wzorzec pisania wniosku z markerami braków i akceptacją człowieka (W7).
- Dopasowanie: wysokie jako wzorzec.
- Zweryfikowano: 2026-11-25, u źródła (README).

### 48. pipeworx-io/mcp-eu-funding-tenders
- URL: https://github.com/pipeworx-io/mcp-eu-funding-tenders
- Co robi: serwer MCP nad Search API portalu F&T, bez klucza (wbudowany publiczny `apiKey=SEDIA`). MIT, push 2026-11-09.
- Jak użyć: podłączyć do Bigshort jako gotowe narzędzie albo przepisać na własny adapter (mała zależność, mało gwiazdek).
- Dopasowanie: wysokie.
- Zweryfikowano: 2026-11-25, u źródła (metadane, opis).

### 49. CiubotaruBogdan/EU-Funding-Tenders-API
- URL: https://github.com/CiubotaruBogdan/EU-Funding-Tenders-API
- Co robi: nieoficjalna dokumentacja, kolekcja Postman, przykłady Python, lista ID programów i kodów krajów (PL = 20000986), opis formatu multipart i podwójnego parsowania pola participants. MIT.
- Jak użyć: dokumentacja do adaptera W1.
- Zweryfikowano: 2026-11-25, u źródła.

### 50. Bogdan0708/grant-scout
- URL: https://github.com/Bogdan0708/grant-scout
- Co robi: demo agentic RAG nad konkursami UE (Next.js, Vercel AI SDK), odpowiedzi z cytatami, ewaluacja LLM-as-judge w CI. MIT.
- Jak użyć: wzorzec testów jakości odpowiedzi Bigshort (zestaw pytań kontrolnych w CI).
- Zweryfikowano: 2026-11-25, u źródła (metadane).

### 51. HHS/simpler-grants-gov
- URL: https://github.com/HHS/simpler-grants-gov
- Co robi: oficjalny kod nowego Grants.gov (API, extracts), dokumentacja z serwerem MCP i llms.txt. 219 gwiazdek, aktywny codziennie.
- Dopasowanie: niskie (USA), przydatne jako wzorzec API dla agentów.
- Zweryfikowano: 2026-11-25, u źródła.

### 52. Recenzja pitch decka: OneWave-AI/claude-skills (pitch-deck-reviewer), rk-vashista/pitch, PitchPilot
- URL: https://github.com/OneWave-AI/claude-skills/blob/main/pitch-deck-reviewer/SKILL.md , https://github.com/rk-vashista/pitch , https://github.com/Akshat2634/PitchPilot-AI-Powered-Investor-Deck-Analyzer-Coach
- Co robi: skill Claude oceniający deck w 8 wymiarach (1 do 10, z dowodami, ocena ważona, uwagi slajd po slajdzie; repo MIT, 446 gwiazdek); multi-agent crewAI do analizy decka; LangGraph z symulacją pytań inwestorów.
- Jak użyć: pętla przeglądu decka w W6.
- Zweryfikowano: 2026-11-25, u źródła (metadane, fragmenty SKILL.md).

### 53. Mniejsze agenty grantowe
- tavisgoldwire/grant_finder_agent_public: scrapuje 30+ źródeł, ocena dopasowania przez Claude (https://github.com/tavisgoldwire/grant_finder_agent_public).
- Quazi-07/Research-Grant-Finder-Agent: wyszukiwanie i ranking grantów NIH (29 gwiazdek) (https://github.com/Quazi-07/Research-Grant-Finder-Agent).
- dsvxmedia/grant-engine: „open-source AI grant discovery and writing engine”, MIT (https://github.com/dsvxmedia/grant-engine).
- Dopasowanie: niskie (USA, nauka, non-profit); tylko jako inspiracja.
- Zweryfikowano: 2026-11-25, u źródła (metadane).

---

## 6. Komercyjne narzędzia AI do fundraisingu

### 54. 12inf
- URL: https://12inf.ai , porównanie: https://12inf.ai/resources/best-ai-investor-matching-tools
- Co robi: z adresu strony (i opcjonalnie decka) pisze brief firmy i zwraca shortlistę funduszy i aniołów pre-seed/seed z oceną, powodami dopasowania, źródłami.
- Koszt: brief i podgląd 3 profili bez logowania; reszta płatna (cennik na stronie).
- Dopasowanie: średnie.
- Zweryfikowano: 2026-11-25, u źródła (strona porównania, która jest autorstwa 12inf, więc stronnicza).

### 55. Evalyze
- URL: https://www.evalyze.ai
- Co robi: ocena gotowości i decka (0 do 100), ranking inwestorów wg etapu, sektora, lokalizacji, czeku i historii, szkice maili zatwierdzane ręcznie.
- Koszt: Starter za darmo (do 30 dopasowań, bez eksportu), Pro 10 USD/mies. rocznie (pośrednio, 12inf.ai).
- Dopasowanie: średnie (tanie, ale źródło danych nieopisane).
- Zweryfikowano: pośrednio.

### 56. Metal
- URL: https://www.metal.so
- Co robi: „AI operating system” do rund: inteligencja o inwestorach, ścieżki intro, pipeline, notatki ze spotkań, data room, MCP; usługa „Autopilot”.
- Koszt: na demo, celuje w późny seed i Series A.
- Dopasowanie: niskie teraz.
- Zweryfikowano: pośrednio.

### 57. Clay (szablony i Sculptor)
- URL: https://www.clay.com/templates , https://www.clay.com/tools/find-investor-leads
- Co robi: tabele z wodospadem 150+ dostawców danych; szablony „wspólni inwestorzy z firmami docelowymi”, „etap i lead investor firmy”, „wzbogacenie listy o dane o rundach”; Sculptor buduje wiersz na inwestora i szuka e-maili partnerów.
- Koszt: plan darmowy 500 akcji/mies. (pośrednio, frontal.so).
- ToS: szablon „Enrich a list with fundraising information” scrapuje strony Crunchbase przez Zenrows, co **łamie regulamin Crunchbase**; nie kopiować tej części.
- Dopasowanie: średnie (wzorce wzbogacania warto skopiować, dostawców niekoniecznie).
- Zweryfikowano: pośrednio (opisy szablonów w wynikach wyszukiwania).

---

## 7. Opublikowane prompty i workflowy (X, blogi)

### 58. Martin Tobias (Incisive Ventures): GPT „find the perfect investor” i „Pre-Seed Deck Scorer”
- URL: https://x.com/MartinGTobias/status/1978825872271389023 , https://x.com/MartinGTobias/status/1999344450007695807
- Co robi: custom GPT zadaje 5 pytań o startup i zwraca 20 najlepiej pasujących inwestorów oraz szablon wiadomości; drugi GPT ocenia deck pod kątem dopasowania do konkretnego funduszu, a nie ogólnej jakości.
- Wzór do skopiowania: (1) krótki wywiad strukturalny zamiast długiego formularza; (2) ocena decka „per fundusz” z jego tezą jako rubryką.
- Ryzyko: listy z czystego LLM bez wyszukiwania bywają zmyślone lub nieaktualne; w Bigshort każde nazwisko musi przejść weryfikację źródłem.
- Zweryfikowano: 2026-11-25, pośrednio (treść postów w wynikach wyszukiwania; nie otwierałem linków X).

### 59. BuccoCapital „Initiation Report” Deep Research prompt (V2)
- URL: https://x.com/buccocapital/status/1952405795485684039 , https://x.com/buccocapital/status/1995310794339176558
- Co robi: prompt z 13-punktową ramą analizy firmy, tylko weryfikowalne źródła, ścisły format wyjścia, poprawka „nie bądź zbyt pozytywny”.
- Wzór do skopiowania: ta sama struktura do analizy **funduszu** (teza, ostatnie 10 inwestycji, wielkość czeku, partner właściwy dla AI infra, konflikty z portfelem, sygnały aktywności) jako „karta inwestora” w Bigshort.
- Zweryfikowano: 2026-11-25, pośrednio.

---

## 8. Co agent może użyć od razu za darmo


1. **EU Funding & Tenders Search API** (pozycja 17). Bez klucza. Przykład:
   ```bash
   echo '{"bool":{"must":[{"terms":{"type":["1","2","8"]}}]}}' > q.json
   curl -s -X POST "https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA&text=large%20language%20model&pageSize=50&pageNumber=1" \
     -F "query=@q.json;type=application/json" -F 'languages=["en"];type=application/json'
   ```
   Plus gotowy serwer MCP pipeworx-io/mcp-eu-funding-tenders (pozycja 48).
2. **Seedlist JSON** (pozycja 24): `https://seedlist.com/enrichment-index.json`, `startup-investor-map.json`, `rounds-feed.json`. Bez klucza.
3. **CORDIS bulk** (pozycja 18): kto dostał pieniądze UE na podobną technologię i z kim.
4. **Portal Funduszy Europejskich: XLSX harmonogramów** (pozycja 25) oraz **grantledger.eu** do przeglądania (pozycja 26).
5. **Listy GitHub** (pozycje 35 do 41) przez `raw.githubusercontent.com` lub GitHub API (bez tokenu 60 zapytań/h): awesome-oss-investors, awesome-ai-dev-funding, bootstrapped-credits, awesome-grants (CC0), awesome-builder-programs.
6. **Awesome AI Market Maps** (pozycja 27): CSV i RSS, fundusze z tezą w AI infra i agentach.
7. **YC OSS API** (pozycja 22): `https://yc-oss.github.io/api/companies/all.json`, mapa konkurencji przed aplikacją do YC.
8. **HN Algolia API** (pozycja 23): `https://hn.algolia.com/api/v1/search_by_date?query=...&tags=story`.
10. **Grants.gov search2** (pozycja 21): bez klucza, ale na razie mało przydatne dla firmy z PL.
11. **aifree.dev RSS** (pozycja 33): nowe i wygasające kredyty AI.


---

## 9. Ograniczenia prawne, o których agent musi wiedzieć

- **RODO**: dane partnerów funduszy i aniołów to dane osobowe. Zbierając je z publicznych źródeł, administrator ma obowiązek informacyjny z art. 14 RODO, a podstawą będzie prawnie uzasadniony interes [WNIOSEK, do konsultacji z prawnikiem]. Bigshort powinien trzymać tylko dane potrzebne do kontaktu, z datą i źródłem, i umieć je usunąć.
- **Zimne e-maile z Polski**: Prawo komunikacji elektronicznej (od 10.11.2024) wymaga zgody na marketing bezpośredni drogą elektroniczną [WNIOSEK: czy pitch do funduszu to „marketing bezpośredni”, wymaga opinii prawnej]. Bezpieczne kanały: formularze zgłoszeń funduszy, „Submit deck” na OpenVC (inwestorzy się zgodzili), warm intro.

---

## 10. Wzorce agentów do skopiowania

### W1. Codzienny skaner grantów UE i PL
2. Raz dziennie: zapytania do EU F&T Search API (typy grantów, status open/forthcoming potwierdzony facetem), cotygodniowo: pobranie XLSX harmonogramów z funduszeeuropejskie.gov.pl i porównanie z poprzednią wersją.
3. Normalizacja do „ledgera” w SQLite (wzór openprose/grant-finder): id, tytuł, program, termin, budżet, URL oficjalny, data pobrania.
4. Ocena dopasowania przez LLM z obowiązkowym cytatem z ogłoszenia dla każdego kryterium (wzór darylalim) i polem „negatywne dowody” (czego nie znaleziono).
5. Wynik: digest „nowe od wczoraj / terminy w 30 dni / odrzucone z powodem”. Testy jakości jak w Bogdan0708/grant-scout: zestaw znanych konkursów, które muszą zostać znalezione.

### W2. „Fundusz właśnie zebrał pieniądze” (świeży kapitał = otwarte czeki)
1. Źródła: EDGAR FTS z `forms=D` i słowami „artificial intelligence”, „AI”, „venture”; Form D Data Sets co kwartał; HN Algolia (`"new fund"`, `"Fund I"`, `"pre-seed fund"`); RSS EU-Startups o nowych funduszach w Europie.
2. Dla każdego nowego funduszu: strona, teza, partner od AI, typowy czek, czy inwestuje w Europie.
3. Filtr: pre-seed/seed, AI infra lub agenci, akceptuje founderów z UE.
4. Wynik: karta inwestora (W4) i propozycja kanału (formularz, OpenVC, intro).

### W3. Odwrócone wyszukiwanie: inwestorzy firm podobnych do nas
1. Zbuduj listę porównywalnych firm: yc-oss (tagi AI, open-source, developer tools), CORDIS (beneficjenci EIC w podobnej technologii), Awesome AI Market Maps (mapy „inference”, „agents”).
2. Dla każdej firmy znajdź inwestorów: Seedlist `startup-investor-map.json`, komunikaty prasowe, Form D, ręczny eksport z Tracxn Lite lub PitchBook for Startups.
3. Zlicz, kto powtarza się w wielu podobnych firmach i kto inwestował w ostatnich 18 miesiącach.
4. Odfiltruj fundusze z konfliktem (bezpośredni konkurent w portfelu).

### W4. Lista bez halucynacji (karta inwestora z dowodami)
Każdy inwestor trafia na listę tylko, jeśli agent ma:
- link do strony funduszu z tezą (data odczytu),
- co najmniej jedną inwestycję z ostatnich 18 miesięcy w podobnym obszarze (link),
- etap i typowy czek (źródło lub oznaczenie „nieznane”),
- geografię (czy inwestuje w PL/UE),
- osobę kontaktową właściwą dla AI (publiczny profil) i kanał (formularz, OpenVC, intro).
Brak dowodu = pole `[NEEDS INPUT]` albo odrzucenie. To połączenie reguł z oncesylvia/fundraising-skills i formatu z darylalim/grant-writer-agent. Ramę analizy funduszu można wziąć z promptu BuccoCapital (pozycja 59).

### W5. Szukanie ścieżek warm intro
3. Dla każdej ścieżki: szkic krótkiej prośby o intro i „forwardable” (3 do 5 zdań o firmie, które pośrednik może przesłać dalej; wzór z Seedlist i fundraising-skills).

### W6. Pętla przeglądu decka pod konkretny fundusz
1. Rubryka ogólna: 8 wymiarów z pitch-deck-reviewer (ocena 1 do 10 z dowodem ze slajdu).
2. Rubryka „per fundusz”: teza i ostatnie inwestycje funduszu jako kryteria (wzór GPT Martina Tobiasa).
4. Wynik: lista poprawek slajd po slajdzie i wersja decka per typ inwestora (VC infra vs VC aplikacyjne vs grant).

### W7. Szkic wniosku grantowego z markerami braków
1. Wejście: PDF ogłoszenia i profil firmy.
2. Ekstrakcja wymagań i kryteriów oceny do tabeli; każde kryterium z numerem strony.
3. Szkic sekcji; każdy fakt nieznany jako `[NEEDS INPUT: pytanie]` (np. przychody, TRL, liczba użytkowników).
4. Audyt: czy każde kryterium oceny ma odpowiedź; lista załączników.

### W8. Zbieracz kredytów i „free money”
1. Co tydzień: parsowanie awesome-ai-dev-funding (filtr „Solo OK” i „Open”), bootstrapped-credits, awesome-builder-programs, RSS aifree.dev.
2. Weryfikacja każdego programu na oficjalnej stronie (data, kwota, wymagania: czy wymaga VC lub partnera akceleratora, czy dopuszcza firmy z PL).
3. Rejestr: program, kwota, status wniosku, data wygaśnięcia kredytów, przypomnienie 30 dni przed.

### W9. Człowiek w pętli dla baz z zakazem automatyzacji
1. Agent pisze „specyfikację wyszukiwania” dla OpenVC, Signal, Tracxn Lite lub PitchBook: dokładne filtry, kolejność, co skopiować.
3. Agent normalizuje, usuwa duplikaty z innymi źródłami, weryfikuje każdy rekord publicznie (W4) i dopisuje do CRM.
To pozwala korzystać z najlepszych baz bez łamania regulaminów.

---
