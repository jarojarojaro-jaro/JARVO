---
source: "Jarvo Skarbiec API v1 (services/skarbiec)"
reviewed: "2026-09-29"
---
# Format `szkic.json`

```json
{
  "platforma": "meta",
  "konto": "act_123456789",
  "kampania": {"nazwa": "JARVO_meta_ruch_260930", "cel": "OUTCOME_TRAFFIC", "kategorie_specjalne": []},
  "zestawy": [
    {"nazwa": "szeroko_PL_auto", "budzet_calkowity": 250, "od": "2026-09-30", "do": "2026-10-06",
     "optymalizacja": "LANDING_PAGE_VIEWS", "kraje": ["PL"], "wiek": [18, 55],
     "reklamy": [
       {"nazwa": "T01_bang_9x16_v1", "plik": "/opt/data/jarvo/missions/M-260930-launch/wideo/out/4-bang.mp4",
        "tekst": "Jarvo: od pomysłu do działającej rzeczy.", "naglowek": "Twoja cyfrowa prawa ręka",
        "cta": "LEARN_MORE", "link": "https://jarvo.pl/?utm_source=meta&utm_medium=paid&utm_campaign={{campaign.name}}&utm_content={{ad.name}}"}
     ]}
  ]
}
```

Google Search (`"platforma": "google"`): `kampania` z `typ: SEARCH`, `grupy` z `slowa` (`[{"tekst": "...", "dopasowanie": "PHRASE"}]`),
`wykluczenia`, `reklamy` RSA (`naglowki` ≤ 15 × 30 znaków, `opisy` ≤ 4 × 90 znaków, `link`).

Kwoty w złotych (Skarbiec przelicza na jednostki platformy). Statusy ignorowane: Skarbiec zawsze tworzy PAUSED.
