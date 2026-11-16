---
typ: blad
tagi: [jarvo, wlasciciel, zgoda, karty]
utworzono: 2026-11-17
zmieniono: 2026-11-17
status: aktualna
zrodlo: "sesja telegram 13.11 13:30 (InstaBox: 5 próśb o „tak”, odmowa po 6 min); 14.11 23:40 polecenie terminala dla właściciela; 16.11 rada „poproś właściciela” w ostrozna.py"
agent: jarvo
sygnatury: ["is a directly-listed tool, not a deferred one"]
wystapienia: 3
---
# Nie proś właściciela o to, co zrobisz sam

**Polecenie właściciela wprost to zgoda; czego nie masz w rozmowie (terminal, ekran), dajesz karcie albo zleceniu, a właściciel nie dostaje ani poleceń do wpisania, ani pytań o rzeczy, które flota zrobi sama.**

**Objaw:** 13.11 na „sam masz zrobić wszystko” Jarvo pięć razy pytał o „tak”, cztery razy wołał terminal przez `tool_call` (Hermes: „is a directly-listed tool, not a deferred one”) i po 6 minutach odpisał „tego nie zrobię sam”, bez karty. 14.11 bot kazał właścicielowi wpisać polecenie na serwerze; 16.11 skrypt radził „poproś właściciela o instalację”.

**Przyczyna:** w rozmowie Jarvo nie ma terminala, a brak narzędzia brał za brak zgody albo możliwości.

**Jak poprawnie:** narzędzie z listy wołasz wprost, nie przez `tool_call`. Czego w tej rozmowie nie masz, robi karta wykonawcy (ekran, telefon, terminal) albo zlecenie w `DLA-CLAUDE.md` (kod floty, serwer). Pytasz właściciela tylko o płatności, rzeczy nieodwracalne i to, czego flota nie umie (jedno pytanie z rekomendacją), nigdy o polecenie do wpisania.

## Powiązane
- hub: [[bledy/_hub-bledy|Księga błędów]]
- [[bledy/cloudflare nie przepuszcza komputera, krok na telefonie floty|Cloudflare nie przepuszcza Komputera]]
- [[bledy/treść zastępcza w wyniku wraca do wykonawcy|Treść zastępcza w wyniku]]
- [[fleet/lekcje|Księga lekcji floty]]
