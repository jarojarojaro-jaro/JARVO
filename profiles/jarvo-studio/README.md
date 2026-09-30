# jarvo-studio: marketing i kreacja

Grafiki, copy i kampanie (filmy: [jarvo-wideo](../jarvo-wideo/README.md), Studio pisze brief). Spec: [docs/FLEET.md](../../docs/FLEET.md#jarvo-studio-marketing-i-kreacja).

| Element | Zawartość |
|---|---|
| `SOUL.md` | main prompt: marka jako prawo, format przed kreacją, kod przed AI dla tekstu, publikacja tylko za zgodą |
| `skills/studio/` | 6: pakiet-kampanii (+ brief wideo), grafika-social (+ szablon HTML), generacja-ai (obrazy), formaty-platform (+ specs), copy-pl, publikacja |
| skille zewnętrzne | 24: marketingskills (12), Anthropic (3), Hermes (7), impeccable (1), wspólny `hooki` (trzy warstwy hooka, 18 taktyk): `vendor/skills.lock.yaml` |
| `scripts/` | `render_html.cjs` (HTML → PNG w wielu rozmiarach), `check_media.py` (wymiary/długość/waga vs platformy) |
| `config.yaml` | model strong; `image_gen` przez OpenRouter; publikacja/reklamy/wysyłki → eskalacja |
| `quality/rubric.md` | rubryka sędziego |
