---
source: "research Hackera 2026-11-25: 709 adresów, każdy kanał sprawdzony zapytaniem z UA przeglądarki, bez logowania"
reviewed: "2026-11-25"
---

# Dzienne źródła ogłoszeń

Jedno żądanie na źródło dziennie, UA przeglądarki; przy 429 albo 503 źródło jest „niesprawdzone”, bez ponawiania.

## Czyta `zrodla.py` (codziennie, z porównaniem z bazą)

| Źródło | Adres | Format | Uwaga |
|---|---|---|---|
| DevGrants Daily | `devgrantsdaily.com/all/` | HTML kart | typ w `data-type` (hackathon, bounty); `?type=` jest ignorowany |
| HackList | `hacklist.io/api/opportunities` | JSON | sprawdzaj `generated_at`: bywa stara kopia |
| Hackathon Hub (UE) | `hackathonhub.eu/llms-full.txt` | Markdown | `## Tytuł` i pola `Date`, `Format`, `Prize`, `URL` |
| BuildJams | `jams.shippedby.app/feed.xml` | RSS | w opisie `Prizes: … Closes: …` |
| advance.to | `advance.to/feed.xml` | RSS | tylko kategoria „Competitions & prizes” |
| make.fun | `make.fun/api/competitions?status=open` | JSON | robots wprost pozwala; OpenAPI pod `/api/openapi.json` |

## Czytasz sam, gdy potrzeba

| Źródło | Adres | Uwaga |
|---|---|---|
| ML Contests | `mlcontests.com/` → atrybut `data-competitions` | `/rss.xml` to blog, nie konkursy |
| Devpost | `devpost.com/api/hackathons?status[]=open&order_by=prize-amount` | regulamin zakazuje scrapingu: najwyżej raz dziennie |
| MLH | `mlh.com/seasons/2027/events` → `props.upcomingEvents` | JSON w HTML |
| DoraHacks | `dorahacks.io/api/v1/hub/hackathons?page=1&page_size=50` | |
| CTFtime | `ctftime.org/api/v1/events/?limit=100&start=<unix>` | |
| GPU MODE | `gpumode.com/api/events` | |
| Luma | `api.lu.ma/discover/get-paginated-events?query=hackathon&latitude=52.23&longitude=21.01` | |
| Bugcrowd | `bugcrowd.com/engagements.json` | |
| aihackathon.app | HTML `/` | tabela po terminie |
| Apart Research | `apartresearch.com/hackathons` | sprinty AI safety |
| Unstop | `/api/public/opportunity/search-result` | robots pozwala tylko na `/api/public/*` |

## X i Telegram

- X przez `api.fxtwitter.com/2/profile/<konto>/statuses` (JSON, 20 postów, `cursor.bottom`; przejściowe 404: ponów po
  5–10 s): @HackListHQ, @Build3DAO, @kaggle, @devpost, @MetaforDevs, @geek__room_, @_HerDAO, @DoraHacks, @SuperteamEarn.
- Telegram przez `t.me/s/<kanał>` (HTML, 20 postów, `?before=<id>`): `devgrants_daily`, `russianhackers_channel`, `wemakedevs`.

## Nie czytać

- Blogi Modal, Baseten, Groq, Cerebras, Together, Cohere, Mistral nie ogłaszają konkursów; NVIDIA i Cloudflare mają
  stare wpisy; huggingface.co/competitions kończy się na 2025; Anthropic nie ma RSS (tylko `sitemap.xml`).
- Martwe: Hackalist, Code4rena, Crossweb (hackathony), EU Datathon, AngelHack `/feed/`, aicrowd `.json`, Solafune API,
  Reddit r/hackathons.
- Codabench serwuje botom losowy tekst: czytaj go przez ML Contests.

## Pułapki

- Termin w agregatorze to często termin wejścia albo data z ogłoszenia; termin oddania bierz od organizatora.
- TAIKAI: dane wydarzeń są w RSC, nie w `__NEXT_DATA__`; Hackster: `/contests.atom`.
