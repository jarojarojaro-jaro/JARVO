# Obraz floty Jarvo: oficjalny Hermes + narzędzia agentów (toolbox.yaml wszystkich profili).
#
#   docker build -f infra/Dockerfile -t jarvo-hermes:local \
#     --build-arg HERMES_IMAGE=nousresearch/hermes-agent:<wersja|digest> \
#     [--build-arg JARVO_EXTRAS="rembg media docling manim office"] .
#
# Zasady: entrypoint Hermesa bez zmian (s6 jako PID 1, zrzucenie uprawnień do użytkownika hermes),
# dane w /opt/data (wolumen), repo i build montowane tylko do odczytu (/opt/jarvo/repo, /opt/jarvo/build).
# Obraz celuje w VPS 8 GB RAM: jedna Chromium (ta z obrazu Hermesa) do renderowania i audytów,
# Lightpanda do codziennego przeglądania, rozpoznawanie mowy uruchamiane na żądanie, bez cache
# instalatorów w warstwach. Ciężkie, rzadko używane narzędzia są opcjonalne (JARVO_EXTRAS).
ARG HERMES_IMAGE=nousresearch/hermes-agent:latest
# Lightpanda (AGPL-3.0, niezmodyfikowana binarka): przeglądarka headless dla narzędzi browser_* agentów.
# Wersja przypięta digestem; wydanie ≥ 14 dni (ta sama kwarantanna co npm/PyPI).
ARG LIGHTPANDA_IMAGE=lightpanda/browser:0.4.0@sha256:01eb5d37ba537259d60ebfe32be49d3db4c7b6d1daac23b59b8532126fe30df0

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

# --- pakiety systemowe: dokumenty, OCR, metadane, fonty (polskie znaki), narzędzia PDF
RUN set -e; extras=" $(echo "$JARVO_EXTRAS" | tr ',' ' ') "; \
    pkgs="pandoc qpdf ocrmypdf tesseract-ocr tesseract-ocr-pol tesseract-ocr-eng \
          libimage-exiftool-perl jq sqlite3 \
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
    # na PATH natywna binarka zamiast nakładki w Node (jak robi postinstall przy instalacji globalnej)
    ln -sf ../agent-browser/bin/agent-browser-$ab node_modules/.bin/agent-browser && \
    ln -sf /opt/jarvo/node/node_modules/agent-browser/bin/agent-browser-$ab /usr/local/bin/agent-browser && \
    agent-browser --version && \
    # jedna Chromium dla wszystkich: playwright-core musi trafić w rewizję przeglądarki z obrazu Hermesa
    node -e "require('playwright-core').chromium.launch().then(b => b.close()).then(() => console.log('playwright-core → Chromium OK'))" && \
    npm cache clean --force && rm -rf /root/.npm/_cacache
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
    if [ -x /opt/jarvo/venv/bin/auto-editor ]; then /opt/jarvo/venv/bin/auto-editor --version; fi

# --- skrypty floty w obrazie (jarvo-stt: rozpoznawanie mowy Parakeet dla Hermesa i napisów)
COPY --chmod=0755 infra/bin/ /opt/jarvo/bin/
# Wiadomości głosowe: Hermes woła jarvo-stt jako lokalną komendę STT (stt.provider: local_command).
# Proces żyje tylko na czas transkrypcji; model (~0,65 GB) pobiera się raz do /opt/data/jarvo/models.
ENV HERMES_LOCAL_STT_COMMAND="/opt/jarvo/bin/jarvo-stt {input_path} --output-dir {output_dir} --language {language}" \
    JARVO_MODELS_DIR=/opt/data/jarvo/models

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
