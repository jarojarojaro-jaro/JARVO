---
source: "hackatony.py (profil jarvo-hacker)"
reviewed: "2026-11-25"
---

# Format wpisu hackathonu (`*.jsonl`, jeden na linię)

```
{"nazwa": "Gemini Agents Challenge 2026", "platforma": "Devpost", "url": "https://gemini.devpost.com",
 "zrodlo": "https://gemini.devpost.com/rules", "start": "2026-11-10", "rejestracja_do": "2026-11-27T17:00",
 "zgloszenie_do": "2026-11-27T17:00", "tryb": "online", "miejsce": null, "pula": 100000, "waluta": "USD",
 "tracki": ["agents", "multimodal"], "sponsorzy": ["Google"], "solo": "tak", "ai_kod": "tak",
 "wymagania": ["repo publiczne", "film do 3 min", "opis"], "kryteria": ["innowacja 25%", "użycie API 25%", "demo 25%", "wpływ 25%"],
 "kwalifikowalnosc": "18+, bez krajów objętych sankcjami", "sprawdzone": "2026-11-25", "notatki": "tracki się łączą"}
```

- Daty: `RRRR-MM-DD` albo `RRRR-MM-DDTHH:MM` w **UTC** (przelicz strefę regulaminu; „Z” i „+00:00” skrypt przyjmie).
- `solo`, `ai_kod`: `tak`, `nie`, `niejasne` (regulamin milczy = `niejasne`).
- `tryb`: `online`, `onsite`, `hybryda`; finał na miejscu opisz w `notatki`.
- `id` opcjonalne (slug z nazwy); nowa edycja = nowa nazwa z rokiem albo sezonem.
- Status zmienia tylko `hackatony.py status`; `dodaj` uzupełnia dane.
