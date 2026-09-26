#!/usr/bin/env bash
# Jednorazowe przygotowanie świeżego VPS (Ubuntu 24.04+/Debian 12+, x86_64) pod flotę TARS.
#
#   curl -fsSL https://raw.githubusercontent.com/<ty>/TARS/<gałąź>/scripts/bootstrap-vps.sh -o bootstrap-vps.sh
#   sudo bash bootstrap-vps.sh --user tars --repo https://github.com/<ty>/TARS.git [--branch main] [--ssh-key "ssh-ed25519 ..."]
#
# Robi: aktualizacje, automatyczne łatki, użytkownik bez roota, twardy SSH (tylko klucze), UFW,
# Docker + compose, Tailscale (logowanie ręcznie), katalogi /srv/tars, klon repo, szablony env.
# NIE robi: logowania do Tailscale, wpisywania kluczy API, zamykania portu 22 (po sprawdzeniu Tailscale: --lock-ssh).
set -euo pipefail

USER_NAME="tars"
REPO=""
BRANCH="main"
SSH_KEY=""
LOCK_SSH=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --user) USER_NAME="$2"; shift 2 ;;
    --repo) REPO="$2"; shift 2 ;;
    --branch) BRANCH="$2"; shift 2 ;;
    --ssh-key) SSH_KEY="$2"; shift 2 ;;
    --lock-ssh) LOCK_SSH=1; shift ;;
    *) echo "Nieznana opcja: $1"; exit 2 ;;
  esac
done
[[ $EUID -eq 0 ]] || { echo "Uruchom jako root (sudo)."; exit 1; }

log() { printf '\n\033[1m▶ %s\033[0m\n' "$*"; }

if [[ $LOCK_SSH -eq 1 ]]; then
  log "Zamykam publiczny SSH (zostaje tylko przez Tailscale)"
  tailscale status >/dev/null || { echo "Tailscale nie działa: przerywam, żeby nie odciąć dostępu."; exit 1; }
  ufw delete allow OpenSSH || true
  ufw allow in on tailscale0 to any port 22 proto tcp
  ufw reload
  echo "OK. SSH tylko przez Tailscale: ssh $USER_NAME@$(tailscale ip -4 | head -1)"
  exit 0
fi

log "Aktualizacje systemu i pakiety bazowe"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y && apt-get upgrade -y
apt-get install -y ca-certificates curl git ufw unattended-upgrades jq restic sqlite3 fail2ban
dpkg-reconfigure -f noninteractive unattended-upgrades
timedatectl set-timezone Europe/Warsaw || true

log "Użytkownik $USER_NAME"
id "$USER_NAME" >/dev/null 2>&1 || adduser --disabled-password --gecos "" "$USER_NAME"
usermod -aG sudo "$USER_NAME"
install -d -m 700 -o "$USER_NAME" -g "$USER_NAME" "/home/$USER_NAME/.ssh"
if [[ -n "$SSH_KEY" ]]; then
  echo "$SSH_KEY" >> "/home/$USER_NAME/.ssh/authorized_keys"
elif [[ -f /root/.ssh/authorized_keys ]]; then
  cat /root/.ssh/authorized_keys >> "/home/$USER_NAME/.ssh/authorized_keys"
fi
chown "$USER_NAME:$USER_NAME" "/home/$USER_NAME/.ssh/authorized_keys" 2>/dev/null || true
chmod 600 "/home/$USER_NAME/.ssh/authorized_keys" 2>/dev/null || true
[[ -s "/home/$USER_NAME/.ssh/authorized_keys" ]] || { echo "Brak klucza SSH dla $USER_NAME (--ssh-key). Przerywam, żeby nie odciąć dostępu."; exit 1; }

log "SSH: tylko klucze, bez roota"
cat > /etc/ssh/sshd_config.d/10-tars.conf <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
X11Forwarding no
EOF
systemctl reload ssh || systemctl reload sshd || true

log "Firewall (UFW): domyślnie blokada przychodzących, SSH otwarty (do czasu Tailscale)"
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw --force enable

log "Docker Engine + compose"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
usermod -aG docker "$USER_NAME"
systemctl enable --now docker

log "Tailscale (logowanie zrobisz ręcznie: sudo tailscale up)"
command -v tailscale >/dev/null || curl -fsSL https://tailscale.com/install.sh | sh

log "Katalogi /srv/tars"
install -d -m 755 -o "$USER_NAME" -g "$USER_NAME" /srv/tars /srv/tars/compose /srv/tars/backups
# sekrety: edytuje je $USER_NAME, czyta kontener (grupa 10000 = użytkownik hermes); setgid → nowe pliki dziedziczą grupę
install -d -m 2750 -o "$USER_NAME" -g 10000 /srv/tars/secrets
# dane i build należą do użytkownika hermes w kontenerze (uid 10000)
install -d -m 755 -o 10000 -g 10000 /srv/tars/data /srv/tars/data/hermes /srv/tars/build
install -d -m 755 /srv/tars/data/valkey /srv/tars/data/uptime-kuma /srv/tars/data/beszel

if [[ -n "$REPO" && ! -d /srv/tars/repo/.git ]]; then
  log "Klon repo"
  sudo -u "$USER_NAME" git clone --branch "$BRANCH" "$REPO" /srv/tars/repo
fi

if [[ -d /srv/tars/repo ]]; then
  log "Szablony konfiguracji (uzupełnij je!)"
  cd /srv/tars/repo
  [[ -f /srv/tars/compose/.env ]] || { cp infra/env/compose.env.example /srv/tars/compose/.env; \
    sed -i -e "s/^SEARXNG_SECRET=.*/SEARXNG_SECRET=$(openssl rand -hex 32)/" \
           -e "s/^DASHBOARD_PASSWORD=.*/DASHBOARD_PASSWORD=$(openssl rand -hex 16)/" \
           -e "s/^DASHBOARD_SESSION_SECRET=.*/DASHBOARD_SESSION_SECRET=$(openssl rand -hex 32)/" \
           /srv/tars/compose/.env; }
  [[ -f /srv/tars/compose/tars.env ]] || cp infra/env/tars.env.example /srv/tars/compose/tars.env
  for f in infra/env/secrets/*.env.example; do
    target="/srv/tars/secrets/$(basename "$f" .example)"
    [[ -f "$target" ]] || cp "$f" "$target"
  done
  chown -R "$USER_NAME:$USER_NAME" /srv/tars/compose
  chown "$USER_NAME:10000" /srv/tars/secrets/*.env
  chmod 600 /srv/tars/compose/.env
  chmod 640 /srv/tars/secrets/*.env
fi

cat <<EOF

✅ Bootstrap zakończony. Dalej (jako $USER_NAME):
  1. sudo tailscale up                         # zaloguj serwer do swojej sieci Tailscale
  2. uzupełnij: /srv/tars/secrets/*.env, /srv/tars/compose/tars.env, /srv/tars/compose/.env (TARS_BIND_IP = tailscale ip -4)
  3. cd /srv/tars/repo && bash scripts/deploy.sh --first-run
  4. po sprawdzeniu, że SSH przez Tailscale działa: sudo bash scripts/bootstrap-vps.sh --lock-ssh
Pełna instrukcja: docs/RUNBOOK.md
EOF
