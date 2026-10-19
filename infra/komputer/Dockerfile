# Komputer Jarva (docs/KOMPUTER.md): pulpit Linux, na którym agent Operator klika i pisze. Osobny kontener bez
# kluczy floty: Xvnc tylko na gnieździe unix, xfwm4 z kompozytorem (bez niego zrzuty zasłoniętych okien są czarne),
# Chromium z drzewem dostępności, sterownik ekranu cua-driver (MIT, wersja i sumy z vendor/zrodla.yaml).
# Bez sudo, bez kompilatorów, bez serwera X na TCP. Buduje go deploy.sh i `jarvo komputer on` (obraz lokalny
# jarvo-komputer:local, przebudowa po zmianie infra/komputer/).
#
# Baza przypięta digestem indeksu (amd64 + arm64). Pakiety Debiana bez przypinania wersji, jak w infra/Dockerfile:
# każda budowa bierze bieżące poprawki bezpieczeństwa (Chromium!), a `jarvo komputer odswiez` buduje od nowa.
ARG DEBIAN_IMAGE=debian:trixie-slim@sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f

FROM ${DEBIAN_IMAGE} AS sterownik
ARG TARGETARCH
# cua-driver-rs 0.21.0 (tag cua-driver-rs-v0.21.0 = commit 70db98d1): ta wersja działa z przypiętym Hermesem
# (nowsze zmieniają argumenty kliknięcia, docs/KOMPUTER.md §6); sumy archiwów -binary z wydania i locka Hermesa
ARG CUA_DRIVER_VERSION=0.21.0
ARG CUA_DRIVER_SHA256_AMD64=cf29bfaad16737e31e72f38dad2a6424f24b21a4ac2edea885e83cb9d5034135
ARG CUA_DRIVER_SHA256_ARM64=6b3a308c6741dd8291aad22a308bd2ec8eb52eab64687be007ac86ceaf7e3307
RUN set -eux; \
    apt-get update; apt-get install -y --no-install-recommends ca-certificates curl; \
    case "${TARGETARCH:-amd64}" in \
      amd64) arch=linux-x86_64; sum="$CUA_DRIVER_SHA256_AMD64" ;; \
      arm64) arch=linux-arm64;  sum="$CUA_DRIVER_SHA256_ARM64" ;; \
      *) echo "Komputer Jarva: brak cua-driver dla architektury ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fsSL --retry 3 -o /tmp/cua.tgz \
      "https://github.com/trycua/cua/releases/download/cua-driver-rs-v${CUA_DRIVER_VERSION}/cua-driver-rs-${CUA_DRIVER_VERSION}-${arch}-binary.tar.gz"; \
    echo "${sum}  /tmp/cua.tgz" | sha256sum -c -; \
    # z archiwum bierzemy tylko sam program (bez SDK, modułu node i pomocnika Waylanda)
    member="$(tar -tzf /tmp/cua.tgz | grep -E '(^|/)cua-driver$' | head -n1)"; \
    mkdir -p "/opt/cua/${CUA_DRIVER_VERSION}"; \
    tar -xzf /tmp/cua.tgz -O "$member" > "/opt/cua/${CUA_DRIVER_VERSION}/cua-driver"; \
    chmod 0755 "/opt/cua/${CUA_DRIVER_VERSION}/cua-driver"; \
    rm -f /tmp/cua.tgz

FROM ${DEBIAN_IMAGE}
ARG CUA_DRIVER_VERSION=0.21.0
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    CUA_DRIVER_RS_TELEMETRY_ENABLED=0 \
    CUA_TELEMETRY_ENABLED=0 \
    CUA_TELEMETRY=0 \
    DO_NOT_TRACK=1 \
    CUA_DRIVER_RS_UPDATE_CHECK=false

# Xvnc (TigerVNC), xfwm4, D-Bus i AT-SPI (drzewo dostępności), gdbus (doctor sterownika), narzędzia X (xdpyinfo,
# xsetroot, xauth, xdotool do puszczania klawiszy po turze), Chromium z polskim interfejsem, fonty z polskimi
# znakami i emoji, iptables (filtr ruchu do sieci lokalnej), tini (PID 1 sprząta procesy), python3 (kanał K2),
# certutil (certyfikaty firmowego proxy z /usr/local/share/ca-certificates także w Chromium)
RUN set -eux; \
    apt-get update; \
    apt-get upgrade -y; \
    apt-get install -y --no-install-recommends \
      tini iptables procps tzdata ca-certificates python3 libnss3-tools \
      tigervnc-standalone-server xauth x11-utils x11-xserver-utils xdotool \
      xfwm4 dbus dbus-x11 at-spi2-core libglib2.0-bin \
      chromium chromium-l10n \
      fonts-dejavu-core fonts-liberation2 fonts-noto-color-emoji; \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/*

# pulpit: ekran, aplikacje i sterownik (jedyny z ciasteczkiem X); agent: przyszła powłoka (K5), bez dostępu do ekranu;
# grupa gniazda ma ten sam numer co hermes w jarvo-hermes (10000), więc tylko flota sięga do gniazd Komputera
RUN set -eux; \
    groupadd -g 10000 gniazda; \
    groupadd -g 10101 pulpit; useradd -u 10101 -g pulpit -G gniazda -m -d /home/pulpit -s /bin/bash pulpit; \
    groupadd -g 10102 agent;  useradd -u 10102 -g agent -m -d /home/agent -s /bin/bash agent; \
    chmod 0700 /home/pulpit /home/agent

COPY --from=sterownik /opt/cua /opt/cua
RUN ln -s "/opt/cua/${CUA_DRIVER_VERSION}/cua-driver" /usr/local/bin/cua-driver
COPY LICENSE-cua-driver.md /opt/cua/LICENSE.md
COPY chromium.json /etc/chromium/policies/managed/jarvo.json
COPY start.sh zdrowie.sh /opt/jarvo-komputer/
RUN chmod 0755 /opt/jarvo-komputer/start.sh /opt/jarvo-komputer/zdrowie.sh

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 CMD ["/opt/jarvo-komputer/zdrowie.sh"]
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/opt/jarvo-komputer/start.sh"]
