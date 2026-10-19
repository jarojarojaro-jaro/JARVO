#!/bin/bash
# Start Komputera Jarva (pod tini). Jako root tylko trzy rzeczy: filtr ruchu, katalogi i uruchomienie procesów
# jako użytkownik pulpit. Kolejność:
#   1. filtr wyjścia: internet tak; sieć lokalna, adresy chmury (169.254.169.254), Tailscale, adresy hosta z
#      KOMPUTER_BLOKADA i poczta (port 25) nie; IPv6 tylko lokalnie. Bez działającego filtra Komputer nie wstaje.
#      Potem start.sh uruchamia się ponownie bez NET_ADMIN w zbiorze uprawnień, więc nic w kontenerze filtra nie zmieni;
#   2. gniazda w /run/jarvo-komputer (wolumen wspólny z jarvo-hermes, tam /opt/jarvo/komputer): katalog pulpit:10000
#      2750, gniazda 0660 dla grupy 10000 (hermes); stare gniazda usuwamy;
#   3. pulpit: Xvnc (RFB tylko na gnieździe unix, X tylko z ciasteczkiem, bez TCP i bez gniazda abstrakcyjnego),
#      sesyjny D-Bus z AT-SPI włączonym przed Chromium, xfwm4 z kompozytorem;
#   4. wejście sterownika (wejscie.py: cua.sock z twardymi zasadami, ster.sock dla HQ) i Chromium z drzewem
#      dostępności; oba wracają po zakończeniu. Gdy padnie Xvnc, D-Bus albo xfwm4, kontener kończy się i Docker go
#      podnosi.
set -euo pipefail

GNIAZDA=/run/jarvo-komputer
GRUPA_GNIAZD=10000
DOM=/home/pulpit
RUNDIR=/run/user/10101
GOTOWY=/run/jarvo-komputer.gotowy          # dla zdrowie.sh: filtr i ekran działają (poza wspólnym wolumenem)
EKRAN="${KOMPUTER_EKRAN:-1440x900}"
log() { printf '[komputer] %s\n' "$*"; }
die() { log "BŁĄD: $*"; exit 1; }

filtr() {
  local ipt="" c s
  # zakresy, do których przeglądarka i programy w Komputerze nie mogą sięgać (RFC 1918, link-local z metadanymi
  # chmury, CGNAT/Tailscale, pętla zwrotna, zakresy specjalne, multicast)
  local zakazane=(0.0.0.0/8 10.0.0.0/8 100.64.0.0/10 127.0.0.0/8 169.254.0.0/16 172.16.0.0/12 192.0.0.0/24
                  192.0.2.0/24 192.168.0.0/16 198.18.0.0/15 198.51.100.0/24 203.0.113.0/24 224.0.0.0/4 240.0.0.0/4)
  local blokada="${KOMPUTER_BLOKADA:-}"
  for s in ${blokada//,/ }; do   # publiczne adresy hosta (jarvo komputer on, deploy.sh)
    if [[ $s =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}(/[0-9]{1,2})?$ ]]; then zakazane+=("$s")
    else log "KOMPUTER_BLOKADA: pomijam $s (tylko adresy IPv4)"; fi
  done
  for c in iptables-nft iptables-legacy; do
    if "$c" -w -L OUTPUT -n >/dev/null 2>&1; then ipt=$c; break; fi
  done
  [[ -n $ipt ]] || die "iptables nie działa (brak NET_ADMIN albo obsługi w jądrze); bez filtra Komputer nie wstaje"
  "$ipt" -w -N JARVO 2>/dev/null || "$ipt" -w -F JARVO
  "$ipt" -w -C OUTPUT -j JARVO 2>/dev/null || "$ipt" -w -I OUTPUT 1 -j JARVO
  "$ipt" -w -A JARVO -o lo -j RETURN                       # w tym DNS Dockera (127.0.0.11)
  for s in "${zakazane[@]}"; do
    "$ipt" -w -A JARVO -d "$s" -p tcp -j REJECT --reject-with tcp-reset
    "$ipt" -w -A JARVO -d "$s" -j REJECT --reject-with icmp-admin-prohibited
  done
  "$ipt" -w -A JARVO -p tcp --dport 25 -j REJECT --reject-with tcp-reset
  # IPv6: sieć jarvo-komputer-net go nie ma (bez enable_ipv6); gdyby działało (inna konfiguracja Dockera),
  # tylko pętla zwrotna
  if [[ "$(cat /proc/sys/net/ipv6/conf/all/disable_ipv6 2>/dev/null || echo 1)" != 1 ]]; then
    local ip6="${ipt/iptables/ip6tables}"
    if ! { { "$ip6" -w -N JARVO 2>/dev/null || "$ip6" -w -F JARVO; } \
           && { "$ip6" -w -C OUTPUT -j JARVO 2>/dev/null || "$ip6" -w -I OUTPUT 1 -j JARVO; } \
           && "$ip6" -w -A JARVO -o lo -j RETURN && "$ip6" -w -A JARVO -j REJECT; }; then
      die "IPv6 działa, a ip6tables nie: bez filtra Komputer nie wstaje"
    fi
  fi
  # próba: adres metadanych chmury i brama sieci Dockera (czyli host) muszą być odrzucone od razu
  python3 -I - <<'EOF' || die "filtr nie zadziałał: Komputer sięga do sieci lokalnej"
import socket, struct, sys
brama = "172.17.0.1"
for linia in open("/proc/net/route").read().splitlines()[1:]:
    p = linia.split()
    if len(p) > 2 and p[1] == "00000000":
        brama = socket.inet_ntoa(struct.pack("<I", int(p[2], 16)))
        break
for host, port in (("169.254.169.254", 80), (brama, 9119), (brama, 22)):
    s = socket.socket()
    s.settimeout(3)
    try:
        s.connect((host, port))
    except OSError:
        continue
    finally:
        s.close()
    print(f"[komputer] połączenie z {host}:{port} przeszło przez filtr", file=sys.stderr)
    sys.exit(1)
EOF
  log "filtr ruchu: $ipt, zablokowane ${#zakazane[@]} zakresów i port 25"
}

if [[ "${1:-}" != --po-filtrze ]]; then
  rm -f "$GOTOWY"
  filtr
  # od tej chwili żaden proces z tego drzewa nie odzyska NET_ADMIN ani NET_RAW; grupa 10000 w uprawnieniach roota,
  # bo bez niej jądro zdejmuje bit setgid z katalogu gniazd (root nie należy do grupy, a nie ma CAP_FSETID)
  exec setpriv --bounding-set=-net_admin,-net_raw --groups="$GRUPA_GNIAZD" -- "$0" --po-filtrze
fi

[[ $EKRAN =~ ^[0-9]{3,4}x[0-9]{3,4}$ ]] || die "KOMPUTER_EKRAN=$EKRAN: podaj szerokość x wysokość, np. 1440x900"

# 2. katalogi i gniazda
install -d -m 2750 -o pulpit -g "$GRUPA_GNIAZD" "$GNIAZDA"
find "$GNIAZDA" -mindepth 1 -maxdepth 1 \( -type s -o -type l \) -delete
install -d -m 0755 -o root -g root /run/user
install -d -m 0700 -o pulpit -g pulpit "$RUNDIR"
install -d -m 1777 -o root -g root /tmp/.X11-unix
# /home to wolumen (stan przeglądarki przetrwa restart, `jarvo komputer wyczysc` go kasuje)
install -d -m 0700 -o pulpit -g pulpit "$DOM"
install -d -m 0700 -o agent -g agent /home/agent
for d in Pobrane .config .config/chromium .cua-driver .cua .pki .pki/nssdb; do
  install -d -m 0700 -o pulpit -g pulpit "$DOM/$d"
done
printf '{"telemetry_enabled": false, "update_check_enabled": false}\n' > "$DOM/.cua-driver/config.json"
printf '[telemetry]\nenabled = "off"\n' > "$DOM/.cua/config.toml"
chown pulpit:pulpit "$DOM/.cua-driver/config.json" "$DOM/.cua/config.toml"
rm -f "$DOM"/.config/chromium/Singleton*

jako_pulpit() {
  setpriv --reuid=pulpit --regid=pulpit --init-groups --no-new-privs --inh-caps=-all --bounding-set=-all -- \
    env -i HOME="$DOM" USER=pulpit LOGNAME=pulpit SHELL=/bin/bash PATH=/usr/local/bin:/usr/bin:/bin \
    LANG=C.UTF-8 LC_ALL=C.UTF-8 TZ="${TZ:-Europe/Warsaw}" DISPLAY=:1 XAUTHORITY="$DOM/.Xauthority" \
    XDG_RUNTIME_DIR="$RUNDIR" DBUS_SESSION_BUS_ADDRESS="unix:path=$RUNDIR/bus" \
    CUA_DRIVER_RS_TELEMETRY_ENABLED=0 CUA_TELEMETRY_ENABLED=0 CUA_TELEMETRY=0 DO_NOT_TRACK=1 \
    CUA_DRIVER_RS_UPDATE_CHECK=false "$@"
}

# certyfikaty własnego proxy (firma, piaskownica) z magazynu systemowego także dla Chromium (NSS pulpitu)
shopt -s nullglob
certy=(/usr/local/share/ca-certificates/*.crt)
suma="$(cat "${certy[@]}" /dev/null | sha256sum | cut -c1-64)"
if (( ${#certy[@]} )) && [[ "$(cat "$DOM/.pki/nssdb/.jarvo-ca" 2>/dev/null)" != "$suma" ]]; then
  rm -f "$DOM"/.pki/nssdb/*.db
  jako_pulpit certutil -N -d "sql:$DOM/.pki/nssdb" --empty-password
  i=0
  for c in "${certy[@]}"; do
    i=$((i + 1))
    jako_pulpit certutil -A -d "sql:$DOM/.pki/nssdb" -t "C,," -n "lokalny-$i" -i "$c" \
      || log "certyfikat $c: nie dodany do Chromium"
  done
  echo "$suma" > "$DOM/.pki/nssdb/.jarvo-ca"
fi
shopt -u nullglob

# 3. pulpit
cookie="$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
install -m 0600 -o pulpit -g pulpit /dev/null "$DOM/.Xauthority"
jako_pulpit xauth -q -f "$DOM/.Xauthority" add :1 . "$cookie"
unset cookie

trap 'trap - TERM INT; log "zatrzymanie"; rm -f "$GOTOWY"; kill 0 2>/dev/null; exit 0' TERM INT

jako_pulpit Xvnc :1 -geometry "$EKRAN" -depth 24 -dpi 96 -desktop "Komputer Jarva" \
  -rfbport -1 -rfbunixpath "$GNIAZDA/rfb.sock" -rfbunixmode 0660 -SecurityTypes None -AlwaysShared \
  -nolisten tcp -nolisten local -auth "$DOM/.Xauthority" -SendCutText=0 &
XVNC=$!
for _ in $(seq 1 100); do jako_pulpit xdpyinfo >/dev/null 2>&1 && break; sleep 0.1; done
jako_pulpit xdpyinfo >/dev/null 2>&1 || die "Xvnc nie wstał"

jako_pulpit dbus-daemon --session --nofork --nopidfile --address="unix:path=$RUNDIR/bus" &
DBUS=$!
for _ in $(seq 1 50); do [[ -S $RUNDIR/bus ]] && break; sleep 0.1; done
[[ -S $RUNDIR/bus ]] || die "D-Bus nie wstał"

# szyna dostępności (AT-SPI) włączona przed aplikacjami: Chromium sprawdza ją tylko przy starcie i bez
# IsEnabled/ScreenReaderEnabled nie wystawia drzewa (sterownik widzi wtedy samo okno, nawet z
# --force-renderer-accessibility); w świeżym kontenerze nikt jej jeszcze nie włączył, więc robimy to sami
a11y() { jako_pulpit gdbus call --session --dest org.a11y.Bus --object-path /org/a11y/bus "$@" >/dev/null 2>&1; }
a11y --method org.a11y.Bus.GetAddress || true
a11y --method org.freedesktop.DBus.Properties.Set org.a11y.Status IsEnabled "<true>" || true
a11y --method org.freedesktop.DBus.Properties.Set org.a11y.Status ScreenReaderEnabled "<true>" || true
for _ in $(seq 1 50); do jako_pulpit xprop -root AT_SPI_BUS 2>/dev/null | grep -q unix: && break; sleep 0.1; done
jako_pulpit xprop -root AT_SPI_BUS 2>/dev/null | grep -q unix: || log "szyna AT-SPI nie wstała: sterownik zobaczy tylko okna"

jako_pulpit xsetroot -solid '#1c1f29' || true
jako_pulpit xfwm4 --compositor=on --sm-client-disable &
WM=$!
for _ in $(seq 1 50); do jako_pulpit xprop -root _NET_SUPPORTING_WM_CHECK >/dev/null 2>&1 && break; sleep 0.1; done

# 4. wejście sterownika (cua.sock, ster.sock): przed Chromium, żeby śledzenie fokusu (AT-SPI) widziało każde pole
wejscie() {
  while :; do
    jako_pulpit python3 -I /opt/jarvo-komputer/wejscie.py || true
    log "wejście sterownika zakończyło się; start ponownie za 2 s"
    sleep 2
  done
}
wejscie &
for _ in $(seq 1 100); do [[ -S $GNIAZDA/cua.sock ]] && break; sleep 0.1; done
[[ -S $GNIAZDA/cua.sock ]] || log "wejście sterownika jeszcze nie wstało (cua.sock)"

# flagi przeglądarki w /etc/chromium.d/jarvo (infra/komputer/chromium-flagi)
przegladarka() {
  local pref="$DOM/.config/chromium/Default/Preferences"
  while :; do
    rm -f "$DOM"/.config/chromium/Singleton*
    # po restarcie kontenera bez dymka „Przywrócić strony?” (Chromium zamknięty przez Dockera, nie przez awarię)
    [[ -f $pref ]] && jako_pulpit sed -i -e 's/"exit_type":"Crashed"/"exit_type":"Normal"/' \
      -e 's/"exited_cleanly":false/"exited_cleanly":true/' "$pref"
    jako_pulpit chromium --start-maximized >/dev/null 2>&1 || true
    sleep 2
  done
}
przegladarka &

touch "$GOTOWY"
log "pulpit gotowy: ekran $EKRAN, gniazda $GNIAZDA/rfb.sock i cua.sock, cua-driver $(readlink /usr/local/bin/cua-driver | cut -d/ -f4)"
wait -n "$XVNC" "$DBUS" "$WM" || true
rm -f "$GOTOWY"
die "Xvnc, D-Bus albo xfwm4 się zakończył: kontener startuje od nowa"
