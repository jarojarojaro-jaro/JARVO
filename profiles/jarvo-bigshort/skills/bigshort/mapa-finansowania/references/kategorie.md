---
source: "opracowanie floty Jarva na podstawie researchu z 2026-11-25 (pliki zrodla-*.md, narzedzia-i-bazy.md)"
reviewed: "2026-11-25"
---

# Kategorie fan-outu i pytania kwalifikujące

Każda kategoria to jeden wątek dla subagenta. W instrukcji wątku: profil projektu, kryteria wykluczające, format JSONL
z `baza-okazji`, wymóg strony programu jako źródła.

| Kategoria | Typ w bazie | Gdzie szukać najpierw | Pytania kwalifikujące |
|---|---|---|---|
| Granty PL (PARP, NCBR, FENG, regiony) | grant | strony agencji, harmonogramy naborów, biznes.gov.pl | forma prawna, MŚP, wkład własny, region, refundacja czy zaliczka |
| Granty i konkursy UE (EIC, Horizon, EIT, Digital Europe) | grant, konkurs | Funding & Tenders Portal, strony EIC i EIT | konsorcjum czy pojedynczo, TRL, kraj, cut-off |
| Fundusze VC PL i CEE (w tym portfele PFR Ventures) | vc | strony funduszy, lista funduszy PFR, ogłoszenia rund | etap, czek, teza, formularz |
| Fundusze VC globalne z otwartym formularzem | vc | OpenVC, strony funduszy, listy „no warm intro” | teza, etap, czy biorą spółki spoza US |
| Aniołowie i syndykaty | aniol, syndykat | sieci aniołów PL, platformy syndykatów | kwota, sektor, sposób zgłoszenia |
| Akceleratory i inkubatory | akcelerator | strony programów (YC, Techstars, Antler, EF, a16z speedrun, lokalne) | equity, kwota, relokacja, solo, termin kohorty |
| Fellowshipy i granty bez udziałów (osoby) | fellowship, grant | strony fundacji i programów | dla osoby czy firmy, kraj, etap, raportowanie |
| Granty open source i infrastruktura | grant | NLnet/NGI, Sovereign Tech, fundacje, GitHub | licencja, cel publiczny, kamienie milowe |
| Kredyty chmurowe, GPU i API modeli | kredyty | programy startupowe dostawców (AWS, Google, Microsoft, NVIDIA, dostawcy GPU i modeli) | wymagany partner VC, czas ważności, limit |
| Konkursy, hackathony, nagrody | konkurs | strony organizatorów, agregatory | nagroda w gotówce, prawa do IP, termin |
| Ulgi i instrumenty podatkowe | ulga | podatki.gov.pl, interpretacje KIS | warunki, dokumentacja B+R, IP Box |
| Dług i finansowanie przychodem (BGK, RBF, venture debt) | dlug | BGK, fundusze pożyczkowe, platformy RBF | przychód, zabezpieczenie, koszt |
| Crowdfunding udziałowy i nagrodowy | crowdfunding | platformy PL i UE | regulacje, koszt kampanii |
| PE, banki inwestycyjne, hedge fundy | pe, bank | tylko przy spółce z przychodem i EBITDA; zwykle nie dla pre-seed | próg przychodu, typ transakcji |

Zasada dla ostatniego wiersza: PE, banki inwestycyjne i hedge fundy nie finansują projektów przed przychodem; wpis tylko
z dowodem, że dany podmiot robi wczesne inwestycje (np. ramię venture banku), inaczej zdanie w raporcie „nie na ten etap”.
