---
name: publikacja
description: "Publikacja (A2): tylko ze zgodą, przez kolejkę Postiz."
version: 1.0.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: [publishing, social, scheduling, approval]
    related_skills: [pakiet-kampanii]
  jarvo:
    agent: jarvo-studio
    autonomy: A2
    reviewed: "2026-09-26"
---

# Publikacja

**A2: tylko z wyraźną zgodą użytkownika**, zapisaną w karcie albo komentarzu (data + zakres, np.
„Decyzja użytkownika 2026-10-03: publikuj posty 1–5 z kalendarza na LinkedIn i IG”).
Brak zgody → `kanban_block(kind="needs_input", reason="Pakiet gotowy. Publikować? <co, gdzie, kiedy>")`.

## Ze zgodą
1. Zakres zgody = zakres działania. Nic ponad to (inne platformy, inne daty = nowa zgoda).
2. Kolejka **Postiz** (self-host na serwerze, `POSTIZ_URL` + `POSTIZ_API_KEY`): utwórz wpisy z kalendarza jako
   zaplanowane, z plikami z `out/`. Jeśli Postiz nie jest skonfigurowany: przygotuj paczkę do ręcznej publikacji
   (`out/do-publikacji/` + instrukcja) i powiedz to w raporcie.
3. Po zaplanowaniu: lista wpisów (platforma, data, link do podglądu w Postiz) w `out/RAPORT.md`, status w `kalendarz.csv` = „zaplanowane”.

## Nigdy
Publikacja z kont, do których użytkownik nie dał dostępu; odpowiadanie w imieniu użytkownika na komentarze/wiadomości;
uruchamianie lub zmiana budżetów reklam bez osobnej zgody.
