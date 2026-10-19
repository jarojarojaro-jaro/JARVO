#!/bin/bash
# Healthcheck Komputera Jarva (HEALTHCHECK w Dockerfile, `jarvo komputer status`): filtr ruchu ustawiony,
# ekran X odpowiada, gniazda są na miejscu: rfb.sock (ekran dla HQ) i cua.sock (wejście sterownika dla floty).
set -u
[[ -f /run/jarvo-komputer.gotowy ]] || { echo "pulpit jeszcze startuje albo filtr ruchu nie wstał"; exit 1; }
[[ -S /run/jarvo-komputer/rfb.sock ]] || { echo "brak gniazda ekranu /run/jarvo-komputer/rfb.sock"; exit 1; }
[[ -S /run/jarvo-komputer/cua.sock ]] || { echo "brak wejścia sterownika /run/jarvo-komputer/cua.sock"; exit 1; }
DISPLAY=:1 XAUTHORITY=/home/pulpit/.Xauthority timeout 5 xdpyinfo >/dev/null 2>&1 \
  || { echo "ekran X nie odpowiada"; exit 1; }
pgrep -u pulpit -x xfwm4 >/dev/null || { echo "menedżer okien nie działa"; exit 1; }
echo "ok"
