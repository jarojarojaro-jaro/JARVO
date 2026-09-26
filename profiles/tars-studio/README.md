# tars-studio: marketing i kreacja

Grafiki, filmy, copy i kampanie. Spec: [docs/FLEET.md](../../docs/FLEET.md#tars-studio-marketing-i-kreacja).

| Element | Zawartość |
|---|---|
| `SOUL.md` | main prompt: marka jako prawo, format przed kreacją, kod przed AI dla tekstu, publikacja tylko za zgodą |
| `skills/studio/` | pakiet-kampanii, grafika-social (+ szablon HTML), film-z-kodu, generacja-ai, formaty-platform (+ specs), copy-pl, publikacja |
| skille zewnętrzne | marketingskills (13), HyperFrames (12), Anthropic (2), Hermes (8): `vendor/skills.lock.yaml` |
| `scripts/` | `render_html.cjs` (HTML → PNG w wielu rozmiarach), `check_media.py` (wymiary/długość/waga vs platformy), `subtitles.py` (napisy PL) |
| `config.yaml` | model strong; `image_gen` i `video_gen` przez OpenRouter; publikacja/reklamy/wysyłki → eskalacja |
| `quality/rubric.md` | rubryka sędziego |
