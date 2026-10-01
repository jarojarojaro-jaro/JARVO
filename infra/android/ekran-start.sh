#!/bin/sh
# ws-scrcpy widzi urządzenia z własnego serwera adb: łączymy go z telefonem testowym floty i pilnujemy połączenia
# (Redroid startuje dłużej niż ten kontener i bywa restartowany).
set -u
(
  while true; do
    adb connect "$JARVO_ANDROID_ADB" >/dev/null 2>&1
    sleep 15
  done
) &
exec node /app/index.js
