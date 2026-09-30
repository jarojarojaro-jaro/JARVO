# jarvo-wideo: Wideograf

Filmy od tematu albo surowego nagrania do gotowego pliku na platformę. Spec: [docs/FLEET.md](../../docs/FLEET.md#jarvo-wideo-wideograf).

| Element | Zawartość |
|---|---|
| `SOUL.md` | main prompt: hook w 2 s, szkic przed finałem, najpierw własne i darmowe materiały, napisy zawsze, publikacja tylko za zgodą |
| `skills/wideo/` | 15: rodzaje-filmu (indeks + 9 plików rodzajów + kontrakt HTML; czytany tylko plik rodzaju), krotki-film (+ `references/plan.md`), scenariusz, material-stock, dobor-ujec, warianty-ab, montaz-nagran, clipmaker (+ master prompt i schemat planu), demo-strony, napisy, lektor-i-dzwiek, film-z-kodu, wideo-ai, formaty-wideo (+ specs), kontrola-wideo (+ rubryka 0–100) |
| skille zewnętrzne | 57: wspólne `transkrypcja-filmu` i `hooki` (trzy warstwy hooka, 18 taktyk), HyperFrames (12), marketingskills `video`, Hermes `manim-video` i `ai-presenter-video`, motion-broll, lemo-opuscar, anidoodle, Remotion (router `remotion-best-practices`), iart (5), bang-motion, pixel2motion, text-to-lottie, screenwriting (5), GSAP (8), Three.js (10), motion (3), claude-animation, slack-gif-creator: `vendor/skills.lock.yaml` |
| `scripts/` | `film.py` (plan → film: lektor Edge TTS, stock, napisy karaoke, muzyka, montaż, warianty), `stock.py` (Pexels/Pixabay), `kadry.py` (arkusz klatek, cięcia scen), `montaz.py` (cięcie, kadr 9:16, cisza, głośność, transkrypcja, napraw), `napisy.py` (SRT/ASS, wypalenie), `qa_wideo.py` (kontrola techniczna + strefy UI), `narzedzia.py` (instalacja silników wideo z kodu raz, przeglądarka z obrazu), `html_wideo.py` (animacja HTML / Lottie → klatki, arkusz, MP4/MOV; preset `jarvo` = nasz kontrakt), `inspiracje.py` (prompty twórców do rodzaju, pobierane w locie), `lektor_linie.py` (lektor PL dla lemo), `rytm.py` (BPM, takty, drop), `projekt.py` (projekt montażu z edytora HQ), `krytyka.py` (krytyka reżyserska: telefon, ocena osi), `assety.py` (zrzuty, logo, kolory ze strony produktu), `maskotka.py` (+ `maskotka/*.png`, mówiąca maskotka Jarvo), `wideo_lib.py`; build dokłada `edytor.py` i `edytor_napisy.js` (silnik edytora HQ), `retime.py` (szybszy film z kodu: przesuwa chwile na osi czasu, nie tnie MP4), `klipy.py` (clipmaker: długie nagranie → `przygotuj` transkrypcja, cięcia ujęć, arkusze → `sprawdz` plan → `zbuduj` edytowalne rolki 9:16/16:9 z napisami karaoke), `demo_strony.py` (demo strony: `rozpoznaj` elementy → `proba` scenariusza → `nagraj` MP4 z kursorem i napisami kroków + SRT) |
| `config.yaml` | model strong; `video_gen`/`image_gen` przez OpenRouter; lektor Edge TTS pl-PL; publikacja/wgrywanie/zakupy → eskalacja |
| `quality/rubric.md` | rubryka sędziego |

Klucze: `PEXELS_API_KEY` albo `PIXABAY_API_KEY` (darmowe) w dashboardzie Keys, profil główny: Jarvo rozdaje je agentom.
Bez klucza Wideograf pracuje na plikach użytkownika, generacjach AI i planszach.
Muzyka „losowa”: utwory z prawem użycia w `/opt/data/jarvo/knowledge/wideo/muzyka/` (albo `brands/<marka>/muzyka/`).

Zasoby (VPS 4 vCPU / 8 GB): render filmu 1080×1920 zajmuje chwilowo 0,5–0,65 GB RAM (x264 na 2 wątkach, dźwięk
w osobnym przebiegu), 11 s filmu ≈ 15–20 s renderu. Mocniejszy serwer: `JARVO_WIDEO_WATKI=4`,
`JARVO_WIDEO_ROWNOLEGLE=2` (sceny naraz). Cache ujęć i scen: `/opt/data/jarvo/cache/wideo` (`film.py cache --starsze-niz 14`).
