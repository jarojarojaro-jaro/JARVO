# jarvo-studio: marketing i kreacja

Grafiki, copy i kampanie (filmy: [jarvo-wideo](../jarvo-wideo/README.md), Studio pisze brief). Spec: [docs/FLEET.md](../../docs/FLEET.md#jarvo-studio-marketing-i-kreacja).

| Element | Zawartość |
|---|---|
| `SOUL.md` | main prompt: marka jako prawo, format przed kreacją, kod przed AI dla tekstu, publikacja tylko za zgodą |
| `skills/studio/` | 7: pakiet-kampanii (+ brief wideo), grafika-social (+ szablon HTML), generacja-ai (obrazy), formaty-platform (+ specs), copy-pl (+ sito AI-izmów), zywy-obraz (zdjęcie → pętla 5 s, warstwy PSD; lemo-wake), publikacja |
| skille zewnętrzne | 25: marketingskills (11), Anthropic (3), Hermes (7), impeccable (1), lemo-wake (2: `lemo-wake`, `lemo-wake-layers`; CC BY-NC 4.0, komercyjnie za zgodą autora), wspólny `hooki` (trzy warstwy hooka, 18 taktyk): `vendor/skills.lock.yaml` |
| `scripts/` | `render_html.cjs` (HTML → PNG w wielu rozmiarach), `check_media.py` (wymiary/długość/waga vs platformy), `lemo_wake.py` (instalacja lemo-wake raz: przypięty commit, pakiety, ścieżki modeli) |
| `config.yaml` | model strong; `image_gen` przez OpenRouter; publikacja/reklamy/wysyłki → eskalacja |
| `quality/rubric.md` | rubryka sędziego |
