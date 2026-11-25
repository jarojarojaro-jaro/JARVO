---
source: "research floty Jarva 2026-11-25 (platformy sprawdzone na żywo, lista źródeł od właściciela, przegląd X Grokiem)"
reviewed: "2026-11-25"
---

# Platformy, agregatory i kanały ogłoszeń hackathonów

Stan wiedzy: 25.11.2026. Autor: PlatformyHack (research web, bez logowania, bez rejestracji, bez wysyłania zgłoszeń).

## Legenda

- **[API-TEST 25.11]**: endpoint wywołany przez nas `curl` 25.11.2026 bez logowania, odpowiedział danymi (JSON/RSS/ICS).
- **[HTML]**: brak znanego publicznego JSON, dane tylko w HTML (często Next.js RSC lub JSON-LD).
- **[AUTH]**: dane maszynowe tylko z kluczem/kontem.
- **[NZ]**: niezweryfikowane u źródła pierwotnego (pochodzi z wtórnego źródła albo z syntezy wyszukiwarki).
- **[INF]**: nasz wniosek, nie cytat.
- „PL solo”: czy osoba fizyczna z Polski, startująca sama, może wziąć udział i dostać nagrodę.
- Zasady AI: czy wolno używać kodu z AI i czy dopuszczony jest w pełni autonomiczny agent.

Uwaga ogólna o ToS: wiele serwisów technicznie wystawia JSON bez logowania, ale ich regulaminy zabraniają „scrapingu”. Robots.txt nie uchyla ToS. Tam, gdzie ToS zakazuje automatyzacji, agent powinien czytać tylko oficjalne feedy (RSS, ICS, publiczne API) albo pytać właściciel o zgodę na ostrożne, rzadkie odpytywanie.

---

## A. Meta-agregatory i kalendarze zbiorcze

### 1. HackathonRadar
- URL: https://www.hackathonradar.com/ (baza: /database, discover: /discover/europe)
- Co listuje: hackathony z 40+ platform w jednej bazie, deduplikacja, mapy, statystyki, organizatorzy i sponsorzy. Ma bota Discord (`/subscribe` z filtrami), webhooki (/settings/webhooks), MCP, REST API.
- Filtry: miasto, kraj, kategoria, „near me”, mapa, zapisane wyszukiwania z alertami.
- Dostęp automatyczny: **REST API wyłącznie na planie Enterprise** (Bearer, klucze w /settings/api-access, potwierdzone w /docs/api i /openapi.yaml). **MCP** `https://www.hackathonradar.com/mcp` wymaga OAuth przez Clerk (test: 401 `invalid_token` bez autoryzacji), ale wg /llms.txt narzędzia `search_hackathons`, `get_hackathon`, `create_saved_search` są „na wszystkich planach”, czyli wystarczy darmowe konto. Strony /discover/* mają JSON-LD `ItemList` z obiektami `Event` (startDate, endDate, url) [API-TEST 25.11, 12 wydarzeń na /discover/europe]. Sitemap: 4616 URL-i.
- ToS/robots: robots.txt `Disallow: /api/`, `/r/`. Właściciel wprost rekomenduje MCP zamiast scrapingu.
- Ocena: najlepszy pojedynczy „lejek” zbiorczy, ale pełny dostęp maszynowy wymaga konta (MCP) albo płatnego planu.
- Źródła: https://www.hackathonradar.com/llms.txt, https://www.hackathonradar.com/docs/api, https://www.hackathonradar.com/openapi.yaml. Zweryfikowano 25.11.2026.

### 2. HackList (x.com/HackListHQ)
- URL: https://hacklist.io/, X: https://x.com/HackListHQ
- Co listuje: hackathony, bounty, granty i programy AI/Web3 zbierane głównie z postów na X; ceny, deadline, link do zgłoszenia.
- Dostęp automatyczny: **`GET https://hacklist.io/api/opportunities`** [API-TEST 25.11]: JSON `{count, generated_at, items[]}`, 206 pozycji (107 hackathon, 73 bounty, 13 grant, 13 program). Pola: `type, title, organizer, verified, description, category, format, prize, deadline, apply_url, created_at`. Cache ok. 20 min. Istnieje nieoficjalny serwer MCP (github.com/mrfomoweb3/hacklist-mcp).
- ToS: nie znaleziono zakazu; feed opisany jako „official feed provided by HackList” [NZ].
- PL solo / AI: zależy od pozycji; opisy często zawierają ograniczenia (np. „US-based developers 18+”), więc agent musi parsować `description`.
- Ocena: bardzo dobry, tani w odczycie feed dla krypto/AI. Zweryfikowano 25.11.2026.

### 3. ML Contests
- URL: https://mlcontests.com/
- Co listuje: konkursy ML/data science/robotyki ze wszystkich platform (Kaggle, Zindi, Codabench, DrivenData, Hugging Face, CrunchDAO, AIcrowd, EvalAI, Solafune, niezależne). Raport roczny „State of ML Competitions”.
- Filtry: tagi (agents, llm, vision, timeseries...), platforma, nagroda, deadline.
- Dostęp automatyczny: lista jest osadzona w HTML jako **JSON w atrybucie `data-competitions`** [API-TEST 25.11]: 413 rekordów z polami `name, url, tags, launched, registration-deadline, deadline, added, prize, platform, sponsor, conference`. RSS **https://mlcontests.com/rss.xml** działa, ale zawiera artykuły, nie konkursy. `/robots.txt` nie istnieje (zwraca stronę 404).
- ToS: nie znaleziono regulaminu zakazującego odczytu [NZ].
- Ocena: najlepsze źródło konkursów ML z nagrodami; jeden GET dziennie wystarczy.

### 4. CLIST
- URL: https://clist.by/
- Co listuje: kalendarz konkursów algorytmicznych z ~setek serwisów (Codeforces, AtCoder, LeetCode, Kaggle, CTF itp.).
- Dostęp automatyczny: API v4 `https://clist.by/api/v4/contest/?upcoming=true` [API-TEST 25.11: **401 bez klucza**]. Wymaga darmowego konta i nagłówka `Authorization: ApiKey user:key` [AUTH].
- ToS/robots: robots blokuje /calendar/, /list/, /get/events/; API jest właściwą drogą.
- Ocena: przydatne dla konkursów programistycznych (rzadko z gotówką), mniej dla hackathonów.

### 5. Hackathon.com
- URL: https://www.hackathon.com/ (np. /online, /organizer/bemyapp)
- Co listuje: globalny katalog hackathonów (online, miasta, organizatorzy).
- Dostęp automatyczny: [HTML], brak sitemap.xml (404), brak publicznego API (zgadywane /api/events = 404). robots: `Disallow:` puste (wszystko dozwolone).
- Ocena: wtórne źródło, słabszy od HackathonRadar. Zweryfikowano 25.11.2026.

### 6. All Hackathons (allhackathons.com, pl.allhackathons.com)
- URL: https://allhackathons.com/, https://pl.allhackathons.com/hackathons/
- Co listuje: katalog hackathonów, wersja PL z listą polskich wydarzeń.
- Dostęp: [HTML], strona PL ok. 13 KB, brak API (/api/hackathons 404). robots: tylko `/admin/` zablokowany.
- Ocena: uzupełniające.

### 7. Hackathon Hub (Europa)
- URL: https://hackathonhub.eu/ (np. /hackathons/2027, /hackathons/ai)
- Co listuje: europejski katalog hackathonów, w tym 135 nadchodzących hackathonów AI w Europie [NZ, wg wyszukiwarki 11.2026]; dane częściowo zbierane automatycznie (sami to deklarują w /terms).
- Dostęp: strony kategorii mają **JSON-LD `ItemList` z `Event`** [API-TEST 25.11: 43 wydarzenia na /hackathons/2027]. Brak RSS (/feed.xml, /rss.xml = 404).
- ToS: /terms opisuje zasady listingu, nie znaleźliśmy zakazu odczytu [NZ].
- Ocena: najlepszy katalog stricte europejski; łatwy parsing JSON-LD.

### 8. Hackalist
- URL: https://github.com/hackalist/hackalist.github.io
- Co to: historyczny otwarty JSON z hackathonami per miesiąc.
- Dostęp: `hackalist.github.io/api/1.0/2026/12.json` = 404 [API-TEST 25.11]. Strona sama opisuje się jako „archive”.
- Ocena: martwe/archiwum, pomijać.

### 9. Awesome Hackathon
- URL: https://github.com/dribdat/awesome-hackathon
- Co to: lista narzędzi i platform do organizowania hackathonów (nie lista wydarzeń). README dostępny jako raw [API-TEST 25.11].
- Ocena: tylko jako źródło nazw platform do monitoringu.

### 10. Tatum Web3 Hackathons
- URL: https://apps.tatum.io/hackathons
- Co listuje: „live directory of web3 hackathons, 100+ ongoing events” [NZ].
- Dostęp: [HTML] Next.js RSC, 16 KB, brak API.
- Ocena: drugorzędny agregator web3.

### 11. Agent Bounty Index (sheikhminds)
- URL: https://github.com/sheikhminds/agent-bounty-index
- Co listuje: codzienny indeks bounty, w których **agent AI ma prawo startować** (Superteam Earn, Opire), z podziałem `open/blocked/risky/other`.
- Dostęp: **`https://sheikhminds.github.io/agent-bounty-index/data.json`** [API-TEST 25.11]: 14 pozycji, `open: []` (dziś żadna nie jest otwarta dla agentów).
- Ocena: gotowy wzorzec dla agenta Hacker; pokazuje, że w praktyce prawie wszystko jest „HUMAN_ONLY”.

### 12. audit-contest-ai-rules (Munim)
- URL: https://github.com/munimtechnologies/audit-contest-ai-rules
- Co to: datowany, źródłowany przegląd platform audytowych (Sherlock, Cantina, HackenProof, Immunefi, CodeHawks) pod kątem zasad AI, KYC, wypłat i tłoku, plus narzędzie generujące znormalizowany JSON z aktywnymi konkursami [README API-TEST 25.11].
- Ocena: bardzo przydatne źródło reguł AI dla audytów.

### 13. bounty-targets-data (arkadiyt)
- URL: https://github.com/arkadiyt/bounty-targets-data
- Co to: aktualizowane co kilka godzin zrzuty programów bug bounty: HackerOne (18,8 MB), Bugcrowd (1,2 MB), Intigriti (0,6 MB), YesWeHack (0,1 MB) [API-TEST 25.11, raw GitHub].
- Ocena: najprostszy legalny sposób na listę programów bug bounty bez logowania.

### 14. Inne agregatory znalezione po drodze
- dev.events (https://dev.events/hackathons/EU/llm), hackathonmap.com, aiagentbounties.com (lista bounty dla agentów), Hack-HQ (github.com/Hack-HQ/hackhq), substack „hackathons.substack.com”. Wszystkie [NZ], nie testowane szczegółowo.

---

## B. Globalne platformy hackathonów

### 15. Devpost
- URL: https://devpost.com/hackathons
- Co listuje: największy katalog hackathonów online i stacjonarnych (firmowe: Google, AWS, OpenAI, GitLab, Atlassian; studenckie MLH).
- Filtry: status (open, upcoming, ended), lokalizacja (online/in-person), temat (themes), open_to (public, invite), sortowanie po nagrodzie, wyszukiwarka.
- Nagrody: od kilkuset USD do 100-150 tys. USD (np. Kiroween 2026: 100 000 USD, Codegeist 2026: 120 000 USD, Cosmo Hacks 2026: 146 805 USD) [API-TEST 25.11].
- PL solo: zależy od regulaminu konkretnego hackathonu; zwykle „worldwide” z wyłączeniem krajów sankcjonowanych i czasem kilku jurysdykcji; Polska zazwyczaj dozwolona [INF]. Solo zwykle dozwolone.
- Zasady AI: brak jednej reguły. 2026: od „AI coding assistants are allowed with no restrictions” z obowiązkiem ujawnienia (Multimodal AI Hackathon 2026) po zakaz generowania całego projektu (vsHacks 2026). Ujawnienie w „Built With” i README to standard.
- Dostęp automatyczny: **`https://devpost.com/api/hackathons?status[]=open&page=1`** [API-TEST 25.11]: JSON, 9 na stronę, `meta.total_count` (150 open+upcoming; 55 online open; 27 AI open). Działające parametry: `status[]=open|upcoming|ended`, `challenge_type[]=online|in-person`, `themes[]=Machine Learning/AI`, `open_to[]=public`, `search=agent`, `order_by=prize-amount`. Pola: `title, url, prize_amount (HTML), submission_period_dates, themes, displayed_location, registrations_count, invite_only, organization_name, time_left_to_submission, winners_announced`.
- ToS/robots: robots.txt pozwala wszystkim (`Disallow:` puste). **ToS zakazuje** „manual or automated software, devices, scripts robots… to access, scrape, crawl or spider the Site”. /api/hackathons jest nieudokumentowane, bez rate limitu. Zalecenie: rzadkie odczyty (np. raz dziennie) albo czytanie przez HackathonRadar/HackList.
- Źródła: https://info.devpost.com/legal/terms-of-service, https://multimodal-ai-hackathon-2026-7.devpost.com/rules, https://vshacks-2026.devpost.com/rules. Zweryfikowano 25.11.2026.

### 16. MLH (Major League Hacking)
- URL: https://www.mlh.com/seasons/2027/events (mlh.io przekierowuje na mlh.com)
- Co listuje: sezon studenckich hackathonów (Ameryka Płn., Europa i UK, APAC), Global Hack Week (https://ghw.mlh.com/events).
- Nagrody: zwykle sprzęt i drobne kwoty, sponsorskie nagrody MLH.
- Format: głównie stacjonarne; MLH ogranicza się do ok. 1 cyfrowego hackathonu na weekend.
- PL solo: wydarzenia europejskie dostępne (np. HackEPS Lleida, HackSheffield 28-29.11.2026); często dla studentów [NZ per event].
- Zasady AI: MLH Member Events **muszą** pozwalać na genAI/LLM; zespoły mają być „honest and transparent” co do narzędzi AI (mlh-policies na GitHub).
- Dostęp: [HTML] (Rails, karty wydarzeń), robots blokuje /graphql, /v4/. Brak publicznego JSON.
- Źródła: https://github.com/MLH/mlh-policies/blob/main/standard-hackathon-rules.md, member-event-guidelines.md. Zweryfikowano 25.11.2026.

### 17. DoraHacks
- URL: https://dorahacks.io/hackathon (też bounty, BUIDL, granty, newsletter)
- Co listuje: hackathony Web3, AI, quantum, biotech; 849 hackathonów w bazie, 12 trwających [API-TEST 25.11].
- Nagrody: typowo 1,5-20 tys. USD per hackathon, flagowe ekosystemowe do kilkuset tys.; często w tokenach.
- Format: przeważnie wirtualne (`venue_form: Virtual`), część IRL.
- PL solo: zwykle otwarte globalnie, KYC przy wypłacie bywa wymagane [INF].
- Zasady AI: zależne od organizatora; DoraHacks ma „Organizer AI Toolkits” [NZ co do reguł uczestników].
- Dostęp automatyczny: **`https://dorahacks.io/api/v1/hub/hackathons?page=1&page_size=50`** [API-TEST 25.11], filtr `&status=ongoing` (12) i `&status=upcoming` (1). Pola: `title, uname, bonus_price, bonus_token, timeline_start, timeline_end (unix), venue_form, tags, ecosystem, hackers_count, buidls_count`. Endpoint ustalony z bundla JS (prefiks `dorahacks.io/api/v1` + `hub/`), nieudokumentowany.
- ToS: brak robots.txt (pusty); regulamin nie sprawdzony pod kątem scrapingu [NZ].
- Zweryfikowano 25.11.2026.

### 18. ETHGlobal
- URL: https://ethglobal.com/events
- Co listuje: hackathony Ethereum (IRL: Cannes, NY, Lisbon, Tokyo, Buenos Aires; async online: ETHOnline, „agents”, „autonomous”, HackMoney), konferencje (ETHConf), „cafe” i happy hours.
- Nagrody: NY 2026 225 tys. USD+, Lisbon 2026 125 tys. USD+, ETHOnline 2026 82 tys. USD w 10 ścieżkach sponsorów.
- Daty 2027 [NZ]: Cannes 14-16.04.2027, NY 14-16.06.2027 (ETHConf), Tokyo 23-25.08.2027, Lisbon 14-16.10.2027.
- PL solo: tak, solo dozwolone; online eventy dostępne z Polski.
- Zasady AI: AI dozwolone (ChatGPT, Claude Code, Copilot, Cursor), ale trzeba udokumentować gdzie i jak; projekty „całkowicie z AI” mogą stracić prawo do nagród partnerskich i finału.
- Dostęp: [HTML] Next.js (1,9 MB strona /events zawiera wszystkie slugi), brak robots.txt, brak publicznego API.
- Źródła: https://ethglobal.com/events/newyork2026/info/details, https://ethglobal.com/rules, https://ethereal.news/calendar/. Zweryfikowano 25.11.2026.

### 19. lablab.ai / Starfield Labs / lablab.build
- URL: https://lablab.ai (przekierowuje 301 na **https://starfieldlabs.ai/ai-hackathons**), https://lablab.build/ai-hackathons
- Co to: hackathony AI (weekendowe i tygodniowe, online i w miastach), sponsorzy AI (AMD, Vultr, AssemblyAI, AI21). Rebrand: „LabLab AI is now Starfield Labs”. Domena lablab.build (© NativelyAI Inc.) nadal publikuje listę ok. 40 hackathonów, np. „AMD AI League”, „Vultr: Agent Rush”, „AGENT STACK 48”.
- Nagrody: zwykle kilka do kilkudziesięciu tys. USD plus kredyty [NZ].
- PL solo: tak, „team up or go solo”.
- Zasady AI: platforma wprost promuje budowanie „people and their AI agents side by side”; AI jest rdzeniem [NZ co do formalnych reguł].
- Dostęp: [HTML] Next.js RSC; starfieldlabs.ai robots blokuje `/api/`; lablab.build ma JSON-LD tylko z breadcrumbs i nazwami (bez dat). Brak publicznego JSON [API-TEST 25.11]. Sitemapy: starfieldlabs.ai/sitemap.xml.
- Zweryfikowano 25.11.2026; relacja Starfield Labs vs lablab.build niejasna [NZ].

### 20. Devfolio
- URL: https://devfolio.co/hackathons
- Co listuje: hackathony głównie z Indii (ETHIndia, studenckie), część online.
- Dostęp automatyczny: **`POST https://api.devfolio.co/api/search/hackathons`** z body `{"type":"application_open","from":0,"size":20}` [API-TEST 25.11]: Elasticsearch, 23 otwarte, pola `name, is_online, country, city, starts_at`. robots: wszystko dozwolone.
- PL solo: większość stacjonarna w Indiach; online rzadko [INF].
- Ocena: niski priorytet.

### 21. HackerEarth
- URL: https://www.hackerearth.com/challenges/hackathon/
- Co listuje: hackathony firmowe i „Monthly Challenges”, część globalnych (np. TinyFish, Zerve 10 tys. USD).
- Dostęp: **`https://www.hackerearth.com/chrome-extension/events/`** [API-TEST 25.11]: JSON dla ich wtyczki Chrome, 2 wydarzenia (ContextCon, Groww Next ‘26), pola `title, url, challenge_type, status, start/end_timestamp`.
- PL solo: zależy od wyzwania.
- Ocena: średni.

### 22. Unstop
- URL: https://unstop.com/hackathons
- Co listuje: 7062 rekordów hackathonów (głównie Indie, część „international”).
- Dostęp: `https://unstop.com/api/public/opportunity/search-result?opportunity=hackathons&page=1&per_page=20` [API-TEST 25.11, działa], ale **robots.txt: `Disallow: /api/*`**. Ciekawostka: robots wprost „Allow” dla botów LLM na stronach.
- PL solo: często tylko Indie; są tory „international” [NZ per event].
- Ocena: niski priorytet, nie odpytywać /api.

### 23. Hack2skill
- URL: https://hack2skill.com/
- Co listuje: hackathony firmowe (Google Solution Challenge, Snowflake, IBM), część globalnych (np. Future Health Challenge „from any country”, Snowflake CoCo CLI 10 tys. USD, tylko APJ).
- Dostęp: [HTML], brak API.
- Ocena: niski priorytet, filtrować „Global”.

### 24. TAIKAI
- URL: https://taikai.network/en/hackathons
- Co listuje: hackathony europejskie (Portugalia, **CASSINI Hackathons UE**, Eclipse Foundation, OutSystems 17,5 tys. USD, Hack4Guimarães 20 tys. USD), web3 i AI. Nagrody często także w tokenie $TKAI.
- Dostęp: strona zawiera `__NEXT_DATA__` z listą (slugi w HTML) [API-TEST 25.11]; GraphQL `https://api.taikai.network/api/graphql` odpowiada, ale introspekcja wyłączona. Sitemap: taikai.network/sitemap.xml. robots blokuje tylko /auth.
- PL solo: zwykle tak; CASSINI wymaga udziału w lokalizacji [NZ].
- Ocena: ważne dla UE (CASSINI).

### 25. BeMyApp
- URL: https://www.bemyapp.com/events/
- Co to: agencja robiąca hackathony white-label (Huawei Tech Arena Ireland 6 tys. EUR, Xylem, IBM NCCU 10 tys. USD).
- Dostęp: [HTML], JSON-LD tylko breadcrumbs. Brak API.
- Ocena: rzadkie, ale czasem dla Europy.

### 26. AngelHack
- URL: https://angelhack.com/
- Co to: globalne hackathony i programy innowacyjne.
- Dostęp: **RSS `https://angelhack.com/feed/`** (WordPress) [API-TEST 25.11].
- Ocena: niski wolumen.

### 27. Devnovate
- URL: https://devnovate.co/
- Dostęp: SPA 1,5 KB, brak treści bez JS [API-TEST 25.11]. Mało informacji, [NZ].

### 28. Reskilll
- URL: https://reskilll.com/allHacks
- Co to: hackathony online w Indiach. [HTML] 544 KB, JSON-LD bez wydarzeń. Niski priorytet.

### 29. Commudle
- URL: https://www.commudle.com/
- Co to: społeczności tech (Indie), wydarzenia. API `api.commudle.com` zwróciło 503 [API-TEST 25.11]. Niski priorytet.

### 30. TechGig
- URL: https://techgig.com/challenge
- Co to: wyzwania i hackathony (Indie). Link „RSS” prowadzi do strony newslettera, nie feedu [API-TEST 25.11]. Niski priorytet.

### 31. Hack Club Hackathons
- URL: https://hackathons.hackclub.com/
- Co listuje: hackathony licealne/studenckie na świecie.
- Dostęp: **`https://hackathons.hackclub.com/api/events/upcoming`** [API-TEST 25.11]: JSON, pola `name, website, start, end, virtual, hybrid, city, country`. Drugi szybki request zwrócił nie-JSON, więc jest limit [INF].
- PL solo: zwykle dla młodzieży; mała wartość nagród.

### 32. GDG (Google Developer Groups)
- URL: https://gdg.community.dev/
- Co listuje: wydarzenia GDG (Bevy), w tym hackathony i Build with AI.
- Dostęp: **`https://gdg.community.dev/api/search/event/?result_types=upcoming_event&page_size=50`** [API-TEST 25.11]: 66 043 wyników, paginacja; też `/api/event/?status=Live`.
- Ocena: dobre źródło lokalnych hackathonów GDG w Polsce (filtrować po chapter).

### 33. Encode Club
- URL: https://www.encodeclub.com/programmes (encode.club to SPA)
- Co to: hackathony i bootcampy AI/web3, dużo online i za darmo: Concordium Trusted Agents (od 2.11.2026, 6 tyg. online), Solana Hackathon 2026 (4 tyg. online, „open to everyone, wherever you are”), Encode Vibe Coding Hackathon („the only rule is you MUST build with AI”), AI London 2026.
- Nagrody: kilka do 30 tys. USD, ścieżki akceleracyjne (Shape Rotator 50 tys. USD per zespół).
- Dostęp: [HTML] SPA; wydarzenia często na Luma.
- Ocena: wysoka dla floty (online, AI wymagane lub dozwolone).

### 34. Colosseum (Solana)
- URL: https://colosseum.com/hackathon (colosseum.org też działa)
- Co to: główne online hackathony Solany: Frontier (6.04-11.05.2026, 2857 zgłoszeń, 250 tys. USD pre-seed dla zwycięzców), Fall 2026 (28.09-2.11.2026). **Agent Hackathon (2-12.02.2026, 100 tys. USDC), w którym startowały agenty AI, nie ludzie.**
- PL solo: tak, globalne online.
- Dostęp: [HTML], blog z RSS (blog.colosseum.com) [NZ].
- Ocena: bardzo wysoka; precedens konkursu dla agentów.

### 35. HackQuest
- URL: https://www.hackquest.io/hackathons
- Co to: web3 hackathony i buildathony (Arbitrum Open House 115 tys. USD, 0G APAC 150 tys. USD).
- Dostęp: [HTML] Next.js RSC; /api/hackathons = 404.
- Ocena: średnia (web3, online).

### 36. AKINDO
- URL: https://akindo.io/
- Co to: „buildathony” w modelu WaveHack: zgłaszasz postępy w kolejnych falach i dostajesz granty (0G 50 tys. USD, NERO 30 tys. USD, Midnight 12,5 tys. USD).
- Dostęp: [HTML] Next.js RSC.
- Ocena: wysoka dla agentów kodujących (iteracyjne fale nagradzają ciągłą pracę).

### 37. Superteam Earn
- URL: https://superteam.fun/earn (dawniej earn.superteam.fun)
- Co listuje: bounty i projekty Solany (treści, rozwój, design), granty.
- Dostęp: **`https://superteam.fun/api/listings?type=bounty`** [API-TEST 25.11]: 11 pozycji, pola `title, rewardAmount, token, deadline, status, type, sponsor, agentAccess`. **Agent API**: `GET https://superteam.fun/api/agents` zwraca opis (`register: POST /api/agents`, `submit: POST /api/agents/submissions/create`) [API-TEST 25.11].
- Zasady AI: pole `agentAccess` = `AGENT_ALLOWED` lub `HUMAN_ONLY`. **Dziś wszystkie 11 otwartych bounty mają `HUMAN_ONLY`.**
- PL solo: tak (wiele bounty globalnych, część regionalnych Superteam).
- Ocena: jedyna znana platforma z formalną ścieżką dla agentów; monitorować `AGENT_ALLOWED`. Nie rejestrowaliśmy agenta (zakaz).

### 38. Layer3
- URL: https://app.layer3.xyz/
- Co to: questy on-chain (XP, CUBE, token L3), nagrody rzędu do ok. 100 USD na sezon [NZ].
- Dostęp: Cloudflare challenge (403) na /api/quests [API-TEST 25.11].
- Ocena: to nie hackathony; nie pasuje do celu, pominąć.

### 39. Gitcoin
- URL: https://gitcoin.co/campaigns, https://grants.gitcoin.co/
- Stan: Gitcoin zamknął własne bounty i hackathony (przekierował do Buidlbox); w 2026 skupia się na grantach (GG24, 1,8 mln USD w 6 domenach) i proponuje wygaszenie marki Gitcoin Grants na rzecz rocznej kampanii.
- Ocena: źródło grantów, nie konkursów.

### 40. Topcoder
- URL: https://www.topcoder.com/challenges
- Co to: płatne wyzwania programistyczne i AI (AI Leaderboard Season 2: 1.08-15.12.2026, bonusy do 2500 USD), wyzwania typu „Build the Best-of-All Submission Agent” (600 USD).
- Dostęp: **`https://api.topcoder.com/v6/challenges?status=Active&perPage=100`** [API-TEST 25.11]: JSON, nagłówki `X-Total`; v5 już nie działa (404). Dziś 1 aktywne wyzwanie.
- PL solo: tak (globalna platforma, wypłaty przez Topcoder).

---

## C. AI, ML, data science i areny agentów

### 41. Kaggle
- URL: https://www.kaggle.com/competitions
- Co listuje: konkursy ML i „Research Code Competitions”; Game Arena (benchmark modeli: szachy, poker, Werewolf).
- Aktualne/ważne [NZ co do szczegółów]: **Gemma 4 Developer Agent** (110 tys. USD, deadline wejścia 25.11.2026), **Generalist Gaming Agent** (start 23.11.2026, deadline 22.02.2027, offline agent grający w gry przeglądarkowe), ARC Prize 2026 (pkt 45), AIMO 3 (2,2 mln USD, zakończony 04.2026), Konwinski Prize (runda 1: 50 tys. USD za 7,5%).
- PL solo: tak; wykluczeni tylko mieszkańcy Krymu, DNR/LNR, Kuby, Iranu, Syrii, Korei Płn. i osoby objęte sankcjami USA.
- Zasady AI: kod z AI dozwolony; w code competitions zwykle **brak internetu podczas oceny**, więc zewnętrzne API (GPT/Claude) niedozwolone w notebooku; często wymóg open source dla nagrodzonych.
- Dostęp: `https://www.kaggle.com/api/v1/competitions/list` = 401 bez tokenu [API-TEST 25.11]; wewnętrzne API strony zwraca reCAPTCHA. Oficjalnie: `kaggle competitions list` z tokenem (darmowe konto) [AUTH]. ToS zakazuje scrapingu, API jest dozwoloną drogą.
- Ocena: kluczowe dla agentów z GPU.

### 42. ARC Prize
- URL: https://arcprize.org/competitions/2026 (konkursy na Kaggle: arc-prize-2026-arc-agi-3, arc-agi-2, paper track)
- Nagrody ARC-AGI-3: 850 tys. USD, Grand Prize 700 tys. USD za 100% (przechodzi na kolejny rok), kamienie milowe 30.06 i 30.09.2026 po 37,5 tys. USD. Final 2.11.2026, wyniki 4.12.2026 [NZ, źródło wtórne z opisu Kaggle].
- Zasady: brak internetu w ocenie, wymóg licencji permisywnej (MIT-0, CC0, Apache-2.0) dla nagród.
- PL solo: tak.
- Ocena: edycja 2026 zamknięta; przygotować się na ARC Prize 2027.

- URL: https://www.gpumode.com/ (leaderboardy), Discord, popcorn-cli na GitHub
- PL solo: tak (globalne, online). Uwaga: polski uczestnik „Olek” w top 3 cholesky.
- Zasady AI: brak zakazu; zgłoszenia oceniane automatycznie po wydajności i poprawności [INF].
- Ocena: **bardzo wysoka**; ocena obiektywna, idealna dla agentów kodujących z dostępem do GPU.

### 44. AIcrowd
- URL: https://www.aicrowd.com/challenges
- Dostęp: [HTML]; `challenges.json`/.atom = 500, `/api/v1/challenges` = 404 [API-TEST 25.11].
- PL solo: zwykle tak.

### 45. DrivenData
- URL: https://www.drivendata.org/competitions/
- Co to: konkursy „social impact” (np. DaT Parkinson’s 25 tys. EUR, NASA, World Bank); nagrody 20-650 tys. USD.
- PL solo: tak; wykluczenia: Rosja, kraje OFAC; tylko osoby fizyczne 18+.
- Dostęp: [HTML], brak feedu (/competitions/feed/ = 404).

### 46. Zindi
- URL: https://zindi.world/ (zindi.africa przekierowuje)
- Co to: konkursy ML w Afryce i globalne (np. GenAI for Good: 40 tys. USD).
- PL solo: **często nagrody tylko dla obywateli Afryki**; część konkursów otwarta globalnie.
- Dostęp: **`https://api.zindi.world/v1/competitions`** [API-TEST 25.11]: JSON, 10 pozycji, pola `id, title, reward, end_time, kind, is_access_restricted`.

### 47. Codabench
- URL: https://www.codabench.org/
- Co to: otwarta platforma konkursów naukowych (36 konkursów w ML Contests).
- Dostęp: **dla `curl` zwraca losowy, bezsensowny tekst** zamiast strony i API (`/api/competitions/public/`) [API-TEST 25.11]. To wygląda na pułapkę anty-scrapingową (zatruwanie danych dla botów) [INF]. Agent musi czytać Codabench przez ML Contests albo przeglądarkę.

### 48. EvalAI
- URL: https://eval.ai/
- Dostęp: **`https://eval.ai/api/challenges/challenge/present/approved/public`** [API-TEST 25.11]: JSON, 18 trwających wyzwań (G2F maize, CLIP2, CVPR).
- Ocena: akademickie, nagrody rzadko.

### 49. Solafune
- URL: https://solafune.com/
- Co to: konkursy na danych satelitarnych (geospatial), nagrody kilka tys. USD [NZ]. [HTML], /api/competitions = 404.
- Ocena: średnia (ESA/Copernicus pokrewne).

### 50. MachineHack
- URL: https://machinehack.com/
- Co to: hackathony ML (Indie). HTML wskazuje `/api/public/leaderboard` [HTML]. Niski priorytet.

### 51. Kaggle Game Arena i areny agentów
- URL: https://www.kaggle.com/game-arena
- Co to: benchmark modeli frontier (szachy, poker, Werewolf), bez nagród dla uczestników zewnętrznych [NZ]. Dla nas ważniejsze: Kaggle „Generalist Gaming Agent” (pkt 41) i Colosseum Agent Hackathon (pkt 34).

### 52. CrunchDAO
- URL: https://hub.crunchdao.com/
- Co to: konkursy predykcyjne (finanse, biologia) do 100 tys. USD (Structural Break Real-Time) [z ML Contests, API-TEST 25.11].
- Ocena: średnia.

---

## D. Polska i Europa

### 53. what_da_hack
- URL: https://whatdahack.pl/
- Co listuje: kalendarz hackathonów w Polsce, filtrowanie po mieście, trybie (online, stacjonarnie, hybrydowo), kategorii, terminie; archiwum zespołów i projektów (np. HackNation 2026, Heroes of the Brain 2026); uzupełniany co tydzień.
- Dostęp: [HTML] Next.js RSC; JSON-LD bez wydarzeń. robots: `Disallow: /api`; podstrona regulaminu ma `noindex`.
- Ocena: najlepszy kalendarz PL, ale bez feedu.

### 54. NaHackathon
- URL: https://nahackathon.pl/
- Co listuje: kalendarz PL plus szukanie ekipy, wspólny dojazd i nocleg.
- Dostęp: **JSON-LD `ItemList` z 12 wydarzeniami** na stronie głównej (np. CASSINI Hackathon Gdańsk, 12. edycja) [API-TEST 25.11]. **Uwaga: HTML zawiera znacznik-pułapkę `api/canary?t=nh-canary-…&src=wm`** (watermark do wykrywania kopiowania). Agent nie może kopiować treści 1:1 ani republikować; tylko odczyt metadanych.

### 55. Crossweb
- URL: https://crossweb.pl/wydarzenia/it/
- Co listuje: baza wydarzeń IT/startup w Polsce, w tym hackathony (HackNation 2026, Hackathon dla Małopolski).
- Dostęp: **RSS `https://crossweb.pl/rss/`** [API-TEST 25.11] (wszystkie wydarzenia, trzeba filtrować słowem „hackathon”). /wydarzenia/hackathony/ przekierowuje na ogólną listę.
- ToS/robots: blokuje kilka botów SEO, ogólnie dozwolone.

### 56. ChallengeRocket
- URL: https://challengerocket.com/
- Co to: polska platforma wyzwań i hackathonów (m.in. **CASSINI Hackathon Wrocław**, pula 6000 PLN lokalnie + 9000 EUR centralnie, 04.2026).
- Dostęp: [HTML], brak API. robots bez ograniczeń.

### 57. Eventornado
- URL: https://eventornado.com/
- Co to: fińska platforma do prowadzenia hackathonów (używana przez uczelnie i miasta). [HTML]. Niski wolumen.

### 58. Agorize
- URL: https://www.agorize.com/en
- Co to: francuska platforma wyzwań korporacyjnych i studenckich (open innovation). [HTML]. Często nagrody i staże, wyzwania dla startupów.

### 59. Junction
- URL: https://hackjunction.app/ (2026.hackjunction.com)
- Co to: największy hackathon w Europie: Junction 2026, 13-15.11.2026, Espoo, 2000 uczestników, 100 000 EUR nagród, granty podróżne 300/100 EUR. Platforma hackjunction.app hostuje też inne eventy.
- PL solo: tak (aplikacja; zespoły zwykle 1-5).
- Dostęp: [HTML] Next.js RSC.
- Ocena: edycja 2026 zakończona; obserwować 2027.

### 60. HackYeah
- URL: https://hackyeah.pl/
- Co to: największy stacjonarny hackathon w Europie, 12. edycja 3-4.10.2026, Tauron Arena Kraków, 24 h; nagrody: Open Tasks ok. 145 000 PLN, zadania partnerskie [wartości różnią się między źródłami, NZ].
- PL solo: tak, ale wydarzenie stacjonarne, wymaga obecności człowieka (właściciel).
- Dostęp: [HTML].

### 61. HackNation
- URL: https://sjsi.org/wydarzenie/hacknation-2026/
- Co to: ogólnopolski hackathon wdrożeniowy dla administracji publicznej, 2. edycja 21-22.11.2026, Bydgoszcz [NZ].

### 62. CASSINI Hackathons (UE, EUSPA)
- URL: https://www.cassini.eu/hackathons
- Co to: hackathony na danych Copernicus, Galileo, EGNOS, IRIS²; 12. edycja „EU Space for Peace and Resilience” 27-29.11.2026 w 10 krajach (w tym Polska, Gdańsk), demo day 2.12.2026. Pula lokalna PL ok. 6000 PLN + 9000 EUR centralnie (11. edycja).
- Platformy: TAIKAI, ChallengeRocket.
- PL solo: tak, wymaga zespołu na miejscu w lokalizacji [NZ].
- Zasady AI: brak informacji [NZ].

### 63. EU Datathon
- URL: https://op.europa.eu/en/web/eudatathon
- Co to: konkurs otwartych danych Urzędu Publikacji UE (od 2017), w 2022 pula 200 000 EUR.
- Stan: **nie znaleźliśmy edycji 2026** [NZ]; obserwować op.europa.eu i data.europa.eu/en/news-events/events.

### 64. ESA Kelvins i wyzwania ESA
- URL: https://kelvins.esa.int/
- Co to: konkursy ESA ACT (pose estimation, space debris, GTOC). Lista 15 historycznych konkursów w HTML [API-TEST 25.11]; brak aktywnych w nawigacji.
- Ocena: rzadkie, ale idealnie mierzalne.

### 65. NASA International Space Apps Challenge
- URL: https://www.spaceappschallenge.org/
- Co to: globalny 48-godzinny hackathon NASA, 2026: 14-15.11.2026, motyw „The Next Frontier”, lokalne eventy w Polsce: Stalowa Wola, Rzeszów (hybrydowo), Poznań, Gliwice.
- Dostęp: serwer odrzuca `curl` (brak odpowiedzi) [API-TEST 25.11].
- PL solo: tak; nagrody głównie uznaniowe [NZ].

### 66. Open Hackathons (NVIDIA/OpenACC)
- URL: https://www.openhackathons.org/s/upcoming-events
- Co to: hackathony GPU dla naukowców z mentorami, dostęp do superkomputerów; bez nagród pieniężnych [INF]. [HTML] (Salesforce).
- Ocena: dobre do zdobycia mocy obliczeniowej, nie pieniędzy.

---

## E. Bug bounty i audyty jako konkursy

### 67. HackerOne
- URL: https://hackerone.com/opportunities/all
- Zasady AI: „Hackbots” dozwolone, ale **„must not operate in a fully autonomous manner”**, człowiek musi zweryfikować każdy raport; operator dostaje bounty i ponosi odpowiedzialność.
- Nagrody: od setek do dziesiątek tys. USD; 2026: 81 mln USD wypłat [NZ].
- Dostęp: strona to SPA; API wymaga tokenu [AUTH]. Lista programów: bounty-targets-data (pkt 13).

### 68. Bugcrowd
- URL: https://bugcrowd.com/
- Zasady AI: Code of Conduct (25.11.2025) wymaga ręcznej weryfikacji raportów z GenAI; od 03.2026 kary za „AI slop” (30 dni zawieszenia, ban za farming), od 05.2026 zgłoszenia tylko przez przeglądarkę z „human-verified token”.
- Dostęp: bounty-targets-data.

### 69. Intigriti (UE, Belgia)
- URL: https://www.intigriti.com/
- Dostęp: **`https://app.intigriti.com/api/core/public/programs`** [API-TEST 25.11]: JSON 231 KB z publicznymi programami bez logowania.
- PL solo: tak (europejska platforma, wypłaty w EUR).
- Zasady AI: nie sprawdzone [NZ].

### 70. YesWeHack (UE, Francja)
- URL: https://yeswehack.com/
- Dostęp: **`https://api.yeswehack.com/programs?page=1`** [API-TEST 25.11]: 52 programy, pola `title, bounty, bounty_reward_max, country, vdp`.
- PL solo: tak.

### 71. Immunefi
- URL: https://immunefi.com/bug-bounty/, audit competitions: https://immunefi.com/audit-competition/
- Dostęp: **`https://immunefi.com/public-api/bounties.json`** [API-TEST 25.11]: 6,3 MB, 217 programów, `maxBounty` do 10 mln USD, pola `kyc, eligibilityCriteria, endDate, inviteOnly`.
- Zasady AI: **zakaz** raportów generowanych przez AI/skanery bez wymaganych informacji (ban, od 12.2022). KYC wymagane w audit competitions 2026.
- Po zamknięciu Code4rena przejmuje jego klientów bug bounty.

### 72. Code4rena
- URL: https://code4rena.com/audits
- Stan: **ogłosił wygaszenie w 05.2026, zamknięcie 12.07.2026**; ostatni konkurs zakończony 27.05.2026 (K2, 135 tys. USD).
- Dostęp: `https://code4rena.com/api/v1/audits` [API-TEST 25.11] działa, 25 historycznych audytów.
- Ocena: martwe, pominąć.

### 73. Sherlock
- URL: https://audits.sherlock.xyz/
- Dostęp: **`https://mainnet-contest.sherlock.xyz/contests`** [API-TEST 25.11]: paginowany JSON (`prize_pool, status, starts_at, ends_at, type_label`); dziś brak aktywnych.
- Zasady AI: publiczne konkursy: brak reguły; **Audit Engine (od 18.08.2026) dopuszcza typ konta „AI auditor”** („automated AI system… without human involvement”).
- Trend: 102 konkursy w 2024, 47 w 2025, 9 w 2026; mediana puli 60 tys. USD.
- Ocena: jedyna platforma audytowa formalnie akceptująca autonomicznych audytorów AI.

### 74. Cantina
- URL: https://cantina.xyz/opportunities/competitions
- Dostęp: **`https://cantina.xyz/api/v0/competitions`** [API-TEST 25.11]: 146 konkursów, pola `name, status, totalRewardPot, kycRequired, entryFee, timeframe`; 1 live: Morpho Midnight Adapter (400 tys. USD).
- Zasady AI: spam i „unverified AI-generated submissions” = utrata depozytu; AI wolno używać tylko z narzędziami nie trenującymi na poufnych danych.

---

## F. Hardware, gry, CTF, algorytmika

### 75. Hackster
- URL: https://www.hackster.io/contests
- Co to: konkursy hardware/edge AI (AMD, Nordic, Arduino), nagrody sprzętowe i gotówkowe.
- Dostęp: **Atom `https://www.hackster.io/contests.rss`** [API-TEST 25.11].
- PL solo: zwykle tak, wysyłka sprzętu.

### 76. itch.io game jams
- URL: https://itch.io/jams/upcoming
- Co to: game jamy (setki miesięcznie), zwykle bez gotówki; część jamów zakazuje AI-assetów.
- Dostęp: [HTML] (brak .json/.xml dla listy jamów) [API-TEST 25.11].

### 77. CTFtime
- URL: https://ctftime.org/event/list/
- Dostęp: **`https://ctftime.org/api/v1/events/?limit=100&start=<unix>`** [API-TEST 25.11]: 26 nadchodzących, 23 online.
- Ocena: CTF to naturalne pole dla agentów cybersec; nagrody zwykle małe, ale ranking się liczy.

### 78. Codeforces (przykład API algorytmicznego)
- Dostęp: **`https://codeforces.com/api/contest.list?gym=false`** [API-TEST 25.11]. Zasady: Codeforces ogranicza użycie AI w rundach rankingowych [NZ]. Brak nagród pieniężnych.

---

## G. Serwisy wydarzeń i powiadomienia

### 79. Luma (lu.ma, luma.com)
- URL: https://luma.com/discover, https://luma.com/ai, kalendarze: Cerebral Valley, AGI House, AI Tinkerers
- Co listuje: większość hackathonów AI w SF, Londynie, Warszawie (np. „n8n Hackathon Warszawa” 7.12.2026, „Samba TV Hackathon Warsaw” 3.12.2026), side-eventy ETHGlobal, GPU MODE.
- Dostęp (nieudokumentowane, bez logowania) [API-TEST 25.11]:
  - `https://api.lu.ma/discover/get-paginated-events?pagination_limit=20&query=hackathon&latitude=52.23&longitude=21.01` (geo-wyszukiwanie; Warszawa i SF działają)
  - `https://api.lu.ma/discover/category/get-page?slug=ai` (3326 wydarzeń AI, 116 273 subskrybentów)
  - `https://api.lu.ma/url?url=<slug>` rozwiązuje slug na kalendarz: agihouse = `cal-miA10DVm0JQ6nT0`, aitinkerers = `cal-UCNcNUQEeTHdcnt`, cerebral-valley = `cal-qTA84G1Wwdl14m4`
  - **ICS: `https://api.lu.ma/ics/get?entity=calendar&id=<cal-id>`** (text/calendar, działa); `calendar/get-items` zwrócił pustą listę.
- Oficjalne API (public-api.luma.com) wymaga Luma Plus (59 USD/mies.) i dotyczy tylko własnych kalendarzy [AUTH].
- ToS: [NZ] nie potwierdziliśmy klauzuli dla luma.com (wyszukiwarka myliła z Luma AI); ICS to oficjalna funkcja subskrypcji, więc jest najbezpieczniejszą drogą.

### 80. Eventbrite i Meetup
- URL: https://www.eventbrite.com/, https://www.meetup.com/
- Dostęp: oba API wymagają tokenu/OAuth (Meetup GraphQL, Eventbrite API bez publicznego wyszukiwania) [AUTH, NZ]. Strony HTML działają [API-TEST 25.11].
- Ocena: niski stosunek sygnału do szumu; pomijać lub czytać przez HackathonRadar.

### 81. Reddit r/hackathon i newslettery
- r/hackathon: `/.rss` zwrócił 429, `/new.json` 403 [API-TEST 25.11]; Reddit wymaga OAuth dla botów.
- Newslettery (Devpost, DoraHacks, MLH, lablab/Starfield, Crossweb, Colosseum Codex): do subskrypcji na skrzynkę właściciel i parsowania maili; to w pełni zgodne z ToS [INF].

---

## Jak agent może je czytać automatycznie

Wszystkie endpointy poniżej wywołaliśmy 25.11.2026 bez logowania (chyba że oznaczono AUTH). Zalecane: User-Agent identyfikujący bota, 1 odczyt na źródło dziennie, cache, backoff przy 429.

### Tier 1: publiczne JSON/RSS/ICS, działające bez konta

| Źródło | Endpoint | Format | Uwagi |
|---|---|---|---|
| HackList | `GET https://hacklist.io/api/opportunities` | JSON | 206 pozycji, oficjalny feed |
| Devpost | `GET https://devpost.com/api/hackathons?status[]=open&challenge_type[]=online&themes[]=Machine%20Learning%2FAI&page=N` | JSON | nieudokumentowane, ToS zakazuje scrapingu: oszczędnie |
| DoraHacks | `GET https://dorahacks.io/api/v1/hub/hackathons?page=1&page_size=50&status=ongoing` | JSON | nieudokumentowane |
| Superteam Earn | `GET https://superteam.fun/api/listings?type=bounty` (+ `GET /api/agents`) | JSON | filtr `agentAccess=="AGENT_ALLOWED"` |
| Agent Bounty Index | `GET https://sheikhminds.github.io/agent-bounty-index/data.json` | JSON | gotowy podział open/blocked |
| ML Contests | `GET https://mlcontests.com/` → atrybut `data-competitions` | JSON w HTML | 413 konkursów ML |
| Zindi | `GET https://api.zindi.world/v1/competitions` | JSON | |
| EvalAI | `GET https://eval.ai/api/challenges/challenge/present/approved/public` | JSON | |
| Topcoder | `GET https://api.topcoder.com/v6/challenges?status=Active&perPage=100` | JSON | v5 nie działa |
| GPU MODE | `GET https://www.gpumode.com/api/leaderboard-summaries`, `/api/events` | JSON | |
| HackerEarth | `GET https://www.hackerearth.com/chrome-extension/events/` | JSON | |
| Devfolio | `POST https://api.devfolio.co/api/search/hackathons` body `{"type":"application_open","from":0,"size":50}` | JSON | |
| Hack Club | `GET https://hackathons.hackclub.com/api/events/upcoming` | JSON | limit przy seriach |
| GDG | `GET https://gdg.community.dev/api/search/event/?result_types=upcoming_event&page_size=50` | JSON | |
| CTFtime | `GET https://ctftime.org/api/v1/events/?limit=100&start=<unix>` | JSON | |
| Codeforces | `GET https://codeforces.com/api/contest.list?gym=false` | JSON | |
| Luma | `GET https://api.lu.ma/discover/get-paginated-events?query=hackathon&latitude=..&longitude=..&pagination_limit=50` | JSON | nieudokumentowane |
| Luma ICS | `GET https://api.lu.ma/ics/get?entity=calendar&id=cal-…` | ICS | oficjalna subskrypcja |
| Crossweb | `GET https://crossweb.pl/rss/` | RSS | filtrować „hackathon” |
| Hackster | `GET https://www.hackster.io/contests.rss` | Atom | |
| AngelHack | `GET https://angelhack.com/feed/` | RSS | |
| Immunefi | `GET https://immunefi.com/public-api/bounties.json` | JSON | 6,3 MB |
| Sherlock | `GET https://mainnet-contest.sherlock.xyz/contests?page=N` | JSON | |
| Cantina | `GET https://cantina.xyz/api/v0/competitions` | JSON | 0,8 MB |
| Intigriti | `GET https://app.intigriti.com/api/core/public/programs` | JSON | |
| YesWeHack | `GET https://api.yeswehack.com/programs?page=N` | JSON | |
| bounty-targets-data | `GET https://raw.githubusercontent.com/arkadiyt/bounty-targets-data/main/data/{hackerone,bugcrowd,intigriti,yeswehack}_data.json` | JSON | |
| Code4rena | `GET https://code4rena.com/api/v1/audits` | JSON | platforma zamknięta 07.2026 |

### Tier 2: JSON-LD lub dane w HTML (parsować stronę)

- HackathonRadar `/discover/<region>` (JSON-LD `Event`), Hackathon Hub `/hackathons/<rok|kategoria>` (JSON-LD `Event`), NaHackathon strona główna (JSON-LD `ItemList`, uwaga na watermark), TAIKAI `/en/hackathons` (`__NEXT_DATA__`), ETHGlobal `/events` (slugi w HTML), lablab.build i starfieldlabs.ai (Next.js RSC), whatdahack.pl, HackQuest, AKINDO, Tatum, Junction (Next.js RSC), DrivenData, AIcrowd, Kelvins, MLH, Hackathon.com, BeMyApp, ChallengeRocket.

### Tier 3: wymaga konta lub klucza

- Kaggle (`kaggle competitions list`, token), CLIST (`ApiKey user:key`), HackathonRadar MCP (OAuth, plan darmowy) lub REST (Enterprise), Luma oficjalne API (Luma Plus), HackerOne API, Meetup, Eventbrite, Reddit.
- Decyzja dla właściciel: założenie kont Kaggle, CLIST i HackathonRadar (free) dałoby pokrycie ok. 90% rynku [INF]; to wymaga jego zgody (my niczego nie zakładaliśmy).

### Pułapki wykryte w testach

- **Codabench** serwuje botom losowy tekst (dane-trucizna); nie wolno ufać odpowiedzi `curl`.
- **NaHackathon** wstrzykuje tokeny-canary do HTML (wykrywanie kopiowania).
- **Unstop** i **whatdahack** blokują `/api` w robots.txt; **HackathonRadar** blokuje `/api/` i kieruje do MCP.
- **Devpost** i **Kaggle** zakazują scrapingu w ToS mimo otwartego robots.
- **Kaggle**: wewnętrzne API zwraca reCAPTCHA; **Layer3**: Cloudflare 403; **NASA Space Apps**: brak odpowiedzi na `curl`.
- **lablab.ai** przekierowuje na Starfield Labs; stare linki mogą się zmieniać.

### Szkic pipeline’u dla agenta Hacker

1. Raz dziennie: Tier 1 (ok. 28 żądań), normalizacja do wspólnego schematu `{source, title, url, start, end, deadline, prize_usd, format, region, tags, agent_allowed, kyc, ai_rules_url}`.
2. Deduplikacja po URL i (tytuł, data), wzbogacenie o JSON-LD z HackathonRadar/Hackathon Hub.
3. Filtr kwalifikacji: online lub Polska/UE, otwarte dla PL, solo dozwolone, deadline > 72 h, nagroda ≥ 1000 USD.
4. Pobranie strony regulaminu (rules) tylko dla kandydatów i klasyfikacja zasad AI (dozwolone z ujawnieniem / ograniczone / zakaz / agent dozwolony).
5. Raport dzienny dla właściciel; decyzję o rejestracji podejmuje człowiek.

---

## Zasady AI: podsumowanie

| Platforma | Kod z AI | Autonomiczny agent jako uczestnik |
|---|---|---|
| MLH | wymagane dopuszczenie, z ujawnieniem | brak reguły [NZ] |
| Devpost | zależne od hackathonu, zwykle z ujawnieniem | rzadko wprost |
| ETHGlobal | dozwolone z dokumentacją | projekt „cały z AI” traci szanse na nagrody |
| Encode Club | dozwolone, w Vibe Coding wymagane | brak reguły |
| Colosseum | dozwolone | był osobny Agent Hackathon (02.2026) |
| Superteam Earn | dozwolone | per listing `AGENT_ALLOWED` (dziś 0) |
| Kaggle | dozwolone, bez internetu w ocenie | brak zakazu, konkursy na agentów |
| HackerOne | dozwolone | hackboty tylko z człowiekiem w pętli |
| Bugcrowd | z ręczną weryfikacją | blokada (human-verified token) |
| Immunefi | zakaz raportów AI | zakaz |
| Cantina | niezweryfikowane AI = spam | brak |
| Sherlock | brak reguły w konkursach | **Audit Engine: konto „AI auditor”** |

---

## Konta na X, które ogłaszają hackathony (przegląd Grokiem 2026-11-25)


Minimum operacyjne dla agenta, który ma znajdować konkursy:

| Konto | Co publikuje | Przykład |
|---|---|---|
| [@HackListHQ](https://x.com/HackListHQ) | Codzienne karty: kwota, termin, zasady. AI, Web3, Kaggle, granty | Firebase 30 tys., 24 lis: [post](https://x.com/HackListHQ/status/2125258138492530931) |
| [@DoraHacks](https://x.com/DoraHacks) | Platforma hackathonów, starty i newsletter. 38,5 tys. obserwujących | Gnome Tavern, 23 lis: [post](https://x.com/DoraHacks/status/2124714857069236385) |
| [@ETHGlobal](https://x.com/ETHGlobal) | Hackathony Ethereum, często async i tory sponsorów | Agentic Markets, 20 lis, 3-10 gru, 50 tys.+ USD: [post](https://x.com/ETHGlobal/status/2123902700471599615) |
| [@devpost](https://x.com/devpost) | „Home for hackathons”, linki devpost.com | Pico Space Program, 50 tys. USD, 18 lis: [post](https://x.com/devpost/status/2123157354849992726) |
| [@lablabai](https://x.com/lablabai) | lablab.build, hackathony agentów AI | Agent Stack 48, 11-13 gru, online: [post](https://x.com/lablabai/status/2124852127948226791) |
| [@kaggle](https://x.com/kaggle) | Konkursy ML i agentów, leaderboard, nagrody | Agent Harness PLE, 400 tys. USD, wpis do 5 sty 2027: [post](https://x.com/kaggle/status/2122725546459070920) |
| [@encodeclub](https://x.com/encodeclub) | Programy AI i Web3, hackathony z nagrodami | Concordium Trusted Agents, 3 mln CCD, 13 lis: [post](https://x.com/encodeclub/status/2121181309641093276) |
| [@colosseum](https://x.com/colosseum) | Hackathon, akcelerator i fundusz krypto | Crypto World’s Fair, wyniki w połowie grudnia: [post](https://x.com/colosseum/status/2125234847916740762) |
| [@HackQuest_](https://x.com/HackQuest_) | Edukacja Web3 i AI plus hackathony | Bittensor: warsztaty, lokalne meetupy, hackathon, 23 lis: [post](https://x.com/HackQuest_/status/2124932824520380806) |
| [@SuperteamEarn](https://x.com/SuperteamEarn) | Bounty i zlecenia na Solanie. 39 tys. obserwujących | Raenest 13 tys. USDC do 13 gru, cytowane 20 lis przez @Abdulkarim2 |
| [@onlyonealexia](https://x.com/onlyonealexia) | Miesięczne zestawienia z nagrodami i linkami | Październik, 60+ hackathonów, 4 paź: [post](https://x.com/onlyonealexia/status/2106567216816603504). Listopad, 8 lis: [post](https://x.com/onlyonealexia/status/2119322302437372016) |
| [@mittalparth_](https://x.com/mittalparth_) | 16 wygranych hackathonów, konkretne listy | Lista listopada, 5 lis, 919 zakładek: [post](https://x.com/mittalparth_/status/2118355592167494074) |
| [@Build3DAO](https://x.com/Build3DAO) | Co tydzień hackathony posortowane po deadline | 25 paź, 1,37 mln USD w 7 konkursach: [post](https://x.com/Build3DAO/status/2114326493811945679) |
| [@BangDropID](https://x.com/BangDropID) | 18 wygranych, „deadline radar” co kilka dni | Radar na 2 tygodnie, 23 lis: [post](https://x.com/BangDropID/status/2124661456926855565) |
| [@_HerDAO](https://x.com/_HerDAO) | Tygodniówka Web3 + AI: granty, hackathony, bounty | 24 lis, pięć okazji do 9-24 gru: [post](https://x.com/_HerDAO/status/2125265395275923844) |
| [@Abdulkarim2](https://x.com/Abdulkarim2) | Codzienny „TOP 10”, punkty 7-10 to konkursy z datami | 23 lis, Gensyn, Even Realities, Raenest: [post](https://x.com/Abdulkarim2/status/2124790507612131646) |
| [@Promise1web3](https://x.com/Promise1web3) | Krótkie listy „4 hackathony, w które jeszcze wejdziesz” | 18 lis, Solana, CMC, MetaEarth, Aevum: [post](https://x.com/Promise1web3/status/2122924910586605665) |
| [@suraj_sharma14](https://x.com/suraj_sharma14) | Listy globalnych hackathonów z linkami | 12 hackathonów na lis-gru, 19 lis: [post](https://x.com/suraj_sharma14/status/2123461304585531575) |
| [@Mapemaofweb3](https://x.com/Mapemaofweb3) | Zestawienia pul nagród AI i Web3 | 19 paź, 2,6 mln+ w 9 konkursach: [post](https://x.com/Mapemaofweb3/status/2112083195780829635) |
| [@CryptooGG_](https://x.com/CryptooGG_) | Katalog agregatorów, nie pojedyncze hackathony | 19 wrz, 7 stron zbierających hackathony: [post](https://x.com/CryptooGG_/status/2101340181785919830) |
| [@MrKqyre](https://x.com/MrKqyre) | Długie listy żywych konkursów i bounty | 30 konkursów, 23 lis: [post](https://x.com/MrKqyre/status/2124910103866544458) |
| [@geek__room_](https://x.com/geek__room_) | Sam organizuje globalne hackathony agentów (społeczność 150 tys.) | Infer-a-thon, 17 lis: [post](https://x.com/geek__room_/status/2122690533030302130) |
| [@gensynai](https://x.com/gensynai) | Konkursy, w których startuje agent, nie tylko człowiek | Evidence Mining, 24 lis: [post](https://x.com/gensynai/status/2125269967436435498) |
| [@NousResearch](https://x.com/NousResearch) | Hackathony wtyczek do agenta Hermes | Ogłoszenie zebrane przez HackList, 6 lis: [post](https://x.com/HackListHQ/status/2118520930183852526) |
| [@0x_beni_](https://x.com/0x_beni_) | Buduje HackList, pisze o wygranych | Drugi wygrany hackathon przez hacklist.io, 25 sie: [post](https://x.com/0x_beni_/status/2092362731693248582) |

Do tego organizatorzy serii, których HackList i listy oznaczają przy okazji: @NEARProtocol, @kirodotdev, @base, @arbitrum, @GoogleQuantumAI, @googlegemma, @MetaVRDevs, @QNX_News, @Atlassian, @awscloud. Ich posty są ogłoszeniem jednego konkursu, nie tygodniówką.

Kwoty z zestawień (@Abdulkarim2, @BangDropID, @MrKqyre, @suraj_sharma14) czasem rozjeżdżają się z kartą HackList o dzień albo o wysokość puli. Do decyzji agenta bierz datę i kwotę z konta organizatora albo z HackList, a zestawienie traktuj jako radar, że konkurs w ogóle istnieje.
