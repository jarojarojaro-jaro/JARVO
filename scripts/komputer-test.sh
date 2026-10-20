#!/bin/bash
# Test Komputera Jarva na żywo (docs/KOMPUTER.md §6): bramka floty → wejście → sterownik → Chromium.
#   bash scripts/komputer-test.sh        (Komputer włączony: jarvo komputer on)
# Stawia w Komputerze stronę testową (wyszukiwarka i koszyk z polem hasła, karty, BLIK, przyciskami płatności
# i kluczem API w treści) na 127.0.0.1:8765 i uruchamia klienta MCP (scripts/komputer_test.py) w jarvo-hermes jako hermes,
# dokładnie tą drogą, którą idzie Hermes. Przed testem i po nim sprząta stronę i zamyka jej karty i okna.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
die() { echo "komputer-test: $*" >&2; exit 1; }

docker exec jarvo-komputer /opt/jarvo-komputer/zdrowie.sh >/dev/null 2>&1 \
  || die "Komputer Jarva nie działa albo nie jest zdrowy (jarvo komputer on, jarvo komputer status)"
docker exec jarvo-hermes test -S /opt/jarvo/komputer/cua.sock || die "flota nie widzi gniazda cua.sock (jarvo up)"

sprzataj() {
  # okna podręczne i karty testowe (także z przerwanych przebiegów): Ctrl+W prawdziwym klawiszem (XTest) w każdym
  # oknie o tym tytule, jako właściciel, nie przez agenta; Chromium zamknięty do końca startuje sam od nowa
  for tytul in "Okno testowe Jarvo" "Sklep testowy Jarvo"; do
    docker exec -u pulpit -e DISPLAY=:1 -e XAUTHORITY=/home/pulpit/.Xauthority jarvo-komputer bash -c \
      'for _ in $(seq 1 30); do w=$(xdotool search --onlyvisible --name "$1" | head -1); [ -n "$w" ] || break
         xdotool windowactivate --sync "$w" key --clearmodifiers ctrl+w; sleep 0.3; done' _ "$tytul" >/dev/null 2>&1 || true
  done
  docker exec -u pulpit jarvo-komputer pkill -f 'http.server 8765' >/dev/null 2>&1 || true
  docker exec -u pulpit jarvo-komputer rm -rf /tmp/jarvo-test >/dev/null 2>&1 || true
}
trap sprzataj EXIT
sprzataj
docker exec -i -u pulpit jarvo-komputer bash -c 'mkdir -p /tmp/jarvo-test && cat > /tmp/jarvo-test/sklep.html' <<'HTML'
<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>Sklep testowy Jarvo</title></head><body>
<form onsubmit="return false"><label>Szukaj w sklepie <input name="q"></label> <button>Szukaj</button></form>
<h1>Koszyk</h1><form onsubmit="return false">
<p><label>E-mail <input name="email" type="email"></label></p>
<p><label>Hasło <input name="haslo" type="password"></label></p>
<p><label>Numer karty <input name="karta" autocomplete="cc-number"></label></p>
<p><label>Kod BLIK <input name="blik" inputmode="numeric"></label></p>
<p><label>Uwagi <textarea name="uwagi"></textarea></label></p>
<button type="button" accesskey="k">Kup teraz</button> <button type="button">Dodaj do koszyka</button> <a href="#x">Zaloguj się</a>
<input type="submit" value="Zapłać 129 zł"></form>
<p><button type="button" onclick="window.open('okno.html','okno','popup,left=520,top=320,width=420,height=320')">Pokaż szczegóły</button></p>
<p>Klucz API: sk-proj-ABCDEFGHIJKLMNOPQRSTUVWX1234567890</p></body></html>
HTML
docker exec -i -u pulpit jarvo-komputer bash -c 'cat > /tmp/jarvo-test/okno.html' <<'HTML'
<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>Okno testowe Jarvo</title></head><body>
<p>Do zapłaty: 129 zł</p><button type="button" style="width:220px;height:70px">Zapłać teraz</button></body></html>
HTML
docker exec -d -u pulpit jarvo-komputer python3 -I -m http.server 8765 --bind 127.0.0.1 --directory /tmp/jarvo-test
for _ in $(seq 1 30); do
  docker exec -u pulpit jarvo-komputer python3 -I -c \
    'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8765/sklep.html", timeout=1)' >/dev/null 2>&1 && break
  sleep 0.2
done

wznow() {   # jak `jarvo komputer wznow`: polecenie jako pulpit, któremu wejście pozwala zdjąć pauzę
  docker exec -u pulpit jarvo-komputer python3 -I -c 'import socket; s = socket.socket(socket.AF_UNIX)
s.connect("/run/jarvo-komputer/ster.sock"); s.sendall(b"{\"polecenie\": \"wznow\"}\n"); s.recv(4096)'
}

echo "Komputer Jarva: test bramki, wejścia i twardych zasad"
# klient w jarvo-hermes jako hermes; linia @@wznow to prośba o wznowienie przez właściciela
docker exec -u hermes jarvo-hermes python3 -I -c "$(cat "$ROOT/scripts/komputer_test.py")" \
  | while IFS= read -r linia; do
      if [[ $linia == "@@wznow" ]]; then wznow; else printf '%s\n' "$linia"; fi
    done
kod=${PIPESTATUS[0]}
exit "$kod"
