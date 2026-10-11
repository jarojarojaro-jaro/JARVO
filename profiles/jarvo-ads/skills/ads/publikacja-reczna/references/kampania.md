---
reviewed: "2026-10-11"
---
# `kampania.json`: format paczki

Ścieżki plików względem katalogu `kampania.json`. Kwoty w walucie konta (domyślnie PLN). Daty `RRRR-MM-DD`.

## Meta (Facebook, Instagram)

```json
{
  "platforma": "meta",
  "konto": "JARVO (PLN)",
  "kampania": {
    "nazwa": "JARVO_meta_leady_261015",
    "cel": "OUTCOME_LEADS",
    "kategorie_specjalne": [],
    "budzet": {"typ": "dzienny", "kwota": 50, "waluta": "PLN"},
    "od": "2026-10-15", "do": "2026-10-28"
  },
  "zestawy": [
    {"nazwa": "szeroko_PL_auto", "odbiorcy": {"lokalizacje": ["Polska"], "wiek": [25, 55], "plec": "wszyscy",
     "zainteresowania": []}, "miejsca": "Advantage+ (automatyczne)", "optymalizacja": "kontakty"}
  ],
  "reklamy": [
    {"nazwa": "T01_hook-pytanie_9x16_v1", "zestaw": "szeroko_PL_auto", "pliki": ["kreacje/film1.mp4"],
     "tekst": "…", "naglowek": "…", "opis": "", "cta": "SIGN_UP", "url": "https://jarvo.pl/start",
     "utm": {"utm_source": "meta", "utm_medium": "paid", "utm_campaign": "JARVO_meta_leady_261015", "utm_content": "T01"}}
  ]
}
```

- `cel`: `OUTCOME_AWARENESS`, `OUTCOME_TRAFFIC`, `OUTCOME_ENGAGEMENT`, `OUTCOME_LEADS`, `OUTCOME_APP_PROMOTION`,
  `OUTCOME_SALES` (w panelu: Rozpoznawalność, Ruch, Aktywność, Kontakty, Promowanie aplikacji, Sprzedaż).
- `cta`: `LEARN_MORE`, `SIGN_UP`, `SHOP_NOW`, `CONTACT_US`, `BOOK_NOW`, `DOWNLOAD`, `GET_QUOTE`, `SUBSCRIBE`,
  `APPLY_NOW`, `ORDER_NOW`.
- Teksty: tekst główny do 125 znaków, nagłówek do 40, opis do 30 widać bez „Więcej” (dłuższe: uwaga, nie błąd).
- Kreacje: JPG/PNG/WebP do 30 MB, MP4/MOV do 4 GB; proporcje 9:16, 4:5, 1:1 (16:9 tylko Feed); krótszy bok ≥ 1080.

## Google Ads (sieć wyszukiwania)

```json
{
  "platforma": "google",
  "kampania": {"nazwa": "JARVO_google_leady_261015", "typ": "search", "lokalizacje": ["Polska"], "jezyki": ["polski"],
    "budzet": {"typ": "dzienny", "kwota": 40}, "od": "2026-10-15", "do": "2026-11-14",
    "stawki": "Maksymalizacja kliknięć, limit CPC 3 zł"},
  "zestawy": [
    {"nazwa": "asystent-ai-firma", "slowa_kluczowe": ["\"asystent ai dla firmy\"", "[automatyzacja obsługi klienta]"],
     "wykluczenia": ["darmowy", "praca"],
     "reklama": {"naglowki": ["…3 do 15, każdy ≤ 30 znaków"], "opisy": ["…2 do 4, każdy ≤ 90 znaków"],
       "sciezki": ["asystent", "ai"], "url": "https://jarvo.pl/start", "utm": {"utm_source": "google", "utm_medium": "cpc"}}}
  ]
}
```

Limity Google są twarde (dłuższy tekst = błąd). Performance Max i YouTube: plan i instrukcja opisem, bez `paczka.py`.

## Co sprawdza `paczka.py`
Błąd (bez paczki): brak daty końca, budżet łączny ponad `--limit`, URL bez `https://`, brak pliku, nieobsługiwany
format, za duży plik, pusty tekst główny lub nagłówek, nieznany cel/CTA, zły zestaw, limity Google. Uwaga: dłuższe
teksty Meta, proporcje i rozdzielczość kreacji (ffprobe), brak UTM, brak wykluczeń, kampania Meta krótsza niż 7 dni,
nazwa poza konwencją, start w przeszłości.
