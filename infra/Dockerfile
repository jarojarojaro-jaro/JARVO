# Obraz floty Jarvo: oficjalny Hermes + narzędzia agentów (toolbox.yaml wszystkich profili).
#
#   docker build -f infra/Dockerfile -t jarvo-hermes:local \
#     --build-arg HERMES_IMAGE=nousresearch/hermes-agent:<wersja|digest> \
#     [--build-arg JARVO_EXTRAS="rembg media docling manim office"] .
#
# Zasady: entrypoint Hermesa bez zmian (s6 jako PID 1, zrzucenie uprawnień do użytkownika hermes),
# dane w /opt/data (wolumen), repo i build montowane tylko do odczytu (/opt/jarvo/repo, /opt/jarvo/build).
# Obraz celuje w VPS 8 GB RAM: jedna Chromium (ta z obrazu Hermesa) do renderowania i audytów,
# Lightpanda do codziennego przeglądania, Camoufox (Firefox) tylko jako zapasowa przeglądarka po odmowie strony
# (jedna naraz, ~0,8 GB RAM na czas jednej strony), rozpoznawanie mowy uruchamiane na żądanie, bez cache
# instalatorów w warstwach. Ciężkie, rzadko używane narzędzia są opcjonalne (JARVO_EXTRAS).
# Wersja Hermesa przypięta tagiem i digestem: ten sam obraz bazowy w CI (gotowy obraz w GHCR) i u każdego.
# Aktualizacja Hermesa = zmiana tej linii, domyślnej w infra/docker-compose.yml i fleet.yaml (test pilnuje zgodności),
# a CI zbuduje nowy obraz floty. HERMES_IMAGE w compose/.env nadpisuje (wtedy obraz buduje się na miejscu).
ARG HERMES_IMAGE=nousresearch/hermes-agent:v2026.9.24@sha256:fca358f12efd65bfaaca05884166f15c0e2788375ca30d77061ac1ebc96452b7
# Lightpanda (AGPL-3.0, niezmodyfikowana binarka): przeglądarka headless dla narzędzi browser_* agentów.
# Wersja przypięta digestem; wydanie ≥ 14 dni (ta sama kwarantanna co npm/PyPI).
ARG LIGHTPANDA_IMAGE=lightpanda/browser:0.4.1@sha256:73f67d2dc0bc243f3a8c87065c9871c98b121197baf7b650df5da91b33b98f02

FROM ${LIGHTPANDA_IMAGE} AS lightpanda

# binarka z obrazu Lightpandy ma symbole debugowania (178 MB); po strip 68 MB
FROM ${HERMES_IMAGE} AS lightpanda-strip
USER root
COPY --from=lightpanda /usr/bin/lightpanda /tmp/lightpanda
RUN strip /tmp/lightpanda && /tmp/lightpanda version

FROM ${HERMES_IMAGE}

# Dodatki (spacje lub przecinki): rembg (wycinanie tła, ~0,5 GB), media (auto-editor, ~0,2 GB),
# docling (PDF→Markdown z modelami ML, ~1–2 GB), manim (animacje matematyczne + LaTeX, ~1 GB),
# office (LibreOffice do XLSX/PPTX→PDF, ~0,5 GB).
ARG JARVO_EXTRAS=""
ARG CLAUDE_SEO_REV=e77e783e38eeb738424eb72117abbd2dacdd88af

USER root
ENV DEBIAN_FRONTEND=noninteractive \
    UV_NO_CACHE=1

# --- pakiety systemowe: dokumenty, OCR, metadane, fonty (polskie znaki), narzędzia PDF;
#     adb: Twórca aplikacji steruje telefonem testowym (profil compose „android”, ~3 MB);
#     libgtk-3-0t64: biblioteka, bez której Firefox (Camoufox) nie startuje nawet bez okna (~60 MB); dbus-x11 spełnia
#     zależność dconf od magistrali sesji bez dbus-user-session, który ciągnąłby systemd
RUN set -e; extras=" $(echo "$JARVO_EXTRAS" | tr ',' ' ') "; \
    pkgs="pandoc qpdf ocrmypdf tesseract-ocr tesseract-ocr-pol tesseract-ocr-eng \
          libimage-exiftool-perl jq sqlite3 adb libgtk-3-0t64 dbus-x11 \
          fonts-dejavu fonts-noto-core fonts-noto-color-emoji fonts-inter"; \
    case "$extras" in *" manim "*) pkgs="$pkgs libcairo2-dev libpango1.0-dev pkg-config texlive-latex-base texlive-fonts-recommended";; esac; \
    case "$extras" in *" office "*) pkgs="$pkgs libreoffice-writer-nogui libreoffice-calc-nogui libreoffice-impress-nogui";; esac; \
    apt-get -o Acquire::Retries=3 update && \
    apt-get -o Acquire::Retries=3 install -y --no-install-recommends $pkgs && \
    rm -rf /var/lib/apt/lists/*

# --- przeglądarki
# 1) Chromium: jedna, z obrazu Hermesa (chrome-headless-shell Playwrighta). Służy do renderowania,
#    PDF, zrzutów, Lighthouse/axe i jako zapasowy silnik agent-browsera. Układ zależy od wersji obrazu:
#    nowsze zapisują ścieżkę w /etc/hermes/agent-browser-executable-path, starsze (≤ 0.21.x) mają
#    chrome-headless-shell w $PLAYWRIGHT_BROWSERS_PATH.
RUN set -e; p=""; \
    if [ -s /etc/hermes/agent-browser-executable-path ]; then p="$(cat /etc/hermes/agent-browser-executable-path)"; fi; \
    if [ -z "$p" ] || [ ! -x "$p" ]; then p="$(command -v chromium || true)"; fi; \
    if [ -z "$p" ]; then \
      p="$(find "${PLAYWRIGHT_BROWSERS_PATH:-/opt/hermes/.playwright}" /opt/hermes/tools -type f \
            \( -name chrome -o -name chromium -o -name chrome-headless-shell -o -name headless_shell \) \
            -perm -u+x 2>/dev/null | sort | tail -1)"; \
    fi; \
    [ -n "$p" ] || { echo "Nie znaleziono Chromium w obrazie Hermesa" >&2; exit 1; }; \
    ln -sf "$p" /usr/local/bin/chromium && echo "chromium -> $p"

# 2) Lightpanda: silnik agent-browsera dla browser_* (≈ 25–30 MB RAM na sesję zamiast ~300 MB Chromium);
#    Hermes sam przełącza na Chromium przy zrzutach ekranu i stronach, których Lightpanda nie obsłuży.
COPY --from=lightpanda-strip /tmp/lightpanda /usr/local/bin/lightpanda
# Uwaga: bez AGENT_BROWSER_EXECUTABLE_PATH, bo agent-browser użyłby go także dla silnika lightpanda;
# Chromium znajduje sam przez PATH (/usr/local/bin/chromium).
ENV CHROME_PATH=/usr/local/bin/chromium \
    PUPPETEER_SKIP_DOWNLOAD=1 \
    PUPPETEER_EXECUTABLE_PATH=/usr/local/bin/chromium

# --- narzędzia Node (wersje przypięte w infra/node/package.json; playwright-core dembrandta ujednolicony
#     przez "overrides" z wersją, której Chromium jest już w obrazie → bez dociągania drugiej przeglądarki)
COPY infra/node/package.json /opt/jarvo/node/package.json
RUN set -e; cd /opt/jarvo/node && \
    npm install --omit=dev --no-audit --no-fund && \
    # dembrandt: model ML tylko dla eksperymentalnej flagi --ai (nie używamy) → bez onnxruntime-node (~0,5 GB)
    rm -rf node_modules/onnxruntime-node node_modules/onnxruntime-common && \
    # agent-browser: zostaje tylko binarka tej platformy (paczka niesie 7 wariantów, ~90 MB)
    case "$(uname -m)" in x86_64) ab=linux-x64;; aarch64) ab=linux-arm64;; *) ab=unknown;; esac && \
    find node_modules/agent-browser/bin -name 'agent-browser-*' ! -name "agent-browser-$ab" -delete && \
    # bit wykonywania nadaje postinstall paczki, a ten jest zablokowany (allowScripts); paczka arm64 przychodzi bez niego
    chmod 0755 node_modules/agent-browser/bin/agent-browser-$ab && \
    # na PATH natywna binarka zamiast nakładki w Node (jak robi postinstall przy instalacji globalnej)
    ln -sf ../agent-browser/bin/agent-browser-$ab node_modules/.bin/agent-browser && \
    ln -sf /opt/jarvo/node/node_modules/agent-browser/bin/agent-browser-$ab /usr/local/bin/agent-browser && \
    agent-browser --version && \
    # jedna Chromium dla wszystkich: playwright-core musi trafić w rewizję przeglądarki z obrazu Hermesa.
    # Obraz Hermesa dla arm64 (Mac z Apple Silicon) ma tylko pełną Chromium starszej rewizji: wtedy dociągamy
    # chrome-headless-shell dokładnie tej wersji, której oczekuje playwright-core (~100 MB, tylko arm64)
    exp="$(node -e "process.stdout.write(require('playwright-core').chromium.executablePath())")" && \
    if [ ! -x "$exp" ]; then echo "Brak $exp: pobieram chrome-headless-shell dla playwright-core"; \
      PLAYWRIGHT_SKIP_BROWSER_GC=1 node node_modules/playwright-core/cli.js install --only-shell chromium; fi && \
    node -e "require('playwright-core').chromium.launch().then(b => b.close()).then(() => console.log('playwright-core → Chromium OK'))" && \
    npm cache clean --force && rm -rf /root/.npm/_cacache
# HyperFrames (wideo z HTML + GSAP; skille Wideografa wołają `npx hyperframes`): globalnie w obrazie, bo npx
# bierze paczkę z globalnego drzewa bez sieci (inaczej ściągał najnowszą przy pierwszym użyciu, a na świeżej
# instalacji bez sieci healthcheck padał). puppeteer-core w paczce używa Chromium obrazu (PUPPETEER_EXECUTABLE_PATH).
# Wersja ≥ 14 dni (npm min-release-age obrazu Hermesa), ta sama co skille z vendor/skills.lock.yaml (commit po v0.8.78).
ARG HYPERFRAMES_VERSION=0.8.78
RUN set -e; npm install -g --no-audit --no-fund "hyperframes@${HYPERFRAMES_VERSION}" && \
    hyperframes --version && npm cache clean --force && rm -rf /root/.npm/_cacache
# render przez Chromium z obrazu (bez tego hyperframes ściąga własny chrome-headless-shell i pada bez unzip);
# bez telemetrii (PostHog) i bez sprawdzania nowszej wersji: wersja jest przypięta wyżej
ENV HYPERFRAMES_BROWSER_PATH=/usr/local/bin/chromium \
    HYPERFRAMES_NO_TELEMETRY=1 \
    HYPERFRAMES_NO_UPDATE_CHECK=1
ENV NODE_PATH=/opt/jarvo/node/node_modules
ENV PATH="/opt/jarvo/bin:/opt/jarvo/node/node_modules/.bin:${PATH}:/opt/jarvo/venv/bin"

# --- narzędzia Pythona (osobny venv na Pythonie 3.12, żeby nie ruszać środowiska Hermesa).
# Interpreter pobrany przez uv musi leżeć poza /root, inaczej venv nie działa dla użytkownika hermes.
ENV UV_PYTHON_INSTALL_DIR=/opt/jarvo/uv-python
COPY infra/python/ /opt/jarvo/python/
RUN set -e; extras=" $(echo "$JARVO_EXTRAS" | tr ',' ' ') "; \
    uv venv /opt/jarvo/venv --python 3.12 && \
    VIRTUAL_ENV=/opt/jarvo/venv uv pip install -r /opt/jarvo/python/requirements-tools.txt && \
    for x in rembg media docling manim; do \
      case "$extras" in *" $x "*) \
        pkg="$(case $x in media) echo auto-editor;; *) echo $x;; esac)"; \
        spec="$(grep -E "^${pkg}(\[[^]]*\])?==" /opt/jarvo/python/requirements-optional.txt)"; \
        [ -n "$spec" ] || { echo "Brak pinu dla dodatku $x" >&2; exit 1; }; \
        VIRTUAL_ENV=/opt/jarvo/venv uv pip install "$spec";; \
      esac; \
    done && \
    # auto-editor ściąga swoją binarkę przy pierwszym uruchomieniu do site-packages (w runtime tylko do odczytu)
    if [ -x /opt/jarvo/venv/bin/auto-editor ]; then /opt/jarvo/venv/bin/auto-editor --version; fi && \
    # Playwright (dla Camoufoxa) na Node z obrazu zamiast własnej kopii Node w paczce (−124 MB)
    pw=/opt/jarvo/venv/lib/python3.12/site-packages/playwright/driver && \
    ln -sf "$(command -v node)" "$pw/node" && "$pw/node" "$pw/package/cli.js" --version

# --- Camoufox (MPL-2.0): Firefox z podmienionym odciskiem przeglądarki, zapasowa przeglądarka Łowcy i Sherlocka
#     (`ostrozna.py`, wspólny skill `ostrozna-przegladarka`) tylko po odmowie zwykłej przeglądarki. Binarka z wydania
#     daijro/camoufox przypięta wersją i sumą SHA-256 dla amd64 i arm64 (wydanie ≥ 14 dni). Z paczki (1,3 GB) zostaje
#     ~0,35 GB: bez fontów macOS i Windows (~0,9 GB fontów Apple i Microsoft, których nie redystrybuujemy), więc
#     przeglądarka udaje tylko Linuksa (fonty Linuksa z paczki: Noto, Arimo, Tinos, Cousine; OFL i Apache-2.0).
#     Na końcu start bez sieci: strona z data: i navigator.webdriver = false.
ARG CAMOUFOX_VERSION=152.0.4-beta.30
ARG CAMOUFOX_SHA256_AMD64=5720d45b894ce1770543de024c6f10d514b38be560fa2dc3226b3d8586caf672
ARG CAMOUFOX_SHA256_ARM64=60447260af8bebdb0ec3f2aa72f687b879e5598367303de2e3fdbc7a5be8c124
RUN set -e; case "$(uname -m)" in x86_64) a=x86_64; s="$CAMOUFOX_SHA256_AMD64";; aarch64) a=arm64; s="$CAMOUFOX_SHA256_ARM64";; \
      *) echo "Camoufox: brak wydania dla $(uname -m)" >&2; exit 1;; esac; \
    d=/opt/jarvo/camoufox; t="$(mktemp -d)"; \
    curl -fsSL --retry 3 -o "$t/camoufox.zip" \
      "https://github.com/daijro/camoufox/releases/download/v${CAMOUFOX_VERSION}/camoufox-${CAMOUFOX_VERSION}-lin.${a}.zip" && \
    echo "$s  $t/camoufox.zip" | sha256sum -c - && \
    python3 -I -c "import os, sys, zipfile; z = zipfile.ZipFile(sys.argv[1]); pomin = ('fonts/macos/', 'fonts/windows/', 'fontconfig/macos/', 'fontconfig/windows/'); [os.chmod(z.extract(i, sys.argv[2]), ((i.external_attr >> 16) & 0o755) | 0o444) for i in z.infolist() if not i.is_dir() and not i.filename.startswith(pomin)]" "$t/camoufox.zip" "$d" && \
    printf '%s\n' "Camoufox ${CAMOUFOX_VERSION} (MPL-2.0), kod źródłowy: https://github.com/daijro/camoufox (tag v${CAMOUFOX_VERSION})." \
      "Binarka bez zmian; Jarvo pomija tylko fonty macOS i Windows z paczki. Licencje Firefoksa: about:license." > "$d/JARVO-ZRODLO.txt" && \
    HOME="$t" /opt/jarvo/venv/bin/python -c "from camoufox.sync_api import Camoufox; from camoufox import DefaultAddons; c = Camoufox(executable_path='$d/camoufox-bin', ff_version=${CAMOUFOX_VERSION%%.*}, headless=True, os='linux', geoip=False, exclude_addons=[DefaultAddons.UBO], i_know_what_im_doing=True); b = c.__enter__(); p = b.new_page(); p.goto('data:text/html,<title>ok</title>'); assert p.title() == 'ok' and p.evaluate('navigator.webdriver') is False; c.__exit__(None, None, None); print('Camoufox OK')" && \
    rm -rf "$t"

# --- skrypty floty w obrazie (jarvo-stt: rozpoznawanie mowy Parakeet dla Hermesa i napisów)
COPY --chmod=0755 infra/bin/ /opt/jarvo/bin/
# Wiadomości głosowe: Hermes woła jarvo-stt jako lokalną komendę STT (stt.provider: local_command).
# Proces żyje tylko na czas transkrypcji; model (~0,65 GB) pobiera się raz do /opt/data/jarvo/models.
ENV HERMES_LOCAL_STT_COMMAND="/opt/jarvo/bin/jarvo-stt {input_path} --output-dir {output_dir} --language {language}" \
    JARVO_MODELS_DIR=/opt/data/jarvo/models

# --- lektor angielski bez sieci (jarvo-tts): Paradee-8M v1.0 (Apache-2.0, int8 ONNX, 9 MB) w obrazie,
#     model spaCy en_core_web_sm 3.8.0 (MIT) dla G2P misaki. Pliki przypięte sumą sha256; na końcu próba mowy.
ARG PARADEE_URL=https://huggingface.co/sahilmahendrakar/Paradee-8M-v1.0/resolve/v1.0
ARG SPACY_EN_URL=https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
RUN set -e; d=/opt/jarvo/models/paradee; mkdir -p "$d" /tmp/spacy-en && \
    curl -fsSL "$PARADEE_URL/onnx/paradee_int8.onnx" -o "$d/paradee_int8.onnx" && \
    curl -fsSL "$PARADEE_URL/config.json" -o "$d/config.json" && \
    curl -fsSL "$PARADEE_URL/LICENSE" -o "$d/LICENSE" && \
    curl -fsSL "$SPACY_EN_URL" -o /tmp/spacy-en/en_core_web_sm-3.8.0-py3-none-any.whl && \
    printf '%s\n' \
      "60e8f8a1bc7c546488154e9d99ecac6e9c50baf3f4b684c5b0de48ea03b698eb  $d/paradee_int8.onnx" \
      "f24046974a3a8c747affefb45c7c504263a99d5081787908b16abe8f5ac94fcd  $d/config.json" \
      "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30  $d/LICENSE" \
      "1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85  /tmp/spacy-en/en_core_web_sm-3.8.0-py3-none-any.whl" \
      | sha256sum -c - && \
    VIRTUAL_ENV=/opt/jarvo/venv uv pip install --no-deps /tmp/spacy-en/en_core_web_sm-3.8.0-py3-none-any.whl && \
    rm -rf /tmp/spacy-en && \
    /opt/jarvo/bin/jarvo-tts --sprawdz

# --- claude-seo: runtime skryptów dla skilli SEO (ten sam commit co w vendor/skills.lock.yaml).
# Playwright przypięty do wersji, której Chromium jest w obrazie (requirements-claude-seo.txt).
RUN set -e; git init -q /opt/jarvo/vendor/claude-seo && cd /opt/jarvo/vendor/claude-seo && \
    git remote add origin https://github.com/AgriciDaniel/claude-seo && \
    git fetch -q --depth 1 origin "$CLAUDE_SEO_REV" && git checkout -q FETCH_HEAD && rm -rf .git && \
    uv venv /opt/jarvo/venvs/claude-seo --python 3.12 && \
    VIRTUAL_ENV=/opt/jarvo/venvs/claude-seo uv pip install -r requirements.txt \
      -c /opt/jarvo/python/requirements-claude-seo.txt && \
    /opt/jarvo/venvs/claude-seo/bin/python -c "from playwright.sync_api import sync_playwright as s; p = s().start(); p.chromium.launch().close(); p.stop(); print('claude-seo playwright → Chromium OK')"
ENV CLAUDE_PLUGIN_ROOT=/opt/jarvo/vendor/claude-seo
ENV CLAUDE_SEO_PYTHON=/opt/jarvo/venvs/claude-seo/bin/python

# --- branding Jarvo w dashboardzie Hermesa (MIT; licencja i autorzy: docs/SOURCES.md):
#     favicon, tytuł karty i nazwa w menu. Kod Hermesa bez zmian, tylko statyczne zasoby.
COPY branding/ /tmp/jarvo-brand/
RUN python3 /tmp/jarvo-brand/patch_dashboard.py /tmp/jarvo-brand && rm -rf /tmp/jarvo-brand

# --- katalogi punktów montowania (zawartość z wolumenów). Bez `chmod -R`: przepisałby cały
#     /opt/jarvo do nowej warstwy (+2,7 GB); instalatory i tak zostawiają pliki czytelne dla wszystkich.
RUN mkdir -p /opt/jarvo/repo /opt/jarvo/build /opt/jarvo/secrets && \
    chmod a+rx /opt/jarvo /opt/jarvo/repo /opt/jarvo/build /opt/jarvo/bin

ENV JARVO_KNOWLEDGE_DIR=/opt/data/jarvo/knowledge \
    JARVO_MISSIONS_DIR=/opt/data/jarvo/missions \
    JARVO_HERMES_SRC=/opt/hermes \
    HERMES_WRITE_SAFE_ROOT=/opt/data

LABEL org.opencontainers.image.title="jarvo-hermes" \
      org.opencontainers.image.description="Hermes Agent + narzędzia floty Jarvo"
# Entrypoint i CMD dziedziczone z obrazu Hermesa (s6-overlay).
