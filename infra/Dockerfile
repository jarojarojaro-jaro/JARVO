# Obraz floty TARS: oficjalny Hermes + narzędzia agentów (toolbox.yaml wszystkich profili).
#
#   docker build -f infra/Dockerfile -t tars-hermes:local \
#     --build-arg HERMES_IMAGE=nousresearch/hermes-agent:<wersja|digest> .
#
# Zasady: entrypoint Hermesa bez zmian (s6 jako PID 1, zrzucenie uprawnień do użytkownika hermes),
# dane w /opt/data (wolumen), repo i build montowane tylko do odczytu (/opt/tars/repo, /opt/tars/build).
ARG HERMES_IMAGE=nousresearch/hermes-agent:latest
FROM ${HERMES_IMAGE}

ARG INSTALL_DOCLING=0
ARG INSTALL_MANIM=0
ARG CLAUDE_SEO_REV=e77e783e38eeb738424eb72117abbd2dacdd88af

USER root
ENV DEBIAN_FRONTEND=noninteractive

# --- pakiety systemowe: dokumenty, OCR, metadane, fonty (polskie znaki), narzędzia PDF
RUN apt-get -o Acquire::Retries=3 update && \
    apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
      pandoc qpdf ocrmypdf tesseract-ocr tesseract-ocr-pol tesseract-ocr-eng \
      libimage-exiftool-perl jq sqlite3 \
      fonts-dejavu fonts-noto-core fonts-noto-color-emoji fonts-inter \
    && if [ "$INSTALL_MANIM" = "1" ]; then \
         apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
           libcairo2-dev libpango1.0-dev pkg-config texlive-latex-base texlive-fonts-recommended ; \
       fi \
    && rm -rf /var/lib/apt/lists/*

# --- przeglądarka: jedna Chromium z obrazu Hermesa dla Lighthouse, Playwright i skryptów.
# Układ zależy od wersji obrazu: nowsze zapisują ścieżkę w /etc/hermes/agent-browser-executable-path
# (pełna Chromium z menedżera narzędzi), starsze (≤ 0.21.x) mają chrome-headless-shell Playwrighta.
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
ENV CHROME_PATH=/usr/local/bin/chromium
# puppeteer (zależność critical/penthouse) nie ściąga własnej Chrome: używa tej samej przeglądarki
ENV PUPPETEER_SKIP_DOWNLOAD=1 \
    PUPPETEER_EXECUTABLE_PATH=/usr/local/bin/chromium

# --- narzędzia Node (wersje przypięte w infra/node/package.json)
COPY infra/node/package.json /opt/tars/node/package.json
RUN cd /opt/tars/node && npm install --omit=dev --no-audit --no-fund && npm cache clean --force
ENV NODE_PATH=/opt/tars/node/node_modules
ENV PATH="/opt/tars/node/node_modules/.bin:${PATH}:/opt/tars/venv/bin"
# dembrandt steruje własną wersją playwright-core; dociągamy pasującą Chromium do katalogu przeglądarek Hermesa
RUN cd /opt/tars/node && npx --no-install dembrandt install-browser || echo "dembrandt install-browser: pominięte (sprawdź healthcheck)"

# --- narzędzia Pythona (osobny venv na Pythonie 3.12, żeby nie ruszać środowiska Hermesa).
# Interpreter pobrany przez uv musi leżeć poza /root, inaczej venv nie działa dla użytkownika hermes.
ENV UV_PYTHON_INSTALL_DIR=/opt/tars/uv-python
COPY infra/python/ /opt/tars/python/
RUN uv venv /opt/tars/venv --python 3.12 && \
    VIRTUAL_ENV=/opt/tars/venv uv pip install -r /opt/tars/python/requirements-tools.txt && \
    # auto-editor ściąga swoją binarkę przy pierwszym uruchomieniu do site-packages (w runtime tylko do odczytu)
    /opt/tars/venv/bin/auto-editor --version && \
    if [ "$INSTALL_DOCLING" = "1" ]; then \
      VIRTUAL_ENV=/opt/tars/venv uv pip install "$(grep -E '^docling==' /opt/tars/python/requirements-optional.txt)"; \
    fi && \
    if [ "$INSTALL_MANIM" = "1" ]; then \
      VIRTUAL_ENV=/opt/tars/venv uv pip install "$(grep -E '^manim==' /opt/tars/python/requirements-optional.txt)"; \
    fi

# --- claude-seo: runtime skryptów dla skilli SEO (ten sam commit co w vendor/skills.lock.yaml)
RUN git init -q /opt/tars/vendor/claude-seo && cd /opt/tars/vendor/claude-seo && \
    git remote add origin https://github.com/AgriciDaniel/claude-seo && \
    git fetch -q --depth 1 origin "$CLAUDE_SEO_REV" && git checkout -q FETCH_HEAD && rm -rf .git && \
    uv venv /opt/tars/venvs/claude-seo --python 3.12 && \
    VIRTUAL_ENV=/opt/tars/venvs/claude-seo uv pip install -r requirements.txt
ENV CLAUDE_PLUGIN_ROOT=/opt/tars/vendor/claude-seo
ENV CLAUDE_SEO_PYTHON=/opt/tars/venvs/claude-seo/bin/python

# --- katalogi punktów montowania (zawartość z wolumenów)
RUN mkdir -p /opt/tars/repo /opt/tars/build /opt/tars/secrets && \
    chmod -R a+rX /opt/tars

ENV TARS_KNOWLEDGE_DIR=/opt/data/tars/knowledge \
    TARS_MISSIONS_DIR=/opt/data/tars/missions \
    TARS_HERMES_SRC=/opt/hermes \
    HERMES_WRITE_SAFE_ROOT=/opt/data

LABEL org.opencontainers.image.title="tars-hermes" \
      org.opencontainers.image.description="Hermes Agent + narzędzia floty TARS"
# Entrypoint i CMD dziedziczone z obrazu Hermesa (s6-overlay).
