---
name: schemat
description: "Schemat w rozmowie: SVG → PNG, gdy obraz wyjaśni szybciej."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [diagram, svg, explain, owner]
    related_skills: [prosty-polski]
  jarvo:
    agent: jarvo
    autonomy: A0
    reviewed: "2026-10-02"
---

# Schemat

Obraz często wyjaśnia szybciej niż tekst (pomysł Karpathy'ego). Rysujesz sam, w rozmowie, w kilka sekund:
piszesz SVG, narzędzie `schemat` robi z niego PNG i daje linię `MEDIA:<ścieżka>`.

## Kiedy użyć
- Właściciel prosi: „pokaż to na schemacie”, „narysuj”, „jak to się łączy?”.
- Odpowiedź opisuje przepływ, kto komu co oddaje, warstwy, oś czasu albo porównanie, a tekst miałby ponad 6 zdań.
  Wtedy wyślij schemat i 1–3 zdania zamiast ściany tekstu.
- Nie do: grafik dla klientów (Studio), filmów (wzorzec „Wyjaśnij mi filmem”), danych z wykresem do raportu.

## Kroki
1. Jedna myśl na rysunek. Zapisz ją jako tytuł (np. „Jak zlecenie trafia do agenta”).
2. Wybierz układ: **przepływ** (od lewej do prawej), **warstwy** (z góry na dół), **oś czasu**, **porównanie**
   (dwie kolumny), **drzewo** (od góry).
3. Napisz SVG według zasad niżej. Wywołaj `schemat(svg=…, tytul=…)`.
4. Wynik: wklej linię `MEDIA:…` i jedno zdanie, co rysunek pokazuje. Błąd narzędzia → popraw SVG raz, potem tekst.

## Zasady rysunku
- `width="1200"` i `height` 500–900, białe tło, tytuł u góry: `font-size` 28, pogrubiony.
- Do 12 prostokątów. Podpis w ramce do 4 słów, `font-size` ≥ 18. Ramka szersza niż tekst: `szerokość ≥ znaki × 0,6 × rozmiar + 32`.
- Strzałki z czasownikiem nad linią („zleca”, „oddaje”, „sprawdza”). Strzałka = `<marker>` w `<defs>`.
- Kolory: tusz `#1B1D22`, szary `#6B7280`, akcent Jarvo `#D4213D` tylko dla jednej najważniejszej rzeczy, wypełnienia jasne
  (`#F3F4F6`, `#FDECEF`). Kolor coś znaczy → legenda na dole.
- Krój: `font-family="Inter, Segoe UI, sans-serif"`; podpisy prostym polskim (skill `prosty-polski`).
- Bez zewnętrznych plików i skryptów: narzędzie blokuje sieć. Ikony rysuj prostymi kształtami albo emoji w `<text>`.

## Szkielet
```svg
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="520" font-family="Inter, Segoe UI, sans-serif">
  <defs><marker id="s" markerUnits="userSpaceOnUse" markerWidth="14" markerHeight="14" refX="12" refY="7" orient="auto">
    <path d="M0,0 L14,7 L0,14 z" fill="#1B1D22"/></marker></defs>
  <text x="40" y="56" font-size="28" font-weight="700" fill="#1B1D22">Jak zlecenie trafia do agenta</text>
  <rect x="40" y="200" width="240" height="96" rx="14" fill="#F3F4F6" stroke="#1B1D22" stroke-width="2"/>
  <text x="160" y="256" font-size="20" text-anchor="middle" fill="#1B1D22">Ty</text>
  <line x1="280" y1="248" x2="470" y2="248" stroke="#1B1D22" stroke-width="3" marker-end="url(#s)"/>
  <text x="375" y="232" font-size="18" text-anchor="middle" fill="#6B7280">zlecasz</text>
  <rect x="480" y="200" width="240" height="96" rx="14" fill="#FDECEF" stroke="#D4213D" stroke-width="2"/>
  <text x="600" y="256" font-size="20" text-anchor="middle" fill="#1B1D22">Jarvo</text>
</svg>
```
