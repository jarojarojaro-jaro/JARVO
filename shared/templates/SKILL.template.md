---
name: "{{nazwa-workflowu}}"
description: "{{Kiedy użyć, w jednym zdaniu. Od tego zależy, czy model wybierze ten skill.}}"
version: 0.1.0
author: Jarvo
license: MIT
metadata:
  hermes:
    tags: ["{{dziedzina}}", "{{typ}}"]
    related_skills: ["{{inny-skill}}"]
  tars:
    agent: "{{tars-xyz}}"
    autonomy: A1            # najwyższy poziom autonomii, jakiego wymaga ten workflow
    reviewed: "{{RRRR-MM-DD}}"
---

# {{Nazwa workflowu}}

## Kiedy użyć
- {{sytuacja}}

## Kiedy NIE używać
- {{sytuacja}} → zamiast tego `{{inny-skill}}` albo oddaj Jarvowi.

## Wejścia
| Wejście | Wymagane | Jeśli brak |
|---|---|---|
| {{np. URL strony}} | tak | zapytaj |

## Kroki
1. {{krok}}
   - ✅ Punkt kontrolny: {{co musi być prawdą, zanim pójdziesz dalej}}
2. {{krok, np. uruchom `scripts/{{skrypt}}.py --json`}}
3. {{…}}

## Wyjścia
- `{{ścieżka/plik}}`: {{opis}}
- raport w formacie z sekcji „Format raportu”

## Definition of Done
- [ ] {{mierzalny warunek}}
- [ ] {{…}}

## Typowe błędy
- {{błąd}} → {{jak uniknąć}}

## Format raportu
```
{{szablon raportu}}
```

## Wiedza
- `references/{{plik}}.md`: {{co zawiera}}
