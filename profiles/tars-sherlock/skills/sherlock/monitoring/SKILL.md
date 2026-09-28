---
name: monitoring
description: "Monitoring tematu/konkurencji: rutyna, tylko nowości."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [research, monitoring, cron, competitors]
    related_skills: [competitor-news-monitor, rss-feeds, blogwatcher]
  tars:
    agent: tars-sherlock
    autonomy: A1
    reviewed: "2026-09-26"
---

# Monitoring

Dla zleceń „pilnuj X”, „daj znać, gdy konkurencja…”. Monitoring to rutyna cron (dostarczanie przez Jarva).

## Konfiguracja (jednorazowo, w karcie zlecenia)
1. Zdefiniuj **obiekt** (firma, produkt, temat, fraza), **źródła** (RSS, strony, wyszukiwania z filtrem czasu)
   i **próg istotności** (co jest warte wiadomości: np. zmiana ceny, nowy produkt, artykuł w mediach tier A/B).
2. Zapisz definicję w `@@WORKSPACES_DIR@@/tars-sherlock/monitoring/<slug>.md`.
3. Zaproponuj harmonogram (domyślnie codziennie rano albo co tydzień). Jarvo tworzy rutynę po akceptacji użytkownika.

## Każde uruchomienie
1. Pobierz nowe elementy od ostatniego uruchomienia (`rss-feeds`, `blogwatcher`, `competitor-news-monitor`, wyszukiwanie `--time day|week`).
2. Odrzuć duplikaty i to, co poniżej progu.
3. Zweryfikuj istotne rzeczy minimum jednym dodatkowym źródłem.
4. Nic istotnego → `[SILENT]`. Coś istotnego → 3–6 linii: co się zmieniło, źródło z datą, znaczenie dla użytkownika.
